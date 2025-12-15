############################################
# MLOps4OFP — MAKEFILE 
############################################

ifneq ("$(wildcard .venv/bin/python3)","")
	PYTHON := .venv/bin/python3
else
	$(error "❌ No existe .venv. Ejecuta: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt")
endif

$(info [INFO] Usando intérprete Python: $(PYTHON))

##########################################
# DVC REMOTE MANAGEMENT
##########################################

# --- Switching remotes ---
switch-local:
	@echo "→ Configurando remoto LOCAL"
	$(PYTHON) project_setup/switch_to_local_remote.py

switch-private:
	@echo "→ Configurando remoto PRIVADO (DAGsHub con token)"
	$(PYTHON) project_setup/switch_to_dagshub_private_remote.py

switch-public:
	@echo "→ Configurando remoto PÚBLICO (DAGsHub sin token)"
	$(PYTHON) project_setup/switch_to_dagshub_public_remote.py

# --- Verificación ---
check-remotes:
	@echo "→ Verificando configuración de remotos"
	$(PYTHON) project_setup/check_remotes.py

help0:
	@echo "---- FASE 00 config ----"
	@echo "make switch-local       Configura el remoto DVC para local"
	@echo "make switch-private     Configura el remoto privado de DAGsHub"
	@echo "make switch-public      Configura el remoto DVC público en DAGsHub"
	@echo "make check-remotes      Verifica la configuración Git, DVC"

############################################
# FASE 01 — EXPLORE (VARIANTES + PUBLICACIÓN)
############################################

PHASE1=01_explore
NOTEBOOK1=notebooks/01_explore.ipynb
#SCRIPT1=scripts/01_explore/01_explore.py
SCRIPT1=scripts/01_explore.py

# Directorio raíz de variantes para esta fase
VARIANTS_DIR_01 = params/$(PHASE1)

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
	@echo "==> Ejecutando notebook FASE 01: $(NOTEBOOK1) con variante $(VARIANT)"
	ACTIVE_VARIANT=$(VARIANT) \
	jupyter nbconvert --to notebook --execute --inplace $(NOTEBOOK1)

############################################
# 2. EJECUCIÓN DE LA SCRIPT
############################################
script1-run:
	@echo "==> Ejecutando script FASE 01: $(SCRIPT1) para variante $(VARIANT)"
	$(PYTHON) $(SCRIPT1) --variant $(VARIANT)

############################################
# 3. CREAR UNA VARIANTE DE LA FASE 01
############################################
# Uso:
#   make variant1 VARIANT=vNNN RAW=/ruta/dataset \
#        CLEANING_STRATEGY=basic \
#        NAN_VALUES="[-999999, None]" \
#        ERROR_VALUES='{"col1":[-1],"col2":[999]}'

variant1:
	@test -n "$(VARIANT)" || (echo "[ERROR] Uso: make variant1 VARIANT=v00X ..."; exit 1)
	@test -n "$(RAW)" || (echo "[ERROR] Debes especificar RAW=/ruta/dataset.csv"; exit 1)
	@echo "==> Creando variante $(PHASE1):$(VARIANT)"

	# Construir lista de parámetros --set
	$(eval SET_LIST := )

	# Añadir parámetro CLEANING_STRATEGY si existe
ifneq ($(strip $(CLEANING)),)
	$(eval SET_LIST += --set cleaning_strategy=$(CLEANING))
endif

	# Añadir parámetro NAN_VALUES si existe
ifneq ($(strip $(NAN_VALUES)),)
	$(eval SET_LIST += --set nan_values='$(NAN_VALUES)')
endif

	# Añadir parámetro ERROR_VALUES si existe
ifneq ($(strip $(ERROR_VALUES)),)
	$(eval SET_LIST += --set error_values_by_column='$(ERROR_VALUES)')
endif

	# Llamada única al gestor de variantes
	$(PYTHON) mlops4ofp/tools/params_manager.py create-variant \
		--phase $(PHASE1) \
		--variant $(VARIANT) \
		--raw $(RAW) \
		$(SET_LIST)

	@echo "[OK] Variante configurada: $(VARIANT)"

	

############################################
# 4. PUBLICAR VARIANTE DE LA FASE 01
############################################
# Uso:
#   make publish1 VARIANT=v001

publish1: check-variant-format
	@test -n "$(VARIANT)" || (echo "[ERROR] Uso: make publish1 VARIANT=v00X"; exit 1)

	@echo "==> Validando variante $(PHASE1):$(VARIANT)"
	$(PYTHON) mlops4ofp/tools/traceability.py validate-variant \
		--phase $(PHASE1) --variant $(VARIANT)

	@echo "==> Registrando artefactos DVC"
	dvc add $(VARIANTS_DIR_01)/$(VARIANT)/*.parquet
	dvc add $(VARIANTS_DIR_01)/$(VARIANT)/*.json
	dvc add $(VARIANTS_DIR_01)/$(VARIANT)/*.html

	@echo "==> Commit + push"
	git add -f $(VARIANTS_DIR_01)/$(VARIANT)/*.dvc
	git add $(VARIANTS_DIR_01)/variants.yaml

	git commit -m "publish variant: $(PHASE1) $(VARIANT)" || true
	git push
	dvc push

	@echo "[OK] Publicación completada: variante $(PHASE1):$(VARIANT)"


############################################
# 5. ELIMINAR VARIANTE (SI NO TIENE HIJOS)
############################################
# Uso:
#   make remove1 VARIANT=v001

remove1: check-variant-format
	@test -n "$(VARIANT)" || (echo "[ERROR] Uso: make remove1 VARIANT=vNNN"; exit 1)

	@echo "==> Comprobando si la variante $(PHASE1):$(VARIANT) tiene hijos…"
	$(PYTHON) mlops4ofp/tools/traceability.py can-delete \
		--phase $(PHASE1) --variant $(VARIANT)

	@echo "==> Eliminando carpeta completa de la variante"
	rm -rf $(VARIANTS_DIR_01)/$(VARIANT)

	@echo "==> Actualizando registro de variantes"
	$(PYTHON) mlops4ofp/tools/params_manager.py delete-variant \
		--phase $(PHASE1) --variant $(VARIANT)

	@echo "==> Commit + push"
	git add -A
	git commit -m "remove variant: $(PHASE1) $(VARIANT)" || true
	git push

	@echo "[OK] Variante $(PHASE1):$(VARIANT) eliminada completamente."



############################################
# 6. REPRODUCIR VIA DVC (opcional)
############################################
script1-repro:
	@echo "==> Ejecutando dvc repro $(PHASE1)"
	dvc repro $(PHASE1)
	dvc push


############################################
# 7. CHEQUEO DE RESULTADOS
############################################
script1-check-results:
	@echo "===== CHECKING 01_explore results ====="
	@test -f $(VARIANTS_DIR_01)/$(VARIANT)/01_dataset_explored.parquet \
	    && echo "[OK] Dataset explored" \
	    || echo "[FAIL] Missing dataset"

	@test -f $(VARIANTS_DIR_01)/$(VARIANT)/01_explore_metadata.json \
	    && echo "[OK] Metadata generated" \
	    || echo "[FAIL] Missing metadata"

	@test -f $(VARIANTS_DIR_01)/$(VARIANT)/01_explore_params.json \
	    && echo "[OK] Params generated" \
	    || echo "[FAIL] Missing params"

	@test -f $(VARIANTS_DIR_01)/$(VARIANT)/01_explore_report.html \
	    && echo "[OK] Report HTML generated" \
	    || echo "[FAIL] Missing HTML report"

	@echo "[INFO] Las figuras solo se generan en el notebook. OK."

	@echo "========================================"



############################################
# 8. CHEQUEO DE DVC
############################################
script1-check-dvc:
	@echo "===== CHECKING DVC STATUS ====="
	@dvc status --cloud && echo "[OK] Local DVC clean" || echo "[FAIL] Local DVC has changes"
	@echo "[Checking remote DVC...]"
	@dvc status -r storage -c && echo "[OK] Remote up to date" || echo "[FAIL] Remote missing data"
	@echo "================================"


############################################
# 9. LIMPIEZA TOTAL DE FASE 01
############################################
clean1-all:
	@echo "==> Limpiando variantes de Fase 01"
	rm -rf params/01_explore/v*
	@echo "==> Eliminando registro de variantes de Fase 01"
	rm -f params/01_explore/variants.yaml
	@echo "[OK] Limpieza completa de Fase 01 (solo parámetros y variantes)"

############################################
# 9. TAGGING
############################################

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
	@echo "---- FASE 01 explore ----"
	@echo "make nb1-run VARIANT=vNNN                   Ejecuta notebook con variante"
	@echo "make script1-run VARIANT=vNNN               Ejecuta script con variante"
	@echo "make variant1 VARIANT=vNNN RAW=/ruta.csv \\"
	@echo "             [CLEANING=...] [NANVALUES='[...]'] [ERRORS=...]"
	@echo "                                            Crea variante con parámetros"
	@echo "make variant1 VARIANT=v001 RAW=./data/raw.csv CLEANING=basic NANVALUES='[-999999.0]'"
	@echo "make publish1 VARIANT=vNNN                  Publica variante"
	@echo "make remove1 VARIANT=vNNN                   Elimina variante (si no tiene hijos)"
	@echo "make script1-repro                          Ejecuta dvc repro fase 01"
	@echo "make script1-check-results VARIANT=vNNN     Verifica artefactos generados"
	@echo "make script1-check-dvc                      Chequea estado de DVC"
	@echo "make clean1-all                             Limpieza total de fase 01"
	@echo "make tag1-*                                 Tagging de fase"

# ==========================================
# FASE 02 — prepareEventsDS
# ==========================================

PHASE2=02_prepareeventsds
VARIANTS_DIR_02 = params/$(PHASE2)
NOTEBOOK2=notebooks/02_prepareeventsds.ipynb
#SCRIPT2=scripts/02_prepareeventsds/02_prepareeventsds.py
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
	@echo "==> Ejecutando notebook FASE 02 para variante $(VARIANT)"
	ACTIVE_VARIANT=$(VARIANT) \
	jupyter nbconvert --to notebook \
	    --execute \
	    --inplace \
	    $(NOTEBOOK2)
		
script2-run: check-variant-format
	@echo "==> Ejecutando script FASE 02 para variante $(VARIANT)"
	$(PYTHON) $(SCRIPT2) --variant $(VARIANT)

variant2: check-variant-format
	@test -n "$(BANDS)" || (echo "[ERROR] Debes especificar BANDS=\"40 60 90\""; exit 1)
	@test -n "$(STRATEGY)" || (echo "[ERROR] Debes especificar STRATEGY=levels|transitions|both"; exit 1)
	@test -n "$(NAN)" || (echo "[ERROR] Debes especificar NAN=keep|discard"; exit 1)
	@test -n "$(PARENT)" || (echo "[ERROR] Debes especificar PARENT=vNNN (variante de fase 01)"; exit 1)

	$(eval BANDS_YAML := [$(shell echo $(BANDS) | sed 's/ /, /g')] )
ifneq ($(strip $(TU)),)
	$(eval SET_TU := --set Tu=$(TU))
else
	$(eval SET_TU := )
endif

	python3 mlops4ofp/tools/params_manager.py create-variant \
		--phase 02_prepareeventsds \
		--variant $(VARIANT) \
		--set band_thresholds_pct='$(BANDS_YAML)' \
		--set event_strategy=$(STRATEGY) \
		--set nan_handling=$(NAN) \
		--set parent_variant=$(PARENT) \
		$(SET_TU)

	@echo "[OK] Variante 02 creada: $(VARIANT)"


publish2: check-variant-format
	@echo "==> Validando variante $(PHASE2):$(VARIANT)"
	$(PYTHON) mlops4ofp/tools/traceability.py validate-variant \
		--phase $(PHASE2) --variant $(VARIANT)

	@echo "==> Registrando artefactos DVC"
	dvc add $(VARIANTS_DIR_02)/$(VARIANT)/*.parquet
	dvc add $(VARIANTS_DIR_02)/$(VARIANT)/*.json
	dvc add $(VARIANTS_DIR_02)/$(VARIANT)/*.html

	git add -f $(VARIANTS_DIR_02)/$(VARIANT)/*.dvc
	git add $(VARIANTS_DIR_02)/variants.yaml

	git commit -m "publish variant: $(PHASE2) $(VARIANT)" || true
	git push
	dvc push

	@echo "[OK] Publicación completada"

remove2: check-variant-format
	@echo "==> Comprobando si la variante puede ser eliminada…"
	$(PYTHON) mlops4ofp/tools/traceability.py can-delete \
		--phase $(PHASE2) --variant $(VARIANT)

	@echo "==> Eliminando carpeta de variante"
	rm -rf $(VARIANTS_DIR_02)/$(VARIANT)

	@echo "==> Actualizando registro"
	$(PYTHON) mlops4ofp/tools/params_manager.py delete-variant \
		--phase $(PHASE2) --variant $(VARIANT)

	git add -A
	git commit -m "remove variant: $(PHASE2) $(VARIANT)" || true
	git push

	@echo "[OK] Variante eliminada"

script2-check-results: check-variant-format
	@echo "===== CHECKING 02_prepareeventsds results ====="

	@test -f $(VARIANTS_DIR_02)/$(VARIANT)/02_prepareeventsds.parquet \
	    && echo "[OK] Dataset events" \
	    || echo "[FAIL] Missing events dataset"

	@test -f $(VARIANTS_DIR_02)/$(VARIANT)/02_prepareeventsds_event_dict.json \
	    && echo "[OK] Event dictionary" \
	    || echo "[FAIL] Missing event dictionary"

	@test -f $(VARIANTS_DIR_02)/$(VARIANT)/02_prepareeventsds_minmax_stats.json \
	    && echo "[OK] Minmax stats" \
	    || echo "[FAIL] Missing minmax"

	@test -f $(VARIANTS_DIR_02)/$(VARIANT)/02_prepareeventsds_report.html \
	    && echo "[OK] HTML report" \
	    || echo "[FAIL] Missing HTML report"

	@echo "========================================"

script2-check-dvc:
	@echo "===== CHECKING DVC STATUS (FASE 02) ====="
	@dvc status --cloud && echo "[OK] Local DVC clean" || echo "[FAIL] Local DVC has changes"
	@echo "[Checking remote DVC...]"
	@dvc status -r storage -c && echo "[OK] Remote up to date" || echo "[FAIL] Remote missing data"
	@echo "=========================================="

clean2-all:
	@echo "==> Limpiando variantes de Fase 02"
	rm -rf params/02_prepareeventsds/v*

	@echo "==> Eliminando registro de variantes de Fase 02"
	rm -f params/02_prepareeventsds/variants.yaml

	@echo "[OK] Limpieza completa de Fase 02 (solo parámetros y variantes)"


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
	@echo "---- FASE 02 prepareEventsDS ----"
	@echo "make variant2 VARIANT=vNNN BANDS=\"40 60 90\" STRATEGY=both NAN=keep"
	@echo "make nb2-run VARIANT=vNNN"
	@echo "make script2-run VARIANT=vNNN"
	@echo "make publish2 VARIANT=vNNN"
	@echo "make remove2 VARIANT=vNNN"
	@echo "make script2-check-results VARIANT=vNNN"
	@echo "make script2-check-dvc                      Chequea estado de DVC"
	@echo "make clean2-all                             Limpieza total de fase 01"
	@echo "make tag2-*                                 Tagging de fase"

# ==========================================

PHASE3=03_preparewindowsds
VARIANTS_DIR_03 = params/$(PHASE3)
NOTEBOOK3=notebooks/03_preparewindowsds.ipynb
#SCRIPT3=scripts/03_preparewindowsds/03_preparewindowsds.py
SCRIPT3=scripts/03_preparewindowsds.py


############################################
# 1. EJECUCIÓN DEL NOTEBOOK
############################################
nb3-run: check-variant-format
	@echo "==> Ejecutando notebook FASE 03 para variante $(VARIANT)"
	ACTIVE_VARIANT=$(VARIANT) \
	jupyter nbconvert --to notebook \
	    --execute \
	    --inplace \
	    $(NOTEBOOK3)


############################################
# 2. EJECUCIÓN DE LA SCRIPT
############################################
script3-run: check-variant-format
	@echo "==> Ejecutando script FASE 03 para variante $(VARIANT)"
	$(PYTHON) $(SCRIPT3) --variant $(VARIANT)


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

	@echo "==> Creando variante Fase 03: $(VARIANT)"

	$(PYTHON) mlops4ofp/tools/params_manager.py create-variant \
		--phase 03_preparewindowsds \
		--variant $(VARIANT) \
		--set variant_id=$(VARIANT) \
		--set parent_variant=$(PARENT) \
		--set OW=$(OW) \
		--set LT=$(LT) \
		--set PW=$(PW) \
		--set window_strategy=$(WS) \
		--set nan_strategy=$(NAN) 

	@echo "[OK] Variante $(VARIANT) creada para Fase 03."


############################################
# 4. PUBLICAR VARIANTE DE FASE 03
############################################
publish3: check-variant-format
	@echo "==> Validando variante $(PHASE3):$(VARIANT)"
	$(PYTHON) mlops4ofp/tools/traceability.py validate-variant \
		--phase $(PHASE3) --variant $(VARIANT)

	@echo "==> Registrando artefactos DVC"
	dvc add $(VARIANTS_DIR_03)/$(VARIANT)/*.parquet
	dvc add $(VARIANTS_DIR_03)/$(VARIANT)/*.yaml
	dvc add $(VARIANTS_DIR_03)/$(VARIANT)/*.pdf

	git add -f $(VARIANTS_DIR_03)/$(VARIANT)/*.dvc
	git add $(VARIANTS_DIR_03)/variants.yaml

	git commit -m "publish variant: $(PHASE3) $(VARIANT)" || true
	git push
	dvc push

	@echo "[OK] Publicación completada para variante $(PHASE3):$(VARIANT)"


############################################
# 5. ELIMINAR VARIANTE FASE 03
############################################
remove3: check-variant-format
	@echo "==> Comprobando si la variante puede ser eliminada…"
	$(PYTHON) mlops4ofp/tools/traceability.py can-delete \
		--phase $(PHASE3) --variant $(VARIANT)

	@echo "==> Eliminando carpeta completa de la variante"
	rm -rf $(VARIANTS_DIR_03)/$(VARIANT)

	@echo "==> Actualizando registro de variantes"
	$(PYTHON) mlops4ofp/tools/params_manager.py delete-variant \
		--phase $(PHASE3) --variant $(VARIANT)

	git add -A
	git commit -m "remove variant: $(PHASE3) $(VARIANT)" || true
	git push

	@echo "[OK] Variante eliminada"


############################################
# 6. CHEQUEO DE RESULTADOS
############################################
script3-check-results: check-variant-format
	@echo "===== CHECKING 03_preparewindowsds results ====="

	@test -f $(VARIANTS_DIR_03)/$(VARIANT)/03_preparewindowsds_windows.parquet \
	    && echo "[OK] Windows dataset" \
	    || echo "[FAIL] Missing windows dataset"

	@test -f $(VARIANTS_DIR_03)/$(VARIANT)/03_preparewindowsds_metadata.yaml \
	    && echo "[OK] Metadata" \
	    || echo "[FAIL] Missing metadata"

	@test -f $(VARIANTS_DIR_03)/$(VARIANT)/03_preparewindowsds_params.yaml \
	    && echo "[OK] Params" \
	    || echo "[FAIL] Missing params"

	@test -f $(VARIANTS_DIR_03)/$(VARIANT)/03_preparewindowsds_report.pdf \
	    && echo "[OK] PDF report" \
	    || echo "[FAIL] Missing report"

	@echo "========================================"


############################################
# 7. CHEQUEO DE DVC PARA FASE 03
############################################
script3-check-dvc:
	@echo "===== CHECKING DVC STATUS (FASE 03) ====="
	@dvc status --cloud && echo "[OK] Local DVC clean" || echo "[FAIL] Local DVC has changes"
	@echo "[Checking remote DVC...]"
	@dvc status -r storage -c && echo "[OK] Remote up to date" || echo "[FAIL] Remote missing data"
	@echo "=========================================="


############################################
# 8. LIMPIEZA DE FASE 03
############################################
clean3-all:
	@echo "==> Eliminando variantes FASE 03"
	rm -rf params/03_preparewindowsds/v*

	@echo "==> Eliminando registro de variantes"
	rm -f params/03_preparewindowsds/variants.yaml

	@echo "[OK] Limpieza total completada (FASE 03)"

############################################
# export
############################################

export3:
	@echo "Exportando dataset F03 variante $(VARIANT)"
	mkdir -p exports/03_preparewindowsds/$(VARIANT)
	cp params/03_preparewindowsds/$(VARIANT)/03_preparewindowsds_dataset.parquet \
	   exports/03_preparewindowsds/$(VARIANT)/03_preparewindowsds_dataset.parquet
	cp params/03_preparewindowsds/$(VARIANT)/03_preparewindowsds_metadata.json \
	   exports/03_preparewindowsds/$(VARIANT)/03_preparewindowsds_metadata.json
	cp params/02_prepareeventsds/$(PARENT)/02_prepareeventsds_event_catalog.json \
	   exports/03_preparewindowsds/$(VARIANT)/
	cp params/03_preparewindowsds/README_dataset.md \
	   exports/03_preparewindowsds/$(VARIANT)/README.md
	@echo "[OK] Export completado: exports/03_preparewindowsds/$(VARIANT)/"





############################################
# 9. HELP
############################################
help3:
	@echo "---- FASE 03 prepareWindowsDS ----"
	@echo "make variant3 VARIANT=vNNN OW=.. LT=.. PW=.. WS=.. NAN=.. PARENT=vNNN"
	@echo "make nb3-run VARIANT=vNNN"
	@echo "make script3-run VARIANT=vNNN"
	@echo "make publish3 VARIANT=vNNN"
	@echo "make remove3 VARIANT=vNNN"
	@echo "make script3-check-results VARIANT=vNNN"
	@echo "make script3-check-dvc"
	@echo "make clean3-all"



# ==========================================
# AYUDA GLOBAL
# ==========================================

make clean-all-all:
	@echo "==> Limpiando todas las fases"
	make clean1-all
	make clean2-all
	make clean3-all
	@echo "[OK] Limpieza completa de todas las fases (solo parámetros y variantes)"

help:
	@echo "---- AYUDA GLOBAL ----"
	@echo "Fase 01 (explore):            make help1"
	@echo "Fase 02 (prepareEventsDS):    make help2"
	@echo "Fase 03 (prepareWindowsDS):   make help3"

.PHONY: nb1-run nb1-save nb1-push nb1-git nb1-dev \
        script1-run script1-repro tag1-stage-ready tag1-script-ready tag1-stable \
        clean1-outputs help1 \
        nb2-run nb2-save nb2-push nb2-git nb2-dev \
        script2-run script2-repro tag2-stage-ready tag2-script-ready tag2-stable \
        clean2-outputs new-variant help2 \
        nb3-run nb3-save nb3-push nb3-git nb3-dev \
        script3-run script3-repro tag3-stage-ready tag3-script-ready tag3-stable \
        clean3-outputs new-variant3 help3 help
