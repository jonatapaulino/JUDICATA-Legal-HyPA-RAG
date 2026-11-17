"""
Normative authority of retrieved sources (Brazilian law).

Brazilian procedure binds judges to certain precedents: súmulas vinculantes
(CF art. 103-A), theses fixed in repercussão geral and in repetitive appeals,
and the other items of CPC art. 927. A decision that invokes a precedent without
identifying its determining grounds, or that does not follow one invoked by a
party without a distinction/overruling, is considered unreasoned (CPC art. 489,
§1º, V and VI). The Rule Matcher therefore must not treat all sources alike.

This module assigns each retrieved document an authority tier and a label that
is shown to the LLM, and exposes the set of revoked statutes used for the
validity check.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Iterable, List, Set, Tuple

from app.models.internal import Document

# Lower tier = stronger authority
TIERS = {
    "SUMULA_VINCULANTE": (1, "PRECEDENTE VINCULANTE (CF art. 103-A; CPC art. 927, II)"),
    "TESE_RG": (1, "TESE DE REPERCUSSÃO GERAL - observância obrigatória (CPC art. 927, III)"),
    "TESE_REPETITIVO": (1, "TESE DE RECURSO REPETITIVO - observância obrigatória (CPC art. 927, III)"),
    "CONSTITUICAO": (2, "CONSTITUIÇÃO FEDERAL"),
    "LEI": (3, "LEGISLAÇÃO FEDERAL"),
    "SUMULA": (4, "SÚMULA (orientação de tribunal superior; CPC art. 927, IV)"),
    "ORIENTACAO_ADMIN": (5, "ORIENTAÇÃO ADMINISTRATIVA/INSTITUCIONAL (não vinculante)"),
    "OUTRO": (6, "OUTRA FONTE"),
}


def source_kind(doc: Document) -> str:
    md = doc.metadata or {}
    dtype = (md.get("type") or "").lower()
    if dtype == "sumula":
        st = (md.get("sumula_type") or "").lower()
        return "SUMULA_VINCULANTE" if "vinc" in st else "SUMULA"
    if dtype == "sumula_vinculante":
        return "SUMULA_VINCULANTE"
    if dtype == "tese_rg":
        return "TESE_RG"
    if dtype == "tese_repetitivo":
        return "TESE_REPETITIVO"
    if dtype == "orientacao":
        return "ORIENTACAO_ADMIN"
    if dtype == "legislation":
        return "CONSTITUICAO" if md.get("law_type") == "CF" or md.get("law_id") == "CF88" else "LEI"
    return "OUTRO"


def authority(doc: Document) -> Tuple[int, str]:
    return TIERS[source_kind(doc)]


def rank_by_authority(documents: Iterable[Document]) -> List[Document]:
    """Stable sort: stronger authority first, retrieval score as tie-breaker."""
    docs = list(documents)
    return sorted(docs, key=lambda d: (authority(d)[0], -(d.score or 0.0)))


def label(doc: Document) -> str:
    md = doc.metadata or {}
    tier, text = authority(doc)
    ref = md.get("citation") or md.get("law_name") or ""
    if md.get("article"):
        ref = f"{ref}, Art. {md.get('article')}"
    if md.get("type") in ("sumula", "sumula_vinculante", "tese_rg", "tese_repetitivo"):
        ref = f"{md.get('court', '')} n. {md.get('number', '')}".strip()
    return f"[{text}] {ref}".strip()


@lru_cache(maxsize=1)
def revoked_laws() -> Set[str]:
    """Statute numbers marked as revoked in the legislation catalog."""
    from app.ingestion.planalto_scraper import BRAZILIAN_LEGISLATION_CATALOG
    from app.reasoning.citations import _find_laws

    out: Set[str] = set()
    for meta in BRAZILIAN_LEGISLATION_CATALOG:
        if (meta.status or "").lower() == "revogada":
            for (_, _, num) in _find_laws(meta.name):
                out.add(num)
    return out


def is_revoked(doc: Document) -> bool:
    md = doc.metadata or {}
    return (md.get("status") or "").lower() == "revogada"
