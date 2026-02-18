SHELL := /bin/bash

############################################
# CARGA AUTOMÁTICA DE VARIABLES DE ENTORNO
# (MLflow, etc.)
############################################

############################################
# PYTHON (estable)
############################################


ifeq ($(OS),Windows_NT)
PYTHON_LOCAL ?= python
else
PYTHON_LOCAL ?= python3.11
endif


# Verificar que existe python3.11
ifeq ($(shell command -v $(PYTHON_LOCAL) 2>/dev/null),)
$(error python3.11 no encontrado en el sistema. Instálalo antes de ejecutar make setup)
endif

$(info [INFO] Usando interprete Python en local: $(PYTHON_LOCAL))

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
	@$(PYTHON_LOCAL) -m pip install pyyaml==6.0.1
	@$(PYTHON_LOCAL) $(SETUP_PY) --config $(SETUP_CFG)


check-setup:
	@echo "==> Verificando entorno base"
	@$(PYTHON) setup/check_env.py
	@echo "==> Verificando configuración del proyecto"
	@$(PYTHON) setup/check_setup.py

clean-setup:
	@echo "==> Eliminando MLflow asociado al proyecto (si existe)"
	@$(PYTHON_LOCAL) -c 'import yaml,pathlib,subprocess,os,shutil,json,sys;cfg_path=pathlib.Path(".mlops4ofp/setup.yaml");sys.exit(0) if not cfg_path.exists() else None;cfg=yaml.safe_load(cfg_path.read_text());ml=cfg.get("mlflow",{});sys.exit(0) if not ml.get("enabled",False) else None;uri=ml.get("tracking_uri","");(print(f"[INFO] Eliminando MLflow local en {path}") or shutil.rmtree(path)) if uri.startswith("file:") and os.path.exists(path:=uri.replace("file:","")) else (print("[INFO] MLflow remoto detectado: eliminando experimentos del proyecto (prefijo F05_)") or [print(f"[INFO] Eliminando experimento remoto {exp.get(\"name\",\"\")}") or subprocess.run(["mlflow","experiments","delete","--experiment-id",exp.get("experiment_id")],check=False) for exp in (experiments:=json.loads(subprocess.check_output(["mlflow","experiments","list","--format","json"]))) if exp.get("name","").startswith("F05_") and exp.get("experiment_id")] if True else None) if uri else None' 2>/dev/null || true
	@echo "==> Eliminando entorno completo del proyecto ML"
	@rm -rf .mlops4ofp .dvc .dvc_storage local_dvc_store .venv executions
	@echo "[OK] Proyecto ML reinicializado. Ejecuta 'make setup' para reconstruir estructura base."



############################################
# ENTORNO DE EJECUCIÓN (PIPELINE)
############################################

ifeq ($(OS),Windows_NT)
PYTHON := .venv/Scripts/python.exe
DVC := .venv/Scripts/dvc.exe
JUPYTER := .venv/Scripts/jupyter.exe
else
ifneq ("$(wildcard .venv/bin/python3)","")
PYTHON := .venv/bin/python3
DVC := .venv/bin/dvc
JUPYTER := .venv/bin/jupyter
else
PYTHON := python3
DVC := dvc
JUPYTER := jupyter
endif
endif

$(info [INFO] Usando interprete Python en venv: $(PYTHON))

############################################
# Objetivos genéricos por fase (reutilizables)
############################################

# Uso: make nb-run-generic PHASE=01_explore NOTEBOOK=notebooks/01_explore.ipynb VARIANT=v001
nb-run-generic: check-variant-format
	@test -f "$(NOTEBOOK)" || (echo "[ERROR] Notebook no existe: $(NOTEBOOK)"; exit 1)
	@echo "==> Ejecutando notebook FASE $(PHASE) para variante $(VARIANT)"
	@echo "    ACTIVE_VARIANT=$(VARIANT) $(JUPYTER) nbconvert --to notebook --execute --inplace $(NOTEBOOK)"
	ACTIVE_VARIANT=$(VARIANT) $(JUPYTER) nbconvert --to notebook --execute --inplace $(NOTEBOOK)
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
	@MODE=$$($(PYTHON) -c "import yaml,pathlib;cfg=pathlib.Path('.mlops4ofp/setup.yaml');print('error' if not cfg.exists() else yaml.safe_load(cfg.read_text()).get('git',{}).get('mode','none'))"); \
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

	@MODE=$$($(PYTHON) -c "import yaml,pathlib;cfg=pathlib.Path('.mlops4ofp/setup.yaml');print('error' if not cfg.exists() else yaml.safe_load(cfg.read_text()).get('git',{}).get('mode','none'))"); \
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




##########################################
# DVC REMOTE MANAGEMENT
##########################################

switch-remote-local:
	$(PYTHON) setup/switch_remote_local.py

switch-remote-public:
	$(PYTHON) setup/switch_remote_dagshub_public.py

switch-remote-private:
	$(PYTHON) setup/switch_remote_dagshub_private.py

check-remotes:
	$(PYTHON) setup/check_remotes.py

############################################
# FASE 01 — EXPLORE (VARIANTES + PUBLICACIÓN)
############################################

PHASE1=01_explore
NOTEBOOK1=notebooks/01_explore.ipynb
SCRIPT1=scripts/01_explore.py

# Directorio raíz de variantes para esta fase
VARIANTS_DIR_01 = executions/$(PHASE1)

############################################
# VALIDACIÓN DEL FORMATO DE VARIANTE: vNNN
############################################
# Uso: make <target> VARIANT=vNNN

check-variant-format:
	@test -n "$(VARIANT)" || (echo "[ERROR] Debes especificar VARIANT=vNNN"; exit 1)
	@if ! echo $(VARIANT) | grep -Eq '^v[0-9]{3}$$'; then \
	    echo "[ERROR] Formato incorrecto para VARIANT: $(VARIANT)"; \
	    echo "        Debe ser vNNN (ej.: v001, v023, v120)"; \
	    exit 1; \
	fi


############################################
# 1. EJECUCIÓN DEL NOTEBOOK
############################################
nb1-run:
	$(MAKE) nb-run-generic PHASE=$(PHASE1) NOTEBOOK=$(NOTEBOOK1) VARIANT=$(VARIANT)

############################################
# 2. EJECUCIÓN DE LA SCRIPT
############################################
script1-run:
	$(MAKE) script-run-generic PHASE=$(PHASE1) SCRIPT=$(SCRIPT1) VARIANT=$(VARIANT)

############################################
# 3. CREAR UNA VARIANTE DE LA FASE 01
############################################
# Uso:
#   make variant1 VARIANT=vNNN RAW=/ruta/dataset \
#        CLEANING_STRATEGY=basic \
#        NAN_VALUES="[-999999, None]" \
#        ERROR_VALUES='{"col1":[-1],"col2":[999]}'

variant1: check-variant-format
	@test -n "$(VARIANT)" || (echo "[ERROR] Uso: make variant1 VARIANT=v00X RAW=<path>"; exit 1)
	@test -n "$(RAW)" || (echo "[ERROR] Debes especificar RAW=/ruta/dataset.csv"; exit 1)
	@echo "==> Preparando parámetros específicos para Fase 01"
	@$(eval SET_LIST := )
	@$(if $(strip $(CLEANING_STRATEGY)),$(eval SET_LIST += --set cleaning_strategy='$(CLEANING_STRATEGY)'))
	@$(if $(strip $(NAN_VALUES)),$(eval SET_LIST += --set nan_values='$(NAN_VALUES)'))
	@$(if $(strip $(ERROR_VALUES)),$(eval SET_LIST += --set error_values_by_column='$(ERROR_VALUES)'))
	@$(if $(strip $(MAX_LINES)),$(eval SET_LIST += --set max_lines='$(MAX_LINES)'))
	@$(if $(strip $(MAX_LINE)),$(eval SET_LIST += --set max_line='$(MAX_LINE)'))
	@$(if $(strip $(FIRST_LINE)),$(eval SET_LIST += --set first_line='$(FIRST_LINE)'))
	@$(MAKE) variant-generic PHASE=$(PHASE1) VARIANT=$(VARIANT) RAW=$(RAW) EXTRA_SET_FLAGS="$(SET_LIST)"

############################################
# 4. PUBLICAR VARIANTE DE LA FASE 01
############################################
# Uso:
#   make publish1 VARIANT=v001

publish1: check-variant-format
	@test -n "$(VARIANT)" || (echo "[ERROR] Uso: make publish1 VARIANT=v00X"; exit 1)

	# delegar a objetivo genérico; PUBLISH_EXTS para fase 01: parquet json html
	$(MAKE) publish-generic PHASE=$(PHASE1) VARIANTS_DIR=$(VARIANTS_DIR_01) \
		PUBLISH_EXTS="parquet json html" VARIANT=$(VARIANT)


############################################
# 5. ELIMINAR VARIANTE (SI NO TIENE HIJOS)
############################################
# Uso:
#   make remove1 VARIANT=v001

remove1: check-variant-format
	$(MAKE) remove-generic PHASE=$(PHASE1) VARIANTS_DIR=$(VARIANTS_DIR_01) VARIANT=$(VARIANT)



############################################
# 6. REPRODUCIR VIA DVC (opcional)
############################################
script1-repro:
	@echo "==> Ejecutando dvc repro $(PHASE1)"
	$(DVC) repro $(PHASE1)
	$(DVC) push


############################################
# 7. CHEQUEO DE RESULTADOS
############################################
script1-check-results: check-variant-format
	$(MAKE) check-results-generic PHASE=$(PHASE1) VARIANTS_DIR=$(VARIANTS_DIR_01) \
		VARIANT=$(VARIANT) CHECK_FILES="01_explore_dataset.parquet \
		01_explore_metadata.json 01_explore_params.json 01_explore_report.html"




############################################
# 9. LIMPIEZA TOTAL DE FASE 01
############################################
remove1-all:
	$(MAKE) remove-phase-all PHASE=$(PHASE1) VARIANTS_DIR=$(VARIANTS_DIR_01)



tag1-stage-ready:
	git tag stage-ready-fase01
	git push origin stage-ready-fase01

tag1-script-ready:
	git tag script-ready-fase01
	git push origin script-ready-fase01

tag1-stable:
	git tag stable-fase01
	git push origin stable-fase01

############################################
# 10. HELP
############################################

help1:
	@echo "==============================================="
	@echo " FASE 01 — EXPLORE"
	@echo "==============================================="
	@echo ""
	@echo " CREAR VARIANTE:"
	@echo "   make variant1 VARIANT=v001 RAW=./data/raw.csv \\"
	@echo "       [CLEANING_STRATEGY=basic] [NAN_VALUES='[-999999]'] [ERROR_VALUES='{}'] \\"
	@echo "       [MAX_LINES=10000] [FIRST_LINE=1]"
	@echo ""
	@echo " EJECUTAR NOTEBOOK:"
	@echo "   make nb1-run VARIANT=v001"
	@echo ""
	@echo " EJECUTAR SCRIPT:"
	@echo "   make script1-run VARIANT=v001"
	@echo ""
	@echo " CHEQUEOS:"
	@echo "   make script1-check-results VARIANT=v001   # Verifica artefactos generados"
	@echo ""
	@echo " PUBLICAR + REPRODUCIR:"
	@echo "   make publish1 VARIANT=v001                  # Publica en DVC + git"
	@echo "   make script1-repro                          # Ejecuta dvc repro"
	@echo ""
	@echo " LIMPIAR + ELIMINAR:"
	@echo "   make remove1 VARIANT=v001                   # Elimina variante (si no tiene hijos)"
	@echo ""
	@echo " TAGGING:"
	@echo "   make tag1-stage-ready / tag1-script-ready / tag1-stable"
	@echo ""
	@echo "==============================================="

# ==========================================
# FASE 02 — prepareEventsDS
# ==========================================

PHASE2=02_prepareeventsds
VARIANTS_DIR_02 = executions/$(PHASE2)
NOTEBOOK2=notebooks/02_prepareeventsds.ipynb
SCRIPT2=scripts/02_prepareeventsds.py

tag2-stage-ready:
	git tag stage-ready-fase02
	git push origin stage-ready-fase02

tag2-script-ready:
	git tag script-ready-fase02
	git push origin script-ready-fase02

tag2-stable:
	git tag stable-fase02
	git push origin stable-fase02

nb2-run: check-variant-format
	$(MAKE) nb-run-generic PHASE=$(PHASE2) NOTEBOOK=$(NOTEBOOK2) VARIANT=$(VARIANT)
		
script2-run: check-variant-format
	$(MAKE) script-run-generic PHASE=$(PHASE2) SCRIPT=$(SCRIPT2) VARIANT=$(VARIANT)

variant2: check-variant-format
	@test -n "$(BANDS)" || (echo "[ERROR] Debes especificar BANDS=\"40 60 90\""; exit 1)
	@test -n "$(STRATEGY)" || (echo "[ERROR] Debes especificar STRATEGY=levels|transitions|both"; exit 1)
	@test -n "$(NAN)" || (echo "[ERROR] Debes especificar NAN=keep|discard"; exit 1)
	@test -n "$(PARENT)" || (echo "[ERROR] Debes especificar PARENT=vNNN (variante de fase 01)"; exit 1)
	@echo "==> Preparando parámetros específicos para Fase 02"
	@$(eval BANDS_YAML := [$(shell echo $(BANDS) | sed 's/ /, /g')] )
	@$(eval SET_TU := $(if $(strip $(TU)),--set Tu=$(TU),))
	@$(eval SET_LIST := --set band_thresholds_pct='$(BANDS_YAML)' \
		--set event_strategy=$(STRATEGY) \
		--set nan_handling=$(NAN) \
		--set parent_variant=$(PARENT) $(SET_TU))
	@$(MAKE) variant-generic PHASE=$(PHASE2) VARIANT=$(VARIANT) EXTRA_SET_FLAGS="$(SET_LIST)"
	@echo "[OK] Variante 02 creada: $(VARIANT)"


publish2: check-variant-format
	@echo "==> Validando variante $(PHASE2):$(VARIANT)"
	# delegar a objetivo genérico; PUBLISH_EXTS para fase 02: parquet json html
	$(MAKE) publish-generic PHASE=$(PHASE2) VARIANTS_DIR=$(VARIANTS_DIR_02) \
		PUBLISH_EXTS="parquet json html" VARIANT=$(VARIANT)

remove2: check-variant-format
	$(MAKE) remove-generic PHASE=$(PHASE2) VARIANTS_DIR=$(VARIANTS_DIR_02) VARIANT=$(VARIANT)

script2-check-results: check-variant-format
	$(MAKE) check-results-generic PHASE=$(PHASE2) VARIANTS_DIR=$(VARIANTS_DIR_02) \
		VARIANT=$(VARIANT) CHECK_FILES="02_prepareeventsds_dataset.parquet \
		02_prepareeventsds_bands.json 02_prepareeventsds_event_catalog.json \
		02_prepareeventsds_metadata.json 02_prepareeventsds_report.html"

remove2-all:
	$(MAKE) remove-phase-all PHASE=$(PHASE2) VARIANTS_DIR=$(VARIANTS_DIR_02)


# ===========================
# push2-stable
# Sube la rama actual, etiqueta la fase y sube el tag al remoto
# ===========================
push2-stable:
	@echo "[INFO] Verificando estado del repositorio..."
	@git diff --quiet || (echo "[ERROR] Tienes cambios sin commitear. Haz commit o stash antes."; exit 1)
	@git diff --cached --quiet || (echo "[ERROR] Hay cambios en staging sin commitear."; exit 1)

	@CURRENT_BRANCH=$$(git rev-parse --abbrev-ref HEAD); \
	echo "[INFO] Pushing branch '$$CURRENT_BRANCH' al remoto..."; \
	git push origin $$CURRENT_BRANCH || exit 1

	@echo "[INFO] Creando tag stable-fase02..."
	@git tag -f stable-fase02

	@echo "[INFO] Subiendo tag al remoto..."
	@git push -f origin stable-fase02

	@echo "==============================================="
	@echo "   ✔ Código y tag 'stable-fase02' enviados     "
	@echo "==============================================="
	
help2:
	@echo "==============================================="
	@echo " FASE 02 — PREPAREEVENTDS"
	@echo "==============================================="
	@echo ""
	@echo " CREAR VARIANTE (requiere PARENT de F01):"
	@echo "   make variant2 VARIANT=v011 PARENT=v001 BANDS=\"40 60 90\" \\"
	@echo "       STRATEGY=both NAN=keep [Tu=<opcional>]"
	@echo ""
	@echo " EJECUTAR NOTEBOOK:"
	@echo "   make nb2-run VARIANT=v011"
	@echo ""
	@echo " EJECUTAR SCRIPT:"
	@echo "   make script2-run VARIANT=v011"
	@echo ""
	@echo " CHEQUEOS:"
	@echo "   make script2-check-results VARIANT=v011   # Verifica artefactos generados"
	@echo ""
	@echo " PUBLICAR + REPRODUCIR:"
	@echo "   make publish2 VARIANT=v011                 # Publica en DVC + git"
	@echo "   make script2-repro                         # Ejecuta dvc repro"
	@echo ""
	@echo " LIMPIAR + ELIMINAR:"
	@echo "   make remove2 VARIANT=v011                  # Elimina variante (si no tiene hijos)"
	@echo ""
	@echo " TAGGING:"
	@echo "   make tag2-stage-ready / tag2-script-ready / tag2-stable"
	@echo ""
	@echo "==============================================="

# ==========================================

PHASE3=03_preparewindowsds
VARIANTS_DIR_03 = executions/$(PHASE3)
NOTEBOOK3=notebooks/03_preparewindowsds.ipynb
SCRIPT3=scripts/03_preparewindowsds.py


############################################
# 1. EJECUCIÓN DEL NOTEBOOK
############################################
nb3-run: check-variant-format
	$(MAKE) nb-run-generic PHASE=$(PHASE3) NOTEBOOK=$(NOTEBOOK3) VARIANT=$(VARIANT)


############################################
# 2. EJECUCIÓN DE LA SCRIPT
############################################
script3-run: check-variant-format
	$(MAKE) script-run-generic PHASE=$(PHASE3) SCRIPT=$(SCRIPT3) VARIANT=$(VARIANT)


############################################
# 3. CREAR VARIANTE DE LA FASE 03
############################################
# Uso:
#   make variant3 VARIANT=vNNN OW=600 LT=300 PW=600 WS=synchro NAN=preserve PARENT=vNNN

variant3: check-variant-format
	@test -n "$(PARENT)" || (echo "[ERROR] Debes especificar PARENT=vNNN (variante de fase 02)"; exit 1)
	@test -n "$(WS)" || (echo "[ERROR] Debes especificar WS=synchro|asynOW|withinPW|asynPW"; exit 1)
	@test -n "$(NAN)" || (echo "[ERROR] Debes especificar NAN=preserve|discard"; exit 1)
	@test -n "$(OW)" || (echo "[ERROR] Debes especificar OW=<entero>"; exit 1)
	@test -n "$(LT)" || (echo "[ERROR] Debes especificar LT=<entero>"; exit 1)
	@test -n "$(PW)" || (echo "[ERROR] Debes especificar PW=<entero>"; exit 1)
	@echo "==> Preparando parámetros específicos para Fase 03"
	@$(eval SET_LIST := --set variant_id=$(VARIANT) \
		--set parent_variant=$(PARENT) \
		--set OW=$(OW) \
		--set LT=$(LT) \
		--set PW=$(PW) \
		--set window_strategy=$(WS) \
		--set nan_strategy=$(NAN) )
	@$(MAKE) variant-generic PHASE=$(PHASE3) VARIANT=$(VARIANT) EXTRA_SET_FLAGS="$(SET_LIST)"
	@echo "[OK] Variante $(VARIANT) creada para Fase 03."


############################################
# 4. PUBLICAR VARIANTE DE FASE 03
############################################
publish3: check-variant-format
	@echo "==> Validando variante $(PHASE3):$(VARIANT)"
	# delegar a objetivo genérico; PUBLISH_EXTS para fase 03: parquet yaml pdf
	$(MAKE) publish-generic PHASE=$(PHASE3) VARIANTS_DIR=$(VARIANTS_DIR_03) \
		PUBLISH_EXTS="parquet yaml pdf" VARIANT=$(VARIANT)


############################################
# 5. ELIMINAR VARIANTE FASE 03
############################################
remove3: check-variant-format
	$(MAKE) remove-generic PHASE=$(PHASE3) VARIANTS_DIR=$(VARIANTS_DIR_03) VARIANT=$(VARIANT)

remove3-all:
	$(MAKE) remove-phase-all PHASE=$(PHASE3) VARIANTS_DIR=$(VARIANTS_DIR_03)


############################################
# 6. CHEQUEO DE RESULTADOS
############################################
script3-check-results: check-variant-format
	$(MAKE) check-results-generic PHASE=$(PHASE3) VARIANTS_DIR=$(VARIANTS_DIR_03) \
		VARIANT=$(VARIANT) CHECK_FILES="03_preparewindowsds_dataset.parquet \
		03_preparewindowsds_metadata.json 03_preparewindowsds_report.html "



############################################
# export
############################################

export3: check-variant-format
	@test -n "$(PARENT)" || (echo "[ERROR] PARENT no definido (variante F02)"; exit 1)
	@echo "==> Exportando dataset F03 variante $(VARIANT)"
	@mkdir -p exports/03_preparewindowsds/$(VARIANT)
	@echo "  - Copiando artefactos de F03..."
	@cp executions/03_preparewindowsds/$(VARIANT)/03_preparewindowsds_dataset.parquet \
	    exports/03_preparewindowsds/$(VARIANT)/ && echo "[OK] dataset.parquet"
	@cp executions/03_preparewindowsds/$(VARIANT)/03_preparewindowsds_metadata.json \
	    exports/03_preparewindowsds/$(VARIANT)/ && echo "[OK] metadata.json"
	@echo "  - Copiando event_catalog de F02 (PARENT=$(PARENT))..."
	@cp executions/02_prepareeventsds/$(PARENT)/02_prepareeventsds_event_catalog.json \
	    exports/03_preparewindowsds/$(VARIANT)/ && echo "[OK] event_catalog.json"
	@echo "  - Copiando README..."
	@cp executions/03_preparewindowsds/README_dataset.md \
	    exports/03_preparewindowsds/$(VARIANT)/README.md && echo "[OK] README.md"
	@echo "[OK] Export completado: exports/03_preparewindowsds/$(VARIANT)/"


############################################
# 9. HELP
############################################
help3:
	@echo "==============================================="
	@echo " FASE 03 — PREPAREWINDOWSDS"
	@echo "==============================================="
	@echo ""
	@echo " CREAR VARIANTE (requiere PARENT de F02):"
	@echo "   make variant3 VARIANT=v111 PARENT=v011 OW=600 LT=300 PW=600 \\"
	@echo "       WS=synchro NAN=preserve"
	@echo ""
	@echo " EJECUTAR NOTEBOOK:"
	@echo "   make nb3-run VARIANT=v111"
	@echo ""
	@echo " EJECUTAR SCRIPT:"
	@echo "   make script3-run VARIANT=v111"
	@echo ""
	@echo " CHEQUEOS:"
	@echo "   make script3-check-results VARIANT=v111   # Verifica artefactos generados"
	@echo ""
	@echo " EXPORTAR:"
	@echo "   make export3 VARIANT=v111 PARENT=v011     # Exporta dataset + metadata"
	@echo ""
	@echo " PUBLICAR + REPRODUCIR:"
	@echo "   make publish3 VARIANT=v111                # Publica en DVC + git"
	@echo "   make script3-repro                        # Ejecuta dvc repro"
	@echo ""
	@echo " LIMPIAR + ELIMINAR:"
	@echo "   make remove3 VARIANT=v111                 # Elimina variante (si no tiene hijos)"
	@echo ""
	@echo " TAGGING:"
	@echo "   make tag3-stage-ready / tag3-script-ready / tag3-stable"
	@echo ""
	@echo "==============================================="

############################################
# FASE 04 — TARGET ENGINEERING
############################################

PHASE4=04_targetengineering
VARIANTS_DIR_04 = executions/$(PHASE4)
NOTEBOOK4=notebooks/04_targetengineering.ipynb
SCRIPT4=scripts/04_targetengineering.py


############################################
# 1. EJECUCIÓN DEL NOTEBOOK
############################################
nb4-run: check-variant-format
	$(MAKE) nb-run-generic PHASE=$(PHASE4) NOTEBOOK=$(NOTEBOOK4) VARIANT=$(VARIANT)


############################################
# 2. EJECUCIÓN DE LA SCRIPT
############################################
script4-run: check-variant-format
	$(MAKE) script-run-generic PHASE=$(PHASE4) SCRIPT=$(SCRIPT4) VARIANT=$(VARIANT)


############################################
# 3. CREAR VARIANTE DE LA FASE 04
############################################
# Uso:
# make variant4 VARIANT=v201 PARENT=v111 \
#   OBJECTIVE="{operator: OR, events: [GRID_OVERVOLTAGE, INVERTER_FAULT]}"

variant4: check-variant-format
	@test -n "$(PARENT)" || (echo "[ERROR] Debes especificar PARENT=vNNN (variante de F03)"; exit 1)
	@test -n "$(PREDICTION_NAME)" || (echo "[ERROR] Debes especificar PREDICTION_NAME=name"; exit 1)
	@test -n "$(OBJECTIVE)" || (echo "[ERROR] Debes especificar OBJECTIVE='{operator: OR, events: [...]}'"; exit 1)
	@echo "==> Preparando parámetros específicos para Fase 04 (Target Engineering)"
	@$(eval SET_LIST := \
		--set parent_variant=$(PARENT) \
		--set prediction_objective='$(OBJECTIVE)' \
		--set prediction_name='$(PREDICTION_NAME)')
	@$(MAKE) variant-generic PHASE=$(PHASE4) VARIANT=$(VARIANT) EXTRA_SET_FLAGS="$(SET_LIST)"
	@echo "[OK] Variante $(VARIANT) creada para Fase 04."


############################################
# 4. PUBLICAR VARIANTE DE FASE 04
############################################
publish4: check-variant-format
	@echo "==> Validando variante $(PHASE4):$(VARIANT)"
	# Artefactos típicos F04: parquet + json + html
	$(MAKE) publish-generic PHASE=$(PHASE4) VARIANTS_DIR=$(VARIANTS_DIR_04) \
		PUBLISH_EXTS="parquet json html" VARIANT=$(VARIANT)


############################################
# 5. ELIMINAR VARIANTE FASE 04
############################################
remove4: check-variant-format
	$(MAKE) remove-generic PHASE=$(PHASE4) VARIANTS_DIR=$(VARIANTS_DIR_04) VARIANT=$(VARIANT)


############################################
# 6. CHEQUEO DE RESULTADOS
############################################
script4-check-results: check-variant-format
	$(MAKE) check-results-generic PHASE=$(PHASE4) VARIANTS_DIR=$(VARIANTS_DIR_04) \
		VARIANT=$(VARIANT) CHECK_FILES="04_targetengineering_dataset.parquet \
		04_targetengineering_metadata.json 04_targetengineering_params.json \
		04_targetengineering_report.html"



############################################
# 8. LIMPIEZA DE FASE 04
############################################

remove4-all:
	$(MAKE) remove-phase-all PHASE=$(PHASE4) VARIANTS_DIR=$(VARIANTS_DIR_04)



advise4: check-variant-format
	@echo "[INFO] ChatGPT Plus NO incluye cuota de API; se requiere billing en platform.openai.com"
	@test -n "$(OPENAI_API_KEY)" || \
	  (echo "[ERROR] Debes proporcionar OPENAI_API_KEY (https://platform.openai.com/account/api-keys)"; exit 1)
	@echo "==> Generando recomendación de modelado para Fase 04, variante $(VARIANT)"
	OPENAI_API_KEY="$(OPENAI_API_KEY)" \
	$(PYTHON) scripts/advise_modeling.py --phase $(PHASE4) --variant $(VARIANT)


############################################
# 9. HELP
############################################
help4:
	@echo "==============================================="
	@echo " FASE 04 — TARGET ENGINEERING"
	@echo "==============================================="
	@echo ""
	@echo " CREAR VARIANTE (requiere PARENT de F03):"
	@echo "   make variant4 VARIANT=v201 PARENT=v111 \\"
	@echo "       OBJECTIVE=\"{operator: OR, events: [GRID_OVERVOLTAGE, INVERTER_FAULT]}\""
	@echo ""
	@echo " EJECUTAR NOTEBOOK:"
	@echo "   make nb4-run VARIANT=v201"
	@echo ""
	@echo " EJECUTAR SCRIPT:"
	@echo "   make script4-run VARIANT=v201"
	@echo ""
	@echo " CHEQUEOS:"
	@echo "   make script4-check-results VARIANT=v201"
	@echo ""
	@echo " PUBLICAR:"
	@echo "   make publish4 VARIANT=v201"
	@echo ""
	@echo " LIMPIAR / ELIMINAR:"
	@echo "   make remove4 VARIANT=v201"
	@echo ""
	@echo " ADVISE (RECOMENDACIÓN DE MODELADO):"
	@echo "   make advise4 VARIANT=vNNN OPENAI_API_KEY=tu_api_key"
	@echo "       # Genera un informe con recomendaciones de técnicas de modelado"
	@echo "       # compatibles con TensorFlow Lite / TFLite Micro (ESP32)"
	@echo ""
	@echo "==============================================="


############################################
# FASE 05 — MODELING
############################################

PHASE5=05_modeling
VARIANTS_DIR_05 = executions/$(PHASE5)
NOTEBOOK5=notebooks/05_modeling.ipynb
SCRIPT5=scripts/05_modeling.py

# ============================================================
# FASE 05 — MODELING — configuración desde make
# ============================================================
IMBALANCE_STRATEGY ?= none          # none | auto | rare_events
IMBALANCE_MAX_NEG ?=                # p.ej. 200000

# Construimos un dict YAML para override de imbalance
# Ejemplo de resultado:
#   {strategy: rare_events, max_negatives: 200000, keep_all_positives: true}
ifeq ($(IMBALANCE_STRATEGY),rare_events)
  IMBALANCE_DICT := "{strategy: rare_events, max_negatives: $(IMBALANCE_MAX_NEG), keep_all_positives: true}"
else
  IMBALANCE_DICT := "{strategy: $(IMBALANCE_STRATEGY)}"
endif


############################################
# FUNCIÓN INTERNA: REGISTRO MLFLOW
############################################
define REGISTER_MLFLOW
META=$(VARIANTS_DIR_05)/$(VARIANT)/$(PHASE5)_metadata.json; \
test -f $$META || (echo "[ERROR] Metadata no encontrada"; exit 1); \
\
read BEST_RECALL MODEL_PATH PARENT MODEL_FAMILY OLD_RUN <<EOF
$$($(PYTHON) - <<EOF2
import json
with open("$$META") as f:
    d=json.load(f)
print(
    d["best_val_recall"],
    d["model_path"],
    d["parent_variant"],
    d["model_family"],
    d.get("mlflow",{}).get("run_id","")
)
EOF2
)
EOF
\
EXP_NAME="F05_$$PARENT"; \
\
if [ -n "$$OLD_RUN" ] && [ "$$OLD_RUN" != "null" ]; then \
  echo "==> Eliminando run anterior $$OLD_RUN"; \
  mlflow runs delete --run-id $$OLD_RUN || true; \
fi; \
\
EXP_ID=$$(mlflow experiments list --format json | \
$(PYTHON) - <<EOF
import sys,json,os
exp_name=os.environ.get("EXP_NAME")
data=json.load(sys.stdin)
for e in data:
    if e["name"]==exp_name:
        print(e["experiment_id"])
        break
EOF
); \
\
if [ -z "$$EXP_ID" ]; then \
  EXP_ID=$$(mlflow experiments create --experiment-name $$EXP_NAME \
    --format json | \
    $(PYTHON) - <<EOF
import sys,json
print(json.load(sys.stdin)["experiment_id"])
EOF
  ); \
fi; \
\
NEW_RUN=$$(mlflow runs create --experiment-id $$EXP_ID \
  --run-name "$(VARIANT)" --format json | \
  $(PYTHON) - <<EOF
import sys,json
print(json.load(sys.stdin)["run"]["info"]["run_id"])
EOF
); \
\
mlflow runs log-metric --run-id $$NEW_RUN best_val_recall $$BEST_RECALL; \
mlflow runs log-param --run-id $$NEW_RUN variant $(VARIANT); \
mlflow runs log-param --run-id $$NEW_RUN parent_variant $$PARENT; \
mlflow runs log-param --run-id $$NEW_RUN model_family $$MODEL_FAMILY; \
mlflow runs log-artifact --run-id $$NEW_RUN $$MODEL_PATH; \
\
$(PYTHON) - <<EOF
import json
with open("$$META") as f:
    d=json.load(f)
d.setdefault("mlflow",{})
d["mlflow"]["run_id"]="$$NEW_RUN"
d["mlflow"]["published"]=False
with open("$$META","w") as f:
    json.dump(d,f,indent=2)
EOF
\
echo "[OK] MLflow registrado en experimento $$EXP_NAME: $$NEW_RUN"
endef




############################################
# 1. EJECUCIÓN DEL NOTEBOOK
############################################
nb5-run: check-variant-format
	$(MAKE) nb-run-generic PHASE=$(PHASE5) NOTEBOOK=$(NOTEBOOK5) VARIANT=$(VARIANT)


############################################
# 2. EJECUCIÓN DEL SCRIPT
############################################
script5-run: check-variant-format
	$(MAKE) script-run-generic PHASE=$(PHASE5) SCRIPT=$(SCRIPT5) VARIANT=$(VARIANT)


############################################
# 3. CREAR VARIANTE (con política imbalance opcional)
############################################

IMBALANCE_STRATEGY ?= none
IMBALANCE_MAX_MAJ ?=

variant5: check-variant-format
	@test -n "$(PARENT)" || (echo "[ERROR] Debes especificar PARENT=vNNN"; exit 1)
	@test -n "$(MODEL_FAMILY)" || (echo "[ERROR] Debes especificar MODEL_FAMILY"; exit 1)
	@echo "==> Creando variante $(PHASE5):$(VARIANT)"
	@$(eval SET_LIST := \
		--set parent_variant=$(PARENT) \
		--set model_family=$(MODEL_FAMILY) )
	# --------------------------------------------------------
	# Política de imbalance explícita
	# --------------------------------------------------------
ifeq ($(IMBALANCE_STRATEGY),rare_events)
	@test -n "$(IMBALANCE_MAX_MAJ)" || \
	  (echo "[ERROR] Debes especificar IMBALANCE_MAX_MAJ para rare_events"; exit 1)
	@$(eval SET_LIST := $(SET_LIST) \
		--set imbalance.strategy=rare_events \
		--set imbalance.max_majority_samples=$(IMBALANCE_MAX_MAJ) )
else
	@$(eval SET_LIST := $(SET_LIST) \
		--set imbalance.strategy=none )
endif
	@$(MAKE) variant-generic PHASE=$(PHASE5) VARIANT=$(VARIANT) EXTRA_SET_FLAGS="$(SET_LIST)"
	@echo "[OK] Variante $(VARIANT) creada con imbalance=$(IMBALANCE_STRATEGY)."



############################################
# 4. PUBLICAR + MARCAR COMO PUBLISHED
############################################
publish5: check-variant-format
	@bash -c 'set -e; \
	META="$(VARIANTS_DIR_05)/$(VARIANT)/$(PHASE5)_metadata.json"; \
	if [ ! -f "$$META" ]; then \
		echo "[ERROR] Falta metadata 05_modeling_metadata.json"; exit 1; \
	fi; \
	echo "==> Registrando run en MLflow"; \
	export META; \
	$(PYTHON) - <<'"'"'EOF'"'"'\
import json, subprocess, os, sys\
\
meta_path = os.environ["META"]\
with open(meta_path) as f:\
    data = json.load(f)\
\
reg = data.get("mlflow_registration")\
if not reg:\
    print("[ERROR] No existe bloque mlflow_registration en metadata")\
    sys.exit(1)\
\
exp_name = reg["experiment_name"]\
metrics = reg.get("metrics", {})\
params = reg.get("params", {})\
artifacts = reg.get("artifacts", [])\
\
subprocess.run(["mlflow", "experiments", "create", "--experiment-name", exp_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\
\
out = subprocess.check_output(["mlflow", "experiments", "list", "--format", "json"])\
import json as _json\
exps = _json.loads(out)\
exp_id = next((e["experiment_id"] for e in exps if e["name"] == exp_name), None)\
\
if not exp_id:\
    print("[ERROR] No se pudo obtener experiment_id")\
    sys.exit(1)\
\
out = subprocess.check_output(["mlflow", "runs", "create", "--experiment-id", exp_id, "--format", "json"])\
run = _json.loads(out)\
run_id = run["info"]["run_id"]\
\
for k, v in params.items():\
    subprocess.run(["mlflow", "runs", "log-param", "--run-id", run_id, "--key", str(k), "--value", str(v)])\
\
for k, v in metrics.items():\
    subprocess.run(["mlflow", "runs", "log-metric", "--run-id", run_id, "--key", str(k), "--value", str(v)])\
\
for a in artifacts:\
    if os.path.exists(a):\
        subprocess.run(["mlflow", "runs", "log-artifact", "--run-id", run_id, "--local-path", a])\
\
data["mlflow"] = {"run_id": run_id, "experiment_id": exp_id, "experiment_name": exp_name}\
\
with open(meta_path, "w") as f:\
    json.dump(data, f, indent=2)\
\
print(f"[OK] Run MLflow creado: {run_id}")\
EOF\
	'

	$(MAKE) publish-generic PHASE=$(PHASE5) VARIANTS_DIR=$(VARIANTS_DIR_05) \
		PUBLISH_EXTS="parquet json html h5" VARIANT=$(VARIANT)


############################################
# 5. ELIMINAR VARIANTE FASE 05 + LIMPIEZA MLFLOW COMPLETA
############################################
remove5: check-variant-format
	@bash -c 'set -e; \
	META="$(VARIANTS_DIR_05)/$(VARIANT)/$(PHASE5)_metadata.json"; \
	if [ -f "$$META" ]; then \
		echo "==> Revisando metadata MLflow"; \
		export META; \
		$(PYTHON) - <<'"'"'EOF'"'"'\
import json, subprocess, sys, os\
\
meta_path = os.environ["META"]\
\
with open(meta_path) as f:\
    data = json.load(f)\
\
ml = data.get("mlflow", {})\
run_id = ml.get("run_id")\
exp_id = ml.get("experiment_id")\
\
if run_id:\
    print(f"[INFO] Eliminando run MLflow {run_id}")\
    subprocess.run(["mlflow", "runs", "delete", "--run-id", run_id], check=False)\
\
if exp_id:\
    try:\
        out = subprocess.check_output(["mlflow", "runs", "list", "--experiment-id", exp_id, "--format", "json"])\
        runs = json.loads(out)\
        active = [r for r in runs if r["info"]["lifecycle_stage"] == "active"]\
        if len(active) == 0:\
            print(f"[INFO] Eliminando experimento MLflow {exp_id} (vacío)")\
            subprocess.run(["mlflow", "experiments", "delete", "--experiment-id", exp_id], check=False)\
    except Exception as e:\
        print("[WARN] No se pudo verificar experimento MLflow:", e)\
EOF\
	fi; \
	'

	$(MAKE) remove-generic PHASE=$(PHASE5) VARIANTS_DIR=$(VARIANTS_DIR_05) VARIANT=$(VARIANT)


remove5-all:
	@echo "==> Eliminando TODAS las variantes de Fase 05 (modo SEGURO)"
	@test -d "$(VARIANTS_DIR_05)" || \
	  (echo "[INFO] No existe $(VARIANTS_DIR_05). Nada que borrar."; exit 0)

	@for v in $$(ls $(VARIANTS_DIR_05) | grep '^v[0-9]\{3\}$$'); do \
	  echo "----> Eliminando $(PHASE5):$$v"; \
	  $(MAKE) remove5 VARIANT=$$v || exit 1; \
	done

	@echo "[OK] Fase 05 eliminada completamente (incluye MLflow)"


############################################
# 6. CHEQUEO DE RESULTADOS
############################################
# En F05 se valida:
# - existencia de metadata
# - existencia de modelo final

script5-check-results: check-variant-format
	@test -f $(VARIANTS_DIR_05)/$(VARIANT)/$(PHASE5)_metadata.json || \
	  (echo "[FAIL] Falta $(PHASE5)_metadata.json"; exit 1)
	@echo "[OK] Metadata de Fase 05 presente"






############################################
# 9. HELP
############################################
help5:
	@echo "==============================================="
	@echo " FASE 05 — MODELING"
	@echo "==============================================="
	@echo ""
	@echo " CREAR VARIANTE (requiere PARENT de F04):"
	@echo ""
	@echo "   make variant5 VARIANT=v301 \\"
	@echo "        PARENT=v201 \\"
	@echo "        MODEL_FAMILY=dense_bow"
	@echo ""
	@echo " CREAR VARIANTE CON RARE EVENTS:"
	@echo ""
	@echo "   make variant5 VARIANT=v302 \\"
	@echo "        PARENT=v201 \\"
	@echo "        MODEL_FAMILY=dense_bow \\"
	@echo "        IMBALANCE_STRATEGY=rare_events \\"
	@echo "        IMBALANCE_MAX_MAJ=200000"
	@echo ""
	@echo " NOTA:"
	@echo " - En problemas binarios, se asume label=1 como clase minoritaria."
	@echo " - rare_events mantiene todos los positivos (label=1)"
	@echo "   y limita el número de negativos."
	@echo ""
	@echo " EJECUTAR NOTEBOOK:"
	@echo "   make nb5-run VARIANT=v301"
	@echo ""
	@echo " EJECUTAR SCRIPT:"
	@echo "   make script5-run VARIANT=v301"
	@echo ""
	@echo " CHEQUEOS:"
	@echo "   make script5-check-results VARIANT=v301"
	@echo ""
	@echo " PUBLICAR:"
	@echo "   make publish5 VARIANT=v301"
	@echo ""
	@echo " ELIMINAR:"
	@echo "   make remove5 VARIANT=v301"
	@echo ""
	@echo " COMPORTAMIENTO:"
	@echo " - Cada variante explora UNA familia de modelos."
	@echo " - Se prueban hasta max_trials configuraciones internas."
	@echo " - Se selecciona automáticamente el modelo con mejor"
	@echo "   métrica primaria en validación."
	@echo " - Se materializa UN único modelo final por variante."
	@echo ""
	@echo "==============================================="


############################################
# FASE 06 — PACKAGING
############################################

PHASE6 := 06_packaging
VARIANTS_DIR_06 := executions/$(PHASE6)

# ------------------------------------------------------------
# Crear variante F06
# ------------------------------------------------------------
# ------------------------------------------------------------
# Crear variante F06 (PACKAGING) — con validación y herencia
# ------------------------------------------------------------
variant6: check-variant-format
	@echo "==> Creando variante F06 $(VARIANT)"

	@if [ -z "$(PARENTS_F05)" ]; then \
		echo "[ERROR] PARENTS_F05 es obligatorio"; exit 1; \
	fi

	# Tomamos el primer parent F05 como referencia de herencia
	$(eval FIRST_F05 := $(word 1,$(PARENTS_F05)))

	# Resolver F04 y F03 a partir de F05
	$(eval F04_FROM_F05 := $(shell yq '.parent_variant' executions/05_modeling/$(FIRST_F05)/params.yaml))
	$(eval F03_FROM_F04 := $(shell yq '.parent_variant' executions/04_targetengineering/$(F04_FROM_F05)/params.yaml))

	# Herencia por defecto del régimen temporal desde F03
	$(eval Tu_FINAL := $(if $(Tu),$(Tu),$(shell yq '.temporal.Tu' executions/03_preparewindowsds/$(F03_FROM_F04)/params.yaml)))
	$(eval OW_FINAL := $(if $(OW),$(OW),$(shell yq '.temporal.OW' executions/03_preparewindowsds/$(F03_FROM_F04)/params.yaml)))
	$(eval PW_FINAL := $(if $(PW),$(PW),$(shell yq '.temporal.PW' executions/03_preparewindowsds/$(F03_FROM_F04)/params.yaml)))

	$(PYTHON) mlops4ofp/tools/params_manager.py \
		create-variant \
		--phase 06_packaging \
		--variant $(VARIANT) \
		--set parent_variants_f05="$(PARENTS_F05)" \
		--set temporal.Tu=$(Tu_FINAL) \
		--set temporal.OW=$(OW_FINAL) \
		--set temporal.PW=$(PW_FINAL)

	@echo "[OK] Variante F06 $(VARIANT) creada"



# ------------------------------------------------------------
# Ejecutar notebook
# ------------------------------------------------------------
nb6-run: check-variant-format
	@echo "==> Ejecutando notebook F06 $(VARIANT)"
	$(PYTHON) -m nbconvert \
		--to notebook \
		--execute notebooks/$(PHASE6).ipynb \
		--output executed_$(PHASE6)_$(VARIANT).ipynb \
		--ExecutePreprocessor.timeout=600

# ------------------------------------------------------------
# Ejecutar script
# ------------------------------------------------------------
script6-run: check-variant-format
	@echo "==> Ejecutando script F06 $(VARIANT)"
	$(PYTHON) scripts/$(PHASE6).py \
		--variant $(VARIANT)

# ------------------------------------------------------------
# Validaciones básicas (coherencia / trazabilidad)
# ------------------------------------------------------------
check6: check-variant-format
	@echo "==> Validando variante F06 $(VARIANT)"
	$(PYTHON) mlops4ofp/tools/traceability.py validate-variant \
		--phase $(PHASE6) \
		--variant $(VARIANT)

# ------------------------------------------------------------
# Publicar resultados (DVC + git)
# ------------------------------------------------------------
publish6: check-variant-format
	@echo "==> Publicando F06 $(VARIANT)"
	dvc add $(VARIANTS_DIR_06)/$(VARIANT) || true
	git add $(VARIANTS_DIR_06)/$(VARIANT) $(VARIANTS_DIR_06)/variants.yaml
	git commit -m "F06 packaging: $(VARIANT)" || true
	dvc push || true
	git push || true

# ------------------------------------------------------------
# Exportar paquete (release externo)
# ------------------------------------------------------------
export6: check-variant-format
	@echo "==> Exportando paquete F06 $(VARIANT)"
	tar -czf $(PHASE6)_$(VARIANT).tar.gz -C $(VARIANTS_DIR_06) $(VARIANT)

# ------------------------------------------------------------
# Eliminar variante
# ------------------------------------------------------------
remove6: check-variant-format
	@echo "==> Comprobando si la variante $(PHASE6):$(VARIANT) tiene hijos…"
	$(PYTHON) mlops4ofp/tools/traceability.py can-delete \
		--phase $(PHASE6) \
		--variant $(VARIANT)
	@echo "==> Eliminando carpeta completa de la variante"
	rm -rf $(VARIANTS_DIR_06)/$(VARIANT)
	@echo "==> Actualizando registro de variantes"
	$(PYTHON) mlops4ofp/tools/params_manager.py delete-variant \
		--phase $(PHASE6) \
		--variant $(VARIANT)
	@git add -A
	@git commit -m "remove variant: $(PHASE6) $(VARIANT)" || true
	@git push || true

# ------------------------------------------------------------
# Limpiar artefactos locales
# ------------------------------------------------------------

# ------------------------------------------------------------
# Ayuda
# ------------------------------------------------------------
help6:
	@echo "=================================================="
	@echo " F06 — PACKAGING (sistema agnóstico)"
	@echo "=================================================="
	@echo ""
	@echo "Objetivo:"
	@echo "  Componer un paquete de sistema a partir de variantes F05,"
	@echo "  seleccionando modelos y fijando valores temporales comunes."
	@echo ""
	@echo "Reglas clave:"
	@echo "  - F06 NO ejecuta inferencia"
	@echo "  - F06 NO evalúa métricas"
	@echo "  - F06 NO interpreta semántica temporal"
	@echo "  - F06 es agnóstica del runtime"
	@echo ""
	@echo "Herencia por defecto:"
	@echo "  - Si Tu / OW / PW no se especifican, se heredan literalmente"
	@echo "    desde la fase 03 (preparewindowsds)."
	@echo "  - Si REPLAY_DATASET no se especifica, se hereda desde la fase 02."
	@echo "  - La herencia es pasiva: F06 no valida ni modifica valores."
	@echo ""
	@echo "Uso:"
	@echo "  make variant6 VARIANT=vNNN \\"
	@echo "       PARENTS_F05=\"vAAA vBBB\" \\"
	@echo "       [Tu=<valor>] [OW=<valor>] [PW=<valor>]"
	@echo ""
	@echo "Parámetros obligatorios:"
	@echo "  VARIANT       Nombre de la variante (vNNN)"
	@echo "  PARENTS_F05   Lista de variantes F05 (separadas por espacios)"
	@echo ""
	@echo "Parámetros opcionales (override):"
	@echo "  Tu, OW, PW    Valores temporales del sistema"
	@echo ""
	@echo "Notas:"
	@echo "  - F06 ya no selecciona modelos manualmente."
	@echo "  - Cada variante F05 aporta su modelo oficial."
	@echo "  - F06 solo compone y sella el sistema."

	@echo "=================================================="
	@echo "  make nb6-run VARIANT=vNNN"
	@echo "  make script6-run VARIANT=vNNN"
	@echo "  make check6 VARIANT=vNNN"
	@echo "  make publish6 VARIANT=vNNN"
	@echo "  make export6 VARIANT=vNNN"
	@echo "  make remove6 VARIANT=vNNN"



# ==========================================
# FASE 07 — DEPLOY & RUN
# ==========================================
PHASE7 := 07_deployrun
VARIANTS_DIR_07 := executions/$(PHASE7)
BASE_PARAMS_07 := $(VARIANTS_DIR_07)/base_params.yaml
SCRIPT_07 := scripts/07_deployrun.py
NOTEBOOK_07 := notebooks/07_deployrun.ipynb

variant7: check-variant-format
	@test -n "$(PARENT)" || (echo "[ERROR] Debes especificar PARENT=vNNN (variante F06)"; exit 1)
	@echo "==> Creando variante $(PHASE7):$(VARIANT) (parent F06: $(PARENT))"

	@$(eval SET_LIST := \
		--set parent_variant_f06=$(PARENT) )

	# ---------------------------------------------
	# Overrides opcionales (sin fallar si no vienen)
	# ---------------------------------------------
	@$(if $(strip $(BATCH_SIZE)),$(eval SET_LIST += --set batch_size=$(BATCH_SIZE)))
	@$(if $(strip $(HOST)),$(eval SET_LIST += --set runtime.host='$(HOST)'))
	@$(if $(strip $(PORT)),$(eval SET_LIST += --set runtime.port=$(PORT)))

	@$(MAKE) variant-generic PHASE=$(PHASE7) VARIANT=$(VARIANT) EXTRA_SET_FLAGS="$(SET_LIST)"

	@echo "==> Generando manifest.json"
	$(PYTHON) $(SCRIPT_07) --variant $(VARIANT) --mode prepare

	@echo "[OK] Variante F07 $(VARIANT) creada"


script7-run: check-variant-format
	@echo "==> Ejecutando F07 (script) para variante $(VARIANT)"
	$(PYTHON) $(SCRIPT_07) \
		--variant $(VARIANT) \
		--mode run

nb7-run: check-variant-format
	@echo "==> Ejecutando F07 (notebook) para variante $(VARIANT)"
	ACTIVE_VARIANT=$(VARIANT) $(JUPYTER) nbconvert \
		--execute $(NOTEBOOK_07) \
		--to notebook \
		--inplace \
		--ExecutePreprocessor.timeout=-1 \
		--ExecutePreprocessor.kernel_name=python3

publish7: check-variant-format
	@echo "==> Publicando F07 $(VARIANT)"
	dvc add $(VARIANTS_DIR_07)/$(VARIANT) || true
	git add $(VARIANTS_DIR_07)/$(VARIANT) $(VARIANTS_DIR_07)/variants.yaml
	git commit -m "F07 deploy-run: $(VARIANT)" || true
	dvc push || true
	git push || true

# ------------------------------------------------------------
# Eliminar variante
# ------------------------------------------------------------
remove7: check-variant-format
	@echo "==> Comprobando si la variante $(PHASE7):$(VARIANT) tiene hijos…"
	$(PYTHON) mlops4ofp/tools/traceability.py can-delete \
		--phase $(PHASE7) \
		--variant $(VARIANT)

	@echo "==> Eliminando seguimiento DVC (si existe)"
	-dvc remove $(VARIANTS_DIR_07)/$(VARIANT).dvc || true

	@echo "==> Eliminando carpeta completa de la variante"
	rm -rf $(VARIANTS_DIR_07)/$(VARIANT)

	@echo "==> Actualizando registro de variantes"
	$(PYTHON) mlops4ofp/tools/params_manager.py delete-variant \
		--phase $(PHASE7) \
		--variant $(VARIANT)

	@git add -A
	@git commit -m "remove variant: $(PHASE7) $(VARIANT)" || true
	@git push || true




help7:
	@echo "=============================================="
	@echo " FASE 07 — DEPLOY & RUNTIME VALIDATION"
	@echo "=============================================="
	@echo ""
	@echo "make variant7 VARIANT=vNNN PARENT=vMMM    -> crear variante F07"
	@echo "make script7-run VARIANT=vNNN  -> ejecutar cliente-servidor y métricas"
	@echo "make nb7-run VARIANT=vNNN      -> ejecutar notebook equivalente"
	@echo "make publish7 VARIANT=vNNN     -> versionar con DVC + Git"
	@echo "make remove7 VARIANT=vNNN      -> eliminar variante si no tiene hijos"
	@echo ""



# ==========================================
# AYUDA GLOBAL
# ==========================================

############################################
# UI unificada (MLflow + DVC)
############################################

############################################
# UI unificada (portable)
############################################

ui:
	@echo "==> UI MLOps4OFP"
	@if [ ! -f .mlops4ofp/setup.yaml ]; then \
		echo "[ERROR] Setup no ejecutado."; \
		exit 1; \
	fi; \
	MLFLOW_BACKEND=$$($(PYTHON) -c "import yaml, pathlib; \
cfg=yaml.safe_load(pathlib.Path('.mlops4ofp/setup.yaml').read_text()); \
print(cfg.get('mlflow',{}).get('backend','local'))"); \
	DVC_BACKEND=$$($(PYTHON) -c "import yaml, pathlib; \
cfg=yaml.safe_load(pathlib.Path('.mlops4ofp/setup.yaml').read_text()); \
print(cfg.get('dvc',{}).get('backend','local'))"); \
	open_url() { \
		URL=$$1; \
		echo "[INFO] Abriendo $$URL"; \
		case "$$(uname)" in \
			Darwin*) open "$$URL" ;; \
			Linux*) xdg-open "$$URL" >/dev/null 2>&1 || sensible-browser "$$URL" ;; \
			MINGW*|MSYS*|CYGWIN*) start "$$URL" ;; \
			*) echo "[WARN] Plataforma desconocida. URL: $$URL" ;; \
		esac; \
	}; \
	if [ "$$MLFLOW_BACKEND" = "dagshub" ]; then \
		URL=$$($(PYTHON) -c "import yaml, pathlib; \
cfg=yaml.safe_load(pathlib.Path('.mlops4ofp/setup.yaml').read_text()); \
print(cfg['mlflow']['tracking_uri'])"); \
		open_url "$$URL"; \
	else \
		echo "[INFO] Arrancando MLflow local en http://127.0.0.1:5000"; \
		. .mlops4ofp/env.sh && \
		$(PYTHON) -m mlflow ui --host 127.0.0.1 --port 5000 >/dev/null 2>&1 & \
		sleep 2; \
		open_url "http://127.0.0.1:5000"; \
	fi; \
	if [ "$$DVC_BACKEND" = "dagshub" ]; then \
		REPO=$$($(PYTHON) -c "import yaml, pathlib; \
cfg=yaml.safe_load(pathlib.Path('.mlops4ofp/setup.yaml').read_text()); \
print(cfg['dvc']['repo'])"); \
		open_url "https://dagshub.com/$$REPO"; \
	else \
		echo "[INFO] Storage local en .dvc_storage"; \
	fi




help: help-setup help1 help2 help3 help4 help5 help6 help7
	@echo "==============================================="

.PHONY: \
	setup check-setup clean-setup help-setup \
	nb-run-generic script-run-generic publish-generic remove-generic check-results-generic export-generic \
	nb1-run nb2-run nb3-run nb4-run \
	script1-run script1-repro script1-check-results script2-run script2-repro script2-check-results script3-run script3-repro script3-check-results  \
	script4-run \
	variant1 variant2 variant3 variant4 variant-generic check-variant-format \
	publish1 publish2 publish3 publish4\
	remove1 remove2 remove3 remove4 \
	export3 \
	tag1-stage-ready tag1-script-ready tag1-stable tag2-stage-ready tag2-script-ready tag2-stable tag3-stage-ready tag3-script-ready tag3-stable \
	help1 help2 help3 help4 help \
	advise4 \
	switch-remote-local switch-remote-public switch-remote-private check-remotes
