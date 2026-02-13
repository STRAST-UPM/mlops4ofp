# ============================================================
#  Informe HTML final (Fase 03)
# ============================================================
from mlops4ofp.tools.figures import figures03 as figures
from datetime import datetime
import pandas as pd
from mlops4ofp.tools.html_reports.html import HtmlReport, close_div, open_grid, kpi_card, kpi_grid, render_figure_card, smart_fmt, render_header, render_footer, html_escape, table_card, subsection, section
import importlib
import mlops4ofp.tools.html_reports.html as html
importlib.reload(html)
importlib.reload(figures)
import numpy as np
from typing import Any, Optional


from collections import Counter
from itertools import chain


#############################################################################################################################################
#--------------------------------------------------------------------------------------------------------------------------------------------
# Procesado del dataset para el informe
#--------------------------------------------------------------------------------------------------------------------------------------------
#############################################################################################################################################



def _iter_lists(arr):
    """Itera listas válidas: None/NaN -> vacío."""
    for x in arr:
        if x is None:
            yield ()
            continue
        if isinstance(x, float) and np.isnan(x):
            yield ()
            continue
        if isinstance(x, (list, tuple, np.ndarray)):
            yield x
        else:
            # si por algún motivo viene algo raro
            yield ()


def precompute_window_col_stats(
    df_windows: pd.DataFrame,
    col: str,
    *,
    max_len_bucket: int = 20,
    top_k: int = 30,
    others_bucket: bool = True,
) -> dict:
    """
    Precomputo único para una columna list[int] (OW_events/PW_events).
    Devuelve dict con:
      - lengths: np.ndarray (len por fila)
      - empty_mask: np.ndarray bool
      - len_table: DataFrame (count, percent) index=length bucket
      - event_table: DataFrame (count, percent) index=event_id (y Others)
      - totals: dict con métricas básicas
    """

    arr = df_windows[col].to_numpy()

    # 1) lengths (rápido con fromiter)
    def _len0(x):
        if x is None:
            return 0
        if isinstance(x, float) and np.isnan(x):
            return 0
        try:
            return len(x)
        except Exception:
            return 0

    lengths = np.fromiter((_len0(x) for x in arr), dtype=np.int64, count=len(arr))
    empty_mask = (lengths == 0)

    # 2) tabla de longitudes bucketizada
    clipped = np.minimum(lengths, max_len_bucket)
    bc = np.bincount(clipped, minlength=max_len_bucket + 1)  # 0..max_len_bucket
    over = int((lengths > max_len_bucket).sum())

    idx = list(range(0, max_len_bucket + 1))
    counts = list(bc.astype(int))
    if over:
        idx.append(f">{max_len_bucket}")
        counts.append(over)

    len_table = pd.DataFrame({"count": counts}, index=idx)
    total_rows = int(len_table["count"].sum())
    len_table["percent"] = (100 * len_table["count"] / total_rows) if total_rows else 0.0

    # 3) frecuencia event_id (sin explode)
    c = Counter()
    for lst in _iter_lists(arr):
        if isinstance(lst, np.ndarray):
            if lst.size == 0:
                continue
        elif not lst:
            continue
        # For numpy arrays, convert to list for iteration
        if isinstance(lst, np.ndarray):
            iterable = lst.tolist()
        else:
            iterable = lst
        for v in iterable:
            if v is None:
                continue
            # normaliza floats tipo 3.0
            if isinstance(v, float):
                try:
                    if np.isnan(v):
                        continue
                except (TypeError, ValueError):
                    # v might be an array or non-scalar
                    continue
                if v.is_integer():
                    v = int(v)
            c[v] += 1

    if not c:
        event_table = pd.DataFrame(columns=["count", "percent"])
    else:
        items = c.most_common(top_k)
        idx = [k for k, _ in items]
        vals = [int(v) for _, v in items]

        if others_bucket and len(c) > top_k:
            others = int(sum(c.values()) - sum(vals))
            idx.append("Others")
            vals.append(others)

        event_table = pd.DataFrame({"count": vals}, index=idx)
        total_events = int(event_table["count"].sum())
        event_table["percent"] = (100 * event_table["count"] / total_events) if total_events else 0.0

    return {
        "lengths": lengths,
        "empty_mask": empty_mask,
        "len_table": len_table,
        "event_table": event_table,
        "totals": {
            "n_rows": int(len(arr)),
            "n_empty": int(empty_mask.sum()),
            "n_non_empty": int((~empty_mask).sum()),
            "total_events": int(sum(c.values())),
            "n_unique_event_ids": int(len(c)),
        },
    }


#############################################################################################################################################
#--------------------------------------------------------------------------------------------------------------------------------------------
# Helpers para informe html
#--------------------------------------------------------------------------------------------------------------------------------------------
#############################################################################################################################################


def window_totals_kpi_cards(stats: dict, *, label: str) -> list[str]:
    """
    KPIs resumen para una columna de ventanas (OW_events o PW_events).

    Cada KPI describe propiedades estructurales del dataset por ventanas,
    no del timeline original.
    """
    t = stats.get("totals", {}) or {}

    n_rows = int(t.get("n_rows", 0) or 0)
    n_empty = int(t.get("n_empty", 0) or 0)
    n_non_empty = int(t.get("n_non_empty", 0) or 0)
    total_events = int(t.get("total_events", 0) or 0)
    n_unique = int(t.get("n_unique_event_ids", 0) or 0)

    avg_events_per_window = (total_events / n_rows) if n_rows > 0 else 0.0
    empty_ratio = (100 * n_empty / n_rows) if n_rows > 0 else 0.0

    return [
        kpi_card(
            f"{label} — Muestras",
            f"{n_rows:,}",
            "Número total de ventanas temporales generadas (filas del dataset).",
        ),
        kpi_card(
            f"{label} — Ventanas con eventos",
            f"{n_non_empty:,}",
            "Ventanas que contienen al menos un evento.",
        ),
        kpi_card(
            f"{label} — Eventos totales",
            f"{total_events:,}",
            "Número total de apariciones de eventos acumuladas en todas las ventanas.",
        ),
        kpi_card(
            f"{label} — Tipos de evento",
            f"{n_unique:,}",
            "Cantidad de eventos distintos observados en las ventanas.",
        ),
        kpi_card(
            f"{label} — Media eventos / ventana",
            f"{avg_events_per_window:.3f}",
            "Promedio de eventos contenidos en cada ventana temporal.",
        ),
        kpi_card(
            f"{label} — % ventanas vacías",
            f"{empty_ratio:.1f}%",
            "Proporción de ventanas sin eventos.",
        ),
    ]



def window_list_length_table_from_stats(stats: dict) -> pd.DataFrame:
    """
    Tabla de tamaños de lista (count, percent) desde precompute_window_col_stats().
    """
    df = stats["len_table"].copy()
    df.index.name = "Events per window"
    # orden: count desc si quieres, o mantener el bucket order:
    # df = df.sort_values("count", ascending=False)
    df= df.reset_index()
    return df



def add_windows_size_tables_to_report(
    rep,
    *,
    col_label: str,
    stats: dict,
    id_to_name: dict[int, str] | None = None,
) -> None:

    df_len = window_list_length_table_from_stats(stats)
    rep.add(table_card(df_len, title=f"Tamaño de lista — {col_label}", index=False))




def invert_event_catalog(name_to_id: dict[str, int]) -> dict[int, str]:
    """{name: id} -> {id: name}"""
    out: dict[int, str] = {}
    for name, eid in (name_to_id or {}).items():
        try:
            eid = int(eid)
        except Exception:
            continue
        out.setdefault(eid, str(name))  # si hay duplicados, se queda el primero
    return out


def window_event_id_compare_table(
    ow_stats: dict,
    pw_stats: dict,
    *,
    id_to_name: Optional[dict[int, str]] = None,
    include_others: bool = True,
    sort_by: str = "total_count",
) -> pd.DataFrame:

    ow_raw = ow_stats.get("event_table")
    pw_raw = pw_stats.get("event_table")

    ow = ow_raw.copy() if isinstance(ow_raw, pd.DataFrame) else pd.DataFrame(columns=["count", "percent"])
    pw = pw_raw.copy() if isinstance(pw_raw, pd.DataFrame) else pd.DataFrame(columns=["count", "percent"])

    # Asegura columnas esperadas
    for df in (ow, pw):
        if "count" not in df.columns:
            df["count"] = 0
        if "percent" not in df.columns:
            df["percent"] = 0.0

    ow.index.name = "event_id"
    pw.index.name = "event_id"

    def _is_others(x):
        return isinstance(x, str) and x.lower() in ("others", "otros")

    if not include_others:
        ow = ow.loc[~ow.index.map(_is_others)]
        pw = pw.loc[~pw.index.map(_is_others)]

    ow = ow.rename(columns={"count": "OW_count", "percent": "OW_percent"})
    pw = pw.rename(columns={"count": "PW_count", "percent": "PW_percent"})

    df = ow.join(pw, how="outer").fillna(0)

    df["total_count"] = df["OW_count"].astype(int) + df["PW_count"].astype(int)

    if id_to_name:
        def _name(idx):
            if _is_others(idx):
                return str(idx)
            try:
                eid = int(idx)
            except Exception:
                return str(idx)
            return id_to_name.get(eid, f"Unknown ({eid})")
        df.insert(0, "event_name", [_name(i) for i in df.index])
    else:
        df.insert(0, "event_name", [str(i) for i in df.index])

    for c in ["OW_count", "PW_count", "total_count"]:
        df[c] = df[c].astype(int)

    if sort_by not in df.columns:
        sort_by = "total_count"
    df = df.sort_values(sort_by, ascending=False)

    if include_others and any(_is_others(i) for i in df.index):
        others_rows = df.loc[df.index.map(_is_others)]
        main_rows = df.loc[~df.index.map(_is_others)]
        df = pd.concat([main_rows, others_rows], axis=0)
    
    df = df.reset_index()

    return df



def add_windows_event_compare_table_to_report(
    rep,
    *,
    ow_stats: dict,
    pw_stats: dict,
    id_to_name: dict,
) -> None:

    df_cmp = window_event_id_compare_table(
        ow_stats,
        pw_stats,
        id_to_name=id_to_name,
        include_others=True,
        sort_by="total_count",
    )
    try:
        if hasattr(df_cmp, 'empty'):
            if not df_cmp.empty:
                rep.add(table_card(df_cmp, title="Event IDs: OW vs PW (count/percent)", index=False, table_class="compare-events"))
        elif df_cmp is not None:
            print(f"[WARN] window_event_id_compare_table returned type {type(df_cmp)} without .empty attribute. Skipping table.")
    except ValueError as e:
        print(f"[ERROR] Could not evaluate DataFrame: {e}. Type: {type(df_cmp)}. Skipping table.")







#############################################################################################################################################
#--------------------------------------------------------------------------------------------------------------------------------------------
#  Generación del informe HTML final
#--------------------------------------------------------------------------------------------------------------------------------------------
#############################################################################################################################################


def generate_html_report(ctx: dict, df_windows: pd.DataFrame, catalog: dict ) -> None:
    """
    Genera el informe HTML final de preparewindowsds.

    Parámetros:
        ctx: Contexto de ejecución.
        df_windows: DataFrame con columnas OW_events y PW_events
        catalog: Catálogo de eventos (event_id -> metadata)
    """
    print("[preparewindowsds] Generando informe HTML final...")

    id_to_name = invert_event_catalog(catalog)
    ow_stats = precompute_window_col_stats(df_windows, "OW_events", max_len_bucket=20, top_k=30, others_bucket=True)
    pw_stats = precompute_window_col_stats(df_windows, "PW_events", max_len_bucket=20, top_k=30, others_bucket=True)

    report_path = ctx["outputs"]["report"]
    figures_dir = ctx["figures_dir"]
    active_variant = ctx["variant"]


    # Report: start() ya mete:
    # - header + css fijo
    # - título + fecha
    # - pills automáticas de ctx["variant_params"]
    # - <hr>
    rep = HtmlReport(
        title=f"PrepareWindowsDS Report — Variante {active_variant}",
        ctx=ctx,
    ).start()


    rep.add(section("Resumen OW_events"))
    rep.add(kpi_grid(window_totals_kpi_cards(ow_stats, label="OW_events")))

    rep.add(section("Resumen PW_events"))
    rep.add(kpi_grid(window_totals_kpi_cards(pw_stats, label="PW_events")))
    
    # Estadísticas
    rep.add(section(
        "Distribución de eventos en ventanas",
        intro=(
            "En esta sección se analiza cómo se distribuyen los eventos dentro de las "
            "ventanas temporales generadas. El objetivo es entender la densidad de eventos "
            "por ventana, identificar ventanas vacías y evaluar si la información está "
            "concentrada en pocas ventanas o repartida de forma homogénea."
        )
    ))


    windows_hist_figs = figures.plot_windows_hist_reports(
        reports_path=figures_dir,
        ow=ow_stats,
        pw=pw_stats,
        max_len=20,
        top_k=30,
    )
    rep.add(open_grid(cols=2, gap_rem=1.0))
    for fig_title, fig_path in windows_hist_figs:
        rep.add(render_figure_card(fig_title, fig_path.name, max_width="80%"))
    rep.add(close_div())

    add_windows_size_tables_to_report(rep, col_label="OW_events", stats=ow_stats, id_to_name=id_to_name)
    add_windows_size_tables_to_report(rep, col_label="PW_events", stats=pw_stats, id_to_name=id_to_name)


    

    rep.add(section(
        "Frecuencia de eventos — comparación OW vs PW",
        intro=(
            "Esta sección compara la frecuencia de aparición de cada tipo de evento "
            "en las ventanas de observación (OW) y de predicción (PW). "
        )
    ))

    
    events_frequency_figs = figures.plot_events_frequency_eda_reports_fast(
        reports_path=figures_dir,
        ow=ow_stats,
        pw=pw_stats,
        max_len=20,
        top_k=30,
    )
    rep.add(open_grid(cols=2, gap_rem=1.0))
    for fig_title, fig_path in events_frequency_figs:
        rep.add(render_figure_card(fig_title, fig_path.name, max_width="80%"))
    rep.add(close_div())


    add_windows_event_compare_table_to_report(
        rep,
        ow_stats=ow_stats,
        pw_stats=pw_stats,
        id_to_name=id_to_name,
    )

    
    rep.add(section(
        "Eventos en ventanas — vacíos y solapamientos",
        intro=(
            "Este apartado analiza cómo se distribuyen los eventos dentro de las ventanas temporales de observación (OW) "
            "y predicción (PW). Las figuras muestran, por un lado, la proporción de ventanas vacías frente a aquellas que "
            "contienen uno o más eventos, y por otro, el grado de solapamiento entre ambas ventanas. "
        )
    ))


    windows_empty_and_overlap_figs = figures.plot_windows_empty_and_overlap_reports(
        reports_path=figures_dir,
        ow=ow_stats,
        pw=pw_stats,
        max_len=20,
        top_k=30,
    )

    rep.add(open_grid(cols=2, gap_rem=1.0))
    for fig_title, fig_path in windows_empty_and_overlap_figs:
        rep.add(render_figure_card(fig_title, fig_path.name, max_width="80%"))
    rep.add(close_div())




    # Guardar
    rep.write(report_path)

    print(f"[OK] Informe HTML generado en {report_path}")