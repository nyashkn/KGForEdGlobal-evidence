"""Check kn/sfi-identity-key-collision: dedup groups that end up with one final identity key.

Branch checked: kn/sfi-identity-key-collision (06b5a94), also present in kn/integration.
Evidence file: evidence/sfi-identity-key-collision.md

For each run it rebuilds the SFI merge groups from the run's recorded candidate registry and
recorded dedup responses, then calls the real `mint_final_sfi_ids`. No model calls.
  recorded  uses the responses as the model gave them.
  flip      turns every recorded `merge` decision into `keep_separate`. This simulates a checker
            that reverts the producer's merge of repeated headings (there is no natural public
            crash in the runs we have).
Run it once with the code of origin/main and once with the branch to compare.

Inputs (all CLI arguments):
  --src       the backend/src folder of the code under test (a checkout or `git archive`).
  --run       one or more run folders written by the pipeline. Each needs
              results/<id>/stitching/document_ir.json and results/<id>/kgs/ with
              sfi_candidate_registry.json, sfi_dedup_review_responses.jsonl,
              sfi_final_records.json and sfi_merge_groups.json.
  --config    the run's config JSON (top-level "kgs" key). Default: <run>/config.json, else the first <run>/config*.json.
  --scenario  recorded or flip (default recorded).

Example (virtualenv of the backend, tests/test.env sourced or fake values for the settings):
  python -I scripts/replay_identity_key.py --src PATH/backend/src --run RUN1 RUN2 --scenario flip
"""

import argparse
import glob
import hashlib
import inspect
import json
import os
import sys
import tempfile
from pathlib import Path


def _prepare_environment(src: str) -> None:
    """Put the code under test first on the path and fill the fake settings the package validates on import."""
    sys.path.insert(0, str(Path(src).resolve()))
    os.environ.setdefault("LEARNING_COMMONS_EXPORT_SCHEMA_VERSION", "2026-07-09")
    os.environ.setdefault("PATHS_PROJECT_DIR", str(Path(src).resolve().parent.parent))
    os.environ.setdefault("OPENAI_API_KEY", "test")
    os.environ.setdefault("CHAT_ENV", "testing")


def replay(run: str, config_path: str | None, scenario: str) -> str:
    """Replay one run and return a verdict word: ok, crash or no-registry."""
    # pylint: disable=import-outside-toplevel
    from kgfeg.document_ir.schemas import DocumentIR
    from kgfeg.kgs import sfi_dedup as dedup
    from kgfeg.kgs.schemas import SFIDedupReviewResponse, SFIRegistryArtifact
    from kgfeg.kgs.sfi_finalization import mint_final_sfi_ids
    from kgfeg.kgs.utils import KGDirs
    from kgfeg.schemas import CreateKGConfig

    found = glob.glob(os.path.join(run, "results", "*"))
    if len(found) != 1:
        raise SystemExit(f"expected exactly one folder under {run}/results, found {len(found)}")
    results = found[0]
    kgs = os.path.join(results, "kgs")
    if not os.path.exists(os.path.join(kgs, "sfi_candidate_registry.json")):
        print(f"{run}: no saved registry, skipped")
        return "no-registry"
    candidates = [config_path] if config_path else [os.path.join(run, "config.json"), *sorted(glob.glob(os.path.join(run, "config*.json")))]
    config_file = next((p for p in candidates if p and os.path.exists(p)), None)
    if config_file is None:
        raise SystemExit(f"no config found for {run}; pass --config")
    kg_config = CreateKGConfig.model_validate(json.load(open(config_file))["kgs"])
    document_ir = DocumentIR.model_validate_json(open(os.path.join(results, "stitching", "document_ir.json")).read())
    registry = SFIRegistryArtifact.model_validate_json(open(os.path.join(kgs, "sfi_candidate_registry.json")).read())
    responses = [
        SFIDedupReviewResponse.model_validate_json(line)
        for line in open(os.path.join(kgs, "sfi_dedup_review_responses.jsonl"))
        if line.strip()
    ]
    flipped = 0
    if scenario == "flip":
        for response in responses:
            for group in response.decision_groups:
                if group.decision == "merge" and len(group.candidate_ids) > 1:
                    group.decision = "keep_separate"
                    flipped += 1

    by_id = {c.registry_candidate_id: c for c in registry.candidates}
    edges = dedup._build_initial_review_edges(registry)  # pylint: disable=protected-access
    components = dedup._split_and_bound_components(  # pylint: disable=protected-access
        components=dedup._merge_edges_to_components(edges),  # pylint: disable=protected-access
        kg_config=kg_config,
        sfi_candidates_by_id=by_id,
    )
    requests, unresolved = dedup._build_review_requests(  # pylint: disable=protected-access
        components=components, kg_config=kg_config, sfi_candidate_registry=registry, sfi_candidates_by_id=by_id
    )
    kwargs = dict(
        review_responses=responses, sfi_candidate_registry=registry, sfi_candidates_by_id=by_id, unresolved_components=unresolved
    )
    if "document_ir" in inspect.signature(dedup._build_current_merge_groups).parameters:  # pylint: disable=protected-access
        kwargs.update(document_ir=document_ir, kg_config=kg_config)
    try:
        groups, unreviewed = dedup._build_current_merge_groups(**kwargs)  # pylint: disable=protected-access
    except Exception as exc:  # pylint: disable=broad-except
        print(f"{os.path.basename(run)} {scenario}: flipped={flipped} MERGE-STEP-ERROR {type(exc).__name__}: {str(exc)[:200]}")
        return "crash"
    report = dedup._build_merge_report(  # pylint: disable=protected-access
        merge_groups=groups,
        review_requests=requests,
        review_responses=responses,
        sfi_candidate_registry=registry,
        unreviewed_singleton_count=unreviewed,
    )
    try:
        records = mint_final_sfi_ids(
            document_ir=document_ir,
            kg_config=kg_config,
            kg_dirs=KGDirs(root=Path(tempfile.mkdtemp())),
            sfi_candidate_registry=registry,
            sfi_merge_report=report,
        )
    except Exception as exc:  # pylint: disable=broad-except
        print(f"{os.path.basename(run)} {scenario}: flipped={flipped} groups={len(groups)} MINT-ERROR {type(exc).__name__}: {str(exc)[:200]}")
        return "crash"
    ids = sorted(str(r.final_sfi_uuid) for r in records)
    recorded_ids = sorted(str(x["final_sfi_uuid"]) for x in json.load(open(os.path.join(kgs, "sfi_final_records.json"))))
    forced = sum(1 for g in groups if "identity_key_forced_merge" in (g.audit_flags or []))
    line = (
        f"{os.path.basename(run)} {scenario}: flipped={flipped} groups={len(groups)} final_sfis={len(records)} "
        f"forced_merges={forced} same_uuid_set_as_recorded_run={recorded_ids == ids} "
        f"idhash={hashlib.sha256('|'.join(ids).encode()).hexdigest()[:10]}"
    )
    if scenario == "recorded":
        recorded_groups = sorted(x["merge_group_id"] for x in json.load(open(os.path.join(kgs, "sfi_merge_groups.json"))))
        line += f" same_merge_group_ids_as_recorded={sorted(g.merge_group_id for g in groups) == recorded_groups}"
    print(line)
    return "ok"


def main() -> None:
    """Parse arguments, replay each run and print a total."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="backend/src of the code under test")
    ap.add_argument("--run", required=True, nargs="+", help="run folder(s) containing results/<id>/")
    ap.add_argument("--config", help="config JSON (default: <run>/config.json, else <run>/config*.json)")
    ap.add_argument("--scenario", choices=["recorded", "flip"], default="recorded")
    args = ap.parse_args()
    _prepare_environment(args.src)
    verdicts = [replay(run, args.config, args.scenario) for run in args.run]
    print(f"total: {verdicts.count('ok')} minted, {verdicts.count('crash')} crashed, {verdicts.count('no-registry')} skipped")


if __name__ == "__main__":
    main()
