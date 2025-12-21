# Guia de Instalação e Execução
## Backend de Soberania Judicial

Este guia fornece instruções passo a passo para executar o sistema completo.

---

## Pré-requisitos

- **Docker** e **Docker Compose** instalados
- **Python 3.10+** (para desenvolvimento local)
- **GPU NVIDIA** (opcional, recomendado para Ollama)
- Pelo menos **8GB RAM** disponível

---

## 1. Configuração Inicial

### 1.1. Copiar arquivo de ambiente

```bash
cp .env.example .env
```

### 1.2. Ajustar variáveis de ambiente (opcional)

Edite o arquivo `.env` conforme necessário. As configurações padrão devem funcionar para testes locais.

---

## 2. Subir a Infraestrutura com Docker

### 2.1. Iniciar todos os serviços

```bash
docker-compose -f docker/docker-compose.yml up -d
```

Isso iniciará:
- **Qdrant** (Vector Database) na porta 6333
- **Neo4j** (Graph Database) nas portas 7474 (HTTP) e 7687 (Bolt)
- **Redis** (Cache) na porta 6379
- **Ollama** (LLM Local) na porta 11434

### 2.2. Verificar se os serviços estão rodando

```bash
docker-compose -f docker/docker-compose.yml ps
```

Todos os serviços devem estar com status `Up` e `healthy`.

### 2.3. Baixar o modelo LLM no Ollama

**Importante**: O SaulLM-7B pode não estar disponível no Ollama. Use um modelo alternativo como Mistral ou Llama2:

```bash
# Entrar no container do Ollama
docker exec -it judicial-ollama bash

# Baixar modelo (escolha um)
ollama pull mistral:7b
# OU
ollama pull llama2:7b

# Sair do container
exit
```

Atualize o `.env` para usar o modelo baixado:
```
OLLAMA_MODEL=mistral:7b
```

---

## 3. Instalar Dependências Python (Desenvolvimento Local)

Se você quiser rodar a API localmente (fora do Docker):

```bash
# Criar ambiente virtual
python -m venv venv

# Ativar ambiente virtual
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Baixar modelo spaCy
python -m spacy download pt_core_news_lg
```

---

## 4. Popular os Bancos de Dados

### 4.1. Seed Qdrant (Vector Database)

```bash
python scripts/seed_qdrant.py
```

Isso criará embeddings para 6 documentos legais de exemplo.

### 4.2. Seed Neo4j (Knowledge Graph)

```bash
python scripts/seed_neo4j.py
```

Isso criará um grafo com casos, leis e relacionamentos.

---

## 5. Iniciar a API

### Opção A: Usando Docker (Recomendado)

Se você já executou o `docker-compose up`, a API já deve estar rodando.

### Opção B: Desenvolvimento Local

```bash
# Ativar ambiente virtual
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Rodar API
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 6. Verificar se está funcionando

### 6.1. Health Check

```bash
curl http://localhost:8000/health
```

Resposta esperada:
```json
{
  "status": "healthy",
  "databases": {
    "qdrant": true,
    "neo4j": true,
    "redis": true
  },
  "version": "1.0.0"
}
```

### 6.2. Testar endpoint principal

```bash
curl -X POST http://localhost:8000/adjudicate \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Um inquilino deixou de pagar aluguel por 6 meses. O proprietário pode rescindir o contrato?",
    "anonymize": true,
    "enable_scot": true
  }'
```

---

## 7. Acessar Interfaces Web

### Neo4j Browser
- URL: http://localhost:7474
- Usuário: `neo4j`
- Senha: `judicial123`

### Qdrant Dashboard
- URL: http://localhost:6333/dashboard

### API Documentation (Swagger)
- URL: http://localhost:8000/docs

---

## 8. Comandos Úteis

### Parar todos os serviços
```bash
docker-compose -f docker/docker-compose.yml down
```

### Ver logs
```bash
# Todos os serviços
docker-compose -f docker/docker-compose.yml logs -f

# Serviço específico
docker-compose -f docker/docker-compose.yml logs -f api
```

### Rebuild da API após mudanças no código
```bash
docker-compose -f docker/docker-compose.yml up -d --build api
```

### Limpar tudo e recomeçar
```bash
docker-compose -f docker/docker-compose.yml down -v
docker-compose -f docker/docker-compose.yml up -d
```

---

## 9. Troubleshooting

### Problema: Ollama não consegue baixar modelo (sem GPU)

Edite `docker/docker-compose.yml` e remova a seção `deploy.resources` do serviço `ollama`.

### Problema: Out of Memory

Reduza os recursos nos serviços ou aumente a memória disponível para Docker.

### Problema: Qdrant não cria collection

Execute manualmente:
```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(host="localhost", port=6333)
client.create_collection(
    collection_name="judicial_cases",
    vectors_config=VectorParams(size=768, distance=Distance.COSINE)
)
```

### Problema: Neo4j não conecta

Verifique se a senha está correta no `.env` e se o serviço está healthy:
```bash
docker-compose -f docker/docker-compose.yml ps neo4j
```

---

## 10. Desenvolvimento

### Estrutura do Projeto
```
judicial-backend/
├── app/
│   ├── core/          # Configuração, database, logging
│   ├── models/        # Modelos Pydantic
│   ├── retrieval/     # HyPA-RAG (busca híbrida)
│   ├── reasoning/     # LSIM (raciocínio lógico)
│   ├── agents/        # LangGraph orchestrator
│   ├── privacy/       # Anonimização
│   └── main.py        # FastAPI app
├── docker/            # Docker configs
├── scripts/           # Seed scripts
└── tests/             # Testes unitários e integração
```

### Adicionar novos documentos ao Qdrant

Edite `scripts/seed_qdrant.py` e adicione ao `SAMPLE_DOCUMENTS`, depois execute:
```bash
python scripts/seed_qdrant.py
```

### Modificar o grafo Neo4j

Edite `scripts/seed_neo4j.py` e modifique o Cypher, depois execute:
```bash
python scripts/seed_neo4j.py
```

---

## 11. Próximos Passos

1. **Testar com dados reais**: Adicione suas próprias leis e jurisprudências
2. **Fine-tuning**: Ajuste os prompts em `app/reasoning/` para seu domínio específico
3. **Implementar autenticação**: Habilite `API_KEY_ENABLED=true` no `.env`
4. **Monitoramento**: Configure logs estruturados e métricas
5. **Testes**: Execute a suite de testes (quando implementada)

---

## Suporte

Para problemas ou dúvidas, consulte:
- Documentação da API: http://localhost:8000/docs
- Logs: `docker-compose logs -f`
- Arquivo README.md principal

---

**Desenvolvido com**: Python, FastAPI, LangGraph, Qdrant, Neo4j, Ollama
