# Run from either the v3 checkout or a clean v2.2.4 RTL snapshot with this script
# and XDC copied in. Vivado 2023.2; all ADC/config inputs remain dynamic.
# vivado -mode batch -source scripts/run_standalone_ooc.tcl -tclargs build/ooc
set repo [file normalize [file join [file dirname [info script]] ..]]
cd $repo
set output [file normalize [lindex $argv 0]]
if {[llength $argv] != 1 || $output eq $repo} {error "Provide a separate output directory"}
file mkdir $output
set_param general.maxThreads 4
set part xcku5p-ffvb676-2-e
create_project -in_memory -part $part
set_property target_language VHDL [current_project]
set sources {}
foreach path [split [exec bender script flist -t rtl] "\n"] {
    if {[string match -nocase *.vhd $path]} {
        lappend sources $path
        read_vhdl -vhdl2008 $path
    }
}
if {[llength $sources] != 4} {error "Expected the four canonical Hi-Lo RTL sources"}
set constraints [file join $repo hw constraints pre_trigger_ooc.xdc]
read_xdc $constraints
set manifest [open [file join $output SHA256SUMS] w]
puts $manifest [exec sha256sum {*}$sources $constraints [info script] [file join $repo Bender.yml]]
close $manifest
set versions [open [file join $output versions.txt] w]
puts $versions [version]
puts $versions [exec bender --version]
close $versions
synth_design -top PRE_TRIGGER -part $part -mode out_of_context -flatten_hierarchy none
if {[llength [get_cells -quiet -hierarchical -filter {IS_BLACKBOX == 1}]]} {
    error "Unresolved black boxes"
}
if {[llength [get_clocks -quiet CLK]] != 1} {error "Missing 250 MHz core clock"}
report_utilization -hierarchical -file [file join $output post_synth_utilization_hier.rpt]
opt_design
place_design
phys_opt_design
route_design
write_checkpoint -force [file join $output post_route.dcp]
report_utilization -file [file join $output post_route_utilization.rpt]
report_utilization -hierarchical -file [file join $output post_route_utilization_hier.rpt]
set timing [report_timing_summary -return_string]
set fp [open [file join $output post_route_timing_summary.rpt] w]
puts $fp $timing
close $fp
report_timing -max_paths 10 -file [file join $output post_route_setup.rpt]
report_cdc -details -file [file join $output post_route_cdc.rpt]
check_timing -verbose -file [file join $output post_route_check_timing.rpt]
report_exceptions -coverage -file [file join $output post_route_exceptions.rpt]
report_drc -file [file join $output post_route_drc.rpt]
set route [report_route_status -return_string]
set fp [open [file join $output post_route_status.rpt] w]
puts $fp $route
close $fp
if {![string match {*All user specified timing constraints are met.*} $timing]} {
    error "Standalone core does not meet its timing constraints; inspect the reports"
}
if {![regexp {nets with routing errors[^:]*:\s+0\s+:} $route]} {error "Routing errors or missing route status"}
if {[llength [get_drc_violations -quiet -filter {SEVERITY == Error}]]} {error "Post-route DRC errors"}
if {[llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ DSP* || REF_NAME =~ RAMB* || REF_NAME =~ URAM*}]]} {
    error "Unexpected DSP/BRAM/URAM use"
}
puts "PASS: standalone 250 MHz Hi-Lo route; full AI-system qualification remains separate"
