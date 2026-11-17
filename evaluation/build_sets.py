#!/usr/bin/env python3
"""
Build the external evaluation sets (PLOS ONE revision).

All sets were downloaded and built AFTER the system was frozen (git tag
v2.0-frozen); none of their items was used to write or tune any rule.

Outputs (evaluation/data/):
  security_external.jsonl  attacks and benign prompts from public datasets
  benign_legal.jsonl       real Brazilian legal questions (OAB exams), used to
                           measure false positives of the defence layers
  oab1_sample.jsonl        stratified sample of OAB 1st-phase MCQs (official key)
  oab2.jsonl               OAB 2nd-phase discursive questions + official guidelines
  temas_cases.jsonl        synthetic health-litigation cases (gold by construction)

Usage: python evaluation/build_sets.py [--oab1-n 200] [--seed 13]
"""
import argparse
import ast
import json
import random
import re
from collections import defaultdict
from pathlib import Path

from datasets import load_dataset

OUT = Path(__file__).parent / "data"


def write(name, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / name, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{name}: {len(rows)}")


def security_sets():
    rows = []
    ds = load_dataset("deepset/prompt-injections")
    for split in ("train", "test"):
        for i, r in enumerate(ds[split]):
            rows.append({"id": f"deepset_{split}_{i}", "source": "deepset/prompt-injections",
                         "text": r["text"], "attack": int(r["label"]) == 1, "lang": "orig"})
    ds = load_dataset("Lakera/gandalf_ignore_instructions")
    for split in ds:
        for i, r in enumerate(ds[split]):
            rows.append({"id": f"lakera_{split}_{i}", "source": "Lakera/gandalf_ignore_instructions",
                         "text": r["text"], "attack": True, "lang": "orig"})
    ds = load_dataset("jackhhao/jailbreak-classification")
    for split in ds:
        for i, r in enumerate(ds[split]):
            rows.append({"id": f"jackhhao_{split}_{i}", "source": "jackhhao/jailbreak-classification",
                         "text": r["prompt"], "attack": r["type"] == "jailbreak", "lang": "orig"})
    write("security_external.jsonl", rows)


def oab_sets(n1, seed):
    rnd = random.Random(seed)
    ds = load_dataset("eduagarcia/oab_exams")["train"]
    benign, pool = [], defaultdict(list)
    for r in ds:
        if r["nullified"]:
            continue
        choices = r["choices"]
        labels, texts = choices["label"], choices["text"]
        q = r["question"].strip()
        benign.append({"id": f"oab1_{r['id']}", "source": "eduagarcia/oab_exams", "text": q, "attack": False})
        if int(r["exam_year"]) >= 2016:
            pool[r["question_type"] or "NA"].append({
                "id": r["id"], "exam_id": r["exam_id"], "area": r["question_type"],
                "question": q, "choices": dict(zip(labels, texts)), "answer": r["answerKey"]})
    write("benign_legal.jsonl", benign)

    # stratified sample by area (proportional, at least 1 per area)
    total = sum(len(v) for v in pool.values())
    sample = []
    for area, items in sorted(pool.items()):
        k = max(1, round(n1 * len(items) / total))
        sample += rnd.sample(items, min(k, len(items)))
    rnd.shuffle(sample)
    write("oab1_sample.jsonl", sample[:n1])

    qs = load_dataset("maritaca-ai/oab-bench", "questions")["train"]
    gl = {r["question_id"]: r for r in load_dataset("maritaca-ai/oab-bench", "guidelines")["train"]}
    rows = []
    for q in qs:
        g = gl.get(q["question_id"])
        if not g:
            continue
        turns = q["turns"] if isinstance(q["turns"], list) else ast.literal_eval(q["turns"])
        gturns = g["choices"][0]["turns"]
        values = q["values"] if isinstance(q["values"], list) else ast.literal_eval(q["values"])
        for k, t in enumerate(turns):
            rows.append({
                "id": f"{q['question_id']}_t{k}", "question_id": q["question_id"], "category": q["category"],
                "is_piece": "peca_profissional" in q["question_id"],
                "statement": q["statement"], "question": t, "guideline": gturns[k] if k < len(gturns) else "",
                "max_points": values[k] if k < len(values) else None,
            })
    write("oab2.jsonl", rows)


# ---------------------------------------------------------------------------
# Synthetic cases for STF Temas 6 / 1234 (gold derived by construction from the
# CNJ "Guia Rápido de Judicialização em Saúde: Medicamentos no SUS", 2025)
# ---------------------------------------------------------------------------
REQS = [
    ("negativa", "Houve pedido administrativo prévio, negado por decisão motivada da Secretaria de Saúde.",
     "Não houve pedido administrativo prévio do medicamento à rede pública."),
    ("conitec", "A CONITEC nunca recebeu pedido de incorporação do medicamento, embora ele esteja registrado há mais de cinco anos.",
     "A CONITEC analisou o medicamento há um ano e, em decisão regularmente fundamentada, recomendou a não incorporação; não há indicação de ilegalidade nessa decisão."),
    ("substituto", "O laudo descreve que todos os medicamentos padronizados no SUS para a doença foram utilizados, com posologia e tempo de uso, sem resposta.",
     "Existe medicamento padronizado no SUS para a mesma indicação, que o autor nunca utilizou."),
    ("evidencia", "Há ensaios clínicos randomizados e meta-análise demonstrando eficácia e segurança do fármaco para a doença.",
     "A eficácia do fármaco para a doença é sustentada apenas por relatos de caso, sem ensaios clínicos randomizados."),
    ("laudo", "Há laudo médico fundamentado e circunstanciado sobre a imprescindibilidade do tratamento.",
     "A única prova médica é uma receita simples, sem fundamentação sobre a imprescindibilidade."),
    ("hipossuficiencia", "O autor comprovou renda familiar de dois salários mínimos e despesas que o impedem de custear o tratamento.",
     "O autor declarou renda mensal de cinquenta salários mínimos e patrimônio elevado."),
]
COST = [(5, "Justiça Estadual", "Estado"), (40, "Justiça Estadual", "Estado"), (300, "Justiça Federal", "União")]
NAMES = ["Ana", "Bruno", "Carla", "Diego", "Elisa", "Fábio"]
FORMAT = ("\n\nAo final, responda exatamente nas quatro linhas abaixo:\n"
          "COMPETENCIA: <Justiça Federal | Justiça Estadual | critérios do Tema 1234 não se aplicam>\n"
          "POLO_PASSIVO: <União | Estado | Município>\n"
          "REQUISITOS_CUMPRIDOS: <sim | não>\n"
          "REQUISITO_AUSENTE: <negativa | conitec | substituto | evidencia | laudo | hipossuficiencia | registro | nenhum>")


def _narrative(name, drug_state, cost_sm, filed, req_flags):
    lines = [f"{name}, portador(a) de doença crônica grave, pretende ajuizar ação para obter o medicamento X."]
    lines.append(drug_state)
    lines.append(f"O custo anual do tratamento, calculado pelo PMVG da CMED, equivale a {cost_sm} salários mínimos.")
    lines.append(f"A ação será ajuizada em {filed}.")
    for (_, ok, bad), flag in zip(REQS, req_flags):
        lines.append(ok if flag else bad)
    return " ".join(lines) + (
        "\nAnalise a competência, o polo passivo e o preenchimento dos requisitos para a concessão judicial, "
        "à luz dos Temas 6 e 1234 do STF e das Súmulas Vinculantes 60 e 61.")


def temas_cases(seed):
    rnd = random.Random(seed)
    rows, k = [], 0
    registered = "O medicamento X possui registro na ANVISA, mas não está incorporado às listas do SUS (RENAME, RESME ou REMUME) nem a PCDT."
    for cost_sm, court, defendant in COST:
        for missing in [None] + list(range(len(REQS))):
            for rep in range(2):
                flags = [i != missing for i in range(len(REQS))]
                name = NAMES[(k + rep) % len(NAMES)]
                rows.append({
                    "id": f"tema_{k:03d}", "query": _narrative(name, registered, cost_sm, "março de 2026", flags) + FORMAT,
                    "gold": {"competencia": court, "polo_passivo": defendant,
                             "requisitos_cumpridos": "sim" if missing is None else "não",
                             "requisito_ausente": "nenhum" if missing is None else REQS[missing][0]},
                    "factors": {"cost_sm": cost_sm, "missing": None if missing is None else REQS[missing][0],
                                "filed": "after_modulation", "registered": True}})
                k += 1
    # Modulation: actions filed before 19/09/2024 keep previous competence rules
    for cost_sm, _, _ in COST:
        flags = [True] * len(REQS)
        rows.append({
            "id": f"tema_{k:03d}", "query": _narrative(NAMES[k % 6], registered, cost_sm, "maio de 2024 (ação já em curso)", flags) + FORMAT,
            "gold": {"competencia": "critérios do Tema 1234 não se aplicam", "polo_passivo": None,
                     "requisitos_cumpridos": "sim", "requisito_ausente": "nenhum"},
            "factors": {"cost_sm": cost_sm, "missing": None, "filed": "before_modulation", "registered": True}})
        k += 1
    # Not registered at ANVISA (Tema 500): Federal court, Union; concession barred as a rule
    not_reg = "O medicamento X não possui registro na ANVISA e não há pedido de registro no Brasil."
    for cost_sm, _, _ in COST:
        for rep in range(2):
            rows.append({
                "id": f"tema_{k:03d}", "query": _narrative(NAMES[(k + rep) % 6], not_reg, cost_sm, "março de 2026", [True] * 6) + FORMAT,
                "gold": {"competencia": "Justiça Federal", "polo_passivo": "União",
                         "requisitos_cumpridos": "não", "requisito_ausente": "registro"},
                "factors": {"cost_sm": cost_sm, "missing": "registro", "filed": "after_modulation", "registered": False}})
            k += 1
    rnd.shuffle(rows)
    write("temas_cases.jsonl", rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--oab1-n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=13)
    a = ap.parse_args()
    security_sets()
    oab_sets(a.oab1_n, a.seed)
    temas_cases(a.seed)
