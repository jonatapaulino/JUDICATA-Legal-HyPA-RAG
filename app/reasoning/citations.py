"""
Legal citation extraction, normalisation and verification.

Used by (i) the Toulmin Backing verifier and the evidence-based Qualifier, and
(ii) the evaluation metrics (citation grounding / validity / recall). Everything
here is deterministic so that the metrics reported in the paper can be recomputed
from the stored outputs.

Normalised citation keys:
    ART:<law>:<n>     article n of a law (law may be "?" when not stated)
    LAW:<law>         a statute / code as a whole
    SUM:<court>:<n>   ordinary súmula (court may be "?")
    SV:<n>            súmula vinculante (STF)
    TEMA:<court>:<n>  repercussão geral / repetitivo theme (court may be "?")

<law> is the bare statute number without dots (e.g. 8078 for Lei 8.078/1990,
"CF" for the Constitution).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set

# Codes and well-known statutes referred to by acronym -> statute number.
CODE_ALIASES: Dict[str, str] = {
    "CF": "CF", "CF/88": "CF", "CF/1988": "CF", "CRFB": "CF", "CONSTITUICAO FEDERAL": "CF",
    "CC": "10406", "CC/2002": "10406", "CODIGO CIVIL": "10406",
    "CPC": "13105", "CPC/2015": "13105", "CODIGO DE PROCESSO CIVIL": "13105",
    "CP": "2848", "CODIGO PENAL": "2848",
    "CPP": "3689", "CODIGO DE PROCESSO PENAL": "3689",
    "CDC": "8078", "CODIGO DE DEFESA DO CONSUMIDOR": "8078",
    "CLT": "5452",
    "CTN": "5172", "CODIGO TRIBUTARIO NACIONAL": "5172",
    "ECA": "8069", "ESTATUTO DA CRIANCA E DO ADOLESCENTE": "8069",
    "LGPD": "13709",
    "LEI ORGANICA DA SAUDE": "8080",
}


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def _norm_law_number(raw: str) -> str:
    return raw.replace(".", "").lstrip("0") or "0"


_ALIAS_RE = "|".join(
    sorted((re.escape(k) for k in CODE_ALIASES), key=len, reverse=True)
)
_LAW_RE = re.compile(
    r"\b(?:lei|decreto[- ]lei|lei complementar|lc|medida provis[oó]ria|mp)\s*"
    r"(?:n[º°o.]*\s*)?(\d{1,2}\.?\d{3})(?:\s*/\s*(\d{2,4}))?",
    re.IGNORECASE,
)
_ART_RE = re.compile(
    r"\bart(?:igo)?s?\.?\s*(\d\.\d{3}|\d{1,4})\s*[º°o]?(?:\s*-\s*([a-z])\b)?",
    re.IGNORECASE,
)


def _art_id(num: str, suffix: Optional[str] = None) -> str:
    n = num.replace(".", "").lstrip("0") or "0"
    return f"{n}-{suffix.upper()}" if suffix else n
_SV_RE = re.compile(
    r"\bs[uú]mula\s+vinculante\s*(?:n[º°o.]*\s*)?(\d{1,3})|\bSV\s*(\d{1,3})\b",
    re.IGNORECASE,
)
_SUM_RE = re.compile(
    r"\bs[uú]mula\s+(?!vinculante)(?:n[º°o.]*\s*)?(\d{1,4})(?:\s*(?:do|da|/)\s*(STF|STJ|TST))?",
    re.IGNORECASE,
)
_TEMA_RE = re.compile(
    r"\btema\s*(?:n[º°o.]*\s*)?(\d{1,4})(?:\s*(?:do|da|/)\s*(STF|STJ))?",
    re.IGNORECASE,
)
# A law / code mentioned within this many characters after an article is attached to it
_ATTACH_WINDOW = 60


@dataclass
class Citation:
    key: str
    kind: str
    surface: str
    law: Optional[str] = None
    number: Optional[str] = None
    court: Optional[str] = None


def _find_laws(text: str) -> List[tuple]:
    """Return (start, end, law_number) for every statute mention in text."""
    out = []
    for m in _LAW_RE.finditer(text):
        out.append((m.start(), m.end(), _norm_law_number(m.group(1))))
    up = _strip_accents(text).upper()
    for m in re.finditer(r"(?<![A-Z])(" + _ALIAS_RE + r")(?![A-Z])", up):
        out.append((m.start(), m.end(), CODE_ALIASES[m.group(1)]))
    return sorted(out)


def extract_citations(text: str) -> List[Citation]:
    """Extract normalised legal citations from free text (Portuguese)."""
    if not text:
        return []
    cites: List[Citation] = []
    laws = _find_laws(text)
    used_law_spans: Set[int] = set()

    for m in _ART_RE.finditer(text):
        n = _art_id(m.group(1), m.group(2))
        law = "?"
        for (s, e, num) in laws:
            if m.end() <= s <= m.end() + _ATTACH_WINDOW:
                law = num
                used_law_spans.add(s)
                break
        cites.append(Citation(f"ART:{law}:{n}", "article", m.group(0), law=law, number=n))

    for (s, e, num) in laws:
        cites.append(Citation(f"LAW:{num}", "law", text[s:e], law=num))

    for m in _SV_RE.finditer(text):
        n = (m.group(1) or m.group(2)).lstrip("0")
        cites.append(Citation(f"SV:{n}", "sv", m.group(0), number=n, court="STF"))

    for m in _SUM_RE.finditer(text):
        n = m.group(1).lstrip("0")
        court = (m.group(2) or "?").upper()
        cites.append(Citation(f"SUM:{court}:{n}", "sumula", m.group(0), number=n, court=court))

    for m in _TEMA_RE.finditer(text):
        n = m.group(1).lstrip("0")
        court = (m.group(2) or "?").upper()
        cites.append(Citation(f"TEMA:{court}:{n}", "tema", m.group(0), number=n, court=court))

    # de-duplicate by key, keep first occurrence
    seen, uniq = set(), []
    for c in cites:
        if c.key not in seen:
            seen.add(c.key)
            uniq.append(c)
    return uniq


def specific_citations(cites: Iterable[Citation]) -> List[Citation]:
    """Citations that point to a specific provision (articles, súmulas, SV, temas)."""
    return [c for c in cites if c.kind != "law"]


def _doc_keys(doc) -> Set[str]:
    """All citation keys a retrieved document can support."""
    md = getattr(doc, "metadata", None) or {}
    content = getattr(doc, "content", "") or ""
    keys: Set[str] = set()
    law_num = None
    law_name = md.get("law_name") or ""
    if md.get("law_id") == "CF88" or "Constitui" in law_name:
        law_num = "CF"
    else:
        found = _find_laws(law_name)
        if found:
            law_num = found[0][2]
    if law_num:
        keys.add(f"LAW:{law_num}")
        art = str(md.get("article") or "").strip()
        m = re.match(r"(\d\.\d{3}|\d+)(?:\s*-\s*([A-Za-z])\b)?", art)
        if m:
            keys.add(f"ART:{law_num}:{_art_id(m.group(1), m.group(2))}")
    dtype = (md.get("type") or "").lower()
    num = str(md.get("number") or md.get("sumula_number") or "").lstrip("0")
    court = (md.get("court") or md.get("tribunal") or "").upper()
    if dtype in ("sumula_vinculante",) and num:
        keys.add(f"SV:{num}")
    elif dtype in ("sumula",) and num:
        if md.get("binding") or "VINC" in (md.get("sumula_type") or md.get("subtype") or "").upper():
            keys.add(f"SV:{num}")
        keys.add(f"SUM:{court or '?'}:{num}")
    if dtype in ("tese_rg", "tese_repetitivo") and num:
        keys.add(f"TEMA:{court or '?'}:{num}")
    # Content-level evidence (e.g. a guide quoting several provisions)
    for c in extract_citations(content[:4000]):
        keys.add(c.key)
    return keys


def _match(key: str, supported: Set[str]) -> bool:
    if key in supported:
        return True
    kind, *rest = key.split(":")
    if kind == "ART" and rest[0] == "?":
        return any(k.startswith("ART:") and k.endswith(f":{rest[1]}") for k in supported)
    if kind in ("SUM", "TEMA") and rest[0] == "?":
        return any(k.startswith(f"{kind}:") and k.endswith(f":{rest[1]}") for k in supported)
    if kind in ("SUM", "TEMA"):
        return f"{kind}:?:{rest[1]}" in supported
    return False


@dataclass
class CitationCheck:
    cited: List[str] = field(default_factory=list)
    grounded: List[str] = field(default_factory=list)
    ungrounded: List[str] = field(default_factory=list)
    revoked: List[str] = field(default_factory=list)

    @property
    def n_cited(self) -> int:
        return len(self.cited)

    @property
    def grounding_rate(self) -> Optional[float]:
        return len(self.grounded) / len(self.cited) if self.cited else None

    def to_dict(self) -> Dict:
        return {
            "cited": self.cited,
            "grounded": self.grounded,
            "ungrounded": self.ungrounded,
            "revoked": self.revoked,
            "grounding_rate": self.grounding_rate,
        }


def verify_citations(text: str, documents: Iterable, revoked_laws: Optional[Set[str]] = None) -> CitationCheck:
    """
    Check every specific citation in `text` against the retrieved `documents`
    (grounding) and against the set of revoked statutes (validity).
    """
    revoked_laws = revoked_laws or set()
    supported: Set[str] = set()
    for d in documents or []:
        supported |= _doc_keys(d)
    chk = CitationCheck()
    for c in extract_citations(text):
        if c.law and c.law in revoked_laws:
            chk.revoked.append(c.key)
        if c.kind == "law":
            continue
        chk.cited.append(c.key)
        (chk.grounded if _match(c.key, supported) else chk.ungrounded).append(c.key)
    return chk
