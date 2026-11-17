"""
LSIM Engine: Logical-Semantic Integration Module
Combines symbolic reasoning with neural LLM generation using Thought Traces.

Author: Delvek da S. V. de Sousa
Copyright (c) 2025 Delvek da S. V. de Sousa
"""
import re
from typing import List

from app.core.config import settings
from app.core.llm import get_llm, generate
from app.core.logging import get_logger
from app.models.internal import (
    ThoughtTrace, Fact, Rule, IntermediateConclusion,
    ReasoningContext, Document
)
from app.reasoning.fact_extractor import fact_extractor
from app.reasoning.rule_matcher import rule_matcher

logger = get_logger(__name__)


class LSIMEngine:
    """
    Logical-Semantic Integration Module.

    Implements structured reasoning that forces the LLM to:
    1. Extract explicit facts
    2. Identify applicable rules
    3. Derive step-by-step conclusions
    4. Validate safety using SCOT
    """

    def __init__(self):
        self.system_prompt = """
Você é um assistente de pesquisa jurídica em Direito Brasileiro (sistema de matriz romano-germânica com precedentes vinculantes: CF art. 103-A; CPC arts. 926-928).
Você NÃO decide casos: você organiza fundamentos para análise por um profissional humano.
Sua tarefa é responder perguntas baseando-se ESTRITAMENTE no contexto fornecido (Legislação e Jurisprudência Brasileira).
1. NÃO utilize seu conhecimento prévio sobre leis dos EUA ou Europa.
2. Se o contexto não tiver a resposta, diga que não sabe.
3. Use terminologia jurídica correta em Português do Brasil.
4. SEMPRE cite os números exatos dos artigos de lei (ex: Art. 5º, §1º da CF/88; Art. 186 do CC/2002; Art. 14 do CDC).
5. Ao referenciar legislação, inclua o nome completo da lei e seu número (ex: Lei 8.078/1990 - CDC).
"""

    @property
    def llm(self):
        return get_llm()

    async def reason(self, context: ReasoningContext) -> ThoughtTrace:
        """
        Execute the complete LSIM reasoning pipeline.

        Args:
            context: Reasoning context with query and documents

        Returns:
            ThoughtTrace with complete reasoning chain
        """
        try:
            logger.info(
                "lsim_reasoning_start",
                query_length=len(context.query),
                doc_count=len(context.documents),
                trace_id=context.trace_id
            )

            if not settings.lsim_enabled:
                return await self._reason_without_lsim(context)

            # Step 1: Extract Facts
            query_facts = await fact_extractor.extract_from_query(context.query)
            doc_facts = await fact_extractor.extract_from_documents(
                context.documents,
                context.query
            )
            all_facts = query_facts + doc_facts

            logger.info("facts_extracted", total_facts=len(all_facts))

            # Step 2: Match Rules
            rules = await rule_matcher.match_rules(
                all_facts,
                context.documents,
                context.query
            )

            logger.info("rules_matched", total_rules=len(rules))

            # Step 3: Derive Intermediate Conclusions
            intermediate_conclusions = await self._derive_conclusions(
                all_facts,
                rules,
                context.query
            )

            logger.info("conclusions_derived", steps=len(intermediate_conclusions))

            # Step 4: Generate Final Conclusion
            final_conclusion = await self._generate_final_conclusion(
                all_facts,
                rules,
                intermediate_conclusions,
                context.query
            )

            # Step 5: SCOT Validation (if enabled)
            safety_validated = True
            safety_issues = []

            if settings.scot_enabled:
                safety_validated, safety_issues = await self._scot_validate(
                    final_conclusion,
                    all_facts,
                    rules
                )

            # Build Thought Trace
            trace = ThoughtTrace(
                facts=all_facts,
                rules=rules,
                intermediate_conclusions=intermediate_conclusions,
                final_conclusion=final_conclusion,
                safety_validated=safety_validated,
                safety_issues=safety_issues
            )

            logger.info(
                "lsim_reasoning_complete",
                safety_validated=safety_validated,
                trace_id=context.trace_id
            )

            return trace

        except Exception as e:
            logger.error("lsim_reasoning_error", error=str(e))
            raise

    async def _derive_conclusions(
        self,
        facts: List[Fact],
        rules: List[Rule],
        query: str
    ) -> List[IntermediateConclusion]:
        """Derive step-by-step intermediate conclusions."""
        try:
            facts_text = "\n".join([f"- {f.text}" for f in facts])
            rules_text = "\n".join([f"- {r.text} (Fonte: {r.source})" for r in rules])

            prompt = self.system_prompt + f"""
Você é um jurista que raciocina de forma estruturada.

Consulta: {query}

Fatos:
{facts_text}

Regras aplicáveis:
{rules_text}

Derive conclusões intermediárias aplicando as regras aos fatos, passo a passo.

Para cada passo, responda no formato:
PASSO X:
PREMISSA: [fatos usados]
REGRA APLICADA: [regra utilizada]
CONCLUSÃO: [conclusão derivada]

Faça no máximo 3 passos."""

            response = await self.llm.ainvoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            # Parse intermediate conclusions
            conclusions = []
            current_step = None
            current_premise = []
            current_rule = None
            current_conclusion = None

            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('PASSO'):
                    if current_step and current_conclusion:
                        conclusions.append(
                            IntermediateConclusion(
                                step=current_step,
                                premise=current_premise,
                                rule_applied=current_rule or "desconhecida",
                                conclusion=current_conclusion,
                                confidence=0.8
                            )
                        )
                    # Extract step number
                    try:
                        current_step = int(line.split(':')[0].replace('PASSO', '').strip())
                    except:
                        current_step = len(conclusions) + 1
                    current_premise = []
                    current_rule = None
                    current_conclusion = None
                elif line.startswith('PREMISSA:'):
                    current_premise = [line.replace('PREMISSA:', '').strip()]
                elif line.startswith('REGRA APLICADA:'):
                    current_rule = line.replace('REGRA APLICADA:', '').strip()
                elif line.startswith('CONCLUSÃO:') or line.startswith('CONCLUSAO:'):
                    current_conclusion = line.replace('CONCLUSÃO:', '').replace('CONCLUSAO:', '').strip()

            # Add last conclusion
            if current_step and current_conclusion:
                conclusions.append(
                    IntermediateConclusion(
                        step=current_step,
                        premise=current_premise,
                        rule_applied=current_rule or "desconhecida",
                        conclusion=current_conclusion,
                        confidence=0.8
                    )
                )

            return conclusions

        except Exception as e:
            logger.error("conclusion_derivation_error", error=str(e))
            return []

    async def _generate_final_conclusion(
        self,
        facts: List[Fact],
        rules: List[Rule],
        intermediate_conclusions: List[IntermediateConclusion],
        query: str
    ) -> str:
        """Generate the final conclusion from all reasoning steps."""
        try:
            conclusions_text = "\n".join([
                f"{c.step}. {c.conclusion}"
                for c in intermediate_conclusions
            ])

            prompt = self.system_prompt + f"""
Com base no raciocínio desenvolvido, forneça uma conclusão final clara e objetiva.

Consulta original: {query}

Conclusões intermediárias:
{conclusions_text}

Forneça uma conclusão final que responda diretamente à consulta."""

            response = await self.llm.ainvoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            return content.strip()

        except Exception as e:
            logger.error("final_conclusion_error", error=str(e))
            return "Não foi possível gerar uma conclusão final."

    async def _scot_validate(
        self,
        conclusion: str,
        facts: List[Fact],
        rules: List[Rule]
    ) -> tuple[bool, List[str]]:
        """
        Safety Chain-of-Thought validation.
        Checks if the conclusion is safe and doesn't hallucinate facts.
        """
        try:
            facts_text = "\n".join([f"- {f.text}" for f in facts])

            prompt = self.system_prompt + f"""
Você é um validador de segurança jurídica.

Fatos estabelecidos:
{facts_text}

Conclusão proposta:
{conclusion}

Valide se esta conclusão:
1. Não alucina fatos que não foram estabelecidos
2. Não viola princípios de segurança jurídica
3. É baseada nas evidências disponíveis

Responda APENAS:
VÁLIDO: sim/não
PROBLEMAS: [liste os problemas se houver, ou "nenhum"]"""

            response = await self.llm.ainvoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            # Parse validation (accent-insensitive; previous parser required "válido: sim")
            is_valid = re.search(r"v[áa]lido\s*:\s*sim", content, re.IGNORECASE) is not None
            issues = []

            for line in content.split('\n'):
                line = line.strip()
                if line.upper().startswith('PROBLEMAS:'):
                    problems = line.split(':', 1)[1].strip()
                    if problems.strip('[]."').lower() not in ("nenhum", "nenhuma", ""):
                        issues.append(problems)

            logger.info("scot_validation_complete", valid=is_valid, issues_count=len(issues))

            return is_valid, issues

        except Exception as e:
            logger.error("scot_validation_error", error=str(e))
            return False, [f"SCOT indisponível: {e}"]  # fail closed: unvalidated output is not certified


    async def _reason_without_lsim(self, context: ReasoningContext) -> ThoughtTrace:
        """Ablation: one grounded generation over the same retrieved sources (no Fact-Rule-Conclusion chain)."""
        from app.reasoning.rule_matcher import select_context, format_sources
        ctx = select_context(context.documents)
        prompt = self.system_prompt + f"""
Fontes:
{format_sources(ctx)}

Consulta: {context.query}

Responda à consulta com base nas fontes, citando os dispositivos exatos."""
        conclusion = await generate(prompt)
        ok, issues = (True, [])
        if settings.scot_enabled:
            ok, issues = await self._scot_validate(conclusion, [], [])
        return ThoughtTrace(facts=[], rules=[], intermediate_conclusions=[],
                            final_conclusion=conclusion, safety_validated=ok, safety_issues=issues)


# Global instance
lsim_engine = LSIMEngine()
