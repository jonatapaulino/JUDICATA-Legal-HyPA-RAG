#!/usr/bin/env python3
"""
Uniform answer extraction (applied identically to every condition).

Free-text answers rarely follow a rigid output format, and the JUDICATA
pipeline returns Toulmin components rather than a letter or a label. To score
all conditions in the same way, a separate extraction call (fixed model,
temperature 0) reads each final answer and returns only the decision it
expresses, without solving the task itself. Regex parsing is tried first; the
extractor is used only when it fails. Both the source of each parsed value
("regex" | "extractor") and the raw extractor output are stored.

Usage: python evaluation/extract_answers.py --results evaluation/results/oab1_qwen.jsonl --task oab1
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.config import settings  # noqa: E402
from app.core.llm import generate  # noqa: E402
from evaluation.analyze import parse_mcq, parse_temas  # noqa: E402

P_OAB1 = ("Abaixo está a resposta de um sistema a uma questão de múltipla escolha. Não resolva a questão. "
          "Diga apenas qual alternativa (A, B, C ou D) a RESPOSTA escolheu como correta. Se ela não escolher "
          "nenhuma, responda NENHUMA.\n\nRESPOSTA:\n{a}\n\nResponda só com: ESCOLHA: <A|B|C|D|NENHUMA>")
P_TEMAS = ("Abaixo está a resposta de um sistema sobre um caso de fornecimento de medicamento. Não analise o caso. "
           "Extraia apenas o que a RESPOSTA afirma, nas quatro linhas abaixo (use 'indefinido' se ela não afirmar):\n"
           "COMPETENCIA: <Justiça Federal | Justiça Estadual | critérios do Tema 1234 não se aplicam | indefinido>\n"
           "POLO_PASSIVO: <União | Estado | Município | indefinido>\n"
           "REQUISITOS_CUMPRIDOS: <sim | não | indefinido>\n"
           "REQUISITO_AUSENTE: <negativa | conitec | substituto | evidencia | laudo | hipossuficiencia | registro | nenhum | indefinido>\n"
           "(negativa = pedido administrativo prévio negado; conitec = mora ou ilegalidade da CONITEC; "
           "substituto = inexistência de substituto no SUS; evidencia = evidência científica de alto nível; "
           "laudo = laudo médico fundamentado; hipossuficiencia = incapacidade financeira; registro = registro na ANVISA)\n\n"
           "RESPOSTA:\n{a}")


def full_text(r):
    t = r.get("toulmin")
    if t:
        parts = [f"{k.upper()}: {t.get(k) or ''}" for k in ("claim", "data", "warrant", "backing", "rebuttal", "qualifier")]
        return "\n".join(parts)
    return r.get("answer") or ""


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--task", required=True, choices=["oab1", "temas"])
    ap.add_argument("--model", default="qwen2.5:14b")
    a = ap.parse_args()
    settings.ollama_model, settings.ollama_temperature = a.model, 0.0
    src = Path(a.results)
    out = src.with_name(src.stem + ".parsed.jsonl")
    done = {(json.loads(l)["condition"], json.loads(l)["id"], json.loads(l)["model"]) for l in open(out, encoding="utf-8")} \
        if out.exists() else set()
    for l in open(src, encoding="utf-8"):
        r = json.loads(l)
        key = (r["condition"], r["id"], r["model"])
        if key in done:
            continue
        text = full_text(r)
        rec = {"condition": r["condition"], "id": r["id"], "model": r["model"], "extractor": a.model}
        if not text.strip():
            rec.update(parsed=None, how="empty")
        elif a.task == "oab1":
            p = parse_mcq(text)
            if p:
                rec.update(parsed=p, how="regex")
            else:
                raw = await generate(P_OAB1.format(a=text[:6000]), num_predict=16)
                p = parse_mcq(raw.replace("ESCOLHA", "RESPOSTA"))
                rec.update(parsed=p, how="extractor", raw=raw[:100])
        else:
            p = parse_temas(text)
            if len(p) == 4 and "indefinido" not in json.dumps(p):
                rec.update(parsed=p, how="regex")
            else:
                raw = await generate(P_TEMAS.format(a=text[:6000]), num_predict=96)
                rec.update(parsed=parse_temas(raw), how="extractor", raw=raw[:300])
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(key, rec.get("parsed"), rec["how"], flush=True)


if __name__ == "__main__":
    asyncio.run(main())
