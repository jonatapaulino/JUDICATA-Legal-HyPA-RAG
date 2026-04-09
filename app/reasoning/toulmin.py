"""
Toulmin formatter - Converts LSIM ThoughtTrace to structured Toulmin response.
Implements the Toulmin model of argumentation for judicial reasoning.

"""
from typing import List
from langchain_community.chat_models import ChatOllama

from app.core.config import settings
from app.core.logging import get_logger
from app.models.internal import ThoughtTrace, Document, SourceReference
from app.models.responses import ToulminResponse, Qualifier

logger = get_logger(__name__)


class ToulminFormatter:
    """
    Formats reasoning output into Toulmin's argumentation model.

    Maps LSIM components to Toulmin components:
    - Facts -> Data
    - Final Conclusion -> Claim
    - Rules -> Warrant + Backing
    - SCOT validation -> Qualifier + Rebuttal
    """

    def __init__(self):
        self.llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=0.1,
        )

    async def format(
        self,
        trace: ThoughtTrace,
        documents: List[Document],
        query: str,
        trace_id: str,
        processing_time_ms: int,
        query_complexity: str,
        anonymized: bool = False
    ) -> ToulminResponse:
        """
        Convert ThoughtTrace to ToulminResponse.

        Args:
            trace: Complete reasoning trace from LSIM
            documents: Retrieved source documents
            query: Original query
            trace_id: Request trace ID
            processing_time_ms: Processing time
            query_complexity: Query complexity level
            anonymized: Whether anonymization was applied

        Returns:
            Structured ToulminResponse
        """
        try:
            logger.info("formatting_toulmin_response", trace_id=trace_id)

            # Extract components
            claim = trace.final_conclusion

            data = [fact.text for fact in trace.facts]

            warrant = await self._generate_warrant(trace)

            backing = await self._generate_backing(trace)

            rebuttal = await self._generate_rebuttal(trace, query)

            qualifier = self._determine_qualifier(trace)

            sources = self._extract_sources(documents)

            # Build response
            response = ToulminResponse(
                claim=claim,
                data=data,
                warrant=warrant,
                backing=backing,
                rebuttal=rebuttal,
                qualifier=qualifier,
                trace_id=trace_id,
                sources=sources,
                processing_time_ms=processing_time_ms,
                query_complexity=query_complexity,
                safety_validated=trace.safety_validated,
                safety_warnings=trace.safety_issues,
                anonymized=anonymized
            )

            logger.info("toulmin_response_formatted", trace_id=trace_id)

            return response

        except Exception as e:
            logger.error("toulmin_formatting_error", error=str(e))
            raise

    async def _generate_warrant(self, trace: ThoughtTrace) -> str:
        """Generate the warrant (logical connection between data and claim)."""
        try:
            rules_text = "\n".join([f"- {r.text}" for r in trace.rules])
            conclusions_text = "\n".join([
                f"- {c.conclusion}"
                for c in trace.intermediate_conclusions
            ])

            prompt = f"""Com base nas regras e conclusões intermediárias, formule o princípio lógico que conecta os fatos à conclusão final.

Regras aplicadas:
{rules_text}

Conclusões intermediárias:
{conclusions_text}

Forneça um princípio lógico claro e conciso (1-2 frases)."""

            response = await self.llm.ainvoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            return content.strip()

        except Exception as e:
            logger.error("warrant_generation_error", error=str(e))
            return "Princípio lógico baseado nas regras aplicáveis."

    async def _generate_backing(self, trace: ThoughtTrace) -> str:
        """Generate the backing (legal authority supporting the warrant)."""
        try:
            rules_with_sources = [
                f"{r.text} (Fonte: {r.source})"
                for r in trace.rules
            ]
            rules_text = "\n".join(rules_with_sources)

            prompt = f"""Com base nas seguintes regras legais, forneça a fundamentação legal (leis, precedentes, artigos).

Regras e fontes:
{rules_text}

Forneça uma fundamentação legal clara citando as fontes."""

            response = await self.llm.ainvoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            return content.strip()

        except Exception as e:
            logger.error("backing_generation_error", error=str(e))
            return "Fundamentação baseada na legislação e jurisprudência aplicável."

    async def _generate_rebuttal(self, trace: ThoughtTrace, query: str) -> str:
        """Generate the rebuttal (counter-arguments and their refutation)."""
        try:
            conclusion = trace.final_conclusion

            prompt = f"""Considere possíveis contra-argumentos à seguinte conclusão e explique por que foram desconsiderados.

Consulta: {query}

Conclusão: {conclusion}

Forneça contra-argumentos relevantes e por que não se aplicam neste caso."""

            response = await self.llm.ainvoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            return content.strip()

        except Exception as e:
            logger.error("rebuttal_generation_error", error=str(e))
            return "Contra-argumentos considerados mas não aplicáveis às circunstâncias específicas do caso."

    def _determine_qualifier(self, trace: ThoughtTrace) -> Qualifier:
        """Determine the degree of certainty based on confidence scores and validation."""
        if not trace.safety_validated:
            return Qualifier.INCERTO

        # Calculate average confidence from facts, rules, and conclusions
        confidences = []

        for fact in trace.facts:
            confidences.append(fact.confidence)

        for rule in trace.rules:
            confidences.append(rule.confidence)

        for conclusion in trace.intermediate_conclusions:
            confidences.append(conclusion.confidence)

        if not confidences:
            return Qualifier.POSSIVEL

        avg_confidence = sum(confidences) / len(confidences)

        if avg_confidence >= 0.9:
            return Qualifier.CERTO
        elif avg_confidence >= 0.75:
            return Qualifier.PROVAVEL
        elif avg_confidence >= 0.5:
            return Qualifier.POSSIVEL
        else:
            return Qualifier.INCERTO

    def _extract_sources(self, documents: List[Document]) -> List[SourceReference]:
        """Extract source references from documents."""
        sources = []

        for doc in documents[:5]:  # Limit to top 5 sources
            citation = doc.metadata.get("citation", f"Documento {doc.id}")
            excerpt = doc.content[:200] + "..." if len(doc.content) > 200 else doc.content

            source = SourceReference(
                document_id=doc.id,
                citation=citation,
                relevance_score=doc.score,
                excerpt=excerpt
            )
            sources.append(source)

        return sources


# Global instance
toulmin_formatter = ToulminFormatter()
