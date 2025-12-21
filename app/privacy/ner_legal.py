"""
Legal Named Entity Recognition for Portuguese.
Identifies sensitive entities in legal text for anonymization.

Author: Delvek da S. V. de Sousa
Copyright (c) 2025 Delvek da S. V. de Sousa
"""
from typing import List, Tuple, Optional
import re
import spacy

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LegalNER:
    """
    Named Entity Recognition specialized for legal documents in Portuguese.

    Identifies:
    - Person names (PER)
    - Organizations (ORG)
    - Locations (LOC)
    - Legal identifiers (CPF, CNPJ, RG, etc.)
    - Case numbers
    """

    def __init__(self):
        self.nlp: Optional[spacy.Language] = None
        self._load_model()

    def _load_model(self) -> None:
        """Load spaCy model for Portuguese."""
        try:
            logger.info("loading_ner_model", model=settings.ner_model)
            self.nlp = spacy.load(settings.ner_model)
            logger.info("ner_model_loaded")
        except Exception as e:
            logger.error("ner_model_load_failed", error=str(e))
            # Continue without NER - will fall back to regex only
            self.nlp = None

    def extract_entities(self, text: str) -> List[Tuple[str, str, int, int]]:
        """
        Extract named entities from text.

        Args:
            text: Input text

        Returns:
            List of tuples: (entity_text, entity_type, start_pos, end_pos)
        """
        entities = []

        # Extract using spaCy
        if self.nlp:
            doc = self.nlp(text)
            for ent in doc.ents:
                if ent.label_ in {"PER", "PERSON", "ORG", "LOC"}:
                    entities.append((
                        ent.text,
                        ent.label_,
                        ent.start_char,
                        ent.end_char
                    ))

        # Extract using regex patterns (more reliable for some patterns)
        regex_entities = self._extract_with_regex(text)
        entities.extend(regex_entities)

        # Remove duplicates (keep longer matches)
        entities = self._deduplicate_entities(entities)

        logger.debug("entities_extracted", count=len(entities))

        return entities

    def _extract_with_regex(self, text: str) -> List[Tuple[str, str, int, int]]:
        """Extract entities using regex patterns."""
        entities = []

        # CPF pattern: 000.000.000-00
        cpf_pattern = r'\d{3}\.\d{3}\.\d{3}-\d{2}'
        for match in re.finditer(cpf_pattern, text):
            entities.append((
                match.group(),
                "CPF",
                match.start(),
                match.end()
            ))

        # CNPJ pattern: 00.000.000/0000-00
        cnpj_pattern = r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}'
        for match in re.finditer(cnpj_pattern, text):
            entities.append((
                match.group(),
                "CNPJ",
                match.start(),
                match.end()
            ))

        # RG pattern (simplified): 00.000.000-0
        rg_pattern = r'\d{2}\.\d{3}\.\d{3}-\d{1}'
        for match in re.finditer(rg_pattern, text):
            entities.append((
                match.group(),
                "RG",
                match.start(),
                match.end()
            ))

        # Case number pattern: 0000000-00.0000.0.00.0000
        case_pattern = r'\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}'
        for match in re.finditer(case_pattern, text):
            entities.append((
                match.group(),
                "CASE_NUMBER",
                match.start(),
                match.end()
            ))

        # Email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        for match in re.finditer(email_pattern, text):
            entities.append((
                match.group(),
                "EMAIL",
                match.start(),
                match.end()
            ))

        # Phone numbers (Brazilian format)
        phone_pattern = r'\(?\d{2}\)?\s?\d{4,5}-?\d{4}'
        for match in re.finditer(phone_pattern, text):
            entities.append((
                match.group(),
                "PHONE",
                match.start(),
                match.end()
            ))

        return entities

    def _deduplicate_entities(
        self,
        entities: List[Tuple[str, str, int, int]]
    ) -> List[Tuple[str, str, int, int]]:
        """Remove overlapping entities, keeping longer ones."""
        if not entities:
            return []

        # Sort by start position, then by length (descending)
        sorted_entities = sorted(
            entities,
            key=lambda x: (x[2], -(x[3] - x[2]))
        )

        deduplicated = []
        last_end = -1

        for entity in sorted_entities:
            text, ent_type, start, end = entity

            # Skip if overlaps with previous entity
            if start < last_end:
                continue

            deduplicated.append(entity)
            last_end = end

        return deduplicated


# Global instance
legal_ner = LegalNER()
