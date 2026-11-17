#!/usr/bin/env python3
"""
Evaluation runner (PLOS ONE revision). Resumable: results are appended to a
JSONL file and items already present are skipped.

Conditions (same model, same decoding, same task text and answer format):
  raw          LLM only.
  vanilla_rag  dense retrieval (BERTimbau/Qdrant, top-5) + one generation call.
  rag_toulmin  the SAME documents JUDICATA retrieves (HyPA-RAG, same context
               selection) + one call explicitly instructed to produce Claim, Data,
               Warrant, Backing, Qualifier and Rebuttal. This is the "fair
               baseline" requested by Reviewer 2: it isolates what the
               multi-step pipeline adds over a single instruction.
  judicata     full pipeline (orchestrator.analyze).
  judicata-<ablation>  full pipeline with one component switched off:
               no_lsim, no_scot, no_kg, fixed_weights, no_hierarchy,
               no_backing_verification.

Usage:
  python evaluation/run_eval.py --task oab1 --model qwen2.5:14b \
      --conditions raw,vanilla_rag,rag_toulmin,judicata --out evaluation/results/oab1_qwen.jsonl
"""
import argparse
import asyncio
import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.llm import generate  # noqa: E402
from app.reasoning import source_hierarchy as sh  # noqa: E402
from app.reasoning.citations import verify_citations  # noqa: E402
from app.reasoning.rule_matcher import select_context, format_sources  # noqa: E402

DATA = Path(__file__).parent / "data"

SYSTEM = ("Você é um assistente de pesquisa jurídica em Direito Brasileiro. "
          "Responda em português, com fundamentação e citação dos dispositivos legais e precedentes aplicáveis.")

TOULMIN_INSTR = ("\n\nEstruture a resposta nos seis componentes do modelo de Toulmin, com estes rótulos:\n"
                 "CLAIM: (conclusão)\nDATA: (fatos relevantes)\nWARRANT: (garantia que liga os fatos à conclusão)\n"
                 "BACKING: (dispositivos legais e precedentes que sustentam a garantia, citados exatamente como nas fontes)\n"
                 "QUALIFIER: (CERTO, PROVAVEL, POSSIVEL ou INCERTO)\nREBUTTAL: (condições em que a conclusão não se aplicaria)\n"
                 "Use somente as fontes fornecidas.")

ABLATIONS = {
    "no_lsim": {"lsim_enabled": False},
    "no_scot": {"scot_enabled": False},
    "no_kg": {"kg_enabled": False},
    "fixed_weights": {"adaptive_weights_enabled": False},
    "no_hierarchy": {"source_hierarchy_enabled": False},
    "no_backing_verification": {"backing_verification_enabled": False},
}
DEFAULT_FLAGS = {k: getattr(settings, k) for v in ABLATIONS.values() for k in v}


# ----------------------------------------------------------------------------- tasks
def load_task(task):
    rows = [json.loads(l) for l in open(DATA / f"{dict(oab1='oab1_sample', oab2='oab2', temas='temas_cases')[task]}.jsonl",
                                         encoding="utf-8")]
    items = []
    for r in rows:
        if task == "oab1":
            alts = "\n".join(f"({k}) {v}" for k, v in r["choices"].items())
            text = (f"{r['question']}\n\n{alts}\n\nIndique a alternativa correta e fundamente. "
                    f"Termine com uma linha no formato: RESPOSTA: <letra>")
            items.append({"id": r["id"], "text": text, "retrieval_query": r["question"] + " " + alts})
        elif task == "oab2":
            text = f"{r['statement']}\n\nQuestão: {r['question']}\n\nResponda de forma fundamentada, indicando os dispositivos legais aplicáveis."
            items.append({"id": r["id"], "text": text, "retrieval_query": r["statement"][:1500] + " " + r["question"]})
        else:
            items.append({"id": r["id"], "text": r["query"], "retrieval_query": r["query"].split("\n\nAo final")[0]})
    return items


# ------------------------------------------------------------------------- conditions
_rag_ready = False


async def _hypa():
    global _rag_ready
    from app.retrieval.hypa_rag import hypa_rag
    if not _rag_ready:
        await hypa_rag.initialize()
        _rag_ready = True
    return hypa_rag


async def run_raw(item):
    out = await generate(f"{SYSTEM}\n\n{item['text']}")
    return {"answer": out, "documents": []}


async def run_vanilla(item):
    rag = await _hypa()
    docs = await rag._dense_search(item["retrieval_query"], 5, "eval")
    ctx = "\n\n".join(f"Fonte {i+1}: {d.content[:settings.rule_matcher_doc_chars]}" for i, d in enumerate(docs))
    out = await generate(f"{SYSTEM}\n\nFontes:\n{ctx}\n\n{item['text']}")
    return {"answer": out, "documents": docs}


async def run_rag_toulmin(item):
    rag = await _hypa()
    docs, _ = await rag.retrieve(item["retrieval_query"], "eval")
    ctx = select_context(docs)
    out = await generate(f"{SYSTEM}\n\nFontes:\n{format_sources(ctx)}\n\n{item['text']}{TOULMIN_INSTR}")
    return {"answer": out, "documents": docs}


async def run_judicata(item):
    from app.agents.orchestrator import orchestrator
    from app.retrieval.hypa_rag import hypa_rag
    await _hypa()
    # The orchestrator retrieves with the full task text; capture its documents for metrics.
    captured = {}
    orig = hypa_rag.retrieve

    async def spy(q, trace_id="unknown"):
        docs, cx = await orig(q, trace_id)
        captured["docs"] = docs
        return docs, cx
    hypa_rag.retrieve = spy
    try:
        res = await orchestrator.analyze(item["text"], anonymize=True, enable_scot=settings.scot_enabled)
    finally:
        hypa_rag.retrieve = orig
    if "error" in res:
        return {"answer": "", "documents": captured.get("docs", []), "blocked_or_error": res}
    answer = "\n".join(f"{k.upper()}: {res.get(k) or ''}" for k in ("claim", "data", "warrant", "backing", "rebuttal", "qualifier"))
    return {"answer": answer, "documents": captured.get("docs", []), "toulmin": res}


RUNNERS = {"raw": run_raw, "vanilla_rag": run_vanilla, "rag_toulmin": run_rag_toulmin, "judicata": run_judicata}


def set_flags(condition):
    for k, v in DEFAULT_FLAGS.items():
        setattr(settings, k, v)
    if condition.startswith("judicata-"):
        for k, v in ABLATIONS[condition.split("-", 1)[1]].items():
            setattr(settings, k, v)


def doc_summary(d):
    md = d.metadata or {}
    return {"id": d.id, "kind": sh.source_kind(d), "law": md.get("law_name") or md.get("court"),
            "article": md.get("article") or md.get("number"), "score": round(float(d.score or 0), 5)}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=["oab1", "oab2", "temas"])
    ap.add_argument("--model", required=True)
    ap.add_argument("--conditions", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sample", type=int, default=0, help="deterministic random subset (seed 13)")
    ap.add_argument("--no-pieces", action="store_true", help="OAB-2: questions only, exclude full pleadings")
    a = ap.parse_args()

    settings.ollama_model = a.model
    settings.ollama_temperature = 0.0
    items = load_task(a.task)
    if a.no_pieces:
        items = [i for i in items if "peca_profissional" not in i["id"]]
    if a.sample and a.sample < len(items):
        import random
        keep = set(i["id"] for i in random.Random(13).sample(items, a.sample))
        items = [i for i in items if i["id"] in keep]
    if a.limit:
        items = items[: a.limit]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        for l in open(out, encoding="utf-8"):
            r = json.loads(l)
            done.add((r["condition"], r["id"]))

    conditions = a.conditions.split(",")
    for cond in conditions:
        set_flags(cond)
        runner = RUNNERS["judicata" if cond.startswith("judicata") else cond]
        for n, item in enumerate(items):
            if (cond, item["id"]) in done:
                continue
            t0 = time.time()
            rec = {"task": a.task, "model": a.model, "condition": cond, "id": item["id"]}
            try:
                r = await runner(item)
                rec["answer"] = r["answer"]
                rec["latency_s"] = round(time.time() - t0, 2)
                rec["documents"] = [doc_summary(d) for d in r["documents"]]
                rec["citation_check"] = verify_citations(r["answer"], r["documents"], sh.revoked_laws()).to_dict()
                if "toulmin" in r:
                    t = r["toulmin"]
                    rec["toulmin"] = {k: (str(t.get(k)).replace("Qualifier.", "") if k == "qualifier" else t.get(k)) for k in ("claim", "data", "warrant", "backing", "rebuttal", "qualifier",
                                                           "qualifier_basis", "citation_check", "binding_sources",
                                                           "safety_validated", "safety_warnings", "query_complexity")}
                if "blocked_or_error" in r:
                    rec["blocked_or_error"] = r["blocked_or_error"]
            except Exception as e:
                rec["exception"] = f"{type(e).__name__}: {e}"
                rec["traceback"] = traceback.format_exc()[-2000:]
                rec["latency_s"] = round(time.time() - t0, 2)
            with open(out, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            print(f"[{a.task}|{a.model}|{cond}] {n+1}/{len(items)} {item['id']} {rec.get('latency_s')}s", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
