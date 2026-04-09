"""
Teste simples de imports - apenas sintaxe, sem carregar modelos pesados.

"""
import sys

print("Testing basic imports...")

# Core
try:
    from app.core import config
    print("[OK] app.core.config")
except Exception as e:
    print(f"[FAIL] app.core.config: {e}")

# Models
try:
    from app.models import internal, requests, responses
    print("[OK] app.models")
except Exception as e:
    print(f"[FAIL] app.models: {e}")

# Agents state
try:
    from app.agents import state
    print("[OK] app.agents.state")
except Exception as e:
    print(f"[FAIL] app.agents.state: {e}")

# Guardian (não precisa de modelos ML)
try:
    from app.agents import guardian
    print("[OK] app.agents.guardian")
except Exception as e:
    print(f"[FAIL] app.agents.guardian: {e}")

# Query classifier (não precisa de modelos ML)
try:
    from app.retrieval import query_classifier
    print("[OK] app.retrieval.query_classifier")
except Exception as e:
    print(f"[FAIL] app.retrieval.query_classifier: {e}")

print("\nImports basics funcionaram!")
