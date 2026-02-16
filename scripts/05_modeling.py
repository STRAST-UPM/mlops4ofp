#!/usr/bin/env python3
"""
Fase 05 — Modeling

Entrena modelos para una única familia por variante.

Produce:
- experiments/              → auditoría de trials
- model_final.h5            → modelo único seleccionado
- splits.parquet            → índices train/val/test
- 05_modeling_metadata.json → metadata enriquecida
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
# TensorFlow runtime stabilization
# ============================================================
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["TF_NUM_INTRAOP_THREADS"] = "1"
os.environ["TF_NUM_INTEROP_THREADS"] = "1"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.optimizers import legacy as legacy_optimizers


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

from mlops4ofp.tools.run_context import (
    detect_execution_dir,
    detect_project_root,
    assemble_run_context,
    print_run_context,
)
from mlops4ofp.tools.params_manager import ParamsManager
from mlops4ofp.tools.traceability import write_metadata
from mlops4ofp.tools.artifacts import get_git_hash


# ============================================================
# UTILIDADES
# ============================================================

def compute_class_weights(y):
    pos = np.sum(y == 1)
    neg = np.sum(y == 0)
    if pos == 0:
        return None
    return {0: 1.0, 1: neg / pos}


def convert_to_native_types(obj):
    """Convierte tipos numpy a tipos nativos de Python para serialización JSON."""
    if isinstance(obj, dict):
        return {k: convert_to_native_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_native_types(item) for item in obj]
    elif isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float32, np.float64)):
        return float(obj)
    else:
        return obj


def apply_rare_events(df, imbalance_cfg, seed):
    strategy = imbalance_cfg.get("strategy", "none")

    if strategy != "rare_events":
        return df, {"strategy": "none"}

    max_majority = imbalance_cfg.get("max_majority_samples")

    if max_majority is None:
        return df, {
            "strategy": "rare_events",
            "note": "max_majority_samples=None → no reducción aplicada"
        }

    df_pos = df[df["label"] == 1]
    df_neg = df[df["label"] == 0]

    n_pos_before = len(df_pos)
    n_neg_before = len(df_neg)

    n_neg_sample = min(max_majority, n_neg_before)
    df_neg_sample = df_neg.sample(n=n_neg_sample, random_state=seed)

    df_new = pd.concat([df_pos, df_neg_sample])
    df_new = df_new.sample(frac=1.0, random_state=seed)

    info = {
        "strategy": "rare_events",
        "n_pos_before": int(n_pos_before),
        "n_neg_before": int(n_neg_before),
        "n_pos_after": int(len(df_pos)),
        "n_neg_after": int(n_neg_sample),
    }

    return df_new, info


def pad_sequences(seqs, max_len, pad_value=0):
    out = np.full((len(seqs), max_len), pad_value, dtype=np.int32)
    for i, s in enumerate(seqs):
        trunc = s[-max_len:]
        out[i, -len(trunc):] = trunc
    return out


# ============================================================
# FAMILIAS
# ============================================================

def vectorize_dense_bow(df):
    sequences = df["OW_events"].tolist()
    y = df["label"].values.astype(np.int32)

    vocab = sorted(set(ev for s in sequences for ev in s))
    index = {ev: i for i, ev in enumerate(vocab)}

    X = np.zeros((len(sequences), len(vocab)), dtype=np.float32)
    for i, s in enumerate(sequences):
        for ev in s:
            X[i, index[ev]] += 1.0

    return X, y, {
        "input_dim": X.shape[1],
        "vocab": vocab,
        "vectorization": "dense_bow"
    }



def build_dense_bow_model(aux, hp):
    model = keras.Sequential()
    model.add(layers.Input(shape=(aux["input_dim"],)))

    for _ in range(hp["n_layers"]):
        model.add(layers.Dense(hp["units"], activation="relu"))
        if hp["dropout"] > 0:
            model.add(layers.Dropout(hp["dropout"]))

    model.add(layers.Dense(1, activation="sigmoid"))
    return model


def vectorize_sequence(df):
    sequences = df["OW_events"].tolist()
    y = df["label"].values.astype(np.int32)

    vocab = sorted(set(ev for s in sequences for ev in s))
    index = {ev: i + 1 for i, ev in enumerate(vocab)}

    seqs_idx = [[index[e] for e in s] for s in sequences]
    max_len = int(np.percentile([len(s) for s in seqs_idx], 95))
    X = pad_sequences(seqs_idx, max_len)

    return X, y, {
        "vocab": vocab,
        "vocab_size": len(vocab),
        "max_len": max_len,
        "vectorization": "sequence"
    }



def build_sequence_embedding_model(aux, hp):
    model = keras.Sequential()
    model.add(layers.Input(shape=(aux["max_len"],)))
    model.add(layers.Embedding(
        input_dim=aux["vocab_size"] + 1,
        output_dim=hp["embed_dim"],
        mask_zero=True,
    ))
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
    model.add(layers.Embedding(
        input_dim=aux["vocab_size"] + 1,
        output_dim=hp["embed_dim"],
    ))
    model.add(layers.Conv1D(
        filters=hp["filters"],
        kernel_size=hp["kernel_size"],
        activation="relu",
        padding="same",
    ))
    model.add(layers.GlobalMaxPooling1D())

    for _ in range(hp["n_layers"]):
        model.add(layers.Dense(hp["units"], activation="relu"))
        if hp["dropout"] > 0:
            model.add(layers.Dropout(hp["dropout"]))

    model.add(layers.Dense(1, activation="sigmoid"))
    return model


MODEL_FAMILIES = {
    "dense_bow": (vectorize_dense_bow, build_dense_bow_model),
    "sequence_embedding": (vectorize_sequence, build_sequence_embedding_model),
    "cnn1d": (vectorize_sequence, build_cnn1d_model),
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

    with open(variant_root / "params.yaml", "r") as f:
        params = yaml.safe_load(f)

    parent_variant = params["parent_variant"]

    f04_metadata_path = (
        Path("executions")
        / "04_targetengineering"
        / parent_variant
        / "04_targetengineering_metadata.json"
    )

    with open(f04_metadata_path) as f:
        f04_metadata = json.load(f)

    prediction_name = f04_metadata.get("params", {}).get("prediction_name")
    if not prediction_name:
        raise ValueError("prediction_name no definido en F04 metadata")

    model_family = params["model_family"]

    vectorize_fn, build_model_fn = MODEL_FAMILIES[model_family]

    search_space = params["search_space"]
    common_space = search_space.get("common", {})
    family_space = search_space.get(model_family, {})
    full_space = {**common_space, **family_space}

    seed = params["automl"].get("seed", 42)
    random.seed(seed)
    np.random.seed(seed)
    tf.random.set_seed(seed)

    dataset_path = (
        project_root
        / "executions"
        / "04_targetengineering"
        / parent_variant
        / "04_targetengineering_dataset.parquet"
    )

    df = pd.read_parquet(dataset_path)

    imbalance_cfg = params.get("imbalance", {})
    df, sampler_info = apply_rare_events(df, imbalance_cfg, seed)

    max_samples = params["training"].get("max_samples")
    if imbalance_cfg.get("strategy") != "rare_events":
        if max_samples is not None and len(df) > max_samples:
            df = df.sample(n=max_samples, random_state=seed)

    X, y, aux = vectorize_fn(df)

    idx = np.arange(len(X))
    np.random.shuffle(idx)

    split = params["evaluation"]["split"]
    n = len(idx)
    n_train = int(split["train"] * n)
    n_val = int(split["val"] * n)

    train_idx = idx[:n_train]
    val_idx = idx[n_train:n_train + n_val]
    test_idx = idx[n_train + n_val:]

    X_train, y_train = X[train_idx], y[train_idx]
    X_val, y_val = X[val_idx], y[val_idx]
    X_test, y_test = X[test_idx], y[test_idx]

    pd.DataFrame({
        "train_idx": train_idx,
        "val_idx": np.pad(val_idx, (0, len(train_idx)-len(val_idx)), constant_values=-1),
        "test_idx": np.pad(test_idx, (0, len(train_idx)-len(test_idx)), constant_values=-1)
    }).to_parquet(variant_root / "splits.parquet")

    class_weights = (
        compute_class_weights(y_train)
        if params["imbalance"]["strategy"] == "auto"
        else None
    )

    experiments_dir = variant_root / "experiments"
    experiments_dir.mkdir(exist_ok=True)

    best_model = None
    best_recall = -1
    best_hp = None
    trials_summary = []

    for trial in range(params["automl"]["max_trials"]):

        hp = {k: random.choice(v) for k, v in full_space.items()}
        hp = convert_to_native_types(hp)  # Convertir tipos numpy a Python nativos

        model = build_model_fn(aux, hp)
        model.compile(
            optimizer=legacy_optimizers.Adam(hp["learning_rate"]),
            loss="binary_crossentropy",
            metrics=[keras.metrics.Recall(name="recall")],
        )

        hist = model.fit(
            X_train,
            y_train,
            validation_data=(X_val, y_val),
            epochs=params["training"]["epochs"],
            batch_size=hp["batch_size"],
            class_weight=class_weights,
            verbose=1,
        )

        val_recall = float(max(hist.history["val_recall"]))

        exp_dir = experiments_dir / f"exp_{trial:03d}"
        exp_dir.mkdir(exist_ok=True)
        model.save(exp_dir / "model.h5")

        with open(exp_dir / "metrics.json", "w") as f:
            json.dump({"val_recall": val_recall}, f, indent=2)

        trials_summary.append({
            "trial_id": trial,
            "hyperparameters": hp,
            "val_recall": val_recall
        })

        if val_recall > best_recall:
            best_recall = val_recall
            best_model = model
            best_hp = hp

    # --------------------------------------------------
    # Guardar modelo oficial en carpeta estructurada
    # --------------------------------------------------
    safe_name = prediction_name.lower().replace(" ", "_")

    models_root = variant_root / "models"
    model_dir = models_root / safe_name
    model_dir.mkdir(parents=True, exist_ok=True)

    final_model_path = model_dir / "model.h5"
    best_model.save(final_model_path)

    # --------------------------------------------------
    # Evaluación en test
    # --------------------------------------------------
    from sklearn.metrics import confusion_matrix, precision_score, f1_score, recall_score

    y_pred_prob = best_model.predict(X_test, verbose=0)
    y_pred = (y_pred_prob >= 0.5).astype(int).ravel()

    cm = confusion_matrix(y_test, y_pred).tolist()
    precision = float(precision_score(y_test, y_pred, zero_division=0))
    recall = float(recall_score(y_test, y_pred, zero_division=0))
    f1 = float(f1_score(y_test, y_pred, zero_division=0))

    # --------------------------------------------------
    # Paths metadata
    # --------------------------------------------------
    trace_metadata_path = variant_root / f"{PHASE}_metadata.json"
    functional_metadata_path = model_dir / "model_summary.json"

    # --------------------------------------------------
    # Metadata funcional completa (runtime-safe)
    # --------------------------------------------------
    metadata = {
        "phase": PHASE,
        "variant": variant,
        "parent_variant": parent_variant,

        "prediction_name": safe_name,
        "model_name": f"{safe_name} ({model_family})",
        "model_family": model_family,

        "model_path": str(final_model_path),

        "vectorization": aux,          # ← incluye vocab / max_len / input_dim
        "threshold": 0.5,

        "dataset_path": str(dataset_path),

        "split_sizes": {
            "train": int(len(train_idx)),
            "val": int(len(val_idx)),
            "test": int(len(test_idx))
        },

        "imbalance_policy": {
            "config": imbalance_cfg,
            "sampler_info": sampler_info
        },

        "num_experiments": len(trials_summary),
        "best_val_recall": float(best_recall),
        "best_hyperparameters": best_hp,

        "test_metrics": {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "confusion_matrix": cm
        },

        "trials_summary": trials_summary,

        "mlflow_registration": {
            "experiment_name": f"F05_{safe_name}",
            "run_name": f"{safe_name}__{variant}",
            "metrics": {
                "val_recall": float(best_recall),
                "test_precision": precision,
                "test_recall": recall,
                "test_f1": f1
            },
            "params": best_hp,
            "artifacts": [
                str(final_model_path),
                str(functional_metadata_path)
            ]
        },

        "git": {
            "commit": get_git_hash()
        },

        "generated_at": datetime.now(timezone.utc).isoformat()
    }

    # --------------------------------------------------
    # Guardar metadata funcional junto al modelo
    # --------------------------------------------------
    with open(functional_metadata_path, "w") as f:
        # Convertir todos los tipos numpy a tipos nativos de Python antes de serializar
        metadata_native = convert_to_native_types(metadata)
        json.dump(metadata_native, f, indent=2)

    # --------------------------------------------------
    # Trazabilidad oficial de fase
    # --------------------------------------------------
    write_metadata(
        stage=PHASE,
        variant=variant,
        parent_variant=parent_variant,
        inputs=[str(dataset_path)],
        outputs=[str(model_dir)],
        params=params,
        metadata_path=trace_metadata_path,
    )


    print(f"[DONE] Fase 05 completada en {perf_counter()-t_start:.1f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", required=True)
    args = parser.parse_args()
    main(args.variant)
