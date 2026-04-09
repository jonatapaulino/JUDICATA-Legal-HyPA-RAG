"""
Brazilian Legislation Parser.
Parses raw legal text into structured chunks (Articles, Paragraphs) following LC 95/98 standards.

"""
import re
from typing import List, Dict, Optional
from pydantic import BaseModel

class LegalChunk(BaseModel):
    """Represents a structured chunk of legislation."""
    law_name: str
    law_type: str  # CF, LEI, DECRETO, CODIGO
    article_number: str
    content: str
    full_text: str
    hierarchy: List[str] = []  # [LIVRO I, TÍTULO II, CAPÍTULO I]

class LegislationParser:
    """
    Parses Brazilian legal text into semantic chunks.
    Focuses on extracting Articles as the primary unit of retrieval.
    """

    # Regex patterns for Brazilian legislative structure
    PATTERNS = {
        "article": r"^\s*Art\.\s*(\d+[º°]?[-A-Za-z]*)\.?",
        "paragraph": r"^\s*§\s*(\d+[º°]?)\.?",
        "single_paragraph": r"^\s*Parágrafo\s+único\.?",
        "item": r"^\s*([IVXLCDM]+)\s*[-–]",
        "structure": r"^\s*(LIVRO|TÍTULO|CAPÍTULO|SEÇÃO|SUBSEÇÃO)\s+([IVXLCDM]+|ÚNICO)"
    }

    def parse_text(self, text: str, law_name: str, law_type: str) -> List[LegalChunk]:
        """
        Parse raw text into a list of LegalChunks.
        """
        chunks = []
        lines = text.split('\n')
        
        current_hierarchy = []
        current_article = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for structural headers (LIVRO, TÍTULO, etc.)
            if re.match(self.PATTERNS["structure"], line, re.IGNORECASE):
                # Update hierarchy logic could be more complex, simplified here
                current_hierarchy = [h for h in current_hierarchy if not self._is_lower_hierarchy(h, line)]
                current_hierarchy.append(line)
                continue

            # Check for Article start
            art_match = re.match(self.PATTERNS["article"], line)
            if art_match:
                # Save previous article if exists
                if current_article:
                    self._finalize_chunk(chunks, current_article, current_content, law_name, law_type, current_hierarchy)
                
                # Start new article
                current_article = art_match.group(1)
                current_content = [line]
                continue

            # If inside an article, append content
            if current_article:
                current_content.append(line)

        # Save last article
        if current_article:
            self._finalize_chunk(chunks, current_article, current_content, law_name, law_type, current_hierarchy)

        return chunks

    def _finalize_chunk(
        self, 
        chunks: List[LegalChunk], 
        art_num: str, 
        content: List[str], 
        law_name: str, 
        law_type: str,
        hierarchy: List[str]
    ):
        """Create and append a LegalChunk."""
        full_text = " ".join(content)
        
        # Clean up text
        full_text = re.sub(r'\s+', ' ', full_text)
        
        chunk = LegalChunk(
            law_name=law_name,
            law_type=law_type,
            article_number=art_num,
            content=full_text,
            full_text=f"{law_name} - Art. {art_num}: {full_text}",
            hierarchy=list(hierarchy)
        )
        chunks.append(chunk)

    def _is_lower_hierarchy(self, current: str, new: str) -> bool:
        """Helper to manage hierarchy stack (simplified)."""
        order = ["LIVRO", "TÍTULO", "CAPÍTULO", "SEÇÃO", "SUBSEÇÃO"]
        
        curr_type = current.split()[0].upper()
        new_type = new.split()[0].upper()
        
        try:
            return order.index(new_type) <= order.index(curr_type)
        except ValueError:
            return False

legislation_parser = LegislationParser()
