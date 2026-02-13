from __future__ import annotations
from pathlib import Path
import matplotlib.pyplot as plt


# Standard library
from pathlib import Path
from tabnanny import verbose
from typing import Any

# Third-party
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch




from mlops4ofp.tools.figures.figures_general import save_fig


# ============================================================================================================================================================
# ============================================================================================================================================================
# ============================================================================================================================================================
# 03- PREPARE WINDOWS FIGURES
# ============================================================================================================================================================
# ============================================================================================================================================================
# ============================================================================================================================================================


def plot_list_length_hist_from_table(len_table: pd.DataFrame, *, title: str = ""):
    x = [str(i) for i in len_table.index]
    y = len_table["count"].to_numpy()
    plt.bar(x, y)
    plt.title(title or "Distribución tamaño lista", fontsize=14, fontweight='bold')
    plt.xlabel("Número de eventos", fontsize=12)
    plt.ylabel("Ocurrencias", fontsize=12)
    plt.xticks(fontsize=11)
    plt.yticks(fontsize=11)
    plt.tight_layout()



def plot_windows_hist_reports(
    reports_path: Path,
    ow =dict(),
    pw = dict(),
    *,
    max_len: int = 20,
    top_k: int = 30,
) -> list[tuple[str, Path]]:
    saved: list[tuple[str, Path]] = []
    reports_path.mkdir(parents=True, exist_ok=True)

    # 1) Tamaño lista OW
    fig, _ = plt.subplots(figsize=(10, 4))
    plot_list_length_hist_from_table(ow["len_table"], title="Distribución tamaño lista — OW_events")
    path = save_fig(fig, reports_path, "ow_list_length_hist.png")
    saved.append(("Distribución tamaño lista — OW_events", path))

    # 2) Tamaño lista PW
    fig, _ = plt.subplots(figsize=(10, 4))
    plot_list_length_hist_from_table(pw["len_table"], title="Distribución tamaño lista — PW_events")
    path = save_fig(fig, reports_path, "pw_list_length_hist.png")
    saved.append(("Distribución tamaño lista — PW_events", path))

    return saved




def plot_event_id_frequency_from_table(event_table: pd.DataFrame, *, title: str = ""):
    if event_table.empty:
        plt.text(0.5, 0.5, "No events", ha="center", va="center", fontsize=14)
        plt.axis("off")
        return
    plt.bar([str(i) for i in event_table.index], event_table["count"].to_numpy())
    plt.title(title or "Frecuencia event_id", fontsize=18, fontweight='bold')
    plt.xlabel("Event ID", fontsize=14)
    plt.xticks(rotation=45, ha="right", fontsize=12)
    plt.ylabel("Count", fontsize=14)
    plt.yticks(fontsize=12)
    plt.tight_layout()



def plot_events_frequency_eda_reports_fast(
    reports_path: Path,
    ow =dict(),
    pw = dict(),
    *,
    max_len: int = 20,
    top_k: int = 30,

) -> list[tuple[str, Path]]:
    saved: list[tuple[str, Path]] = []
    reports_path.mkdir(parents=True, exist_ok=True)
    # 5) Frecuencia event_id OW
    fig, _ = plt.subplots(figsize=(12, 4))
    plot_event_id_frequency_from_table(ow["event_table"], title="Frecuencia event_id — OW_events")
    path = save_fig(fig, reports_path, "ow_event_id_frequency.png")
    saved.append(("Frecuencia event_id — OW_events", path))

    # 6) Frecuencia event_id PW
    fig, _ = plt.subplots(figsize=(12, 4))
    plot_event_id_frequency_from_table(pw["event_table"], title="Frecuencia event_id — PW_events")
    path = save_fig(fig, reports_path, "pw_event_id_frequency.png")
    saved.append(("Frecuencia event_id — PW_events", path))

    return saved




def plot_empty_rate_from_totals(totals: dict, *, title: str = ""):
    counts = [totals["n_empty"], totals["n_non_empty"]]
    total = sum(counts)
    percentages = [c / total * 100 for c in counts]
    labels = [f"Empty\n({percentages[0]:.1f}%)", f"Non-empty\n({percentages[1]:.1f}%)"]
    colors = ["#FF6B6B", "#51CF66"]
    plt.bar(labels, counts, color=colors)
    plt.title(title or "Vacío vs no vacío", fontsize=12, fontweight='bold')
    plt.ylabel("Count", fontsize=11)
    plt.tight_layout()


def plot_windows_empty_and_overlap_reports(
    reports_path: Path,
    ow=dict(),
    pw=dict(),
    *,
    max_len: int = 20,
    top_k: int = 30,
) -> list[tuple[str, Path]]:
    saved: list[tuple[str, Path]] = []
    reports_path.mkdir(parents=True, exist_ok=True)

    # 3) Vacío/no vacío OW
    fig, _ = plt.subplots(figsize=(8, 4))
    plot_empty_rate_from_totals(ow["totals"], title="Vacío vs no vacío — OW_events")
    path = save_fig(fig, reports_path, "ow_empty_rate.png")
    saved.append(("Vacío vs no vacío — OW_events", path))

    # 4) Vacío/no vacío PW
    fig, _ = plt.subplots(figsize=(8, 4))
    plot_empty_rate_from_totals(pw["totals"], title="Vacío vs no vacío — PW_events")
    path = save_fig(fig, reports_path, "pw_empty_rate.png")
    saved.append(("Vacío vs no vacío — PW_events", path))

    # 7) Solapamiento OW vs PW usando empty_mask ya calculados
    fig, _ = plt.subplots(figsize=(10, 4))
    ow_empty = ow["empty_mask"]
    pw_empty = pw["empty_mask"]
    both_nonempty = int((~ow_empty & ~pw_empty).sum())
    ow_only = int((~ow_empty & pw_empty).sum())
    pw_only = int((ow_empty & ~pw_empty).sum())
    both_empty = int((ow_empty & pw_empty).sum())
    
    counts = [both_nonempty, ow_only, pw_only, both_empty]
    total = sum(counts)
    percentages = [c / total * 100 for c in counts]
    labels = [f"both non-empty\n({percentages[0]:.1f}%)", 
              f"OW only\n({percentages[1]:.1f}%)", 
              f"PW only\n({percentages[2]:.1f}%)", 
              f"both empty\n({percentages[3]:.1f}%)"]
    colors = ["#51CF66", "#4ECDC4", "#FFE66D", "#FF6B6B"]
    
    plt.bar(labels, counts, color=colors)
    plt.title("Solapamiento OW vs PW — vacío/no vacío", fontsize=12, fontweight='bold')
    plt.ylabel("Count", fontsize=11)
    plt.tight_layout()

    path = save_fig(fig, reports_path, "ow_pw_overlap_empty_nonempty.png")
    saved.append(("Solapamiento OW vs PW — vacío/no vacío", path))

    return saved
