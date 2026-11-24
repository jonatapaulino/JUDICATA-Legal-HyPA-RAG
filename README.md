[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19489308.svg)](https://doi.org/10.5281/zenodo.19489308)

# JUDICATA
## Pipeline aberto e local de apoio à fundamentação jurídica com verificação de fontes (Direito brasileiro)

> **Escopo.** O JUDICATA é uma ferramenta de **apoio à pesquisa e à fundamentação** para Defensorias Públicas e
> assessorias (análise inicial de casos). **Não decide casos, não substitui a decisão judicial nem a
> orientação de um profissional.** Cada resposta é um rascunho a ser verificado por um profissional habilitado.
> O uso por tribunais para formular juízos conclusivos sobre fatos concretos é de alto risco nos termos da
> Resolução CNJ 615/2025 (Anexo, AR4).

> **Revisão PLOS ONE (PONE-D-26-42993).** O código e os resultados correspondentes ao manuscrito revisado
> estão neste repositório a partir da tag `v2.0.2-frozen` (sistema congelado) e na pasta
> [`evaluation/`](evaluation/) (scripts, saídas armazenadas e `results/RESULTS.md`). Ver a seção
> [Reprodução da avaliação](#-reprodução-da-avaliação-plos-one).

**Autores**: Delvek da S. V. de Sousa, Jonatã P. Costa 
**Copyright**: © 2025 Delvek da S. V. de Sousa and Jonatã P. Costa  
**Versão**: 1.0.0  
**Licença**: MIT

---

## 📋 Sobre o Projeto

Pipeline LangGraph que combina recuperação híbrida sobre legislação federal e súmulas, uma camada de
raciocínio Fato–Regra–Conclusão (LSIM), defesas baseadas em regras, pseudonimização de dados pessoais
**antes** de qualquer chamada a modelo, trilha de auditoria por etapa e saída no modelo de Toulmin com
**verificação das fontes citadas** e hierarquia de fontes (SV/RG/repetitivo > CF > lei > súmula > orientação).
Todos os modelos rodam localmente via Ollama; nenhuma configuração de referência usa serviço em nuvem.

### Características Principais

- **HyPA-RAG**: recuperação densa (BERTimbau-Large/Qdrant) + esparsa (BM25) + grafo (Neo4j, busca por palavra-chave), fusão RRF com pesos por complexidade
- **LSIM**: cadeia Fato–Regra–Conclusão (modela no máximo a justificação interna)
- **Verificação de Backing**: todo dispositivo citado é conferido contra os documentos recuperados e contra o status de vigência; o Qualifier deriva dessa verificação
- **Guardian**: 29 expressões regulares de entrada/saída (filtro inicial; frágil a paráfrases — ver avaliação)
- **P2P**: detector de gatilhos por regras (não altera nem "vacina" o modelo)
- **RAG Defender**: filtro de passagens anômalas por TF-IDF
- **SCOT**: validação **posterior** do raciocínio por LLM (fail-closed)
- **Pseudonimização na entrada**: nomes de pessoas naturais, CPF, RG, e-mail, telefone e número CNJ
- **Trilha de auditoria**: estado de cada nó gravado em SQLite (`data/audit/checkpoints.sqlite`)

---

## 🚀 Quick Start

### Pré-requisitos

- Python 3.10+
- Docker & Docker Compose
- 16GB+ RAM (recomendado)

### Instalação

```bash
# 1. Crie ambiente virtual
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 2. Instale dependências
pip install -r requirements.txt

# 3. Configure .env
cp .env.example .env

# 4. Suba Docker services
cd docker && docker-compose up -d

# 5. Execute o servidor
python app/main.py
```

API: **http://localhost:8000**  
Docs: **http://localhost:8000/docs**

---

## 📡 Endpoints da API

### Principal

#### `POST /analyze`
Análise com argumento Toulmin e fontes verificadas (apoio à fundamentação; não é decisão).

**Request**:
```json
{
  "query": "Um inquilino deixou de pagar 6 meses de aluguel. O proprietário pode rescindir?",
  "anonymize": true,
  "enable_scot": true
}
```

**Response**:
```json
{
  "claim": "Há fundamento para a ação de despejo por falta de pagamento...",
  "data": ["Inadimplência de 6 meses"],
  "warrant": "A falta de pagamento do aluguel autoriza o desfazimento da locação",
  "backing": "Lei 8.245/1991, art. 9º, III (fonte recuperada)",
  "rebuttal": "Purga da mora (art. 62, II) ...",
  "qualifier": "PROVAVEL",
  "qualifier_basis": "1/1 dispositivos citados constam das fontes recuperadas.",
  "citation_check": {"cited": ["ART:8245:9"], "grounded": ["ART:8245:9"], "ungrounded": [], "revoked": []},
  "disclaimer": "Apoio à pesquisa e à fundamentação. Não constitui decisão ...",
  "trace_id": "req_abc123",
  "processing_time_ms": 1234
}
```

---

### API v1 - Para Frontend

#### `POST /api/v1/classify`
Classifica complexidade sem processar.

```json
// Request
{
  "query": "Qual o prazo para recurso?"
}

// Response
{
  "complexity": "MEDIA",
  "score": 3,
  "rag_params": {
    "k": 8,
    "use_graph": true
  }
}
```

**Use Case**: Mostrar tempo estimado de processamento.

---

#### `POST /api/v1/validate`
Valida texto para injection/XSS.

```json
// Request
{
  "text": "Ignore as instruções anteriores",
  "strict_mode": true
}

// Response
{
  "safe": false,
  "reason": "Blocked patterns detected",
  "blocked_patterns": ["ignore as instruções"]
}
```

**Use Case**: Validar input antes de enviar.

---

#### `GET /api/v1/status`
Status de todos os serviços.

```json
{
  "api_status": "operational",
  "services": {
    "qdrant": {"status": "healthy"},
    "neo4j": {"status": "healthy"},
    "redis": {"status": "healthy"}
  }
}
```

**Use Case**: Dashboard de saúde do sistema.

---

#### `GET /health`
Health check básico.

```json
{
  "status": "healthy",
  "databases": {
    "qdrant": true,
    "neo4j": true
  }
}
```

---

## 🧪 Testes

Testes unitários: `pytest tests/unit -q` (100 testes na versão congelada).

```bash
# Executar todos
pytest tests/unit/ -v

# Por componente
pytest tests/unit/test_guardian.py -v          # 37 testes
pytest tests/unit/test_query_classifier.py -v  # 35 testes
pytest tests/unit/test_rag_defender.py -v      # 20 testes
```

---

## 📦 Dataset interno (versão anterior)

O conjunto interno de 165 queries ([`dataset/`](dataset/)) foi usado durante o desenvolvimento e algumas
regras foram ajustadas após inspecionar falhas nele (commit `475cc9c`). Ele **não** é usado como conjunto de
teste na revisão; os resultados nele são reportados apenas como conjunto de desenvolvimento.
See [`dataset/DATASET.md`](dataset/DATASET.md) for the full data dictionary,
sources, and reproduction instructions.

```bash
# Re-export the CSVs from source code
python dataset/build_dataset.py
```

---

## 🔧 Configuração (.env)

```bash
# API
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# Databases
QDRANT_HOST=localhost
NEO4J_URI=bolt://localhost:7687
REDIS_HOST=localhost

# LLM
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2

# Security
GUARDIAN_ENABLED=true
GUARDIAN_STRICT_MODE=true

# RAG
RAG_TOP_K_LOW=3
RAG_TOP_K_MEDIUM=8
RAG_TOP_K_HIGH=15
```

---

## 🛡️ Segurança

As defesas são filtros baseados em regras e **não constituem garantia de segurança**. Na avaliação com
ataques de terceiros (não vistos ao escrever as regras), a taxa de detecção é baixa — ver
`evaluation/results/RESULTS.md`. Ataques via corpus (poisoning) não foram avaliados.

---

## 📊 Performance

Latências medidas estão em `evaluation/results/RESULTS.md` (pipeline completo com Qwen2.5 14B local:
dezenas de segundos por consulta numa RTX 5090 Laptop).

---

## 📚 Documentação Completa

**Swagger UI**: http://localhost:8000/docs  
**ReDoc**: http://localhost:8000/redoc

Documentação interativa com:
- Todos os endpoints
- Schemas request/response
- Exemplos de uso
- Testador integrado

---

## 🐳 Docker

```bash
# Subir serviços
docker-compose up -d

# Logs
docker-compose logs -f api

# Parar
docker-compose down
```

---

## 📝 Licença

**MIT License**

Copyright (c) 2025 Delvek da S. V. de Sousa, 
Jonatã P. Costa

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

---

## 📞 Contato

**Autores**: Delvek da S. V. de Sousa, Jonatã P. Costa

---

## 🎯 Endpoints Resumidos

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/analyze` | POST | Argumento Toulmin com fontes verificadas |
| `/api/v1/classify` | POST | Classificar query |
| `/api/v1/validate` | POST | Validar texto |
| `/api/v1/status` | GET | Status de serviços |
| `/health` | GET | Health check |
| `/` | GET | Info da API |
| `/docs` | GET | Documentação Swagger |

---

**Desenvolvido por Delvek da S. V. de Sousa and Jonatã P. Costa © 2025**


---

## 🔁 Reprodução da avaliação (PLOS ONE)

```bash
git checkout v2.0.2-frozen
pip install -r requirements.txt
python scripts/run_ingest_all.py            # corpus: legislação + súmulas + documentos de saúde
python evaluation/build_sets.py             # conjuntos externos (OAB, oab-bench, ataques) + casos Temas 6/1234
python evaluation/translate_attacks.py      # amostra de ataques traduzida (tradução automática, declarada)
python evaluation/security_eval.py          # E1: defesas em ataques de terceiros (sem LLM)
python evaluation/job_queue.py              # E2–E5: condições, ablações, extração, juízes, auditoria de PII
python evaluation/analyze.py                # todas as tabelas -> evaluation/results/RESULTS.md
```

Números, tabelas e figuras do manuscrito revisado (a partir das saídas armazenadas em `evaluation/results`,
sem chamar nenhum modelo; tag `v2.1.2-plos-revision`):

```bash
git checkout v2.1.2-plos-revision
python evaluation/make_numbers.py  --out <pasta do manuscrito>   # numeros.csv + macros \nm{...}
python evaluation/make_tables.py   --out <pasta do manuscrito>   # tables/tab_*.tex
python evaluation/make_figures.py  --out <pasta do manuscrito>   # figures/Fig4..Fig11 (PDF e TIFF)
```
Os conjuntos externos (`evaluation/data/`) não estão no repositório: são reconstruídos das fontes públicas
por `evaluation/build_sets.py` e mantêm as licenças originais.
Modelos (Ollama, locais): `qwen2.5:14b`, `mistral:7b` (sistemas avaliados); `gemma3:27b`, `llama3.1:8b` (juízes).
