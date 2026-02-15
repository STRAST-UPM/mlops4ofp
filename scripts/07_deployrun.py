#!/usr/bin/env python3

"""
Fase 07 — Deploy & Runtime Validation

Modos:
  --mode prepare   → genera manifest.json
  --mode run       → ejecuta server + cliente + métricas + informe
  --mode server    → arranca servidor Flask

Diseño:
- Cliente y servidor encapsulados.
- Idempotente.
- Caja negra.
- No depende dinámicamente de F06.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
from flask import Flask, request, jsonify
import tensorflow as tf
import matplotlib.pyplot as plt

# ============================================================
# Bootstrap proyecto
# ============================================================

SCRIPT_PATH = Path(__file__).resolve()
ROOT = SCRIPT_PATH
for _ in range(10):
    if (ROOT / "mlops4ofp").exists():
        break
    ROOT = ROOT.parent
else:
    raise RuntimeError("No se pudo localizar project root")

sys.path.insert(0, str(ROOT))

from mlops4ofp.tools.params_manager import ParamsManager
from mlops4ofp.tools.traceability import write_metadata
from mlops4ofp.tools.run_context import detect_execution_dir, detect_project_root


# ============================================================
# Utilidades
# ============================================================

def ensure_clean_dir(path: Path):
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def load_manifest(variant_root: Path):
    manifest_path = variant_root / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("manifest.json no encontrado. Ejecuta variant7 primero.")
    return json.loads(manifest_path.read_text())


# ============================================================
# PREPARE MODE
# ============================================================

def prepare_variant(variant: str):

    execution_dir = detect_execution_dir()
    project_root = detect_project_root(execution_dir)

    pm = ParamsManager("07_deployrun", project_root)
    pm.set_current(variant)
    variant_root = pm.current_variant_dir()

    with open(variant_root / "params.yaml", "r") as f:
        params = json.loads(json.dumps(pd.read_yaml(f))) if False else None

    import yaml
    with open(variant_root / "params.yaml", "r") as f:
        params = yaml.safe_load(f)

    parent_f06 = params["parent_variant_f06"]

    f06_root = project_root / "executions" / "06_packaging" / parent_f06
    if not f06_root.exists():
        raise FileNotFoundError(f"No existe F06 {parent_f06}")

    metadata_path = f06_root / "06_packaging_metadata.json"
    f06_metadata = json.loads(metadata_path.read_text())

    models = []
    for m in f06_metadata["models"]:
        prediction_name = m["prediction_name"]
        model_dir = next((f06_root / "models").glob(f"{prediction_name}__*"))
        models.append({
            "prediction_name": prediction_name,
            "model_dir": str(model_dir),
            "model_h5": "model.h5",
            "model_summary": "model_summary.json"
        })

    datasets = []
    for d in f06_metadata["datasets"]:
        datasets.append({
            "dataset_path": d,
            "x_column": "OW_events",
            "y_column": "label"
        })

    manifest = {
        "f06_variant": parent_f06,
        "f06_path": str(f06_root),
        "models": models,
        "datasets": datasets
    }

    (variant_root / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print("[OK] manifest.json generado")


# ============================================================
# SERVER MODE
# ============================================================

def run_server(variant: str):

    execution_dir = detect_execution_dir()
    project_root = detect_project_root(execution_dir)

    pm = ParamsManager("07_deployrun", project_root)
    pm.set_current(variant)
    variant_root = pm.current_variant_dir()

    manifest = load_manifest(variant_root)

    loaded_models = []

    for m in manifest["models"]:
        model_dir = Path(m["model_dir"])
        summary = json.loads((model_dir / m["model_summary"]).read_text())
        model = tf.keras.models.load_model(model_dir / m["model_h5"])

        loaded_models.append({
            "prediction_name": summary["prediction_name"],
            "model": model,
            "vectorization": summary["vectorization"],
            "threshold": summary.get("threshold", 0.5)
        })

    app = Flask(__name__)

    def vectorize(window, config):
        if config["vectorization"] == "dense_bow":
            vocab = config["vocab"]
            index = {ev: i for i, ev in enumerate(vocab)}
            X = np.zeros((1, config["input_dim"]), dtype=np.float32)
            for ev in window:
                if ev in index:
                    X[0, index[ev]] += 1.0
            return X

        if config["vectorization"] == "sequence":
            vocab = config["vocab"]
            index = {ev: i + 1 for i, ev in enumerate(vocab)}
            seq = [index[e] for e in window if e in index]
            max_len = config["max_len"]
            X = np.zeros((1, max_len), dtype=np.int32)
            seq = seq[-max_len:]
            X[0, -len(seq):] = seq
            return X

        raise ValueError("Vectorization no soportada")

    @app.route("/infer", methods=["POST"])
    def infer():
        window = request.json["window"]
        results = []

        for m in loaded_models:
            X = vectorize(window, m["vectorization"])
            y_prob = m["model"].predict(X, verbose=0)[0][0]
            y_pred = int(y_prob >= m["threshold"])

            results.append({
                "prediction_name": m["prediction_name"],
                "y_pred": y_pred
            })

        return jsonify({"window": window, "results": results})

    @app.route("/control", methods=["POST"])
    def control():
        if request.json.get("cmd") == "shutdown":
            func = request.environ.get('werkzeug.server.shutdown')
            if func:
                func()
            return jsonify({"status": "shutting_down"})
        return jsonify({"status": "unknown_command"})

    host = "127.0.0.1"
    port = 5005
    app.run(host=host, port=port)


# ============================================================
# RUN MODE (Orquestador)
# ============================================================

def run_orchestrator(variant: str):

    execution_dir = detect_execution_dir()
    project_root = detect_project_root(execution_dir)

    pm = ParamsManager("07_deployrun", project_root)
    pm.set_current(variant)
    variant_root = pm.current_variant_dir()

    manifest = load_manifest(variant_root)

    runtime_dir = variant_root / "runtime"
    logs_dir = variant_root / "logs"
    metrics_dir = variant_root / "metrics"
    report_dir = variant_root / "report"
    figures_dir = report_dir / "figures"

    ensure_clean_dir(runtime_dir)
    ensure_clean_dir(logs_dir)
    ensure_clean_dir(metrics_dir)
    ensure_clean_dir(report_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)

    server_proc = subprocess.Popen(
        [sys.executable, __file__, "--variant", variant, "--mode", "server"]
    )
    time.sleep(2)

    raw_rows = []

    for dataset in manifest["datasets"]:
        df = pd.read_parquet(dataset["dataset_path"])

        for _, row in df.iterrows():
            window = row[dataset["x_column"]]
            resp = requests.post(
                "http://127.0.0.1:5005/infer",
                json={"window": window}
            )
            data = resp.json()

            for r in data["results"]:
                raw_rows.append({
                    "window": json.dumps(window),
                    "prediction_name": r["prediction_name"],
                    "y_pred": r["y_pred"]
                })

    raw_df = pd.DataFrame(raw_rows)
    raw_df.to_parquet(logs_dir / "raw_predictions.parquet", index=False)
    raw_df.to_csv(logs_dir / "raw_predictions.csv", index=False)

    requests.post("http://127.0.0.1:5005/control", json={"cmd": "shutdown"})
    server_proc.wait()

    # ------------------------------------------------------------
    # Postprocess métricas
    # ------------------------------------------------------------

    metrics = []

    for m in manifest["models"]:
        pred_name = m["prediction_name"]

        dataset_path = next(
            d["dataset_path"] for d in manifest["datasets"]
        )

        df = pd.read_parquet(dataset_path)
        model_log = raw_df[raw_df["prediction_name"] == pred_name]

        tp = tn = fp = fn = 0

        for _, row in df.iterrows():
            window = json.dumps(row["OW_events"])
            y_true = row["label"]

            match = model_log[model_log["window"] == window]

            if len(match) == 0:
                continue

            y_pred = int(match.iloc[0]["y_pred"])

            if y_true == 1 and y_pred == 1:
                tp += 1
            elif y_true == 0 and y_pred == 0:
                tn += 1
            elif y_true == 0 and y_pred == 1:
                fp += 1
            elif y_true == 1 and y_pred == 0:
                fn += 1

        precision = tp / (tp + fp) if (tp + fp) else 0
        recall = tp / (tp + fn) if (tp + fn) else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0

        metrics.append({
            "prediction_name": pred_name,
            "tp": tp,
            "tn": tn,
            "fp": fp,
            "fn": fn,
            "precision": precision,
            "recall": recall,
            "f1": f1
        })

        # Confusion matrix figure
        plt.figure()
        plt.imshow([[tn, fp], [fn, tp]])
        plt.title(f"Confusion Matrix - {pred_name}")
        plt.savefig(figures_dir / f"confusion_{pred_name}.png")
        plt.close()

    metrics_df = pd.DataFrame(metrics)
    metrics_df.to_csv(metrics_dir / "metrics_per_model.csv", index=False)

    # Simple HTML report
    report_html = "<html><body><h1>F07 Report</h1>"
    report_html += metrics_df.to_html(index=False)
    report_html += "</body></html>"

    (report_dir / "report.html").write_text(report_html)

    # Trazabilidad
    write_metadata(
        stage="07_deployrun",
        variant=variant,
        parent_variant=manifest["f06_variant"],
        inputs=[str(variant_root / "manifest.json")],
        outputs=[
            str(logs_dir),
            str(metrics_dir),
            str(report_dir)
        ],
        params={},
        metadata_path=variant_root / "07_deployrun_metadata.json"
    )

    print("[DONE] F07 completada correctamente")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", required=True)
    parser.add_argument("--mode", required=True, choices=["prepare", "run", "server"])
    args = parser.parse_args()

    if args.mode == "prepare":
        prepare_variant(args.variant)

    elif args.mode == "run":
        run_orchestrator(args.variant)

    elif args.mode == "server":
        run_server(args.variant)
