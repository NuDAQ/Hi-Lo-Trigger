
# This script was generated automatically by bender.
set ROOT "/home/work1/Works/Hi-Lo-Trigger"
add_files -norecurse -fileset [current_fileset] [list \
    $ROOT/hw/sim/tb_pre_trigger_1ch.vhd \
    $ROOT/hw/sim/tb_pre_trigger.vhd \
    $ROOT/hw/sim/tb_pre_trigger_cosim.vhd \
]

set_property verilog_define [list \
    TARGET_FPGA \
    TARGET_SIMULATION \
    TARGET_SYNTHESIS \
    TARGET_VIVADO \
    TARGET_XILINX \
] [current_fileset]

set_property verilog_define [list \
    TARGET_FPGA \
    TARGET_SIMULATION \
    TARGET_SYNTHESIS \
    TARGET_VIVADO \
    TARGET_XILINX \
] [current_fileset -simset]

