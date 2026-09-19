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

-- =============================================================================
--  tb_pre_trigger.vhd
--  Testbench for PRE_TRIGGER (4-channel Hi-Lo bipolar pre-trigger top level)
--
--  Parameters under test
--    THRESH       = 100  (x"064")
--    HILO_WINDOW  =   5  (x"05")   -- intra-channel bipolar gate window
--    COINC_WINDOW =   3  (x"03")   -- inter-channel coincidence smear window
--
--  Pipeline latency: 2 clock cycles (DATA_STR -> PRE_TRIG)
--    Cycle 1 rising edge : PRE_TRIGGER_1CH registers GATE;
--                          data_str_d latches DATA_STR='1'
--    Cycle 2 rising edge : coinc_proc sees data_str_d='1', registers coinc4;
--                          Stage 3 (MULT2BIN) is combinational -> PRE_TRIG valid
--
--  Test cases
--    T01  All-zero input                              -> PRE_TRIG=0
--    T02  1-ch Hi-Lo, BIN_THR=1                      -> PRE_TRIG=1
--    T03  1-ch Hi-Lo, BIN_THR=2                      -> PRE_TRIG=0 (count < thr)
--    T04  2-ch simultaneous, BIN_THR=2               -> PRE_TRIG=1
--    T05  2-ch time-offset=2 < COINC_WINDOW=3,
--           BIN_THR=2                                -> PRE_TRIG=1 (smear overlaps)
--    T06  2-ch time-offset=7 > COINC_WINDOW=3,
--           BIN_THR=2                                -> PRE_TRIG=0 (no overlap)
--    T07  4-ch simultaneous, BIN_THR=4               -> PRE_TRIG=1
--    T08  Cross-batch coincidence carry (BIN_THR=1)
--           Batch-A : Ch0 Hi@12 Lo@14
--             1CH carry: carry_hi=1, carry_lo=3
--             GATE_A(14,15)=1; coinc smear -> bins 14,15
--             coinc carry -> coinc_d(0)=2
--             PRE_TRIG_A=1
--           Batch-B : all-zero
--             1CH carry opens gate_B(0)=1
--             coinc carry(2) + within-batch gate -> coinc bins 0,1,2
--             PRE_TRIG_B=1
--    T09  RESET clears coinc carry
--           Batch-A as above, then RESET, then all-zero Batch-B -> PRE_TRIG=0
-- =============================================================================

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.pre_trigger_pkg.all;

entity tb_pre_trigger is
end entity;

architecture sim of tb_pre_trigger is

    -- -------------------------------------------------------------------------
    --  DUT interface
    -- -------------------------------------------------------------------------
    signal CLK          : std_logic := '0';
    signal RESET        : std_logic := '1';
    signal DATA_STR     : std_logic := '0';
    signal ADC_DATA    : adc_ch_data_type := (others => (others => (others => '0')));
    signal THRESH       : std_logic_vector(N_BITS-1 downto 0);
    signal HILO_WINDOW  : std_logic_vector(N_WIN_WIDTH-1 downto 0);
    signal COINC_WINDOW : std_logic_vector(N_WIN_WIDTH-1 downto 0) :=
        std_logic_vector(to_unsigned(3, N_WIN_WIDTH));
    signal BIN_THR      : std_logic_vector(N_CHANNEL-1 downto 0);
    signal PRE_TRIG     : std_logic;

    -- -------------------------------------------------------------------------
    --  Testbench constants
    -- -------------------------------------------------------------------------
    constant CLK_PERIOD : time    := 10 ns;
    constant ADC_HI     : std_logic_vector(N_BITS-1 downto 0) :=
                              std_logic_vector(to_signed( 150, N_BITS));  -- +150 > +THRESH
    constant ADC_LO     : std_logic_vector(N_BITS-1 downto 0) :=
                              std_logic_vector(to_signed(-150, N_BITS));  -- -150 < -THRESH
    constant ADC_ZERO   : std_logic_vector(N_BITS-1 downto 0) := (others => '0');

begin

    -- -------------------------------------------------------------------------
    --  DUT
    -- -------------------------------------------------------------------------
    U_DUT : entity work.PRE_TRIGGER
        port map (
            CLK          => CLK,
            RESET        => RESET,
            DATA_STR     => DATA_STR,
            ADC_DATA    => ADC_DATA,
            THRESH       => THRESH,
            HILO_WINDOW  => HILO_WINDOW,
            COINC_WINDOW => COINC_WINDOW,
            BIN_THR      => BIN_THR,
            PRE_TRIG     => PRE_TRIG
        );

    -- -------------------------------------------------------------------------
    --  Clock
    -- -------------------------------------------------------------------------
    CLK <= not CLK after CLK_PERIOD / 2;

    -- -------------------------------------------------------------------------
    --  Stimulus
    -- -------------------------------------------------------------------------
    THRESH       <= x"064";  -- 100 ADC counts
    HILO_WINDOW  <= std_logic_vector(to_unsigned(5, N_WIN_WIDTH)); -- 5-sample intra-channel bipolar window

    stimulus : process
        variable batch : adc_ch_data_type;

        -- Apply one DATA_STR pulse and wait through both pipeline stages.
        -- After this procedure returns PRE_TRIG is stable and valid.
        --   Rising edge 1 : Stage 1 (PRE_TRIGGER_1CH) latches GATE;
        --                   data_str_d latches '1'
        --   Rising edge 2 : Stage 2 (coinc_proc) latches coinc4;
        --                   Stage 3 (MULT2BIN) is combinational -> PRE_TRIG valid
        procedure send_batch (constant b : in adc_ch_data_type) is
        begin
            ADC_DATA <= b;
            DATA_STR  <= '1';
            wait until rising_edge(CLK);  -- Stage 1 registers here
            DATA_STR  <= '0';
            wait until rising_edge(CLK);  -- Stage 2 registers here
            wait for 1 ns;                -- advance past delta cycles; PRE_TRIG stable
        end procedure;

        procedure do_reset is
        begin
            RESET <= '1';
            wait until rising_edge(CLK);
            wait until rising_edge(CLK);
            RESET <= '0';
            wait until rising_edge(CLK);
        end procedure;

    begin
        -- -----------------------------------------------------------------------
        --  Power-on reset
        -- -----------------------------------------------------------------------
        do_reset;

        -- -----------------------------------------------------------------------
        --  T01 : All-zero input  ->  PRE_TRIG must be 0
        -- -----------------------------------------------------------------------
        BIN_THR <= std_logic_vector(to_unsigned(1, N_CHANNEL));
        batch   := (others => (others => ADC_ZERO));
        send_batch(batch);
        assert PRE_TRIG = '0'
            report "T01 FAIL: all-zero input should not assert PRE_TRIG" severity failure;
        report "T01 PASS  all-zero input -> PRE_TRIG=0";

        do_reset;

        -- -----------------------------------------------------------------------
        --  T02 : 1-channel Hi-Lo event, BIN_THR=1  ->  PRE_TRIG=1
        --
        --  Ch0: Hi@5, Lo@8
        --    HILO gate: gate_hi(5..9), gate_lo(8..12) -> GATE(8,9)=1
        --    Coinc smear (W=3): k=8->i=8,9,10; k=9->i=9,10,11 -> coinc(0) bins 8..11
        --  count=1 ≥ BIN_THR=1  ->  PRE_TRIG=1
        -- -----------------------------------------------------------------------
        BIN_THR <= std_logic_vector(to_unsigned(1, N_CHANNEL));
        batch   := (others => (others => ADC_ZERO));
        batch(0)(5) := ADC_HI;
        batch(0)(8) := ADC_LO;
        send_batch(batch);
        assert PRE_TRIG = '1'
            report "T02 FAIL: 1-ch Hi@5 Lo@8 with BIN_THR=1 should fire PRE_TRIG" severity failure;
        report "T02 PASS  1-ch Hi@5 Lo@8, BIN_THR=1 -> PRE_TRIG=1";

        do_reset;

        -- -----------------------------------------------------------------------
        --  T03 : 1-channel Hi-Lo event, BIN_THR=2  ->  PRE_TRIG=0
        --
        --  Same signal as T02; only 1 channel fires -> count=1 < BIN_THR=2
        -- -----------------------------------------------------------------------
        BIN_THR <= std_logic_vector(to_unsigned(2, N_CHANNEL));
        batch   := (others => (others => ADC_ZERO));
        batch(0)(5) := ADC_HI;
        batch(0)(8) := ADC_LO;
        send_batch(batch);
        assert PRE_TRIG = '0'
            report "T03 FAIL: 1-ch event with BIN_THR=2 should NOT fire PRE_TRIG" severity failure;
        report "T03 PASS  1-ch Hi@5 Lo@8, BIN_THR=2 -> PRE_TRIG=0";

        do_reset;

        -- -----------------------------------------------------------------------
        --  T04 : 2 channels simultaneous, BIN_THR=2  ->  PRE_TRIG=1
        --
        --  Ch0, Ch1: Hi@5, Lo@8  ->  GATE(8,9)=1 on both channels
        --  Coinc: both open bins 8..11
        --  count=2 at bins 8..11  ≥  BIN_THR=2  ->  PRE_TRIG=1
        -- -----------------------------------------------------------------------
        BIN_THR <= std_logic_vector(to_unsigned(2, N_CHANNEL));
        batch   := (others => (others => ADC_ZERO));
        batch(0)(5) := ADC_HI;  batch(0)(8) := ADC_LO;
        batch(1)(5) := ADC_HI;  batch(1)(8) := ADC_LO;
        send_batch(batch);
        assert PRE_TRIG = '1'
            report "T04 FAIL: 2-ch simultaneous with BIN_THR=2 should fire PRE_TRIG" severity failure;
        report "T04 PASS  2-ch simultaneous Hi@5 Lo@8, BIN_THR=2 -> PRE_TRIG=1";

        do_reset;

        -- -----------------------------------------------------------------------
        --  T05 : 2 channels offset by 2 < COINC_WINDOW=3, BIN_THR=2  ->  PRE_TRIG=1
        --
        --  Ch0: Hi@0, Lo@3  ->  GATE(3,4)
        --    Coinc (W=3): k=3->i=3,4,5; k=4->i=4,5,6  ->  coinc(0) bins 3..6
        --  Ch1: Hi@2, Lo@5  ->  GATE(5,6)
        --    Coinc (W=3): k=5->i=5,6,7; k=6->i=6,7,8  ->  coinc(1) bins 5..8
        --  Overlap at bins 5,6: count=2 ≥ BIN_THR=2  ->  PRE_TRIG=1
        -- -----------------------------------------------------------------------
        BIN_THR <= std_logic_vector(to_unsigned(2, N_CHANNEL));
        batch   := (others => (others => ADC_ZERO));
        batch(0)(0) := ADC_HI;  batch(0)(3) := ADC_LO;
        batch(1)(2) := ADC_HI;  batch(1)(5) := ADC_LO;
        send_batch(batch);
        assert PRE_TRIG = '1'
            report "T05 FAIL: 2-ch time-offset=2 within COINC_WINDOW should fire PRE_TRIG"
            severity failure;
        report "T05 PASS  2-ch offset=2 (< CW=3), BIN_THR=2 -> PRE_TRIG=1";

        do_reset;

        -- -----------------------------------------------------------------------
        --  T06 : 2 channels offset by 7 > COINC_WINDOW=3, BIN_THR=2  ->  PRE_TRIG=0
        --
        --  Ch0: Hi@0,  Lo@3  ->  GATE(3,4)   ->  coinc(0) bins 3..6
        --  Ch1: Hi@10, Lo@13 ->  GATE(13,14) ->  coinc(1) bins 13..16
        --  No overlap between 3..6 and 13..16  ->  PRE_TRIG=0
        -- -----------------------------------------------------------------------
        BIN_THR <= std_logic_vector(to_unsigned(2, N_CHANNEL));
        batch   := (others => (others => ADC_ZERO));
        batch(0)(0)  := ADC_HI;  batch(0)(3)  := ADC_LO;
        batch(1)(10) := ADC_HI;  batch(1)(13) := ADC_LO;
        send_batch(batch);
        assert PRE_TRIG = '0'
            report "T06 FAIL: 2-ch time-offset=7 beyond COINC_WINDOW should NOT fire PRE_TRIG"
            severity failure;
        report "T06 PASS  2-ch offset=7 (> CW=3), BIN_THR=2 -> PRE_TRIG=0";

        do_reset;

        -- -----------------------------------------------------------------------
        --  T07 : All 4 channels simultaneous, BIN_THR=4  ->  PRE_TRIG=1
        --
        --  Ch0-Ch3: Hi@5, Lo@8  ->  GATE(8,9)=1 on all four channels
        --  count=4 at bins 8..11  ≥  BIN_THR=4  ->  PRE_TRIG=1
        -- -----------------------------------------------------------------------
        BIN_THR <= std_logic_vector(to_unsigned(4, N_CHANNEL));
        batch   := (others => (others => ADC_ZERO));
        for ch in 0 to N_CHANNEL-1 loop
            batch(ch)(5) := ADC_HI;
            batch(ch)(8) := ADC_LO;
        end loop;
        send_batch(batch);
        assert PRE_TRIG = '1'
            report "T07 FAIL: 4-ch simultaneous with BIN_THR=4 should fire PRE_TRIG" severity failure;
        report "T07 PASS  4-ch simultaneous Hi@5 Lo@8, BIN_THR=4 -> PRE_TRIG=1";

        do_reset;

        -- -----------------------------------------------------------------------
        --  T08 : Cross-batch coincidence carry, BIN_THR=1
        --
        --  Batch-A: Ch0: Hi@12, Lo@14
        --    GATE_A(14,15)=1
        --      (gate_hi: k=12 -> bins 12..15; gate_lo: k=14 -> bins 14,15; AND -> 14,15)
        --    1CH carry: carry_hi=1 (12+5−16), carry_lo=3 (14+5−16)
        --    Coinc smear (W=3): k=14->i=14,15; k=15->i=15  ->  coinc(0) bins 14,15
        --    Coinc carry: last gate4 bit at k=15; 15+3=18>16 -> coinc_d(0)=2
        --    PRE_TRIG_A=1 (bins 14,15)
        --
        --  Batch-B: all-zero
        --    1CH carry: gate_hi(0)=1 (i<1), gate_lo(0,1,2)=1 (i<3) -> GATE_B(0)=1
        --    Coinc: coinc_d(0)=2 -> carry opens i=0,1;
        --           gate4(0)(0)=1 -> within-batch opens i=0,1,2
        --           Union: bins 0,1,2
        --    PRE_TRIG_B=1 (bins 0..2, count=1 ≥ BIN_THR=1)
        -- -----------------------------------------------------------------------
        BIN_THR <= std_logic_vector(to_unsigned(1, N_CHANNEL));
        batch   := (others => (others => ADC_ZERO));
        batch(0)(N_SAMPLES-4) := ADC_HI;
        batch(0)(N_SAMPLES-2) := ADC_LO;
        send_batch(batch);
        assert PRE_TRIG = '1'
            report "T08 FAIL Batch-A: expected PRE_TRIG=1 at bins 14,15" severity failure;
        report "T08a PASS  Batch-A: Ch0 Hi@12 Lo@14 -> PRE_TRIG=1, coinc carry=2";

        -- Batch-B: all-zero; exercises both 1CH and coinc carry paths
        batch := (others => (others => ADC_ZERO));
        send_batch(batch);
        assert PRE_TRIG = '1'
            report "T08 FAIL Batch-B: expected PRE_TRIG=1 from cross-batch coinc carry"
            severity failure;
        report "T08b PASS  Batch-B: all-zero -> PRE_TRIG=1 from cross-batch coinc carry";

        do_reset;

        -- -----------------------------------------------------------------------
        --  T09 : RESET clears coinc carry  ->  after reset, empty batch gives PRE_TRIG=0
        -- -----------------------------------------------------------------------
        BIN_THR <= std_logic_vector(to_unsigned(1, N_CHANNEL));
        -- Reproduce same Batch-A carry state as T08
        batch   := (others => (others => ADC_ZERO));
        batch(0)(N_SAMPLES-4) := ADC_HI;
        batch(0)(N_SAMPLES-2) := ADC_LO;
        send_batch(batch);
        -- Reset wipes carry_count_hi_d, carry_count_lo_d, coinc_d, GATE, coinc4
        do_reset;
        -- Empty batch: all carry is cleared, PRE_TRIG must be 0
        batch := (others => (others => ADC_ZERO));
        send_batch(batch);
        assert PRE_TRIG = '0'
            report "T09 FAIL: RESET should clear all carry; PRE_TRIG must be 0" severity failure;
        report "T09 PASS  RESET clears coinc carry -> PRE_TRIG=0";

        -- T10: ch0 Hi@0/Lo@1 with HILO=5 has gate samples 1..4.
        -- COINC=255 extends that through sample 258. A second channel's
        -- gate beginning at 257 overlaps; one beginning at 259 does not.
        COINC_WINDOW <= std_logic_vector(to_unsigned(255, N_WIN_WIDTH));
        BIN_THR <= std_logic_vector(to_unsigned(2, N_CHANNEL));
        for late_offset in 0 to 1 loop
            do_reset;
            batch := (others => (others => ADC_ZERO));
            batch(0)(0) := ADC_HI;
            batch(0)(1) := ADC_LO;
            send_batch(batch);
            assert PRE_TRIG = '0'
                report "T10 one channel cannot meet BIN_THR=2" severity failure;
            batch := (others => (others => ADC_ZERO));
            for empty_batch in 1 to 15 loop
                send_batch(batch);
                assert PRE_TRIG = '0'
                    report "T10 empty batches cannot supply a second channel" severity failure;
            end loop;
            batch(1)(2*late_offset) := ADC_HI;
            batch(1)(2*late_offset+1) := ADC_LO;
            send_batch(batch);
            if late_offset = 0 then
                assert PRE_TRIG = '1'
                    report "T10 COINC=255 must retain ch0 until ch1 overlaps"
                    severity failure;
            else
                assert PRE_TRIG = '0'
                    report "T10 coincidence must expire before sample 259" severity failure;
            end if;
            batch := (others => (others => ADC_ZERO));
            send_batch(batch);
            assert PRE_TRIG = '0'
                report "T10 expired ch0 must not keep contributing" severity failure;
        end loop;
        report "T10 PASS  Full eight-bit coincidence window and expiration";

-- -----------------------------------------------------------------------
        report "========================================";
        report "ALL PRE_TRIGGER TESTS PASSED";
        report "========================================";
        std.env.finish;
    end process;

end architecture;
