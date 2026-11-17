"""Tests for citation extraction/verification and the evidence-based qualifier."""
from app.models.internal import Document
from app.models.responses import Qualifier
from app.reasoning.citations import extract_citations, verify_citations
from app.reasoning.toulmin import qualify


def keys(text):
    return [c.key for c in extract_citations(text)]


def test_article_with_law_and_suffix():
    k = keys("Art. 19-Q da Lei 8.080/1990 e art. 1.723 do CC")
    assert "ART:8080:19-Q" in k
    assert "ART:10406:1723" in k


def test_precedents():
    k = keys("Súmula Vinculante 61, Súmula 297 do STJ e Tema 1234 do STF")
    assert {"SV:61", "SUM:STJ:297", "TEMA:STF:1234"} <= set(k)


def test_grounding_and_revoked():
    docs = [Document(id="1", content="Art. 18. ...", metadata={
        "type": "legislation", "law_name": "CDC (Lei 8.078/1990)", "article": "18"})]
    chk = verify_citations("Art. 18 do CDC; art. 75 da Lei 8.666/93", docs, {"8666"})
    assert chk.grounded == ["ART:8078:18"]
    assert "ART:8666:75" in chk.ungrounded
    assert chk.revoked


def test_qualifier_rules():
    docs = [Document(id="1", content="Art. 18.", metadata={
        "type": "legislation", "law_name": "CDC (Lei 8.078/1990)", "article": "18"})]
    ok = verify_citations("Art. 18 do CDC", docs)
    assert qualify(ok, True, False)[0] == Qualifier.PROVAVEL
    assert qualify(ok, True, True)[0] == Qualifier.CERTO
    assert qualify(ok, False, True)[0] == Qualifier.INCERTO
    none = verify_citations("sem citações", docs)
    assert qualify(none, True, True)[0] == Qualifier.INCERTO
