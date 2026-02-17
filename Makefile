############################################
# CARGA AUTOMÁTICA DE VARIABLES DE ENTORNO
# (MLflow, etc.)
############################################

############################################
# PYTHON (estable)
############################################

PYTHON ?= python

# Verificar que existe python3.11
ifeq ($(shell command -v $(PYTHON) 2>/dev/null),)
$(error python3.11 no encontrado en el sistema. Instálalo antes de ejecutar make setup)
endif

$(info [INFO] Usando intérprete Python: $(PYTHON))

############################################
# CARGA AUTOMÁTICA DE VARIABLES DE ENTORNO
############################################

# Si existe .mlops4ofp/env.sh, se incluye automáticamente
# y sus variables pasan a todos los comandos make.
#
# El usuario NO necesita hacer `source` manualmente.
#
ifneq ("$(wildcard .mlops4ofp/env.sh)","")
include .mlops4ofp/env.sh
export
endif

############################################
# SETUP — MLOps4OFP (una sola vez)
############################################

SETUP_PY = setup/setup.py
SETUP_ENV = .mlops4ofp/env.sh
SETUP_CFG ?=

help-setup:
	@echo "=============================================="
	@echo " MLOps4OFP — SETUP DEL PROYECTO"
	@echo "=============================================="
	@echo ""
	@echo "Este proceso se ejecuta UNA SOLA VEZ por copia"
	@echo "de trabajo del proyecto."
	@echo ""
	@echo "Flujos disponibles:"
	@echo ""
	@echo "  make setup SETUP_CFG=setup/example_setup.yaml"
	@echo "      Setup no interactivo desde fichero YAML"
	@echo ""
	@echo "  make setup SETUP_CFG=setup/example_setup.yaml"
	@echo "      Setup no interactivo desde fichero YAML (obligatorio)"
	@echo ""
	@echo "  make check-setup"
	@echo "      Verifica que el setup es válido"
	@echo ""
	@echo "  make clean-setup"
	@echo "      Elimina solo la configuración de setup"
	@echo ""
	@echo "=============================================="

setup:
	@echo "==> Ejecutando setup del proyecto"
ifndef SETUP_CFG
	$(error Debes especificar SETUP_CFG=<fichero.yaml> (ej: setup/local.yaml o setup/remote.yaml))
endif
	@$(PYTHON) $(SETUP_PY) --config $(SETUP_CFG)


check-setup:
	@echo "==> Verificando entorno base"
	@.venv/bin/python setup/check_env.py
	@echo "==> Verificando configuración del proyecto"
	@.venv/bin/python setup/check_setup.py

clean-setup:
	@echo "==> Eliminando MLflow asociado al proyecto (si existe)"
	@echo "import yaml, pathlib, subprocess, os, shutil, json, sys" > clean_setup.py
	@echo "cfg_path = pathlib.Path('.mlops4ofp/setup.yaml')" >> clean_setup.py
	@echo "if not cfg_path.exists():" >> clean_setup.py
	@echo "    sys.exit(0)" >> clean_setup.py
	@echo "cfg = yaml.safe_load(cfg_path.read_text())" >> clean_setup.py
	@echo "ml = cfg.get('mlflow', {})" >> clean_setup.py
	@echo "if not ml.get('enabled', False):" >> clean_setup.py
	@echo "    sys.exit(0)" >> clean_setup.py
	@echo "uri = ml.get('tracking_uri', '')" >> clean_setup.py
	@echo "if uri.startswith('file:'):" >> clean_setup.py
	@echo "    path = uri.replace('file:', '')" >> clean_setup.py
	@echo "    if os.path.exists(path):" >> clean_setup.py
	@echo "        print(f'[INFO] Eliminando MLflow local en {path}')" >> clean_setup.py
	@echo "        shutil.rmtree(path)" >> clean_setup.py
	@echo "else:" >> clean_setup.py
	@echo "    print('[INFO] MLflow remoto detectado: eliminando experimentos del proyecto (prefijo F05_)')" >> clean_setup.py
	@echo "    try:" >> clean_setup.py
	@echo "        out = subprocess.check_output(['mlflow', 'experiments', 'list', '--format', 'json'])" >> clean_setup.py
	@echo "        experiments = json.loads(out)" >> clean_setup.py
	@echo "        for exp in experiments:" >> clean_setup.py
	@echo "            name = exp.get('name', '')" >> clean_setup.py
	@echo "            exp_id = exp.get('experiment_id')" >> clean_setup.py
	@echo "            if name.startswith('F05_') and exp_id:" >> clean_setup.py
	@echo "                print(f'[INFO] Eliminando experimento remoto {name}')" >> clean_setup.py
	@echo "                subprocess.run(['mlflow', 'experiments', 'delete', '--experiment-id', exp_id], check=False)" >> clean_setup.py
	@echo "    except Exception as e:" >> clean_setup.py
	@echo "        print('[WARN] No se pudo limpiar MLflow remoto:', e)" >> clean_setup.py

	@$(PYTHON) clean_setup.py  # Ejecuta el script Python creado temporalmente

	@echo "==> Eliminando entorno completo del proyecto ML"
	@rm -rf .mlops4ofp .dvc .dvc_storage local_dvc_store .venv executions
	@echo "[OK] Proyecto ML reinicializado. Ejecuta 'make setup' para reconstruir estructura base."
	@rm clean_setup.py  # Elimina el archivo temporal después de la ejecución


############################################
# ENTORNO DE EJECUCIÓN (PIPELINE)
############################################

ifeq ($(OS),Windows_NT)
PYTHON := .venv/Scripts/python.exe
DVC := .venv/Scripts/dvc.exe
else
ifneq ("$(wildcard .venv/bin/python3)","")
PYTHON := .venv/bin/python3
DVC := .venv/bin/dvc
else
PYTHON := python3
DVC := dvc
endif
endif

$(info [INFO] Usando intérprete Python: $(PYTHON))

############################################
# Objetivos genéricos por fase (reutilizables)
############################################

# Uso: make nb-run-generic PHASE=01_explore NOTEBOOK=notebooks/01_explore.ipynb VARIANT=v001
nb-run-generic: check-variant-format
	@test -f "$(NOTEBOOK)" || (echo "[ERROR] Notebook no existe: $(NOTEBOOK)"; exit 1)
	@echo "==> Ejecutando notebook FASE $(PHASE) para variante $(VARIANT)"
	@echo "    ACTIVE_VARIANT=$(VARIANT) jupyter nbconvert --to notebook --execute --inplace $(NOTEBOOK)"
	ACTIVE_VARIANT=$(VARIANT) jupyter nbconvert --to notebook --execute --inplace $(NOTEBOOK)
	@echo "[OK] Notebook ejecutado: $(NOTEBOOK)"

script-run-generic: check-variant-format
	@echo "==> Ejecutando script FASE $(PHASE) para variante $(VARIANT)"
	$(PYTHON) $(SCRIPT) --variant $(VARIANT)


############################################
# VARIANT GENERIC (crea la variante en disco y registra)
############################################
variant-generic: check-variant-format
	@echo "==> Creando variante $(PHASE):$(VARIANT)"
	@$(PYTHON) mlops4ofp/tools/params_manager.py create-variant --phase $(PHASE) --variant $(VARIANT) $(if $(RAW),--raw $(RAW)) $(EXTRA_SET_FLAGS)
	@echo "==> Variante creada: $(PHASE):$(VARIANT)"

publish-generic: check-variant-format
	@echo "==> Validando variante $(PHASE):$(VARIANT)"
	$(PYTHON) mlops4ofp/tools/traceability.py validate-variant --phase $(PHASE) --variant $(VARIANT)

	@echo "==> Registrando artefactos DVC"
	@for ext in $(PUBLISH_EXTS); do \
	  $(DVC) add $(VARIANTS_DIR)/$(VARIANT)/*.$$ext 2>/dev/null || true; \
	done

	@echo "==> Añadiendo a Git solo la variante publicada"
	@git add $(VARIANTS_DIR)/$(VARIANT) 2>/dev/null || true
	@git add $(VARIANTS_DIR)/$(VARIANT)/*.dvc 2>/dev/null || true
	@git add $(VARIANTS_DIR)/variants.yaml 2>/dev/null || true
	@git add dvc.yaml dvc.lock 2>/dev/null || true

	@git commit -m "publish variant: $(PHASE) $(VARIANT)" || true

	# Comprobaciones previas: remoto DVC 'storage' debe existir
	@if ! $(DVC) remote list 2>/dev/null | grep -q "^storage"; then \
		echo "[ERROR] Remote DVC 'storage' no configurado. Ejecuta 'make setup' o contacta con el admin"; exit 1; \
	fi

	# Determinamos modo publish
	@MODE=$$($(PYTHON) - <<'EOF'
	import yaml, pathlib
	cfg = pathlib.Path(".mlops4ofp/setup.yaml")
	if not cfg.exists():
		print("error")
	else:
		data = yaml.safe_load(cfg.read_text())
		print(data.get("git", {}).get("mode", "none"))
	EOF
	); \

	if [ "$$MODE" = "custom" ]; then \
		echo "[INFO] Remote 'publish' detectado: empujando a publish"; \
		git push publish HEAD:main || echo "[WARN] git push publish failed"; \
	elif [ "$$MODE" = "none" ]; then \
		echo "[INFO] Setup en modo git.mode=none: commit local únicamente"; \
	else \
		echo "[ERROR] Remote 'publish' no configurado y setup no en modo 'none'."; exit 1; \
	fi

	@echo "==> Push DVC"
	@$(DVC) push -r storage || (echo "[ERROR] dvc push failed"; exit 1)

	@echo "[OK] Publicación completada: variante $(PHASE):$(VARIANT)"

remove-generic: check-variant-format
	@echo "==> Comprobando si la variante $(PHASE):$(VARIANT) tiene hijos…"
	$(PYTHON) mlops4ofp/tools/traceability.py can-delete --phase $(PHASE) --variant $(VARIANT)

	@echo "==> Eliminando artefactos DVC asociados (si existen)"
	@for f in $(VARIANTS_DIR)/$(VARIANT)/*.dvc; do \
		if [ -f "$$f" ]; then \
			$(DVC) remove "$$f" || true; \
		fi; \
	done

	@echo "==> Eliminando carpeta completa de la variante"
	@rm -rf $(VARIANTS_DIR)/$(VARIANT)

	@echo "==> Actualizando registro de variantes"
	$(PYTHON) mlops4ofp/tools/params_manager.py delete-variant --phase $(PHASE) --variant $(VARIANT)

	@echo "==> Añadiendo a Git solo cambios relevantes"
	@git add $(VARIANTS_DIR) 2>/dev/null || true
	@git add dvc.yaml dvc.lock 2>/dev/null || true

	@git commit -m "remove variant: $(PHASE) $(VARIANT)" || true

	@MODE=$$($(PYTHON) - <<'EOF'
	import yaml, pathlib
	cfg = pathlib.Path(".mlops4ofp/setup.yaml")
	if not cfg.exists():
		print("error")
	else:
		data = yaml.safe_load(cfg.read_text())
		print(data.get("git", {}).get("mode", "none"))
	EOF
	); \
	if [ "$$MODE" = "custom" ]; then \
		git push publish HEAD:main || echo "[WARN] git push publish failed"; \
	elif [ "$$MODE" = "none" ]; then \
		echo "[INFO] Setup en modo git.mode=none: commit local únicamente"; \
	else \
		echo "[ERROR] Setup inválido o no configurado."; exit 1; \
	fi

	@echo "==> Push DVC para propagar eliminación"
	@$(DVC) push -r storage || echo "[WARN] dvc push failed"

	@echo "[OK] Variante $(PHASE):$(VARIANT) eliminada completamente."

check-results-generic: check-variant-format
	@test -n "$(PHASE)" || (echo "[ERROR] PHASE no definido"; exit 1)
	@test -n "$(VARIANTS_DIR)" || (echo "[ERROR] VARIANTS_DIR no definido"; exit 1)
	@test -n "$(VARIANT)" || (echo "[ERROR] VARIANT no definido"; exit 1)
	@test -n "$(CHECK_FILES)" || (echo "[ERROR] CHECK_FILES no definido"; exit 1)
	@echo "===== CHECKING $(PHASE) results ($(VARIANT)) ====="
	@MISSING=0; \
	for f in $(CHECK_FILES); do \
	  if [ -f $(VARIANTS_DIR)/$(VARIANT)/$$f ]; then \
	    echo "[OK] $$f"; \
	  else \
	    echo "[FAIL] Missing $$f"; \
	    MISSING=1; \
	  fi; \
	done; \
	echo "================================"; \
	if [ $$MISSING -eq 1 ]; then echo "[ERROR] Some files missing"; exit 1; fi

export-generic: check-variant-format
	@test -n "$(PHASE)" || (echo "[ERROR] PHASE no definido"; exit 1)
	@test -n "$(VARIANTS_DIR)" || (echo "[ERROR] VARIANTS_DIR no definido"; exit 1)
	@test -n "$(VARIANT)" || (echo "[ERROR] VARIANT no definido"; exit 1)
	@echo "==> Exportando artefactos de $(PHASE):$(VARIANT)"
	@mkdir -p $(EXPORT_DIR)
	@for f in $(EXPORT_FILES); do \
	  if [ -f $(VARIANTS_DIR)/$(VARIANT)/$$f ]; then \
	    cp $(VARIANTS_DIR)/$(VARIANT)/$$f $(EXPORT_DIR)/; \
	    echo "[OK] Copiado $$f"; \
	  else \
	    echo "[WARN] No encontrado $$f"; \
	  fi; \
	done
	@echo "[OK] Export completado: $(EXPORT_DIR)/"


remove-phase-all:
	@echo "==> Eliminando TODAS las variantes de la fase $(PHASE) (modo SEGURO)"
	@test -d "$(VARIANTS_DIR)" || \
	  (echo "[INFO] No existe $(VARIANTS_DIR). Nada que borrar."; exit 0)

	@for v in $$(ls $(VARIANTS_DIR) | grep '^v[0-9]\{3\}$$'); do \
	  echo "----> Eliminando $(PHASE):$$v"; \
	  $(MAKE) remove-generic PHASE=$(PHASE) VARIANTS_DIR=$(VARIANTS_DIR) VARIANT=$$v || exit 1; \
	done

	@echo "[OK] Fase $(PHASE) eliminada completamente (modo seguro)"




######################################...