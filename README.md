# Backend de Soberania Judiciária
## Sistema Neuro-Simbólico e Agêntico para Raciocínio Jurídico
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19489309.svg)](https://doi.org/10.5281/zenodo.19489309)

**Autores**: [Anonymized for blind review] 
**Copyright**: © 2026 [Authors]  
**Versão**: 1.0.0  
**Licença**: [MIT](LICENSE)

---

## 📋 Sobre o Projeto

Sistema backend completo para raciocínio jurídico automatizado utilizando arquitetura neuro-simbólica e agêntica. Combina recuperação de informação (RAG) com raciocínio lógico (LSIM) para fornecer fundamentações jurídicas estruturadas no modelo Toulmin.

### Características Principais

- **HyPA-RAG**: Hybrid Parallel Augmented RAG (dense + sparse + graph retrieval)
- **LSIM**: Logical-Semantic Integration Module para raciocínio estruturado
- **Guardian Agent**: Zero Trust security layer (anti-injection, anti-jailbreak)
- **RAG Defender**: Proteção contra data poisoning com TF-IDF clustering
- **Toulmin Model**: Argumentação estruturada (Claim, Data, Warrant, Backing, Rebuttal, Qualifier)
- **SCOT**: Safety Chain-of-Thought validation
- **LOPSIDED**: Local Privacy with Selective Identification Erasure
- **LangGraph Orchestration**: Workflow agêntico com state machine

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

#### `POST /adjudicate`
Raciocínio jurídico completo.

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
  "claim": "O proprietário pode rescindir o contrato...",
  "data": ["Inadimplência de 6 meses", "Lei 8.245/91 Art. 9º"],
  "warrant": "Rescisão permitida por inadimplência",
  "backing": "Jurisprudência do STJ...",
  "rebuttal": "Embora haja defesas possíveis...",
  "qualifier": "CERTO",
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

**92/92 testes passando (100%)**

```bash
# Executar todos
pytest tests/unit/ -v

# Por componente
pytest tests/unit/test_guardian.py -v          # 37 testes
pytest tests/unit/test_query_classifier.py -v  # 35 testes
pytest tests/unit/test_rag_defender.py -v      # 20 testes
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

### Guardian Agent
Bloqueia:
- Injection attacks
- XSS/SQL injection
- Jailbreak attempts

### RAG Defender
- Anti-poisoning via TF-IDF
- Filtra documentos anômalos

### SCOT
- Valida raciocínio do LLM
- Detecta alucinações

---

## 📊 Performance

| Complexidade | Tempo        | Docs Recuperados |
|--------------|--------------|------------------|
| BAIXA        | ~500ms       | 3-5              |
| MEDIA        | ~1500ms      | 8-12             |
| ALTA         | ~3000ms      | 15-20            |

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

[Author 2]

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

**Autores**: [Anonymized for blind review]

---

## 🎯 Endpoints Resumidos

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/adjudicate` | POST | Raciocínio jurídico completo |
| `/api/v1/classify` | POST | Classificar query |
| `/api/v1/validate` | POST | Validar texto |
| `/api/v1/status` | GET | Status de serviços |
| `/health` | GET | Health check |
| `/` | GET | Info da API |
| `/docs` | GET | Documentação Swagger |

---

JUDICATA: Sovereign Neuro-Symbolic Legal RAG Framework > Developed by Jonatã Paulino, Delvek da S. V. de Sousa, Julio, Cauã, and Professor Renato Frances (Advisor) © 2026.

This project is licensed under the MIT License - see the LICENSE file for details.