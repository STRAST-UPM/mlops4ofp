#!/usr/bin/env python3
"""
Fase 05 — Modeling

Entrena modelos para una única familia por variante.
Familias soportadas:
- sequence_embedding
- dense_bow
- cnn1d

Produce:
- experiments/  → todos los trials (auditoría)
- candidates/   → modelos que superan criterio
- best/         → modelo único recomendado
"""

import sys
from pathlib import Path
import argparse
import json
from datetime import datetime, timezone
from time import perf_counter
import random
import os

import numpy as np
import pandas as pd
import yaml

# ============================================================
# TensorFlow runtime stabilization (macOS / CPU)
# ============================================================
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["TF_NUM_INTRAOP_THREADS"] = "1"
os.environ["TF_NUM_INTEROP_THREADS"] = "1"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

from sklearn.metrics import precision_recall_curve, confusion_matrix
import matplotlib.pyplot as plt

# ============================================================
# BOOTSTRAP
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

# ============================================================
# IMPORTS PROYECTO
# ============================================================
from mlops4ofp.tools.run_context import (
    detect_execution_dir,
    detect_project_root,
    assemble_run_context,
    print_run_context,
)
from mlops4ofp.tools.params_manager import ParamsManager
from mlops4ofp.tools.traceability import write_metadata
from mlops4ofp.tools.artifacts import get_git_hash
from mlops4ofp.tools.figures import save_figure

# ============================================================
# UTILIDADES
# ============================================================

def compute_class_weights(y):
    pos = np.sum(y == 1)
    neg = np.sum(y == 0)
    if pos == 0:
        return None
    return {0: 1.0, 1: neg / pos}


def pad_sequences(seqs, max_len, pad_value=0):
    out = np.full((len(seqs), max_len), pad_value, dtype=np.int32)
    for i, s in enumerate(seqs):
        if not s:
            continue
        trunc = s[-max_len:]
        out[i, -len(trunc):] = trunc
    return out


def check_split_feasibility(y_train, y_val):
    issues = []
    if y_train.sum() == 0:
        issues.append("train split sin positivos")
    if y_val.sum() == 0:
        issues.append("val split sin positivos")
    return issues


# ============================================================
# FAMILIAS DE MODELOS
# ============================================================

def vectorize_dense_bow(df, params):
    sequences = df["OW_events"].tolist()
    y = df["label"].values.astype(np.int32)

    vocab = sorted(set(ev for s in sequences for ev in s))
    index = {ev: i for i, ev in enumerate(vocab)}

    X = np.zeros((len(sequences), len(vocab)), dtype=np.float32)
    for i, s in enumerate(sequences):
        for ev in s:
            X[i, index[ev]] += 1.0

    return X, y, {"input_dim": X.shape[1]}


def build_dense_bow_model(aux, hp):
    model = keras.Sequential()
    model.add(layers.Input(shape=(aux["input_dim"],)))

    for _ in range(hp["n_layers"]):
        model.add(layers.Dense(hp["units"], activation="relu"))
        if hp["dropout"] > 0:
            model.add(layers.Dropout(hp["dropout"]))

    model.add(layers.Dense(1, activation="sigmoid"))
    return model


def vectorize_sequence(df, params):
    sequences = df["OW_events"].tolist()
    y = df["label"].values.astype(np.int32)

    vocab = sorted(set(ev for s in sequences for ev in s))
    index = {ev: i + 1 for i, ev in enumerate(vocab)}  # 0 = PAD

    seqs_idx = [[index[e] for e in s] for s in sequences]
    max_len = int(np.percentile([len(s) for s in seqs_idx], 95))
    X = pad_sequences(seqs_idx, max_len)

    return X, y, {"vocab_size": len(vocab), "max_len": max_len}


def build_sequence_embedding_model(aux, hp):
    model = keras.Sequential()
    model.add(layers.Input(shape=(aux["max_len"],)))
    model.add(
        layers.Embedding(
            input_dim=aux["vocab_size"] + 1,
            output_dim=hp["embed_dim"],
            mask_zero=True,
        )
    )
    model.add(layers.GlobalAveragePooling1D())

    for _ in range(hp["n_layers"]):
        model.add(layers.Dense(hp["units"], activation="relu"))
        if hp["dropout"] > 0:
            model.add(layers.Dropout(hp["dropout"]))

    model.add(layers.Dense(1, activation="sigmoid"))
    return model


def build_cnn1d_model(aux, hp):
    model = keras.Sequential()
    model.add(layers.Input(shape=(aux["max_len"],)))
    model.add(
        layers.Embedding(
            input_dim=aux["vocab_size"] + 1,
            output_dim=hp["embed_dim"],
            mask_zero=False,
        )
    )
    model.add(
        layers.Conv1D(
            filters=hp["filters"],
            kernel_size=hp["kernel_size"],
            activation="relu",
            padding="same",
        )
    )
    model.add(layers.GlobalMaxPooling1D())

    for _ in range(hp["n_layers"]):
        model.add(layers.Dense(hp["units"], activation="relu"))
        if hp["dropout"] > 0:
            model.add(layers.Dropout(hp["dropout"]))

    model.add(layers.Dense(1, activation="sigmoid"))
    return model


MODEL_FAMILIES = {
    "dense_bow": {
        "vectorize": vectorize_dense_bow,
        "build_model": build_dense_bow_model,
    },
    "sequence_embedding": {
        "vectorize": vectorize_sequence,
        "build_model": build_sequence_embedding_model,
    },
    "cnn1d": {
        "vectorize": vectorize_sequence,
        "build_model": build_cnn1d_model,
    },
}

# ============================================================
# MAIN
# ============================================================

def main(variant: str):

    PHASE = "05_modeling"
    t_start = perf_counter()

    execution_dir = detect_execution_dir()
    project_root = detect_project_root(execution_dir)

    pm = ParamsManager(PHASE, project_root)
    pm.set_current(variant)
    variant_root = pm.current_variant_dir()

    ctx = assemble_run_context(
        execution_dir, project_root, PHASE, variant, variant_root
    )
    print_run_context(ctx)

    with open(variant_root / "params.yaml", "r", encoding="utf-8") as f:
        params = yaml.safe_load(f)

    parent_variant_f04 = params["parent_variant"]
    model_family = params["model_family"]

    family = MODEL_FAMILIES[model_family]
    vectorize_fn = family["vectorize"]
    build_model_fn = family["build_model"]

    automl_cfg = params["automl"]
    training_cfg = params["training"]
    imbalance_cfg = params["imbalance"]
    eval_cfg = params["evaluation"]
    cand_cfg = params["candidate_selection"]
    search_space = params["search_space"][model_family]

    seed = automl_cfg.get("seed", 42)
    random.seed(seed)
    np.random.seed(seed)
    tf.random.set_seed(seed)

    input_dataset_path = (
        project_root
        / "executions"
        / "04_targetengineering"
        / parent_variant_f04
        / "04_targetengineering_dataset.parquet"
    )

    df = pd.read_parquet(input_dataset_path)
    X, y, aux = vectorize_fn(df, params)

    idx = np.arange(len(X))
    np.random.shuffle(idx)

    n = len(idx)
    n_train = int(eval_cfg["split"]["train"] * n)
    n_val = int(eval_cfg["split"]["val"] * n)

    train_idx = idx[:n_train]
    val_idx = idx[n_train:n_train + n_val]
    test_idx = idx[n_train + n_val:]

    X_train, y_train = X[train_idx], y[train_idx]
    X_val, y_val = X[val_idx], y[val_idx]
    X_test, y_test = X[test_idx], y[test_idx]

    max_samples = training_cfg.get("max_samples")
    if max_samples is not None and len(X_train) > max_samples:
        sel = np.random.choice(len(X_train), size=max_samples, replace=False)
        X_train = X_train[sel]
        y_train = y_train[sel]

    pd.DataFrame(X_train).to_parquet(variant_root / "train.parquet")
    pd.DataFrame(X_val).to_parquet(variant_root / "val.parquet")
    pd.DataFrame(X_test).to_parquet(variant_root / "test.parquet")

    class_weights = (
        compute_class_weights(y_train)
        if imbalance_cfg["strategy"] == "auto"
        else None
    )

    issues = check_split_feasibility(y_train, y_val)
    if issues:
        pm.save_metadata(
            {"phase": PHASE, "variant": variant, "status": "skipped", "reason": issues}
        )
        return

    experiments_dir = variant_root / "experiments"
    experiments_dir.mkdir(exist_ok=True)

    runs = []

    steps_per_epoch = min(
        max(1, len(X_train) // training_cfg["batch_size"]), 2000
    )

    # ---------------- AutoML ----------------
    for trial in range(automl_cfg["max_trials"]):
        hp = {k: random.choice(v) for k, v in search_space.items()}

        model = build_model_fn(aux, hp)
        model.compile(
            optimizer=keras.optimizers.Adam(hp["learning_rate"]),
            loss="binary_crossentropy",
            metrics=[keras.metrics.Recall(name="recall")],
        )

        hist = model.fit(
            X_train,
            y_train,
            validation_data=(X_val, y_val),
            epochs=training_cfg["epochs"],
            batch_size=hp["batch_size"],
            class_weight=class_weights,
            verbose=1,
            steps_per_epoch=steps_per_epoch,
        )

        val_recall = max(hist.history["val_recall"])

        exp_id = f"exp_{trial:03d}"
        exp_dir = experiments_dir / exp_id
        exp_dir.mkdir(exist_ok=True)

        model.save(exp_dir / "model.h5")
        with open(exp_dir / "metrics.json", "w") as f:
            json.dump({"val_recall": val_recall}, f, indent=2)

        runs.append({"exp_id": exp_id, "val_recall": val_recall, "hp": hp})

    # ---------------- Candidates ----------------
    threshold = cand_cfg["threshold"]
    selected = [r for r in runs if r["val_recall"] >= threshold]
    if not selected:
        selected = [max(runs, key=lambda r: r["val_recall"])]

    candidates_dir = variant_root / "candidates"
    candidates_dir.mkdir(exist_ok=True)

    candidates = []
    fig_dir = variant_root / "figures"
    fig_dir.mkdir(exist_ok=True)

    for i, r in enumerate(sorted(selected, key=lambda x: -x["val_recall"]), 1):
        cand_id = f"cand_{i:02d}"
        cand_dir = candidates_dir / cand_id
        cand_dir.mkdir(exist_ok=True)

        src = experiments_dir / r["exp_id"]
        model = keras.models.load_model(src / "model.h5")
        model.save(cand_dir / "model.h5")

        y_score = model.predict(X_test).ravel()
        precision, recall, thresholds = precision_recall_curve(y_test, y_score)

        y_pred = (y_score >= 0.5).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()

        with open(cand_dir / "metrics.json", "w") as f:
            json.dump(
                {
                    "val_recall": r["val_recall"],
                    "tp": int(tp),
                    "tn": int(tn),
                    "fp": int(fp),
                    "fn": int(fn),
                },
                f,
                indent=2,
            )

        save_figure(
            fig_dir / f"{cand_id}_precision_recall.png",
            lambda: (
                plt.plot(recall, precision),
                plt.xlabel("Recall"),
                plt.ylabel("Precision"),
                plt.title(f"{cand_id} — Precision–Recall"),
            ),
        )

        save_figure(
            fig_dir / f"{cand_id}_recall_vs_threshold.png",
            lambda: (
                plt.plot(thresholds, recall[:-1]),
                plt.xlabel("Threshold"),
                plt.ylabel("Recall"),
                plt.title(f"{cand_id} — Recall vs Threshold"),
            ),
        )

        candidates.append(
            {
                "candidate_id": cand_id,
                "from_experiment": r["exp_id"],
                "val_recall": r["val_recall"],
                "confusion_matrix": {
                    "tp": int(tp),
                    "tn": int(tn),
                    "fp": int(fp),
                    "fn": int(fn),
                },
            }
        )

    # ---------------- BEST MODEL ----------------
    best = sorted(
        candidates,
        key=lambda c: (
            -c["val_recall"],
            c["confusion_matrix"]["fn"],
            c["confusion_matrix"]["fp"],
        ),
    )[0]

    best_dir = variant_root / "best"
    best_dir.mkdir(exist_ok=True)

    src_dir = candidates_dir / best["candidate_id"]
    model = keras.models.load_model(src_dir / "model.h5")
    model.save(best_dir / "model.h5")

    with open(src_dir / "metrics.json") as f:
        metrics = json.load(f)

    with open(best_dir / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    with open(best_dir / "origin.json", "w") as f:
        json.dump(
            {
                "selected_from": best["candidate_id"],
                "selection_rule": "max(val_recall), min(fn), min(fp)",
            },
            f,
            indent=2,
        )

    # ---------------- METADATA ----------------
    metadata = {
        "phase": PHASE,
        "variant": variant,
        "parent_variant": parent_variant_f04,
        "model_family": model_family,
        "num_experiments": len(runs),
        "num_candidates": len(candidates),
        "best_model": {
            "candidate_id": best["candidate_id"],
            "path": str(best_dir / "model.h5"),
        },
        "selection_policy": cand_cfg,
        "git": {"commit": get_git_hash()},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    metadata_path = variant_root / f"{PHASE}_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    write_metadata(
        stage=PHASE,
        variant=variant,
        parent_variant=parent_variant_f04,
        inputs=[str(input_dataset_path)],
        outputs=[str(metadata_path)],
        params=params,
        metadata_path=metadata_path,
    )

    elapsed = perf_counter() - t_start
    print(f"[DONE] Fase 05 completada en {elapsed:.1f}s")


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fase 05 — Modeling")
    parser.add_argument("--variant", required=True)
    args = parser.parse_args()
    main(args.variant)
