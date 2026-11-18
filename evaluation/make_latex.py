#!/usr/bin/env python3
"""
Render every results table of the manuscript (LaTeX) and a machine-readable
results.json from the stored outputs. Uses the same metric code as analyze.py.

Usage: python evaluation/make_latex.py --out ../revision/tables
"""
import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evaluation import analyze as A  # noqa: E402

RES = A.RES
DATA = A.DATA
COND_ORDER = ["raw", "vanilla_rag", "rag_toulmin", "rag_toulmin_jq", "judicata"]
COND_LABEL = {"raw": "Raw LLM", "vanilla_rag": "Vanilla RAG", "rag_toulmin": "RAG + Toulmin (statement query)",
              "rag_toulmin_jq": "RAG + Toulmin (JUDICATA docs)",
              "judicata": "JUDICATA", "judicata-no_lsim": "-- LSIM", "judicata-no_scot": "-- SCOT",
              "judicata-no_kg": "-- graph channel", "judicata-fixed_weights": "-- adaptive weights (fixed)",
              "judicata-no_hierarchy": "-- source hierarchy", "judicata-no_backing_verification": "-- Backing verification"}
ABL_ORDER = ["judicata", "judicata-no_lsim", "judicata-no_scot", "judicata-no_kg", "judicata-fixed_weights",
             "judicata-no_hierarchy", "judicata-no_backing_verification"]
MODEL_LABEL = {"qwen2.5:14b": "Qwen2.5 14B", "mistral:7b": "Mistral 7B"}
OUT = {}


def pct(t, d=1):
    if t is None or t[0] is None or (isinstance(t[0], float) and math.isnan(t[0])):
        return "--"
    return f"{100*t[0]:.{d}f} [{100*t[1]:.{d}f}, {100*t[2]:.{d}f}]"


def num(t, d=2):
    if t is None or t[0] is None or (isinstance(t[0], float) and math.isnan(t[0])):
        return "--"
    return f"{t[0]:.{d}f} [{t[1]:.{d}f}, {t[2]:.{d}f}]"


def pfmt(p):
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "--"
    return "$<$0.001" if p < 0.001 else f"{p:.3f}"


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else float("nan")


# --------------------------------------------------------------------- correctness
def oab1_correct():
    key = {json.loads(l)["id"]: json.loads(l)["answer"] for l in open(DATA / "oab1_sample.jsonl", encoding="utf-8")}
    parsed = A.load_parsed("oab1")
    rows = A.load_results("oab1")

    def ok(r):
        k = (r["model"], r["condition"], r["id"])
        a = parsed[k] if k in parsed else (A.parse_mcq(A.text_of(r)) or A.parse_mcq(r.get("answer")))
        return a == key[r["id"]]
    return rows, ok


def temas_correct():
    gold = {json.loads(l)["id"]: json.loads(l) for l in open(DATA / "temas_cases.jsonl", encoding="utf-8")}
    parsed = A.load_parsed("temas")
    rows = A.load_results("temas")

    def fields(r):
        k = (r["model"], r["condition"], r["id"])
        p = (parsed.get(k) if k in parsed else None) or A.parse_temas(r.get("answer") or "")
        g = A.gold_norm(gold[r["id"]]["gold"])
        return {f: p.get(f) == g[f] for f in ("competencia", "polo_passivo", "requisitos_cumpridos", "requisito_ausente")
                if g.get(f) is not None}
    return rows, fields


def by_cond(rows):
    d = defaultdict(dict)
    for r in rows:
        d[(r["model"], r["condition"])][r["id"]] = r
    return d


def mcnemar_vs(base, other):
    ids = set(base) & set(other)
    b = sum(1 for i in ids if base[i] and not other[i])
    c = sum(1 for i in ids if other[i] and not base[i])
    return b, c, A.mcnemar_exact(b, c)


# --------------------------------------------------------------------------- tables
def table_main(out):
    o1rows, o1ok = oab1_correct()
    t_rows, t_fields = temas_correct()
    o1, tm = by_cond(o1rows), by_cond(t_rows)
    oab2 = oab2_scores()
    lines = [r"\begin{table}[!ht]", r"\centering",
             r"\caption{{\bf Main comparison (same model, same task text and answer format).} Accuracy in \% with Wilson 95\% CI; OAB-2 guideline score in [0,1] with bootstrap 95\% CI (judge: Gemma 3 27B). Grounding: mean share of specific citations supported by the retrieved documents.}",
             r"\label{tab:main}", r"\small", r"\begin{tabular}{llcccc}", r"\hline",
             r"\textbf{Model} & \textbf{Condition} & \textbf{OAB-1 acc.} & \textbf{Temas: all fields} & \textbf{OAB-2 score} & \textbf{Grounding (Temas)}\\ \hline"]
    res = {}
    for model in MODEL_LABEL:
        for cond in COND_ORDER:
            a = o1.get((model, cond), {})
            t = tm.get((model, cond), {})
            acc1 = A.wilson(sum(o1ok(r) for r in a.values()), len(a)) if a else None
            accT = A.wilson(sum(all(t_fields(r).values()) for r in t.values()), len(t)) if t else None
            g, _, _ = A.grounding_stats(t.values()) if t and cond != "raw" else (None, 0, 0)
            sc = oab2.get(("gemma3:27b", model, cond))
            sco = A.boot_mean(list(sc.values())) if sc else None
            if not (a or t or sc):
                continue
            res[f"{model}|{cond}"] = {"oab1_acc": acc1, "oab1_n": len(a), "temas_acc": accT, "temas_n": len(t),
                                      "temas_grounding": g, "oab2_score": sco}
            lines.append(f"{MODEL_LABEL[model]} & {COND_LABEL[cond]} & {pct(acc1)} & {pct(accT)} & {num(sco)} & {num(g)}\\\\")
        lines.append(r"\hline")
    lines += [r"\end{tabular}", r"\end{table}"]
    (out / "tab_main.tex").write_text("\n".join(lines), encoding="utf-8")
    OUT["main"] = res

    # paired tests
    tl = [r"\begin{table}[!ht]", r"\centering",
          r"\caption{{\bf Paired comparisons with JUDICATA.} Exact McNemar test on the same items; $b$: items correct only with JUDICATA, $c$: items correct only with the comparator; $p$ Holm-adjusted within each model and task.}",
          r"\label{tab:tests}", r"\small", r"\begin{tabular}{lllrrr}", r"\hline",
          r"\textbf{Task} & \textbf{Model} & \textbf{Comparator} & $b$ & $c$ & $p_\text{Holm}$\\ \hline"]
    tests = {}
    for task, data, okf in (("OAB-1", o1, o1ok), ("Temas", tm, lambda r: all(t_fields(r).values()))):
        for model in MODEL_LABEL:
            if (model, "judicata") not in data:
                continue
            base = {i: okf(r) for i, r in data[(model, "judicata")].items()}
            comps = [c for c in COND_ORDER if c != "judicata" and (model, c) in data]
            stats = [mcnemar_vs(base, {i: okf(r) for i, r in data[(model, c)].items()}) for c in comps]
            adj = A.holm([s[2] for s in stats]) if stats else []
            for c, (b, cc, p), pa in zip(comps, stats, adj):
                tests[f"{task}|{model}|{c}"] = {"b": b, "c": cc, "p": p, "p_holm": pa}
                tl.append(f"{task} & {MODEL_LABEL[model]} & {COND_LABEL[c]} & {b} & {cc} & {pfmt(pa)}\\\\")
    tl += [r"\hline", r"\end{tabular}", r"\end{table}"]
    (out / "tab_tests.tex").write_text("\n".join(tl), encoding="utf-8")
    OUT["tests"] = tests

    # temas per field
    fl = [r"\begin{table}[!ht]", r"\centering",
          r"\caption{{\bf Temas 6/1234 cases: accuracy per field} (\%, Wilson 95\% CI; $n=51$ per condition).}",
          r"\label{tab:temas}", r"\small", r"\begin{tabular}{llcccc}", r"\hline",
          r"\textbf{Model} & \textbf{Condition} & \textbf{Court} & \textbf{Defendant} & \textbf{Req. met} & \textbf{Missing req.}\\ \hline"]
    tf = {}
    for model in MODEL_LABEL:
        for cond in COND_ORDER:
            t = tm.get((model, cond))
            if not t:
                continue
            d = defaultdict(list)
            for r in t.values():
                for f, v in t_fields(r).items():
                    d[f].append(v)
            cells = {f: A.wilson(sum(d[f]), len(d[f])) for f in ("competencia", "polo_passivo", "requisitos_cumpridos", "requisito_ausente")}
            tf[f"{model}|{cond}"] = cells
            fl.append(f"{MODEL_LABEL[model]} & {COND_LABEL[cond]} & " + " & ".join(pct(cells[f], 0) for f in cells) + r"\\")
        fl.append(r"\hline")
    fl += [r"\end{tabular}", r"\end{table}"]
    (out / "tab_temas.tex").write_text("\n".join(fl), encoding="utf-8")
    OUT["temas_fields"] = tf

    # ablation
    al = [r"\begin{table}[!ht]", r"\centering",
          r"\caption{{\bf Ablation of JUDICATA components.} Temas: all-fields accuracy ($n=51$); OAB-1: accuracy on a fixed random subset of 100 questions (Qwen2.5 14B only). \%, Wilson 95\% CI; $p$: exact McNemar vs.\ full system, Holm-adjusted within column.}",
          r"\label{tab:ablation}", r"\small", r"\begin{tabular}{lcccc}", r"\hline",
          r"\textbf{Configuration} & \textbf{Temas, Qwen} & \textbf{Temas, Mistral} & \textbf{OAB-1 (100), Qwen} & \textbf{Grounding, Temas Qwen}\\ \hline"]
    ab = {}
    cols = [("temas", "qwen2.5:14b", tm, lambda r: all(t_fields(r).values()), None),
            ("temas", "mistral:7b", tm, lambda r: all(t_fields(r).values()), None),
            ("oab1", "qwen2.5:14b", o1, o1ok, "abl_subset")]
    abl_ids = set()
    if (("qwen2.5:14b", "judicata-no_lsim") in o1):
        abl_ids = set(o1[("qwen2.5:14b", "judicata-no_lsim")])
    colp = []
    for task, model, data, okf, sub in cols:
        base = data.get((model, "judicata"), {})
        if sub:
            base = {i: r for i, r in base.items() if i in abl_ids}
        bok = {i: okf(r) for i, r in base.items()}
        ps = []
        for c in ABL_ORDER[1:]:
            o = data.get((model, c), {})
            ps.append(mcnemar_vs(bok, {i: okf(r) for i, r in o.items()})[2] if o and bok else float("nan"))
        valid = [p for p in ps if not math.isnan(p)]
        adj = iter(A.holm(valid)) if valid else iter([])
        colp.append({c: (next(adj) if not math.isnan(p) else float("nan")) for c, p in zip(ABL_ORDER[1:], ps)})
    for c in ABL_ORDER:
        cells = []
        for (task, model, data, okf, sub), pc in zip(cols, colp):
            o = data.get((model, c), {})
            if sub:
                o = {i: r for i, r in o.items() if i in abl_ids}
            if not o:
                cells.append("--")
                continue
            w = A.wilson(sum(okf(r) for r in o.values()), len(o))
            ab[f"{task}|{model}|{c}"] = {"acc": w, "n": len(o), "p_holm": pc.get(c)}
            cells.append(pct(w, 0) + ("" if c == "judicata" else f" ($p$={pfmt(pc.get(c))})"))
        g = tm.get(("qwen2.5:14b", c))
        gs = A.grounding_stats(g.values())[0] if g else None
        cells.append(num(gs))
        al.append(f"{COND_LABEL[c] if c != 'judicata' else 'Full JUDICATA'} & " + " & ".join(cells) + r"\\")
    al += [r"\hline", r"\end{tabular}", r"\end{table}"]
    (out / "tab_ablation.tex").write_text("\n".join(al), encoding="utf-8")
    OUT["ablation"] = ab

    # qualifier calibration
    ql = [r"\begin{table}[!ht]", r"\centering",
          r"\caption{{\bf Qualifier and correctness (JUDICATA).} Share of items in each Qualifier class and accuracy within the class (\%, Wilson 95\% CI).}",
          r"\label{tab:qualifier}", r"\small", r"\begin{tabular}{lllrc}", r"\hline",
          r"\textbf{Task} & \textbf{Model} & \textbf{Qualifier} & $n$ & \textbf{Accuracy}\\ \hline"]
    qd = {}
    for task, data, okf in (("OAB-1", o1, o1ok), ("Temas", tm, lambda r: all(t_fields(r).values()))):
        for model in MODEL_LABEL:
            g = defaultdict(list)
            for r in data.get((model, "judicata"), {}).values():
                q = str((r.get("toulmin") or {}).get("qualifier") or "blocked/error").replace("Qualifier.", "")
                g[q].append(okf(r))
            for q in sorted(g):
                w = A.wilson(sum(g[q]), len(g[q]))
                qd[f"{task}|{model}|{q}"] = {"n": len(g[q]), "acc": w}
                ql.append(f"{task} & {MODEL_LABEL[model]} & {q} & {len(g[q])} & {pct(w, 0)}\\\\")
    ql += [r"\hline", r"\end{tabular}", r"\end{table}"]
    (out / "tab_qualifier.tex").write_text("\n".join(ql), encoding="utf-8")
    OUT["qualifier"] = qd

    # latency
    ll = [r"\begin{table}[!ht]", r"\centering", r"\caption{{\bf Median latency per item (seconds), local inference.}}",
          r"\label{tab:latency}", r"\small", r"\begin{tabular}{llccc}", r"\hline",
          r"\textbf{Model} & \textbf{Condition} & \textbf{OAB-1} & \textbf{OAB-2} & \textbf{Temas}\\ \hline"]
    o2 = by_cond(A.load_results("oab2"))
    lat = {}
    for model in MODEL_LABEL:
        for cond in COND_ORDER:
            vals = [median([r.get("latency_s") for r in d.get((model, cond), {}).values()]) for d in (o1, o2, tm)]
            if all(math.isnan(v) for v in vals):
                continue
            lat[f"{model}|{cond}"] = vals
            ll.append(f"{MODEL_LABEL[model]} & {COND_LABEL[cond]} & " + " & ".join("--" if math.isnan(v) else f"{v:.1f}" for v in vals) + r"\\")
        ll.append(r"\hline")
    ll += [r"\end{tabular}", r"\end{table}"]
    (out / "tab_latency.tex").write_text("\n".join(ll), encoding="utf-8")
    OUT["latency"] = lat


def oab2_scores():
    d = defaultdict(dict)
    for p in RES.glob("oab2_*.judge-*.jsonl"):
        for l in open(p, encoding="utf-8"):
            j = json.loads(l)
            if j["score"] is not None:
                d[(j["judge"], j["model"], j["condition"])][j["id"]] = j["score"] / (j["max_points"] or 1)
    return d


def table_oab2(out):
    items = {json.loads(l)["id"]: json.loads(l) for l in open(DATA / "oab2.jsonl", encoding="utf-8")}
    o2 = by_cond(A.load_results("oab2"))
    sc = oab2_scores()
    judges = sorted({k[0] for k in sc})
    lines = [r"\begin{table}[!ht]", r"\centering",
             r"\caption{{\bf OAB second phase (150 discursive questions, official FGV guideline).} Guideline score in [0,1] per judge and deterministic recall of the provisions cited in the guideline; bootstrap 95\% CI. $p$: Wilcoxon signed-rank vs.\ JUDICATA, Holm-adjusted within model and judge.}",
             r"\label{tab:oab2}", r"\small", r"\begin{tabular}{ll" + "c" * (len(judges) + 1) + "}", r"\hline",
             r"\textbf{Model} & \textbf{Condition} & " + " & ".join(f"\\textbf{{Score ({j})}}" for j in judges) + r" & \textbf{Citation recall}\\ \hline"]
    res = {}
    for model in MODEL_LABEL:
        pv = {}
        for j in judges:
            b = sc.get((j, model, "judicata"), {})
            comps = [c for c in COND_ORDER if c != "judicata" and (j, model, c) in sc]
            ps = []
            for c in comps:
                o = sc[(j, model, c)]
                ids = [i for i in b if i in o]
                ps.append(A.wilcoxon([b[i] for i in ids], [o[i] for i in ids]) if ids else float("nan"))
            for c, p in zip(comps, A.holm(ps) if ps else []):
                pv[(j, c)] = p
        recp = {}
        if (model, "judicata") in o2:
            rb = {i: A.guideline_recall(r.get("answer") or "", items[i]["guideline"]) for i, r in o2[(model, "judicata")].items()}
            rcomps = [c for c in COND_ORDER if c != "judicata" and (model, c) in o2]
            rps = []
            for c in rcomps:
                ro = {i: A.guideline_recall(r.get("answer") or "", items[i]["guideline"]) for i, r in o2[(model, c)].items()}
                ids = [i for i in rb if rb[i] is not None and ro.get(i) is not None]
                rps.append(A.wilcoxon([rb[i] for i in ids], [ro[i] for i in ids]))
            recp = dict(zip(rcomps, A.holm(rps) if rps else []))
        for cond in COND_ORDER:
            rs = o2.get((model, cond))
            if not rs:
                continue
            rec = A.boot_mean([A.guideline_recall(r.get("answer") or "", items[r["id"]]["guideline"]) for r in rs.values()])
            cells = []
            for j in judges:
                s = sc.get((j, model, cond))
                m = A.boot_mean(list(s.values())) if s else None
                res[f"{model}|{cond}|{j}"] = m
                cells.append(num(m) + ("" if cond == "judicata" or (j, cond) not in pv else f" ($p$={pfmt(pv[(j, cond)])})"))
            res[f"{model}|{cond}|recall"] = rec
            rp = recp.get(cond)
            lines.append(f"{MODEL_LABEL[model]} & {COND_LABEL[cond]} & " + " & ".join(cells) + f" & {num(rec)}" + ("" if rp is None else f" ($p$={pfmt(rp)})") + "\\\\")
        lines.append(r"\hline")
    if len(judges) >= 2:
        a, b = judges[:2]
        common = sorted(set((k[1], k[2], i) for k in sc if k[0] == a for i in sc[k]) &
                        set((k[1], k[2], i) for k in sc if k[0] == b for i in sc[k]))
        try:
            from scipy.stats import spearmanr
            rho = spearmanr([sc[(a, m, c)][i] for m, c, i in common], [sc[(b, m, c)][i] for m, c, i in common]).correlation
            res["judge_spearman"] = rho
            res["judge_n"] = len(common)
            lines.append(r"\multicolumn{" + str(3 + len(judges) - 1) + r"}{l}{\footnotesize Inter-judge agreement: Spearman $\rho$ = " + f"{rho:.2f} over {len(common)} answers.}}\\\\")
        except Exception:
            pass
    lines += [r"\end{tabular}", r"\end{table}"]
    (out / "tab_oab2.tex").write_text("\n".join(lines), encoding="utf-8")
    OUT["oab2"] = res


SET_LABEL = {"deepset/prompt-injections|orig": "deepset (EN/DE)", "deepset/prompt-injections|pt-mt": "deepset, PT (MT)",
             "Lakera/gandalf_ignore_instructions|orig": "Lakera Gandalf (EN)", "Lakera/gandalf_ignore_instructions|pt-mt": "Lakera Gandalf, PT (MT)",
             "jackhhao/jailbreak-classification|orig": "jailbreak-classification (EN)", "jackhhao/jailbreak-classification|pt-mt": "jailbreak-classification, PT (MT)",
             "oab_exams|legit": "OAB questions (legitimate)", "inhouse_security|dev": "In-house security set (development)",
             "inhouse_p2p|dev": "In-house P2P set (development)"}


def table_security(out):
    s = json.load(open(RES / "security_summary.json", encoding="utf-8"))
    lines = [r"\begin{table}[!ht]", r"\centering",
             r"\caption{{\bf E1: rule-based defences on prompts written by third parties.} Detection rate on attacks (TPR) and on legitimate prompts (FPR), \% with Wilson 95\% CI. MT: machine translation into Portuguese. The in-house sets are development sets on which rules were revised and are shown only for comparison.}",
             r"\label{tab:security}", r"\small", r"\begin{tabular}{lrcccrc}", r"\hline",
             r"\textbf{Set} & $n_\text{att}$ & \textbf{Guardian TPR} & \textbf{P2P TPR} & \textbf{Combined TPR} & $n_\text{leg}$ & \textbf{Combined FPR}\\ \hline"]
    order = ["deepset/prompt-injections|orig", "deepset/prompt-injections|pt-mt", "Lakera/gandalf_ignore_instructions|orig",
             "Lakera/gandalf_ignore_instructions|pt-mt", "jackhhao/jailbreak-classification|orig",
             "jackhhao/jailbreak-classification|pt-mt", "oab_exams|legit", "inhouse_security|dev", "inhouse_p2p|dev"]
    for k in order:
        d = s.get(k)
        if not d:
            continue
        g = lambda key: tuple(d[key]["rate_ci95"]) if key in d else None  # noqa: E731
        n_att = d.get("combined_TPR", {}).get("n", 0)
        n_leg = d.get("combined_FPR", {}).get("n", 0)
        if k == "inhouse_security|dev":
            lines.append(r"\hline")
        lines.append(f"{SET_LABEL[k]} & {n_att or '--'} & {pct(g('guardian_TPR'))} & {pct(g('p2p_TPR'))} & {pct(g('combined_TPR'))} & {n_leg or '--'} & {pct(g('combined_FPR'))}\\\\")
    lines += [r"\hline", r"\end{tabular}", r"\end{table}"]
    (out / "tab_security.tex").write_text("\n".join(lines), encoding="utf-8")
    OUT["security"] = s


def pii(out):
    p = RES / "pii_audit.json"
    if p.exists():
        OUT["pii"] = json.load(open(p, encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in (table_security, table_main, table_oab2, pii):
        try:
            f(out)
        except FileNotFoundError as e:
            print("skip", f.__name__, e)
    json.dump(OUT, open(RES / "results.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
    # shrink tables wider than the text block (never enlarge)
    for p in out.glob("tab_*.tex"):
        s = p.read_text(encoding="utf-8")
        if r"\resizebox" not in s and r"\begin{tabular}" in s:
            s = s.replace(r"\begin{tabular}", r"\resizebox{\ifdim\width>\linewidth\linewidth\else\width\fi}{!}{\begin{tabular}", 1)
            s = s.replace(r"\end{tabular}", r"\end{tabular}}", 1)
            p.write_text(s, encoding="utf-8")
    print("written", sorted(p.name for p in out.glob("tab_*.tex")))


if __name__ == "__main__":
    main()
