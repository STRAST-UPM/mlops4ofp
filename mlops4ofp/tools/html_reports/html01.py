import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import re
import numpy as np

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
import importlib
importlib.reload(explore_figures)
from mlops4ofp.tools.figures.figures_general import ensure_datetime_index_from_segs, save_figure



#############################################################################################################################################
# -------------------------------------------------------------------------------------------------------------------------------------------
# Procesado del dataset para el informe
#--------------------------------------------------------------------------------------------------------------------------------------------
#############################################################################################################################################

DEFAULT_EXCLUDE = {"segs", "segs_diff", "segs_dt", "Timestamp"}

def compute_percentage_distribution_fast(
    df: pd.DataFrame,
    bins=(0, 5, 10, 25, 40, 60, 75, 90, 95, 100),
    labels=("<5%", "5–10%", "10–25%", "25–40%", "40–60%", "60–75%", "75–90%", "90–95%", ">95%"),
    exclude_cols: list[str] | None = None,
) -> pd.DataFrame | None:
    if len(labels) != (len(bins) - 1):
        raise ValueError("labels debe tener longitud len(bins)-1")

    numeric_df = df.select_dtypes(include=[np.number])
    if exclude_cols:
        numeric_df = numeric_df.drop(columns=exclude_cols, errors="ignore")
    if numeric_df.shape[1] == 0:
        return None

    X = numeric_df.to_numpy(dtype=np.float64, copy=False)  # shape (N, M)
    if X.size == 0:
        return None

    # min/max por columna ignorando NaN
    vmin = np.nanmin(X, axis=0)
    vmax = np.nanmax(X, axis=0)
    span = vmax - vmin

    # columnas válidas: span>0 y al menos un valor no-NaN
    has_any = ~np.isnan(vmin) & ~np.isnan(vmax)
    valid = has_any & (span != 0)

    if not valid.any():
        return None

    # normalizar a 0..100 (para columnas inválidas dejamos NaN)
    # norm = (X - vmin)/(vmax-vmin)*100
    norm = (X - vmin) / span * 100.0
    # norm tendrá nan donde X era nan o span era 0 (div by 0 -> inf/nan); lo controlamos:
    norm[:, ~valid] = np.nan

    # binning: queremos intervalos tipo pd.cut con right=True sobre bins [0..100]
    # Para right=True, digitize con right=True encaja bien.
    bins_arr = np.asarray(bins, dtype=np.float64)
    # indices 0..K-1 donde K=len(labels); NaN se queda fuera
    idx = np.digitize(norm, bins_arr, right=True) - 1  # ahora -1..K-1
    K = len(labels)

    # Conteo porcentual por columna y bin
    # Para cada columna j: contar idx[:,j] en [0..K-1] ignorando NaN/(-1)/K
    dist_vals = np.full((numeric_df.shape[1], K), np.nan, dtype=np.float64)

    for j in range(numeric_df.shape[1]):
        if not valid[j]:
            continue
        col_idx = idx[:, j]
        # válidos: 0..K-1
        mask = (col_idx >= 0) & (col_idx < K)
        n = int(mask.sum())
        if n == 0:
            continue
        counts = np.bincount(col_idx[mask], minlength=K).astype(np.float64)
        dist_vals[j, :] = (counts / n) * 100.0

    dist = pd.DataFrame(dist_vals, index=numeric_df.columns, columns=list(labels)).round(2)

    # si todo NaN -> None
    if dist.empty or dist.isna().all().all():
        return None
    return dist


def _compute_bad_cells_fast(
    df: pd.DataFrame,
    *,
    exclude_cols: list[str] | None = None,
) -> tuple[pd.Series | None, pd.Series | None, dict]:
    """
    Versión rápida equivalente a compute_bad_cells_stats:
    - Solo numéricas
    - Sin .copy()
    - Usa numpy (np.isnan) vectorizado
    """
    numeric_df = df.select_dtypes(include=[np.number])
    if exclude_cols:
        numeric_df = numeric_df.drop(columns=exclude_cols, errors="ignore")

    if numeric_df.shape[1] == 0:
        summary = {"has_numeric": False, "rows_with_bad": 0, "total_bad": 0, "max_bad_in_row": 0, "n_cols_with_bad": 0}
        return None, None, summary

    X = numeric_df.to_numpy(dtype=np.float64, copy=False)
    nan_mask = np.isnan(X)

    bad_per_row_all = nan_mask.sum(axis=1).astype(np.int64)
    bad_per_col_all = nan_mask.sum(axis=0).astype(np.int64)

    # Series con índices correctos (filas = df.index, cols = numeric_df.columns)
    bad_per_row_all_s = pd.Series(bad_per_row_all, index=numeric_df.index)
    bad_per_row = bad_per_row_all_s[bad_per_row_all_s > 0]

    bad_per_col_all_s = pd.Series(bad_per_col_all, index=numeric_df.columns).sort_values(ascending=False)
    bad_per_col = bad_per_col_all_s[bad_per_col_all_s > 0]

    summary = {
        "has_numeric": True,
        "rows_with_bad": int((bad_per_row_all > 0).sum()),
        "total_bad": int(nan_mask.sum()),
        "max_bad_in_row": int(bad_per_row.max()) if not bad_per_row.empty else 0,
        "n_cols_with_bad": int((bad_per_col_all > 0).sum()),
    }

    if bad_per_row.empty and bad_per_col.empty:
        return None, None, summary

    return bad_per_row, bad_per_col, summary


def prepare_dataset_explore_fast(
    *,
    df: pd.DataFrame,
    Tu_value: float,
    report_preclean: dict | None = None,
    exclude_cols: set[str] = DEFAULT_EXCLUDE,
    build_measure_cache: bool = True,
):
    """
    Prepara un cache dict con TODO lo que el informe/figuras necesita.
    Optimizado: evita trabajo repetido en el generador y en plots por medida.

    Devuelve:
      prep: dict con keys:
        - kpis
        - quality_table (o None)
        - global: {...}
        - measure_cols
        - cache_by_measure (opcional)
    """

    # ---- columnas base ----
    time_col = "segs"
    cols = list(df.columns)

    measure_cols = [c for c in cols if c not in exclude_cols]
    # numéricas solo para corr/describe (más rápido y menos sorpresas)
    numeric_measure_cols = [c for c in measure_cols if pd.api.types.is_numeric_dtype(df[c])]

    # ---- convertir tiempo una vez ----
    # (float64 para diffs y comparaciones rápidas)
    if time_col in df.columns:
        t = df[time_col].to_numpy(dtype=np.float64, copy=False)
    else:
        t = None

    n_rows = len(df)
    n_cols = df.shape[1]

    # ---- QUALITY preclean (si existe) ----
    quality_table = quality_summary_table(report_preclean) if report_preclean is not None else None

    # ============================================================
    # GLOBAL PRECOMPUTES (una vez)
    # ============================================================

    global_stats = {}

    # 1) NaNs por columna y por fila (rápido y compatible con tus plots)
    bad_per_row, bad_per_col, bad_summary = _compute_bad_cells_fast(
        df,
        exclude_cols=list(DEFAULT_EXCLUDE),
    )

    global_stats["bad_cells"] = {
        "bad_per_row": bad_per_row,   # puede ser None
        "bad_per_col": bad_per_col,   # puede ser None
        "summary": bad_summary,
    }

    # Tabla Top 30 %NaN (igual que hacías: TODAS las columnas salvo segs)
    na_pct = df.drop(columns=["segs"], errors="ignore").isna().mean() * 100
    global_stats["na_pct_top30"] = (
        na_pct.sort_values(ascending=False)
        .to_frame("Porcentaje de nulos (%)")
        .head(30)
    )

    # 2) Huecos temporales (vectorizado)
    # gap si dt > Tu_value * 1.5 (ajusta umbral si quieres)
    gaps_df, gaps_summary = compute_time_gaps_from_t_fast(
        t,
        expected_period=Tu_value,
        tz="UTC",            # o "Europe/Madrid"
        threshold_factor=1.0 # para clavar tu lógica original
    )

    global_stats["gaps"] = {"df": gaps_df, "summary": gaps_summary}



    # 3) Intervalos con NaNs (rápido)
    intervals_df, intervals_summary = compute_bad_intervals_fast(
        df,
        period=Tu_value,
        time_col="segs",
        tz="UTC",           # o "Europe/Madrid" si quieres que Inicio/Fin salgan ya en local
        assume_sorted=True, # pon False si no garantizas orden
    )
    global_stats["bad_intervals"] = {
        "df": intervals_df,
        "summary": intervals_summary,
    }

   # 3) Estadísticos básicos (solo numéricas, excluyendo segs)
    numeric_for_desc = df.select_dtypes(include=[np.number]).columns.drop("segs", errors="ignore")
    if len(numeric_for_desc) > 0:
        desc = df[numeric_for_desc].describe().T
        # Formateo una sola vez
        desc_fmt = desc.map(smart_fmt)

        # Serie de medias lista para plot (ordenada para barh bonito)
        mean_series = desc["mean"].sort_values(ascending=True)

        global_stats["desc_fmt"] = desc_fmt
        global_stats["mean_series"] = mean_series
    else:
        global_stats["desc_fmt"] = pd.DataFrame()
        global_stats["mean_series"] = pd.Series(dtype=float)


    # 4) Correlación (coste alto si muchas columnas)
    # Truco: si son demasiadas, puedes limitar top-K por varianza o por NaN% bajo.
    numeric_for_corr = df.select_dtypes(include=[np.number]).columns.drop("segs", errors="ignore")
    global_stats["corr"] = df[numeric_for_corr].corr(numeric_only=True) if len(numeric_for_corr) else pd.DataFrame()

    # 5) Distribución porcentual (si tu función es pesada, aquí se hace una vez)
    global_stats["pct_dist"] = compute_percentage_distribution_fast(
        df,
        exclude_cols=DEFAULT_EXCLUDE,  #
    )

    # ============================================================
    # CACHE POR MEDIDA (clave para que el loop por medida vuele)
    # ============================================================
    cache_by_measure = None
    if build_measure_cache and t is not None and numeric_measure_cols:
        cache_by_measure = {}
        # Reusar X + nan_mask si existe
        X = df[numeric_measure_cols].to_numpy(dtype=np.float64, copy=False)
        for j, m in enumerate(numeric_measure_cols):
            x = X[:, j]  # view
            # mask y series “limpias”
            good = ~np.isnan(x)
            # OJO: no hagas x[good] si no hace falta (copia). Guarda good y x.
            cache_by_measure[m] = {
                "t": t,
                "x": x,
                "good": good,
                # precomputes útiles típicos (baratos):
                "n": int(good.sum()),
                "min": float(np.nanmin(x)) if good.any() else np.nan,
                "max": float(np.nanmax(x)) if good.any() else np.nan,
                "mean": float(np.nanmean(x)) if good.any() else np.nan,
            }

    prep = {
        "kpis": {
            "Tu_value": float(Tu_value),
            "n_rows": int(n_rows),
            "n_cols": int(n_cols),
            "n_measures": int(len(measure_cols)),
            "n_numeric_measures": int(len(numeric_measure_cols)),
        },
        "quality_table": quality_table,
        "global": global_stats,
        "measure_cols": measure_cols,
        "numeric_measure_cols": numeric_measure_cols,
        "cache_by_measure": cache_by_measure,
    }
    return prep


def compute_bad_intervals_fast(
    df: pd.DataFrame,
    *,
    period: float,
    time_col: str = "segs",
    tz: str = "UTC",          # para Inicio/Fin; tu código original usa utc=True sin tz_convert
    assume_sorted: bool = True,
) -> tuple[pd.DataFrame | None, dict]:
    """
    Intervalos consecutivos de filas con algún NaN en columnas numéricas.
    Vectorizado y sin slicing por grupos.

    - Si assume_sorted=True: asume df ordenado por time_col y sin NaN en time_col.
    - Devuelve mismo formato que tu compute_bad_intervals.
    """

    if time_col not in df.columns:
        return None, {"n_intervals": 0, "missing_rows": 0, "period_seconds": float(period), "max_interval_seconds": 0.0}

    # 1) tiempo
    t = pd.to_numeric(df[time_col], errors="coerce").to_numpy(dtype=np.float64, copy=False)
    if not assume_sorted:
        # ordenar por t y eliminar NaNs en tiempo
        ok_t = ~np.isnan(t)
        if not ok_t.any():
            return None, {"n_intervals": 0, "missing_rows": 0, "period_seconds": float(period), "max_interval_seconds": 0.0}
        order = np.argsort(t[ok_t], kind="mergesort")
        idx_keep = np.flatnonzero(ok_t)[order]
        t = t[idx_keep]
    else:
        # eliminar NaNs en tiempo (sin reordenar)
        ok_t = ~np.isnan(t)
        if not ok_t.all():
            idx_keep = np.flatnonzero(ok_t)
            t = t[idx_keep]
        else:
            idx_keep = None  # usa vista directa

    # 2) matriz numérica sin time_col
    num_cols = df.select_dtypes(include=[np.number]).columns.drop(time_col, errors="ignore")
    if len(num_cols) == 0:
        return None, {"n_intervals": 0, "missing_rows": 0, "period_seconds": float(period), "max_interval_seconds": 0.0}

    if idx_keep is None:
        X = df[num_cols].to_numpy(dtype=np.float64, copy=False)
    else:
        # indexación 1 vez (sí copia, pero solo si hubo NaNs en time)
        X = df.iloc[idx_keep][num_cols].to_numpy(dtype=np.float64, copy=False)

    nan_mask = np.isnan(X)

    # row_bad: fila con al menos un NaN
    row_bad = nan_mask.any(axis=1)
    missing_rows = int(row_bad.sum())
    if missing_rows == 0:
        return None, {"n_intervals": 0, "missing_rows": 0, "period_seconds": float(period), "max_interval_seconds": 0.0}

    # n_bad_cols_per_row: severidad por fila = nº columnas con NaN
    n_bad_cols_per_row = nan_mask.sum(axis=1).astype(np.int64)

    # tiempos solo de filas malas
    bad_idx = np.flatnonzero(row_bad)
    bad_t = t[bad_idx]

    # si hay solo 1 fila mala -> 1 intervalo de duración period
    period_sec = float(period)

    # cortes de intervalo cuando el salto entre filas malas supera period_sec
    # (igual que tu deltas_sec > period)
    if bad_t.size == 1:
        start_i = np.array([0], dtype=np.int64)
        end_i = np.array([0], dtype=np.int64)
    else:
        cut = np.diff(bad_t) > period_sec
        # start indices dentro de bad_t
        start_i = np.r_[0, np.flatnonzero(cut) + 1]
        end_i = np.r_[start_i[1:] - 1, bad_t.size - 1]

    # por intervalo: start/end en segs y nº muestras
    start_seg = bad_t[start_i]
    end_seg = bad_t[end_i]
    n_samples = (end_i - start_i + 1).astype(np.int64)

    # duración: end-start + period_sec (igual que tu fórmula)
    duration_sec = (end_seg - start_seg + period_sec)

    # Media_columnas_malas por intervalo:
    # necesitamos la media de n_bad_cols_per_row en las filas malas de ese intervalo
    bad_severity = n_bad_cols_per_row[bad_idx]  # severidad solo en filas malas

    # suma por segmento con cumsum (O(N))
    csum = np.cumsum(bad_severity, dtype=np.float64)
    seg_sum = csum[end_i] - np.r_[0.0, csum[start_i[1:] - 1]]
    mean_bad_cols = seg_sum / n_samples

    # construir dataframe como el tuyo
    intervals_df = pd.DataFrame({
        "inicio_seg": start_seg,
        "fin_seg": end_seg,
        "duracion_seg": duration_sec,
        "Muestras": n_samples,
        "Media_columnas_malas": mean_bad_cols,
    }).sort_values("inicio_seg").reset_index(drop=True)

    inicio_dt = pd.to_datetime(intervals_df["inicio_seg"], unit="s", utc=True)
    fin_dt = pd.to_datetime(intervals_df["fin_seg"], unit="s", utc=True)
    # si quieres tz local, conviértelo aquí:
    if tz and tz != "UTC":
        inicio_dt = inicio_dt.dt.tz_convert(tz)
        fin_dt = fin_dt.dt.tz_convert(tz)

    intervals_df["Inicio"] = inicio_dt.dt.strftime("%d/%m/%Y %H:%M:%S")
    intervals_df["Fin"] = fin_dt.dt.strftime("%d/%m/%Y %H:%M:%S")
    intervals_df["Duración"] = pd.to_timedelta(intervals_df["duracion_seg"], unit="s")
    intervals_df = intervals_df.drop(columns=["inicio_seg", "fin_seg", "duracion_seg"])

    summary = {
        "period_seconds": period_sec,
        "n_intervals": int(len(intervals_df)),
        "missing_rows": missing_rows,
        "max_interval_seconds": float(intervals_df["Duración"].dt.total_seconds().max()),
    }
    return intervals_df, summary


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
    all_cols = sorted((set(nulls) | set(outliers) | set(suspect)) - DEFAULT_EXCLUDE)
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

    df = pd.DataFrame(rows)

    # 3) ordenar por "más problemáticas"
    sort_cols = ["Null count (NaN)", "Outlier count (IQR, 1.5×IQR)"] + list(suspect_colname.values())
    df = df.sort_values(sort_cols, ascending=False).reset_index(drop=True)
    

    return df



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



def prepare_time_keys_fast(df: pd.DataFrame, time_col="segs", tz="Europe/Madrid"):
    """
    Prepara arrays de tiempo reutilizables para todas las medidas.
    Coste O(N) una vez.
    """
    segs = df[time_col].to_numpy(dtype=np.float64, copy=False)

    # Construye datetime index UNA vez (ajusta unidad si segs está en segundos)
    # Si segs ya es "segundos desde epoch": unit="s". Si es relativo desde 0, también vale para patrones.
    dt = pd.to_datetime(segs, unit="s", utc=True).tz_convert(tz)

    # Keys rápidas para agregaciones
    # month_key: Period[M] para agrupar por mes
    month_key = dt.strftime("%Y-%m") 
    hour = dt.hour.to_numpy()
    month = dt.month.to_numpy()
    day = dt.floor("D")  # para día representativo/agrupaciones por día

    # estación simple (DJF/MAM/JJA/SON)
    # 12,1,2 -> winter; 3,4,5 -> spring; 6,7,8 -> summer; 9,10,11 -> autumn
    season = np.empty_like(month, dtype=np.int8)
    season[(month == 12) | (month <= 2)] = 0
    season[(3 <= month) & (month <= 5)] = 1
    season[(6 <= month) & (month <= 8)] = 2
    season[(9 <= month) & (month <= 11)] = 3

    return {
        "segs": segs,
        "dt": dt,                 # DatetimeIndex (tz-aware)
        "month_key": month_key,   # PeriodIndex-like
        "hour": hour,
        "season": season,
        "day": day,               # DatetimeIndex floored to day
        "tz": tz,
        "time_col": time_col,
    }


def prepare_measure_cache_fast(df: pd.DataFrame, numeric_cols: list[str]):
    """
    Cache por medida: x (float64 view) + good mask.
    """
    X = df[numeric_cols].to_numpy(dtype=np.float64, copy=False)
    cache = {}
    for j, m in enumerate(numeric_cols):
        x = X[:, j]          # view
        good = ~np.isnan(x)  # mask
        cache[m] = {"x": x, "good": good}
    return cache



def compute_time_gaps_from_t_fast(
    t: np.ndarray | None,
    *,
    expected_period: float,
    tz: str = "UTC",            # tu versión usa UTC; si quieres local, pon "Europe/Madrid"
    threshold_factor: float = 1.0,  # 1.0 = tu lógica original (delta > period)
) -> tuple[pd.DataFrame | None, dict]:
    """
    Detecta huecos temporales a partir del vector de tiempos t (segs).
    No toca df. Muy rápido.

    t: np.ndarray float (segs), idealmente ordenado asc.
    """

    period_sec = float(expected_period) if expected_period is not None else None
    if t is None or len(t) < 2 or period_sec is None or period_sec <= 0:
        return None, {
            "n_gaps": 0,
            "missing_samples_total": 0,
            "expected_period_seconds": period_sec,
            "max_gap_seconds": 0.0,
        }

    # Si puede haber NaNs, los filtramos 1 vez
    ok = ~np.isnan(t)
    if not ok.all():
        t = t[ok]
        if len(t) < 2:
            return None, {
                "n_gaps": 0,
                "missing_samples_total": 0,
                "expected_period_seconds": period_sec,
                "max_gap_seconds": 0.0,
            }

    dt = np.diff(t)
    thr = period_sec * float(threshold_factor)
    gap_mask = dt > thr

    if not gap_mask.any():
        return None, {
            "n_gaps": 0,
            "missing_samples_total": 0,
            "expected_period_seconds": period_sec,
            "max_gap_seconds": 0.0,
        }

    idx = np.flatnonzero(gap_mask)  # posiciones en dt
    prev_segs = t[idx]
    curr_segs = t[idx + 1]
    gap_seconds = dt[idx]

    missing_samples = np.clip(np.rint(gap_seconds / period_sec - 1.0).astype(np.int64), 0, None)

    gaps_df = pd.DataFrame({
        "inicio_seg": prev_segs,
        "fin_seg": curr_segs,
        "duracion_hueco_s": gap_seconds,
        "muestras_faltantes": missing_samples,
    })

    inicio_dt = pd.to_datetime(gaps_df["inicio_seg"], unit="s", utc=True)
    fin_dt = pd.to_datetime(gaps_df["fin_seg"], unit="s", utc=True)
    if tz and tz != "UTC":
        inicio_dt = inicio_dt.dt.tz_convert(tz)
        fin_dt = fin_dt.dt.tz_convert(tz)

    gaps_df["inicio"] = inicio_dt.dt.strftime("%d/%m/%Y %H:%M:%S")
    gaps_df["fin"] = fin_dt.dt.strftime("%d/%m/%Y %H:%M:%S")
    gaps_df["duracion_hueco"] = pd.to_timedelta(gaps_df["duracion_hueco_s"], unit="s")

    summary = {
        "expected_period_seconds": period_sec,
        "n_gaps": int(len(gaps_df)),
        "missing_samples_total": int(missing_samples.sum()),
        "max_gap_seconds": float(gap_seconds.max()),
    }

    gaps_df = gaps_df.drop(columns=["inicio_seg", "fin_seg", "duracion_hueco_s"])
    # Opcional: ordenar por duración desc y cortar top50 en el HTML (o aquí)
    gaps_df = gaps_df.sort_values("muestras_faltantes", ascending=False).reset_index(drop=True)

    return gaps_df, summary


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
    
    prep= prepare_dataset_explore_fast(df=df_out, Tu_value=Tu_value, report_preclean=report_preclean, exclude_cols=DEFAULT_EXCLUDE, build_measure_cache=True, )

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

    bad = prep["global"]["bad_cells"]
    bad_per_row = bad["bad_per_row"]
    bad_per_col = bad["bad_per_col"]
    bad_summary = bad["summary"]

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

    rep.add(table_card(
        prep["global"]["na_pct_top30"],
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

    bad_int = prep["global"]["bad_intervals"]
    intervals_df = bad_int["df"]
    intervals_summary = bad_int["summary"]

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
        save_figure(fig_int_1, plot_fn=lambda: explore_figures.plot_bad_intervals_duration_hist(intervals_df), figsize=(12, 5))

        fig_int_2 = figures_dir / "bad_intervals_scatter.png"
        save_figure(fig_int_2, plot_fn=lambda: explore_figures.plot_bad_intervals_scatter(intervals_df), figsize=(12, 5))

        rep.add(open_grid(cols=2, gap_rem=1.0))
        rep.add(render_figure_card("Histograma de duración de intervalos con NaNs", fig_int_1.name, max_width="100%"))
        rep.add(render_figure_card("Scatter: duración vs severidad", fig_int_2.name, max_width="100%"))
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

    g = prep["global"]["gaps"]
    gaps_df = g["df"]
    gaps_summary = g["summary"]

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

    desc_fmt = prep["global"]["desc_fmt"]
    mean_series = prep["global"]["mean_series"]

    fig_mean = figures_dir / "mean_by_variable.png"
    save_figure(
        fig_mean,
        plot_fn=lambda: (
            mean_series.plot(kind="barh", title="Media por variable numérica"),
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

    dist = prep["global"]["pct_dist"]

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
    corr = prep["global"]["corr"]

    corr_path = figures_dir / "corr_heatmap.png"
    save_figure(
        corr_path,
        plot_fn=lambda: explore_figures.plot_correlation_heatmap(corr),
        figsize=(12, 10),
    )
    rep.add(card(render_figure_card("Heatmap de correlación", corr_path.name, max_width="100%")))

    # ------------------------------------------------------------
    # Figuras por medida (summary)
    # ------------------------------------------------------------
    rep.hr()
    rep.add(section("Análisis detallado por medida"))

    # for measure in measure_cols:
    #     rep.add(subsection(measure, center=True))

    #     measure_figs = explore_figures.plot_measure_summary(
    #         df=df_out,
    #         measure=measure,
    #         output_dir=figures_dir,
    #         time_col="segs",
    #     )
    #     rep.add(figures_grid(measure_figs, cols=2, max_width="100%"))

    time_keys = prepare_time_keys_fast(df_out, time_col="segs", tz="Europe/Madrid")
    numeric_cols = [c for c in df_out.columns if c not in DEFAULT_EXCLUDE and pd.api.types.is_numeric_dtype(df_out[c])]
    cache = prepare_measure_cache_fast(df_out, numeric_cols)


    for measure in numeric_cols:
        rep.add(subsection(measure, center=True))
        figs = explore_figures.plot_measure_summary_fast(
            measure=measure,
            cache_item=cache[measure],
            time_keys=time_keys,
            output_dir=figures_dir,
            max_points_plot=50_000,
        )
        rep.add(figures_grid(figs, cols=2, max_width="100%"))



    # ------------------------------------------------------------
    # Figuras extra (temperatura/voltaje/frecuencia/potencia)
    # ------------------------------------------------------------
    rep.hr()
    rep.add(section("Otras figuras"))


    df_dt = ensure_datetime_index_from_segs(df_out, time_col="segs", tz="Europe/Madrid")


    extra_blocks = [
        ("Análisis de Temperaturas del Sistema de Agua", explore_figures.plot_temperature_eda_reports),
        ("Análisis de Voltajes", explore_figures.plot_voltage_eda_reports),
        ("Análisis de Frecuencias", explore_figures.plot_frequency_eda_reports),
        ("Análisis de Potencias del Sistema Eléctrico", explore_figures.plot_power_eda_reports),
    ]

    for title, fn in extra_blocks:
        rep.add(subsection(title))
        figs = fn(df=df_dt, reports_path=figures_dir, time_col="segs")
        rep.add(figures_grid(figs, cols=2, max_width="100%"))

    rep.write(report_path)
    print(f"[OK] Informe HTML generado en {report_path}")
    print(f"[OK] Figuras generadas en: {figures_dir}")
