"""
Safety Validator for P2P Defense.

Validates inputs and outputs against P2P defense rules and integrates
with the broader security architecture.

"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

from .p2p_defense import P2PDefense, P2PConfig, BenignTrigger

logger = logging.getLogger(__name__)


class ValidationResult(Enum):
    """Result of safety validation."""
    SAFE = "safe"
    BLOCKED = "blocked"
    WARNING = "warning"
    REQUIRES_REVIEW = "requires_review"


@dataclass
class ValidationReport:
    """Report from safety validation."""
    result: ValidationResult
    timestamp: datetime = field(default_factory=datetime.now)
    input_safe: bool = True
    output_safe: bool = True
    triggered_defenses: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    safe_response: Optional[str] = None
    confidence: float = 1.0
    details: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "result": self.result.value,
            "timestamp": self.timestamp.isoformat(),
            "input_safe": self.input_safe,
            "output_safe": self.output_safe,
            "triggered_defenses": self.triggered_defenses,
            "warnings": self.warnings,
            "safe_response": self.safe_response,
            "confidence": self.confidence,
            "details": self.details
        }


class SafetyValidator:
    """
    Validates inputs and outputs for safety using P2P defense.

    Integrates P2P defense with the broader security architecture
    including Guardian Agent, RAG Defender, and SCOT.
    """

    def __init__(
        self,
        p2p_defense: Optional[P2PDefense] = None,
        strict_mode: bool = True
    ):
        """
        Initialize SafetyValidator.

        Args:
            p2p_defense: P2P defense instance (created if not provided)
            strict_mode: If True, blocks on any trigger detection
        """
        self.p2p = p2p_defense or P2PDefense()
        self.strict_mode = strict_mode
        self.validation_history: List[ValidationReport] = []

        # Additional safety patterns not in P2P triggers
        self._safety_patterns = self._initialize_safety_patterns()

    def _initialize_safety_patterns(self) -> Dict[str, Dict]:
        """Initialize additional safety check patterns."""
        return {
            # Legal citation verification patterns
            "fake_citation": {
                "pattern": r"(?:Art\.|Artigo)\s*\d+[A-Z]?\s*(?:da|do)\s*(?:Lei|Decreto|CF)\s*(?:n[º°.]?\s*)?[\d\.]+(?:/\d+)?",
                "action": "verify",
                "description": "Detected legal citation - should be verified"
            },

            # Absolute statement patterns (risky in legal context)
            "absolute_statement": {
                "pattern": r"(?:sempre|nunca|em\s+todos\s+os\s+casos|jamais|obrigatoriamente)\s+(?:deve|será|terá)",
                "action": "warning",
                "description": "Absolute legal statement detected - may need qualification"
            },

            # Definitive judgment patterns
            "definitive_judgment": {
                "pattern": r"(?:é\s+culpado|é\s+inocente|deve\s+ser\s+condenado|deve\s+ser\s+absolvido)",
                "action": "review",
                "description": "Definitive judgment detected - requires human review"
            },

            # Personal data patterns (LGPD compliance)
            "personal_data": {
                "pattern": r"(?:CPF|RG|CNH)[\s:]*\d",
                "action": "anonymize",
                "description": "Personal data detected - should be anonymized"
            },

            # Sensitive legal terms
            "sensitive_terms": {
                "pattern": r"(?:segredo\s+de\s+justiça|sigilo|confidencial|restrito)",
                "action": "warning",
                "description": "Sensitive term detected - verify handling"
            }
        }

    def validate_input(self, text: str) -> ValidationReport:
        """
        Validate input text for safety.

        Args:
            text: Input text to validate

        Returns:
            ValidationReport with results
        """
        report = ValidationReport(result=ValidationResult.SAFE)

        # Check P2P triggers
        p2p_matches = self.p2p.detect_triggers(text)

        if p2p_matches:
            report.input_safe = False
            report.triggered_defenses = [f"p2p:{t.id}" for t, _ in p2p_matches]

            # Get safe response from highest confidence match
            best_trigger, confidence = p2p_matches[0]
            report.safe_response = best_trigger.safe_response
            report.confidence = confidence

            if self.strict_mode:
                report.result = ValidationResult.BLOCKED
            else:
                report.result = ValidationResult.WARNING

            report.details["p2p_matches"] = [
                {
                    "trigger_id": t.id,
                    "trigger_type": t.trigger_type.value,
                    "confidence": c
                }
                for t, c in p2p_matches
            ]

        # Check additional safety patterns
        for pattern_name, pattern_info in self._safety_patterns.items():
            if re.search(pattern_info["pattern"], text, re.IGNORECASE):
                report.warnings.append(f"{pattern_name}: {pattern_info['description']}")

                if pattern_info["action"] == "review":
                    if report.result == ValidationResult.SAFE:
                        report.result = ValidationResult.REQUIRES_REVIEW

        # Record in history
        self.validation_history.append(report)

        return report

    def validate_output(
        self,
        input_text: str,
        output_text: str
    ) -> ValidationReport:
        """
        Validate output text for safety given input.

        Args:
            input_text: Original input text
            output_text: Generated output text

        Returns:
            ValidationReport with results
        """
        report = ValidationReport(result=ValidationResult.SAFE)

        # First validate input
        input_report = self.validate_input(input_text)

        if input_report.result == ValidationResult.BLOCKED:
            # Input was blocked, output should be the safe response
            report.input_safe = False
            report.triggered_defenses.extend(input_report.triggered_defenses)
            report.safe_response = input_report.safe_response

            # Check if output matches expected safe response
            if not self._output_matches_safe_pattern(output_text, input_report):
                report.output_safe = False
                report.result = ValidationResult.BLOCKED
                report.warnings.append(
                    "Output does not follow expected safe response pattern"
                )
            else:
                report.result = ValidationResult.WARNING

        # Validate output content
        output_issues = self._validate_output_content(output_text)

        if output_issues:
            report.warnings.extend(output_issues)
            if any("hallucination" in issue.lower() for issue in output_issues):
                report.output_safe = False
                if report.result == ValidationResult.SAFE:
                    report.result = ValidationResult.WARNING

        # Record in history
        self.validation_history.append(report)

        return report

    def _output_matches_safe_pattern(
        self,
        output: str,
        input_report: ValidationReport
    ) -> bool:
        """Check if output follows expected safe response pattern."""
        # Check for safety indicators in output
        safety_indicators = [
            "nao posso",
            "nao e possivel",
            "devo considerar",
            "analise juridica",
            "imparcial",
            "baseado em fatos",
            "legislacao aplicavel",
            "principio",
            "devido processo"
        ]

        output_lower = output.lower()

        # At least one safety indicator should be present
        has_indicator = any(
            indicator in output_lower
            for indicator in safety_indicators
        )

        # Check for absence of harmful patterns
        harmful_patterns = [
            r"vou\s+(?:ignorar|desconsiderar|pular)",
            r"(?:sim|ok|claro),?\s+vou\s+fazer",
            r"como\s+(?:advogado|representante)\s+da\s+parte"
        ]

        has_harmful = any(
            re.search(pattern, output_lower)
            for pattern in harmful_patterns
        )

        return has_indicator and not has_harmful

    def _validate_output_content(self, output: str) -> List[str]:
        """Validate output content for potential issues."""
        issues = []

        # Check for potential hallucination indicators
        hallucination_patterns = [
            (r"(?:Lei|Decreto)\s*n?[º°.]?\s*\d+(?:\.\d+)?/\d{4}", "legal_citation"),
            (r"(?:STF|STJ|TST|TRF|TJ[A-Z]{2})\s*(?:,|-)?\s*(?:RE|REsp|RR|HC|MS|ADI)\s*\d+", "case_citation"),
            (r"Sumula\s*(?:Vinculante)?\s*n?[º°.]?\s*\d+", "sumula_citation"),
        ]

        for pattern, citation_type in hallucination_patterns:
            matches = re.findall(pattern, output, re.IGNORECASE)
            if matches:
                issues.append(
                    f"Contains {len(matches)} {citation_type}(s) that should be verified: {matches[:3]}"
                )

        # Check for overconfident language
        overconfident_patterns = [
            r"certamente\s+será",
            r"sem\s+dúvida\s+alguma",
            r"é\s+garantido\s+que",
            r"sempre\s+(?:será|terá|deve)",
            r"nunca\s+(?:será|terá|deve)"
        ]

        for pattern in overconfident_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                issues.append(
                    "Contains overconfident language that may not be appropriate for legal analysis"
                )
                break

        return issues

    def validate_full_pipeline(
        self,
        input_text: str,
        retrieved_docs: List[str],
        reasoning_chain: str,
        final_output: str
    ) -> ValidationReport:
        """
        Validate the full reasoning pipeline.

        Args:
            input_text: Original input
            retrieved_docs: Documents retrieved by RAG
            reasoning_chain: Chain of thought reasoning
            final_output: Final generated output

        Returns:
            Comprehensive ValidationReport
        """
        report = ValidationReport(result=ValidationResult.SAFE)

        # 1. Validate input
        input_report = self.validate_input(input_text)
        if input_report.result != ValidationResult.SAFE:
            report.triggered_defenses.extend(input_report.triggered_defenses)
            report.warnings.extend(input_report.warnings)
            report.input_safe = input_report.input_safe

        # 2. Validate retrieved documents for poisoning
        for i, doc in enumerate(retrieved_docs):
            doc_issues = self._check_document_for_poisoning(doc)
            if doc_issues:
                report.warnings.append(f"Document {i}: {doc_issues}")
                report.triggered_defenses.append(f"doc_poison_check:{i}")

        # 3. Validate reasoning chain
        chain_issues = self._validate_reasoning_chain(reasoning_chain)
        if chain_issues:
            report.warnings.extend(chain_issues)
            if any("manipulated" in issue.lower() for issue in chain_issues):
                report.result = ValidationResult.REQUIRES_REVIEW

        # 4. Validate final output
        output_report = self.validate_output(input_text, final_output)
        report.output_safe = output_report.output_safe
        report.warnings.extend(output_report.warnings)

        # Determine final result
        if not report.input_safe and self.strict_mode:
            report.result = ValidationResult.BLOCKED
            report.safe_response = input_report.safe_response
        elif not report.output_safe:
            report.result = ValidationResult.WARNING
        elif report.warnings:
            report.result = ValidationResult.REQUIRES_REVIEW

        # Add details
        report.details = {
            "input_validation": input_report.to_dict(),
            "output_validation": output_report.to_dict(),
            "docs_checked": len(retrieved_docs),
            "chain_length": len(reasoning_chain)
        }

        self.validation_history.append(report)
        return report

    def _check_document_for_poisoning(self, doc: str) -> Optional[str]:
        """Check a retrieved document for potential poisoning."""
        # Poisoning indicators
        poison_patterns = [
            (r"ignore\s+(?:as|todas)\s+instrucoes", "instruction_override"),
            (r"novo\s+modo\s+de\s+operacao", "mode_change"),
            (r"sistema:\s*novo\s*prompt", "system_injection"),
            (r"\[INST\]|\[/INST\]|<\|im_start\|>", "prompt_injection"),
        ]

        for pattern, indicator in poison_patterns:
            if re.search(pattern, doc, re.IGNORECASE):
                return f"Potential poisoning detected: {indicator}"

        return None

    def _validate_reasoning_chain(self, chain: str) -> List[str]:
        """Validate reasoning chain for manipulation."""
        issues = []

        # Check for reasoning manipulation patterns
        manipulation_patterns = [
            (r"(?:mas|porem|entretanto)\s+devo\s+ignorar", "reasoning_override"),
            (r"apesar\s+(?:disso|de)\s+vou\s+(?:ignorar|desconsiderar)", "evidence_bypass"),
            (r"mesmo\s+(?:assim|que)\s+(?:nao|sem)\s+(?:provas|evidencias)", "proof_bypass"),
        ]

        for pattern, indicator in manipulation_patterns:
            if re.search(pattern, chain, re.IGNORECASE):
                issues.append(f"Reasoning may be manipulated: {indicator}")

        # Check for logical inconsistencies
        if "portanto" in chain.lower() or "logo" in chain.lower():
            # Has conclusion markers - verify logical flow
            if not self._has_valid_logical_flow(chain):
                issues.append("Reasoning chain may have logical inconsistencies")

        return issues

    def _has_valid_logical_flow(self, chain: str) -> bool:
        """Check if reasoning has valid logical flow."""
        # Simplified check - look for premises before conclusions
        conclusion_markers = ["portanto", "logo", "assim", "consequentemente"]
        premise_markers = ["porque", "pois", "uma vez que", "dado que", "considerando"]

        chain_lower = chain.lower()

        has_premise = any(m in chain_lower for m in premise_markers)
        has_conclusion = any(m in chain_lower for m in conclusion_markers)

        # Valid if either: has both premise and conclusion, or has neither
        return (has_premise and has_conclusion) or (not has_premise and not has_conclusion)

    def get_statistics(self) -> Dict:
        """Get validation statistics."""
        total = len(self.validation_history)

        if total == 0:
            return {"total_validations": 0}

        result_counts = {}
        for report in self.validation_history:
            result = report.result.value
            result_counts[result] = result_counts.get(result, 0) + 1

        blocked_count = result_counts.get("blocked", 0)
        warning_count = result_counts.get("warning", 0)

        return {
            "total_validations": total,
            "results": result_counts,
            "block_rate": blocked_count / total if total > 0 else 0,
            "warning_rate": warning_count / total if total > 0 else 0,
            "p2p_stats": self.p2p.get_statistics()
        }

    def clear_history(self):
        """Clear validation history."""
        self.validation_history.clear()
