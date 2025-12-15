from pathlib import Path
import matplotlib.pyplot as plt

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
 