-- Copyright 2026 Albert L. Cheung @ University of California, Irvine
-- SPDX-License-Identifier: Apache-2.0 WITH SHL-2.1
--
-- Licensed under the Solderpad Hardware License v 2.1 (the “License”); 
-- you may not use this file except in compliance with the License, or, 
-- at your option, the Apache License version 2.0. 
-- You may obtain a copy of the License at
--
-- https://solderpad.org/licenses/SHL-2.1/
--
-- Unless required by applicable law or agreed to in writing, any work 
-- distributed under the License is distributed on an “AS IS” BASIS, 
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. 
-- See the License for the specific language governing permissions and 
-- limitations under the License.

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

PACKAGE PRE_TRIGGER_pkg IS

    -- Source profile: change here before synthesis, never at runtime.
    -- v3.0 qualifies 16 samples x 4 channels x 12 bits for AI-Trigger-System.
    constant N_SAMPLES   : positive := 16;
    constant N_BITS      : positive := 12;
    constant N_CHANNEL   : positive := 4;
    constant N_WIN_WIDTH : positive := 8;

    -- Index N_SAMPLES-1 is newest; windows count accepted samples.
    type adc_data_type is array (0 to N_SAMPLES-1)
        of std_logic_vector(N_BITS-1 downto 0);
    type adc_ch_data_type is array (0 to N_CHANNEL-1) of adc_data_type;
    type time_window_type is array (0 to N_SAMPLES-1)
        of unsigned(N_WIN_WIDTH-1 downto 0);
    type gate_type is array (0 to N_CHANNEL-1)
        of std_logic_vector(0 to N_SAMPLES-1);
    type mult_type is array (0 to N_SAMPLES-1)
        of std_logic_vector(N_CHANNEL-1 downto 0);
    type carry_type is array (0 to N_CHANNEL-1)
        of unsigned(N_WIN_WIDTH-1 downto 0);

End package PRE_TRIGGER_pkg;
