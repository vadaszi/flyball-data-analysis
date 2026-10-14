"""Phase 6 charts for the Hungarian deck and website (SVG, text as outlines).

Colour roles are the ones in `style` (validated with the dataviz palette checker in Phase 3):
red/blue only for the lanes, violet = WRFT or the lever in focus, grey = the field or context,
aqua = good / won, orange = fault / risk. Charts with aqua carry direct labels or a table twin
on the site, because aqua is below 3:1 contrast on the surface.

Chart text is Hungarian; numbers use the decimal comma via `numbers.num`. Titles are left to the
slide (the slide title is the takeaway), so most charts carry only axis labels and a legend.
"""

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch, Rectangle

from flyball import config
from flyball.plots import style
from flyball.plots.style import FAULT, FIELD, FIELD_LIGHT, GOOD, GRID, INK, INK_2, MUTED, SURFACE, WRFT
from flyball.report import figdata
from flyball.report.numbers import num

FONT_DIR = Path(__file__).resolve().parents[1] / "report" / "static" / "fonts"
OUT = config.FIGURES / "phase6"
MIDPOINT = "#f0efec"
WRFT_LIGHT = "#c9c2f2"      # a light step of the violet, for context lines of WRFT


def apply() -> None:
    """The Phase 3 style plus the deck font (Source Sans 3) and outlined SVG text."""
    style.apply()
    for f in FONT_DIR.glob("*.ttf"):
        font_manager.fontManager.addfont(str(f))
    mpl.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Source Sans 3", "DejaVu Sans"],
        "font.size": 12, "axes.titlesize": 13, "axes.labelsize": 12, "xtick.labelsize": 11,
        "ytick.labelsize": 11, "legend.fontsize": 11, "svg.fonttype": "path", "svg.hashsalt": "wrft",
        "axes.formatter.use_mathtext": False,
    })


def save(fig, name: str) -> Path:
    """Save as SVG under figures/phase6/ (deterministic: no date metadata)."""
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.svg"
    fig.savefig(path, format="svg", metadata={"Date": None, "Creator": None})
    plt.close(fig)
    return path


def hu_axis(ax, axis: str = "x", decimals: int = 2, percent: bool = False, sign: bool = False) -> None:
    """Decimal-comma tick labels (percent: shares shown as 40%)."""
    def f(v, _):
        return num(100 * v, decimals, sign) + "%" if percent else num(v, decimals, sign)
    (ax.xaxis if axis == "x" else ax.yaxis).set_major_formatter(f)


def note(ax, text: str, y: float = 1.01) -> None:
    ax.text(0, y, text, transform=ax.transAxes, color=INK_2, fontsize=11, va="bottom")


# --- 1. Season calendar ---------------------------------------------------------------------------

def season_calendar(days: pd.DataFrame, field_clean: float):
    """One tile per WRFT competition day: colour = clean-heat rate vs the field (diverging),
    text = win rate; a temperature strip below; a marker on the days WRFT fell behind its peers."""
    d = days.reset_index(drop=True)
    event = (d["competition"] != d["competition"].shift()).cumsum()
    x = np.arange(len(d)) + (event.to_numpy() - 1) * 0.35
    cmap = LinearSegmentedColormap.from_list("clean", [FAULT, MIDPOINT, GOOD])
    span = 0.25
    fig, ax = plt.subplots(figsize=(12.4, 4.3))
    for i, r in d.iterrows():
        colour = cmap(0.5 + np.clip((r["clean_heat_rate"] - field_clean) / span, -1, 1) / 2)
        ax.add_patch(FancyBboxPatch((x[i] - 0.44, 1.0), 0.88, 1.5, boxstyle="round,pad=0,rounding_size=0.08",
                                    facecolor=colour, edgecolor="none"))
        lum = 0.2126 * colour[0] + 0.7152 * colour[1] + 0.0722 * colour[2]
        tc = "white" if lum < 0.45 else INK
        ax.text(x[i], 2.05, num(100 * r["clean_heat_rate"], 0) + "%", ha="center", va="center",
                fontsize=13, fontweight="bold", color=tc)
        ax.text(x[i], 1.45, "nyert\n" + num(100 * r["win_rate"], 0) + "%", ha="center", va="center",
                fontsize=9.5, color=tc, linespacing=0.95)
        ax.text(x[i], 2.72, r["weekday"][:3].capitalize(), ha="center", va="bottom",
                fontsize=9.5, color=MUTED)
        if r["below_peers"]:
            ax.text(x[i], 0.83, "▲", ha="center", va="top", fontsize=12, color=FAULT)
        # temperature strip
        t = r["temp_mean_c"]
        ax.add_patch(Rectangle((x[i] - 0.3, -0.9), 0.6, 1.2 * t / 35, facecolor=FIELD_LIGHT, edgecolor="none"))
        ax.text(x[i], -0.95, num(t, 0) + "°", ha="center", va="top", fontsize=10, color=INK_2)
    for _, grp in d.groupby(event):
        xs = x[grp.index]
        ax.text(xs.mean(), 3.35, grp["event"].iloc[0], ha="center", va="bottom", fontsize=10.5, color=INK,
                fontweight="semibold")
        ax.text(xs.mean(), 3.08, pd.Timestamp(grp["date"].iloc[0]).strftime("%m.%d."), ha="center",
                va="bottom", fontsize=9.5, color=MUTED)
    ax.text(x[0] - 0.6, 1.75, "hibátlan\nfutam", ha="right", va="center", fontsize=10, color=INK_2)
    ax.text(x[0] - 0.6, -0.55, "átlag-\nhőmérséklet", ha="right", va="center", fontsize=10, color=INK_2)
    ax.set_xlim(x[0] - 1.6, x[-1] + 0.6)
    ax.set_ylim(-1.5, 3.9)
    ax.axis("off")
    # legend, in figure coordinates so it never collides with the tiles
    items = [(f"kevesebb hibátlan futam, mint a mezőnyben ({num(100 * field_clean, 0)}%)", -span),
             ("a mezőny szintje", 0.0), ("több hibátlan futam", span)]
    lx = 0.02
    for lab, v in items:
        fig.patches.append(Rectangle((lx, 0.015), 0.012, 0.04, transform=fig.transFigure,
                                     facecolor=cmap(0.5 + v / span / 2), edgecolor="none"))
        t = fig.text(lx + 0.017, 0.035, lab, va="center", fontsize=10, color=INK_2)
        lx += 0.04 + 0.0068 * len(lab)
    fig.text(lx, 0.035, "▲", va="center", fontsize=11, color=FAULT)
    fig.text(lx + 0.015, 0.035, "kevesebb győzelem, mint a divízió többi csapatáé", va="center",
             fontsize=10, color=INK_2)
    del t
    return fig


# --- 2. Heat strip ------------------------------------------------------------------------------

def heat_strip(pair: pd.DataFrame):
    """Two teams' heat as timelines: start, the four runs and the passes, with the fault marked."""
    fig, ax = plt.subplots(figsize=(12.4, 3.4))
    rows = [(1.0, pair.iloc[0], WRFT), (0.0, pair.iloc[1], FIELD)]
    for y, r, colour in rows:
        t = 0.0
        segs = [("start", r["start"], r["start_code"] if "start_code" in r else "number")]
        for k in range(1, 5):
            if k > 1:
                segs.append((f"chg{k}", r[f"chg{k}"], r[f"chg{k}_code"]))
            segs.append((f"run{k}", r[f"run{k}"], "run"))
        for name, v, code in segs:
            if name.startswith("run"):
                ax.barh(y, v, left=t, height=0.42, color=colour, edgecolor=SURFACE, linewidth=2)
                k = int(name[-1])
                ax.text(t + v / 2, y, f"{r[f'name{k}']}\n{num(v, 2)}", ha="center", va="center",
                        fontsize=10, color="white", linespacing=1.0)
                t += v
            else:
                bad = code in ("error", "early_pass") or (pd.notna(v) and v < 0)
                if bad:
                    ax.plot([t, t], [y - 0.32, y + 0.32], color=FAULT, lw=3, solid_capstyle="butt")
                    ax.annotate("korai váltás\n(hiba, nem futották újra)", (t, y + 0.32), xytext=(0, 14),
                                textcoords="offset points", ha="center", va="bottom", fontsize=10.5,
                                color=INK, arrowprops={"arrowstyle": "-", "color": FAULT, "lw": 1.2})
                elif pd.notna(v) and v > 0:
                    ax.barh(y, v, left=t, height=0.42, color=FIELD_LIGHT, edgecolor=SURFACE, linewidth=1)
                    t += v
        outcome = "győzelem" if r["outcome"] == "win" else "vereség"
        ax.text(t + 0.25, y, f"{num(r['total'], 2)} mp  →  {outcome}", va="center", fontsize=12.5,
                fontweight="bold", color=INK)
        team = figdata.short_team(r["team"]) if r["is_wrft"] else r["team"]
        ax.text(-0.3, y, team, ha="right", va="center", fontsize=12.5, fontweight="semibold", color=INK)
    ax.set_xlim(-0.2, 22.8)
    ax.set_ylim(-0.55, 1.95)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.grid(axis="y", visible=False)
    hu_axis(ax, "x", 0)
    ax.set_xlabel("másodperc a zöld lámpától")
    return fig


# --- 3. What wins a heat ----------------------------------------------------------------------------

FAULT_STATUS_HU = {("own clean", "opponent fault"): "mi hibátlanok, az ellenfél hibázik",
                   ("own clean", "opponent clean"): "egyik csapat sem hibázik",
                   ("own fault", "opponent fault"): "mindkét csapat hibázik",
                   ("own fault", "opponent clean"): "mi hibázunk, az ellenfél hibátlan"}


def what_wins(by_fault: pd.DataFrame, by_gap: pd.DataFrame):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.4, 4.3), gridspec_kw={"width_ratios": [1.05, 1]})
    order = list(FAULT_STATUS_HU)
    t = by_fault.set_index(["own", "opp"]).loc[order]
    y = np.arange(len(t))[::-1]
    colours = [GOOD, FIELD, FIELD, FAULT]
    a1.hlines(y, t["ci_low"], t["ci_high"], color=colours, linewidth=7, alpha=0.35)
    a1.scatter(t["win_rate"], y, s=90, color=colours, edgecolor=SURFACE, linewidth=2, zorder=3)
    for yi, v in zip(y, t["win_rate"]):
        a1.text(v, yi + 0.28, num(100 * v, 0) + "%", ha="center", fontsize=12, fontweight="bold", color=INK)
    a1.set_yticks(y, [FAULT_STATUS_HU[o] for o in order])
    a1.set_xlim(0, 1)
    a1.set_ylim(-0.6, len(t) - 0.2)
    hu_axis(a1, "x", 0, percent=True)
    a1.grid(axis="y", visible=False)
    a1.set_title("Megnyert futamok aránya a hibák szerint", pad=10)

    mid = by_gap["gap_bin"].map(_bin_mid)
    a2.fill_between(mid, by_gap["ci_low"], by_gap["ci_high"], color=WRFT, alpha=0.12, linewidth=0)
    a2.plot(mid, by_gap["win_rate"], color=WRFT, marker="o", markersize=7, markeredgecolor=SURFACE,
            markeredgewidth=2)
    a2.axhline(0.5, color=style.AXIS, linewidth=0.8)
    a2.axvline(0, color=style.AXIS, linewidth=0.8)
    a2.set_ylim(0, 1)
    hu_axis(a2, "y", 0, percent=True)
    hu_axis(a2, "x", 1)
    a2.set_xlabel("a szokásos tiszta idők különbsége (mp)   ← mi vagyunk a gyorsabbak   a lassabbak →")
    a2.set_title("Ha egyik csapat sem hibázik, a gyorsabb nyer", pad=10)
    fig.tight_layout(w_pad=3)
    return fig


def _bin_mid(label: str) -> float:
    lo, hi = (float(x) for x in label.strip("(]").split(","))
    if np.isinf(lo):
        return hi - 0.25
    if np.isinf(hi):
        return lo + 0.25
    return (lo + hi) / 2


# --- 4. Impact ledger -------------------------------------------------------------------------------

GROUP_ORDER = ["Viszonyítás", "Azonnal, ingyen", "Ki kell deríteni", "Edzéssel", "Kutyán múlik", "A kutyák jólléte", "Nem számít"]


def impact_ledger(led: pd.DataFrame):
    """Ranked levers in extra heats won per season (95 % CI), grouped by what they take."""
    d = led.reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(12.4, 5.6))
    y_positions, y, last_group = [], 0.0, None
    for _, r in d.iterrows():
        if r["group"] != last_group and last_group is not None:
            y -= 0.45
        y_positions.append(y)
        last_group = r["group"]
        y -= 1
    y_positions = np.array(y_positions)
    ceiling = d["lever_id"] == "ceiling"
    sub = d["label"].str.startswith("   ")
    for i, r in d.iterrows():
        yi = y_positions[i]
        if r["lever_id"] == "ceiling":
            colour, h = GRID, 0.62
        elif r["group"] == "Nem számít":
            colour, h = FIELD, 0.62
        else:
            colour, h = (WRFT_LIGHT if sub[i] else WRFT), (0.42 if sub[i] else 0.62)
        ax.barh(yi, r["extra_wins"], height=h, color=colour, edgecolor="none")
        if r["ci_high"] > 0 and r["lever_id"] != "ceiling":
            ax.hlines(yi, r["ci_low"], r["ci_high"], color=INK_2, lw=1.4)
        label = "0  (nem számít)" if r["group"] == "Nem számít" else (
            ("+" + num(r["extra_wins"], 0)) + f"  ({num(r['ci_low'], 0)}–{num(r['ci_high'], 0)})")
        if r["lever_id"] == "ceiling":
            label += "  → a skálán kívül"
        xpos = max(r["ci_high"], r["extra_wins"]) + 1.5
        if r["lever_id"] == "ceiling":
            xpos = 50
        ax.text(xpos, yi, label, va="center", fontsize=11 if not sub[i] else 10, color=INK if not sub[i] else INK_2,
                fontweight="bold" if not (sub[i] or ceiling[i]) else "normal")
    ax.set_yticks(y_positions, d["label"].str.strip().where(~sub, "   " + d["label"].str.strip()))
    for lab, s in zip(ax.get_yticklabels(), sub):
        if s:
            lab.set_color(INK_2)
            lab.set_fontsize(10.5)
    # group captions on the right margin
    for g in GROUP_ORDER:
        idx = np.flatnonzero(d["group"] == g)
        if len(idx):
            ax.text(1.0, y_positions[idx].mean(), g, transform=ax.get_yaxis_transform(), ha="left",
                    va="center", fontsize=10.5, color=MUTED, fontstyle="italic")
    ax.set_xlim(0, 72)
    ax.set_ylim(y_positions.min() - 0.6, 0.6)
    ax.set_xlabel("plusz győzelem szezononként (futam); vonal: 95%-os bizonytalansági tartomány")
    ax.grid(axis="y", visible=False)
    return fig


def lever_strip(led: pd.DataFrame, focus: str):
    """Small "you are here" strip: the five levers, the focus one in violet."""
    rows = [(k, v) for k, v in figdata.LEVER_STRIP.items()]
    d = led.set_index("lever_id")
    fig, ax = plt.subplots(figsize=(3.6, 1.55))
    for i, (k, lab) in enumerate(rows):
        v = d.loc[k, "extra_wins"]
        ax.barh(-i, v, height=0.62, color=WRFT if k == focus else FIELD_LIGHT, edgecolor="none")
        ax.text(-1, -i, lab, ha="right", va="center", fontsize=9.5,
                color=INK if k == focus else MUTED, fontweight="bold" if k == focus else "normal")
        ax.text(v + 0.8, -i, "+" + num(v, 0), va="center", fontsize=9.5, color=INK if k == focus else MUTED)
    ax.set_xlim(0, 36)
    ax.axis("off")
    return fig


# --- 5. Saturday vs Sunday ------------------------------------------------------------------------

def day_slope(pairs: pd.DataFrame, totals: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(6.2, 4.9))
    for r in pairs.itertuples():
        ax.plot([0, 1], [r.clean_1, r.clean_2], color=WRFT_LIGHT, lw=1.1, alpha=0.8, zorder=1)
    tot = totals.pivot(index="group", columns="day", values="mean")
    for group, colour, lab in (("field", FIELD, "mezőny"), ("WRFT", WRFT, "WRFT")):
        a, b = tot.loc[group, 1], tot.loc[group, 2]
        ax.plot([0, 1], [a, b], color=colour, lw=3.2, zorder=3, marker="o", markersize=9,
                markeredgecolor=SURFACE, markeredgewidth=2)
        off = 0.022 if group == "field" else -0.022
        ax.text(1.06, b + off, f"{lab}  {num(100 * a, 0)}% → {num(100 * b, 0)}%", va="center", fontsize=11.5,
                color=INK, fontweight="bold")
    ax.set_xticks([0, 1], ["1. nap (szombat)", "2. nap (vasárnap)"])
    ax.set_xlim(-0.15, 1.95)
    ax.set_ylim(0, 1)
    hu_axis(ax, "y", 0, percent=True)
    ax.set_ylabel("hibátlan futamok aránya")
    ax.grid(axis="x", visible=False)
    ax.text(1.06, 0.06, "halvány vonal = egy WRFT-csapat\negy kétnapos versenyen", fontsize=10, color=INK_2)
    return fig


# --- 6. Dogs: speed vs reliability -----------------------------------------------------------------

def dog_quadrant(card: pd.DataFrame, names: list[str], core: list[str], min_runs: int = 20):
    c = card[card["valid_runs"] >= min_runs]
    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    size = 25 + 140 * c["valid_runs"] / c["valid_runs"].max()
    focus = c["dog"].isin(names) | c["dog"].isin(core)
    ax.scatter(c.loc[~focus, "median_run"], 100 * c.loc[~focus, "any_fault_eb"], s=size[~focus], color=FIELD_LIGHT,
               edgecolor=SURFACE, linewidth=2, zorder=2, label="többi kutya")
    for group, colour, lab in ((names, FAULT, "edzéssel javítandó"), (core, WRFT, "a legjobb négyes tagja")):
        m = c["dog"].isin(group)
        ax.scatter(c.loc[m, "median_run"], 100 * c.loc[m, "any_fault_eb"], s=size[m], color=colour,
                   edgecolor=SURFACE, linewidth=2, zorder=3, label=lab)
    ax.set_ylim(top=100 * c["any_fault_eb"].max() + 2.5)
    ax.axvline(c["median_run"].median(), color=style.AXIS, linewidth=0.8)
    ax.axhline(100 * c["any_fault_eb"].median(), color=style.AXIS, linewidth=0.8)
    ax.invert_xaxis()
    from flyball.plots.phase3 import label_points
    sel = c[focus]
    label_points(ax, sel["median_run"], 100 * sel["any_fault_eb"], sel["dog"].tolist(), fontsize=10.5)
    for tx, ty, txt in ((0.98, 0.97, "gyors, de hibázik"), (0.02, 0.97, "lassabb és hibázik"),
                        (0.98, 0.03, "gyors és megbízható"), (0.02, 0.03, "lassabb, de megbízható")):
        ax.text(tx, ty, txt, transform=ax.transAxes, ha="right" if tx > 0.5 else "left",
                va="top" if ty > 0.5 else "bottom", fontsize=10, color=MUTED)
    hu_axis(ax, "x", 1)
    hu_axis(ax, "y", 0)
    ax.set_xlabel("jellemző (medián) futási idő (mp)   ← lassabb   gyorsabb →")
    ax.set_ylabel("hibaarány rajtban, váltásban, futásban (%, korrigált)")
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.13), ncols=3, fontsize=10.5, markerscale=0.7)
    return fig


# --- 7. Start and pass window ---------------------------------------------------------------------

def pass_window(window: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.0), sharey=True)
    ymax = max(20, 100 * window["fault_ci_high"].max() + 2)
    titles = {"start": ("Rajt: a korai rajtok aránya", "a kutya jellemző rajtideje (mp)"),
              "pass": ("Váltás: a korai váltások aránya", "a kutya jellemző váltási ideje (mp; az „ok” váltás = 0)")}
    for ax, kind in zip(axes, ("start", "pass")):
        w = window[window["kind"] == kind]
        xs = w["median_time_s"].to_numpy()
        win = w[w["is_window"]]
        ax.axvspan(win["median_time_s"].iloc[0] - 0.015, win["median_time_s"].iloc[0] + 0.015,
                   color=GOOD, alpha=0.18, linewidth=0)
        ax.vlines(xs, 100 * w["fault_ci_low"], 100 * w["fault_ci_high"], color=FAULT, linewidth=2, alpha=0.5)
        ax.plot(xs, 100 * w["fault_rate"], color=FAULT, marker="o", markersize=7, markeredgecolor=SURFACE,
                markeredgewidth=2)
        ax.set_ylim(0, ymax)
        hu_axis(ax, "x", 2)
        hu_axis(ax, "y", 0)
        ax.set_xlabel(titles[kind][1])
        ax.set_title(titles[kind][0], pad=8)
    axes[0].set_ylabel("hibaarány (%)")
    axes[1].text(0.99, 0.97, "zöld sáv: itt a legkisebb a várható időveszteség\n(idő + a hibák miatti újrafutás)", transform=axes[1].transAxes,
                 ha="right", va="top", fontsize=10, color=INK_2)
    fig.tight_layout(w_pad=3)
    return fig


# --- 8. Line-up: stability and height dog -------------------------------------------------------

def stability_bars(stab: pd.DataFrame, a_team: list[str], n: int = 8):
    d = stab.sort_values("share_of_resamples", ascending=False).head(n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(5.4, 3.6))
    colours = [WRFT if dog in a_team else FIELD_LIGHT for dog in d["dog"]]
    ax.barh(d["dog"], d["share_of_resamples"], color=colours, height=0.6)
    for i, v in enumerate(d["share_of_resamples"]):
        ax.text(v + 0.02, i, num(100 * v, 0) + "%", va="center", fontsize=11, color=INK)
    ax.set_xlim(0, 1.18)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.grid(False)
    return fig


def height_dog(height: pd.DataFrame):
    d = height.sort_values("gain_vs_without_s").reset_index(drop=True)
    y = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.axvline(0, color=style.AXIS, lw=1)
    ax.barh(y + 0.19, d["hurdle_saving_s"], height=0.36, color=GOOD, label="ennyit nyernek a társak az alacsonyabb akadályon")
    ax.barh(y - 0.19, d["gain_vs_without_s"], height=0.36, color=FAULT, label="ennyit nyer vagy veszít összesen a legjobb csapat")
    for i, r in d.iterrows():
        ax.text(r["hurdle_saving_s"] + 0.05, i + 0.19, num(r["hurdle_saving_s"], 2, True), va="center", fontsize=10,
                color=INK_2)
        ax.text(r["gain_vs_without_s"] - 0.05, i - 0.19, num(r["gain_vs_without_s"], 2, True), va="center",
                ha="right", fontsize=10, color=INK_2)
    ax.set_yticks(y, [f"{r.height_dog} ({num(r.height_cm, 1).replace(',0', '')} cm)" for r in d.itertuples()])
    ax.set_xlim(d["gain_vs_without_s"].min() - 0.7, d["hurdle_saving_s"].max() + 0.6)
    hu_axis(ax, "x", 1)
    ax.set_xlabel("mp / futam (+ = gyorsabb)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper left", fontsize=9.5, bbox_to_anchor=(0, -0.2), ncols=1)
    return fig


def lineup_breakdown(rows: pd.DataFrame):
    d = rows.iloc[::-1].reset_index(drop=True)
    parts = [("start_s", "rajt", MUTED), ("runs_s", "4 futás", WRFT),
             ("passes_s", "3 váltás", INK_2), ("fault_s", "a hibák várható időköltsége", FAULT)]
    fig, ax = plt.subplots(figsize=(12.4, 0.5 * len(d) + 1.4))
    left = np.zeros(len(d))
    for col, label, colour in parts:
        ax.barh(d.index, d[col], left=left, color=colour, height=0.62, label=label, edgecolor=SURFACE, linewidth=2)
        left += d[col].to_numpy()
    for i, r in d.iterrows():
        ax.text(r["expected_s"] + 0.2, i, f"{num(r['expected_s'], 1)} mp   hibátlan: {num(100 * r['p_clean'], 0)}%",
                va="center", fontsize=10.5, color=INK_2)
    ax.set_yticks(d.index, d["label"], fontsize=10.5)
    ax.set_xlim(0, d["expected_s"].max() * 1.25)
    hu_axis(ax, "x", 0)
    ax.set_xlabel("várható futamidő (mp)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper left", ncols=4, bbox_to_anchor=(0, -0.7 / len(d) - 0.08))
    return fig


# --- 9. Q1 lanes and Q2 partner -----------------------------------------------------------------

def lane_slopes(dogs: pd.DataFrame, margin: float, n_labels: int = 3):
    d = dogs.sort_values("red_median")
    fig, ax = plt.subplots(figsize=(5.4, 5.0))
    for r in d.itertuples():
        ax.plot([0, 1], [r.red_median, r.blue_median], color=FIELD_LIGHT, lw=1.2, zorder=1)
    ax.scatter(np.zeros(len(d)), d["red_median"], s=36, color=style.LANE["red"], zorder=2, edgecolor=SURFACE, lw=1)
    ax.scatter(np.ones(len(d)), d["blue_median"], s=36, color=style.LANE["blue"], zorder=2, edgecolor=SURFACE, lw=1)
    big = d.reindex(d["blue_minus_red"].abs().sort_values(ascending=False).index[:n_labels])
    for r in big.itertuples():
        ax.annotate(f"{r.dog} {num(r.blue_minus_red, 2, True)}", (1, r.blue_median), xytext=(8, 0),
                    textcoords="offset points", va="center", fontsize=10, color=INK_2)
    ax.set_xticks([0, 1], ["piros pálya", "kék pálya"])
    ax.set_xlim(-0.3, 1.75)
    ax.invert_yaxis()
    hu_axis(ax, "y", 1)
    ax.set_ylabel("jellemző futási idő (mp), fent a gyorsabb")
    ax.grid(axis="x", visible=False)
    return fig


PARTNER_OUTCOMES = {"pass time (racing passes, <= 1 s)": ("Váltási idő", "mp", 1),
                    "early-pass rate": ("Korai váltások aránya", "százalékpont", 100),
                    "held-pass rate (> 1 s)": ("Visszatartott váltás (> 1 mp)", "százalékpont", 100)}


def partner_forest(contrasts: pd.DataFrame, spec: str = "category, adjusted for age and team"):
    levels = ["neutered female", "intact male", "intact female"]
    fig, axes = plt.subplots(1, len(PARTNER_OUTCOMES), figsize=(7.4, 3.6), sharey=True)
    for ax, (outcome, (title, unit, k)) in zip(axes, PARTNER_OUTCOMES.items()):
        c = contrasts[(contrasts["outcome"] == outcome) & (contrasts["spec"] == spec)].set_index("level").loc[levels]
        y = np.arange(len(levels))[::-1]
        ax.axvline(0, color=style.AXIS, lw=1)
        ax.hlines(y, k * c["ci_low"], k * c["ci_high"], color=INK_2, lw=1.6)
        ax.scatter(k * c["estimate"], y, s=44, color=INK, zorder=3, edgecolor=SURFACE, linewidth=1.5)
        ax.set_title(title, fontsize=11.5, pad=6)
        ax.set_xlabel(unit, fontsize=10.5)
        ax.grid(axis="y", visible=False)
        hu_axis(ax, "x", 2 if k == 1 else 0)
        ax.xaxis.set_major_locator(plt.MaxNLocator(4))
    dogs = contrasts.drop_duplicates("level").set_index("level")["incoming_dogs"]
    axes[0].set_yticks(np.arange(len(levels))[::-1],
                       [f"{figdata.CATEGORY_HU[lv]}\n({dogs[lv]} kutya)" for lv in levels])
    fig.tight_layout(w_pad=1.2)
    return fig


def lane_ring_days(days: pd.DataFrame, overall: pd.DataFrame, margin: float):
    d = days.sort_values(["date", "ring"], na_position="first").reset_index(drop=True)
    labels = [f"{pd.Timestamp(r.date):%m.%d.} {figdata.short_competition(r.competition)}"
              + (f" {int(r.ring)}. ring" if pd.notna(r.ring) else "") for r in d.itertuples()]
    y = np.arange(len(d))[::-1]
    fig, ax = plt.subplots(figsize=(7.0, 5.6))
    ax.axvspan(-margin, margin, color=GRID, alpha=0.7, lw=0)
    ax.axvline(0, color=style.AXIS, lw=1)
    ax.hlines(y, d["ci_low_s"], d["ci_high_s"], color=INK_2, lw=1.4)
    ax.scatter(d["seconds"], y, s=30, color=INK, zorder=3, edgecolor=SURFACE, linewidth=1.2)
    ax.set_yticks(y, labels, fontsize=9)
    ax.set_xlim(-0.1, 0.1)
    hu_axis(ax, "x", 2)
    ax.set_xlabel("kék pálya − piros pálya, mp futásonként (pozitív: a kéken lassabb)")
    ax.grid(axis="y", visible=False)
    return fig


# --- 10. Weather -------------------------------------------------------------------------------------

def heat_curve(curve: pd.DataFrame, pdp: pd.DataFrame, hinge: float):
    fig, ax = plt.subplots(figsize=(7.4, 4.3))
    ax.axhline(0, color=style.AXIS, lw=1)
    ax.axvline(hinge, color=style.AXIS, lw=1)
    ax.vlines(curve["temp_c"], curve["ci_low"], curve["ci_high"], color=INK_2, lw=1.5)
    ax.scatter(curve["temp_c"], curve["mean_pct"], s=14 + curve["runs"] / 40, color=INK, zorder=3,
               edgecolor=SURFACE, linewidth=1.5, label="átlag kétfokonként (a pont mérete: a futások száma)")
    t = pdp[pdp["feature"] == "temp_c"]
    ax.plot(t["value"], t["pct"], color=WRFT, lw=2.4, label="gépi tanulási modell görbéje")
    ax.text(hinge + 0.3, 0.04, f"{num(hinge, 0)} °C", transform=ax.get_xaxis_transform(), color=INK_2, fontsize=10.5)
    hu_axis(ax, "x", 0)
    hu_axis(ax, "y", 1)
    ax.set_xlabel("léghőmérséklet a futam idején (°C)")
    ax.set_ylabel("ennyivel lassabb a kutya a saját szintjénél (%)")
    ax.legend(loc="upper left", fontsize=10.5)
    return fig


WEATHER_CONTRASTS = {"temperature +10 °C (below 20 °C)": "hőmérséklet +10 °C (20 °C alatt)",
                     "temperature +10 °C (above 20 °C)": "hőmérséklet +10 °C (20 °C felett)",
                     "humidity +20 pp": "páratartalom +20 százalékpont",
                     "wind +3 m/s": "szél +3 m/s",
                     "rain in the last 3 h": "eső az elmúlt 3 órában"}


def weather_forest(effects: pd.DataFrame, margin: float):
    e = effects[(effects["model"] == "within competition") & (effects["outcome"] == "run time")]
    contrasts = list(WEATHER_CONTRASTS)
    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    ax.axvspan(-margin, margin, color=GRID, alpha=0.7, lw=0)
    ax.axvline(0, color=style.AXIS, lw=1)
    for j, (sample, colour, lab) in enumerate((("field", INK, "mezőny (minden kutya)"), ("WRFT", WRFT, "WRFT-kutyák"))):
        c = e[e["sample"] == sample].set_index("contrast").loc[contrasts]
        y = np.arange(len(contrasts))[::-1] + (0.15 if j == 0 else -0.15)
        ax.hlines(y, c["ci_low"], c["ci_high"], color=colour, lw=1.8)
        ax.scatter(c["estimate"], y, s=46, color=colour, zorder=3, edgecolor=SURFACE, linewidth=1.5, label=lab)
    ax.set_yticks(np.arange(len(contrasts))[::-1], [WEATHER_CONTRASTS[c] for c in contrasts])
    hu_axis(ax, "x", 2)
    ax.set_xlabel("változás a futási időben (mp / kutya / futás)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", fontsize=10)
    ax.text(margin, len(contrasts) - 0.45, f" ±{num(margin, 2)} mp: ennél kisebb hatás nem számít", fontsize=9.5,
            color=MUTED, va="bottom")
    ax.set_ylim(-0.6, len(contrasts) - 0.1)
    return fig


def weather_vs_venue(days: pd.DataFrame):
    d = days.copy()
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    ax.axhline(0, color=style.AXIS, lw=1)
    ax.vlines(d["temp_mean_c"], d["ci_low"], d["ci_high"], color=FIELD_LIGHT, lw=1.5)
    ax.scatter(d["temp_mean_c"], d["pct"], s=44, color=INK, zorder=3, edgecolor=SURFACE, linewidth=1.5,
               label="versenynap (ringenként), 95%-os tartomány")
    ax.scatter(d["temp_mean_c"], d["fitted_pct"], s=60, marker="_", linewidth=2.2, color=WRFT, zorder=2,
               label="az időjárás és az évszak alapján várható")
    hu_axis(ax, "x", 0)
    hu_axis(ax, "y", 1)
    ax.set_xlabel("átlaghőmérséklet a versenyen (°C)")
    ax.set_ylabel("lassabb (+) / gyorsabb (−) egy átlagos napnál (%)")
    ax.legend(loc="upper left", fontsize=10)
    return fig


# --- 11. Per competition ---------------------------------------------------------------------------

def competition_panels(days: pd.DataFrame):
    """Three stacked panels per WRFT competition day: win rate (CI), clean heats, dog-adjusted speed."""
    d = days.reset_index(drop=True)
    event = (d["competition"] != d["competition"].shift()).cumsum()
    x = np.arange(len(d)) + (event.to_numpy() - 1) * 0.5
    fig, axes = plt.subplots(3, 1, figsize=(12.4, 5.6), sharex=True, gridspec_kw={"hspace": 0.4})
    ax = axes[0]
    ax.vlines(x, 100 * d["win_ci_low"], 100 * d["win_ci_high"], color=WRFT, lw=1.6, alpha=0.45)
    ax.scatter(x, 100 * d["win_rate"], s=40, color=WRFT, zorder=3, edgecolor=SURFACE, linewidth=1.5)
    below = d["below_peers"].to_numpy()
    ax.scatter(x[below], 100 * d.loc[below, "win_rate"], s=95, facecolor="none", edgecolor=FAULT, lw=2, zorder=4)
    ax.axhline(50, color=style.AXIS, lw=1)
    ax.set_ylim(0, 85)
    ax.set_ylabel("győzelem %", fontsize=11)
    ax = axes[1]
    ax.bar(x, 100 * d["clean_heat_rate"], width=0.5, color=FIELD)
    ax.set_ylabel("hibátlan futam %", fontsize=11)
    ax.set_ylim(0, 85)
    ax = axes[2]
    ax.axhline(0, color=style.AXIS, lw=1)
    ax.scatter(x, d["speed_index_field_pct"], s=28, color=FIELD, label="mezőny")
    ax.scatter(x, d["speed_index_wrft_pct"], s=40, color=WRFT, label="WRFT-kutyák", edgecolor=SURFACE, lw=1.2)
    ax.set_ylabel("sebesség %\n(− = gyorsabb)", fontsize=11)
    hu_axis(ax, "y", 0)
    ax.legend(loc="lower left", ncols=2, fontsize=10, bbox_to_anchor=(0, -0.02))
    ax.set_xticks(x, [w[:3] for w in d["weekday"]], fontsize=9.5)
    for _, grp in d.groupby(event):
        xs = x[grp.index]
        ax.text(xs.mean(), -0.5, grp["event"].iloc[0], transform=ax.get_xaxis_transform(), ha="center", va="top",
                fontsize=10, color=INK_2)
    for a in axes:
        a.grid(axis="x", visible=False)
    return fig


def dog_competition_heatmap(dog_comp: pd.DataFrame, min_competitions: int = 3, clip: float = 0.3):
    d = dog_comp[dog_comp["valid_runs"] >= 5]
    keep = d.groupby("dog")["competition"].nunique()
    d = d[d["dog"].isin(keep[keep >= min_competitions].index)]
    order_c = d.groupby("competition")["first_date"].min().sort_values().index
    order_d = d.groupby("dog")["season_median"].first().sort_values().index
    grid = d.pivot(index="dog", columns="competition", values="vs_season_s").loc[order_d, order_c]
    cmap = LinearSegmentedColormap.from_list("faster_slower", [GOOD, MIDPOINT, FAULT])
    cmap.set_bad(SURFACE)
    fig, ax = plt.subplots(figsize=(8.6, 0.2 * len(grid) + 1.6))
    im = ax.imshow(grid.to_numpy(dtype=float), cmap=cmap, vmin=-clip, vmax=clip, aspect="auto")
    ax.set_xticks(range(len(order_c)), [figdata.short_competition(c) for c in order_c], rotation=30, ha="right",
                  fontsize=10)
    ax.set_yticks(range(len(order_d)), order_d, fontsize=8.5)
    ax.set_xticks(np.arange(-0.5, len(order_c)), minor=True)
    ax.set_yticks(np.arange(-0.5, len(order_d)), minor=True)
    ax.grid(which="minor", color=SURFACE, lw=2)
    ax.grid(which="major", visible=False)
    ax.tick_params(which="minor", length=0)
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    bar = fig.colorbar(im, ax=ax, shrink=0.5, pad=0.02, extend="both", format=lambda v, _: num(v, 1, True))
    bar.set_label("mp a saját szezonbeli értékéhez képest (− = gyorsabb)", fontsize=10)
    bar.outline.set_visible(False)
    return fig


# --- Appendix ----------------------------------------------------------------------------------------

MODEL_TERMS_HU = {"speed_gap": "lassabb szokásos tiszta idő (+1 mp)",
                  "start_gap": "lassabb szokásos rajtidő (+1 mp)",
                  "own_false_start": "saját korai rajt", "own_pass_fault": "saját korai váltás",
                  "own_run_fault": "saját futási hiba", "opp_false_start": "ellenfél korai rajtja",
                  "opp_pass_fault": "ellenfél korai váltása", "opp_run_fault": "ellenfél futási hibája"}


def heat_model_forest(model: pd.DataFrame):
    terms = list(MODEL_TERMS_HU)
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    ax.axvline(1, color=style.AXIS, lw=1)
    for j, (sample, colour, lab) in enumerate((("field", INK, "mezőny"), ("wrft", WRFT, "WRFT-futamok"))):
        m = model[model["sample"] == sample].set_index("term").loc[terms]
        y = np.arange(len(terms))[::-1] + (0.15 if j == 0 else -0.15)
        ax.hlines(y, m["ci_low"], m["ci_high"], color=colour, lw=1.8)
        ax.scatter(m["estimate"], y, s=44, color=colour, zorder=3, edgecolor=SURFACE, lw=1.5, label=lab)
    ax.set_xscale("log")
    ax.set_xticks([0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8], ["0,05", "0,1", "0,25", "0,5", "1", "2", "4", "8"])
    ax.minorticks_off()
    ax.set_yticks(np.arange(len(terms))[::-1], [MODEL_TERMS_HU[t] for t in terms])
    ax.set_xlabel("esélyhányados (logaritmikus skála; 1 alatt kisebb a győzelem esélye)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper right", fontsize=10)
    return fig


OUTCOME_GROUPS_HU = {"győzelem": (["win_clean", "win_after_fault"], GOOD),
                     "vereség: saját hiba": (["loss_fault", "loss_uncoded_rerun"], FAULT),
                     "vereség: hibátlan, de lassabb": (["loss_slower"], FIELD),
                     "vereség: egyéb": (["loss_breakout_like", "loss_not_finished"], FIELD_LIGHT)}


def heat_outcomes(attr: pd.DataFrame):
    a = attr.copy()
    a["label"] = a["group"].map(lambda g: "Mezőny (nem WRFT)" if g.startswith("Field") else
                                ("WRFT összesen" if g.startswith("WRFT") or g == "WildRunners (all)" else figdata.short_team(g)))
    shares = pd.DataFrame({seg: a[cols].sum(axis=1) / a["heats"] for seg, (cols, _) in OUTCOME_GROUPS_HU.items()})
    fig, ax = plt.subplots(figsize=(7.6, 0.42 * len(a) + 1.4))
    y = np.arange(len(a))[::-1]
    left = np.zeros(len(a))
    for seg, (_, colour) in OUTCOME_GROUPS_HU.items():
        w = shares[seg].to_numpy()
        ax.barh(y, w, left=left, height=0.62, color=colour, edgecolor=SURFACE, linewidth=2, label=seg)
        for yi, li, wi in zip(y, left, w):
            if wi >= 0.09:
                ax.text(li + wi / 2, yi, num(100 * wi, 0) + "%", ha="center", va="center", fontsize=10,
                        color="white" if colour in (FAULT, FIELD) else INK)
        left += w
    ax.set_yticks(y, a["label"])
    ax.set_xlim(0, 1)
    hu_axis(ax, "x", 0, percent=True)
    ax.grid(axis="y", visible=False)
    ax.legend(ncols=2, loc="upper left", bbox_to_anchor=(0, -0.08), fontsize=10)
    return fig


TEAM_METRICS_HU = {"win_rate": "győzelem", "clean_heat_rate": "hibátlan futam", "false_start_rate": "korai rajt",
                   "pass_fault_rate": "korai váltás", "run_fault_rate": "futási hiba"}


def team_gaps(peer: pd.DataFrame):
    """Small multiples: each WRFT team's gap to its division peers per metric (pp), Holm-significant filled."""
    metrics_ = list(TEAM_METRICS_HU)
    teams = [t for t in peer["team"].unique()]
    teams = sorted(teams, key=lambda t: figdata.TEAM_ORDER.index(figdata.short_team(t)))
    fig, axes = plt.subplots(1, len(metrics_), figsize=(12.4, 3.6), sharey=True)
    y = np.arange(len(teams))[::-1]
    for ax, m in zip(axes, metrics_):
        p = peer[peer["metric"] == m].set_index("team").loc[teams]
        bad_up = m != "win_rate" and m != "clean_heat_rate"
        ax.axvline(0, color=style.AXIS, lw=1)
        ax.hlines(y, 100 * p["ci_low"], 100 * p["ci_high"], color=INK_2, lw=1.4)
        sig = (p["p_holm"] < 0.05).to_numpy()
        worse = (p["estimate"] > 0).to_numpy() if bad_up else (p["estimate"] < 0).to_numpy()
        colours = [FAULT if s and w else (GOOD if s else SURFACE) for s, w in zip(sig, worse)]
        ax.scatter(100 * p["estimate"], y, s=46, facecolor=colours, edgecolor=INK, lw=1.2, zorder=3)
        ax.set_title(TEAM_METRICS_HU[m], fontsize=11.5)
        hu_axis(ax, "x", 0, sign=True)
        ax.xaxis.set_major_locator(plt.MaxNLocator(4))
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(y, [figdata.short_team(t) for t in teams])
    fig.supxlabel("eltérés a divízió többi csapatától (százalékpont); színes pont: valódi, nem a véletlennek tulajdonítható eltérés", fontsize=10.5,
                  color=INK_2)
    fig.tight_layout()
    return fig


def lineup_backtest(heats: pd.DataFrame):
    c = heats.dropna(subset=["actual_clean_time"])
    fig, ax = plt.subplots(figsize=(5.6, 4.4))
    lo, hi = c[["actual_clean_time", "predicted_clean_time"]].quantile([0, 1]).values.ravel()[[0, -1]]
    ax.plot([lo, hi], [lo, hi], color=style.AXIS, lw=1)
    ax.scatter(c["predicted_clean_time"], c["actual_clean_time"], s=22, color=WRFT, alpha=0.7, edgecolor=SURFACE, lw=0.5)
    hu_axis(ax, "x", 0)
    hu_axis(ax, "y", 0)
    ax.set_xlabel("előre jelzett tiszta idő (mp)")
    ax.set_ylabel("valódi tiszta idő (mp)")
    return fig


def build_all(f: dict) -> dict[str, Path]:
    """Render every Phase 6 chart from the tables in `f` (see report/deck.py for the inputs)."""
    apply()
    out = {}
    led = f["ledger"]
    out["season_calendar"] = save(season_calendar(f["days"], f["field_clean"]), "season_calendar")
    out["heat_strip"] = save(heat_strip(f["heat_pair"]), "heat_strip")
    out["what_wins"] = save(what_wins(f["win_by_fault"], f["win_by_gap"]), "what_wins")
    out["impact_ledger"] = save(impact_ledger(led), "impact_ledger")
    for k in figdata.LEVER_STRIP:
        name = "strip_" + k.split("|")[0]
        out[name] = save(lever_strip(led, k), name)
    out["day_slope"] = save(day_slope(f["day_pairs"], f["day_totals"]), "day_slope")
    out["dog_quadrant"] = save(dog_quadrant(f["cards"], f["quadrant_names"], f["a_team"]), "dog_quadrant")
    out["pass_window"] = save(pass_window(f["pass_window"]), "pass_window")
    out["stability"] = save(stability_bars(f["stability"], f["a_team"]), "stability")
    out["height_dog"] = save(height_dog(f["height"]), "height_dog")
    out["lineup_breakdown"] = save(lineup_breakdown(f["breakdown"]), "lineup_breakdown")
    out["lane_slopes"] = save(lane_slopes(f["lane_dogs"], f["lane_margin"]), "lane_slopes")
    out["lane_ring_days"] = save(lane_ring_days(f["lane_days"], f["lane_overall"], f["lane_margin"]), "lane_ring_days")
    out["partner_forest"] = save(partner_forest(f["partner"]), "partner_forest")
    out["heat_curve"] = save(heat_curve(f["weather_curve"], f["weather_pdp"], f["hinge"]), "heat_curve")
    out["weather_forest"] = save(weather_forest(f["weather_effects"], f["lane_margin"]), "weather_forest")
    out["weather_vs_venue"] = save(weather_vs_venue(f["weather_days"]), "weather_vs_venue")
    out["competition_panels"] = save(competition_panels(f["days"]), "competition_panels")
    out["dog_heatmap"] = save(dog_competition_heatmap(f["dog_comp"]), "dog_heatmap")
    out["heat_model"] = save(heat_model_forest(f["heat_model"]), "heat_model")
    out["heat_outcomes"] = save(heat_outcomes(f["attribution"]), "heat_outcomes")
    out["team_gaps"] = save(team_gaps(f["peer"]), "team_gaps")
    out["lineup_backtest"] = save(lineup_backtest(f["backtest_heats"]), "lineup_backtest")
    return out
