"""
Rule matching from legal knowledge base and retrieved documents.
Identifies applicable legal rules given a set of facts.

"""
from typing import List
from langchain_community.chat_models import ChatOllama

from app.core.config import settings
from app.core.logging import get_logger
from app.models.internal import Rule, Fact, Document

logger = get_logger(__name__)


class RuleMatcher:
    """
    Matches legal rules to extracted facts using LLM.
    Rules represent legal principles, statutes, or precedents.
    """

    def __init__(self):
        self.llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=0.1,
        )

    async def match_rules(
        self,
        facts: List[Fact],
        documents: List[Document],
        query: str
    ) -> List[Rule]:
        """
        Identify applicable legal rules given facts and documents.

        Args:
            facts: Extracted facts
            documents: Retrieved legal documents
            query: Original query for context

        Returns:
            List of matched Rule objects
        """
        try:
            logger.debug("matching_rules", fact_count=len(facts), doc_count=len(documents))

            # Format facts
            facts_text = "\n".join([f"- {fact.text}" for fact in facts])

            # Format documents (focus on legal sources)
            docs_text = "\n\n".join([
                f"Fonte {i+1}: {doc.content[:600]}"
                for i, doc in enumerate(documents[:3])
            ])

            prompt = f"""Você é um especialista em direito que identifica regras legais aplicáveis.

Consulta: {query}

Fatos identificados:
{facts_text}

Fontes legais disponíveis:
{docs_text}

Identifique as regras legais (leis, artigos, princípios jurídicos, precedentes) que são aplicáveis aos fatos apresentados.

Para cada regra, responda no formato:
REGRA: [descrição da regra]
FONTE: [lei/artigo/precedente]
JURISDIÇÃO: [federal/estadual/etc]

Se não houver regras claras, responda "NENHUMA REGRA IDENTIFICADA"."""

            response = await self.llm.ainvoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            # Parse response
            rules = []
            current_rule = None
            current_source = None
            current_jurisdiction = None

            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('REGRA:'):
                    if current_rule:
                        rules.append(
                            Rule(
                                text=current_rule,
                                source=current_source or "jurisprudencia",
                                article=None,
                                jurisdiction=current_jurisdiction,
                                confidence=0.85
                            )
                        )
                    current_rule = line.replace('REGRA:', '').strip()
                    current_source = None
                    current_jurisdiction = None
                elif line.startswith('FONTE:'):
                    current_source = line.replace('FONTE:', '').strip()
                elif line.startswith('JURISDIÇÃO:') or line.startswith('JURISDICAO:'):
                    current_jurisdiction = line.replace('JURISDIÇÃO:', '').replace('JURISDICAO:', '').strip()

            # Add last rule
            if current_rule:
                rules.append(
                    Rule(
                        text=current_rule,
                        source=current_source or "jurisprudencia",
                        article=None,
                        jurisdiction=current_jurisdiction,
                        confidence=0.85
                    )
                )

            logger.info("rules_matched", count=len(rules))
            return rules

        except Exception as e:
            logger.error("rule_matching_error", error=str(e))
            return []


# Global instance
rule_matcher = RuleMatcher()
