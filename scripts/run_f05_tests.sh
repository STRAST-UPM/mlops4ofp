#!/usr/bin/env bash
set -euo pipefail

echo "==============================================="
echo " FASE 05 — BATERÍA DE PRUEBAS AUTOMATIZADA"
echo "==============================================="

PARENTS=("v903" "v904" "v905" "v906")
FAMILIES=("sequence_embedding" "dense_bow" "cnn1d")

# Numeración manual de variantes para claridad
VARIANTS=(
  "v503" "v504" "v505"
  "v506" "v507" "v508"
  "v509" "v510" "v511"
  "v512" "v513" "v514"
)

i=0

for PARENT in "${PARENTS[@]}"; do
  for FAMILY in "${FAMILIES[@]}"; do

    VARIANT="${VARIANTS[$i]}"
    i=$((i+1))

    echo ""
    echo "-----------------------------------------------"
    echo " VARIANT=${VARIANT}  PARENT=${PARENT}  FAMILY=${FAMILY}"
    echo "-----------------------------------------------"

    echo "[1/4] Creando variante"
    make variant5 VARIANT="${VARIANT}" PARENT="${PARENT}" MODEL_FAMILY="${FAMILY}" \
      || { echo "[FAIL] variant5 ${VARIANT}"; continue; }

    echo "[2/4] Ejecutando script5-run"
    if ! make script5-run VARIANT="${VARIANT}"; then
      echo "[ERROR] script5-run falló para ${VARIANT}"
      echo "→ Posible familia no soportada (${FAMILY})"
      continue
    fi

    echo "[3/4] Ejecutando check5"
    if ! make check5 VARIANT="${VARIANT}"; then
      echo "[ERROR] check5 falló para ${VARIANT}"
      continue
    fi

    echo "[4/4] Resumen rápido (grep)"

    VARIANT_DIR="executions/05_modeling/${VARIANT}"

    echo "  · model_family:"
    grep -H "\"model_family\"" "${VARIANT_DIR}/05_modeling_metadata.json" || true

    echo "  · num_experiments / num_candidates:"
    grep -H "\"num_experiments\"" "${VARIANT_DIR}/05_modeling_metadata.json" || true
    grep -H "\"num_candidates\"" "${VARIANT_DIR}/05_modeling_metadata.json" || true

    echo "  · candidatos:"
    grep -H "\"candidate_id\"" "${VARIANT_DIR}/05_modeling_metadata.json" || true

    echo "  · recalls:"
    grep -H "\"val_recall\"" "${VARIANT_DIR}"/experiments/*/metrics.json 2>/dev/null | head -5 || true

    echo "  · matrices de confusión:"
    grep -H "\"tp\"" "${VARIANT_DIR}/05_modeling_metadata.json" || true

    echo "  · figuras:"
    ls "${VARIANT_DIR}/figures" 2>/dev/null || echo "    (sin figuras)"

    echo "[OK] Variante ${VARIANT} revisada"

  done
done

echo ""
echo "==============================================="
echo " FIN DE PRUEBAS FASE 05"
echo "==============================================="

