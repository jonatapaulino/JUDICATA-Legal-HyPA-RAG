#!/usr/bin/env python3
"""
Sequential job queue for the full evaluation (every step is resumable, so the
queue can be restarted at any point). Usage: python evaluation/job_queue.py [stage ...]
"""
import subprocess
import sys
import time

PY = sys.executable
MODELS = {"qwen": "qwen2.5:14b", "mistral": "mistral:7b"}
MAIN = "raw,vanilla_rag,rag_toulmin,judicata"
ABL = ",".join(f"judicata-{a}" for a in
               ("no_lsim", "no_scot", "no_kg", "fixed_weights", "no_hierarchy", "no_backing_verification"))
JUDGES = ("gemma3:27b", "llama3.1:8b")  # families different from the systems under test


def run_cmds():
    for tag, m in MODELS.items():
        yield ("temas", tag, ["evaluation/run_eval.py", "--task", "temas", "--model", m, "--conditions", MAIN + "," + ABL,
                              "--out", f"evaluation/results/temas_{tag}.jsonl"])
    for tag, m in MODELS.items():
        yield ("oab1", tag, ["evaluation/run_eval.py", "--task", "oab1", "--model", m, "--conditions", MAIN,
                             "--out", f"evaluation/results/oab1_{tag}.jsonl"])
    for tag, m in MODELS.items():
        yield ("oab2", tag, ["evaluation/run_eval.py", "--task", "oab2", "--model", m, "--conditions", MAIN,
                             "--out", f"evaluation/results/oab2_{tag}.jsonl"])
    yield ("oab1abl", "qwen", ["evaluation/run_eval.py", "--task", "oab1", "--model", MODELS["qwen"], "--conditions", ABL,
                               "--limit", "100", "--out", "evaluation/results/oab1_qwen.jsonl"])
    for t in ("temas", "oab1"):
        for tag in MODELS:
            yield ("extract", tag, ["evaluation/extract_answers.py", "--results", f"evaluation/results/{t}_{tag}.jsonl", "--task", t])
    for j in JUDGES:
        for tag in MODELS:
            yield ("judge", tag, ["evaluation/judge_oab2.py", "--results", f"evaluation/results/oab2_{tag}.jsonl", "--judge", j])
    yield ("pii", "qwen", ["evaluation/pii_audit.py", MODELS["qwen"]])
    yield ("analyze", "-", ["evaluation/analyze.py"])


def main():
    stages = set(sys.argv[1:])
    for stage, tag, cmd in run_cmds():
        if stages and stage not in stages:
            continue
        t0 = time.time()
        print(f"=== {time.strftime('%H:%M:%S')} START {stage}/{tag}: {' '.join(cmd)}", flush=True)
        rc = subprocess.run([PY] + cmd).returncode
        print(f"=== {time.strftime('%H:%M:%S')} END {stage}/{tag} rc={rc} {round((time.time()-t0)/60, 1)} min", flush=True)
    print("QUEUE_DONE", flush=True)


if __name__ == "__main__":
    main()
