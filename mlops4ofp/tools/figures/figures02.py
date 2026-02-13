from __future__ import annotations
from pathlib import Path
import matplotlib.pyplot as plt


# Standard library
from datetime import datetime
from importlib import util as importlib_util
from pathlib import Path
from tabnanny import verbose
from typing import Any, Dict, Optional

# Third-party
from IPython.display import display
import matplotlib
import matplotlib.dates as mdates
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.dates import DateFormatter, HourLocator
import numpy as np
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype
import seaborn as sns
from sklearn.feature_selection import mutual_info_regression
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.seasonal import seasonal_decompose
from matplotlib.patches import Patch
import matplotlib.colors as mcolors
from mlops4ofp.tools.figures.figures_general import save_fig


# ============================================================================================================================================================
# ============================================================================================================================================================
# ============================================================================================================================================================
# 02- PREPARE EVENTS FIGURES
# ============================================================================================================================================================
# ============================================================================================================================================================
# ============================================================================================================================================================

def plot_levels_for_measure(
    levels_by_measure: pd.DataFrame,
    measure: str,
    normalize_in_measure: bool = True,
) -> None:
    """
    Barras: distribución de niveles para UNA medida.
    - normalize_in_measure=True -> % dentro de esa medida (recomendado).
    """
    ax = plt.gca()

    g = levels_by_measure[levels_by_measure["measure"] == measure].copy()
    if g.empty:
        ax.text(0.5, 0.5, f"Sin levels para la medida {measure}", ha="center", va="center")
        ax.axis("off")
        return

    g = g.sort_values("level_state")
    y = g["count"].to_numpy(dtype=float)

    if normalize_in_measure and y.sum() > 0:
        y = 100.0 * y / y.sum()
        ylabel = "% dentro de la medida"
    else:
        ylabel = "count"

    ax.bar(g["level_state"].astype(str), y, edgecolor="black")
    ax.set_xlabel("Nivel (LOW_HIGH)")
    ax.set_ylabel(ylabel)
    ax.set_title(f"Distribución de niveles — {measure}", fontsize=12, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()


def plot_levels_heatmap_for_measure(
    levels_by_measure: pd.DataFrame,
    measure: str,
    normalize_in_measure: bool = True,
) -> None:
    """
    Heatmap 1 fila: niveles en X, intensidad = conteo o % dentro de la medida.
    """
    ax = plt.gca()

    g = levels_by_measure[levels_by_measure["measure"] == measure].copy()
    if g.empty:
        ax.text(0.5, 0.5, f"Sin levels para la medida {measure}", ha="center", va="center")
        ax.axis("off")
        return

    g = g.sort_values("level_state")
    vals = g["count"].to_numpy(dtype=float)

    if normalize_in_measure and vals.sum() > 0:
        vals = vals / vals.sum()
        cbar_label = "Proporción"
    else:
        cbar_label = "Frecuencia"

    M = vals.reshape(1, -1)
    im = ax.imshow(M, aspect="auto", origin="lower", cmap="Blues")

    ax.set_yticks([0])
    ax.set_yticklabels([measure])
    ax.set_xticks(np.arange(len(g)))
    ax.set_xticklabels(g["level_state"].astype(str), rotation=45, ha="right")

    ax.set_xlabel("Nivel (LOW_HIGH)")
    ax.set_title(f"Heatmap de niveles — {measure}", fontsize=12, fontweight="bold")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label=cbar_label)
    plt.tight_layout()

def plot_measure_levels_eda_reports(
    levels_by_measure: pd.DataFrame,
    reports_path: Path,
    measure: str,
) -> list[tuple[str, Path]]:
    saved: list[tuple[str, Path]] = []
    reports_path.mkdir(parents=True, exist_ok=True)

    # 1) Barras (%)
    try:
        fig, _ = plt.subplots(figsize=(10, 4))
        plot_levels_for_measure(levels_by_measure, measure, normalize_in_measure=True)
        path = save_fig(fig, reports_path, f"levels_dist_{measure}.png")
        saved.append((f"Distribución de niveles — {measure}", path))
    except Exception as e:
        print(f"Error en levels_dist para {measure}: {e}")
        plt.close()

    return saved


def plot_levels_concentration_ranking(levels_by_measure: pd.DataFrame) -> None:
    """
    Ranking de medidas por concentración de niveles.
    Métrica: max_share = max(count)/sum(count) por medida.
      - 1.0 => casi siempre en un nivel
      - bajo => distribuida en varios niveles
    """
    ax = plt.gca()

    if levels_by_measure.empty:
        ax.text(0.5, 0.5, "No hay datos de niveles.", ha="center", va="center")
        ax.axis("off")
        return

    g = levels_by_measure.groupby("measure")["count"]
    total = g.sum()
    maxv = g.max()
    max_share = (maxv / total).sort_values(ascending=False)

    # mostrar top 30 para legibilidad
    max_share = max_share.iloc[:30]

    ax.bar(max_share.index, max_share.to_numpy(dtype=float), edgecolor="black")
    ax.set_xticks(range(len(max_share)))
    ax.set_xticklabels(max_share.index, rotation=45, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Concentración (máx nivel / total)")
    ax.set_title("Ranking de medidas por concentración de niveles\n(1 = casi siempre mismo nivel)", fontsize=12, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()

def plot_levels_heatmap_general(
    levels_by_measure: pd.DataFrame,
    normalize_in_row: bool = True,
    max_measures: int = 40,
) -> None:
    """
    Heatmap global:
      - filas: measures
      - columnas: level_state
      - color: conteo o proporción por medida (si normalize_in_row)
    """
    ax = plt.gca()

    if levels_by_measure.empty:
        ax.text(0.5, 0.5, "No hay datos de niveles (levels_by_measure vacío).", ha="center", va="center")
        ax.axis("off")
        return

    # Pivot a matriz
    pivot = levels_by_measure.pivot_table(
        index="measure",
        columns="level_state",
        values="count",
        aggfunc="sum",
        fill_value=0
    )

    # limitar nº medidas para que sea legible (top por volumen)
    totals = pivot.sum(axis=1).sort_values(ascending=False)
    pivot = pivot.loc[totals.index[:max_measures]]

    M = pivot.to_numpy(dtype=float)

    if normalize_in_row:
        row_sums = M.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        M = M / row_sums
        cbar_label = "Proporción dentro de la medida"
        title_suffix = " (normalizado por medida)"
        vmin, vmax = 0.0, 1.0
    else:
        cbar_label = "Frecuencia"
        title_suffix = " (conteos)"
        vmin, vmax = None, None

    im = ax.imshow(M, aspect="auto", origin="lower", cmap="Blues", vmin=vmin, vmax=vmax)

    ax.set_yticks(np.arange(pivot.shape[0]))
    ax.set_yticklabels(pivot.index.tolist(), fontsize=8)

    ax.set_xticks(np.arange(pivot.shape[1]))
    ax.set_xticklabels(pivot.columns.astype(str).tolist(), rotation=45, ha="right", fontsize=8)

    ax.set_xlabel("Nivel (LOW_HIGH)")
    ax.set_ylabel("Medida")
    ax.set_title(f"Heatmap global de niveles por medida{title_suffix}", fontsize=12, fontweight="bold")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label=cbar_label)
    plt.tight_layout()


def plot_general_levels_eda_reports(
    levels_by_measure: pd.DataFrame,
    reports_path: Path,
) -> list[tuple[str, Path]]:
    saved: list[tuple[str, Path]] = []
    reports_path.mkdir(parents=True, exist_ok=True)

    # 1) Heatmap global normalizado
    try:
        fig, _ = plt.subplots(figsize=(14, 8))
        plot_levels_heatmap_general(levels_by_measure, normalize_in_row=True, max_measures=40)
        path = save_fig(fig, reports_path, "levels_heatmap_general_norm.png")
        saved.append(("Heatmap global de niveles por medida (normalizado)", path))
    except Exception as e:
        print(f"Error en heatmap global norm: {e}")
        plt.close()

    # 3) Ranking concentración (opcional)
    try:
        fig, _ = plt.subplots(figsize=(14, 5))
        plot_levels_concentration_ranking(levels_by_measure)
        path = save_fig(fig, reports_path, "levels_concentration_ranking.png")
        saved.append(("Ranking de medidas por concentración de niveles", path))
    except Exception as e:
        print(f"Error en ranking concentración: {e}")
        plt.close()

    return saved


def plot_jumps_for_measure(
    events_by_measure_jump: pd.DataFrame,
    measure: str,
    normalize: bool = True,
) -> None:
    """
    Dibuja líneas que representan saltos entre cuantiles usando
    un único color base (azul), con intensidad proporcional al nº de eventos.
    
    Dibuja en el eje actual (plt.gca()), NO crea figura, NO guarda, NO cierra.
    """
    ax = plt.gca()
    
    g = events_by_measure_jump[events_by_measure_jump["measure"] == measure].copy()
    if g.empty:
        ax.text(0.5, 0.5, f"Sin eventos para la medida {measure}", ha="center", va="center")
        ax.axis("off")
        return
    
    # FILTRAR: solo transiciones válidas (con prev_state y new_state)
    g = g[(g["prev_state"].notna()) & (g["new_state"].notna())].copy()
    
    if g.empty:
        ax.text(0.5, 0.5, f"Sin transiciones válidas para {measure}", ha="center", va="center")
        ax.axis("off")
        return

    # 1. Estados (cuantiles)
    states = sorted(set(g["prev_state"]).union(g["new_state"]))
    state_to_x = {s: i for i, s in enumerate(states)}
    n_states = len(states)

    # 2. Intensidad según el nº de eventos
    counts = g["count"].to_numpy()

    if normalize and counts.max() > 0:
        normalized = counts / counts.max()
    else:
        normalized = np.ones_like(counts, dtype=float)

    # 3. Colormap azul (Blues)
    cmap = plt.cm.Blues
    colors = cmap(0.2 + 0.8 * normalized)

    # 4. Grosor también dependiente del nº de eventos
    widths = 1.0 + 4.0 * normalized

    # Dibujar líneas de salto
    for (_, row), w, col in zip(g.iterrows(), widths, colors):
        x0 = state_to_x[row["prev_state"]]
        x1 = state_to_x[row["new_state"]]
        ax.plot([x0, x1], [0, 1], linewidth=w, color=col)

    # Dibujar nodos
    node_color = cmap(0.8)

    for s, x in state_to_x.items():
        ax.scatter(x, 0, s=60, color=node_color)
        ax.scatter(x, 1, s=60, color=node_color)
        ax.text(x, -0.12, s, ha="center", va="top", fontsize=9)
        ax.text(x, 1.12, s, ha="center", va="bottom", fontsize=9)

    ax.set_title(f"Saltos entre cuantiles para la medida: {measure}", fontsize=12, fontweight="bold")
    ax.set_xticks(range(n_states))
    ax.set_xticklabels(states)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["nivel previo", "nivel nuevo"])
    ax.set_ylim(-0.3, 1.3)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    plt.tight_layout()


def plot_transition_heatmap_for_measure(
    events_by_measure_jump: pd.DataFrame,
    measure: str,
    normalize_in_row: bool = False,
) -> None:
    """
    Heatmap de transiciones entre cuantiles para una medida.
    - normalize_in_row=True normaliza por fila (probabilidades condicionales desde cada prev_state).
    
    Dibuja en el eje actual (plt.gca()), NO crea figura, NO guarda, NO cierra.
    """
    ax = plt.gca()
    
    g = events_by_measure_jump[events_by_measure_jump["measure"] == measure].copy()
    if g.empty:
        ax.text(0.5, 0.5, f"Sin eventos para la medida {measure}", ha="center", va="center")
        ax.axis("off")
        return
    
    # FILTRAR: solo filas donde prev_state y new_state son válidos (no NaN/None)
    g = g[(g["prev_state"].notna()) & (g["new_state"].notna())].copy()
    
    if g.empty:
        ax.text(0.5, 0.5, f"Sin transiciones válidas para {measure}", ha="center", va="center")
        ax.axis("off")
        return
    
    states = sorted(set(g["prev_state"]).union(g["new_state"]))
    state_to_idx = {s: i for i, s in enumerate(states)}
    n = len(states)
    
    M = np.zeros((n, n), dtype=float)
    
    for _, row in g.iterrows():
        i = state_to_idx[row["prev_state"]]
        j = state_to_idx[row["new_state"]]
        M[i, j] = row["count"]
    
    if normalize_in_row:
        row_sums = M.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        M = M / row_sums
    
    im = ax.imshow(M, origin="lower", cmap="Blues")
    
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(states, rotation=45, ha="right")
    ax.set_yticklabels(states)
    
    ax.set_xlabel("Estado siguiente (new_state)")
    ax.set_ylabel("Estado previo (prev_state)")
    title_suffix = " (prob. condicional)" if normalize_in_row else " (conteos)"
    ax.set_title(f"Heatmap de transiciones – {measure}{title_suffix}", fontsize=12, fontweight="bold")
    
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label("Frecuencia" if not normalize_in_row else "Probabilidad")
    
    plt.tight_layout()


def plot_transition_heatmap_dual(
    events_by_measure_jump: pd.DataFrame,
    measure: str,
    cmap: str = "Blues",
) -> None:
    """
    Genera dos heatmaps lado a lado:
      1. Conteos absolutos de transiciones
      2. Probabilidad condicional por fila (normalización row-wise)
    
    Dibuja en la figura actual (plt.gcf()), NO crea figura, NO guarda, NO cierra.
    """
    fig = plt.gcf()
    fig.clear()
    
    g = events_by_measure_jump[events_by_measure_jump["measure"] == measure].copy()
    if g.empty:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, f"Sin eventos para la medida {measure}", ha="center", va="center")
        ax.axis("off")
        return
    
    # FILTRAR: solo filas donde prev_state y new_state son válidos (no NaN/None)
    g = g[(g["prev_state"].notna()) & (g["new_state"].notna())].copy()
    
    if g.empty:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, f"Sin transiciones válidas para {measure}", ha="center", va="center")
        ax.axis("off")
        return
    
    states = sorted(set(g["prev_state"]).union(g["new_state"]))
    state_to_idx = {s: i for i, s in enumerate(states)}
    n = len(states)
    
    M = np.zeros((n, n), dtype=float)
    for _, row in g.iterrows():
        i = state_to_idx[row["prev_state"]]
        j = state_to_idx[row["new_state"]]
        M[i, j] = row["count"]
    
    M_norm = M.copy()
    row_sums = M_norm.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    M_norm = M_norm / row_sums
    
    axes = fig.subplots(1, 2)

    im1 = axes[0].imshow(M, origin="lower", cmap=cmap)
    axes[0].set_title(f"{measure}\nConteos de transiciones", fontsize=11, fontweight="bold")
    axes[0].set_xticks(range(n))
    axes[0].set_yticks(range(n))
    axes[0].set_xticklabels(states, rotation=45, ha="right")
    axes[0].set_yticklabels(states)
    fig.colorbar(im1, ax=axes[0], fraction=0.046, pad=0.04, label="Frecuencia")

    im2 = axes[1].imshow(M_norm, origin="lower", cmap=cmap, vmin=0, vmax=1)
    axes[1].set_title(f"{measure}\nProbabilidad condicional", fontsize=11, fontweight="bold")
    axes[1].set_xticks(range(n))
    axes[1].set_yticks(range(n))
    axes[1].set_xticklabels(states, rotation=45, ha="right")
    axes[1].set_yticklabels(states)
    fig.colorbar(im2, ax=axes[1], fraction=0.046, pad=0.04, label="Probabilidad")

    plt.tight_layout()


def plot_ranking_dt_measures(
    dt_summary: pd.DataFrame,
    period_step: float | None = None,
) -> None:
    """
    Ranking de medidas por variabilidad.
    La métrica usada es 1/mean_dt, de modo que:
       - cuanto más variable → barra más alta
       - cuanto más estable  → barra más baja
    
    Dibuja en el eje actual (plt.gca()), NO crea figura, NO guarda, NO cierra.
    """
    ax = plt.gca()

    # Robust handling: check for required columns and non-empty DataFrame
    if (
        dt_summary is None
        or not isinstance(dt_summary, pd.DataFrame)
        or dt_summary.empty
        or "mean_dt" not in dt_summary.columns
    ):
        ax.text(0.5, 0.5, "No hay datos de dt_summary.", ha="center", va="center")
        ax.axis("off")
        return

    dt_summary_clean = dt_summary.dropna(subset=["mean_dt"])
    if dt_summary_clean.empty:
        ax.text(0.5, 0.5, "No hay datos de dt_summary.", ha="center", va="center")
        ax.axis("off")
        return

    dt_summary_ranked = dt_summary_clean.sort_values("mean_dt")

    if period_step is None:
        variability = 1 / dt_summary_ranked["mean_dt"]
        ylabel = "Variabilidad (1 / tiempo medio entre eventos)"
    else:
        variability = 1 / (dt_summary_ranked["mean_dt"] / period_step)
        ylabel = f"Variabilidad (1 / nº de pasos de {period_step}s)"

    ax.bar(dt_summary_ranked.index, variability)

    ax.set_xticks(range(len(dt_summary_ranked)))
    ax.set_xticklabels(dt_summary_ranked.index, rotation=45, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_title("Ranking de medidas por variabilidad\n(barras altas = más variables)", fontsize=12, fontweight="bold")
    ax.grid(axis="y", alpha=0.3, which="both")
    plt.tight_layout()


def plot_visualization_dt_measures(
    dt_summary: pd.DataFrame,
    period_step: float | None = None,
) -> None:
    """
    Visualización del tiempo entre eventos por medida.
    Incluye media, mediana y rango [min, p95].
    
    Dibuja en el eje actual (plt.gca()), NO crea figura, NO guarda, NO cierra.
    """
    ax = plt.gca()

    dt = dt_summary.dropna().sort_values("mean_dt").copy()

    if dt.empty:
        ax.text(0.5, 0.5, "No hay datos de dt_summary.", ha="center", va="center")
        ax.axis("off")
        return

    # Ajustar tamaño de figura dinámicamente según número de medidas
    n_measures = len(dt)
    min_height = 4
    height_per_measure = 0.4
    desired_height = max(min_height, n_measures * height_per_measure)
    fig = plt.gcf()
    fig.set_size_inches(8, desired_height)

    scale = period_step if period_step else 1.0
    unit_label = f"pasos de {period_step}s" if period_step else "segundos"

    mean_dt = dt["mean_dt"] / scale
    median_dt = dt["median_dt"] / scale
    min_dt = dt["min_dt"] / scale
    p95_dt = dt["p95_dt"] / scale

    y = np.arange(len(dt))

    ax.hlines(y=y, xmin=min_dt, xmax=p95_dt, alpha=0.4, linewidth=3, label="Rango [min, p95]")
    ax.scatter(mean_dt, y, s=90, alpha=0.8, marker="o", label="Media Δt")
    ax.scatter(median_dt, y, s=90, alpha=0.8, marker="|", linewidths=3, label="Mediana Δt")

    for i in range(len(dt)):
        ax.text(mean_dt.iloc[i] * 1.05, y[i], f"{mean_dt.iloc[i]:.1f}", va="center", fontsize=9)

    ax.set_yticks(y)
    ax.set_yticklabels(dt.index)
    ax.set_xscale("log")
    ax.set_xlabel(f"Tiempo entre eventos ({unit_label}) [escala log]")
    ax.set_ylabel("Medida")
    ax.set_title("Distribución temporal de eventos por medida", fontsize=12, fontweight="bold")
    ax.grid(alpha=0.3, which="both")
    ax.legend()
    plt.tight_layout()


def plot_dt_hist_for_measure_precomputed(
    dt_steps: np.ndarray,
    measure: str,
    clip_p: float = 99,
    bins: int = 50,
) -> None:
    """
    Histograma dt (inter-arrival time) para UNA medida usando dt_steps precomputados.
    Recorta los outliers al percentil clip_p para que la gráfica sea legible.
    Dibuja en el eje actual (plt.gca()), NO crea figura, NO guarda, NO cierra.
    """
    ax = plt.gca()

    if dt_steps is None or len(dt_steps) == 0:
        ax.text(0.5, 0.5, f"{measure}: no hay suficientes eventos", ha="center", va="center")
        ax.axis("off")
        return

    thr = np.percentile(dt_steps, clip_p)
    dt_clipped = dt_steps[dt_steps <= thr]

    ax.hist(dt_clipped, bins=bins, color="C0", alpha=0.8, edgecolor="black")
    ax.set_title(
        f"Distribución del tiempo entre eventos (dt) – {measure}\n"
        f"(recortado al p{clip_p}, pasos de muestreo)",
        fontsize=12, fontweight="bold"
    )
    ax.set_xlabel("Número de pasos de muestreo (dt / 10 s)")
    ax.set_ylabel("Frecuencia")
    ax.grid(alpha=0.3)
    plt.tight_layout()


def plot_jump_dt_heatmap_for_measure_precomputed(
    dt_steps: np.ndarray,
    jump_types: np.ndarray,
    measure: str,
    max_steps: int = 28,
) -> None:
    """
    Heatmap por medida usando dt_steps y jump_types precomputados:
      - eje X: nº de pasos de muestreo entre eventos (dt)
      - eje Y: tipo de salto (prev_to_new)
      - color: nº de veces
    Dibuja en el eje actual (plt.gca()), NO crea figura, NO guarda, NO cierra.
    """
    ax = plt.gca()

    if dt_steps is None or jump_types is None or len(dt_steps) == 0 or len(jump_types) == 0:
        ax.text(0.5, 0.5, f"{measure}: no hay suficientes eventos.", ha="center", va="center")
        ax.axis("off")
        return

    dt_steps_clipped = np.clip(dt_steps, 1, max_steps)

    # Filter out None/NaN jump_types to avoid comparison errors
    jump_types_clean = np.array([jt for jt in jump_types if jt is not None and not (isinstance(jt, float) and np.isnan(jt))])
    dt_steps_clipped_clean = np.array([dt for dt, jt in zip(dt_steps_clipped, jump_types) if jt is not None and not (isinstance(jt, float) and np.isnan(jt))])

    unique_jumps = sorted(pd.unique(jump_types_clean))
    n_jumps = len(unique_jumps)
    jump_to_row = {j: idx for idx, j in enumerate(unique_jumps)}

    cols = np.arange(1, max_steps + 1)
    col_to_idx = {c: i for i, c in enumerate(cols)}

    M = np.zeros((n_jumps, max_steps), dtype=int)

    for dt_s, jt in zip(dt_steps_clipped_clean, jump_types_clean):
        r = jump_to_row.get(jt)
        c = col_to_idx.get(dt_s)
        if r is not None and c is not None:
            M[r, c] += 1

    # Ajustar tamaño de figura dinámicamente según número de saltos
    fig = plt.gcf()
    min_height = 4
    height_per_jump = 0.2
    desired_height = max(min_height, n_jumps * height_per_jump)
    fig.set_size_inches(fig.get_figwidth(), desired_height)

    im = ax.imshow(M, aspect="auto", origin="lower", cmap="Blues")

    plt.colorbar(im, ax=ax, label="Número de eventos")

    # Eje X: mostrar todos los ticks o reducir si hay muchos
    if max_steps <= 25:
        ax.set_xticks(np.arange(max_steps))
        ax.set_xticklabels(cols, fontsize=9)
    else:
        step_x = max(1, max_steps // 10)
        ax.set_xticks(np.arange(0, max_steps, step_x))
        ax.set_xticklabels(cols[::step_x], fontsize=9)

    # Eje Y: asegurar que todos los ticks sean legibles
    ax.set_yticks(np.arange(n_jumps))

    # Ajustar tamaño de fuente según número de saltos
    if n_jumps <= 10:
        ytick_fontsize = 10
    elif n_jumps <= 20:
        ytick_fontsize = 9
    elif n_jumps <= 30:
        ytick_fontsize = 8
    else:
        ytick_fontsize = 7

    ax.set_yticklabels(unique_jumps, fontsize=ytick_fontsize)

    ax.set_xlabel("Nº de pasos de muestreo entre eventos (dt / 10 s)")
    ax.set_ylabel("Tipo de salto (prev_to_new)")
    ax.set_title(f"Distribución de dt por tipo de salto – {measure}", fontsize=12, fontweight="bold")

    # Añadir flecha indicando que la última columna acumula eventos con dt > max_steps
    total_clipped = np.sum(dt_steps > max_steps)
    if total_clipped > 0:
        arrow_x = max_steps
        arrow_y = n_jumps / 2 - 0.5
        ax.annotate(
            "",
            xy=(arrow_x, arrow_y),
            xytext=(arrow_x, arrow_y),
            arrowprops=dict(
                arrowstyle="->",
                color="#802A2A",
                lw=2,
            ),
        )

    plt.tight_layout()


def plot_measure_events_eda_reports(
    events_by_measure_jump: pd.DataFrame,
    dt_summary: pd.DataFrame, 
    reports_path: Path,
    measure: str,
    precomputed_dt_jumps_by_measure: dict = None,
    period_step: float = 10,
) -> list[tuple[str, Path]]:
    """
    Genera informes EDA centrados en los eventos de cambio de estado.
    Devuelve la lista de tuplas (título, path) de los ficheros guardados.

    Parámetros principales:
      events_by_measure_jump : DataFrame con conteos de transiciones por medida
      dt_summary : DataFrame con estadísticas de dt por medida
      df_events : DataFrame con eventos
      meta : DataFrame con metadatos de eventos
      ids_by_measure : dict mapping measure -> list of event_ids
      reports_path : carpeta para guardar las figuras
      measures : lista de medidas a procesar (si None, usa todas las disponibles)
      period_step : periodo de muestreo en segundos
    """
    saved: list[tuple[str, Path]] = []
    
    reports_path.mkdir(parents=True, exist_ok=True)

    if measure not in dt_summary.index:
        print(f"Medida '{measure}' no encontrada en dt_summary. Se omiten gráficos.")
        return saved
    # Saltos entre cuantiles
    try:
        fig, _ = plt.subplots(figsize=(10, 4))
        plot_jumps_for_measure(events_by_measure_jump, measure)
        plt.tight_layout()
        path = save_fig(fig, reports_path, f"events_jumps_{measure}.png")
        saved.append((f"Saltos entre cuantiles — {measure}", path))
    except Exception as e:
        print(f"Error en saltos para {measure}: {e}")
        plt.close()

    # Heatmap dual de transiciones
    try:
        fig = plt.figure(figsize=(12, 5))
        plot_transition_heatmap_dual(events_by_measure_jump, measure)
        plt.tight_layout()
        path = save_fig(fig, reports_path, f"events_heatmap_dual_{measure}.png")
        saved.append((f"Heatmap de transiciones — {measure}", path))
    except Exception as e:
        print(f"Error en heatmap dual para {measure}: {e}")
        plt.close()

    # Histograma dt (usando preprocesado si está disponible)
    try:
        fig, _ = plt.subplots(figsize=(10, 4))
        if precomputed_dt_jumps_by_measure and measure in precomputed_dt_jumps_by_measure:
            dt_steps = precomputed_dt_jumps_by_measure[measure]["dt_steps"]
            plot_dt_hist_for_measure_precomputed(dt_steps, measure)
        plt.tight_layout()
        path = save_fig(fig, reports_path, f"events_dt_hist_{measure}.png")
        saved.append((f"Histograma dt — {measure}", path))
    except Exception as e:
        print(f"Error en histograma dt para {measure}: {e}")
        plt.close()

    # Heatmap dt por tipo de salto (usando preprocesado si está disponible)
    try:
        fig, _ = plt.subplots(figsize=(10, 6))
        if precomputed_dt_jumps_by_measure and measure in precomputed_dt_jumps_by_measure:
            dt_steps = precomputed_dt_jumps_by_measure[measure]["dt_steps"]
            jump_types = precomputed_dt_jumps_by_measure[measure]["jump_types"]
            plot_jump_dt_heatmap_for_measure_precomputed(dt_steps, jump_types, measure)
        plt.tight_layout()
        path = save_fig(fig, reports_path, f"events_jump_dt_heatmap_{measure}.png")
        saved.append((f"Heatmap dt por salto — {measure}", path))
    except Exception as e:
        print(f"Error en heatmap dt para {measure}: {e}")
        plt.close()

    return saved


def plot_general_events_eda_reports(
    dt_summary: pd.DataFrame,
    reports_path: Path,
    period_step: float = 10,
) -> list[tuple[str, Path]]:
    """
    Genera informes EDA centrados en los eventos de cambio de estado.
    Devuelve la lista de tuplas (título, path) de los ficheros guardados.

    Parámetros principales:
      events_by_measure_jump : DataFrame con conteos de transiciones por medida
      dt_summary : DataFrame con estadísticas de dt por medida
      df_events : DataFrame con eventos
      meta : DataFrame con metadatos de eventos
      ids_by_measure : dict mapping measure -> list of event_ids
      reports_path : carpeta para guardar las figuras
      measures : lista de medidas a procesar (si None, usa todas las disponibles)
      period_step : periodo de muestreo en segundos
    """
    saved: list[tuple[str, Path]] = []
    
    reports_path.mkdir(parents=True, exist_ok=True)

    # 1) Ranking de variabilidad
    try:
        fig, _ = plt.subplots(figsize=(12, 6))
        plot_ranking_dt_measures(dt_summary, period_step=period_step)
        path = save_fig(fig, reports_path, "events_ranking_variability.png")
        saved.append(("Ranking de medidas por variabilidad", path))
    except Exception:
        plt.close()

    # 2) Visualización dt por medida
    try:
        fig, _ = plt.subplots(figsize=(13, 6))
        plot_visualization_dt_measures(dt_summary, period_step=period_step)
        path = save_fig(fig, reports_path, "events_dt_visualization.png")
        saved.append(("Distribución temporal de eventos por medida", path))
    except Exception:
        plt.close()
    
    return saved
