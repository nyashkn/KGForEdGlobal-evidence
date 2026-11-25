"""Check kn/sibling-position-export: the opt-in `position` property of the Learning Commons export.

Branch checked: kn/sibling-position-export (d3ee9b2), also present in kn/integration.
Evidence file: evidence/sibling-position-export.md

What it does, with no model calls:
  1. Copies the run's `kgs` folder to a scratch folder and re-runs only
     `compile_academic_standards_kg` (the export step) with `emit_sibling_position` false.
     Reports whether `as_nodes.jsonl` is byte-identical to the file the pipeline wrote.
  2. Repeats with `emit_sibling_position` true. Reports how many items carry `position`,
     whether the positions inside each parent group are exactly 0..n-1, and whether any
     node or relationship changed other than a node gaining `position`.
  3. If --pdf is given, compares sibling order with the order of the same texts in the
     PDF text layer (PyMuPDF reading order). Only items whose text occurs exactly once in
     the PDF are used, and items with more than one parent are skipped. The PDF text layer is also what the
     page-IR step receives as hints when `use_extracted_hints` is on, so this is not an independent check.

Inputs (all CLI arguments):
  --src     the backend/src folder of the code under test (a checkout or `git archive` of the branch).
  --run     a run folder written by the pipeline: it must contain
            results/<id>/stitching/document_ir.json and results/<id>/kgs/
            (with sfi_final_contexts.json, sfi_final_records.json, has_child_edges_final.json,
            as_nodes.jsonl, as_relationships.jsonl).
  --config  the JSON config file used for that run (the file with a top-level "kgs" key).
  --pdf     optional: the source PDF of that run.

Run it with the backend virtualenv of the branch, for example:
  python -I scripts/check_position.py --src PATH/backend/src --run RUN --config CONFIG.json --pdf SOURCE.pdf
"""

import argparse
import glob
import json
import os
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path


def _prepare_environment(src: str) -> None:
    """Put the code under test first on the path and fill the fake settings the package validates on import."""
    sys.path.insert(0, str(Path(src).resolve()))
    os.environ.setdefault("LEARNING_COMMONS_EXPORT_SCHEMA_VERSION", "2026-07-09")
    os.environ.setdefault("PATHS_PROJECT_DIR", str(Path(src).resolve().parent.parent))
    os.environ.setdefault("OPENAI_API_KEY", "test")
    os.environ.setdefault("CHAT_ENV", "testing")


def _export(results: Path, kgs_copy: Path, config: dict, emit: bool) -> None:
    """Re-run the export step on a scratch copy of `kgs`; it rewrites as_nodes.jsonl and as_relationships.jsonl there."""
    # pylint: disable=import-outside-toplevel
    from kgfeg.document_ir.schemas import DocumentIR
    from kgfeg.kgs.schemas import SFIHasChildEdge
    from kgfeg.kgs.sfi_export import compile_academic_standards_kg
    from kgfeg.kgs.utils import KGDirs
    from kgfeg.schemas import CreateKGConfig

    kg_cfg = json.loads(json.dumps(config["kgs"]))
    kg_cfg.setdefault("as", {})["emit_sibling_position"] = emit
    document_ir = DocumentIR.model_validate_json((results / "stitching" / "document_ir.json").read_text())
    edges = [SFIHasChildEdge.model_validate(e) for e in json.loads((kgs_copy / "has_child_edges_final.json").read_text())]
    compile_academic_standards_kg(
        document_ir=document_ir,
        has_child_edges=edges,
        kg_config=CreateKGConfig.model_validate(kg_cfg),
        kg_dirs=KGDirs(root=kgs_copy),
        overwrite=True,
    )


def _jsonl(path: Path) -> list[dict]:
    """Read a JSON-lines file."""
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _group_check(nodes: list[dict], rels: list[dict]) -> dict[str, list[str]]:
    """Group item identifiers by parent and report whether positions are exactly 0..n-1 in every group."""
    items = {n["properties"]["identifier"]: n["properties"] for n in nodes if "StandardsFrameworkItem" in n["labels"]}
    parents: dict[str, list[str]] = defaultdict(list)
    for rel in rels:
        parents[rel["properties"]["targetEntityValue"]].append(rel["properties"]["sourceEntityValue"])
    groups: dict[str, list[str]] = defaultdict(list)
    for child, plist in parents.items():
        if child in items and len(plist) == 1:
            groups[plist[0]].append(child)
    multi = sum(1 for plist in parents.values() if len(plist) > 1)
    roots = [i for i in items if i not in parents]
    if roots:
        groups["<framework>"] = roots
    exact = sum(
        1 for g in groups.values() if sorted(int(items[c]["position"]) for c in g if "position" in items[c]) == list(range(len(g)))
    )
    print(f"flag on: {exact} of {len(groups)} parent groups have positions exactly 0..n-1; items with more than one parent: {multi}")
    return groups


def _pdf_order(nodes: list[dict], groups: dict[str, list[str]], pdf: str) -> None:
    """Compare sibling order with PDF text order for items whose text occurs exactly once in the PDF."""
    import fitz  # pylint: disable=import-outside-toplevel

    with fitz.open(pdf) as doc:
        text = re.sub(r"\s+", " ", "\n".join(page.get_text() for page in doc))
    items = {n["properties"]["identifier"]: n["properties"] for n in nodes if "position" in n["properties"]}

    def where(identifier: str):
        desc = re.sub(r"\s+", " ", items[identifier].get("description", "")).strip()
        return text.index(desc) if len(desc) >= 12 and text.count(desc) == 1 else None

    where_by_id = {i: where(i) for i in items}
    left_out: dict[str, int] = defaultdict(int)
    for identifier, position in where_by_id.items():
        if position is None:
            left_out[items[identifier].get("statementType", "?")] += 1
    print(f"pdf order: {sum(v is not None for v in where_by_id.values())} of {len(items)} items have text found exactly once in the PDF")
    print(f"pdf order: items left out, by statement type: {dict(sorted(left_out.items()))}")
    tally = {"same statement type": [0, 0], "all types": [0, 0]}
    for children in groups.values():
        ordered = sorted((c for c in children if c in items), key=lambda c: int(items[c]["position"]))
        for i, a in enumerate(ordered):
            for b in ordered[i + 1 :]:
                if where_by_id[a] is None or where_by_id[b] is None:
                    continue
                ok = where_by_id[a] < where_by_id[b]
                kinds = ["all types"] + (["same statement type"] if items[a].get("statementType") == items[b].get("statementType") else [])
                for kind in kinds:
                    tally[kind][1] += 1
                    tally[kind][0] += ok
    for kind, (good, total) in tally.items():
        print(f"pdf order, {kind}: {good} of {total} sibling pairs in PDF order")


def main() -> None:
    """Parse arguments and run the checks."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="backend/src of the code under test")
    ap.add_argument("--run", required=True, help="run folder containing results/<id>/")
    ap.add_argument("--config", required=True, help="the run's config JSON (has a top-level 'kgs' key)")
    ap.add_argument("--pdf", help="optional source PDF for the PDF-order check")
    args = ap.parse_args()
    _prepare_environment(args.src)

    found = glob.glob(os.path.join(args.run, "results", "*"))
    if len(found) != 1:
        raise SystemExit(f"expected exactly one folder under {args.run}/results, found {len(found)}")
    results = Path(found[0])
    config = json.loads(Path(args.config).read_text())
    stored_nodes = results / "kgs" / "as_nodes.jsonl"
    stored_rels = results / "kgs" / "as_relationships.jsonl"
    scratch = Path(tempfile.mkdtemp())
    try:
        off_dir, on_dir = scratch / "off", scratch / "on"
        shutil.copytree(results / "kgs", off_dir)
        shutil.copytree(results / "kgs", on_dir)
        _export(results, off_dir, config, False)
        _export(results, on_dir, config, True)

        print(f"flag off: as_nodes.jsonl byte-identical to the stored file: {(off_dir / 'as_nodes.jsonl').read_bytes() == stored_nodes.read_bytes()}")
        old = {n["properties"]["identifier"]: n for n in _jsonl(stored_nodes)}
        new = _jsonl(on_dir / "as_nodes.jsonl")
        with_position = sum("position" in n["properties"] for n in new)
        changed = 0
        for node in new:
            stripped = json.loads(json.dumps(node))
            stripped["properties"].pop("position", None)
            changed += stripped != old.get(node["properties"]["identifier"])
        print(f"flag on: {with_position} of {len(new)} nodes carry position")
        print(f"flag on: nodes that differ from the stored export in anything other than position: {changed}")
        print(f"flag on: as_relationships.jsonl byte-identical to the stored file: {(on_dir / 'as_relationships.jsonl').read_bytes() == stored_rels.read_bytes()}")
        groups = _group_check(new, _jsonl(on_dir / "as_relationships.jsonl"))
        if args.pdf:
            _pdf_order(new, groups, args.pdf)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
