#!/usr/bin/env python3
"""
Figures of the manuscript (PLOS ONE: TIFF, LZW, 300-600 dpi, width <= 7.5 in), drawn
from the same numbers that make_numbers.py writes for the text.
  Fig1: pipeline (logical architecture, all components local)
  Fig2: main comparison (OAB-1 accuracy, OAB-2 guideline citation recall, Temas all fields)
  Fig3: paired differences JUDICATA minus each comparator (bootstrap 95% CI)
  Fig4: Temas cases: competent court named by each condition against the gold label
  Fig5: Temas cases: position of the threshold pages and sources that filled the prompt
  Fig6: agreement of the two LLM judges on the OAB-2 answers
  Fig7: OAB-2 specific citations per answer, guideline recall and precision
  Fig8: rule-based defenses on third-party attacks
  Fig9: Qualifier label against correctness (OAB-1)
Files are numbered in order of first citation in the manuscript (PLOS ONE).
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


def fig_arch(out):
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


def fig_main(out):
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


def fig_security(out):
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
    save(fig, out, "Fig8")


def fig_courts(out):
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
    save(fig, out, "Fig4")


V = {}


def boot_ci(vals, B=10000, seed=13):
    import numpy as np
    d = np.array(list(vals), dtype=float)
    rs = np.random.default_rng(seed)
    bs = d[rs.integers(0, len(d), size=(B, len(d)))].mean(axis=1)
    return float(d.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


FULL = {"raw": "raw", "vanilla": "vanilla_rag", "rtstmt": "rag_toulmin", "rtjdocs": "rag_toulmin_jq", "judicata": "judicata"}
MID = {"qwen": "qwen2.5:14b", "mistral": "mistral:7b"}
LABELS = ["Raw LLM", "Vanilla RAG", "RAG + Toulmin (stmt.)", "RAG + Toulmin (J. docs)", "JUDICATA"]


def fig_citations(out):
    """OAB-2: specific citations per answer, guideline recall and precision."""
    fig, axes = plt.subplots(1, 3, figsize=(7.5, 2.6), sharey=True)
    panels = [("ncit", "Specific citations per answer", None), ("recall", "Guideline citation recall", 1),
              ("prec", "Citation precision", 1)]
    for ax, (meas, title, top) in zip(axes, panels):
        for j, (m, ml, col, mk) in enumerate(MODELS):
            ys, xs, lo, hi = [], [], [], []
            for i, (c, _) in enumerate(CONDS):
                mu, a, b = boot_ci(V[meas][(MID[m], FULL[c])].values())
                ys.append(i + (j - 0.5) * 0.3)
                xs.append(mu)
                lo.append(mu - a)
                hi.append(b - mu)
            ax.errorbar(xs, ys, xerr=[lo, hi], fmt=mk, color=col, ms=4.5, capsize=2, lw=0.9, label=ml)
        ax.set_yticks(range(len(CONDS)))
        ax.set_yticklabels(LABELS)
        ax.invert_yaxis()
        ax.set_xlim(0, top if top else ax.get_xlim()[1] * 1.05)
        ax.set_title(title)
        ax.grid(axis="x", lw=0.3, alpha=0.6)
        ax.spines[["top", "right"]].set_visible(False)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, frameon=False, loc="upper center", ncol=2)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    save(fig, out, "Fig7")


def fig_diffs(out):
    """Paired differences JUDICATA minus each comparator, bootstrap 95% CI (unadjusted)."""
    comps = [("raw", "Raw LLM"), ("vanilla", "Vanilla RAG"), ("rtstmt", "RAG + Toulmin (stmt.)"),
             ("rtjdocs", "RAG + Toulmin (J. docs)")]
    panels = [("oabone", "OAB-1 accuracy (pp)"), ("temas", "Temas all fields (pp)"),
              ("recall", "OAB-2 recall"), ("prec", "OAB-2 precision")]
    fig, axes = plt.subplots(1, 4, figsize=(7.5, 2.5), sharey=True)
    for ax, (meas, title) in zip(axes, panels):
        for j, (m, ml, col, mk) in enumerate(MODELS):
            for i, (c, _) in enumerate(comps):
                d, lo, hi, _n = (float(x) for x in N[f"diff.{meas}.{m}.{c}.vals"][0].split(","))
                y = i + (j - 0.5) * 0.3
                defect = meas == "oabone" and m == "mistral" and c in ("rtstmt", "rtjdocs")
                ax.errorbar(d, y, xerr=[[d - lo], [hi - d]], fmt=mk, ms=4.5, capsize=2, lw=0.9, color=col,
                            mfc="white" if defect else col, label=ml if (i == 0 and meas == "oabone") else None)
        ax.axvline(0, color="#333333", lw=0.7)
        ax.set_yticks(range(len(comps)))
        ax.set_yticklabels([c[1] for c in comps])
        ax.set_title(title)
        ax.grid(axis="x", lw=0.3, alpha=0.6)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylim(len(comps) - 0.5, -0.5)
    for ax in axes[:2]:
        lim = max(abs(v) for v in ax.get_xlim())
        ax.set_xlim(-lim, lim)
    for ax in axes[2:]:
        ax.set_xlim(-0.25, 0.25)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, frameon=False, loc="upper center", ncol=2)
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    save(fig, out, "Fig3")


def fig_context(out):
    """Temas: what filled the five prompt sources, and where the threshold pages ranked."""
    import json as _json
    from app.reasoning.source_hierarchy import TIERS
    corpus = _json.load(open(Path(__file__).resolve().parent.parent / "dataset" / "precedents" / "health_corpus.json",
                             encoding="utf-8"))
    corpus = corpus if isinstance(corpus, list) else next(v for v in corpus.values() if isinstance(v, list))
    thr = {x["number"] for x in corpus if x["id"].startswith("CNJ_") and "210" in _json.dumps(x, ensure_ascii=False)}
    conds = [("vanilla_rag", "Vanilla RAG"), ("rag_toulmin", "RAG + Toulmin (stmt.)"),
             ("rag_toulmin_jq", "RAG + Toulmin (J. docs)"), ("judicata", "JUDICATA"),
             ("judicata-no_hierarchy", "JUDICATA without hierarchy")]
    rows = MN.ML.by_cond(MN.A.load_results("temas"))
    cats = [("sv", "Súmula vinculante", BLUE, ""), ("lei", "Statute", GREEN, ""),
            ("thr", "CNJ guide, threshold page", VERM, "\\\\\\\\"), ("cnj", "CNJ guide, other page", SKY, "")]

    def cat(d):
        k = d.get("kind")
        if k == "SUMULA_VINCULANTE":
            return "sv"
        if k == "ORIENTACAO_ADMIN":
            return "thr" if d.get("article") in thr else "cnj"
        return "lei"

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.5, 2.7), sharey=True, gridspec_kw={"width_ratios": [1, 1.15]})
    for i, (c, _) in enumerate(conds):
        items = rows[("qwen2.5:14b", c)].values()
        cnt = {k: 0 for k, *_ in cats}
        ranks = []
        for r in items:
            docs = r["documents"]
            order = docs if c in ("vanilla_rag", "judicata-no_hierarchy") else sorted(
                docs, key=lambda d: (TIERS.get(d.get("kind"), (6,))[0], -(d.get("score") or 0)))
            for d in order[:5]:
                cnt[cat(d)] += 1
            pos = [p + 1 for p, d in enumerate(order) if cat(d) == "thr"]
            ranks.append(min(pos) if pos else None)
        left = 0
        for k, lab, col, hat in cats:
            v = cnt[k] / len(items)
            a2.barh(i, v, left=left, color=col, hatch=hat, edgecolor="#333333", lw=0.4, height=0.65,
                    label=lab if i == 0 else None)
            left += v
        got = [x for x in ranks if x]
        if got:
            jit = [((h * 37) % 11 - 5) * 0.035 for h in range(len(got))]
            a1.scatter(got, [i + t for t in jit], s=9, color=VERM, alpha=0.6, lw=0)
        if len(got) < len(ranks):
            a1.text(15.8, i, f"not retrieved: {len(ranks) - len(got)}", va="center", ha="right", fontsize=7.5)
    a1.axvspan(0.5, 5.5, color="#e8e8e8", zorder=0)
    a1.text(3, -0.75, "shown to\nthe model", ha="center", va="center", fontsize=7.5)
    a1.set_xlim(0.5, 16)
    a1.set_ylim(len(conds) - 0.5, -1.2)
    a1.set_xticks([1, 5, 10, 15])
    a1.set_xlabel("Position of the first threshold page")
    a1.set_yticks(range(len(conds)))
    a1.set_yticklabels([c[1] for c in conds])
    a2.set_xlim(0, 5)
    a2.set_xlabel("Sources in the prompt (mean of 5)")
    a2.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.45, 1.25), ncol=2, fontsize=7.5)
    for ax in (a1, a2):
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    save(fig, out, "Fig5")


def fig_qualifier(out):
    """Qualifier label against correctness of the answer (OAB-1), Wilson 95% CI."""
    import json as _json
    R = _json.load(open(MN.RES / "results.json", encoding="utf-8"))
    labs = ["INCERTO", "POSSIVEL", "PROVAVEL", "CERTO"]
    fig, ax = plt.subplots(figsize=(4.6, 2.6))
    for j, (m, ml, col, mk) in enumerate(MODELS):
        xs, ys, lo, hi, ns = [], [], [], [], []
        for i, q in enumerate(labs):
            v = R["qualifier"].get(f"OAB-1|{MID[m]}|{q}")
            if not v or not v["n"]:
                continue
            p, a, b = v["acc"]
            xs.append(i + (j - 0.5) * 0.25)
            ys.append(100 * p)
            lo.append(100 * (p - a))
            hi.append(100 * (b - p))
            ns.append(v["n"])
        ax.errorbar(xs, ys, yerr=[lo, hi], fmt=mk, color=col, ms=4.5, capsize=2, lw=0.9, label=ml)
        for x, y, n in zip(xs, ys, ns):
            ax.text(x + (-0.06 if j == 0 else 0.06), y, f"n={n}", fontsize=6.5, va="center", color="#333333",
                    ha="right" if j == 0 else "left")
    ax.set_xticks(range(len(labs)))
    ax.set_xticklabels(["INCERTO", "POSSÍVEL", "PROVÁVEL", "CERTO"])
    ax.set_xlabel("Qualifier label (increasing source support)")
    ax.set_ylabel("Correct answers (%)")
    ax.set_ylim(0, 100)
    ax.grid(axis="y", lw=0.3, alpha=0.6)
    ax.legend(frameon=False, loc="lower left")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    save(fig, out, "Fig9")


def fig_judges(out):
    """OAB-2: score of the two LLM judges on the same answers."""
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
    fig, ax = plt.subplots(figsize=(3.6, 3.2))
    hb = ax.hexbin(gx, gy, gridsize=12, extent=(0, 1, 0, 1), cmap="Blues", mincnt=1, bins="log", linewidths=0.3, edgecolors="white")
    cb = fig.colorbar(hb, ax=ax, fraction=0.05, pad=0.03)
    cb.set_label("Answers (log scale)")
    ax.plot([0, 1], [0, 1], color="#333333", lw=0.6, ls="--")
    ax.set_xlabel("Gemma 3 27B judge (score / max)")
    ax.set_ylabel("Llama 3.1 8B judge (score / max)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    fig.tight_layout()
    save(fig, out, "Fig6")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    N.update(MN.collect())
    V.update(MN.item_values())
    for fn in (fig_arch, fig_main, fig_diffs, fig_courts, fig_context, fig_judges, fig_citations, fig_security, fig_qualifier):
        fn(out)
    print(sorted(p.name for p in out.iterdir()))
