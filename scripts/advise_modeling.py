#!/usr/bin/env python3
"""
advise_modeling.py

Asistente de recomendación de técnicas de modelado para MLOps4OFP.

Lee el summary.json generado en la Fase 04 (Target Engineering) y consulta
a ChatGPT (OpenAI API) para recomendar técnicas de modelado compatibles con:
- TensorFlow
- TensorFlow Lite
- TensorFlow Lite for Microcontrollers (TFLM, ESP32-class MCU)

Salida:
- Informe Markdown: <PHASE>_advice.md dentro de la carpeta de la variante.
"""

import argparse
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai import OpenAI

from mlops4ofp.tools.run_context import (
    detect_execution_dir,
    detect_project_root,
)


# ============================================================
# Utilidades
# ============================================================

def load_summary(project_root: Path, phase: str, variant: str):
    """Carga el summary.json de la variante indicada."""
    summary_path = (
        project_root
        / "executions"
        / phase
        / variant
        / f"{phase}_summary.json"
    )

    if not summary_path.exists():
        raise FileNotFoundError(f"No se encontró summary.json: {summary_path}")

    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    return summary, summary_path


def build_prompt(summary: dict) -> str:
    """Construye el prompt a partir del summary.json."""
    summary_json = json.dumps(summary, indent=2, ensure_ascii=False)

    prompt = f"""
Eres un experto en aprendizaje automático en el borde (edge ML) y en despliegue de modelos
con TensorFlow Lite for Microcontrollers sobre microcontroladores tipo ESP32.

Tu tarea es actuar como ASESOR TÉCNICO para recomendar técnicas de modelado adecuadas
para el siguiente problema y dataset, generados en la Fase 04 (Target Engineering)
de un pipeline MLOps.

Resumen estructurado del problema y dataset:

```json
{summary_json}
```

Contexto:
- Clasificación binaria de secuencias de eventos (listas de enteros).
- Target definido por un OR de eventos en la ventana de predicción.
- Dataset potencialmente muy desbalanceado (eventos raros).

Restricciones:
- Entrenamiento en TensorFlow.
- Exportable a TensorFlow Lite.
- Compatible con TensorFlow Lite for Microcontrollers (ESP32-class MCU).
- Inferencia en microcontrolador con recursos muy limitados.

Produce la respuesta en CASTELLANO (España), en formato Markdown, con la estructura:

1. Resumen del problema
2. Representación recomendada de los datos
3. Modelos candidatos compatibles con TFLite/TFLM
4. Modelo principal recomendado
5. Modelo baseline recomendado
6. Advertencias y recomendaciones prácticas
7. Próximos pasos sugeridos en F05

No incluyas código ejecutable completo. Sé técnico, claro y conciso.
"""
    return prompt


def call_openai(prompt: str) -> str:
    """Llama a la API de OpenAI y devuelve el texto de respuesta."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY no está definido en el entorno."
        )

    client = OpenAI()

    response = client.responses.create(
        model="gpt-5.2",
        input=prompt,
    )

    return response.output_text


def save_advice(variant_root: Path, phase: str, advice_text: str) -> Path:
    """Guarda el informe de recomendación en Markdown."""
    advice_path = variant_root / f"{phase}_advice.md"
    advice_path.write_text(advice_text, encoding="utf-8")
    return advice_path


# ============================================================
# Main
# ============================================================

def main(phase: str, variant: str):
    execution_dir = detect_execution_dir()
    project_root = detect_project_root(execution_dir)

    print(f"[INFO] execution_dir = {execution_dir}")
    print(f"[INFO] project_root  = {project_root}")
    print(f"[INFO] phase         = {phase}")
    print(f"[INFO] variant       = {variant}")

    variant_root = project_root / "executions" / phase / variant
    if not variant_root.exists():
        raise FileNotFoundError(f"No existe la variante: {variant_root}")

    summary, summary_path = load_summary(project_root, phase, variant)
    print(f"[INFO] summary cargado desde: {summary_path}")

    prompt = build_prompt(summary)

    print("[INFO] Consultando a ChatGPT (OpenAI API)...")
    advice_text = call_openai(prompt)

    advice_path = save_advice(variant_root, phase, advice_text)
    print(f"[OK] Informe guardado en: {advice_path}")

    print("\n--- INICIO DEL INFORME (preview) ---")
    print("\n".join(advice_text.splitlines()[:25]))
    print("--- FIN DEL PREVIEW ---")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Asistente de recomendación de modelado (Fase 04)"
    )
    parser.add_argument(
        "--phase",
        default="04_targetengineering",
        help="Fase (por defecto: 04_targetengineering)"
    )
    parser.add_argument(
        "--variant",
        required=True,
        help="Variante vNNN de la fase indicada"
    )

    args = parser.parse_args()
    main(args.phase, args.variant)
