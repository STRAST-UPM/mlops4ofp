#!/usr/bin/env python3

"""
Fase 07 — Deploy & Runtime Validation

Modos:
  --mode prepare   → genera manifest.json
  --mode run       → ejecuta server + cliente + métricas + informe
  --mode server    → arranca servidor Flask
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
import pyarrow as pa
import pyarrow.parquet as pq
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

def to_json_safe_window(window):
    if hasattr(window, "tolist"):
        return window.tolist()
    if isinstance(window, (list, tuple)):
        return list(window)
    if hasattr(window, "item"):
        return [window.item()]
    return [window]

def load_manifest(variant_root: Path):
    manifest_path = variant_root / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("manifest.json no encontrado. Ejecuta variant7 primero.")
    return json.loads(manifest_path.read_text())

# ============================================================
# PREPARE MODE (sin cambios)
# ============================================================

def prepare_variant(variant: str):

    execution_dir = detect_execution_dir()
    project_root = detect_project_root(execution_dir)

    pm = ParamsManager("07_deployrun", project_root)
    pm.set_current(variant)
    variant_root = pm.current_variant_dir()

    import yaml
    params = yaml.safe_load((variant_root / "params.yaml").read_text())

    parent_f06 = params["parent_variant_f06"]
    f06_root = project_root / "executions" / "06_packaging" / parent_f06

    f06_metadata = json.loads((f06_root / "06_packaging_metadata.json").read_text())
    models_dir = f06_root / "models"
    datasets_dir = f06_root / "datasets"

    models = []
    datasets = []
    seen_datasets = set()

    for m in f06_metadata["models"]:
        pred_name = m["prediction_name"]
        v05 = m["source_f05"]

        model_dir = next(models_dir.glob(f"{pred_name}__*"))
        f05_params = yaml.safe_load(
            (project_root / "executions" / "05_modeling" / v05 / "params.yaml").read_text()
        )
        v04 = f05_params["parent_variant"]

        dataset_path = datasets_dir / f"{v04}__dataset.parquet"

        models.append({
            "prediction_name": pred_name,
            "source_f05": v05,
            "source_f04": v04,
            "model_dir": str(model_dir),
            "model_h5": "model.h5",
            "model_summary": "model_summary.json",
            "dataset_path": str(dataset_path),
            "x_column": "OW_events",
            "y_column": "label",
        })

        if str(dataset_path) not in seen_datasets:
            datasets.append({
                "dataset_path": str(dataset_path),
                "x_column": "OW_events",
                "y_column": "label",
                "source_f04": v04,
            })
            seen_datasets.add(str(dataset_path))

    manifest = {
        "f06_variant": parent_f06,
        "f06_path": str(f06_root),
        "models": models,
        "datasets": datasets,
    }

    (variant_root / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print("[OK] manifest.json generado")

# ============================================================
# SERVER MODE (sin cambios)
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
            "threshold": summary.get("threshold", 0.5),
        })

    app = Flask(__name__)

    def vectorize_batch(windows, config):

        if config["vectorization"] == "dense_bow":
            vocab = config["vocab"]
            index = {ev: i for i, ev in enumerate(vocab)}
            X = np.zeros((len(windows), config["input_dim"]), dtype=np.float32)
            for i, window in enumerate(windows):
                for ev in window:
                    if ev in index:
                        X[i, index[ev]] += 1.0
            return X

        if config["vectorization"] == "sequence":
            vocab = config["vocab"]
            index = {ev: i + 1 for i, ev in enumerate(vocab)}
            max_len = config["max_len"]
            X = np.zeros((len(windows), max_len), dtype=np.int32)
            for i, window in enumerate(windows):
                seq = [index[e] for e in window if e in index]
                seq = seq[-max_len:]
                if len(seq) > 0:
                    X[i, -len(seq):] = seq
            return X

        raise ValueError("Vectorization no soportada")

    @app.route("/", methods=["GET"])
    def health():
        return jsonify({"status": "ready", "models": len(loaded_models)})

    @app.route("/infer_batch", methods=["POST"])
    def infer_batch():

        windows = request.json["windows"]
        batch_results = []

        for m in loaded_models:

            X_batch = vectorize_batch(windows, m["vectorization"])
            y_probs = m["model"].predict(X_batch, verbose=0).flatten()
            y_preds = (y_probs >= m["threshold"]).astype(int)

            for i, window in enumerate(windows):

                if len(batch_results) <= i:
                    batch_results.append({"window": window, "results": []})

                batch_results[i]["results"].append({
                    "prediction_name": m["prediction_name"],
                    "y_pred": int(y_preds[i]),
                })

        return jsonify({"results": batch_results})

    app.run(host="127.0.0.1", port=5005)

# ============================================================
# RUN MODE (OPTIMIZADO)
# ============================================================

def run_orchestrator(variant: str):

    execution_dir = detect_execution_dir()
    project_root = detect_project_root(execution_dir)

    pm = ParamsManager("07_deployrun", project_root)
    pm.set_current(variant)
    variant_root = pm.current_variant_dir()

    manifest = load_manifest(variant_root)

    import yaml
    params = yaml.safe_load((variant_root / "params.yaml").read_text())

    batch_size = params.get("batch_size", 256)
    sample_size = params.get("sample_size", None)

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

    # Lanzar servidor
    server_proc = subprocess.Popen(
        [sys.executable, __file__, "--variant", variant, "--mode", "server"]
    )

    base_url = "http://127.0.0.1:5005"

    # Esperar servidor
    for _ in range(60):
        try:
            if requests.get(f"{base_url}/").status_code == 200:
                break
        except:
            time.sleep(0.5)
    else:
        raise RuntimeError("Servidor no respondió")

    raw_path_parquet = logs_dir / "raw_predictions.parquet"
    raw_path_csv = logs_dir / "raw_predictions.csv"

    parquet_writer = None

    try:
        # ============================================================
        # NUEVO: UNA SOLA PASADA CON VENTANAS ÚNICAS
        # ============================================================

        base_dataset = manifest["datasets"][0]
        df = pd.read_parquet(base_dataset["dataset_path"])

        if sample_size:
            df = df.head(sample_size)

        print(f"[INFO] Dataset base: {len(df)} filas")

        df["window"] = df["OW_events"].apply(
            lambda w: json.dumps(
                to_json_safe_window(w),
                separators=(",", ":"),
                ensure_ascii=False,
            )
        )

        unique_windows = df["window"].unique()
        print(f"[INFO] Ventanas únicas detectadas: {len(unique_windows)}")

        for i in range(0, len(unique_windows), batch_size):

            batch_json = unique_windows[i:i + batch_size]
            batch_windows = [json.loads(w) for w in batch_json]

            resp = requests.post(
                f"{base_url}/infer_batch",
                json={"windows": batch_windows},
                timeout=120,
            )
            resp.raise_for_status()

            data = resp.json()

            rows = []

            for item in data["results"]:
                window_json = json.dumps(
                    item["window"], separators=(",", ":"), ensure_ascii=False
                )
                for r in item["results"]:
                    rows.append({
                        "window": window_json,
                        "prediction_name": r["prediction_name"],
                        "y_pred": r["y_pred"],
                    })

            batch_df = pd.DataFrame(rows)

            table = pa.Table.from_pandas(batch_df, preserve_index=False)
            if parquet_writer is None:
                parquet_writer = pq.ParquetWriter(raw_path_parquet, table.schema)
            parquet_writer.write_table(table)

            if not raw_path_csv.exists():
                batch_df.to_csv(raw_path_csv, index=False)
            else:
                batch_df.to_csv(raw_path_csv, mode="a", header=False, index=False)

            if i % (batch_size * 10) == 0:
                print(f"[RUN] Ventanas únicas procesadas: {i}/{len(unique_windows)}")

        if parquet_writer:
            parquet_writer.close()

        raw_df = pd.read_parquet(raw_path_parquet)

    finally:
        server_proc.terminate()
        server_proc.wait()

    # ============================================================
    # MÉTRICAS (sin cambios)
    # ============================================================

    metrics = []

    for m in manifest["models"]:

        pred_name = m["prediction_name"]
        dataset_path = m["dataset_path"]

        df = pd.read_parquet(dataset_path)
        if sample_size:
            df = df.head(sample_size)

        df["window"] = df["OW_events"].apply(
            lambda w: json.dumps(
                to_json_safe_window(w),
                separators=(",", ":"),
                ensure_ascii=False,
            )
        )

        model_log = raw_df[raw_df["prediction_name"] == pred_name][["window", "y_pred"]]
        merged = df.merge(model_log, on="window", how="left")

        valid = merged[merged["y_pred"].notna()].copy()
        valid["y_pred"] = valid["y_pred"].astype(int)

        tp = ((valid["label"] == 1) & (valid["y_pred"] == 1)).sum()
        tn = ((valid["label"] == 0) & (valid["y_pred"] == 0)).sum()
        fp = ((valid["label"] == 0) & (valid["y_pred"] == 1)).sum()
        fn = ((valid["label"] == 1) & (valid["y_pred"] == 0)).sum()

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
            "f1": f1,
        })

    metrics_df = pd.DataFrame(metrics)
    metrics_df.to_csv(metrics_dir / "metrics_per_model.csv", index=False)

    write_metadata(
        stage="07_deployrun",
        variant=variant,
        parent_variant=manifest["f06_variant"],
        inputs=[str(variant_root / "manifest.json")],
        outputs=[str(logs_dir), str(metrics_dir), str(report_dir)],
        params={},
        metadata_path=variant_root / "07_deployrun_metadata.json",
    )


    # ============================================================
    # GENERACIÓN DE INFORME VISUAL HTML
    # ============================================================

    print("\n[INFO] Generando informe visual HTML...", flush=True)

    metrics_csv_path = metrics_dir / "metrics_per_model.csv"
    metrics_df = pd.read_csv(metrics_csv_path)

    # Ordenar por F1 descendente
    metrics_df = metrics_df.sort_values("f1", ascending=False)

    # ------------------------------------------------------------
    # 1. Gráfico comparativo de métricas
    # ------------------------------------------------------------

    plt.figure(figsize=(10, 6))

    x = np.arange(len(metrics_df))
    width = 0.25

    plt.bar(x - width, metrics_df["precision"], width, label="Precision")
    plt.bar(x, metrics_df["recall"], width, label="Recall")
    plt.bar(x + width, metrics_df["f1"], width, label="F1")

    plt.xticks(x, metrics_df["prediction_name"], rotation=45, ha="right")
    plt.ylim(0, 1)
    plt.legend()
    plt.tight_layout()

    metrics_bar_path = figures_dir / "metrics_comparison.png"
    plt.savefig(metrics_bar_path)
    plt.close()

    print(f"[FIG] Guardado gráfico comparativo: {metrics_bar_path}", flush=True)

    # ------------------------------------------------------------
    # 2. HTML dinámico
    # ------------------------------------------------------------

    html = []
    html.append("<html><head><title>F07 Report</title></head><body>")
    html.append("<h1>F07 — Runtime Validation Report</h1>")

    html.append("<h2>Resumen de Métricas</h2>")
    html.append(metrics_df.to_html(index=False, float_format=lambda x: f"{x:.4f}"))

    html.append("<h2>Comparativa Precision / Recall / F1</h2>")
    html.append(f'<img src="figures/{metrics_bar_path.name}" width="800">')

    html.append("<h2>Detalle por Modelo</h2>")

    for _, row in metrics_df.iterrows():
        pred = row["prediction_name"]
        html.append(f"<h3>{pred}</h3>")
        html.append("<ul>")
        html.append(f"<li>TP: {int(row['tp'])}</li>")
        html.append(f"<li>TN: {int(row['tn'])}</li>")
        html.append(f"<li>FP: {int(row['fp'])}</li>")
        html.append(f"<li>FN: {int(row['fn'])}</li>")
        html.append(f"<li>Precision: {row['precision']:.4f}</li>")
        html.append(f"<li>Recall: {row['recall']:.4f}</li>")
        html.append(f"<li>F1: {row['f1']:.4f}</li>")
        html.append("</ul>")
        #html.append(f'<img src="figures/confusion_{pred}.png" width="400">')
        html.append("<hr>")

    html.append("</body></html>")

    report_path = report_dir / "report.html"
    report_path.write_text("\n".join(html), encoding="utf-8")

    print(f"[OK] Reporte HTML generado: {report_path}", flush=True)



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
