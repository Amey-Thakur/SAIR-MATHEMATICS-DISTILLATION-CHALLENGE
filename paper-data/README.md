# Paper data

The measurements behind every number quoted in the manuscript *The verdict is
free: a saturated benchmark for equational implication, and what it leaves to
prove*. They live here, in the public repository, so that a reader can check the
paper's figures without needing access to the manuscript's own repository.

| file | what it holds |
| --- | --- |
| `benchmark.json` | the public problem sets as shipped: how many distinct problems, how the verdicts split, and how many are decided by looking the pair up in the implication lattice |
| `ablation.json` | the three-stage ablation in aggregate: what each stage adds over the one before it |
| `ablation_detailed.json` | the same ablation per problem, so a reader can see which problems each stage moves rather than only the totals |
| `by_difficulty.json` | the split that the aggregate hides: the collapse rule's behaviour on the normal and hard subsets separately |
| `check_numbers.py` | the guard: it reads the manuscript and fails if any quoted figure disagrees with these files |

## The finding these files are for

The aggregate and the split disagree, and the split is the result. The collapse
rule looks moderately useful in aggregate and is almost entirely a
normal-difficulty effect: it fires on 243 of 500 normal problems and on 1 of 319
hard ones. Anyone reading only the aggregate figure would carry away the
opposite impression, which is why `by_difficulty.json` is here beside
`ablation.json` rather than folded into it.

## Reproducing the figures

The solver, the ablation harness and the benchmark description script are in the
parent repository. `check_numbers.py` needs the manuscript to check it against
and so is included for reference rather than to be run here.
