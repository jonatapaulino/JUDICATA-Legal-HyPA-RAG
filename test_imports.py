"""
Script para testar imports de todos os módulos.
Verifica se há erros de sintaxe ou imports circulares.

Author: Delvek da S. V. de Sousa
Copyright (c) 2025 Delvek da S. V. de Sousa
"""
import sys
import traceback

def test_import(module_name):
    """Testa import de um módulo."""
    try:
        __import__(module_name)
        print(f"[OK] {module_name}")
        return True
    except Exception as e:
        print(f"[FAIL] {module_name}")
        print(f"  Erro: {e}")
        traceback.print_exc()
        return False

def main():
    """Testa todos os imports."""
    print("=" * 60)
    print("TESTE DE IMPORTS - Backend Judicial")
    print("=" * 60)

    modules_to_test = [
        # Core
        "app.core.config",
        "app.core.logging",
        "app.core.database",

        # Models
        "app.models.internal",
        "app.models.requests",
        "app.models.responses",

        # Retrieval
        "app.retrieval.embeddings",
        "app.retrieval.query_classifier",
        "app.retrieval.rag_defender",
        "app.retrieval.hypa_rag",

        # Reasoning
        "app.reasoning.fact_extractor",
        "app.reasoning.rule_matcher",
        "app.reasoning.lsim_engine",
        "app.reasoning.toulmin",

        # Agents
        "app.agents.state",
        "app.agents.tools",
        "app.agents.guardian",
        "app.agents.orchestrator",

        # Privacy
        "app.privacy.ner_legal",
        "app.privacy.anonymizer",

        # Main
        "app.main",
    ]

    results = []
    for module in modules_to_test:
        print(f"\nTestando: {module}")
        success = test_import(module)
        results.append((module, success))

    print("\n" + "=" * 60)
    print("RESUMO DOS TESTES")
    print("=" * 60)

    passed = sum(1 for _, success in results if success)
    failed = len(results) - passed

    print(f"\nTotal: {len(results)}")
    print(f"[+] Passou: {passed}")
    print(f"[-] Falhou: {failed}")

    if failed > 0:
        print("\n[!] MODULOS COM ERRO:")
        for module, success in results:
            if not success:
                print(f"  - {module}")
        sys.exit(1)
    else:
        print("\n[SUCCESS] Todos os imports funcionaram!")
        sys.exit(0)

if __name__ == "__main__":
    main()
