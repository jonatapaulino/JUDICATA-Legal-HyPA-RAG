"""Run full ingestion (legislation + súmulas) then the extra health-precedent corpus, then print status."""
import subprocess, sys
py = sys.executable
for cmd in (["scripts/ingest_full_legislation.py", "--all", "--clear"],
            ["scripts/ingest_extra_corpus.py", "dataset/precedents/health_corpus.json"],
            ["scripts/ingest_full_legislation.py", "--status"]):
    print("=== RUN", " ".join(cmd), flush=True)
    r = subprocess.run([py] + cmd)
    print("=== RC", r.returncode, flush=True)
    if r.returncode != 0:
        sys.exit(r.returncode)
print("INGEST_DONE", flush=True)
