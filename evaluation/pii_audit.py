#!/usr/bin/env python3
"""
E5 - Personal-data leakage audit.

Runs queries containing synthetic personal data (names, CPF, e-mail, phone,
CNJ case number) through the full pipeline while intercepting EVERY prompt sent
to the LLM, and then scans (i) all intercepted prompts and (ii) the SQLite audit
trail for the raw identifiers. Expected result: zero occurrences.

All identifiers below are synthetic (CPFs/case numbers generated to be
format-valid but not assigned to real people).
"""
import asyncio
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core import llm as llm_mod  # noqa: E402
from app.core.config import settings  # noqa: E402

CASES = [
    {"q": "Joaquim Pereira da Silva, CPF 123.456.789-09, residente em Belém, teve o medicamento negado pelo SUS. "
          "Qual a competência para a ação?", "pii": ["Joaquim Pereira da Silva", "123.456.789-09"]},
    {"q": "A cliente Mariana Souza Lima (mariana.lima@example.com, telefone (91) 98888-7777) foi cobrada indevidamente. "
          "Quais direitos ela tem pelo CDC?", "pii": ["Mariana Souza Lima", "mariana.lima@example.com", "98888-7777"]},
    {"q": "No processo 0801234-56.2025.8.14.0301, Roberto Alves Nogueira pede indenização por dano moral. "
          "Quais os requisitos da responsabilidade civil?", "pii": ["Roberto Alves Nogueira", "0801234-56.2025.8.14.0301"]},
    {"q": "Fernanda Costa Ribeiro, CPF 987.654.321-00, servidora pública, quer saber o prazo da licença-maternidade.",
     "pii": ["Fernanda Costa Ribeiro", "987.654.321-00"]},
    {"q": "Lucas Martins de Oliveira foi demitido sem justa causa após 3 anos. Quais verbas rescisórias são devidas?",
     "pii": ["Lucas Martins de Oliveira"]},
]


async def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:14b"
    settings.ollama_model = model
    settings.audit_checkpoint_path = "evaluation/results/pii_audit.sqlite"
    Path(settings.audit_checkpoint_path).unlink(missing_ok=True)

    prompts = []
    orig = llm_mod.generate
    orig_get = llm_mod.get_llm

    class Spy:
        def __init__(self, inner):
            self.inner = inner

        async def ainvoke(self, p, *a, **k):
            prompts.append(str(p))
            return await self.inner.ainvoke(p, *a, **k)

    async def spy_generate(prompt, *a, **k):
        prompts.append(prompt)
        return await orig(prompt, *a, **k)

    llm_mod.generate = spy_generate
    llm_mod.get_llm = lambda *a, **k: Spy(orig_get(*a, **k))
    # modules imported `generate`/`get_llm` by name: patch their references too
    import app.reasoning.rule_matcher as rm, app.reasoning.toulmin as tm, app.reasoning.lsim_engine as le, \
        app.reasoning.fact_extractor as fe
    for m in (rm, tm, le):
        m.generate = spy_generate
    for m in (le, fe):
        m.get_llm = llm_mod.get_llm

    from app.agents.orchestrator import JudicialOrchestrator
    orch = JudicialOrchestrator()
    report = []
    for c in CASES:
        n_before = len(prompts)
        res = await orch.analyze(c["q"], anonymize=True)
        sent = "\n".join(prompts[n_before:])
        leaks = [p for p in c["pii"] if p.lower() in sent.lower()]
        out_leaks = [p for p in c["pii"] if p.lower() in json.dumps(res, ensure_ascii=False).lower()]
        report.append({"query": c["q"][:60], "llm_calls": len(prompts) - n_before,
                       "pii_in_llm_prompts": leaks, "pii_in_output": out_leaks})
    db = sqlite3.connect(settings.audit_checkpoint_path)
    dump = "\n".join(r[0] for r in db.execute("SELECT state_json FROM audit"))
    audit_leaks = sorted({p for c in CASES for p in c["pii"] if p.lower() in dump.lower()})
    summary = {"model": model, "cases": report, "audit_rows": db.execute("SELECT count(*) FROM audit").fetchone()[0],
               "pii_in_audit_trail": audit_leaks,
               "total_llm_prompts": len(prompts),
               "total_pii_leaks_to_llm": sum(len(r["pii_in_llm_prompts"]) for r in report)}
    Path("evaluation/results").mkdir(parents=True, exist_ok=True)
    json.dump(summary, open("evaluation/results/pii_audit.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
