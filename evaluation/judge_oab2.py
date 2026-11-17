#!/usr/bin/env python3
"""
E3 - Grade OAB 2nd-phase answers against the OFFICIAL FGV grading guideline
(maritaca-ai/oab-bench), with an LLM judge from a different model family than
the systems under test, following the oab-bench protocol (score in [0, max]).

Two independent judges can be run; agreement is reported (ICC / Spearman).
Deterministic companion metric: recall of the legal provisions cited in the
official guideline (computed in analyze.py, no LLM involved).

Usage: python evaluation/judge_oab2.py --results evaluation/results/oab2_qwen.jsonl --judge gemma3:27b
"""
import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.config import settings  # noqa: E402
from app.core.llm import generate  # noqa: E402

DATA = Path(__file__).parent / "data"

PROMPT = """Você é examinador da segunda fase do Exame da OAB (FGV). Corrija a resposta do candidato
usando EXCLUSIVAMENTE o padrão de resposta (espelho) oficial abaixo. Atribua pontos apenas aos itens
do espelho efetivamente atendidos pela resposta, com a fundamentação exigida. A simples menção ao
dispositivo legal, sem a resposta correta, não pontua.

ENUNCIADO:
{statement}

QUESTÃO:
{question}

PADRÃO DE RESPOSTA OFICIAL (pontuação máxima: {maxp}):
{guideline}

RESPOSTA DO CANDIDATO:
{answer}

Responda apenas com uma linha no formato: NOTA: <número entre 0 e {maxp}>"""


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--judge", required=True)
    a = ap.parse_args()
    settings.ollama_model, settings.ollama_temperature = a.judge, 0.0
    items = {json.loads(l)["id"]: json.loads(l) for l in open(DATA / "oab2.jsonl", encoding="utf-8")}
    res = Path(a.results)
    out = res.with_name(res.stem + f".judge-{a.judge.replace(':', '_')}.jsonl")
    done = {(json.loads(l)["condition"], json.loads(l)["id"]) for l in open(out, encoding="utf-8")} if out.exists() else set()
    for l in open(res, encoding="utf-8"):
        r = json.loads(l)
        if (r["condition"], r["id"]) in done:
            continue
        it = items[r["id"]]
        maxp = it["max_points"] or 1.0
        answer = (r.get("answer") or "").strip()
        if not answer:
            score, raw = 0.0, "EMPTY"
        else:
            raw = await generate(PROMPT.format(statement=it["statement"][:6000], question=it["question"],
                                               guideline=it["guideline"][:6000], answer=answer[:8000], maxp=maxp),
                                 num_predict=64)
            m = re.search(r"NOTA:\s*([0-9]+(?:[.,][0-9]+)?)", raw)
            score = min(float(m.group(1).replace(",", ".")), maxp) if m else None
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps({"condition": r["condition"], "model": r["model"], "id": r["id"], "judge": a.judge,
                                "score": score, "max_points": maxp, "raw": raw[:200]}, ensure_ascii=False) + "\n")
        print(r["condition"], r["id"], score, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
