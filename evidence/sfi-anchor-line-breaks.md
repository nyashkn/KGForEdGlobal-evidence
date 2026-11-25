# kn/sfi-anchor-line-breaks

Branch: [`kn/sfi-anchor-line-breaks`](https://github.com/nyashkn/KGForEdGlobal/tree/kn/sfi-anchor-line-breaks) at `ea27119`, one commit on IDinsight `main` at `9d87cdb`. Type: fix, opt-in. Also merged into `kn/integration`.

## What the change does

SFI extraction asks the model to copy source text as anchors. PDF table cells hold hard line breaks and the model often re-wraps them. `find_source_anchor_span` then finds no exact match, the candidate fails output validation, the window is retried, and after the retry limit the run stops.

With `KGFEG_SFI_JOIN_LINE_BREAKS=1`, and only after a strict miss, `find_source_anchor_span` matches the anchor's words separated by any whitespace and returns the source's own wrapped span. With the variable unset, behaviour is `origin/main`'s. Anchors made only of whitespace skip the fallback. The variable is read on every call, so it must be the same for a run and for every resume of it (the docstring says so). The change is 17 lines in `sfi_source_anchors.py` plus tests in `test_sfi_line_breaks.py`.

## Method

No model calls. Three checks on the recorded runs:

1. Count the logged anchor misses: [`scripts/scan_run_logs.py`](../scripts/scan_run_logs.py).
2. Re-resolve each logged failing anchor against the window's rebuilt source units, on `origin/main`, on the branch with the variable unset, and on the branch with it set to 1: [`scripts/replay_anchor_misses.py`](../scripts/replay_anchor_misses.py).
3. For every recorded description anchor, resolve its span with the variable at 0 and at 1 and count differences: [`scripts/compare_anchor_flag.py`](../scripts/compare_anchor_flag.py).

## Inputs

The same 12 run folders as in [sfi-identity-key-collision.md](sfi-identity-key-collision.md): IDinsight's Rwanda example config on slices of the 2025 REB mathematics PDF (plus one earlier run on the 2022 edition). They hold 233 extraction windows, 2,337 candidates and 2,340 description anchors. Run folders are not included because they hold the full curriculum text.

## Result

Logged misses ("does not have occurrence_index") on `origin/main` behaviour: 2 of 12 runs, 4 distinct failing anchors. Three are line-break re-wraps; one is a dropped space (`1000Frw.` against the source's `1000 Frw.`). One run reached the retry limit (window 8, exit 1); in that window attempts 2 and 3 failed on line-break anchors and attempts 1 and 4 failed other checks (identity scope, description composition).

Shortest input (one of the logged misses): source `"– Compare\n1/2, 1/4 and 1/8\nusing\ncomparison\nsymbols (<, >\nor =)…"`, anchor `"Compare\n1/2, 1/4 and 1/8\nusing\ncomparison\nsymbols (<, > or\n=)"`. Same words, one line break moved.

| Check | Result |
|---|---|
| 3 line-break anchors, `origin/main` | 3/3 miss |
| same, branch, variable unset | 3/3 miss (same as `origin/main`) |
| same, branch, `KGFEG_SFI_JOIN_LINE_BREAKS=1` | 3/3 match; the span is the source's own wrapped text |
| dropped-space anchor, branch, variable set | still a miss (documented by `test_missing_space_is_not_a_line_break`) |
| 2,340 recorded anchors, variable 0 against 1 | 0 span differences (0 lookup errors) |

The last row holds by construction: the fallback runs only after a strict miss, so an anchor that matched strictly cannot change. The check confirms the code does that.

## Limits

- Only 3 line-break anchors were observed in 12 runs. The result is "the fallback fixes the cases we saw", not a rate.
- It is not shown that a live run with the variable set would have got past window 8 of the stopped run: that window's other two attempts failed different checks.
- One of the four failing anchors (the dropped space) is not fixed.
- The fallback is opt-in, so nothing changes until a run sets the variable.
- No live model run was made for this check.

## Reproduce

```
python -I scripts/scan_run_logs.py --runs-dir RUNS
KGFEG_SFI_JOIN_LINE_BREAKS=1 python -I scripts/replay_anchor_misses.py --src PATH_TO_BRANCH/backend/src --run RUNS/RUN --log RUNS/RUN/create_kgs.log
python -I scripts/compare_anchor_flag.py --src PATH_TO_BRANCH/backend/src --runs-dir RUNS --run RUN1 RUN2 ...
```

Run `replay_anchor_misses.py` once more with `--src` pointing at an `origin/main` tree to see the strict result.
