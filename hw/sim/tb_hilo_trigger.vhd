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

-- Copyright 2026 Albert L. Cheung @ University of California, Irvine
-- SPDX-License-Identifier: Apache-2.0 WITH SHL-2.1

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.textio.all;
use work.pre_trigger_pkg.all;

entity tb_hilo_trigger is
    generic (
        THRESHOLD : integer := 100;
        CLOCKS_PER_EVENT : integer := 1;
        ENABLE_RESET_ISOLATION : boolean := false 
    );
end entity;

architecture sim of tb_hilo_trigger is

    signal CLK          : std_logic := '0';
    signal RESET        : std_logic := '1';
    signal DATA_STR     : std_logic := '0';
    signal DATA_STR_D1  : std_logic := '0';
    signal DATA_STR_D2  : std_logic := '0';
    signal ADC_DATA4    : adc_data4_type := (others => (others => (others => '0')));
    signal THRESH_SIG   : std_logic_vector(11 downto 0);
    signal HILO_WINDOW  : std_logic_vector( 4 downto 0);
    signal COINC_WINDOW : std_logic_vector( 5 downto 0);
    signal BIN_THR      : std_logic_vector( 3 downto 0);
    signal PRE_TRIG     : std_logic;
    
    signal END_SIM      : boolean := false;

    constant CLK_PERIOD : time := 10 ns;
begin

    THRESH_SIG <= std_logic_vector(to_signed(THRESHOLD, 12));

    U_DUT : entity work.PRE_TRIGGER
        port map (
            CLK          => CLK,
            RESET        => RESET,
            DATA_STR     => DATA_STR,
            ADC_DATA4    => ADC_DATA4,
            THRESH       => THRESH_SIG,
            HILO_WINDOW  => HILO_WINDOW,
            COINC_WINDOW => COINC_WINDOW,
            BIN_THR      => BIN_THR,
            PRE_TRIG     => PRE_TRIG
        );

    CLK <= not CLK after CLK_PERIOD / 2;

    -- Latency Tracking
    process(CLK)
    begin
        if rising_edge(CLK) then
            DATA_STR_D1 <= DATA_STR;
            DATA_STR_D2 <= DATA_STR_D1;
        end if;
    end process;

    -- Stimulus Driver
    stimulus : process
        file stim_file      : text;
        variable in_line    : line;
        variable val        : integer;
        variable batch      : adc_data4_type;
        variable clk_count  : integer := 0;
    begin
        HILO_WINDOW  <= "00101";
        COINC_WINDOW <= "011110";
        BIN_THR      <= x"1";
        
        RESET <= '1';
        DATA_STR <= '0';
        wait for CLK_PERIOD * 3;
        wait until rising_edge(CLK);
        RESET <= '0';
        wait until rising_edge(CLK);

        file_open(stim_file, "stimulus.txt", read_mode);
        
        while not endfile(stim_file) loop
            readline(stim_file, in_line);
            for ch in 0 to 3 loop
                for samp in 0 to 31 loop
                    read(in_line, val);
                    batch(ch)(samp) := std_logic_vector(to_signed(val, 12));
                end loop;
            end loop;

            ADC_DATA4 <= batch;
            DATA_STR  <= '1';
            wait until rising_edge(CLK);
            
            clk_count := clk_count + 1;
            
            if ENABLE_RESET_ISOLATION and (clk_count = CLOCKS_PER_EVENT) then
                DATA_STR <= '0';
                RESET <= '1';
                wait until rising_edge(CLK);
                RESET <= '0';
                clk_count := 0;
            end if;
            
        end loop;

        DATA_STR <= '0';
        file_close(stim_file);
        
        -- Flush pipeline
        wait for CLK_PERIOD * 5;
        END_SIM <= true;
        wait;
    end process;

    -- Output Monitor
    monitor : process
        file resp_file    : text;
        variable out_line : line;
    begin
        file_open(resp_file, "hw_resp.txt", write_mode);
        
        while not END_SIM loop
            wait until rising_edge(CLK);
            if DATA_STR_D2 = '1' then
                if PRE_TRIG = '1' then
                    write(out_line, string'("1"));
                else
                    write(out_line, string'("0"));
                end if;
                writeline(resp_file, out_line);
            end if;
        end loop;
        
        file_close(resp_file);
        std.env.finish;
    end process;

end architecture;
