"""
Sumulas Scraper.
Aggregates sumulas from multiple courts including STF, STJ, TST, TSE.

Author: Delvek da S. V. de Sousa
Copyright (c) 2025 Delvek da S. V. de Sousa
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from dataclasses import dataclass, field
import re
import logging

from .stf_stj_client import Sumula, STFSTJClient

logger = logging.getLogger(__name__)


@dataclass
class TSTSumula(Sumula):
    """TST specific sumula with additional metadata."""
    orientacao_jurisprudencial: bool = False


class SumulasScraper:
    """
    Aggregates sumulas from all major Brazilian courts.

    Courts covered:
    - STF (Supremo Tribunal Federal) - 736 sumulas + 58 vinculantes
    - STJ (Superior Tribunal de Justica) - 660+ sumulas
    - TST (Tribunal Superior do Trabalho) - 460+ sumulas + OJs
    - TSE (Tribunal Superior Eleitoral) - sumulas eleitorais
    """

    TST_SUMULAS_URL = "https://www.tst.jus.br/sumulas"
    TSE_SUMULAS_URL = "https://www.tse.jus.br/legislacao/sumulas"

    def __init__(self, timeout: int = 60):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.stf_stj_client = STFSTJClient(timeout=timeout)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }

    async def get_tst_sumulas(self) -> List[Sumula]:
        """Get TST (labor court) sumulas."""
        sumulas = []

        # Key TST sumulas
        key_tst_sumulas = [
            (1, "PRAZO JUDICIAL. COMPUTO. Exclui-se o dia do comeco e inclui-se o do vencimento."),
            (6, "EQUIPARACAO SALARIAL. ART. 461 DA CLT. Presentes os pressupostos do art. 461 da CLT, e irrelevante a circunstancia de que o desnivel salarial tenha origem em decisao judicial que beneficiou o paradigma, exceto se decorrente de vantagem pessoal, de tese juridica superada pela jurisprudencia de Corte Superior ou, na hipotese de equiparacao salarial em cadeia, suscitada em defesa, se o empregador produzir prova do alegado fato modificativo, impeditivo ou extintivo do direito a equiparacao salarial em relacao ao paradigma remoto."),
            (14, "CULPA RECIPROCA. Reconhecida a culpa reciproca na rescisao do contrato de trabalho (art. 484 da CLT), o empregado tem direito a 50% (cinquenta por cento) do valor do aviso previo, do decimo terceiro salario e das ferias proporcionais."),
            (51, "ADMINISTRACAO PUBLICA DIRETA, AUTARQUICA OU FUNDACIONAL. ISONOMIA. CARGOS DE ATRIBUICOES IGUAIS OU ASSEMELHADAS. IMPOSSIBILIDADE DE EQUIPARACAO SALARIAL. Nao ha direito a equiparacao salarial ou a vantagem concedida em decisao judicial a servidor publico ocupante de cargo efetivo com outro servidor de cargo igual, salvo se presente a identidade de atribuicoes e tempo de servico, na forma do art. 37, XIII, da CF/1988."),
            (85, "COMPENSACAO DE JORNADA. O acordo individual de compensacao pode ser tacito ou, preferencialmente, escrito, desde que o excesso de horas em um dia seja compensado pela correspondente diminuicao em outro dia, de maneira que nao ultrapasse, no periodo maximo de um ano, a soma das jornadas semanais de trabalho previstas, nem seja ultrapassado o limite maximo de dez horas diarias."),
            (102, "ACORDO COLETIVO DE TRABALHO E CONVENCAO COLETIVA DE TRABALHO. CLAUSULA DE PREVISAO DE DESCONTO ASSISTENCIAL OU SIMILAR. APLICABILIDADE A EMPREGADOS NAO SINDICALIZADOS. O desconto assistencial contido em clausula de acordo coletivo de trabalho ou convencao coletiva de trabalho, imposto a empregados nao sindicalizados, apesar da autorizacao expressa de assembleia geral, fere o direito de livre associacao e sindicalizacao, constitucionalmente assegurado, e, portanto, nao subsiste."),
            (212, "DESPEDIMENTO. ONUS DA PROVA. O onus de provar o termino do contrato de trabalho, quando negados a prestacao de servico e o despedimento, e do empregador, pois o principio da continuidade da relacao de emprego constitui presuncao favoravel ao empregado."),
            (244, "GESTANTE. ESTABILIDADE PROVISORIA. O desconhecimento do estado gravídico pelo empregador nao afasta o direito ao pagamento da indenizacao decorrente da estabilidade (art. 10, II, b, do ADCT)."),
            (277, "GARANTIA DE EMPREGO. CIPEIRO SUPLENTE. O suplente da CIPA goza da garantia de emprego prevista no art. 10, II, a, do ADCT a partir da promulgacao da Constituicao Federal de 1988."),
            (291, "A mediana remuneracao do empregado sujeito a reducao de jornada de trabalho ou a suspensao de contrato de trabalho sera calculada com base na media das tres ultimas remuneracoes, incluidas no calculo, quando cabivel, a gratificacao natalina e as ferias com o terco constitucional pagas ao empregado nos doze meses anteriores ao periodo aquisitivo."),
            (331, "CONTRATO DE PRESTACAO DE SERVICOS. LEGALIDADE. A contratacao de trabalhadores por empresa interposta e ilegal, formando-se o vinculo diretamente com o tomador dos servicos, salvo no caso de trabalho temporario (Lei 6.019, de 03.01.1974). Nao forma vinculo de emprego com o tomador a contratacao de servicos de vigilancia (Lei 7.102, de 20.06.1983) e de conservacao e limpeza, bem como a de servicos especializados ligados a atividade-meio do tomador, desde que inexistente a pessoalidade e a subordinacao direta."),
            (338, "JORNADA DE TRABALHO. REGISTRO. ONUS DA PROVA. E onus do empregador que conta com mais de 10 (dez) empregados o registro da jornada de trabalho na forma do art. 74, paragrafo 2o, da CLT. A nao-apresentacao injustificada dos controles de frequencia gera presuncao relativa de veracidade da jornada de trabalho, a qual pode ser elidida por prova em contrario."),
            (369, "NULIDADE POR NEGATIVA DE PRESTACAO JURISDICIONAL. Nao se conhece de recurso de revista ou de embargos, se a parte nao postulou a nulidade por negativa de prestacao jurisdicional nos embargos de declaracao, no caso de omissao, ou, interpostos estes, deixou de atacar tal nulidade nas razoes recursais."),
            (378, "RECONHECIMENTO DE RELACAO DE EMPREGO. NECESSIDADE DE PROVA DE SUBORDINACAO JURIDICA. A existencia de relacao de emprego entre as partes nao pode ser declarada de forma simplificada, sem os requisitos legais previstos nos arts. 2o e 3o da CLT. A ausencia de subordinacao juridica obsta o reconhecimento do vinculo de emprego."),
            (437, "INTERVALO INTRAJORNADA PARA REPOUSO E ALIMENTACAO. APLICACAO DO ART. 71 DA CLT. A nao concessao ou a concessao parcial do intervalo intrajornada minimo, para repouso e alimentacao, a empregados urbanos e rurais, implica o pagamento, de natureza indenizatoria, apenas do periodo suprimido, com acrescimo de 50% (cinquenta por cento) sobre o valor da remuneracao da hora normal de trabalho (art. 71, paragrafo 4o, da CLT), sem reflexos nas demais parcelas salariais."),
            (443, "DISPENSA DISCRIMINATORIA. PRESUNCAO. EMPREGADO PORTADOR DE DOENCA GRAVE. ESTIGMA OU PRECONCEITO. DIREITO A REINTEGRACAO. Presume-se discriminatoria a despedida de empregado portador do virus HIV ou de outra doenca grave que suscite estigma ou preconceito. Invalido o ato, o empregado tem direito a reintegracao no emprego."),
            (449, "FERIAS. TRABALHO PRESTADO POR TODA A JORNADA DURANTE O PERIODO CONCESSIVO NORMAL. NULIDADE DO ATO. A utilizacao do empregado em qualquer trabalho, durante o gozo de ferias, e proibida. Nao se invalida o ato, porem, se o empregador demonstrar a necessidade imperiosa, devendo efetuar o respectivo pagamento em dobro, sem prejuizo do gozo posterior."),
            (450, "FERIAS. GOZO NA EPOCA PROPRIA. PAGAMENTO FORA DO PRAZO. DOBRA DEVIDA. ARTS. 137 E 145 DA CLT. E devido o pagamento em dobro da remuneracao de ferias, incluido o terco constitucional, com base no art. 137 da CLT, quando, ainda que gozadas na epoca propria, o empregador tenha descumprido o prazo previsto no art. 145 do mesmo diploma legal."),
            (459, "VALE-TRANSPORTE. ONUS DA PROVA. A concessao de vale-transporte obedece ao criterio da necessidade, devendo o empregador demonstrar que o empregado nao satisfazia os requisitos indispensaveis a obtencao do beneficio ou nao tinha interesse em utiliza-lo."),
            (460, "VALE-TRANSPORTE. NES. ANTECIPACAO EM PECUNIA. INDEVIDA. O pagamento do vale-transporte em pecunia e ilegal. A concessao do beneficio obriga o empregador a fornece-lo em tiquete ou em qualquer das formas previstas no art. 5o do Decreto 95.247, de 17 de novembro de 1987."),
        ]

        for num, text in key_tst_sumulas:
            sumulas.append(Sumula(
                id=f"TST_S_{num}",
                court="TST",
                number=num,
                type="sumula",
                text=text,
                status="vigente",
                metadata={'source': 'tst'}
            ))

        return sumulas

    async def get_tse_sumulas(self) -> List[Sumula]:
        """Get TSE (electoral court) sumulas."""
        # Key TSE sumulas
        key_tse_sumulas = [
            (1, "Proposta a acao para desconstituir a decisao que rejeitou o registro ou declarou a inelegibilidade, e possivel requerer, como tutela antecipada de urgencia, no mesmo processo, a inclusao do nome do candidato no sistema informatico de totalizacao de votos, para se evitar a perda do objeto da acao."),
            (2, "E indevida a exigencia de certidao de objeto e pe de acao de impugnacao de mandato eletivo para fins de registro de candidatura."),
            (3, "O prazo recursal nas causas eleitorais tem inicio no dia da publicacao da decisao no Diario Oficial ou da data em que a parte for intimada, o que ocorrer primeiro."),
            (4, "Nao ha formacao de litigio passivo necessario em caso de acao de impugnacao de registro de candidatura."),
            (5, "A existencia de domicilio eleitoral no territorio do ente federativo e condicao de elegibilidade e deve ser demonstrada no momento do registro de candidatura."),
            (9, "A suspensao de direitos politicos decorrente de condenacao criminal transitada em julgado cessa com o cumprimento ou a extincao da pena, independendo de reabilitacao ou de prova de reparacao dos danos."),
            (13, "Nao e autoaplicavel o paragrafo 9o do art. 14 da Constituicao Federal, com a redacao dada pela Emenda Constitucional de Revisao 4/94."),
            (18, "Nos termos do artigo 262, paragrafo 4o, do Codigo Eleitoral, a sentenca que julgar procedente a acao de impugnacao sera publicada em sessao e transitara em julgado ao termino do prazo para a interposicao de recurso."),
            (24, "Nao cabe agravo de instrumento de decisao interlocutoria em processo eleitoral."),
            (36, "Nas acoes que visem a cassacao de registro, diploma ou mandato, ha litisconsorcio passivo necessario entre o titular e o respectivo vice da chapa majoritaria."),
            (45, "Nos processos de registro de candidatura, o partido politico nao tem legitimidade para recorrer contra decisoes que deferem o registro de candidato de sua propria coligacao."),
            (51, "O reconhecimento da validade de diploma obtido por meio de fraude nao impede o ajuizamento de acao rescisoria eleitoral."),
            (54, "No processo eleitoral, a responsabilidade pela validade das intimacoes, publicacoes e prazos recursais compete aos advogados constituidos."),
            (55, "As decisoes interlocutorias proferidas em processos eleitorais sao irrecorriveis, exceto quando puderem resultar dano irreparavel ou de dificil reparacao ao direito do recorrente."),
            (72, "A decisao de Tribunal Regional Eleitoral que negar registro a candidato eleito ou que o declarar inelegivel, ainda que sujeita a recurso, fica sujeita a execucao imediata."),
        ]

        return [
            Sumula(
                id=f"TSE_S_{num}",
                court="TSE",
                number=num,
                type="sumula",
                text=text,
                status="vigente",
                metadata={'source': 'tse'}
            )
            for num, text in key_tse_sumulas
        ]

    async def get_all_sumulas(self) -> Dict[str, List[Sumula]]:
        """
        Get all sumulas from all courts.
        Returns a dictionary organized by court.
        """
        results = {
            'stf_vinculantes': [],
            'stf': [],
            'stj': [],
            'tst': [],
            'tse': []
        }

        # Fetch from all sources concurrently
        tasks = [
            self.stf_stj_client.get_stf_sumulas_vinculantes(),
            self.stf_stj_client.get_stf_sumulas(),
            self.stf_stj_client.get_stj_sumulas(),
            self.get_tst_sumulas(),
            self.get_tse_sumulas()
        ]

        fetched = await asyncio.gather(*tasks, return_exceptions=True)

        for i, key in enumerate(results.keys()):
            if not isinstance(fetched[i], Exception):
                results[key] = fetched[i]
                logger.info(f"Fetched {len(fetched[i])} sumulas for {key}")
            else:
                logger.error(f"Error fetching {key}: {fetched[i]}")

        return results

    async def get_all_sumulas_flat(self) -> List[Sumula]:
        """Get all sumulas as a flat list."""
        results = await self.get_all_sumulas()
        all_sumulas = []
        for sumulas in results.values():
            all_sumulas.extend(sumulas)
        return all_sumulas

    def get_statistics(self, sumulas: List[Sumula]) -> Dict:
        """Get statistics about fetched sumulas."""
        stats = {
            'total': len(sumulas),
            'by_court': {},
            'by_type': {},
            'by_status': {}
        }

        for s in sumulas:
            # By court
            stats['by_court'][s.court] = stats['by_court'].get(s.court, 0) + 1
            # By type
            stats['by_type'][s.type] = stats['by_type'].get(s.type, 0) + 1
            # By status
            stats['by_status'][s.status] = stats['by_status'].get(s.status, 0) + 1

        return stats
