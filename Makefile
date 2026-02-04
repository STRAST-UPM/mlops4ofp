############################################
# CARGA AUTOMÁTICA DE VARIABLES DE ENTORNO
# (MLflow, etc.)
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
	@echo "  make setup"
	@echo "      Toma por defecto setup/config_default.yaml"
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
ifdef SETUP_CFG
	@python3 $(SETUP_PY) --config $(SETUP_CFG)
else
	@python3 $(SETUP_PY)
endif

check-setup:
	@echo "==> Verificando entorno base"
	@python3 setup/check_env.py
	@echo "==> Verificando configuración del proyecto"
	@.venv/bin/python setup/check_setup.py

clean-setup:
	@echo "==> Eliminando configuración de setup"
	@rm -rf .mlops4ofp
	@echo "[OK] Setup eliminado. El proyecto vuelve a estado post-clone."



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



# ==========================================
# AYUDA GLOBAL
# ==========================================

clean-all-all:
	@echo "==> Limpiando todas las fases"
	$(MAKE) clean1-all
	$(MAKE) clean2-all
	$(MAKE) clean3-all
	@echo "[OK] Limpieza completa de todas las fases (solo parámetros y variantes)"

help:
	@echo "==============================================="
	@echo " MLOps4OFP — Pipeline en 3 Fases"
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
	nb1-run nb2-run nb3-run \
	script1-run script1-repro script1-check-results script1-check-dvc script2-run script2-repro script2-check-results script2-check-dvc script3-run script3-repro script3-check-results script3-check-dvc \
	variant1 variant2 variant3 variant-generic check-variant-format \
	publish1 publish2 publish3 \
	remove1 remove2 remove3 \
	export3 \
	clean1-all clean2-all clean3-all clean-all-all \
	tag1-stage-ready tag1-script-ready tag1-stable tag2-stage-ready tag2-script-ready tag2-stable tag3-stage-ready tag3-script-ready tag3-stable \
	help1 help2 help3 help \
	switch-remote-local switch-remote-public switch-remote-private check-remotes
