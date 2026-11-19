#!/usr/bin/env python3
"""
Quantitative figures of the manuscript, drawn from the same stored outputs and numbers
that make_numbers.py writes for the text. The diagrams (Fig1 overview, Fig2 architecture,
Fig3 sequence) are made separately (draw.io and TikZ, in the manuscript folder).

  Fig4:  main comparison (OAB-1 accuracy, OAB-2 guideline citation recall, Temas all fields)
  Fig5:  paired differences, JUDICATA minus each comparator (bootstrap 95% CI)
  Fig6:  Temas cases: competent court named by each condition and by the gold label
  Fig7:  Temas cases: position of the threshold pages and sources that filled the prompt
  Fig8:  agreement of the two LLM judges on the OAB-2 answers
  Fig9:  OAB-2 specific citations per answer, guideline recall and precision
  Fig10: rule-based defenses on third-party attacks
  Fig11: Qualifier label against correctness (OAB-1)

Files are numbered in order of first citation (PLOS ONE). Every figure is drawn at its
final print size (text width 6.5 in) and included without scaling, so the text is 8-9 pt
Times New Roman (PLOS accepts Arial, Times or Symbol). All figures are black and white:
the two models differ by marker shape and grey level, categories by grey level and hatch,
so nothing depends on colour. Axes of bars start at zero and show units.
The single-call Toulmin baselines are drawn with open markers on OAB-1 and on the health
cases, where their prompt carried two competing format instructions.
Usage: python evaluation/make_figures.py --out ../revision/v3/figures
"""
import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evaluation import make_numbers as MN  # noqa: E402

INK, INK2, GRID, BAND = "#000000", "#4a4a4a", "#e0e0e0", "#efefef"
DARK, MID, LIGHT = "#262626", "#8c8c8c", "#d4d4d4"
TEXTW = 6.5
plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman"], "mathtext.fontset": "stix",
    "font.size": 8.5, "axes.titlesize": 8.5, "axes.labelsize": 8.5, "xtick.labelsize": 8, "ytick.labelsize": 8.5,
    "legend.fontsize": 8.5, "text.color": INK, "axes.labelcolor": INK, "axes.edgecolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "xtick.labelcolor": INK, "ytick.labelcolor": INK,
    "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.major.size": 3,
    "ytick.major.size": 0, "hatch.linewidth": 0.6, "svg.hashsalt": "judicata",
    "legend.frameon": False, "legend.handlelength": 1.4, "axes.titlelocation": "left", "axes.titleweight": "bold",
    "axes.titlepad": 6, "pdf.fonttype": 42})
N = {}
V = {}
MODELS = [("qwen", "Qwen2.5 14B", DARK, "o"), ("mistral", "Mistral 7B", MID, "s")]
CONDS = [("raw", "Raw LLM"), ("vanilla", "Vanilla RAG"), ("rtstmt", "RAG + Toulmin\n(statement query)"),
         ("rtjdocs", "RAG + Toulmin\n(JUDICATA documents)"), ("judicata", "JUDICATA")]
FULL = {"raw": "raw", "vanilla": "vanilla_rag", "rtstmt": "rag_toulmin", "rtjdocs": "rag_toulmin_jq", "judicata": "judicata"}
MID_ = {"qwen": "qwen2.5:14b", "mistral": "mistral:7b"}
DEFECT_TASKS = {"oabone", "temas"}          # tasks whose baseline prompt had competing format instructions
DEFECT_CONDS = {"rtstmt", "rtjdocs"}


def f(key):
    return float(N[key][0].replace(",", "").replace("$-$", "-"))


def save(fig, out, name):
    meta = {"CreationDate": None, "ModDate": None}
    fig.savefig(out / f"{name}.pdf", metadata=meta)
    fig.savefig(out / f"{name}.tif", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
    fig.savefig(out / f"{name}_preview.png", dpi=200)
    plt.close(fig)


def style(ax, grid="x"):
    ax.spines[["top", "right"]].set_visible(False)
    if grid:
        ax.grid(axis=grid, color=GRID, lw=0.6)
        ax.set_axisbelow(True)


def point(ax, x, y, m, open_=False, ms=5.5):
    _, _, col, mk = next(t for t in MODELS if t[0] == m)
    ax.plot(x, y, marker=mk, color=col, ms=ms, ls="none", zorder=3, clip_on=False,
            mfc="white" if open_ else col, mec=col if open_ else "white", mew=1.0 if open_ else 0.6)


def legend_handles(defect=False):
    h = [Line2D([], [], marker=mk, color=col, mec="white", ls="none", ms=5.5, label=ml) for _, ml, col, mk in MODELS]
    if defect:
        h.append(Line2D([], [], marker="o", color=DARK, mfc="white", mew=1.0, ls="none", ms=5.5,
                        label="baseline prompt with competing format instructions"))
    return h


def dots(ax, rows, get, task=None, highlight=None):
    """Point estimates with 95% CI, one row per condition, the two models side by side."""
    for i, (c, _) in enumerate(rows):
        if c == highlight:
            ax.axhspan(i - 0.45, i + 0.45, color=BAND, zorder=0, lw=0)
    for j, (m, _, col, mk) in enumerate(MODELS):
        for i, (c, _) in enumerate(rows):
            mu, lo, hi = get(m, c)
            y = i + (j - 0.5) * 0.32
            ax.plot([lo, hi], [y, y], color=col, lw=1.0, solid_capstyle="butt", zorder=2, clip_on=False)
            point(ax, mu, y, m, open_=(task in DEFECT_TASKS and c in DEFECT_CONDS))
    ax.set_yticks(range(len(rows)))
    ax.set_ylim(len(rows) - 0.5, -0.5)


# ------------------------------------------------------------------------- Fig4
def fig_main(out):
    panels = [("oabone", "oabone.{m}.{c}.acc", f"A  OAB-1 (n = {N['oabone.n'][0]})", "Accuracy (%)", 100),
              ("oabtwo", "oabtwo.{m}.{c}.recall", f"B  OAB-2 (n = {N['oabtwo.recall.n'][0]})",
               "Guideline citation recall", 1),
              ("temas", "temas.{m}.{c}.all", f"C  Health cases (n = {N['temas.cases'][0]})", "All fields correct (%)", 100)]
    fig, axes = plt.subplots(1, 3, figsize=(TEXTW, 2.6), sharey=True, gridspec_kw={"wspace": 0.22})
    for ax, (task, pat, title, xl, top) in zip(axes, panels):
        def get(m, c, pat=pat):
            k = pat.format(m=m, c=c)
            return f(k), f(k + ".lo"), f(k + ".hi")
        dots(ax, CONDS, get, task=task, highlight="judicata")
        ax.set_xlim(0, top)
        ax.set_xticks([0, top / 2, top])
        ax.set_title(title)
        ax.set_xlabel(xl + r"  $\rightarrow$")
        style(ax)
    axes[0].set_yticklabels([c[1] for c in CONDS])
    fig.legend(handles=legend_handles(defect=True), loc="upper center", ncol=3, bbox_to_anchor=(0.55, 1.0),
               columnspacing=1.4, handletextpad=0.4)
    fig.subplots_adjust(left=0.215, right=0.975, top=0.80, bottom=0.17)
    save(fig, out, "Fig4")


# ------------------------------------------------------------------------- Fig5
def fig_diffs(out):
    comps = [c for c in CONDS if c[0] != "judicata"]
    panels = [("oabone", "A  OAB-1 accuracy", "Difference (pp)", "oabone.{m}.{c}.mcn.pholm"),
              ("temas", "B  Health cases", "Difference (pp)", "temas.{m}.{c}.mcn.pholm"),
              ("recall", "C  OAB-2 recall", "Difference", "oabtwo.{m}.{c}.recall.pholm"),
              ("prec", "D  OAB-2 precision", "Difference", None)]
    fig, axes = plt.subplots(1, 4, figsize=(TEXTW, 2.55), sharey=True, gridspec_kw={"wspace": 0.14})
    for ax, (meas, title, xl, pk) in zip(axes, panels):
        for j, (m, _, col, mk) in enumerate(MODELS):
            for i, (c, _) in enumerate(comps):
                d, lo, hi, _n = (float(x) for x in N[f"diff.{meas}.{m}.{c}.vals"][0].split(","))
                y = i + (j - 0.5) * 0.32
                ax.plot([lo, hi], [y, y], color=col, lw=1.0, zorder=2)
                point(ax, d, y, m, open_=(meas in DEFECT_TASKS and c in DEFECT_CONDS))
                if pk:
                    p = N[pk.format(m=m, c=c)][0]
                    sig = "<" in p or float(p) < 0.05
                    if sig:
                        ax.text(hi, y, " *", ha="left", va="center", fontsize=9, fontweight="bold")
        ax.axvline(0, color=INK, lw=0.7, zorder=1)
        ax.set_yticks(range(len(comps)))
        ax.set_ylim(len(comps) - 0.5, -0.5)
        ax.set_title(title)
        ax.set_xlabel(xl)
        style(ax)
    for ax in axes[:2]:
        lim = max(abs(v) for v in ax.get_xlim()) * 1.08
        ax.set_xlim(-lim, lim)
    for ax in axes[2:]:
        ax.set_xlim(-0.25, 0.25)
        ax.set_xticks([-0.2, 0, 0.2])
    axes[0].set_yticklabels([c[1] for c in comps])
    for ax in axes:
        ax.text(0.98, -0.30, r"JUDICATA better $\rightarrow$", transform=ax.transAxes, ha="right", va="top",
                fontsize=7.5, color=INK2)
    h = legend_handles(defect=True)
    h.append(Line2D([], [], ls="none", marker="$*$", color=INK, ms=6, label="Holm-adjusted p < 0.05"))
    fig.legend(handles=h, loc="upper center", ncol=2, bbox_to_anchor=(0.55, 1.01), columnspacing=1.4,
               handletextpad=0.4)
    fig.subplots_adjust(left=0.215, right=0.985, top=0.76, bottom=0.27)
    save(fig, out, "Fig5")


# ------------------------------------------------------------------------- Fig6
def fig_courts(out):
    cls = [("state", "State courts", DARK, "", None), ("federal", "Federal courts", LIGHT, "////", INK),
           ("other", "Other or none", MID, "", None)]
    rows = [("Gold label", "temas.gold.{cls}", None)]
    for m, ml, _, _ in MODELS:
        for c, cl in CONDS:
            rows.append((cl, f"temas.{m}.{c}.comp.{{cls}}", ml))
    fig, ax = plt.subplots(figsize=(TEXTW, 4.7))
    ys, y = [], 0
    for i in range(len(rows)):
        if i in (1, 6):
            y += 1.3
        ys.append(y)
        y += 1
    for (lab, pat, _), y in zip(rows, ys):
        tot = sum(f(pat.format(cls=c)) for c, *_ in cls)
        left = 0
        for c, _, col, hat, hc in cls:
            val = 100 * f(pat.format(cls=c)) / tot
            ax.barh(y, val, left=left, color=col, hatch=hat, hatchcolor=hc or col, edgecolor="white", lw=0.8,
                    height=0.66)
            if lab == "Gold label" and val > 15:
                ax.text(left + val / 2, y, f"{int(f(pat.format(cls=c)))} cases", ha="center", va="center",
                        fontsize=8, color=INK, bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
            left += val
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows])
    ax.set_ylim(ys[-1] + 0.6, -0.6)
    for (m, ml, _, _), yy in zip(MODELS, (ys[1], ys[6])):
        ax.text(1, yy - 0.95, ml, ha="left", va="center", fontsize=8.5, fontweight="bold")
    ax.set_xlim(0, 100)
    ax.set_xlabel(f"Share of the {N['temas.cases'][0]} cases (%)")
    style(ax)
    ax.legend(handles=[Patch(facecolor=col, hatch=hat, edgecolor=hc or col, label=lab)
                       for _, lab, col, hat, hc in cls], loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3)
    fig.subplots_adjust(left=0.215, right=0.985, top=0.90, bottom=0.12)
    save(fig, out, "Fig6")


# ------------------------------------------------------------------------- Fig7
def fig_context(out):
    import json as _json
    from app.reasoning.source_hierarchy import TIERS
    corpus = _json.load(open(Path(__file__).resolve().parent.parent / "dataset" / "precedents" / "health_corpus.json",
                             encoding="utf-8"))
    corpus = corpus if isinstance(corpus, list) else next(v for v in corpus.values() if isinstance(v, list))
    thr = {x["number"] for x in corpus if x["id"].startswith("CNJ_") and "210" in _json.dumps(x, ensure_ascii=False)}
    # order used to fill the prompt: similarity (vanilla RAG, 5 documents), fusion score (no hierarchy),
    # authority tier then score (all other conditions)
    conds = [("vanilla_rag", "Vanilla RAG", "sim"), ("rag_toulmin", "RAG + Toulmin\n(statement query)", "tier"),
             ("rag_toulmin_jq", "RAG + Toulmin\n(JUDICATA documents)", "tier"), ("judicata", "JUDICATA", "tier"),
             ("judicata-fixed_weights", "JUDICATA, fixed\nweights (k = 8)", "tier"),
             ("judicata-no_hierarchy", "JUDICATA without\nsource hierarchy", "fusion")]
    rows = MN.ML.by_cond(MN.A.load_results("temas"))
    cats = [("sv", "Súmula vinculante", DARK, "", None), ("lei", "Statute", MID, "\\\\\\\\", "white"),
            ("cnj", "CNJ guide page", LIGHT, "", None)]

    def cat(d):
        k = d.get("kind")
        if k == "SUMULA_VINCULANTE":
            return "sv"
        if k == "ORIENTACAO_ADMIN":
            return "thr" if d.get("article") in thr else "cnj"
        return "lei"

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(TEXTW, 3.0), sharey=True,
                                 gridspec_kw={"width_ratios": [1.15, 1], "wspace": 0.08})
    for i, (c, _, how) in enumerate(conds):
        items = list(rows[("qwen2.5:14b", c)].values())
        cnt = {k: 0 for k, *_ in cats}
        ranks, nret = [], []
        for r in items:
            docs = r["documents"]
            nret.append(len(docs))
            order = docs if how != "tier" else sorted(
                docs, key=lambda d: (TIERS.get(d.get("kind"), (6,))[0], -(d.get("score") or 0)))
            for d in order[:5]:
                k = cat(d)
                cnt["cnj" if k == "thr" else k] += 1
            pos = [p + 1 for p, d in enumerate(order) if cat(d) == "thr"]
            ranks.append(min(pos) if pos else None)
        got = [x for x in ranks if x]
        for pos in sorted(set(got)):
            k = got.count(pos)
            a1.scatter([pos], [i], s=14 + 2.2 * k, color=INK, edgecolor="white", lw=0.6, zorder=3)
            a1.text(pos, i - 0.36, str(k), ha="center", va="bottom", fontsize=7.5, color=INK2)
        if len(got) < len(ranks):
            a1.text(15.6, i, f"not among its {max(nret)} documents ({len(ranks) - len(got)} cases)", ha="right",
                    va="center", fontsize=8, color=INK2)
        left = 0
        for k, _, col, hat, hc in cats:
            v = cnt[k] / len(items)
            a2.barh(i, v, left=left, color=col, hatch=hat, hatchcolor=hc or col, edgecolor="white", lw=0.8,
                    height=0.62)
            left += v
    a1.axvspan(0.5, 5.5, color=BAND, zorder=0, lw=0)
    a1.text(3.0, len(conds) - 0.45, "shown to\nthe model", ha="center", va="bottom", fontsize=7.5, color=INK2)
    a1.set_xlim(0.5, 15.8)
    a1.set_ylim(len(conds) - 0.45, -0.75)
    a1.set_xticks([1, 5, 10, 15])
    a1.set_xlabel("Rank of the first threshold page in prompt-filling order")
    a1.set_title("A  Where the threshold page ranked")
    a1.set_yticks(range(len(conds)))
    a1.set_yticklabels([c[1] for c in conds])
    a2.set_xlim(0, 5)
    a2.set_xticks(range(6))
    a2.set_xlabel("Sources in the prompt (mean count of 5)")
    a2.set_title("B  What filled the five prompt sources")
    a1.legend(handles=[Line2D([], [], marker="o", color=INK, ls="none", ms=5.5,
                              label="first threshold page\n(label: number of cases)")],
              loc="upper center", bbox_to_anchor=(0.5, -0.22), handletextpad=0.4)
    a2.legend(handles=[Patch(facecolor=col, hatch=hat, edgecolor=hc or col, label=lab) for _, lab, col, hat, hc in cats],
              loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2, handletextpad=0.4, columnspacing=1.0)
    style(a1)
    style(a2)
    fig.subplots_adjust(left=0.215, right=0.985, top=0.92, bottom=0.30)
    save(fig, out, "Fig7")


# ------------------------------------------------------------------------- Fig8
def fig_judges(out):
    import numpy as np
    from matplotlib.colors import LogNorm
    sc = MN.ML.oab2_scores()
    gx, gy = [], []
    for (j, m, c), d in sc.items():
        if j != "gemma3:27b" or c not in FULL.values():
            continue
        other = sc.get(("llama3.1:8b", m, c), {})
        for i, v in d.items():
            if i in other:
                gx.append(v)
                gy.append(other[i])
    edges = np.linspace(0, 1, 11)
    H, _, _ = np.histogram2d(np.clip(gx, 0, 0.9999), np.clip(gy, 0, 0.9999), bins=[edges, edges])
    fig = plt.figure(figsize=(4.2, 3.9))
    gs = fig.add_gridspec(2, 2, width_ratios=[4, 1], height_ratios=[1, 4], wspace=0.05, hspace=0.05)
    ax = fig.add_subplot(gs[1, 0])
    top = fig.add_subplot(gs[0, 0], sharex=ax)
    right = fig.add_subplot(gs[1, 1], sharey=ax)
    im = ax.pcolormesh(edges, edges, np.ma.masked_equal(H.T, 0), cmap="Greys", norm=LogNorm(vmin=1, vmax=H.max()),
                       edgecolors="white", lw=0.6)
    ax.plot([0, 1], [0, 1], color=INK2, lw=0.7, ls=(0, (4, 3)))
    ax.set_xlabel("Gemma 3 27B judge (score / maximum)")
    ax.set_ylabel("Llama 3.1 8B judge (score / maximum)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    top.bar(edges[:-1], H.sum(axis=1), width=0.1, align="edge", color=MID, edgecolor="white", lw=0.6)
    right.barh(edges[:-1], H.sum(axis=0), height=0.1, align="edge", color=MID, edgecolor="white", lw=0.6)
    top.set_ylabel("Answers", fontsize=8)
    right.set_xlabel("Answers", fontsize=8)
    for a in (top, right):
        a.spines[["top", "right"]].set_visible(False)
    top.tick_params(labelbottom=False)
    right.tick_params(labelleft=False)
    right.set_xticks([500])
    top.text(0.98, 0.95, rf"Spearman $\rho$ = {N['oabtwo.rho'][0]}" + f"\n{N['oabtwo.rhon'][0]} answers",
             transform=top.transAxes, ha="right", va="top", fontsize=8)
    cax = fig.add_axes([0.80, 0.80, 0.025, 0.14])
    cb = fig.colorbar(im, cax=cax)
    cb.set_label("Answers\nper cell", fontsize=7.5)
    cb.ax.tick_params(labelsize=7)
    cb.outline.set_linewidth(0.4)
    ax.spines[["top", "right"]].set_visible(False)
    fig.subplots_adjust(left=0.15, right=0.97, top=0.97, bottom=0.12)
    save(fig, out, "Fig8")


# ------------------------------------------------------------------------- Fig9
def boot_ci(vals, B=10000, seed=13):
    import numpy as np
    d = np.array(list(vals), dtype=float)
    rs = np.random.default_rng(seed)
    bs = d[rs.integers(0, len(d), size=(B, len(d)))].mean(axis=1)
    return float(d.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def fig_citations(out):
    panels = [("ncit", "A  Citations per answer", "Specific citations (count)", 12, [0, 4, 8, 12]),
              ("recall", "B  Coverage of the guideline", r"Recall  $\rightarrow$", 0.4, [0, 0.2, 0.4]),
              ("prec", "C  Selectivity", r"Precision  $\rightarrow$", 0.4, [0, 0.2, 0.4])]
    fig, axes = plt.subplots(1, 3, figsize=(TEXTW, 2.6), sharey=True, gridspec_kw={"wspace": 0.22})
    for ax, (meas, title, xl, top, ticks) in zip(axes, panels):
        dots(ax, CONDS, lambda m, c, meas=meas: boot_ci(V[meas][(MID_[m], FULL[c])].values()), highlight="judicata")
        ax.set_xlim(0, top)
        ax.set_xticks(ticks)
        ax.set_title(title)
        ax.set_xlabel(xl)
        style(ax)
    axes[0].set_yticklabels([c[1] for c in CONDS])
    fig.legend(handles=legend_handles(), loc="upper center", ncol=2, bbox_to_anchor=(0.55, 1.0))
    fig.subplots_adjust(left=0.215, right=0.975, top=0.80, bottom=0.17)
    save(fig, out, "Fig9")


# ------------------------------------------------------------------------ Fig10
def fig_security(out):
    sets = [("deepset", "deepset\nprompt injections"), ("lakera", "Lakera\nGandalf"),
            ("jackhhao", "jailbreak-\nclassification")]
    var = [("orig", "Original language", DARK, "", None), ("mt", "Portuguese machine translation", LIGHT, "\\\\\\\\", INK)]
    fig, ax = plt.subplots(figsize=(4.4, 2.7))
    w = 0.36
    for j, (vv, lab, col, hat, hc) in enumerate(var):
        for i, (s, _) in enumerate(sets):
            k = f"sec.{s}.{vv}.combinedtpr"
            x = i + (j - 0.5) * (w + 0.04)
            ax.bar(x, f(k), w, color=col, hatch=hat, hatchcolor=hc or col, edgecolor="white", lw=0.8,
                   label=lab if i == 0 else None)
            ax.plot([x, x], [f(k + ".lo"), f(k + ".hi")], color=INK, lw=0.8)
            ax.text(x, f(k + ".hi") + 2, N[k][0], ha="center", va="bottom", fontsize=8)
    ax.set_xticks(range(len(sets)))
    ax.set_xticklabels([x[1] for x in sets])
    ax.tick_params(axis="x", length=0)
    ax.set_ylabel(r"Attacks flagged (%)  $\rightarrow$")
    ax.set_ylim(0, 100)
    ax.yaxis.set_tick_params(size=3)
    ax.legend(loc="upper left", ncol=1)
    style(ax, grid="y")
    fig.subplots_adjust(left=0.14, right=0.98, top=0.97, bottom=0.18)
    save(fig, out, "Fig10")


# ------------------------------------------------------------------------ Fig11
def fig_qualifier(out):
    import json as _json
    R = _json.load(open(MN.RES / "results.json", encoding="utf-8"))
    labs = [("INCERTO", "INCERTO"), ("POSSIVEL", "POSSÍVEL"), ("PROVAVEL", "PROVÁVEL"), ("CERTO", "CERTO")]
    fig, ax = plt.subplots(figsize=(4.4, 2.7))
    for j, (m, ml, col, mk) in enumerate(MODELS):
        ax.axhline(f(f"oabone.{m}.judicata.acc"), color=col, lw=0.7, ls=(0, (4, 3)), zorder=1)
        for i, (q, _) in enumerate(labs):
            v = R["qualifier"].get(f"OAB-1|{MID_[m]}|{q}")
            if not v or not v["n"]:
                continue
            p, a, b = (100 * x for x in v["acc"])
            x = i + (j - 0.5) * 0.3
            ax.plot([x, x], [a, b], color=col, lw=1.0, zorder=2)
            point(ax, x, p, m)
            ax.text(x + (-0.07 if j == 0 else 0.07), p, f"{v['n']}", ha="right" if j == 0 else "left", va="center",
                    fontsize=7.5, color=INK2)
    ax.set_xticks(range(len(labs)))
    ax.set_xlim(-0.6, len(labs) - 0.4)
    ax.set_xticklabels([x[1] for x in labs])
    ax.tick_params(axis="x", length=0)
    ax.set_xlabel("Qualifier label assigned by JUDICATA (number next to point: answers)")
    ax.set_ylabel("Correct answers (%)")
    ax.set_ylim(0, 100)
    ax.yaxis.set_tick_params(size=3)
    style(ax, grid="y")
    h = legend_handles()
    h.append(Line2D([], [], color=INK2, lw=0.7, ls=(0, (4, 3)), label="JUDICATA accuracy, all answers"))
    ax.legend(handles=h, loc="lower left", ncol=1)
    fig.subplots_adjust(left=0.13, right=0.98, top=0.97, bottom=0.17)
    save(fig, out, "Fig11")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    N.update(MN.collect())
    V.update(MN.item_values())
    for fn in (fig_main, fig_diffs, fig_courts, fig_context, fig_judges, fig_citations, fig_security, fig_qualifier):
        fn(out)
    print(sorted(p.name for p in out.iterdir()))
