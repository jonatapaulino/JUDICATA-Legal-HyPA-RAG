"""Regression tests for Planalto page extraction defects found during the revision."""
from app.ingestion.planalto_scraper import PlanaltoScraper, decode_planalto
from app.retrieval.legislation_parser import legislation_parser


def test_decode_utf16_page():
    assert decode_planalto("Art. 1º ação".encode("utf-16")) == "Art. 1º ação"
    assert decode_planalto("Art. 1º ação".encode("cp1252")) == "Art. 1º ação"


def test_article_number_split_across_inline_tags():
    html = "<p><a>Art.</a> <b>1</b>º Esta Lei cria</p><p><span>Art. 2</span><span>º</span> Toda mulher</p>"
    text = PlanaltoScraper()._clean_html(html, "LEI")
    arts = [c.article_number for c in legislation_parser.parse_text(text, "L", "LEI")]
    assert arts == ["1º", "2º"]


def test_malformed_nested_body_keeps_articles():
    html = "<html><body><p>Preâmbulo</p></body></html><p>Art. 5º Todos são iguais</p><p>Art. 6º São direitos</p>"
    text = PlanaltoScraper()._clean_html(html, "CF")
    assert "Art. 5º" in text and "Art. 6º" in text


def test_strike_through_removed():
    html = "<p>Art. 1º Texto vigente</p><p><strike>Art. 2º Texto revogado</strike></p>"
    text = PlanaltoScraper()._clean_html(html, "LEI")
    assert "revogado" not in text
