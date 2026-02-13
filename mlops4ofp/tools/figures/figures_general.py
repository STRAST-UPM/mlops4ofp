
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

sns.set_theme(style="whitegrid")
plt.rcParams["figure.dpi"] = 120
plt.rcParams["axes.titlepad"] = 12
plt.rcParams["grid.alpha"] = 0.3


def save_figure(fig_path: Path, plot_fn, figsize=(10, 4)):
    """
    Ejecuta una función de plotting y guarda la figura.
    plot_fn debe contener SOLO código de dibujo (sin savefig).
    """
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=figsize)
    plot_fn()
    plt.tight_layout()
    plt.savefig(fig_path)
    plt.close()
 


def season_from_month(m):
    if m in [12,1,2]:  return "Invierno"
    if m in [3,4,5]:   return "Primavera"
    if m in [6,7,8]:   return "Verano"
    if m in [9,10,11]: return "Otoño"



def ensure_datetime_index_from_segs(
    df: pd.DataFrame,
    time_col: str = "segs",
    tz: str = "Europe/Madrid",
) -> pd.DataFrame:
    """
    Devuelve una copia con índice datetime a partir de segs (epoch seconds).
    """
    if isinstance(df.index, pd.DatetimeIndex):
        return df
    df2 = df.copy()
    if time_col in df2.columns:
        df2[time_col] = pd.to_numeric(df2[time_col], errors="coerce")
        df2 = df2.dropna(subset=[time_col]).sort_values(time_col)
        dt = pd.to_datetime(df2[time_col], unit="s", utc=True)
        df2 = df2.set_index(dt)
    elif isinstance(df2.index, pd.DatetimeIndex):
        # si ya viene como datetime, lo dejamos
        pass
    else:
        raise ValueError(f"No se puede construir eje temporal: falta '{time_col}' y el índice no es DatetimeIndex.")
    return df2




def save_fig(fig, output_dir: Path, filename: str) -> Path:
    """Guarda una figura y la cierra."""
    out_path = output_dir / filename
    fig.savefig(out_path, bbox_inches="tight", dpi=100)
    plt.close(fig)
    return out_path
