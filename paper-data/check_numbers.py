#!/usr/bin/env python3
"""Check every quantity the manuscript quotes against the data behind it.

The tables are transcribed from data/benchmark.json and data/ablation.json, and
the prose around them is written by hand, so a figure that was right when typed
and wrong after the ablation was re-run would survive both the compiler and a
proofread. This recomputes each quoted quantity from the data and requires
main.tex to contain it, formatted as the paper formats numbers.

The conditional coverages are the ones that matter, because the marginal ones
understate two of the three stages, so they are recomputed here rather than
trusted: a stage that can only refute is scored against the false problems and
a stage that can only prove against the true ones.

Usage: python tools/check_numbers.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEX = (ROOT / "main.tex").read_text(encoding="utf-8")
BENCH = json.loads((ROOT / "data" / "benchmark.json").read_text(encoding="utf-8"))
ABL = json.loads((ROOT / "data" / "ablation.json").read_text(encoding="utf-8"))

failures: list[str] = []
checked = 0


def grouped(n: int) -> str:
    """The paper writes a thousands separator as LaTeX, not as a comma."""
    return f"{n:,}".replace(",", "{,}")


def want(text: str, what: str) -> None:
    global checked
    checked += 1
    if text not in TEX:
        failures.append(f"{what}: {text!r} does not appear in main.tex")


def main() -> int:
    n_true, n_false = BENCH["true"], BENCH["false"]
    n_distinct = BENCH["n_distinct"]

    # ---- the benchmark's shape --------------------------------------------
    want(grouped(BENCH["n_lines"]), "total lines across the sets")
    want(grouped(n_distinct), "distinct problems")
    want(str(BENCH["duplicates"]), "duplicate pairs removed")
    want(str(n_true), "true problems")
    want(str(n_false), "false problems")
    if BENCH["n_distinct"] != n_true + n_false:
        failures.append("distinct count does not equal true + false")
    for k, v in BENCH["by_difficulty"].items():
        want(grouped(v), f"{k} problems")

    # ---- the per-set table -------------------------------------------------
    for name, lines in BENCH["per_set"].items():
        if lines:
            want(grouped(lines), f"line count for {name}")

    # ---- each stage, marginal and conditional ------------------------------
    for stage, side_n, side in (("collapse", n_true, "true"),
                                ("search", n_false, "false")):
        s = BENCH["stages"][stage]
        fires = s["fires"]
        want(grouped(fires), f"{stage} fires")

        marginal = 100.0 * fires / n_distinct
        want(f"{marginal:.1f}\\%", f"{stage} marginal coverage")

        conditional = 100.0 * fires / side_n
        want(f"{conditional:.1f}\\%", f"{stage} coverage of the {side} side")

        # the stage must not cross the true/false line
        wrong_side = s["on_true"] if stage == "search" else s["on_false"]
        if wrong_side:
            failures.append(
                f"{stage} fired {wrong_side} times on the wrong side, which "
                f"contradicts the paper's argument that it cannot")

        # the remainder the paper quotes
        want(str(side_n - fires), f"{stage} remainder on the {side} side")

    # ---- the lattice -------------------------------------------------------
    lat = BENCH["stages"]["lattice"]
    if lat["fires"] != n_distinct:
        failures.append(f"lattice settles {lat['fires']}, not all {n_distinct}")
    want("100\\%", "the lattice's coverage")

    # ---- accuracy is 100 for every stage, which the paper asserts in prose --
    for stage, s in ABL["stages"].items():
        if s["fires"] and s["correct"] != s["fires"]:
            failures.append(
                f"{stage} was correct on {s['correct']} of {s['fires']}: the "
                f"paper's soundness claim is wrong and must be rewritten")
    want("100.0\\%", "the accuracy figure")

    # ---- cross-check the two data files agree ------------------------------
    for stage in ("lattice", "collapse", "search"):
        a, b = ABL["stages"][stage]["fires"], BENCH["stages"][stage]["fires"]
        if a != b:
            failures.append(f"{stage}: ablation says {a} fires, benchmark says {b}")

    # ---- the search budget and the pass duration ---------------------------
    want(f"{ABL['budget_s']:.0f} seconds", "the per-problem search budget")
    want(str(round(ABL["elapsed_s"] / 60)), "the pass duration in minutes")

    # ---- the difficulty split ----------------------------------------------
    # This is the part of the paper most able to go quietly wrong, because the
    # collapse rule's aggregate and its two halves disagree so sharply that a
    # stale number would still read as plausible.
    split = json.loads(
        (ROOT / "data" / "by_difficulty.json").read_text(encoding="utf-8"))
    for stage, rows in split["stages"].items():
        for band, r in rows.items():
            want(grouped(r["fires"]), f"{stage} fires on {band}")
            want(grouped(r["of"]), f"{stage} denominator on {band}")
            want(f"{r['pct']:.1f}\\%", f"{stage} coverage on {band}")

    for stage in ("collapse", "search"):
        want(f"${split[f'{stage}_spread_pp']:.1f}$",
             f"{stage} spread across difficulty")

    # The paper's claim is that one aggregate survives the split and one does
    # not. If that ever flips, the argument changes and the text must too.
    if split["search_spread_pp"] >= 20:
        failures.append(
            f"the search spread is now {split['search_spread_pp']} points, so "
            f"the paper's claim that its aggregate holds is no longer true")
    if split["collapse_spread_pp"] < 20:
        failures.append(
            f"the collapse spread is now {split['collapse_spread_pp']} points, "
            f"so the paper's claim that its aggregate hides a split is no "
            f"longer true")

    # the count of untouched hard true problems, quoted twice
    hard_true = split["stages"]["collapse"]["hard"]
    want(str(hard_true["of"] - hard_true["fires"]),
         "hard true problems left untouched")

    # ---- report ------------------------------------------------------------
    print(f"  checked {checked} quantities against the data")
    for f in failures:
        print(f"  FAIL  {f}")
    if not failures:
        print("  ok    every quoted number matches")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
