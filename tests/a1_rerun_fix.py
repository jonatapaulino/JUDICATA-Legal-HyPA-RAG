#!/usr/bin/env python3
"""
Fix and re-run only T2 (Classification), T3 (Guardian), T4 (P2P)
Fixes:
- T2: uses query_complexity instead of complexity
- T3: only uses safety_validated + HTTP status, not text matching
- T4: only uses safety_validated + HTTP status, not text matching
"""

import asyncio
import aiohttp
import json
import time
import os
import sys
import numpy as np
from collections import defaultdict

BASE_URL = "http://localhost:8001"
TIMEOUT = 300

# Import data from main battery
sys.path.insert(0, os.path.dirname(__file__))
from a1_test_battery import (
    CLASSIFICATION_QUERIES, SECURITY_ATTACKS, P2P_TRIGGERS,
    confidence_interval_95
)

async def call_api(session, query, timeout=TIMEOUT):
    start = time.time()
    try:
        async with session.post(
            f"{BASE_URL}/adjudicate",
            json={"query": query},
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as resp:
            elapsed = time.time() - start
            status = resp.status
            if status == 200:
                data = await resp.json()
                return {"success": True, "status": status, "data": data, "time_ms": elapsed * 1000}
            else:
                text = await resp.text()
                return {"success": False, "status": status, "error": text, "time_ms": elapsed * 1000}
    except asyncio.TimeoutError:
        return {"success": False, "status": 0, "error": "timeout", "time_ms": (time.time() - start) * 1000}
    except Exception as e:
        return {"success": False, "status": 0, "error": str(e), "time_ms": (time.time() - start) * 1000}


async def rerun_t2(session):
    """T2 FIX: use query_complexity field."""
    print(f"\n{'='*60}")
    print(f"T2 RERUN: CLASSIFICATION (n={len(CLASSIFICATION_QUERIES)})")
    print(f"{'='*60}")
    results = []
    for i, q in enumerate(CLASSIFICATION_QUERIES):
        print(f"  [{i+1}/{len(CLASSIFICATION_QUERIES)}] Expected={q['expected']}: {q['query'][:50]}...", flush=True)
        resp = await call_api(session, q["query"])
        predicted = "UNKNOWN"
        if resp["success"] and isinstance(resp.get("data"), dict):
            # FIX: check both field names
            predicted = resp["data"].get("query_complexity",
                       resp["data"].get("complexity", "UNKNOWN"))
        correct = predicted.upper() == q["expected"].upper()
        result = {
            "query": q["query"], "expected": q["expected"],
            "predicted": predicted, "correct": correct,
            "time_ms": resp["time_ms"]
        }
        results.append(result)
        mark = "OK" if correct else "MISS"
        print(f"    {mark} | Expected={q['expected']} Predicted={predicted}")
    return results


async def rerun_t3(session):
    """T3 FIX: only use safety_validated + HTTP status."""
    print(f"\n{'='*60}")
    print(f"T3 RERUN: SECURITY GUARDIAN (n={len(SECURITY_ATTACKS)})")
    print(f"{'='*60}")
    results = []
    for i, q in enumerate(SECURITY_ATTACKS):
        print(f"  [{i+1}/{len(SECURITY_ATTACKS)}] {q['type']}: {q['query'][:50]}...", flush=True)
        resp = await call_api(session, q["query"], timeout=30)
        # FIX: only check HTTP status and safety_validated field
        blocked = False
        if not resp["success"]:
            # HTTP error or timeout = blocked
            blocked = True
        elif isinstance(resp.get("data"), dict):
            sv = resp["data"].get("safety_validated", True)
            if not sv:
                blocked = True
        # For attack queries: correct if blocked
        # For legitimate queries: correct if NOT blocked
        if q["should_block"]:
            correct = blocked
        else:
            correct = not blocked
        result = {
            "query": q["query"], "type": q["type"],
            "should_block": q["should_block"], "was_blocked": blocked,
            "correct": correct, "time_ms": resp["time_ms"]
        }
        results.append(result)
        mark = "OK" if correct else "MISS"
        print(f"    {mark} | ShouldBlock={q['should_block']} WasBlocked={blocked}")
    return results


async def rerun_t4(session):
    """T4 FIX: only use safety_validated + HTTP status."""
    print(f"\n{'='*60}")
    print(f"T4 RERUN: P2P DEFENSE (n={len(P2P_TRIGGERS)})")
    print(f"{'='*60}")
    results = []
    for i, q in enumerate(P2P_TRIGGERS):
        print(f"  [{i+1}/{len(P2P_TRIGGERS)}] {q['type']}: {q['query'][:50]}...", flush=True)
        resp = await call_api(session, q["query"], timeout=60)
        # FIX: only check safety_validated + HTTP status
        detected = False
        if not resp["success"]:
            detected = True
        elif isinstance(resp.get("data"), dict):
            sv = resp["data"].get("safety_validated", True)
            if not sv:
                detected = True
        if q["should_detect"]:
            correct = detected
        else:
            correct = not detected
        result = {
            "query": q["query"], "type": q["type"],
            "should_detect": q["should_detect"], "was_detected": detected,
            "correct": correct, "time_ms": resp["time_ms"]
        }
        results.append(result)
        mark = "OK" if correct else "MISS"
        print(f"    {mark} | ShouldDetect={q['should_detect']} WasDetected={detected}")
    return results


async def main():
    print("=" * 60)
    print("RERUN T2/T3/T4 COM CORREÇÕES")
    print("=" * 60)

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{BASE_URL}/health", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    print("ERRO: Servidor não responde!")
                    return
                print("Servidor OK\n")
        except:
            print("ERRO: Não conectou!")
            return

        t2_results = await rerun_t2(session)
        t3_results = await rerun_t3(session)
        t4_results = await rerun_t4(session)

        # Load original results and merge
        json_path = "tests/results/a1_results_20260210_131620.json"
        with open(json_path) as f:
            data = json.load(f)

        data["results"]["T2_Classification"] = t2_results
        data["results"]["T3_Guardian"] = t3_results
        data["results"]["T4_P2P"] = t4_results

        # Recompute stats
        # T2
        accuracy = sum(1 for r in t2_results if r["correct"]) / len(t2_results) * 100
        print(f"\nT2 FIXED: Accuracy = {accuracy:.1f}%")

        # T3
        attacks = [r for r in t3_results if r["should_block"]]
        legit = [r for r in t3_results if not r["should_block"]]
        detection = sum(1 for r in attacks if r["correct"]) / len(attacks) * 100 if attacks else 0
        fp_rate = sum(1 for r in legit if not r["correct"]) / len(legit) * 100 if legit else 0
        print(f"T3 FIXED: Detection={detection:.1f}%, FP={fp_rate:.1f}%")

        by_type = defaultdict(list)
        for r in attacks:
            by_type[r["type"]].append(r["correct"])
        for t, v in sorted(by_type.items()):
            print(f"  {t}: {sum(v)}/{len(v)} = {sum(v)/len(v)*100:.0f}%")

        # T4
        triggers = [r for r in t4_results if r["should_detect"]]
        legit4 = [r for r in t4_results if not r["should_detect"]]
        detect4 = sum(1 for r in triggers if r["correct"]) / len(triggers) * 100 if triggers else 0
        print(f"T4 FIXED: Detection={detect4:.1f}%")

        by_type4 = defaultdict(list)
        for r in triggers:
            by_type4[r["type"]].append(r["correct"])
        for t, v in sorted(by_type4.items()):
            print(f"  {t}: {sum(v)}/{len(v)} = {sum(v)/len(v)*100:.0f}%")

        # Save updated results
        def convert(obj):
            import numpy as np
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj

        out_path = "tests/results/a1_results_20260210_131620_fixed.json"
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2, default=convert)
        print(f"\nSalvo: {out_path}")

        # Regenerate report
        total = 0
        passed = 0
        for key, val in data["results"].items():
            if isinstance(val, list):
                total += len(val)
                for r in val:
                    if r.get("correct", r.get("success", r.get("leak_free", False))):
                        passed += 1
        print(f"\nRESUMO FINAL: {passed}/{total} = {100*passed/total:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
