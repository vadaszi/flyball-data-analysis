"""Phase 3 draft figures. Each function takes a result table and returns a figure.

Drafts: the layout and encoding are final-ish, polishing happens in Phase 6.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from flyball.plots import style
from flyball.plots.style import FAULT, FIELD, FIELD_LIGHT, GOOD, INK, INK_2, WRFT


def short_team(name: str) -> str:
    """'WildRunners dreamers' -> 'Dreamers' (other labels are kept as they are)."""
    short = name.replace("WildRunners ", "")
    return short[:1].upper() + short[1:]


def label_points(ax, xs, ys, texts, fontsize=9):
    """Direct labels next to points, trying four offsets to avoid overlapping
    a label that is already placed (a simple greedy placement)."""
    placed = []
    offsets = [(6, 5, "left"), (6, -13, "left"), (-6, 5, "right"), (-6, -13, "right")]
    for x, y, text in sorted(zip(xs, ys, texts), key=lambda t: -t[1]):
        px, py = ax.transData.transform((x, y))
        width, height = 0.62 * fontsize * len(text), 1.3 * fontsize
        for dx, dy, ha in offsets:
            x0 = px + dx - (width if ha == "right" else 0)
            box = (x0, py + dy, x0 + width, py + dy + height)
            if not any(box[0] < b[2] and b[0] < box[2] and box[1] < b[3] and b[1] < box[3] for b in placed):
                break
        placed.append(box)
        ax.annotate(text, (x, y), xytext=(dx, dy), textcoords="offset points",
                    ha=ha, fontsize=fontsize, color=INK)


# --- 1. Why heats are won and lost -----------------------------------------------------

OUTCOME_GROUPS = {   # plotted segment: (reasons, colour)
    "Won": (["win_clean", "win_after_fault"], GOOD),
    "Lost: own fault": (["loss_fault", "loss_uncoded_rerun"], FAULT),
    "Lost: clean, slower": (["loss_slower"], FIELD),
    "Lost: other": (["loss_breakout_like", "loss_not_finished"], FIELD_LIGHT),
}


def heat_outcomes(summary: pd.DataFrame, label_col: str):
    """100 % bars: share of heats won, lost to own faults, lost clean."""
    shares = pd.DataFrame({seg: summary[cols].sum(axis=1) / summary["heats"]
                           for seg, (cols, _) in OUTCOME_GROUPS.items()})
    labels = summary[label_col].tolist()
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(labels) + 1.6))
    y = np.arange(len(labels))[::-1]
    left = np.zeros(len(labels))
    for seg, (_, colour) in OUTCOME_GROUPS.items():
        w = shares[seg].to_numpy()
        ax.barh(y, w, left=left, height=0.62, color=colour, edgecolor=style.SURFACE,
                linewidth=2, label=seg)
        for yi, li, wi in zip(y, left, w):
            if wi >= 0.08:
                text_colour = "white" if colour in (FAULT, FIELD) else INK
                ax.text(li + wi / 2, yi, f"{wi:.0%}", ha="center", va="center",
                        fontsize=8.5, color=text_colour)
        left += w
    ax.set_yticks(y, labels)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.grid(axis="y", visible=False)
    ax.set_title("Most lost heats are lost to the team's own faults", pad=26)
    style.subtitle(ax, "Share of decided heats by outcome and reason, 2023")
    ax.legend(ncol=4, loc="upper left", bbox_to_anchor=(0, -0.06 - 0.6 / len(labels)), fontsize=8.5)
    return fig


# --- 2. What wins heats ----------------------------------------------------------------

def what_wins(by_fault: pd.DataFrame, by_gap: pd.DataFrame):
    """Left: win rate by who faulted. Right: in clean-vs-clean heats, by speed gap."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.8), gridspec_kw={"width_ratios": [1, 1.25]})

    order = [("own clean", "opponent fault"), ("own clean", "opponent clean"),
             ("own fault", "opponent fault"), ("own fault", "opponent clean")]
    t = by_fault.set_index(["own", "opp"]).loc[order]
    y = np.arange(len(t))[::-1]
    colours = [GOOD, FIELD, FAULT, FAULT]
    a1.hlines(y, t["ci_low"], t["ci_high"], color=colours, linewidth=6, alpha=0.35)
    a1.scatter(t["win_rate"], y, s=60, color=colours, edgecolor=style.SURFACE, linewidth=2, zorder=3)
    for yi, (idx, row) in zip(y, t.iterrows()):
        a1.text(row["win_rate"], yi + 0.25, f"{row['win_rate']:.0%}", ha="center", fontsize=8.5, color=INK_2)
    a1.set_ylim(-0.5, len(t) - 0.3)
    a1.set_yticks(y, [f"{o.capitalize()},\n{p}" for o, p in order], fontsize=8.5)
    a1.set_xlim(0, 1)
    a1.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    a1.grid(axis="y", visible=False)
    coin, faulted = t.loc[order[1], "win_rate"], t.loc[order[3], "win_rate"]
    a1.set_title(f"One fault turns a {coin:.0%} coin flip into {faulted:.0%}", pad=22, fontsize=11)
    style.subtitle(a1, "Win rate of a team in a heat (95 % CI), all teams")

    mid = by_gap["gap_bin"].map(_bin_mid)
    a2.fill_between(mid, by_gap["ci_low"], by_gap["ci_high"], color=WRFT, alpha=0.10, linewidth=0)
    a2.plot(mid, by_gap["win_rate"], color=WRFT, marker="o", markersize=6,
            markeredgecolor=style.SURFACE, markeredgewidth=2)
    a2.axhline(0.5, color=style.AXIS, linewidth=0.8)
    a2.axvline(0, color=style.AXIS, linewidth=0.8)
    a2.set_ylim(0, 1)
    a2.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    a2.set_xlabel("Typical clean time, own − opponent (s)   ← faster   slower →")
    a2.set_title("When both run clean, speed decides", pad=22, fontsize=11)
    style.subtitle(a2, "Win rate in clean-vs-clean heats by the teams' typical speed gap")
    fig.tight_layout()
    return fig


def _bin_mid(label: str) -> float:
    lo, hi = (float(x) for x in label.strip("(]").split(","))
    if np.isinf(lo):
        return hi - 0.25
    if np.isinf(hi):
        return lo + 0.25
    return (lo + hi) / 2


# --- 3. Team speed vs reliability --------------------------------------------------------

def team_quadrant(peer: pd.DataFrame):
    """Each WRFT team vs its division peers: clean-time gap (x) and clean-heat gap (y)."""
    p = peer.pivot(index="team", columns="metric")
    x, y = p[("estimate", "clean_time_s")], 100 * p[("estimate", "clean_heat_rate")]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.axhline(0, color=style.AXIS, linewidth=0.8)
    ax.axvline(0, color=style.AXIS, linewidth=0.8)
    ax.errorbar(x, y, xerr=[x - p[("ci_low", "clean_time_s")], p[("ci_high", "clean_time_s")] - x],
                yerr=[y - 100 * p[("ci_low", "clean_heat_rate")], 100 * p[("ci_high", "clean_heat_rate")] - y],
                fmt="none", ecolor=WRFT, alpha=0.35, linewidth=1.2)
    ax.scatter(x, y, s=70, color=WRFT, edgecolor=style.SURFACE, linewidth=2, zorder=3)
    ax.invert_xaxis()                    # faster to the right
    lim = max(abs(y).max() + 8, 15)
    ax.set_ylim(-lim, lim)
    label_points(ax, x, y, [short_team(t) for t in p.index])
    for tx, ty, txt in ((0.98, 0.97, "Faster & cleaner"), (0.02, 0.97, "Slower but cleaner"),
                        (0.98, 0.03, "Faster but faultier"), (0.02, 0.03, "Slower & faultier")):
        ax.text(tx, ty, txt, transform=ax.transAxes, ha="right" if tx > 0.5 else "left",
                va="top" if ty > 0.5 else "bottom", fontsize=8.5, color=style.MUTED)
    ax.set_xlabel("Median clean time vs division peers (s)   ← slower   faster →")
    ax.set_ylabel("Clean-heat rate vs peers (percentage points)")
    ax.set_title("WRFT teams against the teams they actually raced", pad=22)
    style.subtitle(ax, "Within competition × division, 95 % CIs clustered on team")
    return fig


# --- 4. Start and pass window -------------------------------------------------------------

def pass_window(window: pd.DataFrame, profiles: dict[str, pd.DataFrame]):
    """Fault rate by how tight a dog usually starts / passes; WRFT dogs as a rug."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.1), sharey=True)
    ymax = max(20, 100 * window["fault_ci_high"].max() + 2)
    titles = {"start": ("Starts", "false-start rate", "Dog's median start (s)"),
              "pass": ("Passes", "early-pass rate", "Dog's median pass (s, ok = 0)")}
    for ax, kind in zip(axes, ("start", "pass")):
        w = window[window["kind"] == kind]
        xs = w["median_time_s"].to_numpy()
        win = w[w["is_window"]]
        ax.axvspan(win["median_time_s"].iloc[0] - 0.015, win["median_time_s"].iloc[0] + 0.015,
                   color=GOOD, alpha=0.15, linewidth=0)
        ax.vlines(xs, 100 * w["fault_ci_low"], 100 * w["fault_ci_high"], color=FAULT, linewidth=2, alpha=0.5)
        ax.plot(xs, 100 * w["fault_rate"], color=FAULT, marker="o", markersize=6,
                markeredgecolor=style.SURFACE, markeredgewidth=2)
        wd = profiles[kind]
        wd = wd[wd["is_wrft_dog"]]
        ax.plot(wd["median_time_s"], np.full(len(wd), 0.6), "|", color=WRFT, markersize=12, alpha=0.8)
        ax.set_ylim(0, ymax)
        ax.set_xlim(-0.02, min(0.6, max(xs.max(), wd["median_time_s"].max()) + 0.05))
        name, rate, xlabel = titles[kind]
        ax.set_xlabel(xlabel)
        ax.set_title(f"{name}: {rate}", fontsize=11)
    axes[0].set_ylabel("Fault rate (%)")
    axes[1].text(0.99, 0.97, "| WRFT dogs' medians", transform=axes[1].transAxes, ha="right",
                 va="top", color=INK_2, fontsize=8.5)
    fig.suptitle("Tight passes carry fault risk; good starters are both quick and safe",
                 x=0.01, ha="left", fontweight="bold", fontsize=12)
    fig.text(0.01, 0.905, "All dogs with ≥20 attempts, grouped by their median time (95 % CI). "
             "Shaded: group with the lowest expected cost (time on the line + faults × rerun cost)",
             color=INK_2, fontsize=8.5)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    return fig


# --- 5. Dogs: speed vs reliability -------------------------------------------------------

def dog_quadrant(card: pd.DataFrame, min_runs: int = 20, n_labels: int = 8):
    """WRFT dogs: median run (x) vs shrunken fault rate (y); extremes labelled."""
    c = card[card["valid_runs"] >= min_runs]
    fig, ax = plt.subplots(figsize=(8, 5.2))
    size = 20 + 120 * c["valid_runs"] / c["valid_runs"].max()
    ax.scatter(c["median_run"], 100 * c["any_fault_eb"], s=size, color=WRFT, alpha=0.75,
               edgecolor=style.SURFACE, linewidth=2, zorder=3)
    ax.axvline(c["median_run"].median(), color=style.AXIS, linewidth=0.8)
    ax.axhline(100 * c["any_fault_eb"].median(), color=style.AXIS, linewidth=0.8)
    k = n_labels // 2
    picks = pd.concat([c["median_run"].nsmallest(k), c["any_fault_eb"].nsmallest(k),
                       c["any_fault_eb"].nlargest(k)]).index.unique()
    ax.invert_xaxis()
    label_points(ax, c.loc[picks, "median_run"], 100 * c.loc[picks, "any_fault_eb"],
                 c.loc[picks, "dog"].tolist(), fontsize=8.5)
    ax.set_xlabel("Median run time (s)   ← slower   faster →")
    ax.set_ylabel("Faults per start/pass/run (%, shrunken)")
    ax.set_title("WRFT dogs: speed against reliability", pad=22)
    style.subtitle(ax, f"Dogs with ≥{min_runs} valid runs; dot size = runs; lines = WRFT medians; bottom right = fast and reliable")
    return fig


# --- 6. Position and hurdle effects -----------------------------------------------------

TERM_LABELS = {"C(position)[T.2]": "Position 2 vs 1", "C(position)[T.3]": "Position 3 vs 1",
               "C(position)[T.4]": "Position 4 vs 1", "hurdle_step": "Hurdle +2.5 cm"}


def dog_effects(effects: pd.DataFrame):
    """Forest plot of within-dog effects in seconds per run, WRFT vs field (mixed model)."""
    e = effects[effects["model"] == "mixed"]
    fig, ax = plt.subplots(figsize=(7, 3.4))
    terms = list(TERM_LABELS)
    y = np.arange(len(terms))[::-1]
    for offset, (group, colour) in zip((0.14, -0.14), (("WRFT", WRFT), ("Field", FIELD))):
        g = e[e["group"] == group].set_index("term").loc[terms]
        base = g["seconds_at_median"] / g["pct"]          # seconds per 1 %
        ax.hlines(y + offset, g["pct_low"] * base, g["pct_high"] * base, color=colour, linewidth=2)
        ax.scatter(g["seconds_at_median"], y + offset, s=50, color=colour, edgecolor=style.SURFACE,
                   linewidth=2, zorder=3, label=group)
    ax.axvline(0, color=style.AXIS, linewidth=0.8)
    ax.set_yticks(y, [TERM_LABELS[t] for t in terms])
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Change in a dog's run time (s), same dog, same day")
    step = e.set_index(["group", "term"]).loc[("Field", "hurdle_step"), "seconds_at_median"]
    ax.set_title(f"Position 1 is quickest; every hurdle step costs ~{step:.2f} s", pad=22)
    style.subtitle(ax, "Mixed model, dog random effect + competition-day fixed effects, 95 % CI")
    ax.legend(loc="lower right")
    return fig
