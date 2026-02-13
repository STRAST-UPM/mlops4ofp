from __future__ import annotations
from pathlib import Path
import matplotlib.pyplot as plt


# Standard library
from pathlib import Path
from tabnanny import verbose
from typing import Optional

# Third-party
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.dates import DateFormatter, HourLocator
import numpy as np
import pandas as pd
import seaborn as sns
from statsmodels.tsa.seasonal import seasonal_decompose
from matplotlib.patches import Patch
import matplotlib.colors as mcolors
from mlops4ofp.tools.figures.figures_general import save_fig, ensure_datetime_index_from_segs, season_from_month



# ============================================================================================================================================================
# ============================================================================================================================================================
# ============================================================================================================================================================
# 01 - FASE DE EXPLORACIÓN
# ============================================================================================================================================================
# ============================================================================================================================================================
# ============================================================================================================================================================

###########################
# Heatmap de correlación
#############################

def plot_correlation_heatmap(
    corr: pd.DataFrame,
    cmap: str = "coolwarm",
    fmt: str = ".2f",
    annot: bool = True,
    annot_kws: dict | None = None,
):
    """
    Dibuja un heatmap de correlación.
    """
    ax = plt.gca()

    if corr is None or corr.shape[0] == 0 or corr.shape[1] == 0:
        ax.text(0.5, 0.5, "No hay columnas numéricas para calcular la correlación.",
                ha="center", va="center")
        ax.axis("off")
        return

    annot_kws = annot_kws or {"size": 7}

    sns.heatmap(
        corr,
        ax=ax,
        annot=annot,  
        cmap=cmap,
        fmt=fmt,
        annot_kws=annot_kws,
        cbar_kws={"shrink": 0.8, "label": "Correlation"},
        linewidths=0.2,
        square=True,
    )

    plt.title("Matriz de correlación", fontsize=12, pad=12, fontweight="bold")
    # Mismo formateo de etiquetas que tu segunda función
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=8)



###########################
# Análisis de huecos temporales y datos malos
############################


######################################################################
#BAD CELLS
############################################################333



def plot_bad_intervals_duration_hist(intervals: pd.DataFrame) -> None:
    """
    Histograma de duraciones de intervalos con datos malos.
    Usa escala logarítmica para mejor visualización de rangos amplios.
    """
    ax = plt.gca()

    if intervals is None or intervals.empty:
        ax.text(0.5, 0.5, "No hay intervalos con datos malos", ha="center", va="center", fontsize=12)
        ax.axis("off")
        return

    durations = intervals["Duración"].dt.total_seconds().astype(float)

    if len(durations) == 0:
        ax.text(0.5, 0.5, "No hay datos de duración", ha="center", va="center", fontsize=12)
        ax.axis("off")
        return

    # Estadísticas para anotaciones
    median_dur = np.median(durations)
    mean_dur = np.mean(durations)
    max_dur = np.max(durations)

    # Bins logarítmicos para mejor distribución visual
    min_dur = max(durations.min(), 1)  # evitar log(0)
    log_bins = np.logspace(np.log10(min_dur), np.log10(max_dur * 1.1), 25)

    # Colores con degradado según frecuencia
    n, bins_edges, patches = ax.hist(durations, bins=log_bins, edgecolor="white", linewidth=0.8)
    
    # Aplicar colormap a las barras
    cmap = plt.get_cmap("YlOrRd")
    max_n = max(n) if max(n) > 0 else 1
    for count, patch in zip(n, patches):
        patch.set_facecolor(cmap(0.2 + 0.7 * count / max_n))

    ax.set_xscale("log")
    
    # Líneas de referencia para mediana y media
    ax.axvline(median_dur, color="#2563eb", linestyle="--", linewidth=2, label=f"Mediana: {median_dur:.1f}s")
    ax.axvline(mean_dur, color="#dc2626", linestyle=":", linewidth=2, label=f"Media: {mean_dur:.1f}s")

    ax.set_title("Distribución de duración de intervalos con datos malos", 
                 fontsize=13, fontweight="bold", pad=15)
    ax.set_xlabel("Duración del intervalo (segundos, escala log)", fontsize=11)
    ax.set_ylabel("Número de intervalos", fontsize=11)
    
    # Leyenda con estadísticas
    ax.legend(loc="upper right", fontsize=9, framealpha=0.9)
    
    # Añadir texto con resumen
    stats_text = f"Total: {len(durations)} intervalos\nMáx: {max_dur:.1f}s"
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, fontsize=9,
            verticalalignment="top", bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

    ax.grid(True, linestyle="--", alpha=0.4, which="both")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    
    plt.tight_layout()



def plot_bad_intervals_scatter(intervals: pd.DataFrame) -> None:
    """
    Scatter plot: tamaño de intervalo vs severidad (media de columnas malas).
    Visualización más intuitiva con etiquetas claras y leyenda explicativa.
    """
    ax = plt.gca()

    if intervals is None or intervals.empty:
        ax.text(0.5, 0.5, "No hay intervalos con datos malos", ha="center", va="center", fontsize=12)
        ax.axis("off")
        return

    x = intervals["Muestras"].astype(float)
    y = intervals["Media_columnas_malas"].astype(float)

    if len(x) == 0:
        ax.text(0.5, 0.5, "No hay datos de intervalos", ha="center", va="center", fontsize=12)
        ax.axis("off")
        return

    # Clasificar intervalos por gravedad para colores más intuitivos
    # Verde = leve, Amarillo = moderado, Rojo = grave
    severity_colors = []
    
    y_max = y.max() if y.max() > 0 else 1
    for sev in y:
        ratio = sev / y_max
        if ratio < 0.33:
            severity_colors.append("#4CAF50")  # Verde - leve
        elif ratio < 0.66:
            severity_colors.append("#FFC107")  # Amarillo - moderado
        else:
            severity_colors.append("#F44336")  # Rojo - grave

    # Tamaño fijo para mejor legibilidad
    ax.scatter(
        x, y,
        c=severity_colors,
        s=120,
        alpha=0.8,
        edgecolors="black",
        linewidths=1,
    )

    # Leyenda manual más clara - posicionada fuera del gráfico
    legend_elements = [
        Patch(facecolor="#4CAF50", edgecolor="black", label="Leve (pocas columnas afectadas)"),
        Patch(facecolor="#FFC107", edgecolor="black", label="Moderado"),
        Patch(facecolor="#F44336", edgecolor="black", label="Grave (muchas columnas afectadas)"),
    ]
    ax.legend(handles=legend_elements, loc="upper left", fontsize=9, title="Severidad",
              bbox_to_anchor=(1.02, 1), borderaxespad=0)

    ax.set_title("¿Dónde están los problemas de datos?", 
                 fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Cuántas muestras consecutivas tienen problemas", fontsize=11)
    ax.set_ylabel("Cuántas columnas están afectadas (promedio)", fontsize=11)
    ax.grid(True, linestyle="--", alpha=0.4)

    # Añadir zonas de interpretación con fondo suave
    ax.axhspan(0, y_max * 0.33, alpha=0.05, color="#4CAF50", zorder=0)
    ax.axhspan(y_max * 0.33, y_max * 0.66, alpha=0.05, color="#FFC107", zorder=0)
    ax.axhspan(y_max * 0.66, y_max * 1.1, alpha=0.05, color="#F44336", zorder=0)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    
    # Configurar y_ticks en unidades enteras o múltiplos de 2 como máximo
    y_lim_max = y_max * 1.15
    ax.set_ylim(0, y_lim_max)
    
    # Determinar el paso apropiado para los ticks (1 o 2)
    if y_lim_max <= 10:
        step = 1
    else:
        step = 2
    
    y_ticks = np.arange(0, int(np.ceil(y_lim_max)) + step, step)
    ax.set_yticks(y_ticks)

    plt.tight_layout()



def plot_bad_cells_per_column_bar(bad_per_col: pd.Series | None, top_n: int = 18) -> None:
    """
    Barras horizontales: top-N columnas con más NaNs.
    NO crea figura, NO guarda, NO cierra.
    """
    ax = plt.gca()

    if bad_per_col is None or bad_per_col.empty:
        ax.text(0.5, 0.5, "No se detectaron celdas malas (NaN) en columnas.", ha="center", va="center")
        ax.axis("off")
        return

    # Ordenar de mayor a menor y tomar top_n
    top_cols = bad_per_col.head(top_n).sort_values(ascending=True)
    
    # Colores con degradado (más oscuro = más NaNs)
    cmap = plt.get_cmap("Reds")
    norm_vals = (top_cols.values - top_cols.min()) / (top_cols.max() - top_cols.min() + 1e-9)
    colors = [cmap(0.3 + 0.6 * v) for v in norm_vals]  # rango 0.3-0.9 del cmap
    
    bars = ax.barh(top_cols.index, top_cols.values, color=colors, edgecolor="darkred", linewidth=0.5)
    
    # Anotar valores al final de cada barra
    max_val = top_cols.max()
    for bar, val in zip(bars, top_cols.values):
        ax.text(
            val + max_val * 0.02,
            bar.get_y() + bar.get_height() / 2,
            f"{int(val):,}",
            va="center",
            ha="left",
            fontsize=9,
            fontweight="bold",
            color="#333333",
        )
    
    ax.set_title("Top columnas con mayor incidencia de valores perdidos (NaN)", 
                 fontsize=12, fontweight="bold", pad=10)
    ax.set_ylabel("Columna", fontsize=10)
    ax.set_xlabel("Número de valores perdidos (NaN)", fontsize=10)
    
    # Ampliar límite x para que quepan las anotaciones
    ax.set_xlim(0, max_val * 1.15)
    
    # Mejorar etiquetas del eje Y (nombres de columnas más legibles)
    # Fijar primero los ticks para evitar el warning de Matplotlib
    ax.set_yticks(np.arange(len(top_cols.index)))
    ax.set_yticklabels([str(name).replace("_", " ") for name in top_cols.index], fontsize=9)
    
    ax.grid(axis="x", alpha=0.3, linestyle="--")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    
    plt.tight_layout()




###########################################
#
###############################################

def plot_percentage_distribution(
    dist: pd.DataFrame | None,
    cmap: str | mcolors.Colormap = "YlGnBu",
    title: str = "Distribución porcentual de muestras por columna (%)",
    text_threshold: float = 0.5,
) -> None:
    """
    Dibuja un mapa de calor (heatmap) con la distribución porcentual.
    El color del texto se adapta automáticamente al fondo.

    Parámetros
    ----------
    text_threshold : float
        Umbral (0–1) a partir del cual el fondo se considera oscuro.
    """
    ax = plt.gca()

    if dist is None or dist.empty:
        ax.text(0.5, 0.5, "No hay columnas numéricas suficientes",
                ha="center", va="center")
        ax.axis("off")
        return

    dist_plot = dist.apply(pd.to_numeric, errors="coerce")

    # Normalización global para el colormap
    vmin = float(np.nanmin(dist_plot.values))
    vmax = float(np.nanmax(dist_plot.values))
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    cmap_obj = plt.get_cmap(cmap)

    mesh = ax.pcolormesh(dist_plot.values, cmap=cmap_obj, norm=norm, shading="auto")
    cbar = plt.colorbar(mesh, ax=ax)
    cbar.set_label("% de muestras")

    ax.set_xticks(np.arange(dist_plot.shape[1]) + 0.5)
    ax.set_xticklabels(dist_plot.columns, rotation=45, ha="right")
    ax.set_yticks(np.arange(dist_plot.shape[0]) + 0.5)
    ax.set_yticklabels(dist_plot.index)

    ax.set_title(title)

    # Texto adaptativo
    if len(dist_plot) <= 40:
        for i in range(dist_plot.shape[0]):
            for j in range(dist_plot.shape[1]):
                val = dist_plot.iat[i, j]
                if pd.notna(val):
                    # Normalizar valor para decidir color del texto
                    val_norm = norm(val)
                    text_color = "white" if val_norm > text_threshold else "black"

                    ax.text(
                        j + 0.5,
                        i + 0.5,
                        f"{val:.1f}",
                        ha="center",
                        va="center",
                        fontsize=8,
                        color=text_color,
                    )

    plt.tight_layout()




##################################################################
# GRAFICAS PERSONALIZADAS A CADA MEDIDA
#################################################################


# ============================================================
# 1) Día representativo — varias medidas (una sola figura)
# ============================================================

def plot_representative_day_multi(
    df: pd.DataFrame,
    measures: list[str],
    day_start: pd.Timestamp,
    day_end: pd.Timestamp,
    time_col: str = "segs",
    tz: str = "Europe/Madrid",
    title: str | None = None,
) -> None:
    ax = plt.gca()
    df_dt = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)

    missing = [c for c in measures if c not in df_dt.columns]
    if missing:
        raise ValueError(f"Medidas no encontradas: {missing}")

    day_df = (
        df_dt.loc[day_start:day_end, measures]
        .apply(pd.to_numeric, errors="coerce")
        .dropna(how="all")
    )

    if day_df.empty:
        ax.text(0.5, 0.5, "Aviso: no hay datos para el día representativo indicado.", ha="center", va="center")
        ax.axis("off")
        return

    # Colores bonitos consistentes
    colors = plt.get_cmap("tab10").colors

    for i, col in enumerate(measures):
        s = day_df[col].dropna()
        if not s.empty:
            ax.plot(
                s.index,
                s.values,
                linewidth=2.2,
                color=colors[i % len(colors)],
                label=col,
            )

    ax.set_title(title or "Día representativo (varias medidas)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Hora del día")
    ax.set_ylabel("Valor")
    ax.grid(True, alpha=0.3)

    ax.xaxis.set_major_locator(HourLocator(interval=2))
    ax.xaxis.set_major_formatter(DateFormatter("%H:%M"))

    ax.legend()
    plt.tight_layout()


# ============================================================
# 2) Media mensual — una sola medida (una figura)
# ============================================================

def plot_monthly_mean_single(
    df: pd.DataFrame,
    measure: str,
    time_col: str = "segs",
    tz: str = "Europe/Madrid",
    title: str | None = None,
) -> None:
    ax = plt.gca()
    df_dt = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)

    if measure not in df_dt.columns:
        raise ValueError(f"Columna no encontrada: {measure}")

    s = pd.to_numeric(df_dt[measure], errors="coerce")
    monthly_avg = s.groupby(s.index.month).mean()

    if monthly_avg.empty or monthly_avg.dropna().empty:
        ax.text(0.5, 0.5, "No hay datos para calcular la media mensual.", ha="center", va="center")
        ax.axis("off")
        return

    months = monthly_avg.index.astype(int)
    values = monthly_avg.values

    colors = plt.cm.Spectral(np.linspace(0, 1, 12))
    colors = colors[months - 1]

    ax.bar(months, values, color=colors)

    ax.set_title(title or f"Media mensual — {measure}", fontsize=14, fontweight="bold")
    ax.set_xlabel("Mes")
    ax.set_ylabel("Media")

    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"])

    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()


# ============================================================
# 3) Patrón horario por estación — una sola medida (una figura)
# ============================================================

def plot_hourly_by_season_single(
    df: pd.DataFrame,
    measure: str,
    time_col: str = "segs",
    tz: str = "Europe/Madrid",
    title: str | None = None,
) -> None:
    ax = plt.gca()
    df_dt = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)

    if measure not in df_dt.columns:
        raise ValueError(f"Columna no encontrada: {measure}")

    s = pd.to_numeric(df_dt[measure], errors="coerce")

    tmp = pd.DataFrame(
        {"value": s, "month": s.index.month, "hour": s.index.hour}
    )
    tmp["season"] = tmp["month"].apply(season_from_month)

    seasonal_pattern = tmp.groupby(["season", "hour"], as_index=False)["value"].mean()

    if seasonal_pattern.empty or seasonal_pattern["value"].dropna().empty:
        ax.text(0.5, 0.5, "No hay datos para patrón por estación.", ha="center", va="center")
        ax.axis("off")
        return

    order = ["Invierno", "Primavera", "Verano", "Otoño"]

    # Colores bonitos fijos por estación (coolwarm)
    season_colors_list = plt.get_cmap("coolwarm")(np.linspace(0.1, 0.9, 4))
    season_colors = dict(zip(order, season_colors_list))

    for season in order:
        block = seasonal_pattern[seasonal_pattern["season"] == season].sort_values("hour")
        if not block.empty:
            ax.plot(
                block["hour"],
                block["value"],
                linewidth=2.2,
                color=season_colors[season],
                label=season,
            )

    ax.set_title(title or f"Patrón horario medio por estación — {measure}", fontsize=14, fontweight="bold")
    ax.set_xlabel("Hora del día")
    ax.set_ylabel("Valor medio")
    ax.grid(True, alpha=0.3)
    ax.set_xticks(range(0, 24, 2))

    ax.legend()
    plt.tight_layout()


#############################
# PV EDA
###############################

def compute_pv_eda_data(
    df: pd.DataFrame,
    pv_cols: list[str],
    time_col: str = "segs",
    tz: str = "Europe/Madrid",
) -> dict:
    """
    Prepara datos EDA para varias columnas PV.
    Devuelve un dict con:
      - df_dt: df con índice datetime
      - monthly_mean[col]: Series (mes->media)
      - seasonal_hourly[col]: DataFrame con columns season,hour,value
    """
    df_dt = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)

    # Validar columnas
    missing = [c for c in pv_cols if c not in df_dt.columns]
    if missing:
        raise ValueError(f"Columnas PV no encontradas: {missing}")

    month = df_dt.index.month
    hour = df_dt.index.hour
    season = pd.Series(month, index=df_dt.index).apply(season_from_month)

    monthly_mean = {}
    seasonal_hourly = {}

    for col in pv_cols:
        s = pd.to_numeric(df_dt[col], errors="coerce")

        monthly_mean[col] = s.groupby(month).mean()

        tmp = pd.DataFrame({"season": season, "hour": hour, "value": s})
        seasonal_hourly[col] = tmp.groupby(["season", "hour"], as_index=False)["value"].mean()

    return {
        "df_dt": df_dt,
        "monthly_mean": monthly_mean,
        "seasonal_hourly": seasonal_hourly,
    }


def plot_chilled_water_temperatures(
    df: pd.DataFrame,
    measures: list[str] | None = None,
    time_col: str = "segs",
    tz: str = "Europe/Madrid",
) -> None:
    """
    Genera gráficas EDA centradas en las temperaturas Inlet/Outlet
    del sistema de agua helada.
    
    Esta función dibuja en el eje actual (plt.gca()), NO crea figura,
    NO guarda, NO cierra.
    """
    ax = plt.gca()
    
    # Columnas por defecto
    t_in = "Inlet_Temperature_of_Chilled_Water"
    t_out = "Outlet_Temperature"
    
    if measures is not None and len(measures) >= 2:
        t_in, t_out = measures[0], measures[1]

    # Comprobar columnas
    for col in (t_in, t_out):
        if col not in df.columns:
            ax.text(0.5, 0.5, f"Columna no encontrada: {col}", ha="center", va="center")
            ax.axis("off")
            return

    # Asegurar índice datetime
    df_dt = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)

    # Promedio horario
    hourly_pattern = df_dt[[t_in, t_out]].groupby(df_dt.index.hour).mean()

    
    if hourly_pattern.empty or hourly_pattern.dropna().empty:
        ax.text(0.5, 0.5, "No hay datos suficientes para el patrón horario.", ha="center", va="center")
        ax.axis("off")
        return

    ax.plot(hourly_pattern.index, hourly_pattern[t_in], label="Entrada", color="#ff7f0e", linewidth=2.2)
    ax.plot(hourly_pattern.index, hourly_pattern[t_out], label="Salida", color="#1f77b4", linewidth=2.2, linestyle="--")
    ax.fill_between(hourly_pattern.index,
                    hourly_pattern[t_out], hourly_pattern[t_in],
                    color="#b0d0ff", alpha=0.3, label="Diferencia térmica")
    ax.set_title("Promedio horario – Temperaturas del sistema de agua helada", fontsize=14, fontweight="bold")
    ax.set_xlabel("Hora del día")
    ax.set_ylabel("Temperatura media [°C]")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()


def plot_chilled_water_day(
    df: pd.DataFrame,
    day_start: pd.Timestamp,
    day_end: pd.Timestamp,
    measures: list[str] | None = None,
    time_col: str = "segs",
    tz: str = "Europe/Madrid",
    title: str | None = None,
) -> None:
    """
    Gráfica de temperaturas Inlet/Outlet para un día representativo.
    Dibuja en el eje actual (plt.gca()).
    """
    ax = plt.gca()
    
    t_in = "Inlet_Temperature_of_Chilled_Water"
    t_out = "Outlet_Temperature"
    
    if measures is not None and len(measures) >= 2:
        t_in, t_out = measures[0], measures[1]

    for col in (t_in, t_out):
        if col not in df.columns:
            ax.text(0.5, 0.5, f"Columna no encontrada: {col}", ha="center", va="center")
            ax.axis("off")
            return

    df_dt = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)
    day_df = df_dt.loc[day_start:day_end, [t_in, t_out]].dropna(how="all")

    if day_df.empty:
        ax.text(0.5, 0.5, "No hay datos para el día representativo indicado.", ha="center", va="center")
        ax.axis("off")
        return

    ax.plot(day_df.index, day_df[t_in], label="Temperatura de entrada", color="#ff7f0e", linewidth=2.2)
    ax.plot(day_df.index, day_df[t_out], label="Temperatura de salida", color="#1f77b4", linewidth=2.2, linestyle="--")
    ax.set_title(title or "Temperaturas del sistema de agua helada – Día representativo", fontsize=14, fontweight="bold")
    ax.set_xlabel("Hora del día")
    ax.set_ylabel("Temperatura [°C]")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_locator(HourLocator(interval=2))
    ax.xaxis.set_major_formatter(DateFormatter("%H:%M"))
    plt.tight_layout()


def plot_chilled_water_monthly(
    df: pd.DataFrame,
    measures: list[str] | None = None,
    time_col: str = "segs",
    tz: str = "Europe/Madrid",
    title: str | None = None,
) -> None:
    """
    Gráfica de temperaturas promedio mensuales con barras de error (std).
    Dibuja en el eje actual (plt.gca()).
    """
    ax = plt.gca()
    
    t_in = "Inlet_Temperature_of_Chilled_Water"
    t_out = "Outlet_Temperature"
    
    if measures is not None and len(measures) >= 2:
        t_in, t_out = measures[0], measures[1]

    for col in (t_in, t_out):
        if col not in df.columns:
            ax.text(0.5, 0.5, f"Columna no encontrada: {col}", ha="center", va="center")
            ax.axis("off")
            return

    df_dt = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)
    #  groupby por month usando index.month
    g = df_dt[[t_in, t_out]].groupby(df_dt.index.month)
    mean = g.mean()
    std = g.std()

    if mean.empty or mean.dropna().empty:
        ax.text(0.5, 0.5, "No hay datos suficientes para promedios mensuales.", ha="center", va="center")
        ax.axis("off")
        return

    ax.errorbar(mean.index, mean[t_in], yerr=std[t_in], label="Entrada", fmt='-o', capsize=4)
    ax.errorbar(mean.index, mean[t_out], yerr=std[t_out], label="Salida", fmt='--o', capsize=4)

    ax.set_title(title or "Temperaturas promedio mensuales – Inlet/Outlet", fontsize=14, fontweight="bold")
    ax.set_xlabel("Mes")
    ax.set_ylabel("Temperatura [°C]")
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"])
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()


def plot_chilled_water_seasonal_hourly(
    df: pd.DataFrame,
    measures: list[str] | None = None,
    time_col: str = "segs",
    tz: str = "Europe/Madrid",
    title: str | None = None,
) -> None:
    """
    Gráfica de patrón horario por estación para temperaturas Inlet/Outlet.
    Dibuja en el eje actual (plt.gca()) - usa subplots internos.
    """
    t_in = "Inlet_Temperature_of_Chilled_Water"
    t_out = "Outlet_Temperature"
    
    if measures is not None and len(measures) >= 2:
        t_in, t_out = measures[0], measures[1]

    for col in (t_in, t_out):
        if col not in df.columns:
            ax = plt.gca()
            ax.text(0.5, 0.5, f"Columna no encontrada: {col}", ha="center", va="center")
            ax.axis("off")
            return

    df_dt = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)
    hour = df_dt.index.hour
    month = df_dt.index.month

    # ✅ season id 0..3 vectorizado
    season_id = np.empty(len(df_dt), dtype=np.int8)
    season_id[(month == 12) | (month <= 2)] = 0  # Invierno
    season_id[(3 <= month) & (month <= 5)] = 1   # Primavera
    season_id[(6 <= month) & (month <= 8)] = 2   # Verano
    season_id[(9 <= month) & (month <= 11)] = 3  # Otoño

    # ✅ groupby multiindex usando arrays (sin crear columnas)
    seasonal = df_dt[[t_in, t_out]].groupby([season_id, hour]).mean()

    if seasonal.empty:
        ax = plt.gca()
        ax.text(0.5, 0.5, "No hay datos suficientes para patrón estacional.", ha="center", va="center")
        ax.axis("off")
        return

    fig = plt.gcf()
    fig.clear()
    axes = fig.subplots(1, 4, sharey=True)

    labels = ["Invierno", "Primavera", "Verano", "Otoño"]

    for i, name in enumerate(labels):
        ax = axes[i]
        # extraer tabla (24 filas) para esa estación
        try:
            sub = seasonal.loc[i]
        except KeyError:
            ax.set_title(name, fontsize=13, fontweight="bold")
            ax.axis("off")
            continue

        # sub index = hour (0..23)
        ax.plot(sub.index, sub[t_in], label="Inlet", linewidth=2.0)
        ax.plot(sub.index, sub[t_out], label="Outlet", linewidth=2.0, linestyle="--")
        ax.set_title(name, fontsize=13, fontweight="bold")
        ax.set_xlabel("Hora del día")
        if i == 0:
            ax.set_ylabel("Temperatura media [°C]")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best", fontsize=9)

    fig.suptitle(title or "Patrón horario medio – Inlet vs Outlet por estación",
                 fontsize=15, fontweight="bold", y=1.02)
    plt.tight_layout()


def plot_temperature_eda_reports(
    df: pd.DataFrame,
    reports_path: Path,
    measures: list[str] | None = None,
    day_start: Optional[pd.Timestamp] = None,
    day_end: Optional[pd.Timestamp] = None,
    time_col: str = "segs",
    tz: str = "Europe/Madrid",
) -> list[tuple[str, Path]]:
    """
    Genera informes EDA centrados en las temperaturas del sistema de agua helada.
    Devuelve la lista de tuplas (título, path) de los ficheros guardados.

    Parámetros principales:
      df : DataFrame con índice datetime o columna 'Timestamp'
      measures : lista con nombres de columnas [Inlet, Outlet] (si None, se usan por defecto)
      day_start/day_end : Timestamps para el día representativo (si None, se usan los del ejemplo)
      time_col : nombre de la columna de tiempo (si no es el índice)
      tz : zona horaria para conversión datetime
      reports_path : carpeta para guardar las figuras (por defecto REPORTS_PATH)
    """
    saved: list[tuple[str, Path]] = []

    # Valores por defecto para el día representativo
    if day_start is None:
        day_start = pd.Timestamp("2022-12-10 06:00:00", tz=tz)
    elif day_start.tzinfo is None:
        day_start = day_start.tz_localize(tz)
    if day_end is None:
        day_end = pd.Timestamp("2022-12-10 20:59:59", tz=tz)
    elif day_end.tzinfo is None:
        day_end = day_end.tz_localize(tz)

    # 1) Promedio horario
    fig, _ = plt.subplots(figsize=(12, 5))
    plot_chilled_water_temperatures(df, measures=measures, time_col=time_col, tz=tz)
    path = save_fig(fig, reports_path, "chilled_water_hourly_mean.png")
    saved.append(("Promedio horario — Temperaturas del sistema de agua helada", path))

    # 2) Día representativo
    fig, _ = plt.subplots(figsize=(14, 5))
    plot_chilled_water_day(df, day_start, day_end, measures=measures, time_col=time_col, tz=tz)
    path = save_fig(fig, reports_path, "chilled_water_representative_day.png")
    saved.append(("Día representativo — Temperaturas del sistema de agua helada", path))

    # 3) Media mensual
    fig, _ = plt.subplots(figsize=(12, 5))
    plot_chilled_water_monthly(df, measures=measures, time_col=time_col, tz=tz)
    path = save_fig(fig, reports_path, "chilled_water_monthly_mean.png")
    saved.append(("Media mensual — Temperaturas Inlet/Outlet", path))

    # 4) Patrón horario por estación
    fig = plt.figure(figsize=(16, 5))
    plot_chilled_water_seasonal_hourly(df, measures=measures, time_col=time_col, tz=tz)
    path = save_fig(fig, reports_path, "chilled_water_seasonal_hourly.png")
    saved.append(("Patrón horario por estación — Inlet vs Outlet", path))

    return saved





def plot_synchronized_frequency_decomposition(
    df: pd.DataFrame,
    f_mg: str = "MG-LV-MSB_Frequency",
    f_isl: str = "Island_mode_MCCB_Frequency",
    resample_rule: str = "h",
    seasonal_period: int = 24,
    min_samples: int = 48,
    time_col: str = "segs",
    tz: str = "Europe/Madrid",
) -> None:
    """
    Realiza la descomposición estacional sincronizada de las series de
    frecuencia MG vs Island (promediadas por resample_rule).
    
    Dibuja en la figura actual (plt.gcf()), NO crea figura, NO guarda, NO cierra.
    """
    fig = plt.gcf()
    fig.clear()
    
    # Asegurar índice datetime
    df_local = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)

    # Comprobar columnas
    for col in (f_mg, f_isl):
        if col not in df_local.columns:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, f"Columna no encontrada: {col}", ha="center", va="center")
            ax.axis("off")
            return

    # Series por hora (o según resample_rule)
    mg_series = df_local[f_mg].dropna().resample(resample_rule).mean()
    isl_series = df_local[f_isl].dropna().resample(resample_rule).mean()

    # Rellenar huecos simples con la media
    if mg_series.empty or isl_series.empty:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "Una de las series está vacía tras el resample.", ha="center", va="center")
        ax.axis("off")
        return
        
    mg_series = mg_series.fillna(mg_series.mean())
    isl_series = isl_series.fillna(isl_series.mean())

    if (mg_series.dropna().size < min_samples) or (isl_series.dropna().size < min_samples):
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, f"No hay suficientes datos (se requieren ≥ {min_samples} muestras).", ha="center", va="center")
        ax.axis("off")
        return

    dec_mg = seasonal_decompose(mg_series, model="additive", period=seasonal_period)
    dec_isl = seasonal_decompose(isl_series, model="additive", period=seasonal_period)

    COLOR_MG, COLOR_ISL, LINEWIDTH = "#2a6fdb", "#f38b00", 1.2

    gs = gridspec.GridSpec(3, 2, wspace=0.12, hspace=0.35)
    titles = ["Observed", "Trend", "Seasonal"]

    for i, comp in enumerate(titles):
        ax_mg = fig.add_subplot(gs[i, 0])
        ax_isl = fig.add_subplot(gs[i, 1], sharex=ax_mg, sharey=ax_mg)

        getattr(dec_mg, comp.lower()).plot(ax=ax_mg, color=COLOR_MG, lw=LINEWIDTH)
        getattr(dec_isl, comp.lower()).plot(ax=ax_isl, color=COLOR_ISL, lw=LINEWIDTH)

        ax_mg.set_title(f"{comp} – MG Bus", fontsize=12, fontweight="bold")
        ax_isl.set_title(f"{comp} – Island", fontsize=12, fontweight="bold")

        for ax in (ax_mg, ax_isl):
            ax.set_ylabel("Frecuencia [Hz]")
            ax.grid(alpha=0.3)

        if comp.lower() == "seasonal":
            ax_mg.set_ylim(-1.0, 1.0)
            ax_isl.set_ylim(-1.0, 1.0)

    fig.suptitle(
        "Descomposición aditiva sincronizada – Frecuencia MG vs Island (ciclo diario)",
        fontsize=14,
        fontweight="bold",
        y=0.99,
    )
    

##############################################################

def plot_frequency_eda_reports(
    df: pd.DataFrame,
    reports_path: Path,
    day_start: Optional[pd.Timestamp] = None,
    day_end: Optional[pd.Timestamp] = None,
    time_col: str = "segs",
    tz: str = "Europe/Madrid",
) -> list[tuple[str, Path]]:
    """
    Genera informes EDA centrados en las frecuencias del sistema eléctrico.
    Devuelve la lista de tuplas (título, path) de los ficheros guardados.

    Parámetros principales:
      df : DataFrame con índice datetime o columna temporal
      day_start/day_end : Timestamps para el día representativo (si None, se calculan automáticamente)
      time_col : nombre de la columna de tiempo (si no es el índice)
      tz : zona horaria para conversión datetime
      reports_path : carpeta para guardar las figuras
    """
    saved: list[tuple[str, Path]] = []

    f_mg = "MG-LV-MSB_Frequency"
    f_isl = "Island_mode_MCCB_Frequency"
    freq_cols = [f_mg, f_isl]
    nominal_freq = 60.0  # Frecuencia nominal en Hz
    
    # Verificar que al menos una columna de frecuencia existe
    existing_cols = [c for c in freq_cols if c in df.columns]
    if not existing_cols:
        return saved

    # Calcular día representativo si no se proporciona
    if day_start is None or day_end is None:
        try:
            day_start, day_end, _ = compute_representative_day(
                df, existing_cols, time_col=time_col, tz=tz
            )
        except Exception:
            # Fallback: usar el primer día con datos
            df_dt = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)
            first_day = df_dt.index.min().floor("D")
            day_start = first_day.replace(hour=0, minute=0, second=0)
            day_end = first_day.replace(hour=23, minute=59, second=59)
    
    # Asegurar timezone
    if day_start.tzinfo is None:
        day_start = day_start.tz_localize(tz)
    if day_end.tzinfo is None:
        day_end = day_end.tz_localize(tz)

    # 1) Descomposición estacional sincronizada de frecuencias
    try:
        fig = plt.figure(figsize=(16, 10))
        plot_synchronized_frequency_decomposition(df, time_col=time_col, tz=tz)
        path = save_fig(fig, reports_path, "frequency_seasonal_decomposition.png")
        saved.append(("Descomposición estacional — Frecuencias MG vs Island", path))
    except Exception:
        plt.close()

    # 2) Serie temporal de frecuencias (día representativo)
    try:
        fig, ax = plt.subplots(figsize=(14, 5))
        df_dt = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)
        day_df = df_dt.loc[day_start:day_end, existing_cols].dropna(how="all")
        
        if not day_df.empty:
            colors = ["#2a6fdb", "#f38b00"]
            labels = ["MG-LV Bus", "Island Mode"]
            
            for col, color, label in zip(existing_cols, colors, labels):
                if col in day_df.columns:
                    s = day_df[col].dropna()
                    if not s.empty:
                        ax.plot(s.index, s.values, label=label, color=color, linewidth=1.5)
            
            ax.axhline(nominal_freq, color="black", linestyle="--", linewidth=1, label=f"Nominal ({nominal_freq} Hz)")
            ax.set_title(f"Frecuencias del sistema — Día representativo ({day_start.strftime('%d/%m/%Y')})", 
                         fontsize=14, fontweight="bold")
            ax.set_xlabel("Hora del día")
            ax.set_ylabel("Frecuencia [Hz]")
            ax.legend()
            ax.grid(True, alpha=0.3)
            ax.xaxis.set_major_locator(HourLocator(interval=2))
            ax.xaxis.set_major_formatter(DateFormatter("%H:%M"))
            plt.tight_layout()
            path = save_fig(fig, reports_path, "frequency_representative_day.png")
            saved.append(("Frecuencias — Día representativo", path))
        else:
            plt.close()
    except Exception:
        plt.close()

    # 3) Distribución de frecuencias (histogramas)
    try:
        fig, axes = plt.subplots(1, len(existing_cols), figsize=(5 * len(existing_cols), 4))
        if len(existing_cols) == 1:
            axes = [axes]
        
        colors = ["#2a6fdb", "#f38b00", "#2ecc71"]
        labels = ["MG Bus", "Island"]
        
        for ax, col, color, label in zip(axes, existing_cols, colors, labels):
            s = pd.to_numeric(df[col], errors="coerce").dropna()
            if not s.empty:
                ax.hist(s.values, bins=50, color=color, edgecolor="black", alpha=0.7)
                ax.axvline(s.mean(), color="red", linestyle="--", label=f"Media: {s.mean():.2f} Hz")
                ax.axvline(nominal_freq, color="black", linestyle=":", label=f"Nominal: {nominal_freq} Hz")
                ax.set_title(f"Distribución — {label}", fontsize=12, fontweight="bold")
                ax.set_xlabel("Frecuencia [Hz]")
                ax.set_ylabel("Frecuencia")
                ax.legend(fontsize=8)
                ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        path = save_fig(fig, reports_path, "frequency_distribution.png")
        saved.append(("Distribución de frecuencias", path))
    except Exception:
        plt.close()

    # 4) Patrón horario medio de frecuencias
    try:
        fig, ax = plt.subplots(figsize=(12, 5))
        df_dt = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)
        df_plot = df_dt.copy()
        df_plot["hour"] = df_plot.index.hour
        
        hourly_mean = df_plot.groupby("hour")[existing_cols].mean()
        
        if not hourly_mean.empty:
            colors = ["#2a6fdb", "#f38b00", "#2ecc71"]
            labels = ["MG-LV Bus", "Island Mode"]
            
            for col, color, label in zip(existing_cols, colors, labels):
                if col in hourly_mean.columns:
                    ax.plot(hourly_mean.index, hourly_mean[col], label=label, 
                           color=color, linewidth=2.2, marker='o', markersize=4)
            
            ax.axhline(nominal_freq, color="black", linestyle="--", linewidth=1, label=f"Nominal ({nominal_freq} Hz)")
            ax.set_title("Patrón horario medio de frecuencias", fontsize=14, fontweight="bold")
            ax.set_xlabel("Hora del día")
            ax.set_ylabel("Frecuencia media [Hz]")
            ax.set_xticks(range(0, 24, 2))
            ax.legend()
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            path = save_fig(fig, reports_path, "frequency_hourly_pattern.png")
            saved.append(("Patrón horario medio — Frecuencias", path))
        else:
            plt.close()
    except Exception:
        plt.close()

    # 5) Desviación de frecuencia respecto a nominal (60 Hz)
    try:
        fig, ax = plt.subplots(figsize=(14, 5))
        df_dt = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)
        
        # Calcular desviación
        colors = ["#2a6fdb", "#f38b00", "#2ecc71"]
        labels = ["MG-LV Bus", "Island Mode"]
        
        for col, color, label in zip(existing_cols, colors, labels):
            if col in df_dt.columns:
                s = pd.to_numeric(df_dt[col], errors="coerce")
                deviation = s - nominal_freq  # Desviación respecto a nominal
                
                # Resamplear para visualización más clara
                dev_hourly = deviation.resample("h").mean().dropna()
                if not dev_hourly.empty:
                    ax.plot(dev_hourly.index, dev_hourly.values, label=label, 
                           color=color, linewidth=1.5, alpha=0.8)
        
        ax.axhline(0, color="black", linestyle="-", linewidth=1)
        ax.axhline(0.5, color="green", linestyle="--", linewidth=1, alpha=0.7, label="±0.5 Hz (tolerancia)")
        ax.axhline(-0.5, color="green", linestyle="--", linewidth=1, alpha=0.7)
        ax.fill_between(ax.get_xlim(), -0.5, 0.5, alpha=0.1, color="green")
        
        ax.set_title(f"Desviación de frecuencia respecto a nominal ({nominal_freq} Hz)", fontsize=14, fontweight="bold")
        ax.set_xlabel("Tiempo")
        ax.set_ylabel("Desviación [Hz]")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        path = save_fig(fig, reports_path, "frequency_deviation.png")
        saved.append(("Desviación de frecuencia respecto a 60 Hz", path))
    except Exception:
        plt.close()

    return saved


def plot_voltage_control_chart(
    df: pd.DataFrame,
    day_start: pd.Timestamp,
    day_end: pd.Timestamp,
    pv_nominal: float = 485.0,
    bands: tuple[int, ...] = (5, 10, 15),
    time_col: str = "segs",
    tz: str = "Europe/Madrid",
    title: str | None = None,
) -> None:
    """
    Control chart de tensión (24 h) con bandas de tolerancia.
    Dibuja en el eje actual (plt.gca()).
    """
    ax = plt.gca()
    
    V_PCC = "Receiving_Point_AC_Voltage"
    V_MG = "MG-LV-MSB_AC_Voltage"
    V_ISL = "Island_mode_MCCB_AC_Voltage"

    df_local = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)
    
    for col in (V_PCC, V_MG, V_ISL):
        if col not in df_local.columns:
            ax.text(0.5, 0.5, f"Columna no encontrada: {col}", ha="center", va="center")
            ax.axis("off")
            return

    volts = df_local[[V_PCC, V_MG, V_ISL]].copy()
    win = volts.loc[day_start:day_end].dropna()
    
    if win.empty:
        ax.text(0.5, 0.5, "No hay datos para el rango indicado.", ha="center", va="center")
        ax.axis("off")
        return

    ax.plot(win.index, win[V_PCC], label="Receiving Point (PCC)", color="#2a6fdb")
    ax.plot(win.index, win[V_MG], label="MG-LV Bus", color="#f38b00", alpha=0.9)
    ax.plot(win.index, win[V_ISL], label="Island Mode", color="#2ecc71", alpha=0.9)
    
    for thr, c, lab in [(bands[0], "#8bc34a", f"±{bands[0]} V"),
                        (bands[1], "#ffc107", f"±{bands[1]} V"),
                        (bands[2], "#e53935", f"±{bands[2]} V")]:
        ax.fill_between(win.index, pv_nominal - thr, pv_nominal + thr, color=c, alpha=0.10, label=lab)
    
    ax.axhline(pv_nominal, color="k", linestyle="--", linewidth=1)
    ax.set_ylabel("Voltaje [V]")
    ax.set_title(title or f"Control chart de tensión (24 h) {day_start.date()} con bandas", fontsize=14, fontweight="bold")
    ax.legend(ncol=2, fontsize=9, loc="upper left")
    ax.xaxis.set_major_locator(HourLocator(interval=3))
    ax.xaxis.set_major_formatter(DateFormatter("%d %H:%M"))
    ax.grid(True, alpha=0.3)
    plt.tight_layout()


def plot_voltage_seasonal_decomposition(
    df: pd.DataFrame,
    seasonal_period: int = 24,
    min_hourly_samples: int = 48,
    time_col: str = "segs",
    tz: str = "Europe/Madrid",
    title: str | None = None,
) -> None:
    """
    Descomposición estacional sincronizada de voltajes (PCC, MG, Island).
    Dibuja en la figura actual (plt.gcf()).
    """
    fig = plt.gcf()
    fig.clear()
    
    V_PCC = "Receiving_Point_AC_Voltage"
    V_MG = "MG-LV-MSB_AC_Voltage"
    V_ISL = "Island_mode_MCCB_AC_Voltage"

    df_local = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)
    
    series_map = {
        "PCC (Receiving Point)": V_PCC,
        "MG Bus (MG-LV-MSB)": V_MG,
        "Island (MCCB)": V_ISL,
    }
    
    # Filtrar columnas existentes
    valid_map = {name: col for name, col in series_map.items() if col in df_local.columns}
    if not valid_map:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "No se encontraron columnas de voltaje.", ha="center", va="center")
        ax.axis("off")
        return

    series_dict = {
        name: df_local[col].resample("h").mean().fillna(df_local[col].mean())
        for name, col in valid_map.items()
    }

    valid = {name: s for name, s in series_dict.items() if s.dropna().size >= min_hourly_samples}
    if not valid:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, f"No hay suficientes datos horarios (≥ {min_hourly_samples}).", ha="center", va="center")
        ax.axis("off")
        return

    decs = {}
    for name, s in valid.items():
        try:
            decs[name] = seasonal_decompose(s, model="additive", period=seasonal_period)
        except Exception:
            pass
    
    if not decs:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "Descomposición falló para todas las series.", ha="center", va="center")
        ax.axis("off")
        return

    colors = ["#2a6fdb", "#f38b00", "#2ecc71"]
    n = len(decs)
    gs = gridspec.GridSpec(3, n, wspace=0.12, hspace=0.35)

    for j, ((name, dec), color) in enumerate(zip(decs.items(), colors[:n])):
        ax_obs = fig.add_subplot(gs[0, j])
        dec.observed.plot(ax=ax_obs, color=color, lw=1.2)
        ax_obs.set_title(f"Observed – {name}", fontsize=12, fontweight="bold")
        ax_obs.set_ylabel("Voltaje [V]")
        ax_obs.grid(alpha=0.3)

        ax_trend = fig.add_subplot(gs[1, j], sharex=ax_obs)
        dec.trend.plot(ax=ax_trend, color=color, lw=1.2)
        ax_trend.set_title(f"Trend – {name}", fontsize=12, fontweight="bold")
        ax_trend.set_ylabel("Voltaje [V]")
        ax_trend.grid(alpha=0.3)

        ax_seas = fig.add_subplot(gs[2, j], sharex=ax_obs)
        dec.seasonal.plot(ax=ax_seas, color=color, lw=1.2)
        ax_seas.set_title(f"Seasonal – {name}", fontsize=12, fontweight="bold")
        ax_seas.set_ylabel("Voltaje [V]")
        ax_seas.grid(alpha=0.3)
        ax_seas.set_ylim(-5.0, 5.0)

    fig.suptitle(title or "Descomposición aditiva sincronizada – Voltajes (ciclo diario)", 
                 fontsize=14, fontweight="bold", y=0.99)
    


def plot_voltage_eda_reports(
    df: pd.DataFrame,
    reports_path: Path,
    day_start: Optional[pd.Timestamp] = None,
    day_end: Optional[pd.Timestamp] = None,
    time_col: str = "segs",
    tz: str = "Europe/Madrid",
    pv_nominal: float = 485.0,
) -> list[tuple[str, Path]]:
    """
    Genera informes EDA centrados en los voltajes del sistema eléctrico.
    Devuelve la lista de tuplas (título, path) de los ficheros guardados.

    Parámetros principales:
      df : DataFrame con índice datetime o columna temporal
      day_start/day_end : Timestamps para el día representativo (si None, se calculan automáticamente)
      time_col : nombre de la columna de tiempo (si no es el índice)
      tz : zona horaria para conversión datetime
      pv_nominal : voltaje nominal para bandas de tolerancia
      reports_path : carpeta para guardar las figuras
    """
    saved: list[tuple[str, Path]] = []

    V_PCC = "Receiving_Point_AC_Voltage"
    V_MG = "MG-LV-MSB_AC_Voltage"
    V_ISL = "Island_mode_MCCB_AC_Voltage"
    voltage_cols = [V_PCC, V_MG, V_ISL]
    
    # Verificar que al menos una columna de voltaje existe
    existing_cols = [c for c in voltage_cols if c in df.columns]
    if not existing_cols:
        return saved

    # Calcular día representativo si no se proporciona
    if day_start is None or day_end is None:
        try:
            day_start, day_end, _ = compute_representative_day(
                df, existing_cols, time_col=time_col, tz=tz
            )
        except Exception:
            # Fallback: usar el primer día con datos
            df_dt = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)
            first_day = df_dt.index.min().floor("D")
            day_start = first_day.replace(hour=0, minute=0, second=0)
            day_end = first_day.replace(hour=23, minute=59, second=59)
    
    # Asegurar timezone
    if day_start.tzinfo is None:
        day_start = day_start.tz_localize(tz)
    if day_end.tzinfo is None:
        day_end = day_end.tz_localize(tz)

    # 1) Control chart de tensión con bandas de tolerancia
    try:
        fig, _ = plt.subplots(figsize=(14, 6))
        plot_voltage_control_chart(
            df, day_start, day_end, 
            pv_nominal=pv_nominal,
            time_col=time_col, 
            tz=tz
        )
        path = save_fig(fig, reports_path, "voltage_control_chart.png")
        saved.append(("Control chart de tensión (24h) con bandas de tolerancia", path))
    except Exception:
        plt.close()

    # 2) Descomposición estacional de voltajes
    try:
        fig = plt.figure(figsize=(16, 10))
        plot_voltage_seasonal_decomposition(df, time_col=time_col, tz=tz)
        path = save_fig(fig, reports_path, "voltage_seasonal_decomposition.png")
        saved.append(("Descomposición estacional — Voltajes del sistema", path))
    except Exception:
        plt.close()

    

    # 3) Distribución de voltajes (histogramas)
    try:
        n_cols = len(existing_cols)
        n_rows = (n_cols + 2) // 3
        fig, axes = plt.subplots(n_rows, min(3, n_cols), figsize=(5 * min(3, n_cols), 4 * n_rows))
        axes = np.atleast_1d(axes).flatten()
        
        colors = sns.color_palette("husl", n_cols)
        
        for i, (col, color) in enumerate(zip(existing_cols, colors)):
            ax = axes[i]
            s = pd.to_numeric(df[col], errors="coerce").dropna()
            if not s.empty:
                ax.hist(s.values, bins=50, color=color, edgecolor="black", alpha=0.7)
                ax.axvline(s.mean(), color="red", linestyle="--", label=f"Media: {s.mean():.1f}V")
                ax.axvline(pv_nominal, color="black", linestyle=":", label=f"Nominal: {pv_nominal}V")
                ax.set_title(col.replace("_", " "), fontsize=11, fontweight="bold")
                ax.set_xlabel("Voltaje [V]")
                ax.set_ylabel("Frecuencia")
                ax.legend(fontsize=8)
                ax.grid(True, alpha=0.3)
        
        # Ocultar ejes sobrantes
        for j in range(len(existing_cols), len(axes)):
            axes[j].axis("off")
        
        plt.tight_layout()
        path = save_fig(fig, reports_path, "voltage_distribution.png")
        saved.append(("Distribución de voltajes", path))
    except Exception:
        plt.close()

    # 4) Patrón horario medio de voltajes
    try:
        fig, ax = plt.subplots(figsize=(12, 6))
        df_dt = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)
        df_plot = df_dt.copy()
        df_plot["hour"] = df_plot.index.hour
        
        hourly_mean = df_plot.groupby("hour")[existing_cols].mean()
        
        if not hourly_mean.empty:
            colors = sns.color_palette("husl", len(existing_cols))
            
            for col, color in zip(existing_cols, colors):
                if col in hourly_mean.columns:
                    ax.plot(hourly_mean.index, hourly_mean[col], label=col.replace("_", " "), 
                           color=color, linewidth=2.2, marker='o', markersize=4)
            
            ax.axhline(pv_nominal, color="black", linestyle="--", linewidth=1, label=f"Nominal ({pv_nominal}V)")
            ax.set_title("Patrón horario medio de voltajes", fontsize=14, fontweight="bold")
            ax.set_xlabel("Hora del día")
            ax.set_ylabel("Voltaje medio [V]")
            ax.set_xticks(range(0, 24, 2))
            ax.legend(loc="upper left", ncol=2, fontsize=9)
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            path = save_fig(fig, reports_path, "voltage_hourly_pattern.png")
            saved.append(("Patrón horario medio — Voltajes", path))
        else:
            plt.close()
    except Exception:
        plt.close()

    return saved



def plot_power_evolution(
    df: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    power_cols: list[str] | None = None,
    time_col: str = "segs",
    tz: str = "Europe/Madrid",
    title: str | None = None,
) -> None:
    """
    Grafica la evolución temporal de un conjunto de columnas de potencia
    en una ventana definida.
    
    Dibuja en el eje actual (plt.gca()), NO crea figura, NO guarda, NO cierra.
    """
    ax = plt.gca()

    if power_cols is None:
        power_cols = [
            "Battery_Active_Power",
            "PVPCS_Active_Power",
            "FC_Active_Power",
            "GE_Active_Power",
            "Island_mode_MCCB_Active_Power",
        ]

    df_local = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)

    # Filtrar columnas existentes
    existing_cols = [c for c in power_cols if c in df_local.columns]
    if not existing_cols:
        ax.text(0.5, 0.5, "No se encontraron columnas de potencia.", ha="center", va="center")
        ax.axis("off")
        return

    subset = df_local.loc[start:end, existing_cols].dropna(how="all")

    if subset.empty:
        ax.text(0.5, 0.5, "No hay datos en la ventana indicada.", ha="center", va="center")
        ax.axis("off")
        return

    colors = sns.color_palette("husl", len(existing_cols))

    for c, col in zip(colors, existing_cols):
        s = subset[col].dropna()
        if not s.empty:
            ax.plot(s.index, s.values, label=col.replace("_", " "), color=c)

    ax.axhline(0, color="black", linestyle="--", linewidth=1.0)
    ax.set_ylabel("Potencia [kW]")
    ax.set_xlabel("Tiempo")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", ncol=2, fontsize=9)
    ax.set_title(title or "Evolución temporal de las potencias activas", fontsize=14, fontweight="bold")
    plt.tight_layout()


def plot_hexbin_ge_vs_target(
    df: pd.DataFrame,
    target: str = "Island_mode_MCCB_Active_Power",
    ge_col: str = "GE_Active_Power",
    sample_size: int = 200_000,
) -> None:
    """
    Hexbin plot de GE_Active_Power vs target.
    Dibuja en el eje actual (plt.gca()).
    """
    ax = plt.gca()

    if ge_col not in df.columns or target not in df.columns:
        ax.text(0.5, 0.5, f"Columnas {ge_col} o {target} no encontradas.", ha="center", va="center")
        ax.axis("off")
        return

    df_hex = df[[ge_col, target]].dropna()
    if df_hex.empty:
        ax.text(0.5, 0.5, "No hay datos para el hexbin.", ha="center", va="center")
        ax.axis("off")
        return

    n_hex = min(int(sample_size), len(df_hex))
    df_plot = df_hex.sample(n=n_hex, random_state=0)

    hb = ax.hexbin(
        df_plot[ge_col],
        df_plot[target],
        gridsize=60,
        cmap="plasma",
        mincnt=1,
        norm=LogNorm(),
    )
    ax.set_xlabel(f"{ge_col.replace('_', ' ')} (kW)")
    ax.set_ylabel(f"{target.replace('_', ' ')} (kW)")
    ax.set_title("Densidad " + ge_col.replace("_", " ") + " vs " + target.replace("_", " "), fontsize=12, fontweight="bold")
    
    cb = plt.colorbar(hb, ax=ax)
    cb.set_label("Número de muestras")
    plt.tight_layout()


def plot_power_eda_reports(
    df: pd.DataFrame,
    reports_path: Path,
    day_start: Optional[pd.Timestamp] = None,
    day_end: Optional[pd.Timestamp] = None,
    time_col: str = "segs",
    tz: str = "Europe/Madrid",
) -> list[tuple[str, Path]]:
    """
    Genera informes EDA centrados en las potencias del sistema eléctrico.
    Devuelve la lista de tuplas (título, path) de los ficheros guardados.

    Parámetros principales:
      df : DataFrame con índice datetime o columna temporal
      day_start/day_end : Timestamps para el día representativo (si None, se calculan automáticamente)
      time_col : nombre de la columna de tiempo (si no es el índice)
      tz : zona horaria para conversión datetime
      reports_path : carpeta para guardar las figuras
    """
    saved: list[tuple[str, Path]] = []

    power_cols = [
        "Battery_Active_Power",
        "PVPCS_Active_Power",
        "FC_Active_Power",
        "GE_Active_Power",
        "Island_mode_MCCB_Active_Power",
    ]
    
    # Verificar que al menos una columna de potencia existe
    existing_cols = [c for c in power_cols if c in df.columns]
    if not existing_cols:
        return saved

    # Calcular día representativo si no se proporciona
    if day_start is None or day_end is None:
        try:
            day_start, day_end, _ = compute_representative_day(
                df, existing_cols, time_col=time_col, tz=tz
            )
        except Exception:
            # Fallback: usar el primer día con datos
            df_dt = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)
            first_day = df_dt.index.min().floor("D")
            day_start = first_day.replace(hour=0, minute=0, second=0)
            day_end = first_day.replace(hour=23, minute=59, second=59)
    
    # Asegurar timezone
    if day_start.tzinfo is None:
        day_start = day_start.tz_localize(tz)
    if day_end.tzinfo is None:
        day_end = day_end.tz_localize(tz)

    # 1) Evolución temporal de potencias (día representativo)
    try:
        fig, _ = plt.subplots(figsize=(14, 6))
        plot_power_evolution(
            df, day_start, day_end,
            power_cols=power_cols,
            time_col=time_col,
            tz=tz,
            title=f"Evolución de potencias — Día representativo ({day_start.strftime('%d/%m/%Y')})"
        )
        path = save_fig(fig, reports_path, "power_evolution_day.png")
        saved.append(("Evolución de potencias — Día representativo", path))
    except Exception:
        plt.close()

    # 3) Hexbin GE vs Target
    try:
        fig, _ = plt.subplots(figsize=(10, 8))
        plot_hexbin_ge_vs_target(df)
        path = save_fig(fig, reports_path, "power_hexbin_ge_vs_island.png")
        saved.append(("Densidad GE Active Power vs Island Mode", path))
    except Exception:
        plt.close()

    # 4) Distribución de potencias (histogramas)
    try:
        n_cols = len(existing_cols)
        n_rows = (n_cols + 2) // 3
        fig, axes = plt.subplots(n_rows, min(3, n_cols), figsize=(5 * min(3, n_cols), 4 * n_rows))
        axes = np.atleast_1d(axes).flatten()
        
        colors = sns.color_palette("husl", n_cols)
        
        for i, (col, color) in enumerate(zip(existing_cols, colors)):
            ax = axes[i]
            s = pd.to_numeric(df[col], errors="coerce").dropna()
            if not s.empty:
                ax.hist(s.values, bins=50, color=color, edgecolor="black", alpha=0.7)
                ax.axvline(s.mean(), color="red", linestyle="--", label=f"Media: {s.mean():.1f}")
                ax.set_title(col.replace("_", " "), fontsize=11, fontweight="bold")
                ax.set_xlabel("Potencia [kW]")
                ax.set_ylabel("Frecuencia")
                ax.legend(fontsize=8)
                ax.grid(True, alpha=0.3)
        
        # Ocultar ejes sobrantes
        for j in range(len(existing_cols), len(axes)):
            axes[j].axis("off")
        
        plt.tight_layout()
        path = save_fig(fig, reports_path, "power_distribution.png")
        saved.append(("Distribución de potencias", path))
    except Exception:
        plt.close()

    # 5) Patrón horario medio de potencias
    try:
        fig, ax = plt.subplots(figsize=(12, 6))
        df_dt = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)
        df_plot = df_dt.copy()
        df_plot["hour"] = df_plot.index.hour
        
        hourly_mean = df_plot.groupby("hour")[existing_cols].mean()
        
        if not hourly_mean.empty:
            colors = sns.color_palette("husl", len(existing_cols))
            
            for col, color in zip(existing_cols, colors):
                if col in hourly_mean.columns:
                    ax.plot(hourly_mean.index, hourly_mean[col], label=col.replace("_", " "), 
                           color=color, linewidth=2.2, marker='o', markersize=4)
            
            ax.axhline(0, color="black", linestyle="--", linewidth=1)
            ax.set_title("Patrón horario medio de potencias", fontsize=14, fontweight="bold")
            ax.set_xlabel("Hora del día")
            ax.set_ylabel("Potencia media [kW]")
            ax.set_xticks(range(0, 24, 2))
            ax.legend(loc="upper left", ncol=2, fontsize=9)
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            path = save_fig(fig, reports_path, "power_hourly_pattern.png")
            saved.append(("Patrón horario medio — Potencias", path))
        else:
            plt.close()
    except Exception:
        plt.close()

    return saved




# Funciones utilitarias: Hay patrones repetidos (por ejemplo, conversión de tiempos, formateo de fechas, filtrado de columnas numéricas). Puedes crear métodos internos para reutilizar código y reducir duplicación. 
#ensure_datetime_index_from_segs





def plot_measure_summary_fast(
    *,
    measure: str,
    cache_item: dict,
    time_keys: dict,
    output_dir: Path,
    max_points_plot: int = 50_000,
) -> list[tuple[str, Path]]:
    saved: list[tuple[str, Path]] = []

    x = cache_item["x"]
    good = cache_item["good"]

    if not good.any():
        return saved

    dt = time_keys["dt"]            # DatetimeIndex
    month_key = time_keys["month_key"]
    hour = time_keys["hour"]
    season = time_keys["season"]
    day = time_keys["day"]

    # índices de puntos válidos (sin NaN)
    idx = np.flatnonzero(good)
    n = idx.size
    if n == 0:
        return saved

    # subsample (sobre idx, sin crear s_clean)
    if n > max_points_plot:
        step = max(1, n // max_points_plot)
        idx_plot = idx[::step]
    else:
        idx_plot = idx

    # stats (nanmean/nanmedian ya van sobre todo x con NaNs)
    mean_val = float(np.nanmean(x))
    median_val = float(np.nanmedian(x))

    # ------------------------------------------------------------
    # 1) Serie temporal
    # ------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.plot(dt[idx_plot], x[idx_plot], linewidth=0.8, alpha=0.7)
    ax.set_title(f"Serie temporal — {measure}", fontsize=12, fontweight="bold")
    ax.set_xlabel("Tiempo")
    ax.set_ylabel("Valor")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    path = save_fig(fig, output_dir, f"{measure}_serie_temporal.png")
    saved.append((f"Serie temporal — {measure}", path))

    # ------------------------------------------------------------
    # 2) Histograma
    # ------------------------------------------------------------
    x_clean = x[idx]  # copia 1D inevitable si hist necesita array limpio; ok
    n_bins = min(50, max(20, n // 1000))
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(x_clean, bins=n_bins, edgecolor="black", alpha=0.7)
    ax.axvline(mean_val, color="red", linestyle="--", label=f"Media: {mean_val:.2f}")
    ax.axvline(median_val, color="green", linestyle=":", label=f"Mediana: {median_val:.2f}")
    ax.set_title(f"Distribución — {measure}", fontsize=12, fontweight="bold")
    ax.set_xlabel("Valor")
    ax.set_ylabel("Frecuencia")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    path = save_fig(fig, output_dir, f"{measure}_histograma.png")
    saved.append((f"Distribución — {measure}", path))

    # ------------------------------------------------------------
    # 3) Media mensual (rápida: groupby sobre month_key)
    # ------------------------------------------------------------
    try:
        # month_key es indexable: filtramos a good y agrupamos
        s_month = pd.Series(x, index=month_key).where(good).groupby(level=0).mean()
        # y si quieres que salga ordenado cronológicamente:
        s_month = s_month.sort_index()
        if not s_month.empty:
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.plot(s_month.index.astype(str), s_month.values, marker="o", linewidth=1.0)
            ax.set_title(f"Media mensual — {measure}", fontsize=12, fontweight="bold")
            ax.set_xlabel("Mes")
            ax.set_ylabel("Media")
            ax.grid(True, alpha=0.3)
            ax.tick_params(axis="x", rotation=45)
            plt.tight_layout()
            path = save_fig(fig, output_dir, f"{measure}_media_mensual.png")
            saved.append((f"Media mensual — {measure}", path))
    except Exception:
        plt.close()

    # ------------------------------------------------------------
    # 4) Patrón horario por estación (rápido)
    #    Resultado: 4 curvas (inv/prim/ver/oto) con media por hora
    # ------------------------------------------------------------
    try:
        # construimos tabla pequeña: hora, season, x
        # ojo: creamos DF solo con puntos good (para no arrastrar NaNs)
        df_h = pd.DataFrame({
            "hour": hour[idx],
            "season": season[idx],
            "x": x[idx],
        })
        pivot = df_h.groupby(["season", "hour"])["x"].mean().unstack("season")  # index=hour
        if not pivot.empty:
            fig, ax = plt.subplots(figsize=(10, 6))
            # temporadas: 0 winter, 1 spring, 2 summer, 3 autumn
            labels = {0: "Invierno", 1: "Primavera", 2: "Verano", 3: "Otoño"}
            for s in [0, 1, 2, 3]:
                if s in pivot.columns:
                    ax.plot(pivot.index, pivot[s].values, label=labels[s], linewidth=1.2)
            ax.set_title(f"Patrón horario por estación — {measure}", fontsize=12, fontweight="bold")
            ax.set_xlabel("Hora del día")
            ax.set_ylabel("Media")
            ax.grid(True, alpha=0.3)
            ax.legend()
            plt.tight_layout()
            path = save_fig(fig, output_dir, f"{measure}_patron_estacional.png")
            saved.append((f"Patrón horario por estación — {measure}", path))
    except Exception:
        plt.close()

    # ------------------------------------------------------------
    # 5) Día representativo (ultrarrápido y estable):
    #    Elegimos el día cuya curva se parece más a la media diaria.
    #    (Evita compute_representative_day que suele ser caro.)
    # ------------------------------------------------------------
    try:
        # media por (día,hora)
        df_dh = pd.DataFrame({
            "day": day[idx],
            "hour": hour[idx],
            "x": x[idx],
        })
        by_dh = df_dh.groupby(["day", "hour"])["x"].mean().unstack("hour")  # filas=day, cols=0..23
        if by_dh.shape[0] >= 1:
            # rellenar horas faltantes con NaN; distancia L2 ignorando NaN
            template = np.nanmean(by_dh.to_numpy(), axis=0)  # media por hora
            M = by_dh.to_numpy()
            # distancia: sum((M-template)^2) ignorando NaN
            diff = M - template
            diff[np.isnan(diff)] = 0.0
            # penaliza días con pocas horas observadas
            valid_counts = np.sum(~np.isnan(M), axis=1)
            dist = np.sum(diff * diff, axis=1) + (24 - valid_counts) * np.nanvar(template)
            best_i = int(np.argmin(dist))
            best_day = by_dh.index[best_i]
            curve = by_dh.iloc[best_i]

            fig, ax = plt.subplots(figsize=(14, 5))
            ax.plot(curve.index, curve.values, marker="o", linewidth=1.2)
            ax.set_title(f"Día representativo — {measure} ({str(best_day)[:10]})", fontsize=12, fontweight="bold")
            ax.set_xlabel("Hora")
            ax.set_ylabel("Media")
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            path = save_fig(fig, output_dir, f"{measure}_dia_representativo.png")
            saved.append((f"Día representativo — {measure}", path))
    except Exception:
        plt.close()

    return saved

















##############################################################################################
##############################################################################################
##############################################################################################
##############################################################################################
##############################################################################################
##############################################################################################

def compute_representative_day(
    df: pd.DataFrame,
    measures: list[str],
    time_col: str = "segs",
    tz: str = "Europe/Madrid",
    min_coverage: float = 0.90,
) -> tuple[pd.Timestamp | None, pd.Timestamp | None, dict]:
    """
    Elige un “día representativo” universal para una o varias medidas.

    Criterio (simple y robusto):
    1) Agrupa por día y calcula cobertura = % de muestras NO-NaN por día (promedio entre medidas)
    2) Se queda con días con cobertura >= min_coverage
    3) Dentro de esos días, elige el día cuya “actividad media” está más cerca de la mediana
       (para evitar días raros extremos).

    Devuelve day_start/day_end (tz-aware) + summary.
    """
    df_dt = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)

    missing = [c for c in measures if c not in df_dt.columns]
    if missing:
        raise ValueError(f"Medidas no encontradas: {missing}")

    sub = df_dt[measures].apply(pd.to_numeric, errors="coerce")

    # Agrupar por día (timezone-aware)
    day_key = sub.index.floor("D")

    # cobertura por día y medida
    coverage_by_day = sub.notna().groupby(day_key).mean()  # (día x medida) en [0,1]
    coverage_day_avg = coverage_by_day.mean(axis=1)

    # actividad diaria (media de cada medida) y promedio entre medidas
    daily_mean = sub.groupby(day_key).mean()
    daily_activity = daily_mean.mean(axis=1)

    candidates = coverage_day_avg[coverage_day_avg >= float(min_coverage)].index
    if len(candidates) == 0:
        # fallback: el día con mayor cobertura
        best_day = coverage_day_avg.idxmax()
        reason = "fallback_max_coverage"
    else:
        # elegir el día con actividad más cercana a la mediana (día “típico”)
        med = float(daily_activity.loc[candidates].median())
        best_day = (daily_activity.loc[candidates] - med).abs().idxmin()
        reason = "typical_activity_near_median"

    day_start = pd.Timestamp(best_day).tz_localize(None)
    # volvemos a tz (para slicing)
    day_start = pd.Timestamp(day_start, tz=tz)
    day_end = day_start + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    summary = {
        "selected_day": str(best_day),
        "selection_reason": reason,
        "coverage_selected_day": float(coverage_day_avg.loc[best_day]),
        "min_coverage_threshold": float(min_coverage),
    }

    return day_start, day_end, summary


def compute_monthly_means(
    df: pd.DataFrame,
    measures: list[str],
    time_col: str = "segs",
    tz: str = "Europe/Madrid",
) -> pd.DataFrame:
    """
    Devuelve DataFrame (mes 1..12 x medida) con la media mensual.
    """
    df_dt = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)
    sub = df_dt[measures].apply(pd.to_numeric, errors="coerce")
    month = sub.index.month
    out = sub.groupby(month).mean()
    out.index.name = "month"
    return out


def compute_hourly_by_season(
    df: pd.DataFrame,
    measures: list[str],
    time_col: str = "segs",
    tz: str = "Europe/Madrid",
) -> pd.DataFrame:
    """
    Devuelve DataFrame largo con columnas: season, hour, measure, value
    (media por estación y hora).
    """
    df_dt = ensure_datetime_index_from_segs(df, time_col=time_col, tz=tz)
    sub = df_dt[measures].apply(pd.to_numeric, errors="coerce")

    month = sub.index.month
    hour = sub.index.hour
    season = pd.Series(month, index=sub.index).apply(season_from_month)

    long = sub.copy()
    long["season"] = season
    long["hour"] = hour

    melted = long.melt(id_vars=["season", "hour"], var_name="measure", value_name="value")
    out = melted.groupby(["season", "hour", "measure"], as_index=False)["value"].mean()
    return out


def _normalize_series(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    vmin = np.nanmin(s.values)
    vmax = np.nanmax(s.values)
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax == vmin:
        return s * np.nan  # no normalizable
    return (s - vmin) / (vmax - vmin)
