#!/usr/bin/env python3
"""
Figures of the manuscript (PLOS ONE: TIFF, LZW, 300-600 dpi, width <= 7.5 in), drawn
from the same numbers that make_numbers.py writes for the text.
  Fig1: pipeline (logical architecture, all components local)
  Fig2: main comparison (OAB-1 accuracy, OAB-2 guideline citation recall, Temas all fields)
  Fig3: Temas cases: competent court named by each condition against the gold label
  Fig4: rule-based defenses on third-party attacks
Palette: Okabe-Ito (colour-blind safe); series also differ by marker or hatch.
Usage: python evaluation/make_figures.py --out ../revision/v3/figures
"""
import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evaluation import make_numbers as MN  # noqa: E402

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8,
                     "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 8, "svg.hashsalt": "judicata",
                     "hatch.linewidth": 0.6})
BLUE, ORANGE, GREEN, VERM, GREY, SKY = "#0072B2", "#E69F00", "#009E73", "#D55E00", "#7f7f7f", "#56B4E9"
N = {}
MODELS = [("qwen", "Qwen2.5 14B", BLUE, "o"), ("mistral", "Mistral 7B", ORANGE, "s")]
CONDS = [("raw", "Raw\nLLM"), ("vanilla", "Vanilla\nRAG"), ("rtstmt", "RAG+T\nstmt."), ("rtjdocs", "RAG+T\nJ. docs"),
         ("judicata", "JUDICATA")]


def f(key):
    return float(N[key][0].replace(",", ""))


def save(fig, out, name):
    meta = {"CreationDate": None, "ModDate": None}
    fig.savefig(out / f"{name}.pdf", metadata=meta)
    fig.savefig(out / f"{name}.tif", dpi=450, pil_kwargs={"compression": "tiff_lzw"})
    fig.savefig(out / f"{name}_preview.png", dpi=150)
    plt.close(fig)


def fig1(out):
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 62)
    ax.axis("off")

    def box(x, y, w, h, title, sub, fc, ec="#333333"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.0", fc=fc, ec=ec, lw=0.8))
        ax.text(x + w / 2, y + h - 1.6, title, ha="center", va="top", fontsize=8.5, weight="bold")
        ax.text(x + w / 2, y + h - 5.8, sub, ha="center", va="top", fontsize=8, linespacing=1.25)

    def arrow(x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", lw=0.9, color="#333333"))

    chk, data, llm, out_ = "#fbe3d6", "#dbeefa", "#fff2cc", "#e2f0e8"
    ax.text(0.5, 61.5, "Local workstation: Ollama models, Qdrant, Neo4j and SQLite; no cloud service", fontsize=8,
            style="italic", va="top")
    w, h, y1, y2 = 21, 18.5, 39, 15.5
    xs = [0.5, 26.0, 51.5, 77.0]
    box(xs[0], y1, w, h, "0. Pseudonymize", "names, CPF, RG,\ne-mail, phone,\nCNJ case number", data)
    box(xs[1], y1, w, h, "1. Check input", "Guardian:\n29 regular expr.;\nP2P trigger rules", chk)
    box(xs[2], y1, w, h, "2. Retrieve", "HyPA-RAG: dense,\nBM25 and graph;\nweighted RRF", data)
    box(xs[3], y1, w, h, "3. Check docs", "RAG defender\n(TF-IDF outlier\nfilter)", chk)
    for a, b in zip(xs[:-1], xs[1:]):
        arrow(a + w + 0.4, y1 + h / 2, b - 0.4, y1 + h / 2)
    box(xs[3], y2, w, h, "4. Reason (LSIM)", "facts; rules by\nauthority tier;\nconclusion", llm)
    box(xs[2], y2, w, h, "5. Check output", "Guardian leakage;\nSCOT validation\n(post hoc)", chk)
    box(xs[1], y2, w, h, "6. Toulmin output", "six components;\ncitations checked\nvs. documents", llm)
    box(xs[0], y2, w, h, "7. Output", "pseudonymized;\ncitation check,\nQualifier, notice", out_)
    arrow(xs[3] + w / 2, y1 - 0.5, xs[3] + w / 2, y2 + h + 0.5)
    for a, b in zip(xs[1:][::-1], xs[:-1][::-1]):
        arrow(a - 0.4, y2 + h / 2, b + w + 0.4, y2 + h / 2)
    box(0.5, 1, 97.5, 10.5, "Audit trail (append-only SQLite)",
        "each node writes trace id, node, timestamp, model id and pseudonymized state;\n"
        "only a SHA-256 hash of the raw query is kept; a failed check ends the run early", "#eeeeee")
    save(fig, out, "Fig1")


def fig2(out):
    labels = ["Raw LLM", "Vanilla RAG", "RAG + Toulmin (stmt.)", "RAG + Toulmin (J. docs)", "JUDICATA"]
    fig, axes = plt.subplots(1, 3, figsize=(7.5, 2.6), sharey=True)
    panels = [("oabone.{m}.{c}.acc", "OAB-1 accuracy (%)", 100), ("oabtwo.{m}.{c}.recall", "OAB-2 citation recall", 1),
              ("temas.{m}.{c}.all", "Temas all fields (%)", 100)]
    for ax, (pat, title, top) in zip(axes, panels):
        for j, (m, ml, col, mk) in enumerate(MODELS):
            ys, xs, lo, hi = [], [], [], []
            for i, (c, _) in enumerate(CONDS):
                k = pat.format(m=m, c=c)
                ys.append(i + (j - 0.5) * 0.3)
                xs.append(f(k))
                lo.append(f(k) - f(k + ".lo"))
                hi.append(f(k + ".hi") - f(k))
            ax.errorbar(xs, ys, xerr=[lo, hi], fmt=mk, color=col, ms=4.5, capsize=2, lw=0.9, label=ml)
        ax.set_yticks(range(len(CONDS)))
        ax.set_yticklabels(labels)
        ax.invert_yaxis()
        ax.set_xlim(0, top)
        ax.set_title(title)
        ax.grid(axis="x", lw=0.3, alpha=0.6)
        ax.spines[["top", "right"]].set_visible(False)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, frameon=False, loc="upper center", ncol=2)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    save(fig, out, "Fig2")


def fig3(out):
    sets = [("deepset", "deepset"), ("lakera", "Lakera Gandalf"), ("jackhhao", "jailbreak-\nclassification")]
    fig, ax = plt.subplots(figsize=(5.2, 2.8))
    for j, (var, lab, col, hat) in enumerate((("orig", "original language", GREY, ""), ("mt", "Portuguese (MT)", SKY, "///"))):
        for i, (s, _) in enumerate(sets):
            k = f"sec.{s}.{var}.combinedtpr"
            x = i + (j - 0.5) * 0.36
            ax.bar(x, f(k), 0.34, color=col, hatch=hat, edgecolor="#333333", lw=0.5, label=lab if i == 0 else None)
            ax.errorbar(x, f(k), yerr=[[f(k) - f(k + ".lo")], [f(k + ".hi") - f(k)]], color="k", lw=0.8, capsize=2)
    ax.set_xticks(range(len(sets)))
    ax.set_xticklabels([x[1] for x in sets])
    ax.set_ylabel("Attacks flagged (%)")
    ax.set_ylim(0, 100)
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    save(fig, out, "Fig4")


def fig4(out):
    rows = [("Gold label", "temas.gold.{cls}")]
    for m, ml, _, _ in MODELS:
        for c, cl in CONDS:
            rows.append((f"{ml}: {cl.replace(chr(10), ' ')}", f"temas.{m}.{c}.comp.{{cls}}"))
    fig, ax = plt.subplots(figsize=(5.6, 3.8))
    cls = [("state", "State courts", GREEN, ""), ("federal", "Federal courts", VERM, "\\\\\\"), ("other", "Other / none", GREY, "..")]
    for i, (lab, pat) in enumerate(rows):
        tot = sum(f(pat.format(cls=c)) for c, *_ in cls)
        left = 0
        for c, cl, col, hat in cls:
            val = 100 * f(pat.format(cls=c)) / tot
            ax.barh(i, val, left=left, color=col, hatch=hat, edgecolor="#333333", lw=0.4, height=0.7,
                    label=cl if i == 0 else None)
            left += val
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of cases (%)")
    ax.axhline(0.5, color="k", lw=0.6)
    ax.axhline(5.5, color="k", lw=0.3, ls=":")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.45, 1.12), ncol=3)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    save(fig, out, "Fig3")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    N.update(MN.collect())
    for fn in (fig1, fig2, fig3, fig4):
        fn(out)
    print(sorted(p.name for p in out.iterdir()))
