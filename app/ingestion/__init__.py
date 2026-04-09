"""
Ingestion module for Brazilian legal data.
Includes scrapers for Planalto, LexML API, STF/STJ jurisprudence, and sumulas.

"""

from .planalto_scraper import PlanaltoScraper
from .lexml_client import LexMLClient
from .stf_stj_client import STFSTJClient
from .sumulas_scraper import SumulasScraper
from .unified_ingestor import UnifiedLegalIngestor

__all__ = [
    "PlanaltoScraper",
    "LexMLClient",
    "STFSTJClient",
    "SumulasScraper",
    "UnifiedLegalIngestor"
]
