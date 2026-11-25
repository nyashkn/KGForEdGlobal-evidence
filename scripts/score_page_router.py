"""Check kn/page-router: page recall and pages skipped by the model-free router.

Branch checked: kn/page-router (540019e), also present in kn/integration.
Evidence file: evidence/page-router.md

For each curriculum PDF it runs the router (`route_page_inputs`, text layer only, no model calls) and
compares the pages it keeps with the pages that IDinsight's published package cites as the source of
at least one standard. Gold is read here only; the router never sees it. It also reports how much the
single page range written by `route_pages.py --fill-config` (first kept page to last kept page) would
shrink the document, because the pipeline reads one contiguous range.

Inputs (all CLI arguments):
  --src           the backend/src folder of the code under test (the branch).
  --packages-dir  the data/graph_packages folder of a checkout of IDinsight/KGForEdGlobalMCP.
  --case          repeat once per curriculum: LABEL PACKAGE_DIR_NAME PDF_PATH
                  PACKAGE_DIR_NAME is the folder name under --packages-dir; its
                  <version>/slim/as_entity_provenance.json supplies the gold page indexes (0-based).
                  PDF_PATH is the curriculum PDF that package was built from. Page indexes only line up
                  when it is the same file, so check the sha256 in evidence/page-router.md.
  --param         optional KEY=VALUE override of a RouterParams field (repeatable).
  --out           optional path for the per-curriculum rows as JSON.

Example:
  python -I scripts/score_page_router.py --src PATH/backend/src --packages-dir MCP/data/graph_packages \
      --case rwanda rwanda-reb-mathematics-lower-primary-1-3 rwanda_math_p1_p3_2025.pdf
"""

import argparse
import glob
import json
import os
import sys
import time
from pathlib import Path


def _prepare_environment(src: str) -> None:
    """Put the code under test first on the path and fill the fake settings the package validates on import."""
    sys.path.insert(0, str(Path(src).resolve()))
    os.environ.setdefault("LEARNING_COMMONS_EXPORT_SCHEMA_VERSION", "2026-07-09")
    os.environ.setdefault("PATHS_PROJECT_DIR", str(Path(src).resolve().parent.parent))
    os.environ.setdefault("OPENAI_API_KEY", "test")
    os.environ.setdefault("CHAT_ENV", "testing")


def gold_pages(packages_dir: str, package: str) -> set[int]:
    """Return the 0-based pages cited by at least one standard in the package's provenance file."""
    matches = glob.glob(os.path.join(packages_dir, package, "*", "slim", "as_entity_provenance.json"))
    if len(matches) != 1:
        raise SystemExit(f"expected exactly one provenance file for package {package!r} under {packages_dir}, found {len(matches)}")
    path = matches[0]
    pages: set[int] = set()
    for item in json.load(open(path))["items"].values():
        pages |= set(item["source_page_indexes"])
    return pages


def main() -> None:
    """Score every case and print one table."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="backend/src of the code under test")
    ap.add_argument("--packages-dir", required=True, help="data/graph_packages of the IDinsight MCP repo")
    ap.add_argument("--case", required=True, nargs=3, action="append", metavar=("LABEL", "PACKAGE_DIR_NAME", "PDF_PATH"))
    ap.add_argument("--param", action="append", default=[], help="RouterParams override KEY=VALUE")
    ap.add_argument("--out", help="write rows as JSON")
    args = ap.parse_args()
    _prepare_environment(args.src)

    # pylint: disable=import-outside-toplevel
    from kgfeg.page_router.router import read_pdf, route_page_inputs
    from kgfeg.page_router.schemas import RouterParams

    overrides = {k: (int(v) if v.lstrip("-").isdigit() else float(v)) for k, v in (s.split("=") for s in args.param)}
    params = RouterParams(**overrides)
    rows = []
    print(f"{'label':16}{'pages':>6}{'gold':>6}{'kept':>6}{'recall':>8}{'missed':>7}{'skipped%':>10}{'range_saved%':>14}")
    for label, package, pdf in args.case:
        gold = gold_pages(args.packages_dir, package)
        started = time.time()
        pages, outline = read_pdf(pdf)
        route = route_page_inputs(pages, outline=outline, params=params)
        kept = set(route.included)
        if not kept:
            raise SystemExit(f"{label}: the router kept no page")
        range_pages = max(kept) - min(kept) + 1
        missed = sorted(gold - kept)
        row = {
            "label": label,
            "pages": route.page_count,
            "gold_pages": len(gold),
            "kept_pages": len(kept),
            "recall": round(1 - len(missed) / len(gold), 4),
            "missed_pages": missed,
            "skipped_pct": round(100 * (route.page_count - len(kept)) / route.page_count, 1),
            "range_saved_pct": round(100 * (route.page_count - range_pages) / route.page_count, 1),
            "seconds": round(time.time() - started, 1),
        }
        rows.append(row)
        print(
            f"{label:16}{row['pages']:>6}{row['gold_pages']:>6}{row['kept_pages']:>6}"
            f"{row['recall'] * 100:>7.1f}%{len(missed):>7}{row['skipped_pct']:>9.1f}%{row['range_saved_pct']:>13.1f}%"
        )
    if args.out:
        json.dump({"params": params.model_dump(), "rows": rows}, open(args.out, "w"), indent=1)


if __name__ == "__main__":
    main()
