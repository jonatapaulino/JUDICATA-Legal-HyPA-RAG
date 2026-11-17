#!/usr/bin/env python3
"""
Supporting tables S1 (legislation) and S2 (súmulas and precedent documents),
generated from what is ACTUALLY indexed in Qdrant (not from the catalog alone).
Outputs evaluation/results/S1_legislation.csv, S2_sumulas.csv and LaTeX versions.
"""
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from qdrant_client import QdrantClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.ingestion.planalto_scraper import BRAZILIAN_LEGISLATION_CATALOG as CAT  # noqa: E402

RES = Path(__file__).parent / "results"


def tex_escape(s):
    return str(s).replace("&", r"\&").replace("%", r"\%").replace("_", r"\_").replace("#", r"\#")


def main():
    c = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    arts, sums, extra = Counter(), [], []
    off = None
    while True:
        pts, off = c.scroll(settings.qdrant_collection_name, limit=1000, offset=off, with_payload=True, with_vectors=False)
        for p in pts:
            md = (p.payload or {}).get("metadata", {})
            t = md.get("type")
            if t == "legislation":
                arts[md.get("law_id")] += 1
            elif t == "sumula" and md.get("source") != "extra":
                sums.append(md)
            else:
                extra.append(md)
        if off is None:
            break
    RES.mkdir(parents=True, exist_ok=True)
    rows = []
    for m in CAT:
        rows.append({"id": m.id, "name": m.name, "type": m.type, "category": m.category, "status": m.status,
                     "url": m.url, "articles_indexed": arts.get(m.id, 0)})
    with open(RES / "S1_legislation.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    srows = sorted(({"court": s.get("court"), "kind": s.get("sumula_type") or "comum", "number": s.get("number"),
                     "status": s.get("status", "")} for s in sums), key=lambda r: (str(r["court"]), str(r["kind"]),
                                                                                  int(str(r["number"]).split("-")[0]) if str(r["number"]).split("-")[0].isdigit() else 0))
    with open(RES / "S2_sumulas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["court", "kind", "number", "status"])
        w.writeheader()
        w.writerows(srows)
    with open(RES / "S3_extra_documents.csv", "w", newline="", encoding="utf-8") as f:
        keys = sorted({k for e in extra for k in e if isinstance(e.get(k), (str, int, float))})
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(extra)

    # LaTeX
    with open(RES / "S1_legislation.tex", "w", encoding="utf-8") as f:
        f.write("\\begin{longtable}{p{0.55\\linewidth}p{0.12\\linewidth}p{0.16\\linewidth}r}\n"
                "\\hline\\textbf{Statute} & \\textbf{Type} & \\textbf{Status} & \\textbf{Articles}\\\\\\hline\\endhead\n")
        for r in rows:
            f.write(f"{tex_escape(r['name'])} & {tex_escape(r['type'])} & {tex_escape(r['status'])} & {r['articles_indexed']}\\\\\n")
        f.write(f"\\hline\\textbf{{Total ({len(rows)} statutes)}} & & & {sum(r['articles_indexed'] for r in rows)}\\\\\\hline\n\\end{{longtable}}\n")
    by = defaultdict(list)
    for s in srows:
        by[(s["court"], s["kind"])].append(str(s["number"]))
    with open(RES / "S2_sumulas.tex", "w", encoding="utf-8") as f:
        f.write("\\begin{longtable}{p{0.12\\linewidth}p{0.15\\linewidth}r p{0.55\\linewidth}}\n"
                "\\hline\\textbf{Court} & \\textbf{Kind} & \\textbf{n} & \\textbf{Numbers}\\\\\\hline\\endhead\n")
        for (court, kind), nums in sorted(by.items(), key=lambda x: (str(x[0][0]), str(x[0][1]))):
            f.write(f"{tex_escape(court)} & {tex_escape(kind)} & {len(nums)} & {', '.join(nums)}\\\\\n")
        f.write(f"\\hline\\textbf{{Total}} & & {len(srows)} & \\\\\\hline\n\\end{{longtable}}\n")
    print("laws", len(rows), "indexed laws", sum(1 for r in rows if r["articles_indexed"]), "articles", sum(arts.values()),
          "sumulas", len(srows), Counter((s['court'], s['kind']) for s in srows), "extra", len(extra))


if __name__ == "__main__":
    main()
