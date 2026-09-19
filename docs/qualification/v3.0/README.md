# Hi-Lo v3.0 standalone qualification

Status: standalone fork recovery complete on `v3.0`; ready for the maintainer's
`v3.0.0` publication step. No tag or push was performed. Full AI Trigger System
integration and its 250/200 MHz OOC qualification are intentionally deferred
until the published semantic-version dependency can be resolved by Bender.

## Sources and tooling

- Original reference: `v2.2.4`, commit `5758b7c160fa74c8c55fc2a51ac114834f75bdac`.
- Implementation/regression checkpoint: `86fb651eb2010e7a04c71d2e117f8d195c9af80d`.
  Subsequent release documentation and OOC scripts do not alter the tested RTL.
- Recovered fork lineage: Rene Reimann's gateware `5d9eca1` multi-batch carry and
  source dimensions, `e8940c0` unclamped/full-width windows, and later syntax fixes.
- Qualified source profile: 16 samples, four channels, 12-bit ADC, 8-bit windows.
- Local: Bender 0.32.1, GHDL 6.0.0 LLVM, NumPy 2.4.6.
- Remote route: Ubuntu 22.04.5, Vivado 2023.2, `xcku5p-ffvb676-2-e`, 2026-09-19 UTC.

`functional/provenance.json` records the exact RTL, bench, runner, emulator,
generator, and Bender input hashes. Each OOC directory contains a `SHA256SUMS`
source manifest. Current-route source hashes were checked against the local
checkout. Legacy synthesis and simulation use the original release RTL without
editing it; only the shared simulation bench adapts its public names/widths.

## Functional result

Both directed benches pass. The file-driven suite passes 64 cases / 7,744
aggregate decisions against the reused historical Boolean window model;
34 of those cases / 4,128 decisions also match original v2.2.4 RTL exactly.
This is regression evidence, not exhaustive formal equivalence.

The public seams are per-channel `GATE`, top-level `PRE_TRIG`, and the historical
channel-major stimulus/response files. No RTL internal state is used as the oracle.

Coverage includes:

- both threshold-crossing orders, equality boundaries, aggregate edges and reset;
- windows 0, 1, 16, 17, 31, 32, 33, 63, 64, 127, 128, 254 and 255 as applicable;
- multi-aggregate carry, exact expiry, and coincidence overlap/non-overlap;
- continuous input and two-clock strobe gaps with event reset isolation;
- signed threshold values including -2048, -1, 0 and 2047;
- unchanged standalone multiplicity thresholds 0, 1–4, 5 and 15;
- two original four-channel, 256-sample Hi-Lo captures, with their hashes retained
  in `functional/regression_cases.json`; fixed-seed 3000 sparse synthetic streams
  provide additional long quiet tails and boundary coverage.

The repairs followed individual failing tests: stale 32-sample bench indices;
lost cross-aggregate Hi/Lo carry; 5/6-bit interface limits; the coincidence clamp;
32-sample file packing; and reset discarding the final pending event decision.
The first five implementation commits preserve the red/green progression in
Git; selected failure logs are archived under `red/`. Full local execution logs
remain in `build/v3_qualification/` (not part of the release tree).

The repaired `tb_hilo_trigger` retains its historical default settings and now
drains the decision pipeline before asserting event-isolation reset. The old
stimulus generator derives structural dimensions from `PRE_TRIGGER_PKG.vhd`,
retaining scale 64, rounding and signed ADC saturation. The plotting window
algorithm is reused headlessly rather than introducing another core oracle.

The larger CERN thermal dataset was not downloaded or recharacterized. Existing
figures and ROOT analysis scripts are historical assets, not new v3.0 physics
results. In particular, `viz_cosim_verification.py` still assumes an old
eight-aggregate event log and is not the v3 regression entry point.
`tb_pre_trigger_cosim` is Bender compile-checked but its old threshold sweep is
not counted as executed. The newer CNN NPZ corpus belongs to the later AI/native
integration stage, not this standalone Hi-Lo qualification.

## Matched standalone physical comparison

Both runs use the same new standalone script/XDC, dynamic ADC/configuration
ports, a 4.000 ns clock, `flatten_hierarchy none`, and default placement,
physical optimization, and routing. The old utilization wrapper and its 30 ns
constraint are unchanged and are not used for these measurements.

| Metric | Original v2.2.4 | v3.0 | Delta |
| --- | ---: | ---: | ---: |
| CLB LUTs | 2,240 | 2,380 | +140 / +6.25% |
| FFs | 189 | 225 | +36 / +19.05% |
| DSP / BRAM / URAM | 0 / 0 / 0 | 0 / 0 / 0 | 0 |
| WNS | +1.065 ns | +1.114 ns | +0.049 ns |
| WHS | +0.056 ns | +0.047 ns | -0.009 ns |
| WPWS | +1.725 ns | +1.725 ns | 0 |
| Setup / hold / pulse-width failing endpoints | 0 / 0 / 0 | 0 / 0 / 0 | 0 |
| Routing errors / DRC violations | 0 / 0 | 0 / 0 | 0 |

The standalone resource deltas are below the agreed 25% core review threshold.
They do not establish the later full-AI 2% guardrail. The original standalone
2,240-LUT result is not the prior AI hierarchy's 2,216-LUT count; optimization
and placement contexts differ, so those baselines must not be mixed.

Physical evidence limits:

- Zero-delay OOC boundary convention: input-port hold and external reset paths
  are excluded, as in the AI subsystem's existing boundary convention. Internal
  setup/hold/pulse-width paths are checked, with no unconstrained internal endpoints.
- No parent clock-buffer location is supplied (`HD.CLK_SRC` warning); this is
  an ideal-parent-clock standalone comparison, not integrated clock-tree signoff.
- CDC reports retain the external asynchronous RESET-to-CLR boundary warnings
  (`CDC-26`: 189 old / 225 new paths). No new report category appears; the extra
  reset endpoints follow the additional retained carry bits. No reset policy is
  changed or warning hidden. Parent reset/CDC qualification is still required.
- Both versions emit the existing `MULT2BIN` sensitivity-list warning for
  `BIN_THR`. Its process sensitivity and RTL semantics were deliberately preserved.
  Regression uses stable configurations; live BIN_THR-only simulation updates
  are not qualified by this release.

## Reproduce and continue

From the checkout root, with the local v2.2.4 tag available:

```sh
bender update --local
python3 scripts/run_ghdl_tests.py
python3 scripts/run_cosim_tests.py
vivado -mode batch -source scripts/run_standalone_ooc.tcl -tclargs build/ooc
```

For the original physical baseline, export v2.2.4's `Bender.yml`, `Bender.lock`
and `hw/rtl`, then copy in the current `scripts/run_standalone_ooc.tcl` and
`hw/constraints/pre_trigger_ooc.xdc` unchanged and run the same command.

After the maintainer publishes `v3.0.0`, continue in AI Trigger System `v3.5`:
pin the published dependency, run `bender update hilo-trigger --fetch`, adapt
the neutral names and full window widths, retain the four-to-sixteen adapter,
then run integration/native tests and the agreed complete-system OOC gates.
Do not update unrelated CNN dependencies or integrate/remove gateware triggers
in this delivery. Preserve standalone `BIN_THR=0` and all unrelated configuration,
blanking, mode-switch, event-capture and threshold policies.
