#!/usr/bin/env python3
"""
Render the results tables of the manuscript from the same numbers that
make_numbers.py writes for the running text, so that text and tables cannot
diverge. Layout: PLOS ONE (caption above, notes below), booktabs + tabularx at
full width, the same font size and row spacing in every table.

Usage: python evaluation/make_tables.py --out ../revision/v3/tables
The preamble must define the column types L and C and the \\tablenota command:
  \\newcolumntype{L}{>{\\raggedright\\arraybackslash}X}
  \\newcolumntype{C}{>{\\centering\\arraybackslash}X}
  \\newcommand{\\tablenota}[1]{\\par\\smallskip\\begin{minipage}{\\linewidth}\\scriptsize #1\\end{minipage}}
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evaluation import make_numbers as MN  # noqa: E402

N = {}
MODELS = [("qwen", "Qwen2.5 14B"), ("mistral", "Mistral 7B")]
CONDS = [("raw", "Raw LLM"), ("vanilla", "Vanilla RAG"), ("rtstmt", "RAG + Toulmin (statement query)"),
         ("rtjdocs", "RAG + Toulmin (JUDICATA docs)"), ("judicata", "JUDICATA")]
ABL = [("full", "Full JUDICATA"), ("nolsim", "without LSIM"), ("noscot", "without SCOT"), ("nokg", "without graph channel"),
       ("fixedw", "fixed fusion weights"), ("nohier", "without source hierarchy"), ("noverif", "without Backing verification")]


def v(key):
    if key not in N:
        raise KeyError(key)
    return N[key][0].replace("<", "$<$")


def ci(key):
    if key not in N or N[key][0] == "n.a.":
        return "n.a."
    return f"{v(key)} [{v(key + '.lo')}, {v(key + '.hi')}]"


def table(name, header, rows, caption, label, types, note=None, wide=False, groups=None):
    """rows: list of lists, or a str for a group header spanning all columns."""
    n = len(header)
    assert len(types) == n, (name, types, header)
    assert len(caption.split()) <= 12, caption
    out = [r"\begin{table}[!t]"]
    out += [r"\centering", rf"\caption{{{{\bf {caption}.}}}}", rf"\label{{{label}}}", r"\footnotesize",
            rf"\begin{{tabularx}}{{\linewidth}}{{{types}}}", r"\toprule"]
    if groups:
        cells, j = [], 1
        while j <= n:
            g = next((g for g in groups if g[1] == j), None)
            if g:
                cells.append(rf"\multicolumn{{{g[2] - g[1] + 1}}}{{c}}{{{g[0]}}}")
                j = g[2] + 1
            else:
                cells.append("")
                j += 1
        out.append(" & ".join(cells) + r" \\")
        out.append(" ".join(rf"\cmidrule(lr){{{a}-{b}}}" for _, a, b in groups))
    out += [" & ".join(header) + r" \\", r"\midrule"]
    first = True
    for r in rows:
        if isinstance(r, str):
            if not first:
                out.append(r"\midrule")
            out.append(rf"\multicolumn{{{n}}}{{l}}{{\textit{{{r}}}}} \\")
        else:
            assert len(r) == n, (name, r)
            assert all(str(c).strip() for c in r), (name, r)
            out.append(" & ".join(str(c) for c in r) + r" \\")
        first = False
    out += [r"\bottomrule", r"\end{tabularx}"]
    if note:
        out.append(rf"\tablenota{{{note}}}")
    out.append(r"\end{table}")
    (OUT / f"{name}.tex").write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


def t_main():
    rows = []
    for m, ml in MODELS:
        rows.append(ml)
        for c, cl in CONDS:
            rows.append([cl, ci(f"oabone.{m}.{c}.acc"), v(f"oabone.{m}.{c}.noanswer"),
                         ci(f"oabtwo.{m}.{c}.recall"), ci(f"temas.{m}.{c}.all")])
    table("tab_main", ["Condition", "OAB-1 accuracy (\\%)", "OAB-1 no answer ($n$)", "OAB-2 guideline citation recall",
                       "Temas: all fields correct (\\%)"], rows,
          "Main comparison on the three tasks", "tab:main", "LCCCC", wide=True,
          note=(f"Same model, task text and answer format in every condition. OAB-1: {v('oabone.n')} first-phase questions, "
                "accuracy against the official key with Wilson 95\\% CI; answers with no identifiable alternative count as wrong. "
                f"OAB-2: the {v('oabtwo.recall.n')} of {v('oabtwo.sample')} sampled second-phase questions whose guideline cites a "
                "specific provision; share of the provisions cited in the official FGV guideline "
                "that the answer also cites (deterministic), mean with bootstrap 95\\% CI. "
                f"Temas: {v('temas.cases')} synthetic health-litigation cases, share with all four fields correct, Wilson 95\\% CI."))


def t_tests():
    rows = []
    for m, ml in MODELS:
        rows.append(ml)
        for c, cl in CONDS[:-1]:
            rows.append([cl, v(f"oabone.{m}.{c}.mcn.b"), v(f"oabone.{m}.{c}.mcn.c"), v(f"oabone.{m}.{c}.mcn.pholm"),
                         v(f"temas.{m}.{c}.mcn.b"), v(f"temas.{m}.{c}.mcn.c"), v(f"temas.{m}.{c}.mcn.pholm")])
    table("tab_tests", ["Comparator", "$b$", "$c$", "$p_\\text{Holm}$", "$b$", "$c$", "$p_\\text{Holm}$"], rows,
          "Paired comparisons of each baseline with JUDICATA", "tab:tests", "Lcccccc",
          groups=[("OAB-1", 2, 4), ("Temas (all fields)", 5, 7)],
          note=("Exact McNemar test on the same items. $b$: items correct only with JUDICATA; $c$: items correct only with "
                "the comparator. $p$ Holm-adjusted within each model and task."))


def t_oab2():
    rows = []
    for m, ml in MODELS:
        rows.append(ml)
        for c, cl in CONDS:
            j = c == "judicata"
            rows.append([cl, ci(f"oabtwo.{m}.{c}.gemma"), "ref." if j else v(f"oabtwo.{m}.{c}.gemma.pholm"),
                         ci(f"oabtwo.{m}.{c}.llama"), "ref." if j else v(f"oabtwo.{m}.{c}.llama.pholm"),
                         ci(f"oabtwo.{m}.{c}.recall"), "ref." if j else v(f"oabtwo.{m}.{c}.recall.pholm"),
                         ci(f"oabtwo.{m}.{c}.prec"), v(f"oabtwo.{m}.{c}.ncit")])
    table("tab_oab2", ["Condition", "Score", "$p_\\text{Holm}$", "Score", "$p_\\text{Holm}$", "Recall", "$p_\\text{Holm}$",
                       "Precision", "Cit."], rows,
          "OAB second phase: judge scores and guideline citations", "tab:oab2", "LCcCcCcCc", wide=True,
          groups=[("Gemma 3 27B judge", 2, 3), ("Llama 3.1 8B judge", 4, 5), ("Guideline citations (deterministic)", 6, 9)],
          note=(f"{v('oabtwo.sample')} discursive sub-questions ({v('oabtwo.recall.n')} with specific provisions in the guideline "
                "for recall and precision). Score: judge score divided by the maximum points of the official "
                "guideline, in [0, 1]. Recall: share of the provisions cited in the guideline that the answer also cites. "
                "Precision: share of the answer's specific citations that the guideline also cites. Cit.: specific "
                "citations per answer. "
                "Means with bootstrap 95\\% CI. $p$: Wilcoxon signed-rank test against JUDICATA (ref.), Holm-adjusted within "
                f"model and measure. Agreement between the judges: Spearman $\\rho={v('oabtwo.rho')}$ over {v('oabtwo.rhon')} answers."))


def t_security():
    sets = [("deepset", "orig", "deepset prompt injections (EN, DE)"), ("deepset", "mt", "deepset, Portuguese (MT)"),
            ("lakera", "orig", "Lakera Gandalf (EN)"), ("lakera", "mt", "Lakera Gandalf, Portuguese (MT)"),
            ("jackhhao", "orig", "jailbreak-classification (EN)"), ("jackhhao", "mt", "jailbreak-classification, Portuguese (MT)")]
    rows = ["Prompts written by third parties"]
    for s, var, lab in sets:
        b = f"sec.{s}.{var}"
        rows.append([lab, v(f"{b}.natt"), ci(f"{b}.guardiantpr"), ci(f"{b}.p2ptpr"), ci(f"{b}.combinedtpr"),
                     v(f"{b}.nleg") if f"{b}.nleg" in N else "n.a.", ci(f"{b}.combinedfpr")])
    rows.append(["OAB first-phase questions (legitimate)", "n.a.", "n.a.", "n.a.", "n.a.", v("sec.oab.n"), ci("sec.oab.fpr")])
    rows.append("Development sets (rules revised on them)")
    rows.append(["In-house security set", v("sec.devsec.natt"), "n.a.", "n.a.", ci("sec.devsec.tpr"), "n.a.", "n.a."])
    rows.append(["In-house P2P set", v("sec.devp2p.natt"), "n.a.", "n.a.", ci("sec.devp2p.tpr"), "n.a.", "n.a."])
    table("tab_security", ["Set", "$n_\\text{att}$", "Guardian TPR (\\%)", "P2P TPR (\\%)", "Combined TPR (\\%)",
                           "$n_\\text{leg}$", "Combined FPR (\\%)"], rows,
          "Rule-based defenses on held-out and development prompts", "tab:security", "LcCCCcC", wide=True,
          note=("TPR: share of attacks flagged; FPR: share of legitimate prompts flagged; Wilson 95\\% CI. "
                "MT: machine translation into Portuguese of a stratified sample of 100 attacks per set. "
                "n.a.: not applicable (the set has no prompts of that class) or not computed for the development sets."))


def t_temas():
    rows = ["Trivial baseline", ["Majority answer of the field"] + [v(f"temas.triv.{f}.acc")
                                                                   for f in ("court", "defendant", "reqmet", "reqmissing")]]
    for m, ml in MODELS:
        rows.append(ml)
        for c, cl in CONDS:
            rows.append([cl] + [ci(f"temas.{m}.{c}.{f}") for f in ("court", "defendant", "reqmet", "reqmissing")])
    table("tab_temas", ["Condition", "Competent court", "Defendant", "Requirements met", "Missing requirement"], rows,
          "Temas 6 and 1234 cases: accuracy per field", "tab:temas", "LCCCC", wide=True,
          note=(f"Percentage of the {v('temas.cases')} cases with the field correct, Wilson 95\\% CI. Defendant is scored only "
                "on the cases in which the gold label defines it. Majority answer: the most frequent gold value of each field (state "
                "courts; the state; requirements not met; none missing), given in every case. Paired tests per field: "
                "Table~\\ref{tab:temastests}."))


def t_ablation():
    rows = []
    for a, al in ABL:
        rows.append([al, ci(f"abl.temas.qwen.{a}"), ci(f"abl.temas.mistral.{a}"), ci(f"abl.oabone.qwen.{a}"),
                     ci(f"abl.temas.qwen.{a}.grounding"), v(f"abl.temas.qwen.{a}.lat")])
    ps = [N[k][0] for k in N if k.startswith("abl.") and k.endswith(".pholm")]
    pmin = min(ps, key=lambda x: float(x.replace("<", "")))
    table("tab_ablation", ["Configuration", "Temas, Qwen (\\%)", "Temas, Mistral (\\%)", "OAB-1 subset, Qwen (\\%)",
                           "Grounding, Temas, Qwen", "Latency, Temas, Qwen (s)"], rows,
          "Ablation of JUDICATA components", "tab:ablation", "LCCCCC", wide=True,
          note=(f"Temas: all fields correct ({v('temas.cases')} cases). OAB-1 subset: fixed random subset of "
                f"{v('abl.oabone.qwen.nolsim.n')} questions. Wilson 95\\% CI. Grounding: mean share of specific citations supported by "
                "the retrieved documents, bootstrap 95\\% CI. Latency: median per case. Exact McNemar test of each ablation against the "
                f"full system, Holm-adjusted within column: smallest $p_\\text{{Holm}}={pmin}$."))


def t_qualifier():
    rows = []
    for t, tl in (("oabone", "OAB-1"), ("temas", "Temas")):
        for m, ml in MODELS:
            rows.append(f"{tl}, {ml}")
            for q, ql in (("certo", "CERTO"), ("provavel", "PROVÁVEL"), ("possivel", "POSSÍVEL"), ("incerto", "INCERTO")):
                k = f"qual.{t}.{m}.{q}"
                if f"{k}.n" in N:
                    rows.append([ql, v(f"{k}.n"), ci(f"{k}.acc")])
    table("tab_qualifier", ["Qualifier", "Answers ($n$)", "Correct (\\%)"], rows,
          "JUDICATA Qualifier label and correctness of the answer", "tab:qualifier", "LCC",
          note="Answers of JUDICATA in each Qualifier class and the share of them that are correct, Wilson 95\\% CI.")


def t_latency():
    rows = []
    for m, ml in MODELS:
        rows.append(ml)
        for c, cl in CONDS:
            rows.append([cl, v(f"lat.oabone.{m}.{c}"), v(f"lat.oabtwo.{m}.{c}"), v(f"lat.temas.{m}.{c}")])
    table("tab_latency", ["Condition", "OAB-1 (s)", "OAB-2 (s)", "Temas (s)"], rows,
          "Median latency per item with local inference", "tab:latency", "LCCC",
          note="Wall-clock seconds per item on the workstation described in Table~\\ref{tab:setup}.")


def t_volume():
    """OAB-2 recall at equal citation volume and F1 (second-round review, N2)."""
    rows = []
    for m, ml in MODELS:
        rows.append(ml)
        for c, cl in CONDS:
            if c == "judicata":
                rows.append([cl, ci(f"oabtwo.{m}.{c}.recall"), v(f"oabtwo.{m}.{c}.ncit"), "ref.", "ref.",
                             ci(f"oabtwo.{m}.{c}.fone")])
            else:
                rows.append([cl, ci(f"oabtwo.{m}.{c}.recall"), v(f"oabtwo.{m}.{c}.ncit"), v(f"eqvol.{m}.{c}.j"),
                             f"{v(f'eqvol.{m}.{c}.diff')} [{v(f'eqvol.{m}.{c}.lo')}, {v(f'eqvol.{m}.{c}.hi')}]",
                             ci(f"oabtwo.{m}.{c}.fone")])
    table("tab_volume", ["Condition", "Recall", "Cit.", "JUDICATA recall, same $k$", "Difference", "F1"], rows,
          "OAB second phase: guideline recall at equal citation volume", "tab:volume", "LCcccC", wide=True,
          note=(f"{v('eqvol.n')} items. Recall and Cit.: the condition's guideline recall and specific citations per answer. "
                "JUDICATA recall, same $k$: JUDICATA's answer cut to its first $k$ specific citations, in order of appearance, "
                "with $k$ the number of specific citations of the comparator on the same item. Difference: JUDICATA at the same "
                "$k$ minus the comparator, paired bootstrap 95\\% CI. F1: per-item harmonic mean of recall and precision, mean "
                "with bootstrap 95\\% CI."))


def t_grounding():
    """Citation grounding in the three tasks, all citations and named-statute citations only (N5)."""
    rows = []
    for m, ml in MODELS:
        rows.append(ml)
        for c, cl in CONDS[1:]:
            r = [cl]
            for t in ("oabone", "oabtwo", "temas"):
                r += [v(f"ground.{t}.{m}.{c}"), v(f"ground.{t}.{m}.{c}.det"), v(f"ground.{t}.{m}.{c}.undet")]
            rows.append(r)
    table("tab_grounding", ["Condition", "All", "Named", "Unnamed (\\%)", "All", "Named", "Unnamed (\\%)", "All",
                            "Named", "Unnamed (\\%)"], rows,
          "Citation grounding by task and condition", "tab:grounding", "Lccccccccc", wide=True,
          groups=[("OAB-1", 2, 4), ("OAB-2", 5, 7), ("Temas", 8, 10)],
          note=("All: mean share of an answer's specific citations found among its retrieved documents (Eq~\\ref{eq:grounding}), "
                "over answers with at least one citation. Named: the same, counting only citations whose statute or court is "
                "named. Unnamed: share of the citations that name an article without its statute; the check matches them to an "
                "article with that number in any retrieved document. The raw model retrieves nothing and is omitted."))


def t_temastests():
    """Health cases, per-field paired tests of each comparator against JUDICATA (N3)."""
    rows = []
    fields = ("court", "defendant", "reqmet", "reqmissing")
    for m, ml in MODELS:
        rows.append(ml)
        for c, cl in CONDS[:-1]:
            rows.append([cl] + [f"{v(f'temas.{m}.{c}.{f}.b')}/{v(f'temas.{m}.{c}.{f}.c')}; {v(f'temas.{m}.{c}.{f}.pholm')}"
                                for f in fields])
    table("tab_temastests", ["Comparator", "Competent court", "Defendant", "Requirements met", "Missing requirement"], rows,
          "Temas cases: paired tests per field against JUDICATA", "tab:temastests", "LCCCC", wide=True,
          note=("Each cell: $b$/$c$; $p_\\text{Holm}$. $b$: cases correct only with JUDICATA; $c$: cases correct only with the "
                "comparator. Exact McNemar test, Holm-adjusted over the four comparators within each model and field. "
                "The two six-component baselines received competing format instructions on these cases (see text)."))


def main():
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    OUT = Path(a.out)
    OUT.mkdir(parents=True, exist_ok=True)
    N.update(MN.collect())
    for f in (t_main, t_tests, t_oab2, t_volume, t_grounding, t_security, t_temas, t_temastests, t_ablation,
              t_qualifier, t_latency):
        f()
    print("written", sorted(p.name for p in OUT.glob("tab_*.tex")))


if __name__ == "__main__":
    main()
