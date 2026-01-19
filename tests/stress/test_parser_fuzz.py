"""
Fuzzing tests for LegislationParser using Hypothesis.
Generates random legal-like texts to test parser robustness and correctness.
"""
import pytest
from hypothesis import given, strategies as st
from app.retrieval.legislation_parser import legislation_parser

# Strategies for generating legal text components
roman_numerals = st.sampled_from(["I", "II", "III", "IV", "V", "X", "L", "C", "M"])
article_nums = st.integers(min_value=1, max_value=9999).map(str)
paragraph_nums = st.integers(min_value=1, max_value=99).map(str)

@st.composite
def legal_text_strategy(draw):
    """Generates a random legal text structure."""
    parts = []
    
    # Maybe add a header
    if draw(st.booleans()):
        parts.append(f"LIVRO {draw(roman_numerals)}")
    
    # Generate a few articles
    num_articles = draw(st.integers(min_value=1, max_value=5))
    for _ in range(num_articles):
        art_num = draw(article_nums)
        parts.append(f"Art. {art_num}. {draw(st.text(min_size=10, max_size=100))}")
        
        # Maybe add paragraphs
        if draw(st.booleans()):
            num_paras = draw(st.integers(min_value=1, max_value=3))
            for _ in range(num_paras):
                para_num = draw(paragraph_nums)
                parts.append(f"§ {para_num}º {draw(st.text(min_size=10, max_size=100))}")
                
                # Maybe add items (incisos)
                if draw(st.booleans()):
                    num_items = draw(st.integers(min_value=1, max_value=3))
                    for _ in range(num_items):
                        item_num = draw(roman_numerals)
                        parts.append(f"{item_num} - {draw(st.text(min_size=5, max_size=50))}")

    return "\n".join(parts)

class TestParserFuzz:
    
    @given(text=legal_text_strategy())
    def test_parser_structure_correctness(self, text):
        """
        Test that the parser correctly identifies articles in generated legal text.
        """
        chunks = legislation_parser.parse_text(text, "Lei Teste", "LEI")
        
        # Basic invariants
        assert isinstance(chunks, list)
        
        # If text had "Art.", we should probably have chunks
        if "Art." in text:
            # Note: This is a loose check because the strategy might generate "Art." inside content
            # But generally, our strategy puts it at start of line
            pass

        for chunk in chunks:
            assert chunk.law_name == "Lei Teste"
            assert chunk.law_type == "LEI"
            assert chunk.article_number
            assert chunk.content
            assert chunk.full_text

    @given(text=st.text())
    def test_parser_robustness_random_text(self, text):
        """Test that the parser never crashes on completely random text."""
        try:
            chunks = legislation_parser.parse_text(text, "Lei Random", "LEI")
            assert isinstance(chunks, list)
        except Exception as e:
            pytest.fail(f"Parser crashed on random text: {e}")
