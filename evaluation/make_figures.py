#!/usr/bin/env python3
"""
Figures for the revised manuscript (PLOS: TIFF, 300-600 dpi, width <= 7.5 in).
  Fig1: pipeline diagram (revised architecture, all-local)
  Fig2: main comparison (accuracy with 95% CI) from results.json
  Fig3: defences on held-out attacks from security_summary.json
Usage: python evaluation/make_figures.py --out ../revision/figures
"""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

RES = Path(__file__).parent / "results"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8})


def save(fig, out, name):
    fig.savefig(out / f"{name}.tif", dpi=400, pil_kwargs={"compression": "tiff_lzw"})
    fig.savefig(out / f"{name}.pdf")
    plt.close(fig)


def fig1(out):
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 50)
    ax.axis("off")

    def box(x, y, w, h, title, sub, fc):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2", fc=fc, ec="#333", lw=0.8))
        ax.text(x + w / 2, y + h - 2.2, title, ha="center", va="top", fontsize=6.4, weight="bold")
        ax.text(x + w / 2, y + h - 6.0, sub, ha="center", va="top", fontsize=5.6, linespacing=1.25)

    def arrow(x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", lw=0.8, color="#333"))

    ax.text(1, 48.5, "Local workstation (Ollama models, Qdrant, Neo4j, SQLite) — no cloud service", fontsize=7, style="italic", va="top")
    box(1, 27, 12, 17, "0. Pseudonymise", "names, CPF, RG,\ne-mail, phone,\nCNJ number\n(before the graph)", "#e8f1fb")
    box(16, 27, 12, 17, "1. Check input", "Guardian (29 regex)\nP2P trigger\ndetector", "#fdecea")
    box(31, 27, 14, 17, "2. Retrieve", "HyPA-RAG: dense +\nBM25 + graph, RRF\nrevoked statutes\nexcluded", "#eef7ee")
    box(48, 27, 12, 17, "3. Check docs", "RAG defender\n(TF-IDF outliers)\nGuardian", "#fdecea")
    box(63, 27, 14, 17, "4. Reason (LSIM)", "facts -> rules\n(sources ordered\nby authority tier)\n-> conclusion", "#fff6e0")
    box(80, 27, 18, 17, "5. Check output", "Guardian leakage check\nSCOT post-hoc\nvalidation (fail-closed)", "#fdecea")
    for x1, x2 in ((13.8, 15.2), (28.8, 30.2), (45.8, 47.2), (60.8, 62.2), (77.8, 79.2)):
        arrow(x1, 35.5, x2, 35.5)
    box(52, 3, 28, 18, "6. Toulmin + verification", "Claim, Data, Warrant, Backing,\nRebuttal from retrieved sources;\nevery citation checked vs. documents\nand validity; Qualifier from grounding", "#f1ecfb")
    box(83, 3, 15, 18, "7. Output", "pseudonymised answer\n+ citation check\n+ disclaimer\n(not a decision)", "#e8f1fb")
    arrow(89, 26.2, 72, 21.8)
    arrow(80.8, 12, 82.2, 12)
    box(1, 3, 44, 18, "Audit trail (append-only SQLite)", "every node writes: trace id, node, timestamp,\nmodel id, pseudonymised state\nonly a SHA-256 hash of the raw query is stored\nearly exit on any failed validation", "#f4f4f4")
    save(fig, out, "Fig1")


def fig2(out):
    p = RES / "results.json"
    if not p.exists():
        return
    R = json.load(open(p, encoding="utf-8"))["main"]
    conds = [("raw", "Raw\nLLM"), ("vanilla_rag", "Vanilla\nRAG"), ("rag_toulmin", "RAG+T\n(stmt.)"), ("rag_toulmin_jq", "RAG+T\n(J. docs)"), ("judicata", "JUDI-\nCATA")]
    models = [("qwen2.5:14b", "Qwen2.5 14B", "#2b6cb0"), ("mistral:7b", "Mistral 7B", "#c05621")]
    fig, axes = plt.subplots(1, 3, figsize=(7.5, 2.8), sharey=False)
    for ax, (key, title, scale) in zip(axes, (("oab1_acc", "E2: OAB 1st phase\n(accuracy, %)", 100),
                                              ("temas_acc", "E4: Temas 6/1234\n(all fields correct, %)", 100),
                                              ("oab2_score", "E3: OAB 2nd phase\n(guideline score)", 1))):
        for j, (m, ml, col) in enumerate(models):
            xs, ys, lo, hi = [], [], [], []
            for i, (c, _) in enumerate(conds):
                v = R.get(f"{m}|{c}", {}).get(key)
                if not v or v[0] is None:
                    continue
                xs.append(i + (j - 0.5) * 0.3)
                ys.append(v[0] * scale)
                lo.append((v[0] - v[1]) * scale)
                hi.append((v[2] - v[0]) * scale)
            ax.errorbar(xs, ys, yerr=[lo, hi], fmt="o", color=col, ms=4, capsize=2, lw=0.9, label=ml)
        ax.set_xticks(range(len(conds)))
        ax.set_xticklabels([c[1] for c in conds], fontsize=6.5)
        ax.set_title(title, fontsize=7.5)
        ax.grid(axis="y", lw=0.3, alpha=0.6)
        ax.spines[["top", "right"]].set_visible(False)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, fontsize=7, frameon=False, loc="upper center", ncol=2)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    save(fig, out, "Fig2")


def fig3(out):
    p = RES / "security_summary.json"
    if not p.exists():
        return
    s = json.load(open(p, encoding="utf-8"))
    sets = [("deepset/prompt-injections", "deepset"), ("Lakera/gandalf_ignore_instructions", "Lakera Gandalf"),
            ("jackhhao/jailbreak-classification", "jailbreak-class.")]
    fig, ax = plt.subplots(figsize=(5.2, 2.6))
    for j, (lang, lab, col) in enumerate((("orig", "original language", "#4a5568"), ("pt-mt", "Portuguese (MT)", "#2b6cb0"))):
        for i, (k, _) in enumerate(sets):
            d = s.get(f"{k}|{lang}", {}).get("combined_TPR")
            if not d:
                continue
            p_, l_, h_ = d["rate_ci95"]
            ax.bar(i + (j - 0.5) * 0.36, 100 * p_, 0.34, color=col, label=lab if i == 0 else None)
            ax.errorbar(i + (j - 0.5) * 0.36, 100 * p_, yerr=[[100 * (p_ - l_)], [100 * (h_ - p_)]], color="k", lw=0.8, capsize=2)
    ax.set_xticks(range(len(sets)))
    ax.set_xticklabels([x[1] for x in sets])
    ax.set_ylabel("Attacks flagged (%)")
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, fontsize=7)
    ax.spines[["top", "right"]].set_visible(False)
    fpr = s.get("oab_exams|legit", {}).get("combined_FPR", {}).get("rate_ci95", [0])[0]
    ax.set_title(f"E1: Guardian + P2P on third-party attacks (FPR on 2,210 OAB questions: {100*fpr:.1f}%)", fontsize=7.5)
    fig.tight_layout()
    save(fig, out, "Fig3")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    fig1(out)
    fig2(out)
    fig3(out)
    print(sorted(p.name for p in out.iterdir()))
