# Self-curated Dataset — Soberania Judicial

This folder contains the self-curated dataset used to evaluate the
*Soberania Judicial* framework reported in the manuscript
"Soberania Judicial: Um Framework Neuro-Simbolico e Agentico para
Resiliencia Causal e Defensibilidade Juridica em Modelos de Linguagem"
(Sousa, 2026).

The dataset is organised in three layers, all reproducible from this repository:

1. **Knowledge corpus** — the legal documents ingested into the RAG pipeline.
2. **Evaluation queries** — the 165 prompts used in the 10-category test battery.
3. **Experimental outputs** — raw JSON results of all test executions.

---

## 1. Knowledge corpus

**Description.** A curated catalogue of Brazilian federal legislation and
binding precedents (sumulas) ingested into Qdrant (vector store) and Neo4j
(knowledge graph). The corpus was assembled programmatically from public,
public-domain government sources between **2026-02-09T22:49:03Z** and
**2026-02-09T23:15:04Z** (UTC), as recorded in `scripts/ingestion_stats.json`.

**Sources.**
- Legislation: Portal do Planalto, `http://www.planalto.gov.br/ccivil_03/`
  (Federal Government of Brazil — public domain, Lei 9.610/1998 art. 8)
- Sumulas: Supremo Tribunal Federal (`https://portal.stf.jus.br/`) and
  Superior Tribunal de Justica (`https://www.stj.jus.br/`)

**Ingestion summary** (from `scripts/ingestion_stats.json`):

| Source       | Fetched | Indexed |
|--------------|---------|---------|
| Legislation  | 77      | 75      |
| Sumulas      | 67      | 67      |
| **Total chunks (vectors)** | — | **10,374** |
| **Graph nodes (Neo4j)**    | — | **10,449** |

**Files.**
- `corpus_catalog.csv` — full catalogue of the 77 legislations targeted for
  ingestion, with the canonical Planalto URL of each.
- `../scripts/ingestion_stats.json` — machine-readable run record (start/end
  timestamps, per-source counts, errors).
- `../scripts/ingest_brasil_laws.py` and `../scripts/ingest_full_legislation.py`
  — the ingestion scripts that produced the corpus.

**`corpus_catalog.csv` schema.**

| Column   | Type   | Description |
|----------|--------|-------------|
| id       | string | Internal identifier (e.g. `CF88`, `CC2002`, `CPC2015`) |
| name     | string | Official name of the legal instrument |
| type     | string | `CF`, `CODIGO`, `LEI`, `DECRETO_LEI`, `LC`, `EC`, `MP` |
| url      | string | Canonical Planalto URL of the source document |
| date     | string | Publication date of the original act (`YYYY-MM-DD`) |
| status   | string | `vigente`, `revogada`, `parcialmente_revogada` |
| category | string | Legal domain (`constitucional`, `civil`, `penal`, ...) |
| tags     | JSON   | Free-form topical tags |

> **Reproducibility note.** The raw text of each statute is not redistributed
> here because (i) it is freely retrievable from the source URLs and (ii) the
> Planalto HTML changes over time. Re-running `scripts/ingest_full_legislation.py
> --all` from a clean Qdrant/Neo4j stack will rebuild the corpus.

---

## 2. Evaluation queries

**Description.** 165 prompts authored by the authors and grouped into 10 test
categories (T1–T10). They probe functional accuracy, complexity classification,
adversarial robustness, privacy, and edge-case handling.

**Files.**

| File                          | Category | n   | Purpose |
|-------------------------------|----------|----:|---------|
| `queries_functional.csv`      | T1       |  55 | Domain-grounded legal questions across 11 areas |
| `queries_classification.csv`  | T2       |  25 | Ground-truth complexity labels (BAIXA/MEDIA/ALTA) |
| `queries_security.csv`        | T3       |  35 | Adversarial inputs targeting the Guardian Agent |
| `queries_p2p.csv`             | T4       |  25 | Backdoor-trigger probes for the P2P defense |
| `queries_anonymization.csv`   | T5       |  10 | Synthetic prompts containing PII for LOPSIDED |
| `queries_edge_cases.csv`      | T10      |  15 | Anomalous/degenerate inputs |
| `queries_all.csv`             | all      | 165 | Consolidated view (superset of columns) |

> Categories T6 (Toulmin completeness), T7 (performance), T8 (SCOT validation)
> and T9 (concurrency stress) re-use queries from T1 and are not separate
> input lists — see the manuscript Methods section.

**Common columns (all files).**

| Column | Type | Description |
|--------|------|-------------|
| id       | string | Stable identifier `T{category}.{seq:03d}` (e.g. `T1.001`) |
| category | string | Test category code (`T1` … `T10`) |
| query    | string | The prompt sent to the system, verbatim |

**Per-file extra columns.**

`queries_functional.csv` (T1)

| Column              | Type        | Description |
|---------------------|-------------|-------------|
| domain              | string      | Legal domain (consumidor, penal, civil, ...) |
| complexity          | string      | Author-assigned complexity (BAIXA/MEDIA/ALTA) |
| expected_keywords   | JSON list   | Terms expected to appear in a correct answer |
| expected_citations  | JSON list   | Statutory references expected in a correct answer |

`queries_classification.csv` (T2)

| Column   | Type   | Description |
|----------|--------|-------------|
| expected | string | Ground-truth complexity label (BAIXA/MEDIA/ALTA) |

`queries_security.csv` (T3)

| Column        | Type    | Description |
|---------------|---------|-------------|
| type          | string  | `jailbreak`, `sql_injection`, `xss`, `template_injection`, `instruction_bypass`, `leetspeak`, `legitimate` |
| should_block  | boolean | Expected Guardian decision (True = block) |

`queries_p2p.csv` (T4)

| Column         | Type    | Description |
|----------------|---------|-------------|
| type           | string  | `lexical`, `syntactic`, `semantic`, `legitimate` |
| should_detect  | boolean | Expected P2P trigger detection |

`queries_anonymization.csv` (T5)

| Column     | Type      | Description |
|------------|-----------|-------------|
| pii_types  | JSON list | PII categories present (`nome`, `cpf`, `cnpj`, `processo`, `email`, `telefone`, `local`, `endereco`, `oab`, `data`, `organizacao`) |

> **Synthetic data note.** All names, CPF/CNPJ/RG numbers and case numbers in
> T5 are fictitious and were generated by the authors solely for evaluation;
> they do not refer to real individuals or proceedings.

`queries_edge_cases.csv` (T10)

| Column        | Type    | Description |
|---------------|---------|-------------|
| name          | string  | Short label of the edge condition |
| expect_error  | boolean | Whether the API is expected to reject the input |

---

## 3. Experimental outputs

Raw, machine-readable outputs of every test execution are checked into the
repository under `tests/results/`:

| File | Description |
|------|-------------|
| `tests/results/a1_results_20260210_131620.json`       | Full A1 battery results (per-query metrics) |
| `tests/results/a1_results_20260210_131620_fixed.json` | Re-run with classification fix applied |
| `tests/results/a1_report_20260210_131620.md`          | Human-readable summary report |
| `tests/results/a1_run_log.txt`                        | Stdout of the A1 run |
| `tests/results/a1_rerun_log.txt`                      | Stdout of the re-run |
| `tests/results/test_results_20260210_003205.json`     | Earlier exploratory run |
| `tests/results/test_report_20260210_003205.md`        | Earlier report |

---

## 4. Reproducing the dataset

```bash
# 1. Bring up Qdrant, Neo4j, Redis, and Ollama (Qwen2.5:14B)
cd docker && docker-compose up -d

# 2. Build the legal corpus
python scripts/ingest_full_legislation.py --all

# 3. Start the API
python app/main.py

# 4. Run the full A1 evaluation battery (writes to tests/results/)
python tests/a1_test_battery.py

# 5. Re-export the CSVs in this folder
python dataset/build_dataset.py
```

Hardware reference: the published runs were executed on CPU inference of
Qwen2.5:14B (Q4_K_M) via Ollama. Per-query latency averaged 19.9 s (BAIXA),
23.7 s (MEDIA), and 32.6 s (ALTA).

---

## 5. License

- **Source code and ingestion scripts:** MIT License (see `../LICENSE`).
- **Evaluation queries (this folder):** CC BY 4.0 — reuse permitted with
  attribution to the manuscript.
- **Brazilian legislation (corpus content):** Public domain under
  Lei 9.610/1998 art. 8. The redistributed metadata in `corpus_catalog.csv`
  references the original Planalto URLs.

---

## 6. Citation

If you reuse this dataset, please cite:

> Sousa, D. S. V. (2026). *Soberania Judicial: Um Framework Neuro-Simbolico e
> Agentico para Resiliencia Causal e Defensibilidade Juridica em Modelos de
> Linguagem.* Manuscript submitted to PeerJ Computer Science.

---

## 7. Contact

- **Author:** Delvek da S. V. de Sousa
- **Affiliation:** Universidade Federal do Tocantins (UFT) — Ciencia da Computacao
- **Repository:** https://github.com/Labcity-LLM/LLM-data-poisoning
