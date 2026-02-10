"""
LexML Brasil API Client.
Integrates with the official Brazilian legal data API for searching and retrieving legislation.

LexML Brasil: https://www.lexml.gov.br/
API Documentation: https://www.lexml.gov.br/busca/SRU

Author: Delvek da S. V. de Sousa
Copyright (c) 2025 Delvek da S. V. de Sousa
"""

import asyncio
import aiohttp
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlencode, quote
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class LexMLDocument:
    """Represents a document from LexML."""
    urn: str  # Unique identifier
    title: str
    type: str  # lei, decreto, constituicao, etc.
    date: Optional[str] = None
    authority: Optional[str] = None  # federal, estadual, municipal
    jurisdiction: Optional[str] = None  # brasil, sp, rj, etc.
    text_url: Optional[str] = None
    xml_url: Optional[str] = None
    html_url: Optional[str] = None
    content: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


class LexMLClient:
    """
    Client for LexML Brasil SRU (Search/Retrieve via URL) API.

    LexML provides access to:
    - Federal, State, and Municipal legislation
    - Jurisprudence from various courts
    - Legal doctrine and articles
    """

    BASE_URL = "https://www.lexml.gov.br/busca/SRU"
    TEXT_BASE_URL = "https://www.lexml.gov.br"

    # Document type mappings
    DOC_TYPES = {
        "lei": "Legislacao",
        "decreto": "Legislacao",
        "constituicao": "Legislacao",
        "lei_complementar": "Legislacao",
        "emenda_constitucional": "Legislacao",
        "medida_provisoria": "Legislacao",
        "resolucao": "Legislacao",
        "portaria": "Legislacao",
        "jurisprudencia": "Jurisprudencia",
        "sumula": "Jurisprudencia",
        "acordao": "Jurisprudencia",
        "doutrina": "Doutrina"
    }

    def __init__(
        self,
        timeout: int = 30,
        max_records_per_request: int = 100
    ):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_records = max_records_per_request
        self.headers = {
            'User-Agent': 'LLM-Judicial-System/1.0',
            'Accept': 'application/xml,text/xml,*/*'
        }

    def _build_query(
        self,
        terms: Optional[str] = None,
        doc_type: Optional[str] = None,
        authority: str = "federal",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        jurisdiction: str = "brasil"
    ) -> str:
        """
        Build CQL query for LexML SRU API.

        CQL (Contextual Query Language) syntax for LexML:
        - urn = "urn:lex:br:federal:lei:*"
        - tipoDocumento = "Legislacao"
        - localidade = "br"
        """
        clauses = []

        # Base URN pattern for Brazilian federal legislation
        if authority == "federal":
            urn_pattern = f"urn:lex:br:federal"
        elif authority == "estadual":
            urn_pattern = f"urn:lex:br;{jurisdiction}"
        else:
            urn_pattern = "urn:lex:br"

        if doc_type:
            type_map = {
                "lei": "lei",
                "lei_ordinaria": "lei",
                "lei_complementar": "lei.complementar",
                "decreto": "decreto",
                "decreto_lei": "decreto.lei",
                "medida_provisoria": "medida.provisoria",
                "constituicao": "constituicao",
                "emenda_constitucional": "emenda.constitucional",
                "resolucao": "resolucao",
                "portaria": "portaria"
            }
            doc_suffix = type_map.get(doc_type, doc_type)
            clauses.append(f'urn = "{urn_pattern}:{doc_suffix}:*"')
        else:
            clauses.append(f'urn = "{urn_pattern}:*"')

        if terms:
            # Full-text search
            clauses.append(f'text = "{terms}"')

        if date_from:
            clauses.append(f'data >= "{date_from}"')

        if date_to:
            clauses.append(f'data <= "{date_to}"')

        return " AND ".join(clauses) if clauses else 'urn = "urn:lex:br:*"'

    async def search(
        self,
        query: Optional[str] = None,
        doc_type: Optional[str] = None,
        authority: str = "federal",
        jurisdiction: str = "brasil",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        start_record: int = 1,
        max_records: Optional[int] = None
    ) -> List[LexMLDocument]:
        """
        Search LexML for documents matching criteria.

        Args:
            query: Free-text search terms
            doc_type: Type of document (lei, decreto, etc.)
            authority: Level of authority (federal, estadual, municipal)
            jurisdiction: Jurisdiction code (brasil, sp, rj, etc.)
            date_from: Start date filter (YYYY-MM-DD)
            date_to: End date filter (YYYY-MM-DD)
            start_record: Starting record for pagination
            max_records: Maximum records to return

        Returns:
            List of LexMLDocument objects
        """
        if max_records is None:
            max_records = self.max_records

        cql_query = self._build_query(
            terms=query,
            doc_type=doc_type,
            authority=authority,
            date_from=date_from,
            date_to=date_to,
            jurisdiction=jurisdiction
        )

        params = {
            'operation': 'searchRetrieve',
            'version': '1.1',
            'query': cql_query,
            'maximumRecords': str(max_records),
            'startRecord': str(start_record),
            'recordSchema': 'lexml'
        }

        url = f"{self.BASE_URL}?{urlencode(params)}"
        logger.info(f"LexML search: {cql_query}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=self.headers,
                    timeout=self.timeout
                ) as response:
                    if response.status != 200:
                        logger.error(f"LexML API error: HTTP {response.status}")
                        return []

                    xml_content = await response.text()
                    return self._parse_response(xml_content)

        except asyncio.TimeoutError:
            logger.error("LexML API timeout")
            return []
        except Exception as e:
            logger.error(f"LexML API error: {e}")
            return []

    def _parse_response(self, xml_content: str) -> List[LexMLDocument]:
        """Parse LexML SRU XML response."""
        documents = []

        try:
            # Remove namespace prefixes for easier parsing
            xml_content = re.sub(r'xmlns[^"]*"[^"]*"', '', xml_content)
            xml_content = re.sub(r'</?[a-z]+:', '</', xml_content).replace('</', '<')

            root = ET.fromstring(xml_content)

            # Find all records
            for record in root.findall('.//record'):
                try:
                    doc = self._parse_record(record)
                    if doc:
                        documents.append(doc)
                except Exception as e:
                    logger.warning(f"Error parsing record: {e}")
                    continue

        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")

        return documents

    def _parse_record(self, record: ET.Element) -> Optional[LexMLDocument]:
        """Parse a single LexML record."""
        # Extract URN
        urn_elem = record.find('.//urn')
        urn = urn_elem.text if urn_elem is not None else None

        if not urn:
            return None

        # Extract title
        title_elem = record.find('.//titulo')
        title = title_elem.text if title_elem is not None else "Sem titulo"

        # Extract document type from URN
        # URN format: urn:lex:br:federal:lei:2002-01-10;10406
        doc_type = self._extract_type_from_urn(urn)

        # Extract date
        date_elem = record.find('.//data')
        date = date_elem.text if date_elem is not None else None

        # Extract authority
        authority = self._extract_authority_from_urn(urn)

        # Extract URLs
        text_url = None
        xml_url = None
        html_url = None

        for link in record.findall('.//link'):
            href = link.get('href', '')
            link_type = link.get('type', '')

            if 'text' in link_type or href.endswith('.txt'):
                text_url = href
            elif 'xml' in link_type or href.endswith('.xml'):
                xml_url = href
            elif 'html' in link_type or href.endswith('.html'):
                html_url = href

        # Build metadata
        metadata = {
            'urn': urn,
            'source': 'lexml'
        }

        # Add any additional fields
        for field in ['ementa', 'indexacao', 'autor']:
            elem = record.find(f'.//{field}')
            if elem is not None and elem.text:
                metadata[field] = elem.text

        return LexMLDocument(
            urn=urn,
            title=title,
            type=doc_type,
            date=date,
            authority=authority,
            text_url=text_url,
            xml_url=xml_url,
            html_url=html_url,
            metadata=metadata
        )

    def _extract_type_from_urn(self, urn: str) -> str:
        """Extract document type from URN."""
        # urn:lex:br:federal:lei:2002-01-10;10406
        parts = urn.split(':')
        if len(parts) >= 5:
            return parts[4].replace('.', '_')
        return "unknown"

    def _extract_authority_from_urn(self, urn: str) -> str:
        """Extract authority level from URN."""
        if ':federal:' in urn:
            return 'federal'
        elif ';' in urn.split(':')[2]:  # State code after br;
            return 'estadual'
        return 'federal'

    async def fetch_document_content(
        self,
        document: LexMLDocument,
        session: Optional[aiohttp.ClientSession] = None
    ) -> Optional[str]:
        """
        Fetch the full text content of a document.
        Tries text URL first, then HTML, then XML.
        """
        urls_to_try = [
            url for url in [document.text_url, document.html_url, document.xml_url]
            if url
        ]

        if not urls_to_try:
            return None

        should_close = session is None
        if session is None:
            session = aiohttp.ClientSession()

        try:
            for url in urls_to_try:
                try:
                    # Make URL absolute if needed
                    if not url.startswith('http'):
                        url = f"{self.TEXT_BASE_URL}{url}"

                    async with session.get(
                        url,
                        headers=self.headers,
                        timeout=self.timeout
                    ) as response:
                        if response.status == 200:
                            content = await response.text()
                            return self._clean_content(content, url)

                except Exception as e:
                    logger.warning(f"Error fetching {url}: {e}")
                    continue

        finally:
            if should_close:
                await session.close()

        return None

    def _clean_content(self, content: str, url: str) -> str:
        """Clean fetched content based on format."""
        if url.endswith('.xml'):
            # Extract text from XML
            try:
                root = ET.fromstring(content)
                return ' '.join(root.itertext())
            except:
                return content

        elif url.endswith('.html') or '<html' in content.lower():
            # Extract text from HTML
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            for elem in soup(['script', 'style']):
                elem.decompose()
            return soup.get_text(separator='\n')

        return content

    async def search_federal_laws(
        self,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        max_records: int = 1000
    ) -> AsyncGenerator[LexMLDocument, None]:
        """
        Search all federal laws within a date range.
        Yields documents as they are found.
        """
        date_from = f"{year_from}-01-01" if year_from else None
        date_to = f"{year_to}-12-31" if year_to else None

        start_record = 1
        total_fetched = 0

        while total_fetched < max_records:
            batch_size = min(100, max_records - total_fetched)

            results = await self.search(
                doc_type="lei",
                authority="federal",
                date_from=date_from,
                date_to=date_to,
                start_record=start_record,
                max_records=batch_size
            )

            if not results:
                break

            for doc in results:
                yield doc
                total_fetched += 1

            if len(results) < batch_size:
                break

            start_record += len(results)

    async def search_jurisprudence(
        self,
        court: str = "stf",
        terms: Optional[str] = None,
        year_from: Optional[int] = None,
        max_records: int = 100
    ) -> List[LexMLDocument]:
        """
        Search jurisprudence from specific courts.

        Args:
            court: Court code (stf, stj, tst, etc.)
            terms: Search terms
            year_from: Starting year
            max_records: Maximum results
        """
        # Build URN pattern for court
        court_urn_map = {
            'stf': 'urn:lex:br:supremo.tribunal.federal',
            'stj': 'urn:lex:br:superior.tribunal.justica',
            'tst': 'urn:lex:br:tribunal.superior.trabalho',
            'tse': 'urn:lex:br:tribunal.superior.eleitoral',
            'stm': 'urn:lex:br:superior.tribunal.militar'
        }

        # Custom search for jurisprudence
        query_parts = []

        if court.lower() in court_urn_map:
            query_parts.append(f'urn = "{court_urn_map[court.lower()]}:*"')
        else:
            query_parts.append(f'urn = "urn:lex:br:*:{court}:*"')

        query_parts.append('tipoDocumento = "Jurisprudencia"')

        if terms:
            query_parts.append(f'text = "{terms}"')

        if year_from:
            query_parts.append(f'data >= "{year_from}-01-01"')

        cql_query = " AND ".join(query_parts)

        params = {
            'operation': 'searchRetrieve',
            'version': '1.1',
            'query': cql_query,
            'maximumRecords': str(max_records),
            'recordSchema': 'lexml'
        }

        url = f"{self.BASE_URL}?{urlencode(params)}"
        logger.info(f"LexML jurisprudence search: {cql_query}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=self.headers,
                    timeout=self.timeout
                ) as response:
                    if response.status != 200:
                        return []

                    xml_content = await response.text()
                    return self._parse_response(xml_content)

        except Exception as e:
            logger.error(f"LexML jurisprudence search error: {e}")
            return []

    async def get_document_by_urn(self, urn: str) -> Optional[LexMLDocument]:
        """
        Retrieve a specific document by its URN.
        """
        params = {
            'operation': 'searchRetrieve',
            'version': '1.1',
            'query': f'urn = "{urn}"',
            'maximumRecords': '1',
            'recordSchema': 'lexml'
        }

        url = f"{self.BASE_URL}?{urlencode(params)}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=self.headers,
                    timeout=self.timeout
                ) as response:
                    if response.status != 200:
                        return None

                    xml_content = await response.text()
                    results = self._parse_response(xml_content)
                    return results[0] if results else None

        except Exception as e:
            logger.error(f"Error fetching URN {urn}: {e}")
            return None
