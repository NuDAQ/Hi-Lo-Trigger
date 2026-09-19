#!/usr/bin/env python3
"""Qualify the historical Hi-Lo stimulus generator and file-driven bench."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np

from run_ghdl_tests import ROOT, bender_sources

sys.path.insert(0, str(ROOT / "analysis/scripts"))
from submodule.stimulus_generation import generate_stimulus_file


def check_packing(work):
    data = np.arange(2 * 4 * 32, dtype=float).reshape(2, 4, 32) / 64
    data[0, 0, :4] = [-100, 100, 1.5 / 64, 2.5 / 64]
    np.save(work / "events.npy", data)
    clocks = generate_stimulus_file(work / "events.npy", work / "stimulus.txt")
    assert clocks == 2, f"16-sample profile needs two clocks/event, got {clocks}"
    actual = np.loadtxt(work / "stimulus.txt", dtype=int)
    expected = np.clip(np.rint(data * 64), -2048, 2047).astype(int)
    expected = expected.reshape(2, 4, 2, 16).transpose(0, 2, 1, 3).reshape(4, 64)
    np.testing.assert_array_equal(actual, expected)
    for single in (data[:1], data[0], data[:1, ..., np.newaxis]):
        np.save(work / "events.npy", single)
        assert generate_stimulus_file(work / "events.npy", work / "stimulus.txt") == 2
        np.testing.assert_array_equal(np.loadtxt(work / "stimulus.txt", dtype=int), expected[:2])
    np.save(work / "events.npy", data[..., :31])
    try:
        generate_stimulus_file(work / "events.npy", work / "stimulus.txt")
    except ValueError:
        pass
    else:
        raise AssertionError("non-integral aggregates must not silently lose samples")


def run(command, work):
    result = subprocess.run(command, cwd=work, capture_output=True, text=True)
    with (work / "ghdl.log").open("a") as log:
        log.write("$ " + " ".join(map(str, command)) + "\n")
        log.write(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "simulation stopped by --stop-time" not in result.stdout, "bench timed out"


def check_isolation(work):
    # A crossing in the last accepted batch must be observed before event reset.
    batches = np.zeros((2, 4, 16), dtype=int)
    batches[0, 0, 14:16] = [200, -200]
    np.savetxt(work / "stimulus.txt", batches.reshape(2, 64), fmt="%d")
    sources = bender_sources("simulation")
    bench = ROOT / "hw/sim/tb_hilo_trigger.vhd"
    assert bench in sources, "Bender simulation target must include the file-driven bench"
    run(["ghdl", "-a", "--std=08", *map(str, sources)], work)
    run(["ghdl", "-e", "--std=08", "tb_hilo_trigger"], work)
    run(["ghdl", "-r", "--std=08", "tb_hilo_trigger",
         "-gENABLE_RESET_ISOLATION=true", "-gCLOCKS_PER_EVENT=1",
         "--assert-level=error", "--ieee-asserts=disable-at-0",
         "--stop-time=100us"], work)
    actual = np.loadtxt(work / "hw_resp.txt", dtype=int, ndmin=1)
    np.testing.assert_array_equal(actual, [1, 0])


def main():
    checks = {"packing": check_packing, "isolation": check_isolation}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", choices=checks, action="append")
    parser.add_argument("--output", type=Path, default=ROOT / "build/cosim")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    for name in args.check or checks:
        with tempfile.TemporaryDirectory(prefix=f"hilo-{name}-") as tmp:
            work = Path(tmp)
            try:
                checks[name](work)
                result = {"test": name, "passed": True}
            except (AssertionError, ValueError) as error:
                result = {"test": name, "passed": False, "error": str(error)}
            if (work / "ghdl.log").exists():
                (args.output / f"{name}.log").write_text((work / "ghdl.log").read_text())
            results.append(result)
            print(json.dumps(result), flush=True)
    (args.output / "summary.json").write_text(json.dumps(results, indent=2) + "\n")
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
