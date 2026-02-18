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
import traceback
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

    models_dir = f06_root / "models"
    datasets_dir = f06_root / "datasets"
    
    # Reconstruir lista de modelos desde params de F06
    models = []
    seen_datasets = set()
    datasets = []
    
    parent_f05_list = params.get("parent_variants_f05", [])
    if not parent_f05_list:
        parent_f05_list = f06_metadata.get("parent_variants", [])
    
    for v05 in parent_f05_list:
        # Leer params de F05 para obtener F04 y prediction_name
        f05_params_path = project_root / "executions" / "05_modeling" / v05 / "params.yaml"
        if not f05_params_path.exists():
            print(f"[WARN] No se encontró params.yaml de F05 {v05}")
            continue
        
        f05_params = yaml.safe_load(f05_params_path.read_text())
        v04 = f05_params["parent_variant"]
        
        # Buscar el directorio del modelo en models/ (puede haber múltiples patrones)
        # Buscar primero por model_summary.json para obtener prediction_name
        model_dir_found = None
        prediction_name = None
        
        for model_dir_path in models_dir.iterdir():
            if not model_dir_path.is_dir():
                continue
            
            summary_path = model_dir_path / "model_summary.json"
            if not summary_path.exists():
                continue
            
            summary = json.loads(summary_path.read_text())
            # Verificar si este modelo corresponde a este F05
            # (por ahora, asumimos que cada F05 tiene exactamente un modelo)
            prediction_name = summary["prediction_name"]
            model_dir_found = model_dir_path
            break
        
        if not model_dir_found:
            print(f"[WARN] No se encontró modelo para F05 {v05}")
            continue
        
        dataset_path = datasets_dir / f"{v04}__dataset.parquet"
        
        models.append({
            "prediction_name": prediction_name,
            "source_f05": v05,
            "source_f04": v04,
            "model_dir": str(model_dir_found),
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
            if len(seq) > 0:
                X[0, -len(seq):] = seq
            return X

        raise ValueError("Vectorization no soportada")

    @app.route("/", methods=["GET"])
    def health():
        return jsonify({"status": "ready", "models": len(loaded_models)})

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

    @app.route("/infer_batch", methods=["POST"])
    def infer_batch():
        windows = request.json["windows"]

        batch_results = []

        for m in loaded_models:

            # Vectorizar todo el batch para este modelo
            X_list = []

            for window in windows:
                X = vectorize(window, m["vectorization"])
                X_list.append(X)

            X_batch = np.vstack(X_list)

            y_probs = m["model"].predict(X_batch, verbose=0).flatten()
            y_preds = (y_probs >= m["threshold"]).astype(int)

            for i, window in enumerate(windows):

                if len(batch_results) <= i:
                    batch_results.append({
                        "window": window,
                        "results": []
                    })

                batch_results[i]["results"].append({
                    "prediction_name": m["prediction_name"],
                    "y_pred": int(y_preds[i])
                })

        return jsonify({"results": batch_results})


    @app.route("/control", methods=["POST"])
    def control():
        if request.json.get("cmd") == "shutdown":
            func = request.environ.get('werkzeug.server.shutdown')
            if func:
                func()
            return jsonify({"status": "shutting_down"})
        return jsonify({"status": "unknown_command"})

    @app.errorhandler(Exception)
    def handle_server_exception(err):
        tb = traceback.format_exc()
        return jsonify({"error": str(err), "traceback": tb}), 500

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
    
    # Cargar parámetros
    import yaml
    with open(variant_root / "params.yaml", "r") as f:
        params = yaml.safe_load(f)
    
    sample_size = params.get("sample_size", None)
    batch_size = params.get("batch_size", 256)

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

    server_log_path = runtime_dir / "server.log"
    server_log_file = open(server_log_path, "w", encoding="utf-8")

    # Iniciar servidor
    server_proc = subprocess.Popen(
        [sys.executable, __file__, "--variant", variant, "--mode", "server"],
        stdout=server_log_file,
        stderr=server_log_file
    )

    time.sleep(0.5)
    if server_proc.poll() is not None:
        server_log_file.flush()
        startup_log = ""
        if server_log_path.exists():
            startup_log = server_log_path.read_text(encoding="utf-8")[:1000]
        server_log_file.close()
        raise RuntimeError(
            "No se pudo arrancar el servidor F07. "
            f"Revisa {server_log_path}. Log inicial: {startup_log}"
        )
    
    # Esperar a que el servidor esté listo (healthcheck)
    max_retries = 20
    for attempt in range(max_retries):
        try:
            resp = requests.get("http://127.0.0.1:5005/", timeout=0.5)
            if resp.status_code != 200:
                raise RuntimeError(f"Healthcheck HTTP {resp.status_code}")
            break
        except Exception:
            if attempt == max_retries - 1:
                server_proc.kill()
                server_log_file.close()
                raise RuntimeError("Servidor Flask no respondió después de 10s")
            time.sleep(0.5)

    raw_rows = []

    try:
        for dataset_idx, dataset in enumerate(manifest["datasets"], start=1):
            df = pd.read_parquet(dataset["dataset_path"])
            total_rows = len(df)
            x_column = dataset["x_column"]
            dataset_name = Path(dataset["dataset_path"]).name
            
            # Aplicar límite de muestra si está definido
            if sample_size is not None:
                print(
                    f"[INFO] Dataset {dataset_idx}/{len(manifest['datasets'])} {dataset_name}: "
                    f"limitando a {sample_size} filas (de {total_rows} totales)"
                )
                df = df.head(sample_size)
            else:
                print(
                    f"[INFO] Dataset {dataset_idx}/{len(manifest['datasets'])} {dataset_name}: "
                    f"procesando {total_rows} ventanas completas"
                )

            windows_buffer = []
            dataset_processed = 0

            for idx, row in df.iterrows():

                window = to_json_safe_window(row[x_column])
                windows_buffer.append(window)
                dataset_processed += 1

                if len(windows_buffer) == batch_size:

                    resp = requests.post(
                        "http://127.0.0.1:5005/infer_batch",
                        json={"windows": windows_buffer},
                        timeout=60,
                    )
                    if resp.status_code >= 400:
                        error_body = resp.text[:500]
                        raise RuntimeError(
                            f"infer_batch devolvió HTTP {resp.status_code}. Body: {error_body}. "
                            f"Revisa logs en {server_log_path}"
                        )

                    data = resp.json()

                    for item in data["results"]:
                        window_json = json.dumps(item["window"], separators=(",", ":"), ensure_ascii=False)
                        for r in item["results"]:
                            raw_rows.append({
                                "window": window_json,
                                "prediction_name": r["prediction_name"],
                                "y_pred": r["y_pred"]
                            })

                    if dataset_processed % (batch_size * 10) == 0 or dataset_processed == len(df):
                        print(
                            f"[RUN] {dataset_name}: enviadas {dataset_processed}/{len(df)} "
                            f"ventanas ({(dataset_processed / len(df) * 100):.1f}%)"
                        )

                    windows_buffer = []

            # Procesar último bloque
            if windows_buffer:

                resp = requests.post(
                    "http://127.0.0.1:5005/infer_batch",
                    json={"windows": windows_buffer},
                    timeout=60,
                )
                if resp.status_code >= 400:
                    error_body = resp.text[:500]
                    raise RuntimeError(
                        f"infer_batch devolvió HTTP {resp.status_code}. Body: {error_body}. "
                        f"Revisa logs en {server_log_path}"
                    )

                data = resp.json()

                for item in data["results"]:
                    window_json = json.dumps(item["window"], separators=(",", ":"), ensure_ascii=False)
                    for r in item["results"]:
                        raw_rows.append({
                            "window": window_json,
                            "prediction_name": r["prediction_name"],
                            "y_pred": r["y_pred"]
                        })

            print(
                f"[RUN] {dataset_name}: completado {dataset_processed}/{len(df)} ventanas"
            )


        raw_df = pd.DataFrame(raw_rows)
        raw_df.to_parquet(logs_dir / "raw_predictions.parquet", index=False)
        raw_df.to_csv(logs_dir / "raw_predictions.csv", index=False)
        
        print(f"[OK] {len(raw_df)} predicciones guardadas")
    finally:
        # Terminar servidor
        server_proc.terminate()
        try:
            server_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server_proc.kill()
        server_log_file.close()

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
        
        # Aplicar sample_size también para métricas
        if sample_size is not None:
            df = df.head(sample_size)
        
        model_log = raw_df[raw_df["prediction_name"] == pred_name]

        tp = tn = fp = fn = 0
        
        print(f"[INFO] Calculando métricas para {pred_name} ({len(df)} ventanas)...")

        progress_every = max(1000, len(df) // 20) if len(df) > 0 else 1000

        for idx, row in df.iterrows():
            if idx % progress_every == 0:
                print(
                    f"[METRICS] {pred_name}: procesadas {idx}/{len(df)} "
                    f"ventanas ({(idx / len(df) * 100):.1f}%)"
                )
            
            window_list = to_json_safe_window(row["OW_events"])
            
            window = json.dumps(window_list, separators=(",", ":"), ensure_ascii=False)
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

        print(
            f"[METRICS] {pred_name}: completadas {len(df)}/{len(df)} ventanas"
        )

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
