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
    def ev(task, tag, conds, out, extra=()):
        return (task, tag, ["evaluation/run_eval.py", "--task", task, "--model", MODELS[tag], "--conditions", conds,
                            "--out", f"evaluation/results/{out}.jsonl", *extra])
    OAB2 = ("--no-pieces", "--sample", "150")
    for tag in ("qwen", "mistral"):           # main comparison first, primary model first
        yield ev("temas", tag, MAIN, f"temas_{tag}")
        yield ev("oab1", tag, MAIN, f"oab1_{tag}")
        yield ev("oab2", tag, MAIN, f"oab2_{tag}", OAB2)
    for tag in ("qwen", "mistral"):           # ablations
        yield ev("temas", tag, ABL, f"temas_{tag}")
    yield ev("oab1", "qwen", ABL, "oab1_qwen", ("--sample", "100"))
    for t in ("temas", "oab1"):
        for tag in MODELS:
            yield ("extract", tag, ["evaluation/extract_answers.py", "--results", f"evaluation/results/{t}_{tag}.jsonl", "--task", t])
    for j in JUDGES:
        for tag in MODELS:
            yield ("judge", tag, ["evaluation/judge_oab2.py", "--results", f"evaluation/results/oab2_{tag}.jsonl", "--judge", j])
    yield ("pii", "qwen", ["evaluation/pii_audit.py", MODELS["qwen"]])
    yield ("analyze", "-", ["evaluation/analyze.py"])


def supp_cmds():
    """Supplementary baseline (added after the main runs; see run_eval.run_rag_toulmin_jq):
    RAG + Toulmin prompt with JUDICATA's own retrieval input, then extraction, judges, analysis."""
    OAB2 = ("--no-pieces", "--sample", "150")
    for tag in ("qwen", "mistral"):
        yield ("supp", tag, ["evaluation/run_eval.py", "--task", "temas", "--model", MODELS[tag], "--conditions", "rag_toulmin_jq", "--out", f"evaluation/results/temas_{tag}.jsonl"])
        yield ("supp", tag, ["evaluation/run_eval.py", "--task", "oab1", "--model", MODELS[tag], "--conditions", "rag_toulmin_jq", "--out", f"evaluation/results/oab1_{tag}.jsonl"])
        yield ("supp", tag, ["evaluation/run_eval.py", "--task", "oab2", "--model", MODELS[tag], "--conditions", "rag_toulmin_jq", "--out", f"evaluation/results/oab2_{tag}.jsonl", *OAB2])
    for t in ("temas", "oab1"):
        for tag in MODELS:
            yield ("extract", tag, ["evaluation/extract_answers.py", "--results", f"evaluation/results/{t}_{tag}.jsonl", "--task", t])
    for j in JUDGES:
        for tag in MODELS:
            yield ("judge", tag, ["evaluation/judge_oab2.py", "--results", f"evaluation/results/oab2_{tag}.jsonl", "--judge", j])
    yield ("analyze", "-", ["evaluation/analyze.py"])


def main():
    stages = set(sys.argv[1:])
    cmds = supp_cmds() if "supp" in stages else run_cmds()
    if "supp" in stages:
        stages = set()
    for stage, tag, cmd in cmds:
        if stages and stage not in stages:
            continue
        t0 = time.time()
        print(f"=== {time.strftime('%H:%M:%S')} START {stage}/{tag}: {' '.join(cmd)}", flush=True)
        rc = subprocess.run([PY] + cmd).returncode
        print(f"=== {time.strftime('%H:%M:%S')} END {stage}/{tag} rc={rc} {round((time.time()-t0)/60, 1)} min", flush=True)
    print("QUEUE_DONE", flush=True)


if __name__ == "__main__":
    main()
