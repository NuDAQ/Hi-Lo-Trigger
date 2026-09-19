# Standalone core comparison, not board or full AI-system qualification.
# Same internal-block zero-delay convention as AI-Trigger-System's OOC flow.
create_clock -name CLK -period 4.000 [get_ports CLK]
set_input_delay 0.000 -clock [get_clocks CLK] [get_ports {DATA_STR ADC_DATA* THRESH* HILO_WINDOW* COINC_WINDOW* BIN_THR*}]
set_false_path -hold -from [get_ports {DATA_STR ADC_DATA* THRESH* HILO_WINDOW* COINC_WINDOW* BIN_THR*}]
set_output_delay 0.000 -clock [get_clocks CLK] [get_ports PRE_TRIG]
set_false_path -from [get_ports RESET]
