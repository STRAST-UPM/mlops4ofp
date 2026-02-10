############################################
# CARGA AUTOMÁTICA DE VARIABLES DE ENTORNO
# (MLflow, etc.)
############################################

PYTHON ?= python

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
	@$(PYTHON) setup/check_env.py
	@echo "==> Verificando configuración del proyecto"
	@.venv/bin/python setup/check_setup.py

clean-setup:
	@echo "==> Eliminando configuración de setup"
	@rm -rf .mlops4ofp
	@echo "[OK] Setup eliminado. El proyecto vuelve a estado post-clone."

############################################
# ADMIN — DVC GARBAGE COLLECTION (PELIGRO)
############################################

gc-admin:
	@echo "==============================================="
	@echo " ⚠️  DVC GARBAGE COLLECTION — ADMINISTRADOR ⚠️"
	@echo "==============================================="
	@echo ""
	@echo "Esta operación eliminará DEFINITIVAMENTE"
	@echo "los blobs DVC no referenciados por NINGÚN commit."
	@echo ""
	@echo "Remoto afectado: 'storage'"
	@echo ""
	@echo "NO ejecutar si no sabes exactamente lo que haces."
	@echo ""
	@read -p "Escribe EXACTAMENTE 'GC-ADMIN' para continuar: " CONFIRM; \
	if [ "$$CONFIRM" != "GC-ADMIN" ]; then \
		echo "[ABORT] Operación cancelada."; exit 1; \
	fi
	@echo ""
	@echo "==> Ejecutando dvc gc (esto puede tardar)..."
	@$(DVC) gc -r storage --all-branches --all-tags --all-commits --force
	@echo ""
	@echo "[OK] Garbage collection completada en remoto DVC."




############################################
# ENTORNO DE EJECUCIÓN (PIPELINE)
############################################

ifneq ("$(wildcard .venv/bin/python3)","")
PYTHON := .venv/bin/python3
DVC := .venv/bin/dvc
else
# Si no existe .venv, usar los ejecutables del sistema para permitir targets
# como `make setup` que crean el entorno virtual.
PYTHON := python3
DVC := dvc
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
	  dvc add $(VARIANTS_DIR)/$(VARIANT)/*.$$ext || true; \
	done
	@git add -f $(VARIANTS_DIR)/$(VARIANT)/*.dvc || true
	@git add $(VARIANTS_DIR)/variants.yaml || true
	@git commit -m "publish variant: $(PHASE) $(VARIANT)" || true
	# Comprobaciones previas: remoto DVC 'storage' debe existir
	@if ! $(DVC) remote list 2>/dev/null | grep -q "^storage"; then \
		echo "[ERROR] Remote DVC 'storage' no configurado. Ejecuta 'make setup' o contacta con el admin"; exit 1; \
	fi
	# Si existe remote git 'publish' lo usamos; si no existe pero el setup está en
	# modo git.mode=none (local), permitimos commit local y dvc push.
	# Determinamos el modo mediante script Python (usa .venv)
	@MODE=$$($(PYTHON) scripts/check_publish_mode.py); \
	if [ "$$MODE" = "publish" ]; then \
		echo "[INFO] Remote 'publish' detectado: empujando a publish"; \
		git push publish HEAD:main || echo "[WARN] git push publish failed"; \
	elif [ "$$MODE" = "none" ]; then \
		echo "[INFO] Setup en modo git.mode=none: no se empuja a Git remoto (commit local solo)"; \
	else \
		echo "[ERROR] Remote 'publish' no configurado y setup no en modo 'none'. Ejecuta 'make setup' o contacta con el admin"; exit 1; \
	fi
	# Finalmente, push DVC al remote 'storage' (puede ser local o remoto)
	@$(DVC) push -r storage || (echo "[WARN] dvc push failed (credenciales o acceso)"; exit 1)
	@echo "[OK] Publicación completada: variante $(PHASE):$(VARIANT)"

remove-generic: check-variant-format
	@echo "==> Comprobando si la variante $(PHASE):$(VARIANT) tiene hijos…"
	$(PYTHON) mlops4ofp/tools/traceability.py can-delete --phase $(PHASE) --variant $(VARIANT)
	@echo "==> Eliminando carpeta completa de la variante"
	rm -rf $(VARIANTS_DIR)/$(VARIANT)
	@echo "==> Actualizando registro de variantes"
	$(PYTHON) mlops4ofp/tools/params_manager.py delete-variant --phase $(PHASE) --variant $(VARIANT)
	@echo "==> Commit + push"
	@git add -A
	@git commit -m "remove variant: $(PHASE) $(VARIANT)" || true
	# Si existe remote publish empujamos; si setup git.mode=none permitimos omitir
	@MODE=$$($(PYTHON) scripts/check_publish_mode.py); \
	if [ "$$MODE" = "publish" ]; then \
		git push publish HEAD:main || echo "[WARN] git push publish failed"; \
	elif [ "$$MODE" = "none" ]; then \
		echo "[INFO] Setup en modo git.mode=none: no se empuja a Git remoto (commit local solo)"; \
	else \
		echo "[ERROR] Remote 'publish' no configurado y setup no en modo 'none'. Ejecuta 'make setup' o contacta con el admin"; exit 1; \
	fi
	@echo "[OK] Variante $(PHASE):$(VARIANT) eliminada completamente."

check-dvc-generic:
	@echo "===== CHECKING DVC STATUS ($(PHASE)) ====="
	@echo "[Checking local DVC...]"
	@$(DVC) status --cloud 2>/dev/null && echo "[OK] Local DVC clean" || echo "[WARN] Local DVC has changes"
	@echo "[Checking remote DVC (storage)...]"
	@$(DVC) status -r storage -c 2>/dev/null && echo "[OK] Remote up to date" || echo "[WARN] Remote missing data"
	@echo "================================"

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

clean-phase-generic:
	@echo "==> Limpiando variantes de Fase $(PHASE)"
	rm -rf $(VARIANTS_DIR)/v*
	@echo "==> Eliminando registro de variantes de Fase $(PHASE)"
	rm -f $(VARIANTS_DIR)/variants.yaml
	@echo "[OK] Limpieza completa de Fase $(PHASE) (solo parámetros y variantes)"

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

define CHECK_MODELS_YAML
python - << 'EOF'
import sys, yaml
try:
    data = yaml.safe_load("""$(MODELS)""")
    if not isinstance(data, dict) or not data:
        raise ValueError("MODELS debe ser un diccionario no vacío")
    for obj, models in data.items():
        if not isinstance(models, list) or not models:
            raise ValueError(f"El objetivo {obj} no tiene modelos válidos")
    print("[OK] MODELS válido")
except Exception as e:
    print(f"[ERROR] MODELS inválido: {e}", file=sys.stderr)
    sys.exit(1)
EOF
endef



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
# 8. CHEQUEO DE DVC
############################################
script1-check-dvc:
	$(MAKE) check-dvc-generic PHASE=$(PHASE1)


############################################
# 9. LIMPIEZA TOTAL DE FASE 01
############################################
clean1-all:
	$(MAKE) clean-phase-generic PHASE=$(PHASE1) VARIANTS_DIR=$(VARIANTS_DIR_01)

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
	@echo "       [CLEANING_STRATEGY=basic] [NAN_VALUES='[-999999]'] [ERROR_VALUES='{}']"
	@echo ""
	@echo " EJECUTAR NOTEBOOK:"
	@echo "   make nb1-run VARIANT=v001"
	@echo ""
	@echo " EJECUTAR SCRIPT:"
	@echo "   make script1-run VARIANT=v001"
	@echo ""
	@echo " CHEQUEOS:"
	@echo "   make script1-check-results VARIANT=v001   # Verifica artefactos generados"
	@echo "   make script1-check-dvc                      # Chequea estado de DVC"
	@echo ""
	@echo " PUBLICAR + REPRODUCIR:"
	@echo "   make publish1 VARIANT=v001                  # Publica en DVC + git"
	@echo "   make script1-repro                          # Ejecuta dvc repro"
	@echo ""
	@echo " LIMPIAR + ELIMINAR:"
	@echo "   make remove1 VARIANT=v001                   # Elimina variante (si no tiene hijos)"
	@echo "   make clean1-all                             # Limpia todas las variantes de F01"
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

script2-check-dvc:
	$(MAKE) check-dvc-generic PHASE=$(PHASE2)

clean2-all:
	$(MAKE) clean-phase-generic PHASE=$(PHASE2) VARIANTS_DIR=$(VARIANTS_DIR_02)

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
	@echo "   make script2-check-dvc                     # Chequea estado de DVC"
	@echo ""
	@echo " PUBLICAR + REPRODUCIR:"
	@echo "   make publish2 VARIANT=v011                 # Publica en DVC + git"
	@echo "   make script2-repro                         # Ejecuta dvc repro"
	@echo ""
	@echo " LIMPIAR + ELIMINAR:"
	@echo "   make remove2 VARIANT=v011                  # Elimina variante (si no tiene hijos)"
	@echo "   make clean2-all                            # Limpia todas las variantes de F02"
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
		03_preparewindowsds_metadata.json 03_preparewindowsds_report.html \
		03_preparewindowsds_stats.json"

############################################
# 7. CHEQUEO DE DVC PARA FASE 03
############################################
script3-check-dvc:
	$(MAKE) check-dvc-generic PHASE=$(PHASE3)


############################################
# 8. LIMPIEZA DE FASE 03
############################################
clean3-all:
	$(MAKE) clean-phase-generic PHASE=$(PHASE3) VARIANTS_DIR=$(VARIANTS_DIR_03)

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
	@echo "   make script3-check-dvc                    # Chequea estado de DVC"
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
	@echo "   make clean3-all                           # Limpia todas las variantes de F03"
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
	@test -n "$(OBJECTIVE)" || (echo "[ERROR] Debes especificar OBJECTIVE='{operator: OR, events: [...]}'"; exit 1)
	@echo "==> Preparando parámetros específicos para Fase 04 (Target Engineering)"
	@$(eval SET_LIST := \
		--set parent_variant=$(PARENT) \
		--set prediction_objective='$(OBJECTIVE)' )
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
# 7. CHEQUEO DE DVC PARA FASE 04
############################################
script4-check-dvc:
	$(MAKE) check-dvc-generic PHASE=$(PHASE4)


############################################
# 8. LIMPIEZA DE FASE 04
############################################
clean4-all:
	$(MAKE) clean-phase-generic PHASE=$(PHASE4) VARIANTS_DIR=$(VARIANTS_DIR_04)

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
	@echo "   make script4-check-dvc"
	@echo ""
	@echo " PUBLICAR:"
	@echo "   make publish4 VARIANT=v201"
	@echo ""
	@echo " LIMPIAR / ELIMINAR:"
	@echo "   make remove4 VARIANT=v201"
	@echo "   make clean4-all"
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


############################################
# 1. EJECUCIÓN DEL NOTEBOOK
############################################
nb5-run: check-variant-format
	$(MAKE) nb-run-generic PHASE=$(PHASE5) NOTEBOOK=$(NOTEBOOK5) VARIANT=$(VARIANT)


############################################
# 2. EJECUCIÓN DE LA SCRIPT
############################################
script5-run: check-variant-format
	$(MAKE) script-run-generic PHASE=$(PHASE5) SCRIPT=$(SCRIPT5) VARIANT=$(VARIANT)


############################################
# 3. CREAR VARIANTE DE LA FASE 05
############################################
# Uso:
# make variant5 VARIANT=v301 PARENT=v201 MODEL_FAMILY=dense_nn
#
# Los valores por defecto (AutoML, métricas, etc.)
# se toman de base_params.yaml y pueden modificarse
# editando params.yaml tras la creación de la variante.

variant5: check-variant-format
	@test -n "$(PARENT)" || (echo "[ERROR] Debes especificar PARENT=vNNN (variante de F04)"; exit 1)
	@test -n "$(MODEL_FAMILY)" || (echo "[ERROR] Debes especificar MODEL_FAMILY (familias soportadas: sequence_embedding, dense_bow, cnn1d)"; exit 1)
	@echo "==> Preparando parámetros específicos para Fase 05 (Modeling)"
	@$(eval SET_LIST := \
		--set parent_variant=$(PARENT) \
		--set model_family=$(MODEL_FAMILY) )
	@$(MAKE) variant-generic PHASE=$(PHASE5) VARIANT=$(VARIANT) EXTRA_SET_FLAGS="$(SET_LIST)"
	@echo "[OK] Variante $(VARIANT) creada para Fase 05."


############################################
# 4. PUBLICAR VARIANTE DE FASE 05
############################################
# En F05 se publican:
# - params.yaml
# - <phase>_params.json
# - <phase>_metadata.json   (OBLIGATORIO)
# - artefactos de modelos y splits (parquet / h5 / json)
# - informes html

publish5: check-variant-format
	@echo "==> Validando variante $(PHASE5):$(VARIANT)"
	@test -f $(VARIANTS_DIR_05)/$(VARIANT)/$(PHASE5)_metadata.json || \
	  (echo "[ERROR] Falta $(PHASE5)_metadata.json (obligatorio en F05)"; exit 1)
	$(MAKE) publish-generic PHASE=$(PHASE5) VARIANTS_DIR=$(VARIANTS_DIR_05) \
		PUBLISH_EXTS="parquet json html h5" VARIANT=$(VARIANT)


############################################
# 5. ELIMINAR VARIANTE FASE 05
############################################
remove5: check-variant-format
	$(MAKE) remove-generic PHASE=$(PHASE5) VARIANTS_DIR=$(VARIANTS_DIR_05) VARIANT=$(VARIANT)

remove5-all:
	$(MAKE) remove-phase-all PHASE=$(PHASE5) VARIANTS_DIR=$(VARIANTS_DIR_05)


############################################
# 6. CHEQUEO DE RESULTADOS
############################################
# En F05 no se valida un único dataset, sino:
# - existencia de metadata
# - al menos un candidato si se ha ejecutado la fase

script5-check-results: check-variant-format
	@test -f $(VARIANTS_DIR_05)/$(VARIANT)/$(PHASE5)_metadata.json || \
	  (echo "[FAIL] Falta $(PHASE5)_metadata.json"; exit 1)
	@echo "[OK] Metadata de Fase 05 presente"
	@test -d $(VARIANTS_DIR_05)/$(VARIANT)/candidates || \
	  (echo "[WARN] No existe carpeta candidates (¿fase no ejecutada aún?)"; exit 0)
	@echo "[OK] Carpeta candidates presente"


############################################
# 7. CHEQUEO DE DVC PARA FASE 05
############################################
script5-check-dvc:
	$(MAKE) check-dvc-generic PHASE=$(PHASE5)


############################################
# 8. LIMPIEZA DE FASE 05
############################################
clean5-all:
	$(MAKE) clean-phase-generic PHASE=$(PHASE5) VARIANTS_DIR=$(VARIANTS_DIR_05)


############################################
# 9. HELP
############################################
help5:
	@echo "==============================================="
	@echo " FASE 05 — MODELING"
	@echo "==============================================="
	@echo ""
	@echo " CREAR VARIANTE (requiere PARENT de F04):"
	@echo "   make variant5 VARIANT=v301 PARENT=v201 MODEL_FAMILY=dense_nn"
	@echo ""
	@echo " EJECUTAR NOTEBOOK:"
	@echo "   make nb5-run VARIANT=v301"
	@echo ""
	@echo " EJECUTAR SCRIPT:"
	@echo "   make script5-run VARIANT=v301"
	@echo ""
	@echo " CHEQUEOS:"
	@echo "   make script5-check-results VARIANT=v301"
	@echo "   make script5-check-dvc"
	@echo ""
	@echo " PUBLICAR:"
	@echo "   make publish5 VARIANT=v301"
	@echo ""
	@echo " LIMPIAR / ELIMINAR:"
	@echo "   make remove5 VARIANT=v301"
	@echo "   make clean5-all"
	@echo ""
	@echo " NOTAS:"
	@echo " - Cada variante F05 explora UNA familia de modelos."
	@echo " - La selección de candidatos se basa en umbral de métrica primaria."
	@echo " - Si ningún modelo supera el umbral, se conserva el mejor."
	@echo " - La metadata es obligatoria para publicar la variante."
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

	@if [ -z "$(MODELS)" ]; then \
		echo "[ERROR] MODELS es obligatorio en F06"; exit 1; \
	fi
	@if [ -z "$(PARENTS_F05)" ]; then \
		echo "[ERROR] PARENTS_F05 es obligatorio"; exit 1; \
	fi

	@echo "==> Validando MODELS"
	@$(CHECK_MODELS_YAML)

	# Tomamos el primer parent F05 como referencia de herencia
	$(eval FIRST_F05 := $(word 1,$(PARENTS_F05)))

	# Resolver F04 y F03 a partir de F05 (trazabilidad)
	$(eval F04_FROM_F05 := $(shell yq '.parent_variant' executions/05_modeling/$(FIRST_F05)/params.yaml))
	$(eval F03_FROM_F04 := $(shell yq '.parent_variant' executions/04_targetengineering/$(F04_FROM_F05)/params.yaml))

	# Herencia por defecto del régimen temporal (copia literal)
	$(eval Tu_FINAL := $(if $(Tu),$(Tu),$(shell yq '.temporal.Tu' executions/03_preparewindowsds/$(F03_FROM_F04)/params.yaml)))
	$(eval OW_FINAL := $(if $(OW),$(OW),$(shell yq '.temporal.OW' executions/03_preparewindowsds/$(F03_FROM_F04)/params.yaml)))
	$(eval PW_FINAL := $(if $(PW),$(PW),$(shell yq '.temporal.PW' executions/03_preparewindowsds/$(F03_FROM_F04)/params.yaml)))

	# Resolver F02 para el replay (herencia por defecto)
	$(eval F02_FROM_F03 := $(shell yq '.parent_variant' executions/03_preparewindowsds/$(F03_FROM_F04)/params.yaml))
	$(eval REPLAY_DATASET_FINAL := $(if $(REPLAY_DATASET),$(REPLAY_DATASET),$(F02_FROM_F03)))

	$(PYTHON) mlops4ofp/tools/params_manager.py \
		create-variant \
		--phase 06_packaging \
		--variant $(VARIANT) \
		--set parent_variants_f05="$(PARENTS_F05)" \
		--set temporal.Tu=$(Tu_FINAL) \
		--set temporal.OW=$(OW_FINAL) \
		--set temporal.PW=$(PW_FINAL) \
		--set models='$(MODELS)' \
		--set replay.dataset_id=$(REPLAY_DATASET_FINAL)

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
clean6:
	rm -rf $(VARIANTS_DIR_06)/*/figures
	rm -f $(PHASE6)_*.tar.gz

# ------------------------------------------------------------
# Ayuda
# ------------------------------------------------------------
help6:
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
	@echo "       MODELS=\"<yaml>\" \\"
	@echo "       [Tu=<valor>] [OW=<valor>] [PW=<valor>] \\"
	@echo "       [REPLAY_DATASET=<f02_variant>]"
	@echo ""
	@echo "Parámetros obligatorios:"
	@echo "  VARIANT       Nombre de la variante (vNNN)"
	@echo "  PARENTS_F05   Lista de variantes F05 (separadas por espacios)"
	@echo "  MODELS        Selección explícita de modelos (YAML)"
	@echo ""
	@echo "Parámetros opcionales (override):"
	@echo "  Tu, OW, PW    Valores temporales del sistema"
	@echo "  REPLAY_DATASET  Dataset de replay (variante F02)"
	@echo ""
	@echo "Notas:"
	@echo "  - No se admiten inputs RAW en F06."
	@echo "  - Todos los valores finales quedan sellados en params.yaml."
	@echo "=================================================="
	@echo "  make nb6-run VARIANT=vNNN"
	@echo "  make script6-run VARIANT=vNNN"
	@echo "  make check6 VARIANT=vNNN"
	@echo "  make publish6 VARIANT=vNNN"
	@echo "  make export6 VARIANT=vNNN"
	@echo "  make remove6 VARIANT=vNNN"
	@echo "  make clean6"










# ==========================================
# AYUDA GLOBAL
# ==========================================

clean-all-all:
	@echo "==> Limpiando todas las fases"
	$(MAKE) clean5-all
	$(MAKE) clean4-all
	$(MAKE) clean3-all
	$(MAKE) clean2-all
	$(MAKE) clean1-all
	@echo "[OK] Limpieza completa de todas las fases (solo parámetros y variantes)"

help:
	@echo "==============================================="
	@echo " MLOps4OFP — Pipeline en 4 Fases"
	@echo "==============================================="
	@echo ""
	@echo " FASE 01: EXPLORE (análisis de datos RAW)"
	@echo "   make help1"
	@echo ""
	@echo " FASE 02: PREPARE EVENTS (ingeniería de eventos)"
	@echo "   make help2"
	@echo ""
	@echo " FASE 03: PREPARE WINDOWS (generación de ventanas)"
	@echo "   make help3"
	@echo ""
	@echo " MANTENIMIENTO:"
	@echo "   make help-setup          # Setup inicial del proyecto"
	@echo "   make clean-all-all       # Limpia todas las fases"
	@echo ""
	@echo "==============================================="

.PHONY: \
	setup check-setup clean-setup help-setup \
	nb-run-generic script-run-generic publish-generic remove-generic check-dvc-generic check-results-generic clean-phase-generic export-generic \
	nb1-run nb2-run nb3-run nb4-run \
	script1-run script1-repro script1-check-results script1-check-dvc script2-run script2-repro script2-check-results script2-check-dvc script3-run script3-repro script3-check-results script3-check-dvc \
	script4-run \
	variant1 variant2 variant3 variant4 variant-generic check-variant-format \
	publish1 publish2 publish3 publish4\
	remove1 remove2 remove3 remove4 \
	export3 \
	clean1-all clean2-all clean3-all clean4-all clean-all-all \
	tag1-stage-ready tag1-script-ready tag1-stable tag2-stage-ready tag2-script-ready tag2-stable tag3-stage-ready tag3-script-ready tag3-stable \
	help1 help2 help3 help4 help \
	advise4 \
	switch-remote-local switch-remote-public switch-remote-private check-remotes
