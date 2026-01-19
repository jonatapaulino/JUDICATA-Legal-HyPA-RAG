"""
Guardian Agent - Zero Trust security layer.
Validates all inputs and outputs to prevent injection attacks and jailbreaks.

Author: Delvek da S. V. de Sousa
Copyright (c) 2025 Delvek da S. V. de Sousa
"""
import re
from typing import List
from datetime import datetime

from app.core.config import settings
from app.core.logging import get_logger
from app.models.internal import ValidationResult

logger = get_logger(__name__)


class GuardianAgent:
    """
    Security agent that validates inputs and outputs.

    Implements Zero Trust principles:
    - All inputs are untrusted until validated
    - All LLM outputs are checked for injection patterns
    - Maintains audit trail of all validations
    """

    # Patterns that indicate injection or jailbreak attempts
    BLOCKED_PATTERNS = [
        r"ignore\s+(as|todas|previous|anteriores|tudo|everything|all)\s+(instru[cç][õo][õe]s|instructions)?",
        r"ignore\s+(tudo|everything|all)",  # "Ignore tudo" mesmo sem segunda palavra
        r"você\s+(agora\s+)?(é|e|seja|se\s+torne)\s+",
        # BUG FIX #1: Adicionar variação sem acento (esqueca) e aceitar palavras no meio
        r"(esqueça|esqueca|ignore|delete|apague).{0,30}(regras|normas|instruções|instrucoes)",
        r"execute\s+(o\s+)?(comando|script|code|código)",
        r"system\s+(prompt|message|instruction)",
        r"<\s*script\s*>",
        r"javascript:",
        # BUG FIX #2: Melhorar SQL injection - detectar UNION SELECT separado
        r"(union\s+select|select\s+.*\s+from|insert\s+into|update\s+.*\s+set|delete\s+from|drop\s+table)",
        r"\$\{.*\}",  # Template injection
        r"\{\{.*\}\}",  # Template injection
    ]

    # Additional strict mode patterns
    STRICT_PATTERNS = [
        r"bypass",
        r"jailbreak",
        r"override",
        r"sudo",
        r"admin\s+mode",
    ]

    def __init__(self):
        self.enabled = settings.guardian_enabled
        self.strict_mode = settings.guardian_strict_mode

        # TODO: Considerar a integração de modelos de ML (ex: BERT-based) para detecção
        #       mais sofisticada de Prompt Injection, além dos padrões regex estáticos.
        #       Isso aumentaria a robustez contra ataques ofuscados.

        if self.strict_mode:
            self.compiled_patterns.extend([
                re.compile(pattern, re.IGNORECASE)
                for pattern in self.STRICT_PATTERNS
            ])

    def validate_input(self, text: str, source: str = "unknown") -> ValidationResult:
        """
        Validate input text for security threats.

        Args:
            text: Text to validate
            source: Source of the text (for logging)

        Returns:
            ValidationResult indicating if text is safe
        """
        if not self.enabled:
            return ValidationResult(safe=True)

        logger.debug("validating_input", source=source, text_length=len(text))

        blocked = []

        for pattern in self.compiled_patterns:
            match = pattern.search(text)
            if match:
                blocked.append(match.group(0))
                logger.warning(
                    "blocked_pattern_detected",
                    pattern=match.group(0),
                    source=source
                )

        if blocked:
            return ValidationResult(
                safe=False,
                reason=f"Blocked patterns detected: {', '.join(blocked[:3])}",
                blocked_patterns=blocked,
                timestamp=datetime.utcnow()
            )

        return ValidationResult(
            safe=True,
            timestamp=datetime.utcnow()
        )

    def validate_output(self, text: str, context: str = "unknown") -> ValidationResult:
        """
        Validate LLM output for leaked instructions or malicious content.

        Args:
            text: LLM output to validate
            context: Context of the output (for logging)

        Returns:
            ValidationResult indicating if output is safe
        """
        if not self.enabled:
            return ValidationResult(safe=True)

        logger.debug("validating_output", context=context, text_length=len(text))

        # Check for system prompt leakage
        system_indicators = [
            "você é um",
            "system:",
            "assistant:",
            "user:",
            "[INST]",
            "[/INST]",
        ]

        leaked = []
        for indicator in system_indicators:
            if indicator.lower() in text.lower():
                leaked.append(indicator)

        if leaked:
            logger.warning(
                "potential_prompt_leakage",
                indicators=leaked,
                context=context
            )

            if self.strict_mode:
                return ValidationResult(
                    safe=False,
                    reason="Potential system prompt leakage detected",
                    blocked_patterns=leaked,
                    timestamp=datetime.utcnow()
                )

        # Check for malicious patterns in output
        blocked = []
        for pattern in self.compiled_patterns:
            match = pattern.search(text)
            if match:
                blocked.append(match.group(0))

        if blocked:
            logger.error(
                "malicious_output_detected",
                patterns=blocked,
                context=context
            )
            return ValidationResult(
                safe=False,
                reason=f"Malicious patterns in output: {', '.join(blocked[:3])}",
                blocked_patterns=blocked,
                timestamp=datetime.utcnow()
            )

        return ValidationResult(
            safe=True,
            timestamp=datetime.utcnow()
        )

    def validate_chain(self, items: List[str], context: str = "chain") -> ValidationResult:
        """
        Validate a chain of texts (e.g., thought trace).

        Args:
            items: List of text items to validate
            context: Context for logging

        Returns:
            ValidationResult for the entire chain
        """
        # BUG FIX #3: Usar validate_input em vez de validate_output
        # validate_output é para saídas do LLM, validate_input é para textos que vão pro LLM
        for i, item in enumerate(items):
            result = self.validate_input(item, source=f"{context}[{i}]")
            if not result.safe:
                return result

        return ValidationResult(
            safe=True,
            timestamp=datetime.utcnow()
        )


# Global instance
guardian = GuardianAgent()
