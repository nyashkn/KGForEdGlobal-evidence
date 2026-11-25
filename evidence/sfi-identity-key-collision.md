# kn/sfi-identity-key-collision

Branch: [`kn/sfi-identity-key-collision`](https://github.com/nyashkn/KGForEdGlobal/tree/kn/sfi-identity-key-collision) at `06b5a94`, one commit on IDinsight `main` at `9d87cdb` (release 0.2.1). Type: fix. It is also merged into `kn/integration`.

## What the change does

Dedup can leave two SFI merge groups that finalization keys identically (same statement type, same identity scope, same normalized text). `mint_final_sfi_ids` then stops with `ValueError: Final SFI UUID collisions detected`. The branch adds a step to `merge_sfi_candidates` (`sfi_dedup.py`) that finds such groups and merges them before minting:

- every candidate and its provenance is kept;
- the merged group gets the audit flag `identity_key_forced_merge`;
- when the colliding groups cannot form one SFI (for example they have different statement types), the run stops with an error that names the groups and the key;
- `uncoded_identity_keys` in `sfi_finalization.py` exposes the same key construction that minting uses, so the two steps cannot disagree.

There is no flag: the step is always on, and it changes nothing unless a collision exists. `merge_sfi_candidates` now takes the `document_ir` as an argument, so `entries/create_kgs.py` passes it.

## Method

A replay that makes no model calls. For each run it loads the recorded DocumentIR, the recorded SFI candidate registry and the recorded dedup responses, rebuilds the merge groups, builds the merge report, and calls the real `mint_final_sfi_ids`. Two cases:

- `recorded`: the responses exactly as the model gave them.
- `flip`: every recorded `merge` decision (4 to 5 per run: repeated Topic Area, Sub-Topic Area and Grade headings, 2 to 11 candidates each) is changed to `keep_separate`. This stands in for a checker model that reverts the producer's merge of a heading and its table-cell copy.

The same replay runs on `origin/main` and on the branch. Script: [`scripts/replay_identity_key.py`](../scripts/replay_identity_key.py).

## Inputs

Run folders from the pipeline on IDinsight's `examples/rwanda/config_math_curriculum_p1_p3.json`, with `start_page` and `end_page` set to a slice of the 2025 Rwanda REB mathematics PDF (sha256 `7b9629e6bd5ad5566e6420892908a307687543ede8cc0c676ddf5b0321ba5874`): nine runs of the P1 slice (pages 25 to 56), two of the P2 slice (pages 56 to 100) and one earlier run on the 2022 edition. Different runs used different models and some settings that are not on IDinsight `main`; they are not a controlled sample. One run has no saved registry, so n = 11 replays. The run folders are not in this repository because they contain curriculum text.

## Result (n = 11 runs)

| Case | `origin/main` | Branch |
|---|---|---|
| `recorded` | 11/11 give the same merge-group ids and the same final SFI UUID set as the recorded run | 11/11 identical to `origin/main` and to the recorded run; 0 forced merges |
| `flip` | 11/11 stop with "Final SFI UUID collisions detected" (4 to 5 colliding UUIDs); for example 206 groups where the recorded run has 184 | 11/11 mint; 4 to 5 forced merges per run; the final SFI UUID set equals the recorded run's in 11/11 (184 SFIs for the 184-group runs) |

Shortest input: two Rwanda Topic Area candidates, `"TOPIC AREA: NUMBERS AND\nOPERATIONS"` and `"TOPIC AREA: NUMBERS AND OPERATIONS"`, scope Grade P1, decision `keep_separate`. It is the test `test_rwanda_topic_area_repeats_with_line_break_merge` in `backend/tests/kgfeg/kgs/test_sfi_identity_merge.py`. The same file also covers a heading-and-table-cell merge, a resume round trip with a forced-merge group, items that must stay separate, and the mixed-type failure.

How often it happens without the flip: [`scripts/scan_run_logs.py`](../scripts/scan_run_logs.py) over the same 12 runs finds 0 logs that mention `UUID collisions detected`.

## Limits

- No collision occurs naturally in the public runs. The `flip` case simulates a checker verdict; it is not a recorded one.
- No live model run was made for this check, so there is no measure of how often a real checker reverts a real merge.
- The mixed-type failure path is covered by a unit test only.
- The replay shows that `main` crashes and the branch mints; it does not show that the forced merge is the right call for every curriculum.

## Reproduce

```
python -I scripts/replay_identity_key.py --src PATH_TO_MAIN/backend/src   --run RUN1 RUN2 ... --scenario flip
python -I scripts/replay_identity_key.py --src PATH_TO_BRANCH/backend/src --run RUN1 RUN2 ... --scenario flip
```

Use the backend virtualenv. See the README for how to get the run folders and the two source trees.
