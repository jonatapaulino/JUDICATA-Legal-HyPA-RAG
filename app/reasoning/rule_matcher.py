"""
Rule matching from retrieved documents.
Identifies applicable legal rules given a set of facts.

Revision notes (PLOS ONE review):
- Sources are ranked and labelled by normative authority (see
  app/reasoning/source_hierarchy.py). Binding precedents (súmula vinculante,
  repercussão geral, repetitivos) are presented first and the model is told that
  they must be applied or expressly distinguished (CPC arts. 927 and 489, §1º, V-VI).
- More context is passed (configurable; default 5 documents x 1200 characters
  instead of 3 x 600).
- Rule.confidence no longer feeds the Qualifier; it encodes only the authority tier.
"""
from typing import List

from app.core.config import settings
from app.core.llm import generate
from app.core.logging import get_logger
from app.models.internal import Rule, Fact, Document
from app.reasoning import source_hierarchy as sh

logger = get_logger(__name__)


def select_context(documents: List[Document]) -> List[Document]:
    docs = [d for d in documents if not (settings.exclude_revoked_norms and sh.is_revoked(d))]
    if settings.source_hierarchy_enabled:
        docs = sh.rank_by_authority(docs)
    return docs[: settings.rule_matcher_max_docs]


def format_sources(documents: List[Document]) -> str:
    parts = []
    for i, doc in enumerate(documents):
        head = sh.label(doc) if settings.source_hierarchy_enabled else (
            (doc.metadata or {}).get("law_name") or doc.source or "")
        parts.append(f"Fonte {i+1} {head}:\n{doc.content[: settings.rule_matcher_doc_chars]}")
    return "\n\n".join(parts)


HIERARCHY_INSTRUCTION = """
Hierarquia das fontes: fontes marcadas como PRECEDENTE VINCULANTE ou TESE de observância
obrigatória devem ser aplicadas ou expressamente afastadas por distinção (CPC art. 927 e
art. 489, §1º, V e VI). Ao invocar um precedente, identifique seus fundamentos determinantes.
Não trate súmulas comuns ou orientações administrativas como vinculantes."""


class RuleMatcher:
    """Matches legal rules to extracted facts using the LLM, restricted to the retrieved sources."""

    async def match_rules(self, facts: List[Fact], documents: List[Document], query: str) -> List[Rule]:
        try:
            logger.debug("matching_rules", fact_count=len(facts), doc_count=len(documents))
            facts_text = "\n".join(f"- {fact.text}" for fact in facts)
            ctx = select_context(documents)
            docs_text = format_sources(ctx)
            hierarchy = HIERARCHY_INSTRUCTION if settings.source_hierarchy_enabled else ""

            prompt = f"""Você identifica as regras jurídicas aplicáveis, usando SOMENTE as fontes fornecidas.

Consulta: {query}

Fatos identificados:
{facts_text}

Fontes disponíveis:
{docs_text}
{hierarchy}

Para cada regra aplicável, responda no formato:
REGRA: [descrição da regra]
FONTE: [dispositivo exato, ex.: Art. 19-Q da Lei 8.080/1990; Súmula Vinculante 61; Tema 1234 do STF]
NÚMERO DA FONTE: [número da Fonte acima]

Não cite dispositivos que não estejam nas fontes. Se não houver regra aplicável nas fontes,
responda "NENHUMA REGRA IDENTIFICADA"."""

            content = await generate(prompt)
            rules: List[Rule] = []
            cur_rule, cur_src, cur_idx = None, None, None

            def flush():
                if not cur_rule:
                    return
                tier = 6
                if cur_idx is not None and 0 <= cur_idx < len(ctx):
                    tier = sh.authority(ctx[cur_idx])[0]
                rules.append(Rule(
                    text=cur_rule,
                    source=cur_src or "fonte não indicada",
                    article=None,
                    jurisdiction=None,
                    confidence=round(1.0 - (tier - 1) * 0.1, 2),  # authority tier only
                ))

            for line in content.split("\n"):
                line = line.strip()
                up = line.upper()
                if up.startswith("REGRA:"):
                    flush()
                    cur_rule, cur_src, cur_idx = line.split(":", 1)[1].strip(), None, None
                elif up.startswith("FONTE:"):
                    cur_src = line.split(":", 1)[1].strip()
                elif up.startswith("NÚMERO DA FONTE:") or up.startswith("NUMERO DA FONTE:"):
                    digits = "".join(ch for ch in line.split(":", 1)[1] if ch.isdigit())
                    cur_idx = int(digits) - 1 if digits else None
            flush()

            logger.info("rules_matched", count=len(rules))
            return rules
        except Exception as e:
            logger.error("rule_matching_error", error=str(e))
            return []


rule_matcher = RuleMatcher()
