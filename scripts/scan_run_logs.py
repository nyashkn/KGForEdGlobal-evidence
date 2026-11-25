"""Count SFI extraction integrity failures and final-UUID collisions in run logs.

Branches this supports: kn/sfi-anchor-line-breaks (how often anchor misses happen) and
kn/sfi-identity-key-collision (how often a natural collision happens).
Evidence files: evidence/sfi-anchor-line-breaks.md, evidence/sfi-identity-key-collision.md

Walks a folder of runs, reads every create_kgs log (and hamilton.log / pipeline.log if present) outside
the `results/**/kgs` artifact folders, and prints each `SFI extraction integrity check failed for window N
attempt M: ...` line plus whether the log mentions `UUID collisions detected`. Pure text scan, no code under test.

Output contains excerpts of the run's curriculum text; do not publish it.

Inputs (CLI argument):
  --runs-dir   a folder that holds run folders with their logs.

Example:
  python -I scripts/scan_run_logs.py --runs-dir RUNS
"""

import argparse
import os
import re


def main() -> None:
    """Scan the logs and print one block per log that has a failure."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs-dir", required=True, help="folder holding run folders and their logs")
    args = ap.parse_args()
    rows = []
    scanned = 0
    for dirpath, _dirs, files in os.walk(args.runs_dir, followlinks=True):
        if os.sep + "results" in dirpath + os.sep and "kgs" in dirpath:
            continue
        for name in files:
            if name.endswith(".log") and ("create_kgs" in name or name in ("hamilton.log", "pipeline.log")):
                path = os.path.join(dirpath, name)
                scanned += 1
                text = re.sub(r"\x1b\[[0-9;]*m", "", open(path, errors="ignore").read())
                events = re.findall(r"SFI extraction integrity check failed for window (\d+) attempt (\d+): (.{0,260})", text)
                collided = "UUID collisions detected" in text
                if events or collided:
                    rows.append((os.path.relpath(path, args.runs_dir), events, collided))
    for path, events, collided in rows:
        print(f"## {path} events {len(events)} uuid_collision {collided}")
        for window, attempt, message in events:
            print(f"   w{window} a{attempt} {message.replace(chr(10), ' / ')[:230]}")
    print(f"logs scanned: {scanned}")
    print(f"logs with a failure: {len(rows)}; logs with a UUID collision: {sum(1 for r in rows if r[2])}")


if __name__ == "__main__":
    main()
