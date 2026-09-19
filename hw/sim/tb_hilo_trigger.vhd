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
        ENABLE_RESET_ISOLATION : boolean := false;
        HILO_WINDOW_VALUE : natural := 5;
        COINC_WINDOW_VALUE : natural := 30;
        BIN_THRESHOLD : natural := 1;
        GAP_CYCLES : natural := 0
    );
end entity;

architecture sim of tb_hilo_trigger is

    signal CLK          : std_logic := '0';
    signal RESET        : std_logic := '1';
    signal DATA_STR     : std_logic := '0';
    signal DATA_STR_D1  : std_logic := '0';
    signal DATA_STR_D2  : std_logic := '0';
    signal ADC_DATA    : adc_ch_data_type := (others => (others => (others => '0')));
    signal THRESH_SIG   : std_logic_vector(N_BITS-1 downto 0);
    signal HILO_WINDOW  : std_logic_vector(N_WIN_WIDTH-1 downto 0);
    signal COINC_WINDOW : std_logic_vector(N_WIN_WIDTH-1 downto 0);
    signal BIN_THR      : std_logic_vector(N_CHANNEL-1 downto 0);
    signal PRE_TRIG     : std_logic;
    
    signal END_SIM      : boolean := false;

    constant CLK_PERIOD : time := 10 ns;
begin

    THRESH_SIG <= std_logic_vector(to_signed(THRESHOLD, N_BITS));

    U_DUT : entity work.PRE_TRIGGER
        port map (
            CLK          => CLK,
            RESET        => RESET,
            DATA_STR     => DATA_STR,
            ADC_DATA    => ADC_DATA,
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
        variable batch      : adc_ch_data_type;
        variable clk_count  : integer := 0;
    begin
        HILO_WINDOW  <= std_logic_vector(to_unsigned(HILO_WINDOW_VALUE, HILO_WINDOW'length));
        COINC_WINDOW <= std_logic_vector(to_unsigned(COINC_WINDOW_VALUE, COINC_WINDOW'length));
        BIN_THR      <= std_logic_vector(to_unsigned(BIN_THRESHOLD, BIN_THR'length));
        
        RESET <= '1';
        DATA_STR <= '0';
        wait for CLK_PERIOD * 3;
        wait until rising_edge(CLK);
        RESET <= '0';
        wait until rising_edge(CLK);

        file_open(stim_file, "stimulus.txt", read_mode);
        
        while not endfile(stim_file) loop
            readline(stim_file, in_line);
            for ch in 0 to N_CHANNEL-1 loop
                for samp in 0 to N_SAMPLES-1 loop
                    read(in_line, val);
                    batch(ch)(samp) := std_logic_vector(to_signed(val, N_BITS));
                end loop;
            end loop;

            ADC_DATA <= batch;
            DATA_STR  <= '1';
            wait until rising_edge(CLK);
            
            clk_count := clk_count + 1;
            
            if ENABLE_RESET_ISOLATION and (clk_count = CLOCKS_PER_EVENT) then
                DATA_STR <= '0';
                -- Let the last accepted batch pass both registered stages and
                -- reach the monitor before the asynchronous reset clears it.
                wait until rising_edge(CLK);
                wait until rising_edge(CLK);
                RESET <= '1';
                wait until rising_edge(CLK);
                RESET <= '0';
                clk_count := 0;
            elsif GAP_CYCLES > 0 then
                DATA_STR <= '0';
                for gap in 1 to GAP_CYCLES loop
                    wait until rising_edge(CLK);
                end loop;
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
