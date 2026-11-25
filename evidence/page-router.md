# kn/page-router

Branch: [`kn/page-router`](https://github.com/nyashkn/KGForEdGlobal/tree/kn/page-router) at `540019e`, one commit on IDinsight `main` at `9d87cdb`. Type: feat, opt-in. Also merged into `kn/integration`. This branch is the **model-free router only**. The router never calls a model.

## What the change does

A router that decides which PDF pages hold standards, before page IR extraction, from the text layer, the outline and the table of contents.

- `kgfeg/page_router/` (`router.py`, `signals.py`, `toc.py`, `schemas.py`): scores every page from signals such as table density, heading cues and standard codes, labels it, and pads each kept page with its neighbours. Pages with no text layer or a middling score are labelled `unknown` and kept; if no page looks like a standards page, every page is kept. It reads no gold labels.
- `entries/route_pages.py`: a stand-alone entry point, `python src/kgfeg/entries/route_pages.py <config.json>`, that writes `route.json`. `--fill-config` also writes `start_page` and `end_page` into the config. Nothing in the existing pipeline entries calls the router, so nothing changes unless it is run.
- Defaults of `RouterParams` were tuned on three public PDFs: Rwanda, Nigeria and Ghana maths (the schema's own docstring says so).
- 24 new test functions in `backend/tests/kgfeg/page_router/`.

## Method

No model calls. [`scripts/score_page_router.py`](../scripts/score_page_router.py) runs the router on each PDF and compares the pages it keeps with the pages that IDinsight's published package cites as the source of at least one standard (`source_page_indexes` in the package's `slim/as_entity_provenance.json`, 0-based). Recall is the share of those gold pages the router keeps. "Skipped" is the share of all pages it drops. "Range saved" is how much the single page range that `--fill-config` writes (first kept page to last kept page + 1) shrinks the document, which is what the pipeline would actually read. The router is deterministic, so there are no replicates.

## Inputs

IDinsight's packages in `KGForEdGlobalMCP/data/graph_packages` (public) for the gold pages, and the curriculum PDF each package was built from. The PDFs are not in this repository; page indexes only line up if you use the same file.

| Curriculum | Package folder | PDF sha256 |
|---|---|---|
| Rwanda REB maths P1-P3 (2025) | `rwanda-reb-mathematics-lower-primary-1-3` | `7b9629e6bd5ad5566e6420892908a307687543ede8cc0c676ddf5b0321ba5874` |
| Nigeria maths primary 1-3 | `nigeria-nerdc-mathematics-primary-1-3` | `09d6b52b54b2f6b00d5279a58650d0ef10ab5a6a5d3da02d10b24c42edb1058a` |
| South Africa CAPS English home language R-3 | `south-africa-dbe-caps-english-home-language-grades-r-3` | `c939a3a9dcce92ed61d970f4599ced6f2ddc425d1220eeeab9828472b878d24d` |
| Ghana NaCCA maths B4-B6 | `ghana-nacca-primary-mathematics-basic-4-6` | `4b4439306ad2fafc07f92ca6061dcbfbde63975549177fde3c69393faf4a427c` |
| Ghana NaCCA English B1-B3 | `ghana-nacca-primary-english-language-basic-1-3` | `e49a792637011b32ed2ed906d58f9992e5208d2b7c15425ccc971f4f51de43c8` |
| India CBSE science 9-10 | `india-cbse-science-learning-framework-classes-9-10` | `df4fcc0a81e59e564d2d92d5dc6110652758b3b90f60e893b91113b44e5e4ef4` |

The Tamil Nadu package was not scored: we have no PDF for it.

## Result (n = 6 PDFs, router defaults)

| PDF | Pages | Gold pages | Kept | Gold pages kept | Pages skipped | Range saved by `--fill-config` |
|---|---|---|---|---|---|---|
| Rwanda | 147 | 84 | 129 | 84 (100%) | 12.2% | 5.4% |
| Nigeria | 37 | 37 | 37 | 37 (100%) | 0.0% | 0.0% |
| South Africa | 142 | 65 | 132 | 65 (100%) | 7.0% | 0.0% |
| Ghana maths | 183 | 158 | 174 | 158 (100%) | 4.9% | 0.5% |
| Ghana English | 125 | 98 | 121 | 98 (100%) | 3.2% | 0.0% |
| India CBSE | 124 | 69 | 118 | 69 (100%) | 4.8% | 4.0% |

The router kept every gold page of all six PDFs and flagged 0.0% to 12.2% of pages as skippable. Because the pipeline reads one contiguous range, the range actually saved is 0.0% to 5.4%.

## Limits

- Six PDFs, mostly primary level (one is grade 9-10 science), so the 100% is a small sample. The defaults were tuned on three of the six (Rwanda, Nigeria, Ghana maths). South Africa, Ghana English and CBSE were not part of that tuning, but we had seen them in earlier rounds, so none of the six is a clean held-out test.
- Gold is "pages cited by IDinsight's package". A standard the pipeline missed would not appear in it.
- "Skipped" is not precision. The kept pages that are not gold are often real continuation pages. The pipeline reads one contiguous page range, so `--fill-config` writes a single start-to-end range; savings come from trimming the front and back of the document, and are smaller than the skipped share. Savings in extraction cost were not measured.
- The range that `--fill-config` writes saves 0.0% to 5.4% of pages (Rwanda 5.4%, CBSE 4.0%, Ghana maths 0.5%, the other three 0%).
- Nigeria: every page is a gold page, so its row tests nothing.
- Not covered by this branch: any model-based pass for unsure pages.
- Not run here: a pipeline run using `route.json`.

## Reproduce

```
python -I scripts/score_page_router.py --src PATH_TO_BRANCH/backend/src --packages-dir KGForEdGlobalMCP/data/graph_packages \
  --case rwanda rwanda-reb-mathematics-lower-primary-1-3 PATH/rwanda_math_p1_p3_2025.pdf \
  --case nigeria nigeria-nerdc-mathematics-primary-1-3 PATH/nigeria_maths_1_3.pdf \
  --case south_africa south-africa-dbe-caps-english-home-language-grades-r-3 PATH/south_africa.pdf \
  --case ghana_maths ghana-nacca-primary-mathematics-basic-4-6 PATH/ghana_maths.pdf \
  --case ghana_english ghana-nacca-primary-english-language-basic-1-3 PATH/ghana_english.pdf \
  --case india_cbse india-cbse-science-learning-framework-classes-9-10 PATH/india_cbse.pdf
```

Replace each `PATH/...pdf` with the file whose sha256 is in the Inputs table (file names do not matter, contents do).
