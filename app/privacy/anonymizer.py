"""
Anonymization pipeline for sensitive legal data.
Implements the LOPSIDED approach (Local Privacy with Selective Identification Erasure and Deidentification).

Author: Delvek da S. V. de Sousa
Copyright (c) 2025 Delvek da S. V. de Sousa
"""
from typing import Dict
import hashlib

from app.core.config import settings
from app.core.logging import get_logger
from app.privacy.ner_legal import legal_ner

logger = get_logger(__name__)

PERSONAL_TYPES = {"PER", "PERSON", "CPF", "RG", "EMAIL", "PHONE", "CASE_NUMBER"}

# Names that are part of statute names or legal doctrines, not data subjects.
LEGAL_EPONYMS = (
    "maria da penha", "carolina dieckmann", "pelé", "pele", "toulmin", "kelsen", "alexy",
    "aldir blanc", "paulo gustavo", "mariana ferrer", "henry borel", "joanna maranhão",
)
_LEGAL_CONTEXT = ("lei ", "código", "codigo", "súmula", "sumula", "tema ", "estatuto", "teoria", "princípio")


def _is_legal_eponym(text: str, ent) -> bool:
    value, etype, start, end = ent
    if etype not in ("PER", "PERSON"):
        return False
    low = value.lower()
    if any(name in low for name in LEGAL_EPONYMS):
        return True
    if value.isupper() and len(value) <= 6:  # acronyms tagged as names (e.g. "CDC", "STF")
        return True
    before = text[max(0, start - 25):start].lower()
    return any(k in before for k in _LEGAL_CONTEXT)


class Anonymizer:
    """
    Anonymizes sensitive entities in legal text.

    Strategy:
    - Person names -> [PESSOA_X]
    - Organizations -> [ORGANIZAÇÃO_X]
    - Locations -> [LOCAL_X]
    - CPF/CNPJ/RG -> [DOCUMENTO_X]
    - Case numbers -> [PROCESSO_X]
    - Emails -> [EMAIL_X]
    - Phones -> [TELEFONE_X]

    Uses deterministic hashing to maintain consistency within a document.
    """

    def __init__(self):
        self.enabled = settings.anonymizer_enabled

        # Mapping of entity types to anonymized labels
        self.type_labels = {
            "PER": "PESSOA",
            "PERSON": "PESSOA",
            "ORG": "ORGANIZAÇÃO",
            "LOC": "LOCAL",
            "CPF": "CPF",
            "CNPJ": "CNPJ",
            "RG": "RG",
            "CASE_NUMBER": "PROCESSO",
            "EMAIL": "EMAIL",
            "PHONE": "TELEFONE"
        }

        # Counter for each entity type (per document)
        self.entity_counters: Dict[str, Dict[str, int]] = {}

    def anonymize(self, text: str, doc_id: str = "default") -> str:
        """
        Anonymize sensitive entities in text.

        Args:
            text: Input text
            doc_id: Document identifier (for consistent anonymization)

        Returns:
            Anonymized text
        """
        if not self.enabled:
            return text

        logger.debug("anonymizing_text", doc_id=doc_id, length=len(text))

        # Initialize counter for this document
        if doc_id not in self.entity_counters:
            self.entity_counters[doc_id] = {}

        # Extract entities, keeping only PERSONAL data (LGPD art. 5, I: data about an
        # identified or identifiable natural person). Organisations and places are
        # not pseudonymised: replacing "STF", "ANVISA", "União" or "Lei Maria da Penha"
        # would destroy the legal content of the query, and they are not personal data.
        entities = [
            e for e in legal_ner.extract_entities(text)
            if e[1] in PERSONAL_TYPES and not _is_legal_eponym(text, e)
        ]

        if not entities:
            logger.debug("no_entities_found", doc_id=doc_id)
            return text

        # Sort entities by position (reverse) to replace from end to start
        # This prevents position shifts during replacement
        entities_sorted = sorted(entities, key=lambda x: x[2], reverse=True)

        # Replace entities
        anonymized_text = text
        for entity_text, entity_type, start, end in entities_sorted:
            replacement = self._get_replacement(
                entity_text,
                entity_type,
                doc_id
            )

            anonymized_text = (
                anonymized_text[:start] +
                replacement +
                anonymized_text[end:]
            )

        logger.info(
            "anonymization_complete",
            doc_id=doc_id,
            entities_anonymized=len(entities)
        )

        return anonymized_text

    def _get_replacement(
        self,
        entity_text: str,
        entity_type: str,
        doc_id: str
    ) -> str:
        """
        Get anonymized replacement for an entity.

        Uses deterministic hashing to ensure the same entity
        gets the same replacement within a document.
        """
        # Get label for this entity type
        label = self.type_labels.get(entity_type, "ENTIDADE")

        # Create hash of entity text for deterministic mapping
        entity_hash = hashlib.md5(
            f"{doc_id}:{entity_text}".encode()
        ).hexdigest()[:8]

        # Get or create counter for this entity
        counter_key = f"{label}_{entity_hash}"

        if counter_key not in self.entity_counters[doc_id]:
            # Assign new counter
            type_count = sum(
                1 for k in self.entity_counters[doc_id].keys()
                if k.startswith(label)
            ) + 1
            self.entity_counters[doc_id][counter_key] = type_count

        counter = self.entity_counters[doc_id][counter_key]

        return f"[{label}_{counter}]"

    def reset_counters(self, doc_id: str = None) -> None:
        """
        Reset entity counters.

        Args:
            doc_id: Specific document ID, or None to reset all
        """
        if doc_id:
            if doc_id in self.entity_counters:
                del self.entity_counters[doc_id]
        else:
            self.entity_counters.clear()


# Global instance
anonymizer = Anonymizer()


def anonymize_text(text: str, doc_id: str = "default") -> str:
    """
    Anonymize text (convenience function).

    Args:
        text: Input text
        doc_id: Document identifier

    Returns:
        Anonymized text
    """
    return anonymizer.anonymize(text, doc_id)
