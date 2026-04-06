# Hi-Lo Trigger
[![SHL-2.1 license](https://img.shields.io/badge/license-SHL--2.1-green)](LICENSE)

## Introduction
A Hi-Lo Pre-Trigger for ARIANNA, a neutrino experiment. This is a submodule for the whole DAQ System. This module is a 4-channel VHDL-based trigger logic designed to identify coincident signal events across a 32-sample window. It utilizes a bipolar thresholding mechanism and configurable temporal stretching to determine event multiplicity.

### Core Functional Logic
The system operates through a three-stage pipeline to process ADC data:

1. **Bipolar Thresholding (`PRE_TRIGGER_1CH`)**
Each of the 4 channels independently compares 12-bit signed ADC samples against a positive threshold (`THRESH`) and its negative equivalent (`-THRESH`). 
A logical AND is performed between the high and low threshold detections within a sliding window defined by `HILO_WINDOW` (hardware-clamped to a maximum of 16 samples). 
This stage generates a `GATE` signal, which is active only when both high and low threshold crossings occur within the specified window.

2. **Temporal Coincidence Smearing (`PRE_TRIGGER`)**
The `GATE` signal from each channel is stretched using a second sliding window, `COINC_WINDOW` (up to 32 samples). 
This logic includes cross-batch carry-over. If an event occurs near the end of a 32-sample batch, the active state is carried into the subsequent batch to ensure continuous temporal coverage and prevent boundary data loss.

3. **Multiplicity Evaluation (`MULT2BIN`)**
For every individual time bin (0 to 31), the system aggregates the coincidence bits from all 4 channels into a multiplicity vector. The `MULT2BIN` module calculates the number of active channels in each bin. A global `PRE_TRIG` is asserted if the active channel count meets or exceeds the user-defined `BIN_THR` for any of the 32 time bins.

### Technical Specifications

| Parameter | Specification |
| :--- | :--- |
| **Channel Count** | 4 Channels |
| **Batch Size** | 32 samples per clock cycle |
| **ADC Resolution** | 12-bit signed |
| **Hi-Lo Window** | 0 to 16 samples (Hardware clamped) |
| **Coincidence Window** | 0 to 32 samples |
| **Multiplicity** | Configurable threshold (0 to 4) via `BIN_THR` |

## Simulator and Plotting



## License
This project is licensed under the SHL-2.1 License. See the [LICENSE](LICENSE).

---
> Remaining part is for developers. End-users should focus on the above sections only.

## Bender How-To

1. Add source files to your working directory or declare new external IPs, in `Bender.yml`.
2. `Bender Update`.
3. `bender script vivado` for the vivado script.

How to write `Bender.yml`?

```yml
package:
  name: my_project
  description: "Description for this project."
  authors:
    - "Albert <albert@example.com>" # current maintainer
    - "Albert <albert@example.com>" # current maintainer

dependencies:
  # METHODOLOGY FIX: Never track a moving branch like 'main'. 
  # Pin to exact semantic versions or commit hashes to guarantee reproducible builds.
  common_cells: { git: "https://github.com/pulp-platform/common_cells.git", version: 1.37.0 }
  mydep: { git: "git@github.com:pulp-platform/common_verification.git", rev: "<commit-ish>" }
  mydep: { git: "git@github.com:pulp-platform/common_verification.git", version: "1.1" }

sources:
  # Source files grouped in levels. Files in level 0 have no dependencies on files in this
  # package. Files in level 1 only depend on files in level 0, files in level 2 on files in
  # levels 1 and 0, etc. Files within a level are ordered alphabetically.
  # Level 0
  - src/axi_pkg.sv
  # Level 1
  - src/axi_intf.sv
  # Level 2
  - src/axi_atop_filter.sv
  - src/axi_burst_splitter_gran.sv
  - src/axi_burst_unwrap.sv

  - target: synth_test
    files:
      - test/axi_synth_bench.sv

  - target: simulation
    files:
      - src/axi_chan_compare.sv
      - src/axi_dumper.sv
      - src/axi_sim_mem.sv
      - src/axi_test.sv
```
