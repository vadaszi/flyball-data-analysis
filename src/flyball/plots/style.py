"""Shared chart style: colour roles, matplotlib defaults and small helpers.

Colours are assigned by the job they do (dataviz skill, validated with its
palette checker: aqua / orange / violet pass all-pairs CVD and normal-vision
separation on the light surface):

- red and blue are reserved for the two lanes (Q1) and used nowhere else;
- WRFT is the emphasis hue (violet), the rest of the field is grey context;
- aqua = won / good outcome, orange = fault / risk.
Aqua is below 3:1 contrast on the surface, so charts using it carry direct
labels or a table twin.
"""

import matplotlib as mpl
import matplotlib.pyplot as plt

from flyball import config

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

WRFT = "#6250d6"
FIELD = MUTED
FIELD_LIGHT = AXIS
GOOD = "#1baf7a"
FAULT = "#eb6834"
LANE = {"red": "#e34948", "blue": "#2a78d6"}


def apply() -> None:
    """Matplotlib defaults: hairline recessive axes, no top/right spines, system sans."""
    mpl.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "figure.dpi": 110, "savefig.dpi": 200, "savefig.bbox": "tight",
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans", "Arial", "sans-serif"],
        "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
        "axes.titlelocation": "left", "axes.labelcolor": INK_2, "axes.edgecolor": AXIS,
        "axes.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "grid.linestyle": "-",
        "axes.axisbelow": True, "xtick.color": MUTED, "ytick.color": MUTED,
        "xtick.labelcolor": INK_2, "ytick.labelcolor": INK_2, "text.color": INK,
        "legend.frameon": False, "lines.linewidth": 2, "lines.solid_capstyle": "round",
    })


def subtitle(ax, text: str) -> None:
    """Muted one-line subtitle under the axes title."""
    ax.text(0, 1.01, text, transform=ax.transAxes, color=INK_2, fontsize=9, va="bottom")


def save(fig, name: str, folder: str = "phase3"):
    """Save a figure as PNG under figures/<folder>/ and close it."""
    out = config.FIGURES / folder
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.png"
    fig.savefig(path)
    plt.close(fig)
    return path
