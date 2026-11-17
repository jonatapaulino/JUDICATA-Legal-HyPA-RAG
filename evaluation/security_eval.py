#!/usr/bin/env python3
"""
E1 - Defence layers on held-out data (no LLM involved).

Guardian (input validation) and the P2P trigger detector are deterministic
rule-based components; they are evaluated on prompts written by third parties
and never seen while the rules were written (system frozen at v2.0.1-frozen):

  * attacks / benign prompts from deepset/prompt-injections,
    Lakera/gandalf_ignore_instructions and jackhhao/jailbreak-classification
    (original language and a machine-translated PT sample);
  * 2,210 real Brazilian legal questions (OAB exams) as legitimate traffic;
  * the authors' original in-house set (dataset/queries_security.csv and
    queries_p2p.csv), reported separately because rules were revised after
    observing failures on it (commit 475cc9c).

Outputs evaluation/results/security_summary.json and security_items.jsonl.
"""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.agents.guardian import GuardianAgent  # noqa: E402
from app.defense.p2p_defense import P2PDefense  # noqa: E402

DATA = Path(__file__).parent / "data"
RES = Path(__file__).parent / "results"
ROOT = Path(__file__).resolve().parent.parent


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(p, 4), round(max(0, c - h), 4), round(min(1, c + h), 4))


def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")] if p.exists() else []


def main():
    g, p2p = GuardianAgent(), P2PDefense()
    sets = defaultdict(list)
    for r in load_jsonl(DATA / "security_external.jsonl"):
        sets[f"{r['source']}|orig"].append(r)
    for r in load_jsonl(DATA / "security_attacks_pt.jsonl"):
        sets[f"{r['source']}|pt-mt"].append(r)
    for r in load_jsonl(DATA / "benign_legal.jsonl"):
        sets["oab_exams|legit"].append(r)
    for r in csv.DictReader(open(ROOT / "dataset/queries_security.csv", encoding="utf-8")):
        sets["inhouse_security|dev"].append({"id": r["id"], "text": r["query"], "attack": r["should_block"] == "True"})
    for r in csv.DictReader(open(ROOT / "dataset/queries_p2p.csv", encoding="utf-8")):
        sets["inhouse_p2p|dev"].append({"id": r["id"], "text": r["query"], "attack": r["should_detect"] == "True"})

    RES.mkdir(parents=True, exist_ok=True)
    summary = {}
    with open(RES / "security_items.jsonl", "w", encoding="utf-8") as f:
        for name, rows in sorted(sets.items()):
            cnt = defaultdict(lambda: [0, 0])  # key -> [flagged, total]
            for r in rows:
                gv = not g.validate_input(r["text"]).safe
                pv = p2p.get_safe_response(r["text"]) is not None
                both = gv or pv
                lab = "attack" if r["attack"] else "benign"
                for comp, v in (("guardian", gv), ("p2p", pv), ("combined", both)):
                    cnt[(comp, lab)][0] += int(v)
                    cnt[(comp, lab)][1] += 1
                f.write(json.dumps({"set": name, "id": r["id"], "attack": r["attack"], "guardian": gv, "p2p": pv},
                                   ensure_ascii=False) + "\n")
            summary[name] = {
                f"{comp}_{'TPR' if lab == 'attack' else 'FPR'}": {"k": k, "n": n, "rate_ci95": wilson(k, n)}
                for (comp, lab), (k, n) in cnt.items()}
    json.dump(summary, open(RES / "security_summary.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for name, s in summary.items():
        print(name, {k: v["rate_ci95"][0] for k, v in s.items()}, {k: v["n"] for k, v in s.items()})


if __name__ == "__main__":
    main()
