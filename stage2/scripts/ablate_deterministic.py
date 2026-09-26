#!/usr/bin/env python3
# ==============================================================================
# File: ablate_deterministic.py
# Description: Measures what the deterministic half of the hybrid solver settles
#   on a fixed, public problem set, with no model call at any point.
#
#   The paper's earlier figures came from a competition playground: a sample of
#   twenty, scored against a judge we could not rerun. That is anecdote, not
#   measurement. The selected-problems sets shipped in stage1/sources carry
#   1,869 instances with ground truth, so every stage of the dispatch can be
#   given a coverage and an accuracy on the same fixed set, and the result is
#   reproducible by anyone who clones the repository.
#
#   Three stages are measured separately and then together:
#     lattice   the Equational Theories Project verdict, a table lookup
#     collapse  the one-step collapse rule, a syntactic derivation
#     search    exhaustive and backtracking counterexample search over small
#               finite magmas, which settles an implication negatively
#
#   A counterexample is a proof, so the search stage should never be wrong. That
#   is checked rather than assumed: any disagreement with ground truth is
#   reported as a soundness failure, which would be a defect in the solver.
#
# Usage: py stage2/scripts/ablate_deterministic.py [--budget 2.0] [--limit N]
# Author: Amey Thakur
# License: CC BY 4.0
# ==============================================================================

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE / "stage2" / "solvers" / "hybrid"))

import solver  # noqa: E402

DATA = HERE / "stage1" / "sources" / "equational-theories-selected-problems" / "data"
SETS = ["normal.jsonl", "hard.jsonl", "hard1.jsonl", "hard2.jsonl", "hard3.jsonl"]


def load(names):
    rows = []
    seen = set()
    for name in names:
        p = DATA / name
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            key = (r["equation1"], r["equation2"])
            if key in seen:          # the hard splits overlap
                continue
            seen.add(key)
            rows.append(r)
    return rows


def try_lattice(r):
    """The ETP table. Returns True, False or None."""
    try:
        v = solver.etp_verdict(r)
    except Exception:
        return None
    if v == 1:
        return True
    if v == 2:
        return False
    return None                       # 0 unknown, 3 only conjectured


def try_collapse(r):
    """The syntactic collapse rule. Settles an implication positively."""
    try:
        proof = solver.collapse_proof(r["equation1"], r["equation2"])
    except Exception:
        return None
    return True if proof else None


def try_search(r, budget, strict=False):
    """Counterexample search. A witness settles the implication negatively.

    The statement has to go through normalize() first: the parser splits on the
    canonical operator glyph, and the problem sets write it as an asterisk, so
    an unnormalised string raises rather than parsing. Swallowing that
    exception silently reports the stage as never firing, which is what an
    earlier version of this script did.
    """
    try:
        eq1 = solver.parse_equation(solver.normalize(r["equation1"]))
        eq2 = solver.parse_equation(solver.normalize(r["equation2"]))
    except Exception:
        if strict:
            raise
        return None
    try:
        n, _table = solver.find_counterexample(eq1, eq2, budget)
    except Exception:
        if strict:
            raise
        return None
    return False if n else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=2.0,
                    help="seconds of counterexample search per problem")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=str(HERE / "stage2" / "ablation.json"))
    args = ap.parse_args()

    rows = load(SETS)
    if args.limit:
        rows = rows[:args.limit]
    print(f"  {len(rows)} distinct problems from {len(SETS)} public sets")
    print(f"  search budget {args.budget}s per problem, no model call anywhere\n")

    stages = ["lattice", "collapse", "search"]
    fired = Counter()
    correct = Counter()
    unsound = {s: [] for s in stages}
    settled_by = {s: [] for s in stages}   # ids, for later cross-tabulation
    settled = 0
    settled_correct = 0
    by_difficulty = Counter()
    difficulty_total = Counter()
    t0 = time.monotonic()

    for i, r in enumerate(rows, 1):
        truth = bool(r["answer"])
        difficulty_total[r.get("difficulty", "?")] += 1
        verdict = None
        for name, fn in (("lattice", try_lattice),
                         ("collapse", try_collapse),
                         ("search", lambda x: try_search(x, args.budget))):
            got = fn(r)
            if got is None:
                continue
            fired[name] += 1
            settled_by[name].append(
                {"id": r["id"], "truth": truth, "got": got,
                 "difficulty": r.get("difficulty", "?")})
            if got == truth:
                correct[name] += 1
            else:
                unsound[name].append(r["id"])
            if verdict is None:
                verdict = got
                verdict_stage = name
        if verdict is not None:
            settled += 1
            if verdict == truth:
                settled_correct += 1
                by_difficulty[r.get("difficulty", "?")] += 1
        if i % 200 == 0:
            print(f"    {i}/{len(rows)}  settled {settled}  "
                  f"{time.monotonic() - t0:.0f}s", flush=True)

    n = len(rows)
    print(f"\n  {'stage':<10}{'fires':>8}{'of':>8}{'coverage':>11}{'accuracy':>11}")
    print("  " + "-" * 48)
    out = {"n_problems": n, "budget_s": args.budget, "stages": {}}
    for s in stages:
        f, c = fired[s], correct[s]
        cov = 100.0 * f / n
        acc = 100.0 * c / f if f else 0.0
        out["stages"][s] = {"fires": f, "correct": c,
                            "settled": settled_by[s],
                            "coverage_pct": round(cov, 1),
                            "accuracy_pct": round(acc, 1),
                            "disagreements": unsound[s][:20]}
        print(f"  {s:<10}{f:>8}{n:>8}{cov:>10.1f}%{acc:>10.1f}%")

    out["settled"] = settled
    out["settled_correct"] = settled_correct
    out["settled_coverage_pct"] = round(100.0 * settled / n, 1)
    out["settled_accuracy_pct"] = round(100.0 * settled_correct / settled, 1) if settled else 0.0
    out["by_difficulty"] = {k: {"settled_correct": by_difficulty[k],
                                "total": difficulty_total[k]}
                            for k in difficulty_total}
    print("  " + "-" * 48)
    print(f"  {'combined':<10}{settled:>8}{n:>8}"
          f"{out['settled_coverage_pct']:>10.1f}%{out['settled_accuracy_pct']:>10.1f}%")
    print(f"\n  {n - settled} left for the model "
          f"({100.0 * (n - settled) / n:.1f}%)")

    bad = {s: v for s, v in unsound.items() if v}
    if bad:
        print("\n  SOUNDNESS DISAGREEMENTS (a counterexample is a proof, so search "
              "must never disagree):")
        for s, ids in bad.items():
            print(f"    {s}: {len(ids)} e.g. {ids[:5]}")
    else:
        print("\n  no stage disagreed with ground truth on any problem")

    out["elapsed_s"] = round(time.monotonic() - t0, 1)
    pathlib.Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n  written to {args.out} in {out['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
