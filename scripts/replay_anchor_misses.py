"""Check kn/sfi-anchor-line-breaks: re-resolve logged source-anchor misses.

Branch checked: kn/sfi-anchor-line-breaks (ea27119), also present in kn/integration.
Evidence file: evidence/sfi-anchor-line-breaks.md

The pipeline logs `Source excerpt '...' does not have occurrence_index=N in source unit '...'`
when the model's copied anchor is not found in the source text. This script finds those lines in a
log, rebuilds the window's source units from the run's saved extraction windows, and tries each
failing anchor again with the code under test.
Output contains excerpts of the run's curriculum text; do not publish it. Set KGFEG_SFI_JOIN_LINE_BREAKS=1 to turn the
branch's fallback on; unset it for the strict (origin/main) behaviour. No model calls.

Inputs (all CLI arguments):
  --src   the backend/src folder of the code under test (a checkout or `git archive`).
  --run   a run folder with results/<id>/kgs/sfi_extraction_windows.jsonl.
  --log   a log file of that run (for example its create_kgs log) that contains the miss lines.

Example:
  KGFEG_SFI_JOIN_LINE_BREAKS=1 python -I scripts/replay_anchor_misses.py --src PATH/backend/src --run RUN --log RUN/create_kgs.log
"""

import argparse
import ast
import glob
import os
import re
import sys
from pathlib import Path


def _prepare_environment(src: str) -> None:
    """Put the code under test first on the path and fill the fake settings the package validates on import."""
    sys.path.insert(0, str(Path(src).resolve()))
    os.environ.setdefault("LEARNING_COMMONS_EXPORT_SCHEMA_VERSION", "2026-07-09")
    os.environ.setdefault("PATHS_PROJECT_DIR", str(Path(src).resolve().parent.parent))
    os.environ.setdefault("OPENAI_API_KEY", "test")
    os.environ.setdefault("CHAT_ENV", "testing")


MISS = re.compile(r"Source excerpt ('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\") does not have occurrence_index=(\d+) in source unit '([^']+)'")


def main() -> None:
    """Re-resolve each distinct logged miss and print MATCH or MISS."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="backend/src of the code under test")
    ap.add_argument("--run", required=True, help="run folder containing results/<id>/")
    ap.add_argument("--log", required=True, help="log file containing the anchor-miss lines")
    args = ap.parse_args()
    _prepare_environment(args.src)

    # pylint: disable=import-outside-toplevel
    from kgfeg.kgs.schemas import ExtractionWindow, SFISourceAnchor
    from kgfeg.kgs.sfi_source_anchors import build_sfi_source_units, find_source_anchor_span

    found = glob.glob(os.path.join(args.run, "results", "*", "kgs", "sfi_extraction_windows.jsonl"))
    if len(found) != 1:
        raise SystemExit(f"expected exactly one sfi_extraction_windows.jsonl under {args.run}/results/*/kgs, found {len(found)}")
    windows = found[0]
    units = {}
    for line in open(windows):
        for unit in build_sfi_source_units(ExtractionWindow.model_validate_json(line)):
            units[unit.source_unit_id] = unit
    log = re.sub(r"\x1b\[[0-9;]*m", "", open(args.log, errors="ignore").read())
    seen, rows = set(), []
    for excerpt, occurrence, unit_id in MISS.findall(log):
        key = (excerpt, occurrence, unit_id)
        if key in seen:
            continue
        seen.add(key)
        text = ast.literal_eval(excerpt)
        unit = units.get(unit_id)
        if unit is None:
            rows.append(("unit-not-found", unit_id[-30:]))
            continue
        anchor = SFISourceAnchor.model_validate({"occurrence_index": int(occurrence), "source_text": text, "source_unit_id": unit_id})
        try:
            start, end = find_source_anchor_span(anchor=anchor, source_unit=unit)
            result = "MATCH " + repr(unit.source_text[start:end])[:70]
        except ValueError:
            result = "MISS"
        rows.append((result, "anchor=" + repr(text)[:60], "unit=" + repr(unit.source_text)[:90]))
    print(f"KGFEG_SFI_JOIN_LINE_BREAKS={os.environ.get('KGFEG_SFI_JOIN_LINE_BREAKS')} distinct failing anchors: {len(rows)}")
    for row in rows:
        print("  ", *row, sep=" | ")


if __name__ == "__main__":
    main()
