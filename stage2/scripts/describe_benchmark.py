#!/usr/bin/env python3
# ==============================================================================
# File: describe_benchmark.py
# Description: Describes the fixed public problem set the ablation is measured
#   on, and cross-tabulates each deterministic stage against the ground-truth
#   answer.
#
#   The ablation reports coverage and accuracy per stage. That is not enough to
#   read the result correctly, because the three stages are not
#   interchangeable: a counterexample settles an implication negatively and can
#   never settle one positively, so a stage that fires on 48% of problems may
#   be firing on 96% of the half it can address. The paper needs the
#   conditional numbers, not only the marginal ones.
#
# Usage: py stage2/scripts/describe_benchmark.py
# Author: Amey Thakur
# License: CC BY 4.0
# ==============================================================================

from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE / "stage2" / "solvers" / "hybrid"))

import solver  # noqa: E402

DATA = HERE / "stage1" / "sources" / "equational-theories-selected-problems" / "data"
SETS = ["normal.jsonl", "hard.jsonl", "hard1.jsonl", "hard2.jsonl", "hard3.jsonl"]
OUT = HERE / "stage2" / "benchmark.json"


def load():
    rows, seen, per_set, dup = [], set(), {}, 0
    for name in SETS:
        p = DATA / name
        if not p.exists():
            per_set[name] = None
            continue
        n = 0
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            n += 1
            r = json.loads(line)
            key = (r["equation1"], r["equation2"])
            if key in seen:
                dup += 1
                continue
            seen.add(key)
            r["_set"] = name
            rows.append(r)
        per_set[name] = n
    return rows, per_set, dup


def main() -> int:
    rows, per_set, dup = load()
    total = sum(v for v in per_set.values() if v)
    print(f"  {total:,} lines across {len([v for v in per_set.values() if v])} sets, "
          f"{dup:,} duplicate pairs removed, {len(rows):,} distinct")
    for name, n in per_set.items():
        print(f"    {name:<14} {n if n is not None else 'absent'}")

    truth = Counter(bool(r["answer"]) for r in rows)
    print(f"\n  distinct set: {truth[True]:,} true, {truth[False]:,} false "
          f"({100.0 * truth[False] / len(rows):.1f}% false)")

    diff = Counter(r.get("difficulty", "?") for r in rows)
    print(f"  by difficulty: " + ", ".join(f"{k} {v:,}" for k, v in sorted(diff.items())))

    # ---- how each stage distributes over the ground truth ------------------
    # The lattice and the collapse rule are rerun here; the search stage is
    # read from the ablation, because rerunning it costs half an hour and the
    # ablation already stored which problems it settled.
    print(f"\n  {'stage':<10}{'fires':>7}{'on true':>9}{'on false':>10}"
          f"{'of all true':>13}{'of all false':>14}")
    print("  " + "-" * 63)

    out = {"n_lines": total, "n_distinct": len(rows), "duplicates": dup,
           "per_set": per_set, "true": truth[True], "false": truth[False],
           "by_difficulty": dict(diff), "stages": {}}

    for name, fn in (
        ("lattice", lambda r: _lattice(r)),
        ("collapse", lambda r: _collapse(r)),
    ):
        on_true = on_false = 0
        for r in rows:
            got = fn(r)
            if got is None:
                continue
            if r["answer"]:
                on_true += 1
            else:
                on_false += 1
        fires = on_true + on_false
        print(f"  {name:<10}{fires:>7}{on_true:>9}{on_false:>10}"
              f"{100.0 * on_true / truth[True]:>12.1f}%"
              f"{100.0 * on_false / truth[False]:>13.1f}%")
        out["stages"][name] = {"fires": fires, "on_true": on_true,
                               "on_false": on_false}

    abl = json.loads((HERE / "stage2" / "ablation.json").read_text(encoding="utf-8"))
    s = abl["stages"]["search"]["fires"]
    print(f"  {'search':<10}{s:>7}{0:>9}{s:>10}{0.0:>12.1f}%"
          f"{100.0 * s / truth[False]:>13.1f}%")
    print("  " + "-" * 63)
    print("  search fires only on false problems by construction: a finite")
    print("  counterexample refutes an implication and cannot establish one.")
    out["stages"]["search"] = {"fires": s, "on_true": 0, "on_false": s,
                               "pct_of_false": round(100.0 * s / truth[False], 1)}

    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"\n  written {OUT}")
    return 0


def _lattice(r):
    try:
        v = solver.etp_verdict(r)
    except Exception:
        return None
    return True if v == 1 else False if v == 2 else None


def _collapse(r):
    try:
        return True if solver.collapse_proof(r["equation1"], r["equation2"]) else None
    except Exception:
        return None


if __name__ == "__main__":
    sys.exit(main())
