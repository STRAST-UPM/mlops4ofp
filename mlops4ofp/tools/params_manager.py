import json
import yaml
import hashlib
import shutil
import re
from datetime import datetime, timezone
from pathlib import Path


# ===============================================================
# VALIDACIÓN DE PARÁMETROS SEGÚN traceability_schema.yaml
# ===============================================================

def _load_schema():
    schema_path = Path("mlops4ofp/schemas/traceability_schema.yaml")
    if not schema_path.exists():
        raise FileNotFoundError(f"No se encontró schema: {schema_path}")
    with open(schema_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def _validate_type(name, value, rule):
    """Valida el tipo según rule['type']."""
    expected = rule.get("type")
    if expected is None:
        return

    if expected == "string" and not isinstance(value, str):
        raise ValueError(f"'{name}' debe ser string, recibido: {type(value).__name__}")

    if expected == "int" and not isinstance(value, int):
        raise ValueError(f"'{name}' debe ser int, recibido: {type(value).__name__}")

    if expected == "float" and not isinstance(value, (int, float)):
        raise ValueError(f"'{name}' debe ser float, recibido: {type(value).__name__}")

    if expected == "bool" and not isinstance(value, bool):
        raise ValueError(f"'{name}' debe ser bool, recibido: {type(value).__name__}")

    if expected == "list":
        if not isinstance(value, list):
            raise ValueError(f"'{name}' debe ser lista, recibido: {type(value).__name__}")
        element_type = rule.get("element_type")
        if element_type:
            for elem in value:
                if element_type == "number" and not isinstance(elem, (int, float)):
                    raise ValueError(f"'{name}' contiene valor no numérico: {elem}")

    if expected == "dict" and not isinstance(value, dict):
        raise ValueError(f"'{name}' debe ser diccionario, recibido: {type(value).__name__}")


def _validate_constraints(name, value, rule):
    """Valida allowed, min, max, must_exist."""
    if "allowed" in rule:
        if value not in rule["allowed"]:
            raise ValueError(
                f"Valor inválido para '{name}': '{value}'. "
                f"Permitidos: {rule['allowed']}"
            )

    if "min" in rule and value < rule["min"]:
        raise ValueError(f"'{name}' debe ser >= {rule['min']}")

    if "max" in rule and value > rule["max"]:
        raise ValueError(f"'{name}' debe ser <= {rule['max']}")

    if rule.get("must_exist"):
        if not Path(value).expanduser().exists():
            raise ValueError(f"'{name}' apunta a un fichero inexistente: {value}")


# ==============================================================
# VALIDACIÓN DE PARÁMETROS SEGÚN traceability_schema.yaml
# ==============================================================

def validate_params(phase: str, params: dict, project_root: Path):
    """
    Valida que los parámetros de una variante cumplen el esquema definido
    en mlops4ofp/schemas/traceability_schema.yaml → param_rules.

    Soporta claves meta por fase, como:
      _free_keys: ["search_space"]
    que no se validan como parámetros, pero permiten claves sueltas.
    """

    schema_path = project_root / "mlops4ofp" / "schemas" / "traceability_schema.yaml"
    if not schema_path.exists():
        raise FileNotFoundError(f"No existe el esquema: {schema_path}")

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = yaml.safe_load(f)

    # -------------------------------
    # 1) Reglas de la fase
    # -------------------------------
    phase_rules = schema.get("param_rules", {}).get(phase)
    if phase_rules is None:
        raise RuntimeError(f"No existen reglas de parámetros para la fase {phase}")

    if not isinstance(phase_rules, dict):
        raise RuntimeError(f"param_rules[{phase}] debe ser un diccionario")

    # Claves meta (no corresponden a parámetros, p.ej. _free_keys)
    free_keys = set(phase_rules.get("_free_keys", []))

    # Claves de parámetros "reales" (las que sí tienen reglas)
    param_rule_keys = {k for k in phase_rules.keys() if not k.startswith("_")}

    allowed_keys = set(param_rule_keys)
    provided_keys = set(params.keys())

    # -------------------------------
    # 2) Parámetros desconocidos
    # -------------------------------
    unknown_keys = provided_keys - (allowed_keys | free_keys)
    if unknown_keys:
        raise ValueError(
            f"Parámetros no permitidos para fase {phase}: {sorted(unknown_keys)}\n"
            f"Parámetros válidos: {sorted(allowed_keys)}\n"
            f"Claves libres: {sorted(free_keys)}"
        )

    # -------------------------------
    # 3) Validación clave por clave
    # -------------------------------
    for key in param_rule_keys:
        rules = phase_rules[key]

        if not isinstance(rules, dict):
            raise RuntimeError(
                f"Reglas de parámetro inválidas para '{key}' en fase {phase}: "
                f"se esperaba dict, recibido {type(rules).__name__}"
            )

        # ---- Requerido ----
        if rules.get("required", False) and key not in params:
            raise ValueError(f"Falta parámetro obligatorio: {key}")

        value = params.get(key)

        # Si es opcional y no está, saltamos sin validar
        if value is None:
            continue

        expected_type = rules.get("type")

        if expected_type == "string":
            if not isinstance(value, str):
                raise ValueError(f"Parámetro {key} debe ser string, recibido: {type(value)}")

        elif expected_type == "number":
            if isinstance(value, str):
                try:
                    value = float(value) if "." in value else int(value)
                    params[key] = value
                except ValueError:
                    raise ValueError(f"Parámetro {key} debe ser numérico, recibido: {value}")
            if not isinstance(value, (int, float)):
                raise ValueError(f"Parámetro {key} debe ser numérico, recibido: {type(value)}")

        elif expected_type == "list":
            if not isinstance(value, list):
                raise ValueError(f"Parámetro {key} debe ser una lista")
            elem_type = rules.get("element_type")
            if elem_type == "number":
                for i, elem in enumerate(value):
                    if not isinstance(elem, (int, float)):
                        raise ValueError(
                            f"Elemento inválido en {key}[{i}]: debe ser numérico, recibido {elem}"
                        )

        elif expected_type == "dict":
            if not isinstance(value, dict):
                raise ValueError(f"Parámetro {key} debe ser un diccionario")

        else:
            raise RuntimeError(f"Tipo desconocido en schema para {key}: {expected_type}")

        # Enum
        if "enum" in rules:
            allowed = rules["enum"]
            if value not in allowed:
                raise ValueError(
                    f"Valor inválido para {key}: '{value}'. "
                    f"Debe ser uno de: {allowed}"
                )

    # -------------------------------
    # 4) Validación opcional específica de F01
    # -------------------------------
    if phase == "01_explore" and "raw_dataset_path" in params:
        raw_path = (project_root / params["raw_dataset_path"]).expanduser()
        if not raw_path.exists():
            raise ValueError(
                f"raw_dataset_path apunta a un fichero inexistente: {raw_path}"
            )

    return True

    # -------------------------------
    # 1) Comprobamos que exista sección param_rules para esta fase
    # -------------------------------
    phase_rules = schema.get("param_rules", {}).get(phase)
    if phase_rules is None:
        raise RuntimeError(f"No existen reglas de parámetros para la fase {phase}")

    allowed_keys = set(phase_rules.keys())
    provided_keys = set(params.keys())

    free_keys = phase_rules.get("_free_keys", [])
    allowed_keys = allowed_keys | set(free_keys)
    
    # -------------------------------
    # 2) Comprobar claves desconocidas
    # -------------------------------
    unknown_keys = provided_keys - allowed_keys
    if unknown_keys:
        raise ValueError(
            f"Parámetros no permitidos para fase {phase}: {sorted(unknown_keys)}\n"
            f"Parámetros válidos: {sorted(allowed_keys)}"
        )

    # -------------------------------
    # 3) Validación clave por clave
    # -------------------------------
    for key, rules in phase_rules.items():

        # ---- Requerido ----
        if rules.get("required", False) and key not in params:
            raise ValueError(f"Falta parámetro obligatorio: {key}")

        value = params.get(key)

        # Si es opcional y no está, saltamos sin validar
        if value is None:
            continue

        # -------------------------------------------------
        # Validación: tipo base
        # -------------------------------------------------
        expected_type = rules.get("type")

        if expected_type == "string":
            if not isinstance(value, str):
                raise ValueError(f"Parámetro {key} debe ser string, recibido: {type(value)}")

        elif expected_type == "number":
            if isinstance(value, str):
                try:
                    value = float(value) if "." in value else int(value)
                    params[key] = value  # actualizar el parámetro convertido
                except ValueError:
                    raise ValueError(f"Parámetro {key} debe ser numérico, recibido: {value}")
            if not isinstance(value, (int, float)):
                raise ValueError(f"Parámetro {key} debe ser numérico, recibido: {type(value)}")

        elif expected_type == "list":
            if not isinstance(value, list):
                raise ValueError(f"Parámetro {key} debe ser una lista")

            # Validar sub-tipo
            elem_type = rules.get("element_type")
            if elem_type == "number":
                for i, elem in enumerate(value):
                    if not isinstance(elem, (int, float)):
                        raise ValueError(
                            f"Elemento inválido en {key}[{i}]: debe ser numérico, recibido {elem}"
                        )

        elif expected_type == "dict":
            if not isinstance(value, dict):
                raise ValueError(f"Parámetro {key} debe ser un diccionario")

        else:
            raise RuntimeError(f"Tipo desconocido en schema para {key}: {expected_type}")

        # -------------------------------------------------
        # Validación enum (lista de valores permitidos)
        # -------------------------------------------------
        if "enum" in rules:
            allowed = rules["enum"]
            if value not in allowed:
                raise ValueError(
                    f"Valor inválido para {key}: '{value}'. "
                    f"Debe ser uno de: {allowed}"
                )

    # -------------------------------
    # 4) Validación opcional: raw_dataset_path debe existir
    # -------------------------------
    if phase == "01_explore" and "raw_dataset_path" in params:
        raw_path = (project_root / params["raw_dataset_path"]).expanduser()
        if not raw_path.exists():
            raise ValueError(
                f"raw_dataset_path apunta a un fichero inexistente: {raw_path}"
            )

    return True


class ParamsManager:
    """
    Gestor de variantes para una fase del pipeline MLOps4OFP.

    Esta versión implementa:
      ✔ Variantes como carpetas (vNNN)
      ✔ params.yaml por variante
      ✔ variants.yaml como registro
      ✔ Inyección de parámetros vía --set key=value
      ✔ Eliminación segura de variantes
      ✔ Conversión automática de listas y diccionarios
    """

    def __init__(self, phase_name: str, project_root: Path):
        self.phase = phase_name
        self.phase_dir = project_root / "executions" / phase_name
        self.base_params_file = self.phase_dir / "base_params.yaml"
        self.variants_registry_file = self.phase_dir / "variants.yaml"

        self._current_variant = None
        self._current_variant_dir = None

        # Crear carpeta si no existe
        self.phase_dir.mkdir(parents=True, exist_ok=True)

        # Crear variants.yaml vacío si no existe
        if not self.variants_registry_file.exists():
            with open(self.variants_registry_file, "w", encoding="utf-8") as f:
                yaml.safe_dump({"variants": {}}, f)


    def check_metadata_exists(self):
        vdir = self._current_variant_dir
        meta = vdir / f"{self.phase}_metadata.json"
        if not meta.exists():
            raise RuntimeError(
                f"Falta metadata obligatoria: {meta.name}"
            )

    # ============================================================
    # UTILIDADES
    # ============================================================

    def load_base_params(self):
        """Carga base_params.yaml y lo retorna como dict."""
        if not self.base_params_file.exists():
            raise FileNotFoundError(f"No existe base_params.yaml en {self.base_params_file}")
        with open(self.base_params_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _load_registry(self):
        """Carga variants.yaml."""
        with open(self.variants_registry_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {"variants": {}}

    def _save_registry(self, reg):
        """Guarda variants.yaml."""
        with open(self.variants_registry_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(reg, f)



    # ============================================================
    # PARSEADOR DE PARÁMETROS EXTRA (--set key=value)
    # ============================================================

    def _parse_extra_params(self, extra_params_list):
        """
        Convierte:
           ["cleaning_strategy=basic", 
            "nan_values=[-999, -1]",
            "error_values_by_column={'col':[1,2]}"]
        en:
           {"cleaning_strategy": "basic",
            "nan_values": [...],
            "error_values_by_column": {...}}
        """
        result = {}

        if not extra_params_list:
            return result

        for item in extra_params_list:
            if "=" not in item:
                raise ValueError(f"Formato inválido --set {item}")

            key, raw_value = item.split("=", 1)

            raw_value = raw_value.strip()

            # Intentar evaluar listas o diccionarios
            #if raw_value.startswith("[") or raw_value.startswith("{"):
            #    try:
            #        value = json.loads(raw_value.replace("'", "\""))
            #    except json.JSONDecodeError:
            #        raise ValueError(f"No se pudo interpretar {raw_value} como JSON válido")
            #else:
            try:
            # YAML safe_load interpreta correctamente:
            # "10" -> 10
            # "3.14" -> 3.14
            # "[1,2]" -> list
            # "{a:1}" -> dict
            # "true" -> True
            # "synchro" -> "synchro"
                value = yaml.safe_load(raw_value)
            except Exception:
                value = raw_value

            result[key] = value

        return result

    # ============================================================
    # CREACIÓN DE VARIANTE
    # ============================================================

    def create_named_variant(
        self,
        variant_name: str,
        raw_path_from_make: str = None,
        extra_params=None
    ):
        """Crea una variante explícita con nombre vNNN."""
        if not re.match(r"^v[0-9]{3}$", variant_name):
            raise ValueError(f"Nombre de variante inválido: {variant_name}")

        registry = self._load_registry()

        if variant_name in registry["variants"]:
            raise RuntimeError(f"La variante {variant_name} ya existe.")

        # ---------------------------------------------------------
        # Crear carpeta de variante
        # ---------------------------------------------------------
        variant_dir = self.phase_dir / variant_name
        variant_dir.mkdir(parents=True, exist_ok=True)

        # ---------------------------------------------------------
        # Cargar params base
        # ---------------------------------------------------------
        base_params = self.load_base_params()

        # Inyectar RAW si se proporcionó (solo fases que lo usen)
        if raw_path_from_make and self.phase != "06_packaging":
            base_params["raw_dataset_path"] = raw_path_from_make

        # Inyectar parámetros extra desde --set
        if extra_params:
            extra_dict = self._parse_extra_params(extra_params)
            for k, v in extra_dict.items():
                base_params[k] = v

        # ---------------------------------------------------------
        # Validar parámetros antes de crear la variante
        # ---------------------------------------------------------
        validate_params(self.phase, base_params, PROJECT_ROOT)

        # ---------------------------------------------------------
        # Guardar params.yaml de la variante
        # ---------------------------------------------------------
        params_path = variant_dir / "params.yaml"
        with open(params_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(base_params, f, sort_keys=False)

        # ---------------------------------------------------------
        # Registrar variante en variants.yaml
        # ---------------------------------------------------------
        entry = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "params_path": str(params_path),
        }

        # Caso especial F06: linaje múltiple
        if self.phase == "06_packaging":
            parents = base_params.get("parent_variants_f05")
            if parents:
                entry["parent_variants_f05"] = list(parents)

        registry["variants"][variant_name] = entry
        self._save_registry(registry)

        print(f"[OK] Variante creada: {variant_dir}")

    # ============================================================
    # ELIMINAR VARIANTE
    # ============================================================

    def delete_variant(self, variant_name: str):
        """Elimina una variante del filesystem y del registro."""
        registry = self._load_registry()

        if variant_name not in registry["variants"]:
            raise ValueError(f"La variante no existe: {variant_name}")

        # Borrar carpeta
        vdir = self.phase_dir / variant_name
        if vdir.exists():
            shutil.rmtree(vdir)

        # Eliminar registro
        del registry["variants"][variant_name]
        self._save_registry(registry)

        print(f"[OK] Variante eliminada: {variant_name}")

    # ============================================================
    # SELECCIÓN Y ACCESO A VARIANTE
    # ============================================================

    def set_current(self, variant_name: str):
        vdir = self.phase_dir / variant_name
        if not vdir.exists():
            raise RuntimeError(f"La variante {variant_name} no existe.")
        self._current_variant = variant_name
        self._current_variant_dir = vdir

    def current_variant_dir(self):
        return self._current_variant_dir

    # ============================================================
    # GUARDADO DE ARTEFACTOS EN LA VARIANTE
    # ============================================================

    def save_generated_params(self, params_dict: dict):
        """Guarda json dentro de la variante."""
        vdir = self._current_variant_dir
        # Usar el nombre de fichero consistente con la fase actual
        path = vdir / f"{self.phase}_params.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(params_dict, f, indent=2)
        return path

    def save_metadata(self, metadata: dict):
        vdir = self._current_variant_dir
        # Usar el nombre de fichero consistente con la fase actual
        path = vdir / f"{self.phase}_metadata.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        return path


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")

    # create
    p_create = sub.add_parser("create-variant")
    p_create.add_argument("--phase", required=True)
    p_create.add_argument("--variant", required=True)
    p_create.add_argument("--raw", required=False)
    p_create.add_argument("--set", action="append", required=False)

    # delete
    p_delete = sub.add_parser("delete-variant")
    p_delete.add_argument("--phase", required=True)
    p_delete.add_argument("--variant", required=True)

    args = parser.parse_args()

    PROJECT_ROOT = Path(__file__).resolve().parents[2]

    if args.command == "create-variant":
        pm = ParamsManager(args.phase, PROJECT_ROOT)
        pm.create_named_variant(
            args.variant,
            raw_path_from_make=args.raw,
            extra_params=args.set
        )

    elif args.command == "delete-variant":
        pm = ParamsManager(args.phase, PROJECT_ROOT)
        pm.delete_variant(args.variant)

    else:
        parser.print_help()
