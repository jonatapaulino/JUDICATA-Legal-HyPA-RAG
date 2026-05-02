#!/usr/bin/env python3
"""
Extracts the self-curated evaluation queries from tests/a1_test_battery.py
into machine-readable CSV files for dataset publication (PeerJ requirement).

Output:
    dataset/queries_functional.csv      (T1, n=55)
    dataset/queries_classification.csv  (T2, n=25)
    dataset/queries_security.csv        (T3, n=35)
    dataset/queries_p2p.csv             (T4, n=25)
    dataset/queries_anonymization.csv   (T5, n=10)
    dataset/queries_edge_cases.csv      (T10, n=15)
    dataset/queries_all.csv             (consolidated, n=165)
"""
import ast
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "tests" / "a1_test_battery.py"
CATALOG_SOURCE = ROOT / "app" / "ingestion" / "planalto_scraper.py"
OUT = ROOT / "dataset"

DATASETS = {
    "FUNCTIONAL_QUERIES":     ("queries_functional.csv",     "T1"),
    "CLASSIFICATION_QUERIES": ("queries_classification.csv", "T2"),
    "SECURITY_ATTACKS":       ("queries_security.csv",       "T3"),
    "P2P_TRIGGERS":           ("queries_p2p.csv",            "T4"),
    "ANONYMIZATION_QUERIES":  ("queries_anonymization.csv",  "T5"),
    "EDGE_CASES":             ("queries_edge_cases.csv",     "T10"),
}


def safe_eval(node):
    """Like ast.literal_eval, but also supports str/int Mult and Add."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [safe_eval(e) for e in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(safe_eval(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return {safe_eval(k): safe_eval(v)
                for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -safe_eval(node.operand)
    if isinstance(node, ast.BinOp):
        left, right = safe_eval(node.left), safe_eval(node.right)
        if isinstance(node.op, ast.Mult): return left * right
        if isinstance(node.op, ast.Add):  return left + right
    raise ValueError(f"unsupported node: {ast.dump(node)}")


def extract_lists(source_path):
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in DATASETS:
                    found[target.id] = safe_eval(node.value)
    return found


def normalize_value(v):
    """Render lists as JSON for CSV portability; keep scalars as-is."""
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return v


def write_csv(path, rows, category):
    if not rows:
        return
    fields = ["id", "category"] + list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, r in enumerate(rows, 1):
            row_id = f"{category}.{i:03d}"
            w.writerow({"id": row_id, "category": category,
                        **{k: normalize_value(v) for k, v in r.items()}})


def write_consolidated(all_rows, path):
    fields = ["id", "category", "query", "domain", "complexity", "type",
              "expected", "expected_keywords", "expected_citations",
              "should_block", "should_detect", "pii_types",
              "name", "expect_error"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in all_rows:
            w.writerow({k: normalize_value(v) for k, v in r.items()})


CATALOG_FIELDS = ["id", "name", "type", "url", "date", "status",
                  "category", "tags"]


def extract_catalog(source_path):
    """Extract BRAZILIAN_LEGISLATION_CATALOG (list of LegislationMetadata calls)."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if (isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == "BRAZILIAN_LEGISLATION_CATALOG"):
            value = node.value
        elif (isinstance(node, ast.Assign)
              and any(isinstance(t, ast.Name)
                      and t.id == "BRAZILIAN_LEGISLATION_CATALOG"
                      for t in node.targets)):
            value = node.value
        else:
            continue
        if not isinstance(value, ast.List):
            return []
        items = []
        for call in value.elts:
            if not isinstance(call, ast.Call):
                continue
            row = {f: "" for f in CATALOG_FIELDS}
            for kw in call.keywords:
                if kw.arg in CATALOG_FIELDS:
                    try:
                        row[kw.arg] = safe_eval(kw.value)
                    except ValueError:
                        row[kw.arg] = ""
            items.append(row)
        return items
    return []


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    extracted = extract_lists(SOURCE)

    consolidated = []
    for var_name, (filename, category) in DATASETS.items():
        rows = extracted.get(var_name, [])
        out_path = OUT / filename
        write_csv(out_path, rows, category)
        print(f"  {filename}: {len(rows)} rows -> {out_path.relative_to(ROOT)}")
        for i, r in enumerate(rows, 1):
            consolidated.append({"id": f"{category}.{i:03d}",
                                 "category": category, **r})

    consolidated_path = OUT / "queries_all.csv"
    write_consolidated(consolidated, consolidated_path)
    print(f"\n  queries_all.csv: {len(consolidated)} rows -> "
          f"{consolidated_path.relative_to(ROOT)}")

    catalog = extract_catalog(CATALOG_SOURCE)
    catalog_path = OUT / "corpus_catalog.csv"
    with catalog_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CATALOG_FIELDS)
        w.writeheader()
        for row in catalog:
            w.writerow({k: normalize_value(v) for k, v in row.items()})
    print(f"  corpus_catalog.csv: {len(catalog)} rows -> "
          f"{catalog_path.relative_to(ROOT)}")

    print(f"\nDone. Queries: {len(consolidated)} | "
          f"Catalog entries: {len(catalog)}")


if __name__ == "__main__":
    main()
