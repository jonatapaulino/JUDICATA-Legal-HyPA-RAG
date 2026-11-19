#!/usr/bin/env python3
"""
Write every number quoted in the running text of the manuscript as a LaTeX macro,
computed from the stored outputs. The manuscript never types a result by hand: it
uses \\N{key}, and this script defines each key.

Outputs (in --out):
  numeros.tex   \\judnum{key}{value} for every key
  numeros.csv   key, value, source (file or computation), evidence label

Usage: python evaluation/make_numbers.py --out ../revision/v3
Run after make_latex.py (it reads results/results.json written by that script and
recomputes the remaining quantities from results/*.jsonl).
"""
import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evaluation import analyze as A  # noqa: E402
from evaluation import make_latex as ML  # noqa: E402

RES = A.RES
DATA = A.DATA
MODELS = {"qwen2.5:14b": "qwen", "mistral:7b": "mistral"}
CONDS = {"raw": "raw", "vanilla_rag": "vanilla", "rag_toulmin": "rtstmt", "rag_toulmin_jq": "rtjdocs", "judicata": "judicata"}
ABL = {"judicata-no_lsim": "nolsim", "judicata-no_scot": "noscot", "judicata-no_kg": "nokg",
       "judicata-fixed_weights": "fixedw", "judicata-no_hierarchy": "nohier", "judicata-no_backing_verification": "noverif"}
ROWS = []  # (key, value, source, label)


def put(key, value, source, label="medido"):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        value = "n.a."
    ROWS.append((key, str(value), source, label))


def p1(x):  # proportion -> percent, one decimal, half-up
    return f"{math.floor(1000 * x + 0.5) / 10:.1f}"


def p0(x):
    return f"{math.floor(100 * x + 0.5):.0f}"


def d2(x):
    return f"{math.floor(100 * x + 0.5) / 100:.2f}"


def d1(x):
    return f"{math.floor(10 * x + 0.5) / 10:.1f}"


def pv(p):
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "n.a."
    return "<0.001" if p < 0.001 else f"{math.floor(1000 * p + 0.5) / 1000:.3f}"


def thousands(n):
    return f"{n:,}"


def ci_pct(key, t, src, dec=1):
    f = p1 if dec == 1 else p0
    put(key, f(t[0]), src)
    put(key + ".lo", f(t[1]), src)
    put(key + ".hi", f(t[2]), src)


def ci_num(key, t, src):
    put(key, d2(t[0]), src)
    put(key + ".lo", d2(t[1]), src)
    put(key + ".hi", d2(t[2]), src)


# ------------------------------------------------------------------------------ corpus
def corpus():
    s1 = list(csv.DictReader(open(RES / "S1_legislation.csv", encoding="utf-8")))
    s2 = list(csv.DictReader(open(RES / "S2_sumulas.csv", encoding="utf-8")))
    s3 = list(csv.DictReader(open(RES / "S3_extra_documents.csv", encoding="utf-8")))
    src = "results/S1_legislation.csv"
    vig = [r for r in s1 if r["status"] != "revogada"]
    put("corpus.statutes.catalogue", len(s1), src)
    put("corpus.statutes.revoked", len(s1) - len(vig), src)
    put("corpus.statutes", len(vig), src)
    put("corpus.articles", thousands(sum(int(r["articles_indexed"] or 0) for r in s1)), src)
    put("corpus.sumulas", len(s2), "results/S2_sumulas.csv")
    by_court = Counter(r["court"] for r in s2)
    for c, n in by_court.items():
        put(f"corpus.sumulas.{c.lower()}", n, "results/S2_sumulas.csv")
    put("corpus.sv", sum(1 for r in s2 if r["kind"] != "sumula"), "results/S2_sumulas.csv")
    put("corpus.extra", len(s3), "results/S3_extra_documents.csv")
    put("corpus.cnjpages", sum(1 for r in s3 if r["court"] == "CNJ"), "results/S3_extra_documents.csv")


# ---------------------------------------------------------------------------- security
SETS = {"deepset/prompt-injections": "deepset", "Lakera/gandalf_ignore_instructions": "lakera",
        "jackhhao/jailbreak-classification": "jackhhao"}


def security(R):
    s = R["security"]
    src = "results/security_summary.json"
    att_orig = att_mt = ben = 0
    for full, k in SETS.items():
        for var, v in (("orig", "orig"), ("pt-mt", "mt")):
            d = s.get(f"{full}|{var}", {})
            for m in ("guardian_TPR", "p2p_TPR", "combined_TPR", "combined_FPR", "guardian_FPR", "p2p_FPR"):
                if m in d:
                    ci_pct(f"sec.{k}.{v}.{m.replace('_', '').lower()}", d[m]["rate_ci95"], src)
            if "combined_TPR" in d:
                put(f"sec.{k}.{v}.natt", thousands(d["combined_TPR"]["n"]), src)
                if v == "orig":
                    att_orig += d["combined_TPR"]["n"]
                else:
                    att_mt += d["combined_TPR"]["n"]
            if "combined_FPR" in d:
                put(f"sec.{k}.{v}.nleg", thousands(d["combined_FPR"]["n"]), src)
                put(f"sec.{k}.{v}.kleg", d["combined_FPR"]["k"], src)
                ben += d["combined_FPR"]["n"]
    put("sec.att.orig", thousands(att_orig), src)
    put("sec.att.mt", thousands(att_mt), src)
    put("sec.att.total", thousands(att_orig + att_mt), src)
    put("sec.benign.thirdparty", thousands(ben), src)
    put("sec.thirdparty.total", thousands(att_orig + ben), src)
    o = s["oab_exams|legit"]
    put("sec.oab.n", thousands(o["combined_FPR"]["n"]), src)
    put("sec.oab.k", o["combined_FPR"]["k"], src)
    ci_pct("sec.oab.fpr", o["combined_FPR"]["rate_ci95"], src)
    for k, name in (("inhouse_security|dev", "devsec"), ("inhouse_p2p|dev", "devp2p")):
        d = s[k]
        ci_pct(f"sec.{name}.tpr", d["combined_TPR"]["rate_ci95"], src)
        put(f"sec.{name}.natt", d["combined_TPR"]["n"], src)
    tprs = [s[f"{f}|{v}"]["combined_TPR"]["rate_ci95"][0] for f in SETS for v in ("orig", "pt-mt")]
    put("sec.tpr.min", p0(min(tprs)), src)
    put("sec.tpr.max", p0(max(tprs)), src)
    tprs_o = [s[f"{f}|orig"]["combined_TPR"]["rate_ci95"][0] for f in SETS]
    put("sec.tpr.orig.min", p0(min(tprs_o)), src)
    put("sec.tpr.orig.max", p0(max(tprs_o)), src)
    p2p_orig = [s[f"{f}|orig"]["p2p_TPR"]["rate_ci95"][0] for f in SETS]
    put("sec.p2p.orig.max", p1(max(p2p_orig)), src)


# ------------------------------------------------------------------------------- main
def main_tables(R):
    src = "results/results.json"
    for key, v in R["main"].items():
        m, c = key.split("|")
        if c not in CONDS:
            continue
        b = f"{MODELS[m]}.{CONDS[c]}"
        ci_pct(f"oabone.{b}.acc", v["oab1_acc"], src)
        put(f"oabone.n", v["oab1_n"], src)
        ci_pct(f"temas.{b}.all", v["temas_acc"], src)
        put("temas.n", v["temas_n"], src)
        if v.get("temas_grounding"):
            ci_num(f"temas.{b}.grounding", v["temas_grounding"], src)
    for key, v in R["tests"].items():
        task, m, c = key.split("|")
        t = "oabone" if task == "OAB-1" else "temas"
        b = f"{t}.{MODELS[m]}.{CONDS[c]}"
        put(f"{b}.mcn.b", v["b"], src)
        put(f"{b}.mcn.c", v["c"], src)
        put(f"{b}.mcn.p", pv(v["p"]), src)
        put(f"{b}.mcn.pholm", pv(v["p_holm"]), src)
    for key, v in R["temas_fields"].items():
        m, c = key.split("|")
        for f, short in (("competencia", "court"), ("polo_passivo", "defendant"), ("requisitos_cumpridos", "reqmet"),
                         ("requisito_ausente", "reqmissing")):
            ci_pct(f"temas.{MODELS[m]}.{CONDS[c]}.{short}", v[f], src, dec=0)
    for key, v in R["latency"].items():
        m, c = key.split("|")
        for task, x in zip(("oabone", "oabtwo", "temas"), v):
            put(f"lat.{task}.{MODELS[m]}.{CONDS[c]}", d1(x), src)
    # latency ratio JUDICATA / single-call baselines, per model and task
    for m in MODELS:
        ratios = []
        for i in range(3):
            j = R["latency"][f"{m}|judicata"][i]
            for c in ("raw", "vanilla_rag", "rag_toulmin", "rag_toulmin_jq"):
                ratios.append(j / R["latency"][f"{m}|{c}"][i])
        put(f"lat.ratio.{MODELS[m]}.min", f"{min(ratios):.0f}", "results/results.json (latency ratio)", "medido")
        put(f"lat.ratio.{MODELS[m]}.max", f"{max(ratios):.0f}", "results/results.json (latency ratio)", "medido")
        js = [R["latency"][f"{m}|judicata"][i] for i in range(3)]
        put(f"lat.judicata.{MODELS[m]}.min", f"{min(js):.0f}", src)
        put(f"lat.judicata.{MODELS[m]}.max", f"{max(js):.0f}", src)


def oab2(R):
    src = "results/results.json"
    o = R["oab2"]
    for key, v in o.items():
        if "|" not in key:
            continue
        m, c, j = key.split("|")
        jj = {"gemma3:27b": "gemma", "llama3.1:8b": "llama", "recall": "recall"}[j]
        ci_num(f"oabtwo.{MODELS[m]}.{CONDS[c]}.{jj}", v, src)
    put("oabtwo.rho", d2(o["judge_spearman"]), src)
    put("oabtwo.rhon", thousands(o["judge_n"]), src)


def oab2_volume():
    """Answer length, specific citations per answer and citation precision against the
    official guideline (share of the answer's specific citations that the guideline also
    cites; same matching as the recall, both directions)."""
    from app.reasoning.citations import extract_citations, specific_citations, _match
    items = {json.loads(l)["id"]: json.loads(l) for l in open(DATA / "oab2.jsonl", encoding="utf-8")}
    src = "results/oab2_*.jsonl + data/oab2.jsonl"
    by = defaultdict(lambda: defaultdict(list))
    for r in A.load_results("oab2"):
        if r["condition"] not in CONDS:
            continue
        g = [c.key for c in specific_citations(extract_citations(items[r["id"]]["guideline"]))]
        a = {c.key for c in specific_citations(extract_citations(r.get("answer") or ""))}
        b = by[(r["model"], r["condition"])]
        b["len"].append(len(r.get("answer") or ""))
        b["ncit"].append(len(a))
        b["undet"].append(sum(1 for k in a if ":?:" in k))
        if g:
            b["prec"].append(sum(1 for x in a if _match(x, set(g)) or any(_match(k, {x}) for k in g)) / len(a) if a else 0.0)
    for (m, c), b in by.items():
        k = f"oabtwo.{MODELS[m]}.{CONDS[c]}"
        put(f"{k}.len", thousands(round(sum(b["len"]) / len(b["len"]))), src)
        put(f"{k}.ncit", d1(sum(b["ncit"]) / len(b["ncit"])), src)
        put(f"{k}.undet", p0(sum(b["undet"]) / max(1, sum(b["ncit"]))), src)
        ci_num(f"{k}.prec", A.boot_mean(b["prec"]), src)
        put("oabtwo.recall.n", len(b["prec"]), src)
    for m in MODELS.values():
        for q in ("len", "ncit"):
            vals = [float(str(v).replace(",", "")) for kk, v, _, _ in ROWS
                    if kk.startswith(f"oabtwo.{m}.") and kk.endswith(f".{q}") and ".judicata." not in kk]
            put(f"oabtwo.{m}.base.{q}.min", (thousands(round(min(vals))) if q == "len" else d1(min(vals))), src)
            put(f"oabtwo.{m}.base.{q}.max", (thousands(round(max(vals))) if q == "len" else d1(max(vals))), src)


def temas_context():
    """Which sources reached the prompt in the Temas cases. The five context sources are
    the retrieved documents ordered by authority tier, then score (rule_matcher.py with
    source_hierarchy.rank_by_authority); vanilla RAG shows its five documents as retrieved.
    CNJ guide pages p4 and p7 are the only indexed texts that state the 210-minimum-wage
    threshold of Tema 1234; the indexed text of SV 60 does not state it."""
    from app.reasoning.source_hierarchy import TIERS
    src = "results/temas_*.jsonl + app/reasoning/source_hierarchy.py + dataset/precedents/health_corpus.json"
    corpus = json.load(open(Path(__file__).resolve().parent.parent / "dataset" / "precedents" / "health_corpus.json", encoding="utf-8"))
    corpus = corpus if isinstance(corpus, list) else next(v for v in corpus.values() if isinstance(v, list))
    thr = {x["number"] for x in corpus if x["id"].startswith("CNJ_") and "210" in json.dumps(x, ensure_ascii=False)}
    sv60 = next(x for x in corpus if x["id"] == "STF_SV_60")
    put("temas.sv60.states210", "yes" if "210" in json.dumps(sv60, ensure_ascii=False) else "no", src)
    put("temas.thresholdpages", len(thr), src)
    tot_ret = tot_prompt = n = 0
    for r_task in ("temas",):
        for (m, c), items in ML.by_cond(A.load_results(r_task)).items():
            if c == "raw":
                continue
            ret = prompt = sv = 0
            for r in items.values():
                docs = r["documents"]
                shown = docs[:5] if c in ("vanilla_rag", "judicata-no_hierarchy") else sorted(
                    docs, key=lambda d: (TIERS.get(d.get("kind"), (6,))[0], -(d.get("score") or 0)))[:5]
                ret += any(d.get("kind") == "ORIENTACAO_ADMIN" and d.get("article") in thr for d in docs)
                prompt += any(d.get("kind") == "ORIENTACAO_ADMIN" and d.get("article") in thr for d in shown)
                sv += any(d.get("kind") == "SUMULA_VINCULANTE" and str(d.get("article")) == "60" for d in shown)
            tot_ret += ret
            tot_prompt += prompt
            n += len(items)
            if c in CONDS:
                b = f"temas.{MODELS[m]}.{CONDS[c]}"
                put(f"{b}.thrret", ret, src)
                put(f"{b}.thrprompt", prompt, src)
                put(f"{b}.svsixtyprompt", sv, src)
    put("temas.thrprompt.total", tot_prompt, src)
    put("temas.retruns.total", thousands(n), src)
    gold = [json.loads(l) for l in open(DATA / "temas_cases.jsonl", encoding="utf-8")]
    fed = sum(1 for g in gold if "federal" in str(A.gold_norm(g["gold"]).get("competencia") or ""))
    put("temas.alwaysfederal.acc", p0(fed / len(gold)), "data/temas_cases.jsonl")


def oab2_tests():
    """Holm-adjusted Wilcoxon p-values vs JUDICATA, per model, for each judge and for recall."""
    items = {json.loads(l)["id"]: json.loads(l) for l in open(DATA / "oab2.jsonl", encoding="utf-8")}
    o2 = ML.by_cond(A.load_results("oab2"))
    sc = ML.oab2_scores()
    src = "results/oab2_*.jsonl (Wilcoxon, Holm)"
    out = {}
    for m in MODELS:
        for j, jj in (("gemma3:27b", "gemma"), ("llama3.1:8b", "llama")):
            b = sc.get((j, m, "judicata"), {})
            comps = [c for c in ML.COND_ORDER if c != "judicata" and (j, m, c) in sc]
            ps = []
            for c in comps:
                ids = [i for i in b if i in sc[(j, m, c)]]
                ps.append(A.wilcoxon([b[i] for i in ids], [sc[(j, m, c)][i] for i in ids]))
            for c, p in zip(comps, A.holm(ps)):
                put(f"oabtwo.{MODELS[m]}.{CONDS[c]}.{jj}.pholm", pv(p), src)
                out[f"{m}|{c}|{j}"] = p
        rb = {i: A.guideline_recall(r.get("answer") or "", items[i]["guideline"]) for i, r in o2[(m, "judicata")].items()}
        comps = [c for c in ML.COND_ORDER if c != "judicata" and (m, c) in o2]
        ps = []
        for c in comps:
            ro = {i: A.guideline_recall(r.get("answer") or "", items[i]["guideline"]) for i, r in o2[(m, c)].items()}
            ids = [i for i in rb if rb[i] is not None and ro.get(i) is not None]
            ps.append(A.wilcoxon([rb[i] for i in ids], [ro[i] for i in ids]))
            put("oabtwo.recall.nitems", len(ids), src)
        for c, p in zip(comps, A.holm(ps)):
            put(f"oabtwo.{MODELS[m]}.{CONDS[c]}.recall.pholm", pv(p), src)
            out[f"{m}|{c}|recall"] = p
    put("oabtwo.n", len(items), "data/oab2.jsonl")
    return out


# --------------------------------------------------------------------- OAB-1 extras
def oab1_extras():
    key = {json.loads(l)["id"]: json.loads(l)["answer"] for l in open(DATA / "oab1_sample.jsonl", encoding="utf-8")}
    parsed = A.load_parsed("oab1")
    rows = A.load_results("oab1")
    by = ML.by_cond(rows)
    src = "results/oab1_*.jsonl + *.parsed.jsonl"
    out = {}
    for (m, c), items in by.items():
        if c not in CONDS:
            continue
        b = f"oabone.{MODELS[m]}.{CONDS[c]}"
        ans = {}
        for i, r in items.items():
            k = (m, c, i)
            ans[i] = parsed[k] if k in parsed else (A.parse_mcq(A.text_of(r)) or A.parse_mcq(r.get("answer")))
        noans = sum(1 for a in ans.values() if not a)
        answered = [i for i, a in ans.items() if a]
        put(f"{b}.noanswer", noans, src)
        acc = A.wilson(sum(1 for i in answered if ans[i] == key[i]), len(answered))
        ci_pct(f"{b}.accanswered", acc, src, dec=0)
        g, nocite, revoked = A.grounding_stats(items.values())
        if c != "raw":
            ci_num(f"{b}.grounding", g, src)
        put(f"{b}.nocite", nocite, src)
        put(f"{b}.revoked", revoked, src)
        out[(m, c)] = noans
    sample = [json.loads(l) for l in open(DATA / "oab1_sample.jsonl", encoding="utf-8")]
    exams = sorted({r["exam_id"] for r in sample})
    put("oabone.exams", len(exams), "data/oab1_sample.jsonl")
    put("oabone.year.first", exams[0][:4], "data/oab1_sample.jsonl")
    put("oabone.year.last", exams[-1][:4], "data/oab1_sample.jsonl")
    put("oabone.withtype", sum(1 for r in sample if r.get("area")), "data/oab1_sample.jsonl")
    pool = [json.loads(l) for l in open(DATA / "oab2.jsonl", encoding="utf-8")]
    nonpiece = [r for r in pool if not r["is_piece"]]
    used = {r["id"] for r in A.load_results("oab2")}
    ed = sorted({r["category"].split("_")[0] for r in pool if r["id"] in used})
    put("oabtwo.pool", len(nonpiece), "data/oab2.jsonl")
    put("oabtwo.sample", len(used), "results/oab2_*.jsonl")
    put("oabtwo.exam.first", ed[0], "data/oab2.jsonl")
    put("oabtwo.exam.last", ed[-1], "data/oab2.jsonl")
    put("oabtwo.areas", len({r["category"].split("_", 1)[1] for r in pool if r["id"] in used}), "data/oab2.jsonl")
    return out


# ------------------------------------------------------------------------ Temas extras
def temas_extras():
    gold = {json.loads(l)["id"]: json.loads(l) for l in open(DATA / "temas_cases.jsonl", encoding="utf-8")}
    parsed = A.load_parsed("temas")
    rows = A.load_results("temas")
    src = "results/temas_*.jsonl + *.parsed.jsonl"
    put("temas.cases", len(gold), "data/temas_cases.jsonl")
    gstate = sum(1 for g in gold.values() if "estadual" in str(A.gold_norm(g["gold"]).get("competencia") or ""))
    put("temas.gold.state", gstate, "data/temas_cases.jsonl")
    gfed = sum(1 for g in gold.values() if "federal" in str(A.gold_norm(g["gold"]).get("competencia") or ""))
    put("temas.gold.federal", gfed, "data/temas_cases.jsonl")
    comp = Counter()
    for r in rows:
        k = (r["model"], r["condition"], r["id"])
        p = (parsed.get(k) if k in parsed else None) or A.parse_temas(r.get("answer") or "")
        comp[str(p.get("competencia"))] += 1
    put("temas.answers.total", thousands(len(rows)), src)
    per = defaultdict(Counter)
    for r in rows:
        k = (r["model"], r["condition"], r["id"])
        p = (parsed.get(k) if k in parsed else None) or A.parse_temas(r.get("answer") or "")
        cval = str(p.get("competencia") or "")
        cls = "federal" if "federal" in cval else ("state" if "estadual" in cval else "other")
        per[(r["model"], r["condition"])][cls] += 1
    for (m, c), cnt in per.items():
        if c in CONDS:
            for cls in ("federal", "state", "other"):
                put(f"temas.{MODELS[m]}.{CONDS[c]}.comp.{cls}", cnt[cls], src)
    put("temas.gold.other", len(gold) - gstate - gfed, "data/temas_cases.jsonl")
    put("temas.answers.state", sum(v for k, v in comp.items() if "estadual" in k), src)
    put("temas.answers.federal", thousands(sum(v for k, v in comp.items() if "federal" in k)), src)
    # retrieval of the binding súmulas (SV 60 / SV 61) per condition
    by = ML.by_cond(rows)
    for (m, c), items in by.items():
        if c not in CONDS or c == "raw":
            continue
        sv60 = sum(1 for r in items.values() if any(d.get("kind") == "SUMULA_VINCULANTE" and str(d.get("article")) == "60" for d in r["documents"]))
        sv61 = sum(1 for r in items.values() if any(d.get("kind") == "SUMULA_VINCULANTE" and str(d.get("article")) == "61" for d in r["documents"]))
        both = sum(1 for r in items.values() if {str(d.get("article")) for d in r["documents"] if d.get("kind") == "SUMULA_VINCULANTE"} >= {"60", "61"})
        b = f"temas.{MODELS[m]}.{CONDS[c]}"
        put(f"{b}.svsixty", sv60, src)
        put(f"{b}.svsixtyone", sv61, src)
        put(f"{b}.svboth", both, src)
        # cases in which the answer cites SV 60 or 61
        cites = sum(1 for r in items.values() if any(x.startswith("SV:6") for x in (r.get("citation_check") or {}).get("cited", [])))
        put(f"{b}.citessv", cites, src)
        unsup = sum(1 for r in items.values() if any(x.startswith("SV:6") for x in (r.get("citation_check") or {}).get("ungrounded", [])))
        put(f"{b}.svunsupported", unsup, src)
    # state-court cases answered with state court, by condition (all models)
    # ablation grounding and latency on Temas (Qwen)
    for c, short in list(ABL.items()) + [("judicata", "full")]:
        it = by.get(("qwen2.5:14b", c))
        if not it:
            continue
        g, _, _ = A.grounding_stats(it.values())
        ci_num(f"abl.temas.qwen.{short}.grounding", g, src)
        put(f"abl.temas.qwen.{short}.lat", d1(ML.median([r.get("latency_s") for r in it.values()])), src)
    # blocked by the output check
    for task in ("oab1", "oab2", "temas"):
        pass
    blocked_main = blocked_abl = 0
    for task in ("oab1", "oab2", "temas"):
        for r in A.load_results(task):
            if r.get("blocked_or_error"):
                if r["condition"] in ABL:
                    blocked_abl += 1
                else:
                    blocked_main += 1
    put("guard.blocked.main", blocked_main, "results/*.jsonl (blocked_or_error)")
    put("guard.blocked.abl", blocked_abl, "results/*.jsonl (blocked_or_error)")
    put("guard.blocked.total", blocked_main + blocked_abl, "results/*.jsonl (blocked_or_error)")


def ablation(R):
    src = "results/results.json"
    for key, v in R["ablation"].items():
        task, m, c = key.split("|")
        short = "full" if c == "judicata" else ABL[c]
        t = "oabone" if task == "oab1" else "temas"
        ci_pct(f"abl.{t}.{MODELS[m]}.{short}", v["acc"], src, dec=0)
        put(f"abl.{t}.{MODELS[m]}.{short}.n", v["n"], src)
        if v.get("p_holm") is not None:
            put(f"abl.{t}.{MODELS[m]}.{short}.pholm", pv(v["p_holm"]), src)
    lat = defaultdict(list)
    for r in A.load_results("oab1"):
        if r["model"] == "qwen2.5:14b" and (r["condition"] in ABL or r["condition"] == "judicata"):
            lat[r["condition"]].append(r.get("latency_s"))
    for c, xs in lat.items():
        put(f"abl.oabone.qwen.{'full' if c == 'judicata' else ABL[c]}.lat", d1(ML.median(xs)), "results/oab1_qwen.jsonl")


def qualifier(R):
    src = "results/results.json"
    tot = Counter()
    for key, v in R["qualifier"].items():
        task, m, q = key.split("|")
        t = "oabone" if task == "OAB-1" else "temas"
        q = q.lower()
        put(f"qual.{t}.{MODELS[m]}.{q}.n", v["n"], src)
        ci_pct(f"qual.{t}.{MODELS[m]}.{q}.acc", v["acc"], src, dec=0)
        tot[(t, q)] += v["n"]
        tot[(t, q, "k")] += round(v["n"] * v["acc"][0])
    for (t, *rest), n in list(tot.items()):
        if rest[-1] == "k":
            continue
        q = rest[0]
        put(f"qual.{t}.both.{q}.n", n, src)
        put(f"qual.{t}.both.{q}.correct", tot[(t, q, "k")], src)


def overlap():
    src = "results/*.jsonl (documents)"
    for task, t in (("oab1", "oabone"), ("oab2", "oabtwo"), ("temas", "temas")):
        by = defaultdict(dict)
        for r in A.load_results(task):
            by[(r["model"], r["condition"])][r["id"]] = {d["id"] for d in (r.get("documents") or [])}
        for m in MODELS:
            b = by.get((m, "judicata"))
            for c in ("vanilla_rag", "rag_toulmin", "rag_toulmin_jq"):
                d = by.get((m, c))
                if not (b and d):
                    continue
                ids = [i for i in d if i in b and (d[i] or b[i])]
                j = [len(d[i] & b[i]) / len(d[i] | b[i]) for i in ids]
                put(f"overlap.{t}.{MODELS[m]}.{CONDS[c]}", d2(sum(j) / len(j)), src)
                put(f"overlap.{t}.{MODELS[m]}.{CONDS[c]}.identical", sum(1 for x in j if x == 1.0), src)
                put(f"overlap.{t}.{MODELS[m]}.{CONDS[c]}.n", len(j), src)


def pii(R):
    p = R.get("pii") or {}
    src = "results/pii_audit.json"
    put("pii.queries", len(p.get("cases", [])), src)
    put("pii.prompts", p.get("total_llm_prompts"), src)
    put("pii.auditrows", p.get("audit_rows"), src)
    put("pii.leaks", p.get("total_pii_leaks_to_llm"), src)
    put("pii.leaks.audit", len(p.get("pii_in_audit_trail", [])), src)
    put("pii.leaks.output", sum(len(c.get("pii_in_output", [])) for c in p.get("cases", [])), src)


def counts():
    src = "results/*.jsonl"
    n = 0
    for task in ("oab1", "oab2", "temas"):
        n += len(A.load_results(task))
    put("runs.total", thousands(n), src)
    j = 0
    for p in RES.glob("oab2_*.judge-*.jsonl"):
        j += sum(1 for _ in open(p, encoding="utf-8"))
    put("runs.judgements", thousands(j), "results/oab2_*.judge-*.jsonl")


def ranges():
    """Smallest and largest value over the four baselines, for statements such as 'X against A to B'."""
    have = {k: v for k, v, s, lab in ROWS}
    pats = ["oabone.{m}.{c}.acc", "oabtwo.{m}.{c}.recall", "oabtwo.{m}.{c}.gemma", "oabtwo.{m}.{c}.llama",
            "temas.{m}.{c}.all", "oabone.{m}.{c}.grounding", "lat.oabone.{m}.{c}", "lat.oabtwo.{m}.{c}", "lat.temas.{m}.{c}",
            "oabone.{m}.{c}.mcn.pholm", "temas.{m}.{c}.mcn.pholm", "oabtwo.{m}.{c}.recall.pholm",
            "oabtwo.{m}.{c}.gemma.pholm", "oabtwo.{m}.{c}.llama.pholm"]
    for m in MODELS.values():
        for pat in pats:
            for group, conds in (("base", ["raw", "vanilla", "rtstmt", "rtjdocs"]), ("toulmin", ["rtstmt", "rtjdocs"]),
                                 ("simple", ["raw", "vanilla"])):
                vals = [have.get(pat.format(m=m, c=c)) for c in conds]
                vals = [x for x in vals if x not in (None, "n.a.")]
                if not vals:
                    continue
                num = lambda x: float(x.replace("<", "").replace(",", ""))  # noqa: E731
                key = pat.format(m=m, c=group)
                put(key + ".min", min(vals, key=num), "range over baselines of " + pat)
                put(key + ".max", max(vals, key=num), "range over baselines of " + pat)


def item_values():
    """Per-item values for each (model, condition): OAB-1 correct (0/1), OAB-2 guideline
    recall, precision and specific citations, Temas all fields correct (0/1).
    Returns {measure: {(model, condition): {item_id: value}}}; items without a
    guideline provision have no recall or precision."""
    from app.reasoning.citations import extract_citations, specific_citations, _match
    out = defaultdict(lambda: defaultdict(dict))
    key = {json.loads(l)["id"]: json.loads(l)["answer"] for l in open(DATA / "oab1_sample.jsonl", encoding="utf-8")}
    parsed = A.load_parsed("oab1")
    for r in A.load_results("oab1"):
        k = (r["model"], r["condition"], r["id"])
        a = parsed[k] if k in parsed else (A.parse_mcq(A.text_of(r)) or A.parse_mcq(r.get("answer")))
        out["oab1"][k[:2]][r["id"]] = 1.0 if a == key[r["id"]] else 0.0
    items = {json.loads(l)["id"]: json.loads(l) for l in open(DATA / "oab2.jsonl", encoding="utf-8")}
    for r in A.load_results("oab2"):
        g = [c.key for c in specific_citations(extract_citations(items[r["id"]]["guideline"]))]
        a = {c.key for c in specific_citations(extract_citations(r.get("answer") or ""))}
        k = (r["model"], r["condition"])
        out["ncit"][k][r["id"]] = float(len(a))
        if g:
            out["recall"][k][r["id"]] = A.guideline_recall(r.get("answer") or "", items[r["id"]]["guideline"])
            out["prec"][k][r["id"]] = (sum(1 for x in a if _match(x, set(g)) or any(_match(q, {x}) for q in g)) / len(a)) if a else 0.0
    gold = {json.loads(l)["id"]: json.loads(l) for l in open(DATA / "temas_cases.jsonl", encoding="utf-8")}
    tparsed = A.load_parsed("temas")
    for r in A.load_results("temas"):
        k = (r["model"], r["condition"], r["id"])
        p = (tparsed.get(k) if k in tparsed else None) or A.parse_temas(r.get("answer") or "")
        g = A.gold_norm(gold[r["id"]]["gold"])
        ok = all(p.get(f) == g[f] for f in ("competencia", "polo_passivo", "requisitos_cumpridos", "requisito_ausente")
                 if g.get(f) is not None)
        out["temas"][k[:2]][r["id"]] = 1.0 if ok else 0.0
    return out


def paired_boot(x, y, B=10000, seed=11):
    """Mean of the paired differences x - y over the shared items, with a percentile
    bootstrap 95% CI (resampling items)."""
    import numpy as np
    ids = sorted(set(x) & set(y))
    d = np.array([x[i] - y[i] for i in ids], dtype=float)
    rs = np.random.default_rng(seed)
    bs = d[rs.integers(0, len(d), size=(B, len(d)))].mean(axis=1)
    return float(d.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)), len(ids)


def paired_diffs():
    """JUDICATA minus each comparator, paired by item, for the four main measures.
    Percentage points for accuracies; proportion units for recall and precision."""
    V = item_values()
    src = "results/*.jsonl (paired bootstrap, 10,000 resamples)"
    for meas, short, scale in (("oab1", "oabone", 100), ("temas", "temas", 100), ("recall", "recall", 1), ("prec", "prec", 1)):
        for m in MODELS:
            for c in CONDS:
                if c == "judicata" or (m, c) not in V[meas]:
                    continue
                d, lo, hi, n = paired_boot(V[meas][(m, "judicata")], V[meas][(m, c)])
                fmt = (lambda z: f"{z * scale:.1f}") if scale == 100 else (lambda z: f"{z:.2f}")
                k = f"diff.{short}.{MODELS[m]}.{CONDS[c]}"
                put(k, fmt(d).replace("-", "$-$"), src)
                put(f"{k}.lo", fmt(lo).replace("-", "$-$"), src)
                put(f"{k}.hi", fmt(hi).replace("-", "$-$"), src)
                put(f"{k}.vals", f"{d * scale:.4f},{lo * scale:.4f},{hi * scale:.4f},{n}", src)


def temas_format():
    """Health cases: answers whose text states the COMPETENCIA line requested by the task (parsed
    by regex, no extraction call). The single-call Toulmin baselines received the task format and
    the six-component instruction in the same prompt, so they often followed only the second."""
    src = "results/temas_*.jsonl (regex parse)"
    n = defaultdict(int)
    for r in A.load_results("temas"):
        if r["condition"] in CONDS and A.parse_temas(r.get("answer") or "").get("competencia") is not None:
            n[(r["model"], r["condition"])] += 1
    vals = []
    for m in MODELS:
        for c in ("rag_toulmin", "rag_toulmin_jq"):
            put(f"temas.{MODELS[m]}.{CONDS[c]}.fmt", n[(m, c)], src)
            vals.append(n[(m, c)])
    put("temas.fmt.min", min(vals), src)
    put("temas.fmt.max", max(vals), src)


def collect():
    """Compute every number; return {key: (value, source, label)}."""
    ROWS.clear()
    R = json.load(open(RES / "results.json", encoding="utf-8"))
    corpus()
    security(R)
    main_tables(R)
    oab2(R)
    oab2_tests()
    oab2_volume()
    temas_context()
    oab1_extras()
    temas_extras()
    ablation(R)
    qualifier(R)
    overlap()
    pii(R)
    counts()
    ranges()
    temas_format()
    paired_diffs()
    seen = {}
    for k, v, s, lab in ROWS:
        if k in seen and seen[k] != v:
            raise SystemExit(f"inconsistent value for {k}: {seen[k]} vs {v}")
        seen[k] = v
    uniq = {}
    for k, v, s, lab in ROWS:
        uniq.setdefault(k, (v, s, lab))
    return uniq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    uniq = collect()
    tex =["% generated by evaluation/make_numbers.py; do not edit",
           r"\providecommand{\judnum}[2]{\expandafter\def\csname num@#1\endcsname{#2}}"]
    for k, (v, s, lab) in sorted(uniq.items()):
        val = v.replace("%", r"\%").replace("<", r"\ensuremath{<}")
        tex.append(rf"\judnum{{{k}}}{{{val}}}")
    (out / "numeros.tex").write_text("\n".join(tex) + "\n", encoding="utf-8", newline="\n")
    with open(out / "numeros.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["macro", "valor", "fonte", "rotulo"])
        for k, (v, s, lab) in sorted(uniq.items()):
            w.writerow([k, v, s, lab])
    print(f"{len(uniq)} numbers written to {out}")


if __name__ == "__main__":
    main()
