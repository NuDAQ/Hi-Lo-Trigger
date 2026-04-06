# Hi-Lo-Trigger
[![SHL-2.1 license](https://img.shields.io/badge/license-SHL--2.1-green)](LICENSE)

## Introduction
A Hi-Lo Pre-Trigger for ARIANNA. This module is a 4-channel VHDL-based trigger logic designed to identify coincident signal events across a 32-sample window. It utilizes a bipolar thresholding mechanism and configurable temporal stretching to determine event multiplicity.




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
