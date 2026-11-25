# kn/sibling-position-export

Branch: [`kn/sibling-position-export`](https://github.com/nyashkn/KGForEdGlobal/tree/kn/sibling-position-export) at `d3ee9b2`, one commit on IDinsight `main` at `9d87cdb`. Type: feat, opt-in. Also merged into `kn/integration`.

This branch carries **sibling order (`position`) only**. The idea it started from also covered outcome codes (`statementCode`); that part did not hold up and the branch contains nothing for it. See "What did not hold".

## What the change does

- New config setting `kgs.as.emit_sibling_position` (default `false`). When `true`, each exported item gets a zero-based source-order index among the children of its primary parent (the framework, for root items), written as the string property `position` in the Learning Commons export. An item with several parents is numbered under its earliest parent. Order comes from the existing `sfi_final_contexts.json` `source_order`.
- `StandardsFrameworkItem` gets an optional internal field `position`, so the later LC and LP stages, which rebuild nodes from bundle items, stay consistent.
- The export validator also checks that `position` (and, as a separate small guard, `statementCode`) survives into the node.
- 6 new tests in `backend/tests/kgfeg/kgs/test_sfi_position.py`; one line each in `docs/pipeline/academic-standards.md` and `docs/reference/output-artifacts.md`.
- One existing test fixture changes: `backend/tests/fixtures/lp/loader.py` holds an approved set of item field names, and it gains the key `position`.
- With the setting off, the Learning Commons export is unchanged. The internal item artifacts (`as_standards_framework_items.jsonl`, `as_kg_bundle.json`) gain `"position": null`, because the optional field is dumped with nulls. This second part was not replayed on those files.

## Method

No model calls. [`scripts/check_position.py`](../scripts/check_position.py) copies a run's `kgs` folder and re-runs only `compile_academic_standards_kg` with the setting off, then on, using the run's own DocumentIR, final contexts and final `hasChild` edges. It then:

1. compares the setting-off `as_nodes.jsonl` byte for byte with the file the pipeline wrote;
2. counts items with `position`, checks that each parent group holds exactly 0..n-1, and checks that nothing else in the nodes or relationships changed;
3. with `--pdf`, compares sibling order with the order of the same texts in the PDF text layer (PyMuPDF reading order). Only items whose text occurs exactly once in the PDF are used.

## Input

Three run folders of the same slice, made with different models and settings. The first is the one in the tables below; the other two are listed after them. Each is IDinsight's `examples/rwanda/config_math_curriculum_p1_p3.json` with `start_page` 25 and `end_page` 56 (the P1 slice) of the 2025 REB mathematics PDF (sha256 `7b9629e6bd5ad5566e6420892908a307687543ede8cc0c676ddf5b0321ba5874`). The first run has 184 items in 33 parent groups. Not in this repository (they contain curriculum text).

## Result (Rwanda P1 slice, n = 184 items)

| Check | Result |
|---|---|
| Setting off: `as_nodes.jsonl` against the pipeline's own file | byte-identical |
| Setting on: items with `position` | 184 of 184 (the 185th node is the framework) |
| Setting on: parent groups with positions exactly 0..n-1 | 33 of 33 |
| Setting on: nodes that differ in anything but `position` | 0; `as_relationships.jsonl` byte-identical |
| Sibling order against PDF text order, same statement type | 299 of 299 pairs in order |
| Sibling order against PDF text order, all statement types | 840 of 840 pairs in order |

In the PDF-order rows, 170 of the 184 items have text that occurs exactly once in the PDF; pairs are formed only from those. The 14 left out are 7 Attitudes and Values objectives, 4 Topic Areas, 2 Sub-Topic Areas and 1 Grade, the repeated-text kind the earlier check found out of order. No item in these runs has two parents, so the multi-parent rule is covered by unit tests only.

Two further P1-slice runs give the same pattern. Both have 184 items in 34 parent groups, a byte-identical off state, `position` on 184 of 184 items and positions exactly 0..n-1 in 34 of 34 groups. Run 2: 162 items with unique text, 275 of 275 same-type pairs and 779 of 779 all-type pairs in order. Run 3: 171 items with unique text, 300 of 300 and 854 of 854. Five more P1-slice runs we replayed (184 to 187 items) also had every pair in order and a byte-identical off state; they are not listed.

An earlier hand-run check (not this script) reported 238 of 238 same-type pairs and 871 of 953 pairs over all types, with the misses put down to table reading order. That check used a different matching rule and its script was not kept, so those numbers are not reproduced here; the script above gives the figures in the table.

## What did not hold: `statementCode`

The first idea was that outcome codes such as 1.0, 1.1 or a) are lost in the export. They are not. The exporter already writes `statementCode` whenever an item has a `statement_code` (the item-to-node mapping in `sfi_export.py`). It is empty for the Rwanda example because `kgs.as.code_patterns` is `{}` there and the source prints few usable codes: a regex count of markers at the start of item text finds at most 17 of 184 items in the P1 slice, all local ordinals (1., 2., Unit N) rather than framework-wide codes. So there is nothing to change in the exporter for it; any gain would come from per-curriculum configuration.

On the MCP side, IDinsight's Rwanda package profile sets `codeSearchPolicy.availability` to `none`, and the MCP validator rejects a package that carries coded items under that setting (`profile_code_availability_conflict`). Code search therefore also needs a profile that declares a code type and availability.

## Limits

- Position was replayed on one curriculum and one slice. There is no replay for Nigeria or for any other country.
- The PDF-order check uses the text layer and a plain text match; it is not a visual check of each page, and 14 items were left out because their text was not found exactly once in the PDF.
- Position is a string in the export. The MCP package validation accepting it as a string and rejecting it as a JSON number was reported from an earlier check on IDinsight's Rwanda package and was not re-run for this repository.
- No `statementCode` was measured from a real pipeline run; the marker counts are regex ceilings, not pipeline output.
- The PDF-order check is not independent of the pipeline: PyMuPDF text is also what the page-IR step gets as hints when `use_extracted_hints` is on. It shows that `position` follows the document's text order, not that the text order is the printed reading order.
- Not checked: the 14 items (in the first run) with repeated text, half of them Attitudes and Values objectives. The earlier hand check attributed its out-of-order pairs to this kind of item.

## Reproduce

```
python -I scripts/check_position.py --src PATH_TO_BRANCH/backend/src --run RUN --config RUN_CONFIG.json --pdf rwanda_math_p1_p3_2025.pdf
```
