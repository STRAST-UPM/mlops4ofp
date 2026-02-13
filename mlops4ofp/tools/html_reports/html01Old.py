import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import re

import mlops4ofp.tools.figures.figures01 as explore_figures
from mlops4ofp.tools.html_reports.html import (
    HtmlReport,
    close_div,
    kpi_card,
    kpi_grid,
    open_grid,
    section,
    subsection,
    para,
    card,
    table_card,
    figures_grid,
    render_figure_card,
    smart_fmt,
)

from mlops4ofp.tools.figures.figures_general import save_figure


#############################################################################################################################################
# -------------------------------------------------------------------------------------------------------------------------------------------
# Procesado del dataset para el informe
#--------------------------------------------------------------------------------------------------------------------------------------------
#############################################################################################################################################

DEFAULT_EXCLUDE = {"segs", "segs_diff", "segs_dt", "Timestamp"}

def _pretty_suspect_key(k: str) -> str:
    """
    Convierte keys tipo:
      - 'nan_value_-999999.0'   -> 'Suspect: NaN-coded (-999999.0)'
      - 'error_value_123'       -> 'Suspect: Error-coded (123)'
    Si no matchea, lo deja en 'Suspect: <k>'.
    """
    m = re.match(r"^(nan_value|error_value)_(.+)$", k)
    if not m:
        return f"Suspect: {k}"
    kind, value = m.group(1), m.group(2)
    if kind == "nan_value":
        return f"Suspect: NaN-coded ({value})"
    return f"Suspect: Error-coded ({value})"


def quality_summary_table(stats: dict) -> pd.DataFrame:
    nulls = stats.get("nulls", {}) or {}
    outliers = stats.get("outliers_IQR", {}) or {}
    suspect = stats.get("suspect_values", {}) or {}

    # 1) detectar tipos de sospechosos
    suspect_types = set()
    for _, d in suspect.items():
        if isinstance(d, dict):
            suspect_types.update(d.keys())

    # Mapa: key original -> nombre bonito
    suspect_colname = {k: _pretty_suspect_key(k) for k in sorted(suspect_types)}

    # 2) construir filas
    rows = []
    all_cols = sorted(set(nulls) | set(outliers) | set(suspect))
    for col in all_cols:
        row = {
            "Column": col,
            "Null count (NaN)": int(nulls.get(col, 0) or 0),
            "Outlier count (IQR, 1.5×IQR)": int(outliers.get(col, 0) or 0),
        }

        d = suspect.get(col, {}) or {}
        for raw_key, pretty_name in suspect_colname.items():
            row[pretty_name] = int(d.get(raw_key, 0) or 0)

        rows.append(row)

    df = pd.DataFrame(rows).set_index("Column")

    # 3) ordenar por “más problemáticas”
    sort_cols = ["Null count (NaN)", "Outlier count (IQR, 1.5×IQR)"] + list(suspect_colname.values())
    df = df.sort_values(sort_cols, ascending=False).reset_index()

    return df



#############################################################################################################################################
#--------------------------------------------------------------------------------------------------------------------------------------------
#  Generación del informe HTML final
#--------------------------------------------------------------------------------------------------------------------------------------------
#############################################################################################################################################

def generate_figures_and_report(
    *,
    variant: str,
    ctx: dict,
    df_out: pd.DataFrame,
    numeric_cols: list[str],
    Tu_value: float,
    report_preclean: dict | None = None,
) -> None:
    print("[explore] Generando informe HTML final...")

    figures_dir: Path = ctx["figures_dir"]
    figures_dir.mkdir(parents=True, exist_ok=True)

    report_path = ctx["outputs"]["report"]

    rep = HtmlReport(
        title=f"Exploration Report — Variante {variant}",
        ctx=ctx,
    ).start()

    # ------------------------------------------------------------
    # Estadísticas básicas
    # ------------------------------------------------------------
    cards = [
        kpi_card("Time Unit (Tu)", f"{Tu_value:.3f}", "Tiempo de muestreo"),
        kpi_card("Filas", f"{len(df_out):,}", "Número de instantes temporales registrados"),
        kpi_card("Columnas", f"{df_out.shape[1]:,}", "Número de medidas/sensores registrados"),
    ]

    rep.add("<h2>Estadísticas básicas</h2>")
    rep.add(kpi_grid(cards))
    rep.hr()
    

    # ------------------------------------------------------------
    # Informe pre-limpieza
    # ------------------------------------------------------------
    if report_preclean is not None:
        rep.add(section(
            "Informe pre-limpieza",
            intro="Análisis de calidad del dato (nulos, outliers y valores sospechosos) antes de aplicar transformaciones o limpieza."
        ))

        df_q = quality_summary_table(report_preclean)
        rep.add(table_card(df_q, title="Nulls / Outliers (IQR) / Suspect values", index=False))


    # ------------------------------------------------------------
    # Calidad: NaNs por columna + celdas malas
    # ------------------------------------------------------------
    rep.add(section(
        "Calidad de datos — Nulos por columna",
        intro="Cuantifica NaNs por variable para detectar sensores/medidas incompletas o fallos sistemáticos."
    ))

    bad_per_row, bad_per_col, bad_summary = explore_figures.compute_bad_cells_stats(
        df_out, exclude_cols=["segs", "segs_diff"]
    )

    if bad_per_row is None and bad_per_col is None:
        rep.add(para("No se han detectado celdas malas (NaN) en columnas numéricas."))
    else:
        rep.add(para(
            f"<b>Filas con algún NaN:</b> {bad_summary['rows_with_bad']}<br>"
            f"<b>Total de NaNs:</b> {bad_summary['total_bad']}<br>"
            f"<b>Máximo NaNs en la misma fila:</b> {bad_summary['max_bad_in_row']}<br>"
        ))

        fig_bad_col = figures_dir / "bad_cells_per_column.png"
        save_figure(
            fig_bad_col,
            plot_fn=lambda: explore_figures.plot_bad_cells_per_column_bar(bad_per_col, top_n=18),
            figsize=(10, 6),
        )
        # figura dentro de una card
        rep.add(card(render_figure_card("NaNs por columna (top 18)", fig_bad_col.name, max_width="100%")))

    na_pct = df_out.drop(columns=["segs"], errors="ignore").isna().mean() * 100
    rep.add(table_card(
        na_pct.sort_values(ascending=False).to_frame("Porcentaje de nulos (%)").head(30),
        title="Top 30 columnas por porcentaje de NaN",
        index=True,
    ))

    # ------------------------------------------------------------
    # Intervalos con NaNs
    # ------------------------------------------------------------
    rep.hr()
    rep.add(section(
        "Calidad por intervalos — tramos con valores nulos",
        intro=("Se detectan tramos temporales consecutivos con NaNs en columnas numéricas. "
              "Permite diferenciar fallos puntuales vs sostenidos.")
    ))

    intervals_df, intervals_summary = explore_figures.compute_bad_intervals(
        df_out, period=Tu_value, time_col="segs"
    )
    if intervals_df is None:
        rep.add(para("No se han detectado intervalos con NaNs en columnas numéricas."))
    else:
        rep.add(card(
            f"<b>Periodo usado:</b> {intervals_summary['period_seconds']:.3f} s<br>"
            f"<b>Nº de intervalos:</b> {intervals_summary['n_intervals']}<br>"
            f"<b>Filas con al menos un NaN:</b> {intervals_summary['missing_rows']}<br>"
            f"<b>Duración máxima:</b> {intervals_summary['max_interval_seconds']:.1f} s"
        ))

        rep.add(table_card(intervals_df.head(10), title="Detalle (10 primeros intervalos)", index=False))

        fig_int_1 = figures_dir / "bad_intervals_duration_hist.png"
        save_figure(
            fig_int_1,
            plot_fn=lambda: explore_figures.plot_bad_intervals_duration_hist(intervals_df),
            figsize=(12, 5),
        )

        fig_int_2 = figures_dir / "bad_intervals_scatter.png"
        save_figure(
            fig_int_2,
            plot_fn=lambda: explore_figures.plot_bad_intervals_scatter(intervals_df),
            figsize=(12, 5),
        )

        rep.add(open_grid(cols=2, gap_rem=1.0))
        rep.add(render_figure_card(
            "Histograma de duración de intervalos con NaNs",
            fig_int_1.name,
            max_width="100%",
        ))
        rep.add(render_figure_card(
            "Scatter: duración vs severidad",
            fig_int_2.name,
            max_width="100%",
        ))
        rep.add(close_div())


        rep.add(para(
            "<b>Cómo interpretar el scatter:</b> "
            "X = duración del intervalo (más a la derecha, fallo más largo). "
            "Y = severidad (más arriba, más NaNs/columnas afectadas).",
            cls="small",
        ))

    # ------------------------------------------------------------
    # Huecos temporales
    # ------------------------------------------------------------
    rep.add(section(
        "Huecos temporales",
        intro=("Se analizan saltos anómalos en la columna temporal para detectar interrupciones "
              "en el muestreo (ausencia de registros durante intervalos mayores que Tu).")
    ))

    gaps_df, gaps_summary = explore_figures.compute_time_gaps(
        df_out, time_col="segs", expected_period=Tu_value
    )

    if gaps_df is None:
        rep.add(card(para("No se han detectado huecos temporales (o no hay datos suficientes).")))
    else:
        rep.add(card(
            f"<b>Periodo típico:</b> {gaps_summary['expected_period_seconds']:.3f} s<br>"
            f"<b>Nº de huecos:</b> {gaps_summary['n_gaps']}<br>"
            f"<b>Muestras faltantes:</b> {gaps_summary['missing_samples_total']}<br>"
            f"<b>Hueco máximo:</b> {gaps_summary['max_gap_seconds']:.1f} s"
        ))
        rep.add(table_card(gaps_df.head(50), title="Detalle de huecos (top 50)", index=False))

    # ------------------------------------------------------------
    # Estadísticos básicos + media por variable
    # ------------------------------------------------------------
    rep.hr()
    rep.add(section(
        "Estadísticos básicos",
        intro=("Resumen estadístico por variable: media, desviación típica, percentiles y extremos. "
              "Útil para detectar escalas incoherentes, outliers y variables casi constantes.")
    ))

    desc = df_out.drop(columns=["segs"], errors="ignore").describe().T
    desc_fmt = desc.map(smart_fmt)

    fig_mean = figures_dir / "mean_by_variable.png"
    save_figure(
        fig_mean,
        plot_fn=lambda: (
            desc["mean"].plot(kind="barh", title="Media por variable numérica"),
            plt.xlabel("Media"),
            plt.ylabel("Variable"),
            plt.tight_layout(),
        ),
        figsize=(12, 8),
    )

    rep.add(card(render_figure_card("Media por variable numérica", fig_mean.name, max_width="100%")))
    rep.add(table_card(desc_fmt, title="Tabla de estadísticos (formateada)", index=True))

    # ------------------------------------------------------------
    # Distribución porcentual
    # ------------------------------------------------------------
    rep.add(section(
        "Distribución porcentual (min–max por variable)",
        intro=("Muestra, para cada variable, en qué porcentaje de su rango total (0% = mínimo, 100% = máximo) "
              "se concentran sus valores.")
    ))

    dist = explore_figures.compute_percentage_distribution(
        df_out, exclude_cols=["segs_diff", "segs", "segs_dt", "Timestamp"]
    )

    fig_dist = figures_dir / "percentage_distribution.png"
    save_figure(
        fig_dist,
        plot_fn=lambda: explore_figures.plot_percentage_distribution(dist),
        figsize=(12, max(4, 0.4 * (len(dist) if dist is not None else 5))),
    )
    rep.add(card(render_figure_card("Distribución porcentual (min–max)", fig_dist.name, max_width="100%")))

    # ------------------------------------------------------------
    # Correlación
    # ------------------------------------------------------------
    rep.hr()
    rep.add(section(
        "Relación entre variables — Matriz de correlación",
        intro=("Correlación lineal entre variables numéricas. "
              "Cerca de 1: relación positiva fuerte. Cerca de −1: negativa fuerte. Cerca de 0: sin relación lineal.")
    ))

    corr_path = figures_dir / "corr_heatmap.png"
    save_figure(
        corr_path,
        plot_fn=lambda: explore_figures.plot_correlation_heatmap(
            df_out.drop(columns=["segs"], errors="ignore").corr()
        ),
        figsize=(12, 10),
    )
    rep.add(card(render_figure_card("Heatmap de correlación", corr_path.name, max_width="100%")))

    # ------------------------------------------------------------
    # Figuras por medida (summary)
    # ------------------------------------------------------------
    rep.hr()
    rep.add(section("Análisis detallado por medida"))

    measure_cols = [c for c in df_out.columns if c not in ["segs", "segs_diff", "segs_dt", "Timestamp"]]

    for measure in measure_cols:
        rep.add(subsection(measure, center=True))

        measure_figs = explore_figures.plot_measure_summary(
            df=df_out,
            measure=measure,
            output_dir=figures_dir,
            time_col="segs",
        )
        rep.add(figures_grid(measure_figs, cols=2, max_width="100%"))

    # ------------------------------------------------------------
    # Figuras extra (temperatura/voltaje/frecuencia/potencia)
    # ------------------------------------------------------------
    rep.hr()
    rep.add(section("Otras figuras"))

    extra_blocks = [
        ("Análisis de Temperaturas del Sistema de Agua", explore_figures.plot_temperature_eda_reports),
        ("Análisis de Voltajes", explore_figures.plot_voltage_eda_reports),
        ("Análisis de Frecuencias", explore_figures.plot_frequency_eda_reports),
        ("Análisis de Potencias del Sistema Eléctrico", explore_figures.plot_power_eda_reports),
    ]

    for title, fn in extra_blocks:
        rep.add(subsection(title))
        figs = fn(df=df_out, reports_path=figures_dir, time_col="segs")
        rep.add(figures_grid(figs, cols=2, max_width="100%"))

    rep.write(report_path)
    print(f"[OK] Informe HTML generado en {report_path}")
    print(f"[OK] Figuras generadas en: {figures_dir}")
