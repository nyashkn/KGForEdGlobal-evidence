"""Check kn/sfi-anchor-line-breaks: no regression on anchors that already matched.

Branch checked: kn/sfi-anchor-line-breaks (ea27119), also present in kn/integration.
Evidence file: evidence/sfi-anchor-line-breaks.md

For every description anchor recorded in the given runs, resolves its span with
KGFEG_SFI_JOIN_LINE_BREAKS=0 and again with =1, and counts anchors whose span differs. The
fallback runs only after a strict miss, so anchors that matched strictly must not change. No model calls.

Inputs (all CLI arguments):
  --src        the backend/src folder of the code under test (the branch).
  --runs-dir   a folder holding run folders.
  --run        one or more run folder names inside --runs-dir. Each needs
               results/<id>/kgs/sfi_extraction_windows.jsonl and sfi_extraction_results.jsonl.

Example:
  python -I scripts/compare_anchor_flag.py --src PATH/backend/src --runs-dir RUNS --run run_a run_b
"""

import argparse
import glob
import json
import os
import sys
from pathlib import Path


def _prepare_environment(src: str) -> None:
    """Put the code under test first on the path and fill the fake settings the package validates on import."""
    sys.path.insert(0, str(Path(src).resolve()))
    os.environ.setdefault("LEARNING_COMMONS_EXPORT_SCHEMA_VERSION", "2026-07-09")
    os.environ.setdefault("PATHS_PROJECT_DIR", str(Path(src).resolve().parent.parent))
    os.environ.setdefault("OPENAI_API_KEY", "test")
    os.environ.setdefault("CHAT_ENV", "testing")


def main() -> None:
    """Count anchors whose span depends on the flag."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="backend/src of the code under test")
    ap.add_argument("--runs-dir", required=True, help="folder holding the run folders")
    ap.add_argument("--run", required=True, nargs="+", help="run folder names inside --runs-dir")
    args = ap.parse_args()
    _prepare_environment(args.src)

    # pylint: disable=import-outside-toplevel
    from kgfeg.kgs.schemas import ExtractionWindow, SFISourceAnchor
    from kgfeg.kgs.sfi_source_anchors import build_sfi_source_units, find_source_anchor_span

    total = dict(runs=0, windows=0, candidates=0, anchors=0, span_differences=0, errors=0)
    for run in args.run:
        base = os.path.join(args.runs_dir, run, "results", "*", "kgs")
        window_files = glob.glob(os.path.join(base, "sfi_extraction_windows.jsonl"))
        result_files = glob.glob(os.path.join(base, "sfi_extraction_results.jsonl"))
        if not window_files or not result_files:
            print("skip", run)
            continue
        units = {}
        for line in open(window_files[0]):
            for unit in build_sfi_source_units(ExtractionWindow.model_validate_json(line)):
                units[unit.source_unit_id] = unit
        total["runs"] += 1
        for line in open(result_files[0]):
            window = json.loads(line)
            total["windows"] += 1
            for candidate in window["sfi_candidates"]:
                total["candidates"] += 1
                for anchor in candidate.get("description_source_anchors", []):
                    total["anchors"] += 1
                    spans = {}
                    for flag in ("0", "1"):
                        os.environ["KGFEG_SFI_JOIN_LINE_BREAKS"] = flag
                        try:
                            spans[flag] = find_source_anchor_span(
                                anchor=SFISourceAnchor.model_validate(anchor), source_unit=units[anchor["source_unit_id"]]
                            )
                        except Exception:  # pylint: disable=broad-except
                            spans[flag] = None
                            total["errors"] += 1
                    total["span_differences"] += spans["0"] != spans["1"]
    print(total)
    if total["errors"]:
        print(f"warning: {total['errors']} anchor lookups raised an error (counted, not treated as differences); check them before trusting the zero")


if __name__ == "__main__":
    main()
