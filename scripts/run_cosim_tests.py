#!/usr/bin/env python3
"""Qualify the historical Hi-Lo stimulus generator and file-driven bench."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np

from run_ghdl_tests import ROOT, bender_sources

sys.path.insert(0, str(ROOT / "analysis/scripts"))
from submodule.stimulus_generation import generate_stimulus_file, source_profile


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
    assert "simulation stopped by --stop-time" not in result.stdout + result.stderr, "bench timed out"


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


def check_reference(work):
    # Independent worked example: hi@14 remains active through 44; lo@32
    # overlaps at 32..44, then a two-sample coincidence extends through 45.
    from plot_rtl_emulation import evaluate_windows
    hi = np.zeros((4, 64), dtype=bool)
    lo = np.zeros_like(hi)
    hi[0, 14] = True
    lo[0, 32] = True
    gate, coinc, mult = evaluate_windows(hi, lo, 31, 2)
    np.testing.assert_array_equal(np.flatnonzero(gate[0]), np.arange(32, 45))
    np.testing.assert_array_equal(np.flatnonzero(coinc[0]), np.arange(32, 46))
    np.testing.assert_array_equal(np.flatnonzero(mult), np.arange(32, 46))
    for hilo, coincidence in ((0, 2), (31, 0)):
        _, coinc, mult = evaluate_windows(hi, lo, hilo, coincidence)
        assert not coinc.any() and not mult.any()


def compile_core(work, legacy=False):
    work.mkdir()
    sources = bender_sources("rtl")
    bench = (ROOT / "hw/sim/tb_hilo_trigger.vhd").read_text()
    if legacy:
        old_sources = []
        for source in sources:
            # Compile the original release RTL unchanged. Only adapt the shared
            # testbench's public port names and widths to the legacy interface.
            text = subprocess.check_output(
                ["git", "show", f"v2.2.4:{source.relative_to(ROOT)}"], cwd=ROOT, text=True)
            path = work / source.name
            path.write_text(text)
            old_sources.append(path)
        sources = old_sources
        bench = bench.replace("adc_ch_data_type", "adc_data4_type").replace("ADC_DATA", "ADC_DATA4")
        bench = bench.replace("N_BITS", "12").replace("N_CHANNEL", "4").replace("N_WIN_WIDTH", "5")
        bench = bench.replace("COINC_WINDOW : std_logic_vector(5-1", "COINC_WINDOW : std_logic_vector(6-1")
    bench_path = work / "tb_hilo_trigger.vhd"
    bench_path.write_text(bench)
    run(["ghdl", "-a", "--std=08", *map(str, sources), str(bench_path)], work)
    run(["ghdl", "-e", "--std=08", "tb_hilo_trigger"], work)


def simulate(work, data, threshold, hilo, coincidence, multiplicity, isolated, gap):
    np.save(work / "events.npy", data)
    clocks = generate_stimulus_file(work / "events.npy", work / "stimulus.txt")
    run(["ghdl", "-r", "--std=08", "tb_hilo_trigger",
         f"-gTHRESHOLD={threshold}", f"-gHILO_WINDOW_VALUE={hilo}",
         f"-gCOINC_WINDOW_VALUE={coincidence}", f"-gBIN_THRESHOLD={multiplicity}",
         f"-gCLOCKS_PER_EVENT={clocks}", f"-gENABLE_RESET_ISOLATION={str(isolated).lower()}",
         f"-gGAP_CYCLES={gap}", "--assert-level=error",
         "--ieee-asserts=disable-at-0", "--stop-time=1ms"], work)
    return np.loadtxt(work / "hw_resp.txt", dtype=int, ndmin=1)


def expected_decisions(data, threshold, hilo, coincidence, multiplicity, isolated):
    from plot_rtl_emulation import evaluate_windows
    profile = source_profile()
    limit = 2 ** (profile["N_BITS"] - 1)
    raw = np.clip(np.rint(data * 64), -limit, limit - 1).astype(int)
    # Preserve N_BITS-wide signed negation, including its existing minimum-value wrap.
    negative_threshold = ((-threshold + limit) % (2 * limit)) - limit
    streams = raw if isolated else [raw.transpose(1, 0, 2).reshape(profile["N_CHANNEL"], -1)]
    decisions = []
    for stream in streams:
        _, _, mult = evaluate_windows(stream > threshold, stream < negative_threshold, hilo, coincidence)
        decisions.extend(np.any((mult >= multiplicity).reshape(-1, profile["N_SAMPLES"]), axis=1))
    return np.asarray(decisions, dtype=int)


def check_regression(work):
    profile = source_profile()
    assert profile == {"N_SAMPLES": 16, "N_BITS": 12, "N_CHANNEL": 4, "N_WIN_WIDTH": 8}, \
        "this release qualifies only the agreed 16 x 4 x 12, 8-bit-window profile"
    compile_core(work / "new")
    compile_core(work / "legacy", legacy=True)
    rng = np.random.default_rng(3000)
    raw = rng.integers(-100, 101, size=(2, 4, 1024))
    raw[:, :, 512:] = 0  # long quiet tail exposes carry expiry, not only trigger onset
    for event in range(2):
        for channel in range(4):
            positions = rng.choice(512, size=12, replace=False)
            raw[event, channel, positions] = rng.choice([-2048, -101, 101, 2047], size=12)
    raw[0, 0, 14] = 200
    raw[0, 0, 32] = -200
    raw[0, 1, 255:257] = [200, -200]
    data = raw / 64.0
    common = [(100, h, c, b) for h, c, b in
              [(0, 32, 2), (1, 32, 2), (2, 1, 1), (5, 0, 2),
               (5, 16, 2), (5, 30, 1), (5, 32, 2), (15, 31, 3), (16, 32, 4)]]
    common += [(threshold, 5, 32, 2) for threshold in (-2048, -1, 0, 2047)]
    common += [(100, 5, 32, multiplicity) for multiplicity in (0, 5, 15)]
    extended = [(100, h, c, 2) for h, c in
                [(17, 32), (31, 32), (32, 33), (33, 16), (63, 64),
                 (127, 128), (128, 127), (254, 255), (255, 254),
                 (255, 255), (5, 255), (255, 1), (0, 255), (255, 0)]]
    records = []
    for config in common + extended:
        for isolated, gap in ((False, 0), (True, 2)):
            expected = expected_decisions(data, *config, isolated)
            actual = simulate(work / "new", data, *config, isolated, gap)
            label = f"config={config}, isolated={isolated}, gap={gap}"
            np.testing.assert_array_equal(actual, expected, err_msg=label)
            if config in common:
                old = simulate(work / "legacy", data, *config, isolated, gap)
                np.testing.assert_array_equal(actual, old, err_msg="v2.2.4 equivalence: " + label)
            records.append({"config": config, "isolated": isolated, "gap": gap,
                            "batches": len(actual), "triggered_batches": int(actual.sum()),
                            "legacy_compared": config in common})
    fixtures = sorted((ROOT / "analysis/data/false_triggered_events").glob("*.npy"))
    assert len(fixtures) >= 2, "historical Hi-Lo capture fixtures are required"
    for path in fixtures:
        capture = np.load(path)[np.newaxis, ...]
        for config in ((261, 16, 32, 2), (261, 255, 255, 2)):
            actual = simulate(work / "new", capture, *config, True, 0)
            expected = expected_decisions(capture, *config, True)
            np.testing.assert_array_equal(actual, expected, err_msg=path.name)
            if config[1] == 16:
                old = simulate(work / "legacy", capture, *config, True, 0)
                np.testing.assert_array_equal(actual, old, err_msg=path.name)
            records.append({"fixture": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "config": config, "batches": len(actual),
                            "triggered_batches": int(actual.sum()), "legacy_compared": config[1] == 16})
    (work / "cases.json").write_text(json.dumps(records, indent=2) + "\n")
    return {"cases": len(records), "batches": sum(case["batches"] for case in records),
            "legacy_cases": sum(case["legacy_compared"] for case in records)}


def main():
    checks = {"packing": check_packing, "isolation": check_isolation,
              "reference": check_reference, "regression": check_regression}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", choices=checks, action="append")
    parser.add_argument("--output", type=Path, default=ROOT / "build/cosim")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    inputs = bender_sources("simulation") + [Path(__file__).resolve(),
        ROOT / "analysis/scripts/submodule/stimulus_generation.py",
        ROOT / "analysis/scripts/plot_rtl_emulation.py", ROOT / "Bender.yml", ROOT / "Bender.lock"]
    provenance = {
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "legacy": subprocess.check_output(["git", "rev-parse", "v2.2.4^{commit}"], cwd=ROOT, text=True).strip(),
        "profile": source_profile(), "random_seed": 3000, "numpy": np.__version__,
        "ghdl": subprocess.check_output(["ghdl", "--version"], text=True).splitlines()[0],
        "bender": subprocess.check_output(["bender", "--version"], text=True).strip(),
        "sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs},
    }
    (args.output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    results = []
    for name in args.check or checks:
        with tempfile.TemporaryDirectory(prefix=f"hilo-{name}-") as tmp:
            work = Path(tmp)
            try:
                details = checks[name](work)
                result = {"test": name, "passed": True, "details": details}
            except (AssertionError, ValueError, ImportError) as error:
                result = {"test": name, "passed": False, "error": str(error)}
            for artifact in (*work.rglob("ghdl.log"), *work.glob("cases.json")):
                suffix = str(artifact.relative_to(work)).replace("/", "_")
                (args.output / f"{name}_{suffix}").write_text(artifact.read_text())
            results.append(result)
            print(json.dumps(result), flush=True)
    (args.output / "summary.json").write_text(json.dumps(results, indent=2) + "\n")
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
