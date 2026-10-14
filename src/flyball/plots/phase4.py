"""Phase 4 draft figures. Colour roles come from `style` (dataviz skill).

- Neutral ink wherever a panel holds a single measure named by its title
  (weather strip, forest plots): no hue is needed for identity.
- Red and blue appear only where they mean the lanes (Q1).
- WRFT is violet against the grey field (Q3).
- 4B: field estimates in ink, WRFT in violet; the line-up breakdown uses
  violet for the dogs' runs, greys for start and passes, orange for the
  expected fault cost; the height-dog chart uses aqua for the hurdle saving
  and orange for the net loss.
- The dog x competition heatmap is diverging: aqua = faster than the dog's
  own season median, orange = slower, grey midpoint (validated: CVD ΔE 9.2;
  aqua is below 3:1 on the surface, so the colour bar and the CSV table twin
  carry the values).
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from flyball.plots import style

MIDPOINT = "#f0efec"     # neutral grey midpoint of the diverging scale


def short_competition(name: str) -> str:
    """Compact competition labels for crowded axes."""
    return {"Mistrovství České republiky": "Czech champ.", "Máchale, spadlo ti to!": "Máchale",
            "BCCCZ mistrovství": "BCCCZ champ.", "Flyvaryors turnaj": "Flyvaryors",
            "Budějckej xtreme": "Budějckej", "Křupky na břehu": "Křupky",
            "Hanácké škvarek": "Hanácké"}.get(name, name)


def event_positions(dates: pd.Series) -> tuple[np.ndarray, pd.Series]:
    """x positions for date-ordered days: days of one event sit together, a gap between events."""
    event = (pd.to_datetime(dates).diff().dt.days.fillna(99) > 1).cumsum()
    return np.arange(len(dates)) + event.to_numpy() * 0.6, event


def weather_strip(day: pd.DataFrame):
    """Season calendar: one column per venue-day, three stacked panels sharing the x axis.

    `day` is weather_day.csv; rings at the same venue and date are merged.
    """
    d = day.drop_duplicates(["venue", "date"]).sort_values("date").reset_index(drop=True)
    d["date"] = pd.to_datetime(d["date"])
    x, event = event_positions(d["date"])

    fig, axes = plt.subplots(3, 1, figsize=(11, 7.2), sharex=True,
                             gridspec_kw={"height_ratios": [1.4, 1, 1], "hspace": 0.45})
    ax = axes[0]
    ax.vlines(x, d["temp_min_c"], d["temp_max_c"], color=style.MUTED, linewidth=6, capstyle="round")
    ax.scatter(x, d["temp_mean_c"], s=36, color=style.INK, zorder=3, edgecolor=style.SURFACE, linewidth=1.5)
    ax.set_title("Temperature during racing (°C)", pad=16)
    style.subtitle(ax, "bar = min to max over the racing hours, dot = mean")
    for col in ("temp_max_c", "temp_min_c"):            # label only the season's extremes
        i = d[col].idxmax() if col == "temp_max_c" else d[col].idxmin()
        ax.annotate(f"{d.loc[i, col]:.0f}°", (x[i], d.loc[i, col]), xytext=(8, 0), textcoords="offset points",
                    va="center", color=style.INK_2, fontsize=9)

    ax = axes[1]
    ax.bar(x, d["precip_total_mm"], width=0.6, color=style.INK_2)
    ax.set_title("Rain during racing (mm)", pad=16)
    style.subtitle(ax, "numbers above = rain in the 24 h before racing started (wet ground)")
    for i, (r, before) in enumerate(zip(d["precip_total_mm"], d["precip_24h_before_mm"])):
        if before >= 1:
            ax.text(x[i], r + 0.15, f"{before:.0f}", ha="center", va="bottom", fontsize=8, color=style.MUTED)
    ax.set_ylim(0, max(d["precip_total_mm"].max(), 1) * 1.35)

    ax = axes[2]
    ax.bar(x, d["wind_mean_ms"], width=0.6, color=style.INK_2, label="mean wind")
    ax.scatter(x, d["gust_max_ms"], marker="_", s=160, linewidth=2, color=style.INK, label="strongest gust")
    ax.set_title("Wind (m/s)")
    ax.legend(loc="upper left", ncols=2, fontsize=9, bbox_to_anchor=(0, 1.0))
    ax.set_ylim(0, d["gust_max_ms"].max() * 1.3)

    ax.set_xticks(x, [f"{t:%d}" for t in d["date"]], fontsize=8)
    for _, grp in d.groupby(event):
        xs = x[grp.index]
        name = grp["venue"].iloc[0].replace("Nové Město pod Smrkem", "Nové Město").replace("Tápiószentmárton", "Tápió-\nszentmárton")
        ax.text(xs.mean(), -0.32, f"{grp['date'].iloc[0]:%b}\n{name}", transform=ax.get_xaxis_transform(),
                ha="center", va="top", fontsize=8, color=style.INK_2)
    for a in axes:
        a.grid(axis="x", visible=False)
    fig.suptitle("Weather at the 2023 competitions (Open-Meteo reanalysis)", x=0.125, ha="left",
                 fontweight="bold", fontsize=13, y=0.995)
    return fig


# --- Q1: lane colour ---------------------------------------------------------------------

def lane_ring_days(days: pd.DataFrame, overall: pd.DataFrame, margin: float = 0.05):
    """Forest plot: blue-minus-red run-time effect per ring-day, with the equivalence band."""
    d = days.sort_values(["date", "ring"], na_position="first").reset_index(drop=True)
    labels = [f"{pd.Timestamp(r.date):%d %b}  {short_competition(r.competition)}"
              + (f" ring {int(r.ring)}" if pd.notna(r.ring) else "") for r in d.itertuples()]
    y = np.arange(len(d))[::-1]
    fig, ax = plt.subplots(figsize=(8, 8.5))
    ax.axvspan(-margin, margin, color=style.GRID, alpha=0.6, lw=0)
    ax.axvline(0, color=style.AXIS, lw=1)
    ax.hlines(y, d["ci_low_s"], d["ci_high_s"], color=style.INK_2, lw=1.5)
    sig = d["p_bh"] < 0.05
    ax.scatter(d["seconds"], y, s=40, color=style.INK, zorder=3, edgecolor=style.SURFACE, linewidth=1.5)
    ax.scatter(d.loc[sig, "seconds"], y[sig.to_numpy()], s=40, facecolor=style.SURFACE, edgecolor=style.INK,
               linewidth=1.5, zorder=4, label="different from 0 after BH correction")
    field = overall[(overall["sample"] == "field") & (overall["model"] == "within dog-day")].iloc[0]
    ax.axvline(field["seconds"], color=style.INK, lw=1)
    ax.text(field["seconds"], len(d) - 0.3, f" season: {field['seconds']:+.3f} s", fontsize=8.5,
            color=style.INK_2, va="bottom")
    ax.set_yticks(y, labels, fontsize=8.5)
    ax.set_xlim(-0.1, 0.1)
    ax.set_ylim(-0.8, len(d) + 0.6)
    ax.set_xlabel("blue lane minus red lane, seconds per dog run  (> 0 = blue slower)")
    ax.grid(axis="y", visible=False)
    ax.text(margin, -0.7, f" ±{margin:.2f} s = smallest difference that matters", fontsize=8,
            color=style.MUTED, va="bottom")
    ax.legend(loc="upper left", fontsize=8.5, bbox_to_anchor=(0, -0.07))
    ax.set_title("Lane colour: every ring-day sits inside the 'doesn't matter' band", pad=18)
    style.subtitle(ax, "same dog, same day, red vs blue lane; all dogs in the field; 95 % CI, errors clustered on race")
    return fig


def lane_dog_slopes(dogs: pd.DataFrame, n_labels: int = 3):
    """Slope chart: each WRFT dog's median run time in the red and the blue lane."""
    d = dogs.sort_values("red_median")
    fig, ax = plt.subplots(figsize=(5.5, 7))
    for r in d.itertuples():
        ax.plot([0, 1], [r.red_median, r.blue_median], color=style.FIELD_LIGHT, lw=1.2, zorder=1)
    ax.scatter(np.zeros(len(d)), d["red_median"], s=30, color=style.LANE["red"], zorder=2,
               edgecolor=style.SURFACE, linewidth=1)
    ax.scatter(np.ones(len(d)), d["blue_median"], s=30, color=style.LANE["blue"], zorder=2,
               edgecolor=style.SURFACE, linewidth=1)
    for r in d.reindex(d["blue_minus_red"].abs().sort_values(ascending=False).index[:n_labels]).itertuples():
        ax.annotate(f"{r.dog} {r.blue_minus_red:+.2f} s", (1, r.blue_median), xytext=(8, 0),
                    textcoords="offset points", va="center", fontsize=8.5, color=style.INK_2)
    ax.set_xticks([0, 1], ["red lane", "blue lane"])
    ax.set_xlim(-0.3, 1.6)
    ax.invert_yaxis()
    ax.set_ylabel("median run time (s), faster at the top")
    ax.grid(axis="x", visible=False)
    ax.set_title("WRFT dogs run the same in both lanes", pad=18)
    style.subtitle(ax, f"{len(d)} dogs with ≥ 10 valid runs in each lane; largest gaps labelled")
    return fig


# --- Q2: pass partner -----------------------------------------------------------------------

def partner_forest(contrasts: pd.DataFrame):
    """Small multiples, one per outcome: each incoming category against an incoming neutered male."""
    outcomes = list(dict.fromkeys(contrasts["outcome"]))
    specs = list(dict.fromkeys(contrasts["spec"]))
    levels = ["neutered female", "intact male", "intact female"]
    fig, axes = plt.subplots(1, len(outcomes), figsize=(3.0 * len(outcomes), 3.6), sharey=True)
    for ax, outcome in zip(axes, outcomes):
        c = contrasts[contrasts["outcome"] == outcome]
        share = c["unit"].iat[0] == "share"
        k = 100 if share else 1
        ax.axvline(0, color=style.AXIS, lw=1)
        for j, spec in enumerate(specs):
            cs = c[c["spec"] == spec].set_index("level").loc[levels]
            y = np.arange(len(levels))[::-1] + (0.15 if j == 0 else -0.15)
            ax.hlines(y, k * cs["ci_low"], k * cs["ci_high"], color=style.INK_2, lw=1.5)
            ax.scatter(k * cs["estimate"], y, s=36, zorder=3, linewidth=1.5,
                       facecolor=style.INK if j == 0 else style.SURFACE, edgecolor=style.INK,
                       label=spec if ax is axes[0] else None)
        ax.set_title(outcome.replace(" (", "\n("), fontsize=10, pad=6)
        ax.set_xlabel("percentage points" if share else "seconds", fontsize=9)
        ax.grid(axis="y", visible=False)
    dogs = contrasts.drop_duplicates("level").set_index("level")["incoming_dogs"]
    axes[0].set_yticks(np.arange(len(levels))[::-1], [f"{lv}\n({dogs[lv]} dogs)" for lv in levels])
    fig.legend(loc="lower left", ncols=2, fontsize=9, bbox_to_anchor=(0.06, -0.08))
    fig.suptitle("Passing onto each kind of dog, compared with passing onto a neutered male",
                 x=0.06, ha="left", fontweight="bold", fontsize=12, y=1.15)
    fig.text(0.06, 1.07, "outcomes of the outgoing WRFT dog; 95 % CI; both dogs as random effects",
             color=style.INK_2, fontsize=9)
    return fig


# --- Q3: per competition ----------------------------------------------------------------------

def competition_small_multiples(days: pd.DataFrame):
    """One column per WRFT competition day, five stacked panels sharing the x axis."""
    d = days.sort_values("date").reset_index(drop=True)
    d["date"] = pd.to_datetime(d["date"])
    x, event = event_positions(d["date"])
    fig, axes = plt.subplots(5, 1, figsize=(11, 11), sharex=True,
                             gridspec_kw={"hspace": 0.55, "height_ratios": [1.2, 1, 1, 1.2, 0.8]})

    ax = axes[0]
    ax.vlines(x, 100 * d["win_ci_low"], 100 * d["win_ci_high"], color=style.WRFT, lw=1.5, alpha=0.5)
    ax.scatter(x, 100 * d["win_rate"], s=36, color=style.WRFT, zorder=3, edgecolor=style.SURFACE, linewidth=1.5)
    ax.axhline(50, color=style.AXIS, lw=1)
    ax.set_title("WRFT heat win rate (%)", pad=14)
    style.subtitle(ax, "all WRFT teams that day, 95 % CI; 50 % line for reference")

    ax = axes[1]
    ax.bar(x, 100 * d["clean_heat_rate"], width=0.6, color=style.INK_2)
    ax.set_title("Clean heats (%)", pad=14)
    style.subtitle(ax, "all 4 dogs ran, no fault, no rerun")

    ax = axes[2]
    ax.bar(x, 100 * d["share_losses_avoidable"], width=0.6, color=style.INK_2)
    ax.set_title("Avoidable losses (% of losses)", pad=14)
    style.subtitle(ax, "lost through a fault, but the team's usual clean time would have won")

    ax = axes[3]
    ax.axhline(0, color=style.AXIS, lw=1)
    ax.plot(x, d["speed_index_field_pct"], color=style.FIELD, marker="o", ms=5, lw=0, label="field")
    ax.plot(x, d["speed_index_wrft_pct"], color=style.WRFT, marker="o", ms=6, lw=0, label="WRFT dogs")
    ax.set_title("Dog-adjusted speed (% vs an average day; below 0 = faster)", pad=14)
    style.subtitle(ax, "same dogs compared with themselves: venue, ground and weather together")
    ax.legend(loc="upper right", ncols=2, fontsize=9)

    ax = axes[4]
    ax.scatter(x, d["temp_mean_c"], s=30, color=style.INK, zorder=3)
    ax.set_title("Mean temperature during racing (°C)", pad=6)

    ax.set_xticks(x, [f"{t:%d}" for t in d["date"]], fontsize=8)
    for _, grp in d.groupby(event):
        xs = x[grp.index]
        ax.text(xs.mean(), -0.45, f"{grp['date'].iloc[0]:%b}\n{short_competition(grp['competition'].iloc[0])}",
                transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=8, color=style.INK_2)
    for a in axes:
        a.grid(axis="x", visible=False)
    fig.suptitle("WRFT competition by competition, 2023", x=0.125, ha="left", fontweight="bold",
                 fontsize=13, y=0.95)
    return fig


def dog_competition_heatmap(dog_comp: pd.DataFrame, min_competitions: int = 3, clip: float = 0.3):
    """Each WRFT dog's median run at each competition, minus its own season median."""
    d = dog_comp[dog_comp["valid_runs"] >= 5]
    keep = d.groupby("dog")["competition"].nunique()
    d = d[d["dog"].isin(keep[keep >= min_competitions].index)]
    order_c = d.groupby("competition")["first_date"].min().sort_values().index
    order_d = d.groupby("dog")["season_median"].first().sort_values().index
    grid = d.pivot(index="dog", columns="competition", values="vs_season_s").loc[order_d, order_c]

    cmap = LinearSegmentedColormap.from_list("faster_slower", [style.GOOD, MIDPOINT, style.FAULT])
    cmap.set_bad(style.SURFACE)
    fig, ax = plt.subplots(figsize=(8, 0.24 * len(grid) + 2))
    im = ax.imshow(grid.to_numpy(dtype=float), cmap=cmap, vmin=-clip, vmax=clip, aspect="auto")
    ax.set_xticks(range(len(order_c)), [short_competition(c) for c in order_c], rotation=35, ha="right", fontsize=8.5)
    ax.set_yticks(range(len(order_d)), order_d, fontsize=8)
    ax.set_xticks(np.arange(-0.5, len(order_c)), minor=True)
    ax.set_yticks(np.arange(-0.5, len(order_d)), minor=True)
    ax.grid(which="minor", color=style.SURFACE, lw=2)         # 2px surface gap between cells
    ax.grid(which="major", visible=False)
    ax.tick_params(which="minor", length=0)
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    bar = fig.colorbar(im, ax=ax, shrink=0.5, pad=0.02, extend="both")
    bar.set_label("s vs own season median  (− = faster)", fontsize=8.5)
    bar.outline.set_visible(False)
    ax.set_title("Where each WRFT dog ran fast or slow", pad=18)
    style.subtitle(ax, f"dogs with ≥ 5 valid runs at ≥ {min_competitions} competitions, fastest dogs at the top; "
                       "blank = did not race")
    return fig


# --- 4B: weather ----------------------------------------------------------------------------

def weather_forest(effects: pd.DataFrame, margins=(("run time", 0.05), ("clean heat time", 0.20))):
    """Coach's weather factors: run time per dog and clean heat time, field vs WRFT, within competition."""
    e = effects[effects["model"].eq("within competition")]
    contrasts = list(dict.fromkeys(e["contrast"]))
    fig, axes = plt.subplots(1, len(margins), figsize=(11, 3.9), sharey=True)
    for ax, (outcome, margin) in zip(axes, margins):
        ax.axvspan(-margin, margin, color=style.GRID, alpha=0.6, lw=0)
        ax.axvline(0, color=style.AXIS, lw=1)
        for j, (sample, colour) in enumerate((("field", style.INK), ("WRFT", style.WRFT))):
            c = e[(e["outcome"] == outcome) & (e["sample"] == sample)].set_index("contrast").loc[contrasts]
            y = np.arange(len(contrasts))[::-1] + (0.14 if j == 0 else -0.14)
            ax.hlines(y, c["ci_low"], c["ci_high"], color=colour, lw=1.6)
            ax.scatter(c["estimate"], y, s=40, color=colour, zorder=3, edgecolor=style.SURFACE, linewidth=1.5,
                       label=f"{sample} ({'all dogs' if sample == 'field' else '50 dogs'})" if ax is axes[0] else None)
        unit = "s per dog run" if outcome == "run time" else "s per heat"
        ax.set_title(outcome.capitalize(), pad=16)
        style.subtitle(ax, f"band = ±{margin:g} s, the smallest change that matters")
        ax.set_xlabel(unit, fontsize=9)
        ax.xaxis.set_major_locator(plt.MaxNLocator(6))
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(np.arange(len(contrasts))[::-1], contrasts)
    fig.legend(loc="lower left", ncols=2, fontsize=9, bbox_to_anchor=(0.2, -0.1))
    fig.suptitle("Only heat above 20 °C slows the dogs down", x=0.02, ha="left", fontweight="bold", fontsize=13, y=1.1)
    fig.text(0.02, 1.02, "same dog (team) at the same competition; 95 % CI, clustered on venue-day",
             color=style.INK_2, fontsize=9)
    return fig


def heat_curve(curve: pd.DataFrame, pdp: pd.DataFrame, hinge: float = 20.0):
    """Dog-adjusted run time by temperature: binned means (dots) and the gradient-boosting curve (line)."""
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.axhline(0, color=style.AXIS, lw=1)
    ax.axvline(hinge, color=style.AXIS, lw=1, ls=(0, (3, 3)))
    ax.vlines(curve["temp_c"], curve["ci_low"], curve["ci_high"], color=style.INK_2, lw=1.5)
    ax.scatter(curve["temp_c"], curve["mean_pct"], s=12 + curve["runs"] / 40, color=style.INK, zorder=3,
               edgecolor=style.SURFACE, linewidth=1.5, label="mean of runs in each 2 °C band (size = runs)")
    t = pdp[pdp["feature"] == "temp_c"]
    ax.plot(t["value"], t["pct"], color=style.WRFT, lw=2, label="gradient-boosting partial dependence (centred)")
    ax.text(hinge + 0.3, 0.03, f"{hinge:g} °C hinge", transform=ax.get_xaxis_transform(), color=style.INK_2, fontsize=9)
    ax.set_xlabel("air temperature at the heat (°C)")
    ax.set_ylabel("% slower than the dog's usual run")
    ax.set_title("Dogs run slower once it gets warmer than about 22 °C", pad=16)
    style.subtitle(ax, "all dogs; each run compared with the same dog's own level; across venues, so descriptive")
    ax.legend(loc="upper left", fontsize=9)
    return fig


def weather_vs_venue(days: pd.DataFrame):
    """Each ring-day's dog-adjusted speed against its mean temperature, with the weather + season fit."""
    d = days.copy()
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.axhline(0, color=style.AXIS, lw=1)
    ax.vlines(d["temp_mean_c"], d["ci_low"], d["ci_high"], color=style.FIELD_LIGHT, lw=1.5)
    ax.scatter(d["temp_mean_c"], d["pct"], s=40, color=style.INK, zorder=3, edgecolor=style.SURFACE, linewidth=1.5,
               label="ring-day (95 % CI)")
    ax.scatter(d["temp_mean_c"], d["fitted_pct"], s=40, marker="_", linewidth=2, color=style.WRFT, zorder=2,
               label="predicted from weather + season")
    labelled = d.loc[d["pct"].abs().nlargest(6).index].drop_duplicates("competition").sort_values("temp_mean_c")
    last_x, flip = -99.0, 1
    for r in labelled.itertuples():
        flip = -flip if r.temp_mean_c - last_x < 1.5 else 1      # stagger labels of neighbouring points
        last_x = r.temp_mean_c
        ax.annotate(f"{short_competition(r.competition)} {pd.Timestamp(r.date):%a}", (r.temp_mean_c, r.pct),
                    xytext=(6, 8 * flip if flip < 0 else 0), textcoords="offset points", va="center",
                    ha="right" if flip < 0 else "left", fontsize=8, color=style.INK_2)
    ax.set_xlabel("mean temperature during racing (°C)")
    ax.set_ylabel("% slower (+) or faster (−) than an average day")
    ax.set_title("Hot days were slow, but venue and season matter too", pad=16)
    style.subtitle(ax, "same dogs, all teams; distance from the violet mark = venue/day not explained by weather")
    ax.legend(loc="upper left", fontsize=9)
    return fig


# --- 4B: line-up --------------------------------------------------------------------------

def lineup_breakdown(rows: pd.DataFrame):
    """Expected heat time split into start, runs, passes and expected fault cost, one bar per line-up.

    `rows` has label, start_s, runs_s, passes_s, fault_s, expected_s, p_clean.
    """
    d = rows.iloc[::-1].reset_index(drop=True)
    parts = [("start_s", "start", style.MUTED), ("runs_s", "4 runs", style.WRFT),
             ("passes_s", "3 passes", style.INK_2), ("fault_s", "expected fault cost", style.FAULT)]
    fig, ax = plt.subplots(figsize=(10, 0.45 * len(d) + 1.6))
    left = np.zeros(len(d))
    for col, label, colour in parts:
        ax.barh(d.index, d[col], left=left, color=colour, height=0.62, label=label, edgecolor=style.SURFACE, linewidth=2)
        left += d[col].to_numpy()
    for i, r in d.iterrows():
        ax.text(r["expected_s"] + 0.15, i, f"{r['expected_s']:.1f} s   P(clean) {r['p_clean']:.0%}",
                va="center", fontsize=8.5, color=style.INK_2)
    ax.set_yticks(d.index, d["label"], fontsize=8.5)
    ax.set_xlim(0, d["expected_s"].max() * 1.22)
    ax.set_xlabel("expected heat time (s)")
    ax.grid(axis="y", visible=False)
    ax.set_title("Expected heat time of each line-up", pad=16)
    style.subtitle(ax, "fault cost = expected number of faults × the ~8 s a rerun costs")
    ax.legend(loc="upper left", ncols=4, fontsize=9, bbox_to_anchor=(0, -0.6 / len(d) - 0.04))
    return fig


def height_dog_tradeoff(height: pd.DataFrame):
    """For each small dog: what the lower hurdle saves the partners vs the net change of the best line-up."""
    d = height.sort_values("gain_vs_without_s").reset_index(drop=True)
    y = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(8, 0.7 * len(d) + 1.6))
    ax.axvline(0, color=style.AXIS, lw=1)
    ax.barh(y + 0.18, d["hurdle_saving_s"], height=0.34, color=style.GOOD, label="partners' saving from the lower hurdle")
    ax.barh(y - 0.18, d["gain_vs_without_s"], height=0.34, color=style.FAULT, label="net change of the best line-up")
    for i, r in d.iterrows():
        ax.text(r["hurdle_saving_s"] + 0.05, i + 0.18, f"+{r['hurdle_saving_s']:.2f}", va="center", fontsize=8.5, color=style.INK_2)
        ax.text(r["gain_vs_without_s"] - 0.05, i - 0.18, f"{r['gain_vs_without_s']:+.2f}", va="center", ha="right",
                fontsize=8.5, color=style.INK_2)
    ax.set_yticks(y, [f"{r.height_dog} ({r.height_cm:g} cm, {r.run_at_own_height_s:.2f} s)" for r in d.itertuples()])
    ax.set_xlim(d["gain_vs_without_s"].min() - 0.5, d["hurdle_saving_s"].max() + 0.5)
    ax.set_xlabel("seconds per heat (+ = faster)")
    ax.grid(axis="y", visible=False)
    ax.set_title("A small height dog lowers the hurdle, but none of ours is fast enough to pay", pad=16)
    style.subtitle(ax, "compared with the best line-up without a dog under 25 cm")
    ax.legend(loc="upper left", ncols=2, fontsize=9, bbox_to_anchor=(0, -0.16))
    return fig


def lineup_backtest(heats: pd.DataFrame):
    """Sep-Oct clean heat times: predicted (from Apr-Jul) vs actual, model and naive baseline."""
    c = heats.dropna(subset=["actual_clean_time"])
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), sharex=True, sharey=True)
    lo, hi = c[["actual_clean_time", "predicted_clean_time", "baseline_clean_time"]].quantile([0, 1]).values.ravel()[[0, -1]]
    for ax, (col, title) in zip(axes, (("predicted_clean_time", "Profile model"),
                                       ("baseline_clean_time", "Naive: sum of each dog's median"))):
        ax.plot([lo, hi], [lo, hi], color=style.AXIS, lw=1)
        small = c["hurdle_cm"] <= 15
        ax.scatter(c.loc[~small, col], c.loc[~small, "actual_clean_time"], s=18, color=style.INK, alpha=0.7,
                   edgecolor=style.SURFACE, linewidth=0.5, label="hurdle 20–30 cm")
        ax.scatter(c.loc[small, col], c.loc[small, "actual_clean_time"], s=26, color=style.WRFT,
                   edgecolor=style.SURFACE, linewidth=0.5, label="hurdle 15 cm")
        mae = (c[col] - c["actual_clean_time"]).abs().mean()
        rho = c[col].corr(c["actual_clean_time"], method="spearman")
        ax.set_title(title, pad=16)
        style.subtitle(ax, f"MAE {mae:.2f} s, rank correlation {rho:.2f}, {len(c)} clean heats")
        ax.set_xlabel("predicted clean time (s)")
    axes[0].set_ylabel("actual clean time (s)")
    axes[0].legend(loc="upper left", fontsize=9)
    fig.suptitle("Back-test: profiles from Apr–Jul predict Sep–Oct WRFT heats", x=0.02, ha="left",
                 fontweight="bold", fontsize=13, y=1.06)
    return fig
