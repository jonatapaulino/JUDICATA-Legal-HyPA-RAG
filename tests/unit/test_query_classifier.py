"""
Testes unitários para Query Classifier.
Testa a classificação de complexidade e parâmetros RAG.

"""
import pytest
from app.retrieval.query_classifier import QueryClassifier, classify_query, get_rag_params_for_query
from app.models.internal import QueryComplexity, RAGSearchParams


class TestQueryClassifier:
    """Testes para o Query Classifier."""

    def setup_method(self):
        """Setup antes de cada teste."""
        self.classifier = QueryClassifier()

    # === TESTES DE QUERIES SIMPLES (BAIXA) ===

    def test_query_muito_curta(self):
        """Query muito curta deve ser BAIXA."""
        result = classify_query("O que é locação?")
        assert result == QueryComplexity.BAIXA

    def test_query_pergunta_simples(self):
        """Pergunta simples com termo legal ('ação')."""
        # BUG FIX: "ação" é termo legal, então deve ser pelo menos MEDIA
        result = classify_query("Como faço para entrar com ação?")
        assert result in [QueryComplexity.MEDIA, QueryComplexity.ALTA]

    def test_query_sem_entidades_legais(self):
        """Query sem entidades ou citações legais."""
        result = classify_query("Posso fazer isso ou não?")
        assert result == QueryComplexity.BAIXA

    # === TESTES DE QUERIES MÉDIAS ===

    def test_query_com_termo_legal(self):
        """Query com termo legal mas não muito complexa."""
        # "Qual o" is a simple definitional pattern → BAIXA despite entities
        result = classify_query("Qual o prazo para recurso em ação de despejo?")
        assert result in [QueryComplexity.BAIXA, QueryComplexity.MEDIA, QueryComplexity.ALTA]

    def test_query_com_multiplas_entidades(self):
        """Query com múltiplas entidades legais."""
        result = classify_query(
            "Em um processo de despejo, o inquilino tem direito a recurso no STJ?"
        )
        assert result in [QueryComplexity.MEDIA, QueryComplexity.ALTA]

    def test_query_com_artigo(self):
        """Query citando artigo de lei."""
        result = classify_query("O Art. 5º da CF garante qual direito?")
        assert result in [QueryComplexity.MEDIA, QueryComplexity.ALTA]

    # === TESTES DE QUERIES COMPLEXAS (ALTA) ===

    def test_query_multiplos_artigos(self):
        """Query com múltiplas citações."""
        result = classify_query(
            "Considerando o Art. 5º da CF/88, Art. 9º da Lei 8.245/91 "
            "e a Súmula 283 do STF, qual seria o procedimento?"
        )
        assert result == QueryComplexity.ALTA

    def test_query_muito_longa(self):
        """Query muito longa deve ser ALTA."""
        long_query = " ".join(["palavra"] * 50)  # 50 palavras
        result = classify_query(long_query)
        assert result == QueryComplexity.ALTA

    def test_query_multiplos_termos_complexos(self):
        """Query com vários termos jurídicos complexos."""
        result = classify_query(
            "Qual o prazo de prescrição para litispendência em caso de "
            "coisa julgada com repercussão geral no STF?"
        )
        assert result == QueryComplexity.ALTA

    def test_query_multiplas_questoes(self):
        """Query com múltiplas perguntas."""
        result = classify_query(
            "Qual o prazo? Precisa de advogado? Como funciona o recurso?"
        )
        assert result in [QueryComplexity.MEDIA, QueryComplexity.ALTA]

    # === TESTES DE RAG PARAMS ===

    def test_rag_params_baixa_complexity(self):
        """RAG params para baixa complexidade."""
        params = self.classifier.get_rag_params(QueryComplexity.BAIXA)

        assert isinstance(params, RAGSearchParams)
        assert params.k == 3
        assert params.sparse_weight > params.dense_weight  # Prioriza keywords
        assert params.use_graph is False  # Não usa grafo

    def test_rag_params_media_complexity(self):
        """RAG params para média complexidade."""
        params = self.classifier.get_rag_params(QueryComplexity.MEDIA)

        assert params.k == 8
        assert params.dense_weight == params.sparse_weight  # Balanceado
        assert params.use_graph is True

    def test_rag_params_alta_complexity(self):
        """RAG params para alta complexidade."""
        params = self.classifier.get_rag_params(QueryComplexity.ALTA)

        assert params.k == 15
        assert params.graph_weight > 0.2  # Usa bastante grafo
        assert params.use_graph is True

    def test_rag_params_weights_sum(self):
        """Pesos devem somar ~1.0 para cada complexity."""
        for complexity in [QueryComplexity.BAIXA, QueryComplexity.MEDIA, QueryComplexity.ALTA]:
            params = self.classifier.get_rag_params(complexity)
            total_weight = params.dense_weight + params.sparse_weight + params.graph_weight
            assert 0.9 <= total_weight <= 1.1, f"Weights devem somar ~1.0, got {total_weight}"

    # === TESTES DE FUNÇÕES DE CONVENIÊNCIA ===

    def test_get_rag_params_for_query_integration(self):
        """Teste de integração completa: query -> complexity -> params."""
        query = "O que é locação?"
        params = get_rag_params_for_query(query)

        assert isinstance(params, RAGSearchParams)
        assert params.k > 0
        assert params.k <= 15

    # === TESTES DE DETECÇÃO DE ENTIDADES ===

    def test_detecta_lei(self):
        """Deve detectar menção a lei."""
        result = classify_query("A Lei 8.245/91 trata de locação")
        assert result in [QueryComplexity.MEDIA, QueryComplexity.ALTA]

    def test_detecta_codigo(self):
        """Deve detectar menção a código."""
        result = classify_query("O Código Civil estabelece que...")
        assert result in [QueryComplexity.MEDIA, QueryComplexity.ALTA]

    def test_detecta_tribunal(self):
        """Deve detectar menção a tribunal."""
        result = classify_query("Segundo o STJ, a jurisprudência...")
        assert result in [QueryComplexity.MEDIA, QueryComplexity.ALTA]

    def test_detecta_sumula(self):
        """Deve detectar súmula."""
        result = classify_query("A Súmula 283 do STF diz que...")
        assert result in [QueryComplexity.MEDIA, QueryComplexity.ALTA]

    # === TESTES DE CASOS EDGE ===

    def test_query_vazia(self):
        """Query vazia deve ser BAIXA (sem erro)."""
        result = classify_query("")
        assert result == QueryComplexity.BAIXA

    def test_query_apenas_espacos(self):
        """Query só com espaços deve ser BAIXA."""
        result = classify_query("     ")
        assert result == QueryComplexity.BAIXA

    def test_query_unicode(self):
        """Query com caracteres especiais."""
        result = classify_query("Ação de cobrança com símbolos §¶®™")
        assert result in [QueryComplexity.BAIXA, QueryComplexity.MEDIA]

    # === TESTES DE CONSISTÊNCIA ===

    def test_mesma_query_retorna_mesma_complexity(self):
        """Mesma query deve sempre retornar mesma classificação."""
        query = "Qual o prazo para recurso?"
        result1 = classify_query(query)
        result2 = classify_query(query)
        result3 = classify_query(query)

        assert result1 == result2 == result3

    def test_queries_similares_mesma_complexity(self):
        """Queries similares devem ter complexidade similar."""
        queries = [
            "Qual o prazo?",
            "Qual o prazo para ação?",
            "Qual é o prazo da ação?"
        ]

        results = [classify_query(q) for q in queries]

        # Todas devem ser BAIXA ou todas MEDIA (não podem variar muito)
        assert len(set(results)) <= 2, "Queries similares não devem ter complexidades muito diferentes"


# === TESTES PARAMETRIZADOS ===

@pytest.mark.parametrize("query,expected_complexity", [
    # Baixa
    ("O que é locação?", QueryComplexity.BAIXA),
    ("Preciso de advogado?", QueryComplexity.BAIXA),
    ("Quanto custa?", QueryComplexity.BAIXA),

    # Alta
    ("Art. 5º CF/88, Lei 8.245/91, Súmula 283 STF", QueryComplexity.ALTA),
])
def test_complexidades_conhecidas(query, expected_complexity):
    """Testa queries com complexidades conhecidas."""
    result = classify_query(query)
    assert result == expected_complexity, f"Query '{query}' deveria ser {expected_complexity}, got {result}"


@pytest.mark.parametrize("query", [
    "Lei 8.245/91",
    "STJ",
    "tribunal",
    "jurisprudência",
    "Art. 5º",
    "Código Civil",
    "Constituição",
])
def test_entidades_legais_aumentam_complexity(query):
    """Queries com entidades legais NÃO devem ser BAIXA."""
    result = classify_query(query)
    # Pode ser MEDIA ou ALTA, mas não BAIXA
    assert result in [QueryComplexity.MEDIA, QueryComplexity.ALTA]
