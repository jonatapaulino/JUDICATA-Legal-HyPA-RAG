"""
Guardian Agent - Zero Trust security layer.
Validates all inputs and outputs to prevent injection attacks and jailbreaks.

"""
import re
from typing import List
from datetime import datetime, timezone

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
        r"ignore\s+(as|todas|previous|anteriores|tudo|everything|all|your|suas)?\s*(instru[cç][õo][õe]s|instructions)",
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
        # Jailbreak: roleplay/pretend attacks
        r"finja\s+(ser|que)",
        r"responda\s+como\s+se",
        r"(sem|n[ãa]o\s+tivesse)\s+(restri[çc][õo]es|filtros|limites)",
        r"DAN\s+mode",
        # XSS: additional dangerous HTML tags and event handlers
        r"<\s*(svg|img|iframe|object|embed)\b",
        r"on(load|error|click|mouseover)\s*=",
        r"fetch\s*\(",
        # Instruction bypass: false information and temporal bypass
        r"informa[çc][õo]es\s+falsas",
        r"(cite|crie|invente)\s+leis\s+que\s+n[ãa]o\s+existem",
        r"a\s+partir\s+de\s+agora",
        # Hack/exfiltration/destruction attempts
        r"(hackear|hack|hacker|invadir)\b",
        r"(exportar|extrair|dump)\s+(banco|base|dados)",
        r"(delete|deletar|apagar|destruir)\s+(todos|tudo|dados|sistema)",
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

        # Compile patterns for efficiency
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.BLOCKED_PATTERNS
        ]

        if self.strict_mode:
            self.compiled_patterns.extend([
                re.compile(pattern, re.IGNORECASE)
                for pattern in self.STRICT_PATTERNS
            ])

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text to handle obfuscation (Leetspeak).
        Example: "1gn0r3" -> "ignore"
        """
        leet_map = {
            '0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's',
            '7': 't', '@': 'a', '$': 's', '!': 'i',
            '8': 'b', '2': 'z', '9': 'g', '6': 'g',
        }

        normalized = text.lower()
        for char, replacement in leet_map.items():
            normalized = normalized.replace(char, replacement)

        # Normalize underscores and hyphens to spaces
        normalized = normalized.replace('_', ' ').replace('-', ' ')

        return normalized

    def validate_input(self, text: str, source: str = "unknown") -> ValidationResult:
        """
        Validate input text for security threats.
        Checks both original and normalized (anti-obfuscation) text.

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
        
        # Check original text
        for pattern in self.compiled_patterns:
            match = pattern.search(text)
            if match:
                blocked.append(match.group(0))

        # Check normalized text (if different)
        normalized_text = self._normalize_text(text)
        if normalized_text != text.lower():
            for pattern in self.compiled_patterns:
                match = pattern.search(normalized_text)
                if match:
                    blocked.append(f"{match.group(0)} (obfuscated)")

        if blocked:
            logger.warning(
                "blocked_pattern_detected",
                patterns=blocked,
                source=source
            )
            return ValidationResult(
                safe=False,
                reason=f"Blocked patterns detected: {', '.join(blocked[:3])}",
                blocked_patterns=blocked,
                timestamp=datetime.now(timezone.utc)
            )

        return ValidationResult(
            safe=True,
            timestamp=datetime.now(timezone.utc)
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
                    timestamp=datetime.now(timezone.utc)
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
                timestamp=datetime.now(timezone.utc)
            )

        return ValidationResult(
            safe=True,
            timestamp=datetime.now(timezone.utc)
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
            timestamp=datetime.now(timezone.utc)
        )


# Global instance
guardian = GuardianAgent()
