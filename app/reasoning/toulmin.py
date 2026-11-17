"""
Toulmin formatter - converts the LSIM ThoughtTrace into Toulmin's six components.

Revision notes (PLOS ONE review):
- Toulmin is used as a STRUCTURE for presenting and contesting an argument. It is
  not, by itself, a procedural guarantee (no parties, evidence or adversarial
  hearing exist in this system).
- Backing is generated only from the retrieved source excerpts, and every
  provision cited in Claim/Backing is checked deterministically against the
  retrieved documents (grounding) and the validity catalog (revoked statutes).
- The Qualifier is derived from that evidence (grounding rate, revoked citations,
  presence of a binding source, SCOT result) instead of from hard-coded confidence
  constants. The rule is documented in `qualify()` and reported in the paper.
"""
from typing import List, Tuple

from app.core.config import settings
from app.core.llm import generate
from app.core.logging import get_logger
from app.models.internal import ThoughtTrace, Document, SourceReference
from app.models.responses import ToulminResponse, Qualifier
from app.reasoning import source_hierarchy as sh
from app.reasoning.citations import verify_citations, CitationCheck
from app.reasoning.rule_matcher import select_context, format_sources

logger = get_logger(__name__)


def qualify(check: CitationCheck, safety_validated: bool, has_binding_source: bool) -> Tuple[Qualifier, str]:
    """
    Evidence-based qualifier.

    INCERTO  - SCOT rejected the conclusion, or a revoked statute is cited, or
               no specific provision is cited, or fewer than half of the cited
               provisions are found in the retrieved sources;
    POSSIVEL - 50% <= grounding < 80%;
    PROVAVEL - grounding >= 80%;
    CERTO    - grounding = 100% AND at least one binding source (SV, RG or
               repetitive thesis) was retrieved and cited.
    """
    if not safety_validated:
        return Qualifier.INCERTO, "Validação SCOT não aprovou a conclusão."
    if check.revoked:
        return Qualifier.INCERTO, f"Cita norma revogada: {', '.join(check.revoked)}."
    if not check.cited:
        return Qualifier.INCERTO, "Nenhum dispositivo específico citado."
    g = check.grounding_rate or 0.0
    basis = f"{len(check.grounded)}/{len(check.cited)} dispositivos citados constam das fontes recuperadas"
    if g < 0.5:
        return Qualifier.INCERTO, basis + "."
    if g < 0.8:
        return Qualifier.POSSIVEL, basis + "."
    if g == 1.0 and has_binding_source:
        return Qualifier.CERTO, basis + "; há precedente vinculante aplicável entre as fontes."
    return Qualifier.PROVAVEL, basis + "."


class ToulminFormatter:
    """Formats reasoning output into Toulmin's argumentation model."""

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
        try:
            logger.info("formatting_toulmin_response", trace_id=trace_id)
            ctx = select_context(documents or [])

            claim = trace.final_conclusion
            data = [fact.text for fact in trace.facts]
            warrant = await self._generate_warrant(trace)
            backing = await self._generate_backing(trace, ctx)
            rebuttal = await self._generate_rebuttal(trace, query, ctx)

            binding = [sh.label(d) for d in ctx if sh.authority(d)[0] == 1]
            if settings.backing_verification_enabled:
                check = verify_citations(f"{claim}\n{backing}", documents or [], sh.revoked_laws())
                qualifier, basis = qualify(check, trace.safety_validated, bool(binding))
            else:
                check = CitationCheck()
                qualifier, basis = self._legacy_qualifier(trace), "Qualificador sem verificação (ablação)."

            return ToulminResponse(
                claim=claim,
                data=data,
                warrant=warrant,
                backing=backing,
                rebuttal=rebuttal,
                qualifier=qualifier,
                trace_id=trace_id,
                sources=self._extract_sources(ctx),
                processing_time_ms=processing_time_ms,
                query_complexity=query_complexity,
                safety_validated=trace.safety_validated,
                safety_warnings=trace.safety_issues,
                anonymized=anonymized,
                citation_check=check.to_dict(),
                qualifier_basis=basis,
                binding_sources=binding,
            )
        except Exception as e:
            logger.error("toulmin_formatting_error", error=str(e))
            raise

    async def _generate_warrant(self, trace: ThoughtTrace) -> str:
        rules_text = "\n".join(f"- {r.text} ({r.source})" for r in trace.rules)
        conclusions_text = "\n".join(f"- {c.conclusion}" for c in trace.intermediate_conclusions)
        prompt = f"""Formule, em 1-2 frases, a garantia (warrant) que liga os dados à conclusão.

Regras aplicadas:
{rules_text or '- (nenhuma regra extraída)'}

Conclusões intermediárias:
{conclusions_text or '- (nenhuma)'}

Conclusão: {trace.final_conclusion}"""
        try:
            return await generate(prompt, temperature=0.1)
        except Exception as e:
            logger.error("warrant_generation_error", error=str(e))
            return ""

    async def _generate_backing(self, trace: ThoughtTrace, ctx: List[Document]) -> str:
        prompt = f"""Escreva o respaldo (backing) da garantia: os dispositivos legais e precedentes que a sustentam.
Use EXCLUSIVAMENTE as fontes abaixo e cite cada dispositivo exatamente como aparece nelas.
Não cite nada que não esteja nas fontes.

Fontes:
{format_sources(ctx)}

Regras identificadas:
{chr(10).join(f'- {r.text} ({r.source})' for r in trace.rules) or '- (nenhuma)'}"""
        try:
            return await generate(prompt, temperature=0.1)
        except Exception as e:
            logger.error("backing_generation_error", error=str(e))
            return ""

    async def _generate_rebuttal(self, trace: ThoughtTrace, query: str, ctx: List[Document]) -> str:
        prompt = f"""Indique as condições de refutação (rebuttal): em que circunstâncias a conclusão NÃO se aplicaria
(fatos que, se presentes, afastariam a conclusão; exceções e distinções possíveis). Seja específico e
baseie-se nas fontes.

Consulta: {query}
Conclusão: {trace.final_conclusion}

Fontes:
{format_sources(ctx)}"""
        try:
            return await generate(prompt, temperature=0.1)
        except Exception as e:
            logger.error("rebuttal_generation_error", error=str(e))
            return ""

    @staticmethod
    def _legacy_qualifier(trace: ThoughtTrace) -> Qualifier:
        """Original (pre-revision) qualifier, kept only for the ablation study."""
        if not trace.safety_validated:
            return Qualifier.INCERTO
        conf = [f.confidence for f in trace.facts] + [0.85 for _ in trace.rules] + \
               [c.confidence for c in trace.intermediate_conclusions]
        if not conf:
            return Qualifier.POSSIVEL
        avg = sum(conf) / len(conf)
        return (Qualifier.CERTO if avg >= 0.9 else Qualifier.PROVAVEL if avg >= 0.75
                else Qualifier.POSSIVEL if avg >= 0.5 else Qualifier.INCERTO)

    @staticmethod
    def _extract_sources(documents: List[Document]) -> List[SourceReference]:
        out = []
        for doc in documents[:5]:
            out.append(SourceReference(
                document_id=doc.id,
                citation=sh.label(doc),
                relevance_score=doc.score,
                excerpt=doc.content[:200] + ("..." if len(doc.content) > 200 else ""),
            ))
        return out


toulmin_formatter = ToulminFormatter()
