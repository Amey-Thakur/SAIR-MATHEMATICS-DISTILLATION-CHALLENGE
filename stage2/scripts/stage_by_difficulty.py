#!/usr/bin/env python3
# ==============================================================================
# File: stage_by_difficulty.py
# Description: Cross-tabulates each deterministic stage against difficulty as
#   well as truth, from the per-problem records in ablation_detailed.json.
#
#   The headline result is that counterexample search closes 94.1% of the false
#   side. A single figure like that can hide a split: if the search closed
#   almost all of the normal problems and almost none of the hard ones, the
#   remaining work would look very different from the aggregate. This asks
#   whether that happened.
#
# Usage: py stage2/scripts/stage_by_difficulty.py
# Author: Amey Thakur
# License: CC BY 4.0
# ==============================================================================

from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parents[2]
DETAIL = HERE / "stage2" / "ablation_detailed.json"
BENCH = HERE / "stage2" / "benchmark.json"
OUT = HERE / "stage2" / "by_difficulty.json"

# which side of the ground truth each stage is able to settle at all
SIDE = {"lattice": None, "collapse": True, "search": False}


def main() -> int:
    detail = json.loads(DETAIL.read_text(encoding="utf-8"))

    # the denominators: how many problems of each (difficulty, truth) exist.
    # The lattice fires on every problem, so its records enumerate the set.
    universe = Counter((r["difficulty"], r["truth"])
                       for r in detail["stages"]["lattice"]["settled"])
    difficulties = sorted({d for d, _ in universe})

    print("  the benchmark, by difficulty and truth")
    for d in difficulties:
        print(f"    {d:<8} {universe[(d, True)]:>5} true  "
              f"{universe[(d, False)]:>5} false  "
              f"{universe[(d, True)] + universe[(d, False)]:>5} total")

    out = {"universe": {f"{d}|{t}": n for (d, t), n in universe.items()},
           "stages": {}}

    for stage, side in SIDE.items():
        recs = detail["stages"][stage]["settled"]
        fired = Counter((r["difficulty"], r["truth"]) for r in recs)
        wrong = [r for r in recs if r["got"] != r["truth"]]
        if wrong:
            raise SystemExit(f"{stage} disagreed with ground truth on "
                             f"{len(wrong)} problems: {wrong[:3]}")

        print(f"\n  {stage}" + (f"  (settles {side} only)" if side is not None
                                else "  (verdict only, both sides)"))
        rows = {}
        for d in difficulties:
            if side is None:
                n = universe[(d, True)] + universe[(d, False)]
                f = fired[(d, True)] + fired[(d, False)]
            else:
                n = universe[(d, side)]
                f = fired[(d, side)]
            pct = 100.0 * f / n if n else 0.0
            rows[d] = {"fires": f, "of": n, "pct": round(pct, 1)}
            print(f"    {d:<8} {f:>5} of {n:>5}   {pct:>5.1f}%")

            # a stage must never fire on the side it cannot address
            if side is not None and fired[(d, not side)]:
                raise SystemExit(
                    f"{stage} fired {fired[(d, not side)]} times on the "
                    f"{not side} side in {d}, which contradicts the argument "
                    f"that it cannot")
        out["stages"][stage] = rows

    # Does each aggregate hold across difficulty, or is it an average over two
    # different regimes? Asked of every stage, not only of the one whose answer
    # was expected: the first version of this script checked the search alone
    # and would have reported reassuringly while the collapse rule was hiding a
    # 48-point split.
    print()
    for stage in ("collapse", "search"):
        rows = out["stages"][stage]
        lo = min(rows.values(), key=lambda r: r["pct"])
        hi = max(rows.values(), key=lambda r: r["pct"])
        spread = hi["pct"] - lo["pct"]
        out[f"{stage}_spread_pp"] = round(spread, 1)
        verdict = ("holds across difficulty" if spread < 20 else
                   "DOES NOT hold across difficulty: the aggregate is an "
                   "average over two different regimes")
        print(f"  {stage}: {lo['pct']:.1f}% to {hi['pct']:.1f}%, "
              f"a spread of {spread:.1f} points, {verdict}")

    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"\n  written {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
