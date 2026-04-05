# This script was generated automatically by bender.
set ROOT "/home/work1/Works/Hi-Lo-Trigger"

add_files -norecurse -fileset [current_fileset] [list \
    $ROOT/hw/rtl/PRE_TRIGGER_PKG.vhd \
    $ROOT/hw/rtl/Mult_to_bin.vhd \
    $ROOT/hw/rtl/Pre_trigger_1ch.vhd \
    $ROOT/hw/rtl/Pre_trigger.vhd \
]

add_files -norecurse -fileset [current_fileset] [list \
    $ROOT/hw/constraints/pre_trigger.xdc \
]

add_files -norecurse -fileset [current_fileset] [list \
    $ROOT/hw/sim/PRE_TRIGGER_UTIL_WRAPPER.vhd \
]

set_property verilog_define [list \
    TARGET_FPGA \
    TARGET_SYNTHESIS \
    TARGET_UTILIZATION \
    TARGET_VIVADO \
    TARGET_XILINX \
] [current_fileset]

set_property verilog_define [list \
    TARGET_FPGA \
    TARGET_SYNTHESIS \
    TARGET_UTILIZATION \
    TARGET_VIVADO \
    TARGET_XILINX \
] [current_fileset -simset]

