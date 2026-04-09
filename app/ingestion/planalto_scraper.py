"""
Planalto.gov.br Scraper for Brazilian Legislation.
Downloads and parses legal texts from the official government portal.

"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class LegislationMetadata:
    """Metadata for a piece of legislation."""
    id: str
    name: str
    type: str  # CF, LEI, DECRETO_LEI, CODIGO, LC, MP, EC
    url: str
    date: Optional[str] = None
    status: str = "vigente"  # vigente, revogada, parcialmente_revogada
    category: str = "geral"  # constitucional, civil, penal, trabalhista, tributario, etc.
    tags: List[str] = field(default_factory=list)


# Complete catalog of Brazilian legislation
BRAZILIAN_LEGISLATION_CATALOG: List[LegislationMetadata] = [
    # === CONSTITUICAO ===
    LegislationMetadata(
        id="CF88",
        name="Constituicao Federal de 1988",
        type="CF",
        url="http://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
        date="1988-10-05",
        category="constitucional",
        tags=["constituicao", "direitos_fundamentais", "organizacao_estado"]
    ),

    # === CODIGOS PRINCIPAIS ===
    LegislationMetadata(
        id="CC2002",
        name="Codigo Civil (Lei 10.406/2002)",
        type="CODIGO",
        url="http://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm",
        date="2002-01-10",
        category="civil",
        tags=["codigo_civil", "obrigacoes", "contratos", "familia", "sucessoes"]
    ),
    LegislationMetadata(
        id="CPC2015",
        name="Codigo de Processo Civil (Lei 13.105/2015)",
        type="CODIGO",
        url="http://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105.htm",
        date="2015-03-16",
        category="processual_civil",
        tags=["processo_civil", "recursos", "execucao", "tutela_provisoria"]
    ),
    LegislationMetadata(
        id="CP",
        name="Codigo Penal (Decreto-Lei 2.848/1940)",
        type="CODIGO",
        url="http://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm",
        date="1940-12-07",
        category="penal",
        tags=["codigo_penal", "crimes", "penas", "dosimetria"]
    ),
    LegislationMetadata(
        id="CPP",
        name="Codigo de Processo Penal (Decreto-Lei 3.689/1941)",
        type="CODIGO",
        url="http://www.planalto.gov.br/ccivil_03/decreto-lei/del3689compilado.htm",
        date="1941-10-03",
        category="processual_penal",
        tags=["processo_penal", "inquerito", "acao_penal", "prisao"]
    ),
    LegislationMetadata(
        id="CLT",
        name="Consolidacao das Leis do Trabalho (Decreto-Lei 5.452/1943)",
        type="CODIGO",
        url="http://www.planalto.gov.br/ccivil_03/decreto-lei/del5452.htm",
        date="1943-05-01",
        category="trabalhista",
        tags=["trabalho", "emprego", "sindicato", "ferias", "rescisao"]
    ),
    LegislationMetadata(
        id="CTN",
        name="Codigo Tributario Nacional (Lei 5.172/1966)",
        type="CODIGO",
        url="http://www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm",
        date="1966-10-25",
        category="tributario",
        tags=["tributos", "impostos", "obrigacao_tributaria", "credito_tributario"]
    ),
    LegislationMetadata(
        id="CDC",
        name="Codigo de Defesa do Consumidor (Lei 8.078/1990)",
        type="CODIGO",
        url="http://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm",
        date="1990-09-11",
        category="consumidor",
        tags=["consumidor", "fornecedor", "responsabilidade", "praticas_abusivas"]
    ),
    LegislationMetadata(
        id="CTB",
        name="Codigo de Transito Brasileiro (Lei 9.503/1997)",
        type="CODIGO",
        url="http://www.planalto.gov.br/ccivil_03/leis/l9503compilado.htm",
        date="1997-09-23",
        category="transito",
        tags=["transito", "infracoes", "habilitacao", "veiculos"]
    ),
    LegislationMetadata(
        id="CBA",
        name="Codigo Brasileiro de Aeronautica (Lei 7.565/1986)",
        type="CODIGO",
        url="http://www.planalto.gov.br/ccivil_03/leis/l7565compilado.htm",
        date="1986-12-19",
        category="aeronautico",
        tags=["aviacao", "aeronautica", "transporte_aereo"]
    ),
    LegislationMetadata(
        id="CF_MILITAR",
        name="Codigo Penal Militar (Decreto-Lei 1.001/1969)",
        type="CODIGO",
        url="http://www.planalto.gov.br/ccivil_03/decreto-lei/del1001.htm",
        date="1969-10-21",
        category="militar",
        tags=["militar", "crime_militar", "justica_militar"]
    ),
    LegislationMetadata(
        id="CPPM",
        name="Codigo de Processo Penal Militar (Decreto-Lei 1.002/1969)",
        type="CODIGO",
        url="http://www.planalto.gov.br/ccivil_03/decreto-lei/del1002.htm",
        date="1969-10-21",
        category="militar",
        tags=["processo_penal_militar", "justica_militar"]
    ),
    LegislationMetadata(
        id="CODIGO_ELEITORAL",
        name="Codigo Eleitoral (Lei 4.737/1965)",
        type="CODIGO",
        url="http://www.planalto.gov.br/ccivil_03/leis/l4737compilado.htm",
        date="1965-07-15",
        category="eleitoral",
        tags=["eleicoes", "partidos", "voto", "propaganda_eleitoral"]
    ),

    # === ESTATUTOS ===
    LegislationMetadata(
        id="ECA",
        name="Estatuto da Crianca e do Adolescente (Lei 8.069/1990)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l8069.htm",
        date="1990-07-13",
        category="infancia",
        tags=["crianca", "adolescente", "menor", "ato_infracional", "adocao"]
    ),
    LegislationMetadata(
        id="ESTATUTO_IDOSO",
        name="Estatuto do Idoso (Lei 10.741/2003)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/2003/l10.741.htm",
        date="2003-10-01",
        category="idoso",
        tags=["idoso", "terceira_idade", "direitos_idoso"]
    ),
    LegislationMetadata(
        id="ESTATUTO_PCD",
        name="Estatuto da Pessoa com Deficiencia (Lei 13.146/2015)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13146.htm",
        date="2015-07-06",
        category="pcd",
        tags=["deficiencia", "acessibilidade", "inclusao"]
    ),
    LegislationMetadata(
        id="ESTATUTO_CIDADE",
        name="Estatuto da Cidade (Lei 10.257/2001)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/leis_2001/l10257.htm",
        date="2001-07-10",
        category="urbanistico",
        tags=["urbanismo", "cidade", "politica_urbana", "funcao_social"]
    ),
    LegislationMetadata(
        id="ESTATUTO_TERRA",
        name="Estatuto da Terra (Lei 4.504/1964)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l4504.htm",
        date="1964-11-30",
        category="agrario",
        tags=["agrario", "terra", "reforma_agraria", "propriedade_rural"]
    ),
    LegislationMetadata(
        id="ESTATUTO_ADVOCACIA",
        name="Estatuto da Advocacia e da OAB (Lei 8.906/1994)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l8906.htm",
        date="1994-07-04",
        category="profissional",
        tags=["advocacia", "oab", "advogado", "etica_profissional"]
    ),
    LegislationMetadata(
        id="ESTATUTO_SERVIDOR",
        name="Estatuto dos Servidores Publicos Federais (Lei 8.112/1990)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l8112cons.htm",
        date="1990-12-11",
        category="administrativo",
        tags=["servidor_publico", "funcionalismo", "cargo_publico", "pad"]
    ),
    LegislationMetadata(
        id="ESTATUTO_MILITAR",
        name="Estatuto dos Militares (Lei 6.880/1980)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l6880.htm",
        date="1980-12-09",
        category="militar",
        tags=["militar", "forcas_armadas", "hierarquia"]
    ),
    LegislationMetadata(
        id="ESTATUTO_DESARMAMENTO",
        name="Estatuto do Desarmamento (Lei 10.826/2003)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/2003/l10.826.htm",
        date="2003-12-22",
        category="seguranca",
        tags=["armas", "desarmamento", "porte", "posse"]
    ),
    LegislationMetadata(
        id="ESTATUTO_TORCEDOR",
        name="Estatuto de Defesa do Torcedor (Lei 10.671/2003)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/2003/l10.671.htm",
        date="2003-05-15",
        category="esporte",
        tags=["torcedor", "esporte", "futebol", "evento_esportivo"]
    ),
    LegislationMetadata(
        id="ESTATUTO_IGUALDADE_RACIAL",
        name="Estatuto da Igualdade Racial (Lei 12.288/2010)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/_ato2007-2010/2010/lei/l12288.htm",
        date="2010-07-20",
        category="igualdade",
        tags=["igualdade_racial", "racismo", "discriminacao"]
    ),

    # === LEIS ESPECIAIS IMPORTANTES ===
    LegislationMetadata(
        id="LEI_INQUILINATO",
        name="Lei do Inquilinato (Lei 8.245/1991)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l8245.htm",
        date="1991-10-18",
        category="civil",
        tags=["locacao", "aluguel", "inquilino", "despejo"]
    ),
    LegislationMetadata(
        id="LEI_IMPROBIDADE",
        name="Lei de Improbidade Administrativa (Lei 8.429/1992)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l8429.htm",
        date="1992-06-02",
        category="administrativo",
        tags=["improbidade", "agente_publico", "enriquecimento_ilicito"]
    ),
    LegislationMetadata(
        id="LEI_LICITACOES_ANTIGA",
        name="Lei de Licitacoes (Lei 8.666/1993)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l8666cons.htm",
        date="1993-06-21",
        category="administrativo",
        tags=["licitacao", "contrato_administrativo", "pregao"]
    ),
    LegislationMetadata(
        id="LEI_LICITACOES_NOVA",
        name="Nova Lei de Licitacoes (Lei 14.133/2021)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/L14133.htm",
        date="2021-04-01",
        category="administrativo",
        tags=["licitacao", "contrato_administrativo", "pregao"]
    ),
    LegislationMetadata(
        id="LEI_ACAO_CIVIL_PUBLICA",
        name="Lei da Acao Civil Publica (Lei 7.347/1985)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l7347orig.htm",
        date="1985-07-24",
        category="processual",
        tags=["acao_civil_publica", "direitos_difusos", "ministerio_publico"]
    ),
    LegislationMetadata(
        id="LEI_MANDADO_SEGURANCA",
        name="Lei do Mandado de Seguranca (Lei 12.016/2009)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/_ato2007-2010/2009/lei/l12016.htm",
        date="2009-08-07",
        category="processual",
        tags=["mandado_seguranca", "direito_liquido_certo"]
    ),
    LegislationMetadata(
        id="LEI_JUIZADOS",
        name="Lei dos Juizados Especiais (Lei 9.099/1995)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l9099.htm",
        date="1995-09-26",
        category="processual",
        tags=["juizados_especiais", "pequenas_causas", "conciliacao"]
    ),
    LegislationMetadata(
        id="LEI_ARBITRAGEM",
        name="Lei de Arbitragem (Lei 9.307/1996)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l9307.htm",
        date="1996-09-23",
        category="processual",
        tags=["arbitragem", "mediacao", "solucao_conflitos"]
    ),
    LegislationMetadata(
        id="LEI_EXECUCAO_FISCAL",
        name="Lei de Execucao Fiscal (Lei 6.830/1980)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l6830.htm",
        date="1980-09-22",
        category="tributario",
        tags=["execucao_fiscal", "divida_ativa", "fazenda_publica"]
    ),
    LegislationMetadata(
        id="LEI_FALENCIAS",
        name="Lei de Recuperacao Judicial e Falencias (Lei 11.101/2005)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/_ato2004-2006/2005/lei/l11101.htm",
        date="2005-02-09",
        category="empresarial",
        tags=["falencia", "recuperacao_judicial", "insolvencia"]
    ),
    LegislationMetadata(
        id="LEI_SA",
        name="Lei das Sociedades Anonimas (Lei 6.404/1976)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l6404consol.htm",
        date="1976-12-15",
        category="empresarial",
        tags=["sociedade_anonima", "acoes", "assembleia", "conselho"]
    ),
    LegislationMetadata(
        id="LEI_REGISTROS_PUBLICOS",
        name="Lei de Registros Publicos (Lei 6.015/1973)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l6015compilada.htm",
        date="1973-12-31",
        category="registral",
        tags=["registro_imoveis", "registro_civil", "cartorio"]
    ),
    LegislationMetadata(
        id="LGPD",
        name="Lei Geral de Protecao de Dados (Lei 13.709/2018)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm",
        date="2018-08-14",
        category="dados",
        tags=["dados_pessoais", "privacidade", "tratamento_dados", "anpd"]
    ),
    LegislationMetadata(
        id="MARCO_CIVIL",
        name="Marco Civil da Internet (Lei 12.965/2014)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/lei/l12965.htm",
        date="2014-04-23",
        category="digital",
        tags=["internet", "provedores", "neutralidade_rede", "dados"]
    ),
    LegislationMetadata(
        id="LEI_DROGAS",
        name="Lei de Drogas (Lei 11.343/2006)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/lei/l11343.htm",
        date="2006-08-23",
        category="penal",
        tags=["drogas", "entorpecentes", "trafico", "sisnad"]
    ),
    LegislationMetadata(
        id="LEI_MARIA_PENHA",
        name="Lei Maria da Penha (Lei 11.340/2006)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/lei/l11340.htm",
        date="2006-08-07",
        category="penal",
        tags=["violencia_domestica", "mulher", "medidas_protetivas"]
    ),
    LegislationMetadata(
        id="LEI_CRIMES_HEDIONDOS",
        name="Lei dos Crimes Hediondos (Lei 8.072/1990)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l8072.htm",
        date="1990-07-25",
        category="penal",
        tags=["crime_hediondo", "progressao", "regime_fechado"]
    ),
    LegislationMetadata(
        id="LEI_TORTURA",
        name="Lei de Tortura (Lei 9.455/1997)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l9455.htm",
        date="1997-04-07",
        category="penal",
        tags=["tortura", "crime_hediondo"]
    ),
    LegislationMetadata(
        id="LEI_ORGANIZACAO_CRIMINOSA",
        name="Lei de Organizacao Criminosa (Lei 12.850/2013)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/lei/l12850.htm",
        date="2013-08-02",
        category="penal",
        tags=["organizacao_criminosa", "delacao_premiada", "infiltracao"]
    ),
    LegislationMetadata(
        id="LEI_LAVAGEM",
        name="Lei de Lavagem de Dinheiro (Lei 9.613/1998)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l9613.htm",
        date="1998-03-03",
        category="penal",
        tags=["lavagem_dinheiro", "coaf", "compliance"]
    ),
    LegislationMetadata(
        id="LEI_CRIMES_AMBIENTAIS",
        name="Lei de Crimes Ambientais (Lei 9.605/1998)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l9605.htm",
        date="1998-02-12",
        category="ambiental",
        tags=["crime_ambiental", "meio_ambiente", "fauna", "flora"]
    ),
    LegislationMetadata(
        id="LEI_EXECUCAO_PENAL",
        name="Lei de Execucao Penal (Lei 7.210/1984)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l7210.htm",
        date="1984-07-11",
        category="penal",
        tags=["execucao_penal", "progressao_regime", "remicao", "livramento"]
    ),
    LegislationMetadata(
        id="LEI_PRISAO_TEMPORARIA",
        name="Lei de Prisao Temporaria (Lei 7.960/1989)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l7960.htm",
        date="1989-12-21",
        category="penal",
        tags=["prisao_temporaria", "inquerito", "investigacao"]
    ),
    LegislationMetadata(
        id="LEI_INTERCEPTACAO",
        name="Lei de Interceptacao Telefonica (Lei 9.296/1996)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l9296.htm",
        date="1996-07-24",
        category="penal",
        tags=["interceptacao", "escuta", "telefone", "prova"]
    ),
    LegislationMetadata(
        id="LEI_ABUSO_AUTORIDADE",
        name="Lei de Abuso de Autoridade (Lei 13.869/2019)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/_ato2019-2022/2019/lei/L13869.htm",
        date="2019-09-05",
        category="penal",
        tags=["abuso_autoridade", "agente_publico"]
    ),
    LegislationMetadata(
        id="LEI_ANTICORRUPCAO",
        name="Lei Anticorrupcao (Lei 12.846/2013)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/lei/l12846.htm",
        date="2013-08-01",
        category="administrativo",
        tags=["corrupcao", "acordo_leniencia", "pessoa_juridica"]
    ),
    LegislationMetadata(
        id="LEI_ACESSO_INFORMACAO",
        name="Lei de Acesso a Informacao (Lei 12.527/2011)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/_ato2011-2014/2011/lei/l12527.htm",
        date="2011-11-18",
        category="administrativo",
        tags=["transparencia", "acesso_informacao", "sigilo"]
    ),
    LegislationMetadata(
        id="LEI_PROCESSO_ADMINISTRATIVO",
        name="Lei do Processo Administrativo Federal (Lei 9.784/1999)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l9784.htm",
        date="1999-01-29",
        category="administrativo",
        tags=["processo_administrativo", "ampla_defesa", "contraditorio"]
    ),
    LegislationMetadata(
        id="LEI_CONCESSOES",
        name="Lei de Concessoes (Lei 8.987/1995)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l8987cons.htm",
        date="1995-02-13",
        category="administrativo",
        tags=["concessao", "servico_publico", "permissao"]
    ),
    LegislationMetadata(
        id="LEI_PPP",
        name="Lei das PPPs (Lei 11.079/2004)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/_ato2004-2006/2004/lei/l11079.htm",
        date="2004-12-30",
        category="administrativo",
        tags=["ppp", "parceria_publico_privada", "concessao"]
    ),
    LegislationMetadata(
        id="LINDB",
        name="Lei de Introducao as Normas do Direito Brasileiro (Decreto-Lei 4.657/1942)",
        type="DECRETO_LEI",
        url="http://www.planalto.gov.br/ccivil_03/decreto-lei/del4657compilado.htm",
        date="1942-09-04",
        category="geral",
        tags=["lindb", "vigencia", "interpretacao", "aplicacao_normas"]
    ),
    LegislationMetadata(
        id="LEI_USUCAPIAO",
        name="Lei de Usucapiao Urbano (Lei 10.257/2001 - Arts. 9-14)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/leis_2001/l10257.htm",
        date="2001-07-10",
        category="civil",
        tags=["usucapiao", "propriedade", "posse"]
    ),
    LegislationMetadata(
        id="LEI_ALIMENTOS_GRAVIDAS",
        name="Lei de Alimentos Gravidas (Lei 11.804/2008)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/_ato2007-2010/2008/lei/l11804.htm",
        date="2008-11-05",
        category="familia",
        tags=["alimentos", "gravidez", "nascituro"]
    ),
    LegislationMetadata(
        id="LEI_DIVORCIO",
        name="Lei do Divorcio (Lei 6.515/1977)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l6515.htm",
        date="1977-12-26",
        category="familia",
        tags=["divorcio", "separacao", "casamento"]
    ),
    LegislationMetadata(
        id="LEI_UNIAO_ESTAVEL",
        name="Lei da Uniao Estavel (Lei 9.278/1996)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l9278.htm",
        date="1996-05-10",
        category="familia",
        tags=["uniao_estavel", "convivencia", "familia"]
    ),
    LegislationMetadata(
        id="LEI_DIREITOS_AUTORAIS",
        name="Lei de Direitos Autorais (Lei 9.610/1998)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l9610.htm",
        date="1998-02-19",
        category="propriedade_intelectual",
        tags=["direito_autoral", "copyright", "obra_intelectual"]
    ),
    LegislationMetadata(
        id="LEI_PROPRIEDADE_INDUSTRIAL",
        name="Lei de Propriedade Industrial (Lei 9.279/1996)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l9279.htm",
        date="1996-05-14",
        category="propriedade_intelectual",
        tags=["patente", "marca", "propriedade_industrial", "inpi"]
    ),
    LegislationMetadata(
        id="LEI_SOFTWARE",
        name="Lei de Software (Lei 9.609/1998)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l9609.htm",
        date="1998-02-19",
        category="propriedade_intelectual",
        tags=["software", "programa_computador", "licenca"]
    ),
    LegislationMetadata(
        id="LEI_CRIMES_INFORMATICOS",
        name="Lei de Crimes Informaticos - Carolina Dieckmann (Lei 12.737/2012)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/_ato2011-2014/2012/lei/l12737.htm",
        date="2012-11-30",
        category="penal",
        tags=["crime_informatico", "invasao", "hacker"]
    ),
    LegislationMetadata(
        id="LEI_PREVIDENCIA",
        name="Lei de Beneficios da Previdencia Social (Lei 8.213/1991)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l8213cons.htm",
        date="1991-07-24",
        category="previdenciario",
        tags=["previdencia", "aposentadoria", "auxilio_doenca", "inss"]
    ),
    LegislationMetadata(
        id="LEI_CUSTEIO_PREVIDENCIA",
        name="Lei de Custeio da Seguridade Social (Lei 8.212/1991)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l8212cons.htm",
        date="1991-07-24",
        category="previdenciario",
        tags=["contribuicao", "seguridade_social", "inss"]
    ),
    LegislationMetadata(
        id="LEI_ORGANICA_SUS",
        name="Lei Organica da Saude (Lei 8.080/1990)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l8080.htm",
        date="1990-09-19",
        category="saude",
        tags=["sus", "saude", "sistema_unico"]
    ),
    LegislationMetadata(
        id="LEI_PLANOS_SAUDE",
        name="Lei dos Planos de Saude (Lei 9.656/1998)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l9656.htm",
        date="1998-06-03",
        category="saude",
        tags=["plano_saude", "ans", "operadora"]
    ),
    LegislationMetadata(
        id="LEI_EDUCACAO",
        name="Lei de Diretrizes e Bases da Educacao (Lei 9.394/1996)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l9394.htm",
        date="1996-12-20",
        category="educacao",
        tags=["educacao", "ensino", "escola", "universidade"]
    ),
    LegislationMetadata(
        id="LEI_MEIO_AMBIENTE",
        name="Politica Nacional do Meio Ambiente (Lei 6.938/1981)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l6938.htm",
        date="1981-08-31",
        category="ambiental",
        tags=["meio_ambiente", "licenciamento", "ibama", "conama"]
    ),
    LegislationMetadata(
        id="CODIGO_FLORESTAL",
        name="Codigo Florestal (Lei 12.651/2012)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/_ato2011-2014/2012/lei/l12651.htm",
        date="2012-05-25",
        category="ambiental",
        tags=["floresta", "app", "reserva_legal", "desmatamento"]
    ),
    LegislationMetadata(
        id="LEI_RECURSOS_HIDRICOS",
        name="Politica Nacional de Recursos Hidricos (Lei 9.433/1997)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/leis/l9433.htm",
        date="1997-01-08",
        category="ambiental",
        tags=["agua", "recursos_hidricos", "bacia_hidrografica"]
    ),
    LegislationMetadata(
        id="LEI_RESIDUOS_SOLIDOS",
        name="Politica Nacional de Residuos Solidos (Lei 12.305/2010)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/_ato2007-2010/2010/lei/l12305.htm",
        date="2010-08-02",
        category="ambiental",
        tags=["residuos", "lixo", "reciclagem", "logistica_reversa"]
    ),
    LegislationMetadata(
        id="LEI_SANEAMENTO",
        name="Marco Legal do Saneamento (Lei 14.026/2020)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/_ato2019-2022/2020/lei/l14026.htm",
        date="2020-07-15",
        category="ambiental",
        tags=["saneamento", "agua", "esgoto"]
    ),

    # === LEIS COMPLEMENTARES ===
    LegislationMetadata(
        id="LC_RESPONSABILIDADE_FISCAL",
        name="Lei de Responsabilidade Fiscal (LC 101/2000)",
        type="LC",
        url="http://www.planalto.gov.br/ccivil_03/leis/lcp/lcp101.htm",
        date="2000-05-04",
        category="financeiro",
        tags=["responsabilidade_fiscal", "orcamento", "divida_publica"]
    ),
    LegislationMetadata(
        id="LC_ESTATAIS",
        name="Lei das Estatais (Lei 13.303/2016)",
        type="LEI",
        url="http://www.planalto.gov.br/ccivil_03/_ato2015-2018/2016/lei/l13303.htm",
        date="2016-06-30",
        category="administrativo",
        tags=["estatal", "empresa_publica", "sociedade_economia_mista"]
    ),
    LegislationMetadata(
        id="LC_SUPER_SIMPLES",
        name="Estatuto da Micro e Pequena Empresa (LC 123/2006)",
        type="LC",
        url="http://www.planalto.gov.br/ccivil_03/leis/lcp/lcp123.htm",
        date="2006-12-14",
        category="empresarial",
        tags=["simples_nacional", "mei", "microempresa"]
    ),
    LegislationMetadata(
        id="LC_INELEGIBILIDADE",
        name="Lei da Ficha Limpa (LC 135/2010)",
        type="LC",
        url="http://www.planalto.gov.br/ccivil_03/leis/lcp/lcp135.htm",
        date="2010-06-04",
        category="eleitoral",
        tags=["ficha_limpa", "inelegibilidade", "eleicoes"]
    ),
]


class PlanaltoScraper:
    """
    Scraper for Brazilian legislation from Planalto.gov.br.
    Implements rate limiting and retry logic for reliability.
    """

    def __init__(
        self,
        rate_limit: float = 1.0,  # seconds between requests
        max_retries: int = 3,
        timeout: int = 30
    ):
        self.rate_limit = rate_limit
        self.max_retries = max_retries
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        self._last_request_time = 0

    async def _rate_limit_wait(self):
        """Enforce rate limiting between requests."""
        import time
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            await asyncio.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()

    async def fetch_legislation(
        self,
        legislation: LegislationMetadata,
        session: aiohttp.ClientSession
    ) -> Optional[str]:
        """
        Fetch and clean text from a single legislation URL.
        Returns None if fetch fails after retries.
        """
        for attempt in range(self.max_retries):
            try:
                await self._rate_limit_wait()

                async with session.get(
                    legislation.url,
                    headers=self.headers,
                    timeout=self.timeout
                ) as response:
                    if response.status == 200:
                        # Planalto uses windows-1252 encoding
                        content = await response.read()
                        try:
                            text = content.decode('windows-1252')
                        except UnicodeDecodeError:
                            text = content.decode('utf-8', errors='replace')

                        return self._clean_html(text, legislation.type)
                    else:
                        logger.warning(
                            f"HTTP {response.status} for {legislation.name} "
                            f"(attempt {attempt + 1}/{self.max_retries})"
                        )
            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout fetching {legislation.name} "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
            except Exception as e:
                logger.error(
                    f"Error fetching {legislation.name}: {e} "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )

            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

        return None

    def _clean_html(self, html: str, law_type: str) -> str:
        """
        Extract and clean text from Planalto HTML.
        Handles the messy HTML structure of the portal.
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Remove script and style elements
        for element in soup(['script', 'style', 'header', 'footer', 'nav']):
            element.decompose()

        # Try to find the main content area
        # Planalto uses various content containers
        content = None
        for selector in ['#conteudo', '.conteudo', '#texto', '.texto', 'body']:
            content = soup.select_one(selector)
            if content:
                break

        if not content:
            content = soup

        # Get text preserving some structure
        text = content.get_text(separator='\n')

        # Clean up excessive whitespace
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            if line and not self._is_noise(line):
                lines.append(line)

        return '\n'.join(lines)

    def _is_noise(self, line: str) -> bool:
        """Check if a line is navigation/footer noise."""
        noise_patterns = [
            r'^Presidência da República$',
            r'^Casa Civil$',
            r'^Subchefia para Assuntos Jurídicos$',
            r'^Voltar ao topo$',
            r'^Imprimir$',
            r'^javascript:',
            r'^\d+$',  # Just numbers
            r'^[\s\.\-_]+$',  # Just punctuation/whitespace
        ]
        for pattern in noise_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return True
        return False

    async def fetch_all(
        self,
        legislations: Optional[List[LegislationMetadata]] = None,
        categories: Optional[List[str]] = None
    ) -> AsyncGenerator[tuple[LegislationMetadata, str], None]:
        """
        Fetch all specified legislations.
        Yields tuples of (metadata, text) for each successful fetch.
        """
        if legislations is None:
            legislations = BRAZILIAN_LEGISLATION_CATALOG

        # Filter by category if specified
        if categories:
            legislations = [l for l in legislations if l.category in categories]

        logger.info(f"Starting fetch of {len(legislations)} legislations...")

        async with aiohttp.ClientSession() as session:
            for i, legislation in enumerate(legislations):
                logger.info(
                    f"[{i+1}/{len(legislations)}] Fetching {legislation.name}..."
                )

                text = await self.fetch_legislation(legislation, session)

                if text:
                    logger.info(
                        f"Successfully fetched {legislation.name} "
                        f"({len(text)} chars)"
                    )
                    yield legislation, text
                else:
                    logger.error(f"Failed to fetch {legislation.name}")

    def get_catalog(
        self,
        categories: Optional[List[str]] = None,
        tags: Optional[List[str]] = None
    ) -> List[LegislationMetadata]:
        """
        Get filtered catalog of available legislations.
        """
        result = BRAZILIAN_LEGISLATION_CATALOG.copy()

        if categories:
            result = [l for l in result if l.category in categories]

        if tags:
            result = [
                l for l in result
                if any(t in l.tags for t in tags)
            ]

        return result

    def get_categories(self) -> List[str]:
        """Get list of all available categories."""
        return sorted(set(l.category for l in BRAZILIAN_LEGISLATION_CATALOG))

    def get_tags(self) -> List[str]:
        """Get list of all available tags."""
        tags = set()
        for l in BRAZILIAN_LEGISLATION_CATALOG:
            tags.update(l.tags)
        return sorted(tags)
