#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fase 02 — prepareEventsDS (script)

- Lee parámetros de la variante F02 (params/02_prepareeventsds/vNNN/params.yaml)
- Resuelve Tu (override -> F01 -> global)
- Carga el dataset explorado de la variante padre (F01)
- Genera dataset de eventos (niveles / transiciones / ambos)
- Genera catálogo de eventos, min/max, tablas, figuras e informe HTML
"""

import argparse
import json
import yaml
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import re

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import sys

# ============================================================
# BOOTSTRAP (OBLIGATORIO ANTES DE IMPORTAR mlops4ofp)
# ============================================================

SCRIPT_PATH = Path(__file__).resolve()
BOOTSTRAP_ROOT = SCRIPT_PATH
for _ in range(10):
    if (BOOTSTRAP_ROOT / "mlops4ofp").exists():
        break
    BOOTSTRAP_ROOT = BOOTSTRAP_ROOT.parent
else:
    raise RuntimeError("No se pudo localizar el repo root (mlops4ofp)")

sys.path.insert(0, str(BOOTSTRAP_ROOT))


# ============================================================
# IMPORTS DEL PROYECTO (ya con sys.path correcto)
# ============================================================

from mlops4ofp.tools.run_context import (
    detect_execution_dir,
    detect_project_root,
    assemble_run_context,
    build_phase_outputs,
)
from mlops4ofp.tools.params_manager import ParamsManager, validate_params
from mlops4ofp.tools.artifacts import (
    get_git_hash,
    save_numeric_dataset,
    save_params_and_metadata,
)
from mlops4ofp.tools.figures import save_figure

execution_dir = detect_execution_dir()
PROJECT_ROOT = detect_project_root(execution_dir)

PHASE = "02_prepareeventsds"

parser = argparse.ArgumentParser()
parser.add_argument("--variant", required=True)
args = parser.parse_args()

ACTIVE_VARIANT = args.variant

variant_root = (
    PROJECT_ROOT
    / "executions"
    / PHASE
    / ACTIVE_VARIANT
)

ctx = assemble_run_context(
    project_root=PROJECT_ROOT,
    execution_dir=execution_dir,
    phase=PHASE,
    variant=ACTIVE_VARIANT,
    variant_root=variant_root,
)

VARIANT_DIR = ctx["variant_root"]

print(f"[prepareeventsds] PROJECT_ROOT = {PROJECT_ROOT}")
print(f"[prepareeventsds] VARIANT_DIR  = {VARIANT_DIR}")

# ============================================================
# 2. Carga y validación de parámetros Fase 02
# ============================================================

# --- Leer params.yaml de la variante ---
params_path = VARIANT_DIR / "params.yaml"
if not params_path.exists():
    raise FileNotFoundError(
        f"No existe params.yaml para la variante F02 {ACTIVE_VARIANT}:\n{params_path}"
    )

with open(params_path, "r", encoding="utf-8") as f:
    params_f02 = yaml.safe_load(f) or {}

# --- Validar contra schema ---
validate_params(PHASE, params_f02, PROJECT_ROOT)
print("[prepareeventsds] Parámetros F02 validados correctamente.")

# --- Parámetros propios de F02 ---
band_thresholds_pct = params_f02.get("band_thresholds_pct", [40, 60, 90])
event_strategy = params_f02.get("event_strategy", "both")
nan_handling = params_f02.get("nan_handling", "keep")

parent_phase = params_f02.get("parent_phase", "01_explore")
parent_variant = params_f02.get("parent_variant")

if not parent_variant:
    raise RuntimeError("parent_variant no está definido en params.yaml de F02.")

print(f"[prepareeventsds] parent = {parent_phase}:{parent_variant}")
print(f"[prepareeventsds] band_thresholds_pct = {band_thresholds_pct}")
print(f"[prepareeventsds] event_strategy = {event_strategy}")
print(f"[prepareeventsds] nan_handling = {nan_handling}")

# ============================================================
# 3. Resolver Tu (prioridad: F02 -> F01)
# ============================================================

# --- Cargar metadata de la fase padre ---
parent_metadata_path = (
    PROJECT_ROOT
    / "executions"
    / parent_phase
    / parent_variant
    / f"{parent_phase}_metadata.json"
)

if not parent_metadata_path.exists():
    raise FileNotFoundError(
        f"No se encontró metadata de la fase padre:\n{parent_metadata_path}"
    )

with open(parent_metadata_path, "r", encoding="utf-8") as f:
    parent_metadata = json.load(f)

# --- Resolver Tu ---
if params_f02.get("Tu") is not None:
    Tu = float(params_f02["Tu"])
    source_Tu = "F02_variant"
    print(f"[prepareeventsds] Tu tomado de variante F02: {Tu}")
else:
    Tu_parent = parent_metadata.get("Tu")
    if Tu_parent is None:
        raise RuntimeError("No se pudo resolver Tu ni en F02 ni en metadata de F01.")
    Tu = float(Tu_parent)
    source_Tu = "F01_metadata"
    print(f"[prepareeventsds] Tu heredado de F01: {Tu}")

print(f"[prepareeventsds] Tu final = {Tu} (origen: {source_Tu})")

# ============================================================
# 4. Carga del dataset explorado de la fase padre (F01)
# ============================================================

# --- Ruta al dataset padre desde metadata F01 ---
parent_dataset_path = parent_metadata.get("dataset_explored")
if not parent_dataset_path:
    raise RuntimeError(
        "La metadata de F01 no contiene 'dataset_explored'."
    )

parent_dataset_path = (PROJECT_ROOT / parent_dataset_path).resolve()
if not parent_dataset_path.exists():
    raise FileNotFoundError(
        f"Dataset explorado de F01 no encontrado:\n{parent_dataset_path}"
    )

print(f"[prepareeventsds] Dataset padre (F01): {parent_dataset_path}")

# --- Cargar dataset ---
df_explored = pd.read_parquet(parent_dataset_path)

# --- Detectar columna temporal ---
if "segs" in df_explored.columns:
    epoch_col = "segs"
elif "epoch" in df_explored.columns:
    epoch_col = "epoch"
else:
    raise RuntimeError(
        "El dataset explorado no contiene columna temporal 'segs' ni 'epoch'."
    )

# --- Columnas de medida ---
numeric_cols = df_explored.select_dtypes(include=[np.number]).columns.tolist()
measurement_cols = [c for c in numeric_cols if c != epoch_col]

if not measurement_cols:
    raise RuntimeError(
        "No se han encontrado columnas numéricas de medida en el dataset explorado."
    )

print(f"[prepareeventsds] Filas: {len(df_explored)}")
print(f"[prepareeventsds] Columna temporal: {epoch_col}")
print(f"[prepareeventsds] Nº de medidas: {len(measurement_cols)}")


# ============================================================
# 5. Generación del dataset de eventos (versión rápida)
# ============================================================

# ------------------------------------------------------------
# Min / Max por medida
# ------------------------------------------------------------

def compute_minmax(df: pd.DataFrame, measure_cols):
    return {
        col: {
            "min": float(df[col].min()),
            "max": float(df[col].max()),
        }
        for col in measure_cols
    }

minmax_stats = compute_minmax(df_explored, measurement_cols)

print("[prepareeventsds] Min/max por medida calculado.")

# ------------------------------------------------------------
# Cálculo de cortes y etiquetas de bandas
# ------------------------------------------------------------

def compute_cuts_and_labels(minmax_stats, pct_thresholds):
    pct_list = [0.0] + pct_thresholds + [100.0]
    out = {}

    for col, mm in minmax_stats.items():
        mn, mx = mm["min"], mm["max"]
        r = mx - mn

        if r == 0:
            cuts = np.array([mn, mx])
            labels = ["0_100"]
        else:
            cuts = np.array([mn + p / 100 * r for p in pct_list])
            labels = [
                f"{int(pct_list[i])}_{int(pct_list[i + 1])}"
                for i in range(len(pct_list) - 1)
            ]

        out[col] = {"cuts": cuts, "labels": labels}

    return out


bands = compute_cuts_and_labels(
    minmax_stats=minmax_stats,
    pct_thresholds=band_thresholds_pct,
)

print("[prepareeventsds] Bandas calculadas.")

# ------------------------------------------------------------
# Catálogo de eventos
# ------------------------------------------------------------
def build_event_catalog(bands, event_strategy, nan_handling):
    """
    Devuelve:
      { event_name → event_id }
    """
    event_to_id = {}
    next_id = 1

    strat = event_strategy.lower()
    nan_keep = (nan_handling.lower() == "keep")

    for col, info in bands.items():
        labels = info["labels"]

        # Eventos de transición (solo band → band)
        if strat in ("transitions", "both"):
            for a in labels:
                for b in labels:
                    if a != b:
                        event_to_id[f"{col}_{a}-to-{b}"] = next_id
                        next_id += 1

        # Eventos de nivel (band)
        if strat in ("levels", "both"):
            for a in labels:
                event_to_id[f"{col}_{a}"] = next_id
                next_id += 1

        # Evento de nivel NaN (independiente de la estrategia)
        if nan_keep:
            event_to_id[f"{col}_NaN_NaN"] = next_id
            next_id += 1

    return event_to_id


event_to_id = build_event_catalog(
    bands=bands,
    event_strategy=event_strategy,
    nan_handling=nan_handling,
)

print(f"[prepareeventsds] Catálogo de eventos: {len(event_to_id)} tipos.")

# ------------------------------------------------------------
# Asignación vectorizada de bandas
# ------------------------------------------------------------

def assign_bands_to_column(values, cuts, labels):
    is_nan = np.isnan(values)
    kind = np.where(is_nan, "NaN", "band")

    idx = np.searchsorted(cuts, values, side="right") - 1
    idx = np.clip(idx, 0, len(labels) - 1)

    labels_arr = np.array(labels, dtype=object)
    assigned_labels = labels_arr[idx]

    assigned_labels[is_nan] = None
    kind[(values < cuts[0]) | (values > cuts[-1])] = "none"
    assigned_labels[(values < cuts[0]) | (values > cuts[-1])] = None

    return kind, assigned_labels


# ------------------------------------------------------------
# Generación rápida de eventos
# ------------------------------------------------------------

def fast_generate_events(
    df,
    epoch_col,
    measure_cols,
    bands,
    event_to_id,
    event_strategy,
    nan_handling,
    Tu,
):
    N = len(df)
    epochs = df[epoch_col].values.astype(np.int64)

    is_consecutive = np.zeros(N, dtype=bool)
    is_consecutive[1:] = (np.diff(epochs) == Tu)

    strat = event_strategy.lower()
    nan_keep = nan_handling.lower() == "keep"

    events_column = [[] for _ in range(N)]

    prev_kind = {col: None for col in measure_cols}
    prev_label = {col: None for col in measure_cols}

    col_kind = {}
    col_label = {}

    print("[DEBUG] measure_cols:", measure_cols)

    for col in measure_cols:
        vals = df[col].values
        cuts = bands[col]["cuts"]
        labels = bands[col]["labels"]

        k_arr, lbl_arr = assign_bands_to_column(vals, cuts, labels)
        print("[DEBUG] unique kinds:", set(k_arr))
        col_kind[col] = k_arr
        col_label[col] = lbl_arr

    for i in range(N):
        row_events = []

        for col in measure_cols:
            curr_k = col_kind[col][i]
            curr_lbl = col_label[col][i]

            # Transiciones
            if i > 0 and is_consecutive[i] and strat in ("transitions", "both"):
                pk = prev_kind[col]
                pl = prev_label[col]

                if pk == "band" and curr_k == "band" and pl != curr_lbl:
                    ev = event_to_id.get(f"{col}_{pl}-to-{curr_lbl}")
                    if ev:
                        row_events.append(ev)

            # NIVELES
            if curr_k == "band" and strat in ("levels", "both"):
                ev = event_to_id.get(f"{col}_{curr_lbl}")
                if ev:
                    row_events.append(ev)

            elif curr_k == "NaN" and nan_keep:
                ev = event_to_id.get(f"{col}_NaN_NaN")
                if ev:
                    row_events.append(ev)

            prev_kind[col] = curr_k
            prev_label[col] = curr_lbl

        events_column[i] = row_events

    df_events = pd.DataFrame(
        {
            epoch_col: df[epoch_col].values,
            "events": events_column,
        }
    )

    return df_events


df_events = fast_generate_events(
    df=df_explored,
    epoch_col=epoch_col,
    measure_cols=measurement_cols,
    bands=bands,
    event_to_id=event_to_id,
    event_strategy=event_strategy,
    nan_handling=nan_handling,
    Tu=Tu,
)

print("[prepareeventsds] Dataset de eventos generado.")
print(f"[prepareeventsds] Filas eventos: {len(df_events)}")


# ============================================================
# 6. Persistencia de resultados, metadata y trazabilidad
# ============================================================

from mlops4ofp.tools.artifacts import (
    get_git_hash,
    save_params_and_metadata,
)

import json

# ------------------------------------------------------------
# 6.1 Guardar dataset de eventos
# ------------------------------------------------------------

events_dataset_path = VARIANT_DIR / "02_prepareeventsds_dataset.parquet"
df_events.to_parquet(events_dataset_path, index=False)

print(f"[prepareeventsds] Dataset de eventos guardado en:\n{events_dataset_path}")
# IDs de eventos NaN (nivel)
nan_event_ids = {
    eid for name, eid in event_to_id.items()
    if name.endswith("_NaN_NaN")
}
print("[SCRIPT DEBUG] filas totales:", len(df_events))
print("[SCRIPT DEBUG] filas con NaN:",
      sum(any(e in nan_event_ids for e in evs) for evs in df_events["events"]))

# ------------------------------------------------------------
# 6.2 Guardar artefactos auxiliares
# ------------------------------------------------------------

bands_path = VARIANT_DIR / "02_prepareeventsds_bands.json"
event_catalog_path = VARIANT_DIR / "02_prepareeventsds_event_catalog.json"

with open(bands_path, "w", encoding="utf-8") as f:
    json.dump(
        {
            col: {
                "cuts": bands[col]["cuts"].tolist(),
                "labels": bands[col]["labels"],
            }
            for col in bands
        },
        f,
        indent=2,
    )

with open(event_catalog_path, "w", encoding="utf-8") as f:
    json.dump(event_to_id, f, indent=2)

print("[prepareeventsds] Artefactos guardados:")
print(f"  - {bands_path}")
print(f"  - {event_catalog_path}")

# ------------------------------------------------------------
# 6.3 Parámetros generados (para trazabilidad)
# ------------------------------------------------------------

gen_params = {
    "Tu": float(Tu),
    "band_thresholds_pct": band_thresholds_pct,
    "event_strategy": event_strategy,
    "nan_handling": nan_handling,
    "n_rows_input": int(len(df_explored)),
    "n_rows_events": int(len(df_events)),
    "n_event_types": int(len(event_to_id)),
    "n_measures": int(len(measurement_cols)),
}

# ------------------------------------------------------------
# 6.4 Metadata extendida Fase 02
# ------------------------------------------------------------

metadata_extra = {
    "dataset_events": str(events_dataset_path),
    "parent_phase": parent_phase,
    "parent_variant": parent_variant,
    "input_dataset": str(parent_dataset_path),
    "Tu": float(Tu),
    "band_thresholds_pct": band_thresholds_pct,
    "event_strategy": event_strategy,
    "nan_handling": nan_handling,
    "n_rows_input": int(len(df_explored)),
    "n_rows_events": int(len(df_events)),
    "n_event_types": int(len(event_to_id)),
    "n_measures": int(len(measurement_cols)),
}

# ------------------------------------------------------------
# 6.5 Guardar params + metadata + trazabilidad
# ------------------------------------------------------------

save_params_and_metadata(
    phase=PHASE,
    variant=ACTIVE_VARIANT,
    variant_root=VARIANT_DIR,
    raw_path=parent_dataset_path,   # dataset padre como "raw lógico"
    gen_params=gen_params,
    metadata_extra=metadata_extra,
    pm=None,                         # ParamsManager opcional
    git_commit=get_git_hash(),
)

print("[prepareeventsds] Metadata y trazabilidad F02 registradas correctamente.")


print("[STATS DEBUG] filas totales:", len(df_events))
print("[STATS DEBUG] filas con NaN:",
      sum(any(e in nan_event_ids for e in evs) for evs in df_events["events"]))


# ============================================================
# 7. Tablas, figuras e informe HTML (Fase 02)
# ============================================================

from collections import Counter
import matplotlib.pyplot as plt
from mlops4ofp.tools.figures import save_figure

print("[prepareeventsds] Generando tablas, figuras e informe HTML...")

FIGURES_DIR = VARIANT_DIR / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

MAX_X_TU = 10
MAX_BINS = 10

# ------------------------------------------------------------
# Preparación común
# ------------------------------------------------------------

flat_events = [ev for evs in df_events["events"] for ev in evs]
counts = Counter(flat_events)
inv_event = {v: k for k, v in event_to_id.items()}
missing = [ev for ev in flat_events if ev not in inv_event]
print("[DEBUG] event_ids sin nombre en inv_event:", len(missing))

MEASURE_NAMES = sorted(measurement_cols, key=len, reverse=True)

def extract_measure(ev_name: str) -> str:
    for m in MEASURE_NAMES:
        if ev_name.startswith(m + "_") or ev_name == m:
            return m
    return ev_name.split("_")[0]

# ------------------------------------------------------------
# Tabla 1 — Recuento por tipo de evento
# ------------------------------------------------------------

df_event_counts = (
    pd.DataFrame(
        [
            {"event_id": ev_id, "event_name": inv_event[ev_id], "count": cnt}
            for ev_id, cnt in counts.items()
        ]
    )
    .sort_values("event_id")
    .reset_index(drop=True)
)

# ------------------------------------------------------------
# Tabla 2 — Recuento por medida
# ------------------------------------------------------------

measure_counts = {}
for ev_id, cnt in counts.items():
    m = extract_measure(inv_event[ev_id])
    measure_counts[m] = measure_counts.get(m, 0) + cnt

df_measure_counts = (
    pd.DataFrame(
        [{"measure": m, "count": c} for m, c in measure_counts.items()]
    )
    .sort_values("measure")
    .reset_index(drop=True)
)

# ------------------------------------------------------------
# Índice inverso: event_id → posiciones
# ------------------------------------------------------------

event_positions = {ev_id: [] for ev_id in event_to_id.values()}
for idx, evs in enumerate(df_events["events"].values):
    for ev in evs:
        event_positions[ev].append(idx)

for ev_id in event_positions:
    event_positions[ev_id] = np.array(event_positions[ev_id], dtype=np.int64)

# ------------------------------------------------------------
# Tabla 3 — Interarrival por evento (solo num_appearances > 0)
# ------------------------------------------------------------

interarrival_rows = []

for ev_id, positions in event_positions.items():
    if len(positions) == 0:
        continue

    epochs = df_events.iloc[positions][epoch_col].values.astype(float)

    if len(epochs) < 2:
        interarrival_rows.append({
            "event_id": ev_id,
            "event_name": inv_event[ev_id],
            "num_appearances": len(epochs),
            "num_intervals": 0,
            "mean_interarrival": None,
            "std_interarrival": None,
            "min_interarrival": None,
            "max_interarrival": None,
        })
        continue

    deltas = np.diff(epochs)
    deltas = deltas[deltas >= 0]

    if len(deltas) == 0:
        interarrival_rows.append({
            "event_id": ev_id,
            "event_name": inv_event[ev_id],
            "num_appearances": len(epochs),
            "num_intervals": 0,
            "mean_interarrival": None,
            "std_interarrival": None,
            "min_interarrival": None,
            "max_interarrival": None,
        })
        continue

    interarrival_rows.append({
        "event_id": ev_id,
        "event_name": inv_event[ev_id],
        "num_appearances": len(epochs),
        "num_intervals": len(deltas),
        "mean_interarrival": float(np.mean(deltas)),
        "std_interarrival": float(np.std(deltas)),
        "min_interarrival": float(np.min(deltas)),
        "max_interarrival": float(np.max(deltas)),
    })

df_interarrival_stats = (
    pd.DataFrame(interarrival_rows)
    .sort_values("event_id")
    .reset_index(drop=True)
)

# ------------------------------------------------------------
# FIGURAS — Interarrival por EVENTO (unidades Tu)
# ------------------------------------------------------------

interarrival_event_info = {}

for _, row in df_interarrival_stats.iterrows():
    ev_id = row["event_id"]
    ev_name = row["event_name"]
    positions = event_positions[ev_id]

    if len(positions) < 3:
        interarrival_event_info[ev_id] = {"has_fig": False, "reason": "<3 apariciones"}
        continue

    epochs = df_events.iloc[positions][epoch_col].values.astype(float)
    deltas = np.diff(epochs)
    deltas = deltas[deltas >= 0]

    if len(deltas) < 2:
        interarrival_event_info[ev_id] = {"has_fig": False, "reason": "intervalos insuficientes"}
        continue

    deltas_TU = deltas / Tu
    clipped = np.clip(deltas_TU, 0, MAX_X_TU)

    fig_path = FIGURES_DIR / f"interarrival_event_{ev_id}.png"

    def _plot():
        bins = min(MAX_BINS, len(np.unique(clipped)))
        plt.hist(clipped, bins=bins, edgecolor="black")
        plt.xlabel("Tiempo entre llegadas (Tu)")
        plt.ylabel("count")
        plt.title(f"Interarrival — {ev_name}")
        plt.xlim(0, MAX_X_TU)
        if np.any(deltas_TU > MAX_X_TU):
            plt.annotate(
                "→",
                xy=(MAX_X_TU, plt.ylim()[1] * 0.9),
                color="red",
                fontsize=20,
                ha="center",
            )

    save_figure(fig_path, plot_fn=_plot, figsize=(10, 4))

    interarrival_event_info[ev_id] = {
        "has_fig": True,
        "file": fig_path.name,
        "num_app": int(len(epochs)),
    }

# ------------------------------------------------------------
# FIGURAS — Interarrival por MEDIDA (unidades Tu)
# ------------------------------------------------------------

interarrival_measure_info = {}

for measure in df_measure_counts["measure"]:
    ev_ids = [
        ev_id for ev_id, name in inv_event.items()
        if extract_measure(name) == measure
    ]

    all_pos = []
    for ev_id in ev_ids:
        all_pos.extend(event_positions[ev_id].tolist())

    all_pos = np.array(sorted(all_pos), dtype=np.int64)

    if len(all_pos) < 3:
        interarrival_measure_info[measure] = {"has_fig": False, "reason": "<3 eventos"}
        continue

    epochs = df_events.iloc[all_pos][epoch_col].values.astype(float)
    deltas = np.diff(epochs)
    deltas = deltas[deltas >= 0]

    if len(deltas) < 2:
        interarrival_measure_info[measure] = {"has_fig": False, "reason": "intervalos insuficientes"}
        continue

    deltas_TU = deltas / Tu
    clipped = np.clip(deltas_TU, 0, MAX_X_TU)

    fig_path = FIGURES_DIR / f"interarrival_measure_{measure}.png"

    def _plot():
        bins = min(MAX_BINS, len(np.unique(clipped)))
        plt.hist(clipped, bins=bins, edgecolor="black")
        plt.xlabel("Tiempo entre llegadas (Tu)")
        plt.ylabel("count")
        plt.title(f"Interarrival — medida {measure}")
        plt.xlim(0, MAX_X_TU)
        if np.any(deltas_TU > MAX_X_TU):
            plt.annotate(
                "→",
                xy=(MAX_X_TU, plt.ylim()[1] * 0.9),
                color="red",
                fontsize=20,
                ha="center",
            )

    save_figure(fig_path, plot_fn=_plot, figsize=(10, 4))

    interarrival_measure_info[measure] = {
        "has_fig": True,
        "file": fig_path.name,
        "num_events": int(len(all_pos)),
    }

# ------------------------------------------------------------
# Informe HTML final
# ------------------------------------------------------------

REPORT_PATH = VARIANT_DIR / "02_prepareeventsds_report.html"

sections = []

sections.append(f"<h1>PrepareEventsDS Report — Variante {ACTIVE_VARIANT}</h1>")
sections.append(f"<p><b>Fase padre:</b> {parent_phase}:{parent_variant}</p>")
sections.append(f"<p><b>Tu:</b> {Tu}</p>")
sections.append(f"<p><b>Band thresholds (%):</b> {band_thresholds_pct}</p>")
sections.append(f"<p><b>Event strategy:</b> {event_strategy}</p>")
sections.append(f"<p><b>NaN handling:</b> {nan_handling}</p>")
sections.append("<hr>")

total_events = len(flat_events)
epochs_with_events = (df_events["events"].apply(len) > 0).sum()

sections.append("<h2>Estadísticas globales</h2>")
sections.append(f"<p>Epochs totales: {len(df_events)}</p>")
sections.append(f"<p>Eventos totales: {total_events}</p>")
sections.append(f"<p>Tipos de evento distintos: {len(counts)}</p>")
sections.append(f"<p>Epochs con ≥1 evento: {epochs_with_events}</p>")
sections.append(f"<p>Eventos medios por epoch: {total_events/len(df_events):.3f}</p>")

sections.append("<h2>Recuento por tipo de evento</h2>")
sections.append(df_event_counts.to_html(index=False))

sections.append("<h2>Recuento por medida</h2>")
sections.append(df_measure_counts.to_html(index=False))

sections.append("<h2>Estadísticas interarrival por evento</h2>")
sections.append(df_interarrival_stats.to_html(index=False))

sections.append("<h2>Interarrival por evento (unidades Tu)</h2>")
for ev_id, info in interarrival_event_info.items():
    sections.append(f"<h3>Evento {ev_id}: {inv_event[ev_id]}</h3>")
    if not info["has_fig"]:
        sections.append(f"<p><i>No se genera figura: {info.get('reason')}</i></p>")
        continue
    sections.append(f"<p>Apariciones: {info['num_app']}</p>")
    sections.append(f"<img src='figures/{info['file']}' width='800'>")

sections.append("<h2>Interarrival por medida (unidades Tu)</h2>")
for measure, info in interarrival_measure_info.items():
    sections.append(f"<h3>Medida {measure}</h3>")
    if not info["has_fig"]:
        sections.append(f"<p><i>No se genera figura: {info.get('reason')}</i></p>")
        continue
    sections.append(f"<p>Nº eventos asociados: {info['num_events']}</p>")
    sections.append(f"<img src='figures/{info['file']}' width='800'>")

with open(REPORT_PATH, "w", encoding="utf-8") as f:
    f.write("<html><body>" + "\n".join(sections) + "</body></html>")

print(f"[prepareeventsds] Informe HTML generado en {REPORT_PATH}")
print("[prepareeventsds] Fase 02 completada correctamente.")

print("[STATS DEBUG] filas totales:", len(df_events))
print("[STATS DEBUG] filas con NaN:",
      sum(any(e in nan_event_ids for e in evs) for evs in df_events["events"]))


def main():
    pass

if __name__ == "__main__":
    main()
