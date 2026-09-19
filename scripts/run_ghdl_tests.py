#!/usr/bin/env python3
"""Run the existing Hi-Lo unit benches in isolated GHDL work directories.

Uses the Bender source-order / temporary-workdir pattern of AI-Trigger-System's
scripts/run_ghdl_tests.py. File-driven analysis benches are compiled, but need
their own stimulus driver and are not silently counted as executed tests.
"""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UNIT_TESTS = ("tb_pre_trigger_1ch", "tb_pre_trigger")


def bender_sources(target):
    result = subprocess.run(
        ["bender", "script", "flist", "-t", target], cwd=ROOT,
        check=True, capture_output=True, text=True,
    )
    return [Path(line) for line in result.stdout.splitlines()
            if line.lower().endswith((".vhd", ".vhdl"))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tests", nargs="*", help="Unit test names; default: both benches.")
    parser.add_argument("--output", type=Path, default=ROOT / "build/ghdl")
    args = parser.parse_args()
    if any(name not in UNIT_TESTS for name in args.tests):
        parser.error("unknown test; choose from " + ", ".join(UNIT_TESTS))
    args.output.mkdir(parents=True, exist_ok=True)
    sources = bender_sources("simulation")
    if not sources or any(not path.is_file() for path in sources):
        raise SystemExit("Bender returned an empty or incomplete VHDL source list")
    results = []
    for name in args.tests or UNIT_TESTS:
        with tempfile.TemporaryDirectory(prefix=f"hilo-{name}-") as tmp:
            commands = [
                ["ghdl", "-a", "--std=08", *(str(path) for path in sources)],
                ["ghdl", "-e", "--std=08", name],
                ["ghdl", "-r", "--std=08", name, "--assert-level=error",
                 "--ieee-asserts=disable-at-0", "--stop-time=100us"],
            ]
            transcript = ""
            passed = True
            for command in commands:
                run = subprocess.run(command, cwd=tmp, capture_output=True, text=True)
                transcript += run.stdout + run.stderr
                if run.returncode or "simulation stopped by --stop-time" in transcript:
                    passed = False
                    break
            (args.output / f"{name}.log").write_text(transcript)
            results.append({"test": name, "passed": passed})
            print(f"{'PASS' if passed else 'FAIL'} {name}", flush=True)
            if not passed:
                print(transcript)
    (args.output / "summary.json").write_text(json.dumps(results, indent=2) + "\n")
    return 0 if all(item["passed"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
