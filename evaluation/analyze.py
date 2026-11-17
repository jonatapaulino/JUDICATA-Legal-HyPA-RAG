#!/usr/bin/env python3
"""
Compute every number reported in the revised manuscript from the stored
result files (evaluation/results/*.jsonl). Nothing is hard-coded.

Metric definitions (also given in the paper, Section "Evaluation metrics"):
  accuracy            share of items whose parsed answer equals the official key
                      (OAB 1st phase) or the gold label (Temas cases). Unparseable
                      or blocked answers count as wrong.
  field accuracy      per-field accuracy for Temas cases (competence, defendant,
                      requirements met, missing requirement) and all-fields-correct.
  guideline score     judge score / maximum points of the official FGV guideline (OAB 2nd phase).
  guideline citation recall  |C_ans ∩ C_guide| / |C_guide|, where C are the specific
                      provisions (articles, súmulas, temas) extracted deterministically.
  citation grounding  |cited ∩ supported by retrieved documents| / |cited| per answer
                      (answers with no specific citation are excluded and counted separately).
  revoked-citation rate  share of answers citing a statute marked as revoked.
  latency             wall-clock seconds per item.
Statistics: Wilson 95% CI for proportions, percentile bootstrap (10,000 resamples)
for means, exact McNemar test for paired proportions, Wilcoxon signed-rank test
for paired scores, Holm correction within each family of comparisons.
"""
import json
import math
import random
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.reasoning.citations import extract_citations, specific_citations, _match  # noqa: E402

RES = Path(__file__).parent / "results"
DATA = Path(__file__).parent / "data"
BASE = "judicata"
rng = random.Random(7)


# ----------------------------------------------------------------------------- stats
def wilson(k, n, z=1.96):
    if not n:
        return (float("nan"),) * 3
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def boot_mean(xs, B=10000):
    xs = [x for x in xs if x is not None]
    if not xs:
        return (float("nan"),) * 3
    m = sum(xs) / len(xs)
    bs = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(B))
    return (m, bs[int(0.025 * B)], bs[int(0.975 * B) - 1])


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def wilcoxon(x, y):
    try:
        from scipy.stats import wilcoxon as w
        d = [a - b for a, b in zip(x, y) if a is not None and b is not None]
        if not any(d):
            return 1.0
        return float(w(d).pvalue)
    except Exception:
        return float("nan")


def holm(pvals):
    idx = sorted(range(len(pvals)), key=lambda i: pvals[i])
    adj, prev = [0.0] * len(pvals), 0.0
    for r, i in enumerate(idx):
        v = min(1.0, (len(pvals) - r) * pvals[i])
        prev = max(prev, v)
        adj[i] = prev
    return adj


# ---------------------------------------------------------------------------- parsing
def norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")


def parse_mcq(text):
    t = text or ""
    for pat in (r"RESPOSTA\s*[:\-]?\s*\**\s*\(?([A-D])\)?\b", r"alternativa\s+(?:correta\s+(?:é|e)\s+)?(?:a\s+)?\(?([A-D])\)",
                r"\(([A-D])\)\s*(?:é|e)\s+a\s+(?:alternativa\s+)?correta"):
        m = re.findall(pat, t, re.IGNORECASE)
        if m:
            return m[-1].upper()
    return None


REQ_KEYS = ["negativa", "conitec", "substituto", "evidencia", "laudo", "hipossuficiencia", "registro", "nenhum"]


def parse_temas(text):
    t = norm(text).replace("*", "").replace("#", "")
    for a, b in (("polo passivo", "polo_passivo"), ("requisitos cumpridos", "requisitos_cumpridos"),
                 ("requisito ausente", "requisito_ausente")):
        t = t.replace(a, b)
    out = {}
    m = re.findall(r"competencia\s*:\s*([^\n]+)", t)
    if m:
        v = m[-1]
        out["competencia"] = ("criterios do tema 1234 nao se aplicam" if "nao se aplic" in v
                              else "justica federal" if "federal" in v else "justica estadual" if "estadual" in v else v.strip())
    m = re.findall(r"polo_passivo\s*:\s*([^\n]+)", t)
    if m:
        v = m[-1]
        out["polo_passivo"] = "uniao" if "uniao" in v else "estado" if "estado" in v else "municipio" if "municipio" in v else v.strip()
    m = re.findall(r"requisitos_cumpridos\s*:\s*([^\n]+)", t)
    if m:
        v = m[-1].strip()
        out["requisitos_cumpridos"] = ("sim" if v.startswith("sim") else "nao" if (v.startswith("nao") or " nao " in f" {v} ")
                                       else "sim" if ("cumprid" in v or "preenchid" in v or "atendid" in v) else v)
    m = re.findall(r"requisito_ausente\s*:\s*([^\n]+)", t)
    if m:
        v = m[-1]
        out["requisito_ausente"] = next((k for k in REQ_KEYS if k in v),
                                        "nenhum" if ("nao ha" in v or "nenhum" in v) else v.strip())
    return out


def gold_norm(g):
    return {k: (None if v is None else norm(v)) for k, v in g.items()}


# ------------------------------------------------------------------------------- load
def load_results(prefix):
    rows = []
    for p in sorted(RES.glob(f"{prefix}_*.jsonl")):
        if ".judge-" in p.name or ".parsed" in p.name:
            continue
        rows += [json.loads(l) for l in open(p, encoding="utf-8")]
    # keep last record per (model, condition, id)
    last = {}
    for r in rows:
        last[(r["model"], r["condition"], r["id"])] = r
    return list(last.values())


def load_parsed(prefix):
    d = {}
    for p in sorted(RES.glob(f"{prefix}_*.parsed.jsonl")):
        for l in open(p, encoding="utf-8"):
            r = json.loads(l)
            d[(r["model"], r["condition"], r["id"])] = r.get("parsed")
    return d


def text_of(r):
    if r.get("toulmin"):
        return r["toulmin"].get("claim") or r.get("answer") or ""
    return r.get("answer") or ""


def grounding_stats(rows):
    g, nocite, revoked = [], 0, 0
    for r in rows:
        cc = r.get("citation_check") or {}
        if cc.get("revoked"):
            revoked += 1
        if cc.get("cited"):
            g.append(cc["grounding_rate"])
        else:
            nocite += 1
    return boot_mean(g), nocite, revoked


def fmt(x, d=3):
    return "nan" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{d}f}"


def ci(t, d=3):
    return f"{fmt(t[0], d)} [{fmt(t[1], d)}, {fmt(t[2], d)}]"


# ------------------------------------------------------------------------------ tasks
def analyze_binary(rows, correct_fn, label):
    by = defaultdict(dict)
    for r in rows:
        by[(r["model"], r["condition"])][r["id"]] = r
    lines, table = [f"\n## {label}\n", "| Model | Condition | n | Accuracy [95% CI] | Blocked/err | Grounding [95% CI] | No-citation | Revoked-cit. | Median latency (s) |",
                    "|---|---|---|---|---|---|---|---|---|"], {}
    for (model, cond), items in sorted(by.items()):
        corr = {i: correct_fn(r) for i, r in items.items()}
        k, n = sum(corr.values()), len(corr)
        blocked = sum(1 for r in items.values() if r.get("blocked_or_error") or r.get("exception"))
        gst, nocite, rev = grounding_stats(items.values())
        lat = sorted(r.get("latency_s") or 0 for r in items.values())
        table[(model, cond)] = corr
        lines.append(f"| {model} | {cond} | {n} | {ci(wilson(k, n))} | {blocked} | {ci(gst)} | {nocite} | {rev} | {fmt(lat[len(lat)//2], 1)} |")
    # paired tests vs JUDICATA within each model
    lines += ["", f"Paired exact McNemar tests vs `{BASE}` (Holm-adjusted within model):", "",
              "| Model | Comparison | JUDICATA-only correct | Other-only correct | p | p (Holm) |", "|---|---|---|---|---|---|"]
    for model in sorted({m for m, _ in table}):
        if (model, BASE) not in table:
            continue
        base = table[(model, BASE)]
        comps = [(c, t) for (m, c), t in table.items() if m == model and c != BASE]
        ps, rowsout = [], []
        for c, t in comps:
            ids = set(base) & set(t)
            b = sum(1 for i in ids if base[i] and not t[i])
            cc = sum(1 for i in ids if t[i] and not base[i])
            p = mcnemar_exact(b, cc)
            ps.append(p)
            rowsout.append((c, b, cc, p))
        for (c, b, cc, p), pa in zip(rowsout, holm(ps) if ps else []):
            lines.append(f"| {model} | {BASE} vs {c} | {b} | {cc} | {fmt(p, 4)} | {fmt(pa, 4)} |")
    return lines, table


def qualifier_calibration(rows, correct_fn, label):
    lines = [f"\n### Qualifier calibration ({label}, `{BASE}`)\n", "| Model | Qualifier | n | Accuracy [95% CI] |", "|---|---|---|---|"]
    by = defaultdict(list)
    for r in rows:
        if r["condition"] == BASE and r.get("toulmin"):
            by[(r["model"], str(r["toulmin"].get("qualifier")).replace("Qualifier.", ""))].append(correct_fn(r))
    for (m, q), v in sorted(by.items(), key=lambda x: (x[0][0], str(x[0][1]))):
        lines.append(f"| {m} | {q} | {len(v)} | {ci(wilson(sum(v), len(v)))} |")
    return lines


def oab1():
    key = {json.loads(l)["id"]: json.loads(l)["answer"] for l in open(DATA / "oab1_sample.jsonl", encoding="utf-8")}
    rows = load_results("oab1")
    if not rows:
        return []

    parsed = load_parsed("oab1")

    def correct(r):
        k = (r["model"], r["condition"], r["id"])
        a = parsed[k] if k in parsed else (parse_mcq(text_of(r)) or parse_mcq(r.get("answer")))
        return a == key[r["id"]]
    lines, _ = analyze_binary(rows, correct, "E2 - OAB 1st phase (official answer key)")
    return lines + qualifier_calibration(rows, correct, "OAB 1st phase")


def temas():
    gold = {json.loads(l)["id"]: json.loads(l) for l in open(DATA / "temas_cases.jsonl", encoding="utf-8")}
    rows = load_results("temas")
    if not rows:
        return []

    parsed = load_parsed("temas")

    def fields(r):
        k = (r["model"], r["condition"], r["id"])
        p = (parsed.get(k) if k in parsed else None) or parse_temas(r.get("answer") or "")
        g = gold_norm(gold[r["id"]]["gold"])
        res = {}
        for f in ("competencia", "polo_passivo", "requisitos_cumpridos", "requisito_ausente"):
            if g.get(f) is None:
                continue
            res[f] = p.get(f) == g[f]
        return res

    lines, _ = analyze_binary(rows, lambda r: all(fields(r).values()), "E4 - Temas 6/1234 cases (all fields correct)")
    lines += ["", "Per-field accuracy:", "", "| Model | Condition | Competence | Defendant | Requirements met | Missing requirement |", "|---|---|---|---|---|---|"]
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        for f, v in fields(r).items():
            by[(r["model"], r["condition"])][f].append(v)
    for (m, c), d in sorted(by.items()):
        cells = [ci(wilson(sum(d[f]), len(d[f])), 2) for f in ("competencia", "polo_passivo", "requisitos_cumpridos", "requisito_ausente")]
        lines.append(f"| {m} | {c} | " + " | ".join(cells) + " |")
    return lines + qualifier_calibration(rows, lambda r: all(fields(r).values()), "Temas")


def guideline_recall(answer, guideline):
    g = [c.key for c in specific_citations(extract_citations(guideline))]
    if not g:
        return None
    a = {c.key for c in specific_citations(extract_citations(answer))}
    hit = sum(1 for k in g if _match(k, a) or any(_match(x, {k}) for x in a))
    return hit / len(g)


def oab2():
    items = {json.loads(l)["id"]: json.loads(l) for l in open(DATA / "oab2.jsonl", encoding="utf-8")}
    rows = load_results("oab2")
    if not rows:
        return []
    judges = defaultdict(dict)
    for p in RES.glob("oab2_*.judge-*.jsonl"):
        for l in open(p, encoding="utf-8"):
            j = json.loads(l)
            if j["score"] is not None:
                judges[j["judge"]][(j["model"], j["condition"], j["id"])] = j["score"] / (j["max_points"] or 1)
    lines = ["\n## E3 - OAB 2nd phase (official FGV guideline)\n",
             "| Model | Condition | n | Guideline citation recall [95% CI] | " + " | ".join(f"Score/{j} [95% CI]" for j in sorted(judges)) + " | Grounding | Median latency (s) |",
             "|---|---|---|---|" + "---|" * len(judges) + "---|---|"]
    by = defaultdict(list)
    for r in rows:
        by[(r["model"], r["condition"])].append(r)
    scores = {}
    for (m, c), rs in sorted(by.items()):
        rec = [guideline_recall(r.get("answer") or "", items[r["id"]]["guideline"]) for r in rs]
        js = []
        for j in sorted(judges):
            s = {r["id"]: judges[j].get((m, c, r["id"])) for r in rs}
            scores[(j, m, c)] = s
            js.append(ci(boot_mean(list(s.values()))))
        gst, _, _ = grounding_stats(rs)
        lat = sorted(r.get("latency_s") or 0 for r in rs)
        lines.append(f"| {m} | {c} | {len(rs)} | {ci(boot_mean(rec))} | " + " | ".join(js) + f" | {ci(gst)} | {fmt(lat[len(lat)//2], 1)} |")
    for j in sorted(judges):
        lines += ["", f"Paired Wilcoxon vs `{BASE}` (judge {j}, Holm within model):", "", "| Model | Comparison | mean diff | p | p (Holm) |", "|---|---|---|---|---|"]
        for m in sorted({k[1] for k in scores}):
            if (j, m, BASE) not in scores:
                continue
            b = scores[(j, m, BASE)]
            comps = [c for (jj, mm, c) in scores if jj == j and mm == m and c != BASE]
            ps, outs = [], []
            for c in comps:
                o = scores[(j, m, c)]
                ids = [i for i in b if b[i] is not None and o.get(i) is not None]
                x, y = [b[i] for i in ids], [o[i] for i in ids]
                ps.append(wilcoxon(x, y))
                outs.append((c, (sum(x) - sum(y)) / max(1, len(ids))))
            for (c, d), p, pa in zip(outs, ps, holm(ps) if ps else []):
                lines.append(f"| {m} | {BASE} vs {c} | {fmt(d)} | {fmt(p, 4)} | {fmt(pa, 4)} |")
    if len(judges) >= 2:
        a, b = sorted(judges)[:2]
        common = sorted(set(judges[a]) & set(judges[b]))
        try:
            from scipy.stats import spearmanr
            rho = spearmanr([judges[a][k] for k in common], [judges[b][k] for k in common]).correlation
            lines.append(f"\nInter-judge agreement ({a} vs {b}): Spearman rho = {fmt(rho)} over {len(common)} answers.")
        except Exception:
            pass
    return lines


def security():
    p = RES / "security_summary.json"
    if not p.exists():
        return []
    s = json.load(open(p, encoding="utf-8"))
    lines = ["\n## E1 - Defence layers (deterministic; held-out sets)\n",
             "| Set | Guardian TPR | P2P TPR | Combined TPR | Guardian FPR | P2P FPR | Combined FPR |", "|---|---|---|---|---|---|---|"]
    for name, d in sorted(s.items()):
        cell = lambda k: (ci(tuple(d[k]["rate_ci95"])) + f" (n={d[k]['n']})") if k in d else "-"  # noqa: E731
        lines.append(f"| {name} | {cell('guardian_TPR')} | {cell('p2p_TPR')} | {cell('combined_TPR')} | "
                     f"{cell('guardian_FPR')} | {cell('p2p_FPR')} | {cell('combined_FPR')} |")
    return lines


def pii():
    p = RES / "pii_audit.json"
    if not p.exists():
        return []
    s = json.load(open(p, encoding="utf-8"))
    return ["\n## E6 - Personal-data leakage audit\n",
            f"- Queries: {len(s['cases'])}; LLM prompts intercepted: {s['total_llm_prompts']}; audit rows: {s['audit_rows']}",
            f"- Raw identifiers found in LLM prompts: {s['total_pii_leaks_to_llm']}",
            f"- Raw identifiers found in the audit trail: {len(s['pii_in_audit_trail'])} {s['pii_in_audit_trail']}"]


def main():
    out = ["# Results (generated by evaluation/analyze.py)\n"]
    for f in (security, oab1, oab2, temas, pii):
        out += f()
    (RES / "RESULTS.md").write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
