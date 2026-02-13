import pandas as pd
import mlops4ofp.tools.figures.figures02 as figures
import re
import numpy as np

from mlops4ofp.tools.html_reports.html import (
    HtmlReport,
    events_card,
    figures_grid,
    h,
    para,
    section,
    subsection,
    card,
    table_card,
    kpi_card,
    kpi_grid,
)



#############################################################################################################################################
# -------------------------------------------------------------------------------------------------------------------------------------------
# Procesado del dataset para el informe
#--------------------------------------------------------------------------------------------------------------------------------------------
#############################################################################################################################################


_LEVEL_RE = re.compile(r"_(\d+_\d+)$")   # "0_40", "90_100", etc.

def _precompute_dt_and_jumps(df_long, meta_stats, measure, period_step=10):
    # Solo IDs de transiciones para esta medida
    ids_transitions = meta_stats.index[
        (meta_stats["measure"] == measure) & (meta_stats["prev_to_new"].notna())
    ].to_numpy()
    mask = df_long["event_id"].isin(ids_transitions)
    df_m = df_long.loc[mask].sort_values("segs")
    if len(df_m) < 2:
        return None, None
    ts = df_m["segs"].to_numpy(dtype=np.int64)
    ev_ids = df_m["event_id"].to_numpy(dtype=np.int64)
    dt = np.diff(ts)
    dt_steps = (dt / period_step).astype(int)
    jump_types = meta_stats.loc[ev_ids[1:], "prev_to_new"].to_numpy() if len(ev_ids) > 1 else None
    return dt_steps, jump_types


def prepare_dataset_events_analysis(event_dict, df_events, strategy: str = "both"):
    """
    Prepara análisis de eventos a partir del diccionario y el DataFrame de eventos.

    Devuelve:
        meta_stats : pd.DataFrame
            Metadata de eventos (index=event_id): event_name, measure, prev_state, new_state, prev_to_new, count, percent_total
        events_by_measure_jump : pd.DataFrame
            Conteos y % solo de transiciones (measure, prev_to_new, count, percent_total, prev_state, new_state)
        ids_by_measure : dict
            measure -> np.array([event_ids])
        df_interarrival_stats : pd.DataFrame
            Tabla — Interarrival por evento (event_id, event_name, num_appearances, num_intervals, mean/std/min/max)
        dt_summary_transitions : pd.DataFrame
            Estadísticas de dt por medida (index=measure)
        precomputed_dt_jumps_by_measure : dict
            measure -> {"dt_steps": ..., "jump_types": ...}
    """

    # ------------------------------------------------------------
    # 0) Normalizar df_events a formato long interno
    #    df_long: una fila por ocurrencia (event_id, segs, row_idx_origen)
    # ------------------------------------------------------------
    if "event_id" in df_events.columns:
        df_long = df_events[["event_id", "segs"]].copy()
        df_long["event_id"] = df_long["event_id"].astype(int)
        df_long["row_idx"] = np.arange(len(df_long), dtype=np.int64)
    elif "events" in df_events.columns:
        exploded = df_events[["events", "segs"]].explode("events")
        exploded = exploded.dropna(subset=["events"])
        exploded = exploded.rename(columns={"events": "event_id"})
        exploded["event_id"] = exploded["event_id"].astype(int)
        exploded["row_idx"] = exploded.index.to_numpy(dtype=np.int64)
        df_long = exploded.reset_index(drop=True)
    else:
        raise ValueError("df_events debe contener 'event_id' o 'events'.")

    # ============================================================
    # 1. META: Parsear measure + transiciones a partir del nombre
    # ============================================================
    trans_re = re.compile(r'_(\d+_\d+)-to-(\d+_\d+)$')
    level_re = re.compile(r'_(\d+_\d+)$')
    meta_stats = pd.DataFrame([
        {
            "event_id": int(eid),
            "event_name": name,
        }
        for name, eid in event_dict.items()
    ])

    def parse_event(row):
        name = row["event_name"]
        m = trans_re.search(name)
        if m:
            prev_state, new_state = m.group(1), m.group(2)
            prev_to_new = f"{prev_state}-to-{new_state}"
            measure = name[:m.start()]
        else:
            m2 = level_re.search(name)
            if m2:
                measure = name[:m2.start()]
                prev_state = new_state = prev_to_new = None
            else:
                # Si termina en _NaN_NaN, extrae la medida correctamente
                if name.endswith("_NaN_NaN"):
                    measure = name[:name.rfind("_NaN_NaN")]
                else:
                    measure = None
                prev_state = new_state = prev_to_new = None
        return pd.Series({
            "measure": measure,
            "prev_state": prev_state,
            "new_state": new_state,
            "prev_to_new": prev_to_new
        })
    meta_stats = pd.concat([meta_stats, meta_stats.apply(parse_event, axis=1)], axis=1).set_index("event_id").sort_index()

    # ============================================================
    # 2. CONTEO por evento + % total
    # ============================================================
    counts_by_id = df_long["event_id"].value_counts().rename("count")
    meta_stats["count"] = counts_by_id
    meta_stats["count"] = meta_stats["count"].fillna(0).astype("int64")
    total_events = int(meta_stats["count"].sum())
    meta_stats["percent_total"] = (100 * meta_stats["count"] / total_events) if total_events > 0 else 0.0

    # ============================================================
    # 3. SOLO transiciones — events_by_measure_jump
    # ============================================================
    events_by_measure_jump = (
        meta_stats[meta_stats["prev_to_new"].notna()]
        .groupby(["measure", "prev_to_new"], as_index=False)["count"]
        .sum()
    )
    if not events_by_measure_jump.empty:
        events_by_measure_jump["percent_total"] = (
            100 * events_by_measure_jump["count"] / total_events
            if total_events > 0 else 0.0
        )
        split_states = events_by_measure_jump["prev_to_new"].str.split("-to-", expand=True)
        events_by_measure_jump["prev_state"] = split_states[0]
        events_by_measure_jump["new_state"] = split_states[1]

    # ============================================================
    # 4. ids_by_measure
    # ============================================================
    ids_by_measure = {
        m: meta_stats.index[meta_stats["measure"] == m].to_numpy()
        for m in meta_stats["measure"].dropna().unique()
    }

    # ============================================================
    # 5. dt_summary por medida de transiciones
    # ============================================================
    dt_rows_transitions = []
    transition_event_ids = meta_stats.index[meta_stats["prev_to_new"].notna()].to_numpy()
    measures_with_transitions = meta_stats.loc[transition_event_ids, "measure"].dropna().unique()
    for measure in measures_with_transitions:
        ids = meta_stats.index[(meta_stats["measure"] == measure) & (meta_stats["prev_to_new"].notna())].to_numpy()
        ts = df_long.loc[df_long["event_id"].isin(ids), "segs"].to_numpy(dtype=np.float64)
        if len(ts) < 2:
            continue
        ts_sorted = np.sort(ts)
        dt = np.diff(ts_sorted)
        dt = dt[dt >= 0]
        if len(dt) == 0:
            continue
        dt_rows_transitions.append({
            "measure": measure,
            "n_events": int(len(ts)),
            "mean_dt": float(np.mean(dt)),
            "median_dt": float(np.median(dt)),
            "p95_dt": float(np.percentile(dt, 95)),
            "min_dt": float(np.min(dt)),
            "max_dt": float(np.max(dt)),
        })
    dt_summary_transitions = (
        pd.DataFrame(dt_rows_transitions).set_index("measure")
        if dt_rows_transitions else
        pd.DataFrame(columns=["n_events","mean_dt","median_dt","p95_dt","min_dt","max_dt"]).set_index("measure")
    )

    # ============================================================
    # 6. Tabla — Interarrival por evento (solo transiciones)
    # ============================================================
    interarrival_rows = []
    transition_ids = meta_stats.index[meta_stats["prev_to_new"].notna()]
    grouped = df_long[df_long["event_id"].isin(transition_ids)].groupby("event_id")["segs"]
    for ev_id, segs in grouped:
        epochs = np.sort(segs.to_numpy(dtype=np.float64))
        n = len(epochs)
        if n == 0:
            continue
        if n < 2:
            interarrival_rows.append({
                "event_id": int(ev_id),
                "event_name": meta_stats.loc[ev_id, "event_name"],
                "num_appearances": int(n),
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
                "event_id": int(ev_id),
                "event_name": meta_stats.loc[ev_id, "event_name"],
                "num_appearances": int(n),
                "num_intervals": 0,
                "mean_interarrival": None,
                "std_interarrival": None,
                "min_interarrival": None,
                "max_interarrival": None,
            })
            continue
        interarrival_rows.append({
            "event_id": int(ev_id),
            "event_name": meta_stats.loc[ev_id, "event_name"],
            "num_appearances": int(n),
            "num_intervals": int(len(deltas)),
            "mean_interarrival": float(np.mean(deltas)),
            "std_interarrival": float(np.std(deltas)),
            "min_interarrival": float(np.min(deltas)),
            "max_interarrival": float(np.max(deltas)),
        })
    df_interarrival_stats = (
        pd.DataFrame(interarrival_rows)
        .sort_values("event_id")
        .reset_index(drop=True)
        if interarrival_rows else
        pd.DataFrame(columns=[
            "event_id","event_name","num_appearances","num_intervals",
            "mean_interarrival","std_interarrival","min_interarrival","max_interarrival"
        ])
    )

    # ============================================================
    # 7. Preprocesado dt_steps y jump_types por medida (para gráficos rápidos)
    # ============================================================
    precomputed_dt_jumps_by_measure = {}
    for measure in meta_stats["measure"].dropna().unique():
        dt_steps, jump_types = _precompute_dt_and_jumps(df_long, meta_stats, measure)
        precomputed_dt_jumps_by_measure[measure] = {"dt_steps": dt_steps, "jump_types": jump_types}

    return (
        meta_stats,
        events_by_measure_jump,
        ids_by_measure,
        df_interarrival_stats,
        dt_summary_transitions,
        precomputed_dt_jumps_by_measure
    )

#############################################################################################################################################
#--------------------------------------------------------------------------------------------------------------------------------------------
# Helpers para informe html
#--------------------------------------------------------------------------------------------------------------------------------------------
#############################################################################################################################################


def _events_by_measure_block(meta_stats: pd.DataFrame) -> str:
    df_events_long_sorted = (
        meta_stats.reset_index()[["measure", "event_id", "event_name", "count"]]
        .dropna(subset=["measure"])
        .query("count > 0")
        .sort_values(["measure", "count", "event_name"], ascending=[True, False, True])
        .reset_index(drop=True)
    )
    if df_events_long_sorted.empty:
        return section("Eventos por medida (total + desglose)") + para(
            "No hay eventos para mostrar por medida.", cls="small"
        )

    df_measure_totals = (
        df_events_long_sorted.groupby("measure", as_index=False)["count"]
        .sum()
        .rename(columns={"count": "total"})
    )

    parts = [
        section(
            "Eventos por medida (total + desglose)",
            intro="Cada tarjeta muestra el total de eventos de una medida y, debajo, el recuento por tipo de evento.",
        ),
        "<div class='events-grid'>",
    ]

    for measure in sorted(
        df_events_long_sorted["measure"].unique(),
        key=lambda m: len(df_events_long_sorted[df_events_long_sorted["measure"] == m]),
        reverse=True,
    ):
        total = int(df_measure_totals.loc[df_measure_totals["measure"] == measure, "total"].values[0])
        table_html = (
            df_events_long_sorted[df_events_long_sorted["measure"] == measure][["event_name", "count"]]
            .to_html(index=False, escape=False)
        )
        n_types = int((df_events_long_sorted["measure"] == measure).sum())
        parts.append(events_card(measure, total, table_html, n_types))

    parts.append("</div>")
    return "\n".join(parts)



#############################################################################################################################################
#--------------------------------------------------------------------------------------------------------------------------------------------
#  Generación del informe HTML final
#--------------------------------------------------------------------------------------------------------------------------------------------
#############################################################################################################################################

def generate_figures_and_report(
    *,
    ctx: dict,
    event_to_id: dict[str, int],
    df_events: pd.DataFrame,
) -> None:
    print("[prepareeventsds] Generando informe HTML final...")

    vp = ctx.get("variant_params", {})
    variant = ctx.get("variant", "N/A")
    event_strategy = str(vp.get("event_strategy", "both")).lower()

    (
        meta_stats,
        events_by_measure_jump,
        ids_by_measure,
        df_interarrival_stats,
        dt_summary_transitions,
        precomputed_dt_jumps_by_measure,
    ) = prepare_dataset_events_analysis(
        event_to_id,
        df_events,
        strategy=vp.get("event_strategy", "both"),
    )

    report_path = ctx["outputs"]["report"]

    rep = HtmlReport(
        title=f"PrepareEventsDS Report — Variante {variant}",
        ctx=ctx,
    ).start()

    # ============================================================
    # Estadísticas globales
    # ============================================================
    total_events = int(meta_stats["count"].sum())
    n_epochs = int(len(df_events))
    n_event_types = int((meta_stats["count"] > 0).sum())
    avg_events_per_epoch = (total_events / n_epochs) if n_epochs > 0 else 0.0

    if "events" in df_events.columns:
        epochs_with_events = int((df_events["events"].apply(len) > 0).sum())
    else:
        epochs_with_events = None

    cards = [
        kpi_card("Instantes temporales", f"{n_epochs:,}", "Filas del dataset, cada una asociada a un timestamp."),
        kpi_card("Eventos totales", f"{total_events:,}", "Número total de apariciones de eventos."),
        kpi_card("Tipos de evento", f"{n_event_types:,}", "Tipos distintos con al menos una aparición."),
        kpi_card("Media eventos / fila", f"{avg_events_per_epoch:.3f}", "Promedio de eventos por instante temporal."),
    ]
    cards.append(
        kpi_card(
            "Instantes con eventos",
            "—" if epochs_with_events is None else f"{epochs_with_events:,}",
            "No disponible en este formato de datos." if epochs_with_events is None else
            "Instantes temporales con al menos un evento.",
            muted=(epochs_with_events is None),
        )
    )

    rep.add(section("Estadísticas globales"))
    rep.add(kpi_grid(cards))
    rep.hr()

    # ============================================================
    # Eventos por medida
    # ============================================================
    rep.add(_events_by_measure_block(meta_stats))
    rep.hr()

    # ============================================================
    # Figuras de niveles
    # ============================================================
    if event_strategy in ("levels", "both") and not df_events.empty:
        rep.add(section("Figuras de niveles"))

        levels_by_measure = (
            meta_stats[meta_stats["prev_to_new"].isna() & meta_stats["measure"].notna()]
            .assign(level_state=lambda df: df["event_name"].str.extract(r"_(\d+_\d+)$"))
            [["measure", "level_state", "count"]]
            .reset_index(drop=True)
        )

        saved_levels_general = figures.plot_general_levels_eda_reports(
            levels_by_measure=levels_by_measure,
            reports_path=ctx["figures_dir"],
        )
        if saved_levels_general:
            rep.add(figures_grid(saved_levels_general, cols=2, max_width="100%"))

        measures_levels = levels_by_measure["measure"].dropna().unique().tolist()

        for measure in measures_levels:
            rep.add(subsection(measure, center=True))
            fig_by_measure = figures.plot_measure_levels_eda_reports(
                levels_by_measure=levels_by_measure,
                reports_path=ctx["figures_dir"],
                measure=measure,
            )
            rep.add(figures_grid(fig_by_measure, cols=2, max_width="100%"))
            

    # ============================================================
    # Figuras de transiciones
    # ============================================================
    if event_strategy in ("transitions", "both") and not events_by_measure_jump.empty:
        rep.add(section("Figuras de transiciones"))

        general_transition_figures = figures.plot_general_events_eda_reports(
            dt_summary=dt_summary_transitions,
            reports_path=ctx["figures_dir"],
        )
        rep.add(subsection("Transiciones generales", center=True))
        if general_transition_figures:
            rep.add(figures_grid(general_transition_figures, cols=2, max_width="100%"))

        measures_with_transitions = (
            events_by_measure_jump[events_by_measure_jump["prev_to_new"].notna()]
            ["measure"].dropna().unique().tolist()
        )

        for measure in measures_with_transitions:
            rep.add(subsection(measure, center=True))
            fig_by_measure = figures.plot_measure_events_eda_reports(
            events_by_measure_jump=events_by_measure_jump,
            dt_summary=dt_summary_transitions,
            reports_path=ctx["figures_dir"],
            measure=measure,
            precomputed_dt_jumps_by_measure=precomputed_dt_jumps_by_measure,
            )
            rep.add(figures_grid(fig_by_measure, cols=2, max_width="100%"))

        rep.hr()

    # ============================================================
    # Interarrival por evento
    # ============================================================
    rep.add(section("Estadísticas interarrival por evento"))
    rep.add(table_card(
        df_interarrival_stats,
        title=None,
        index=False,
    ))

    rep.write(report_path)
    print(f"[OK] Informe HTML generado en {report_path}")





