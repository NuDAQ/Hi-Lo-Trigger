library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

-- Include your package containing the array types
library work;
use work.PRE_TRIGGER_pkg.all;

entity PRE_TRIGGER_UTIL_WRAPPER is
    Port (
        clk_i        : in  std_logic;
        rst_i        : in  std_logic;
        -- Minimal physical I/O to pass DRC (Design Rule Check)
        seed_data_i  : in  std_logic_vector(11 downto 0); 
        trig_out_o   : out std_logic
    );
end PRE_TRIGGER_UTIL_WRAPPER;

architecture Behavioral of PRE_TRIGGER_UTIL_WRAPPER is

    -- Signals to interface with the DUT (Device Under Test)
    signal sig_adc_data4  : adc_data4_type; -- Corrected type from PRE_TRIGGER_pkg
    signal sig_thresh     : std_logic_vector(11 downto 0);
    signal sig_hilo_win   : std_logic_vector(4 downto 0);
    signal sig_coinc_win  : std_logic_vector(5 downto 0);
    signal sig_bin_thr    : std_logic_vector(3 downto 0);
    signal sig_data_str   : std_logic;
    signal sig_pre_trig   : std_logic;
    
    -- Internal registers to prevent optimization
    signal shift_reg      : std_logic_vector(11 downto 0);

begin

    -- 1. Dynamic Stimulus Generation
    process(clk_i)
    begin
        if rising_edge(clk_i) then
            if rst_i = '1' then
                shift_reg <= (others => '0');
                sig_data_str <= '0';
            else
                shift_reg <= seed_data_i;
                -- Toggle DATA_STR to mimic active data phases
                sig_data_str <= not sig_data_str; 
            end if;
        end if;
    end process;

    -- 2. Fanout to DUT Inputs
    FANOUT_GEN_CH: for c in 0 to 3 generate
        FANOUT_GEN_SAMP: for s in 0 to 31 generate
            sig_adc_data4(c)(s) <= shift_reg xor std_logic_vector(to_unsigned(c * s, 12));
        end generate;
    end generate;

    -- Assign dynamic/static values to config ports
    sig_thresh    <= shift_reg;
    sig_hilo_win  <= "01000"; -- Example static window of 8
    sig_coinc_win <= "010000"; -- Example static window of 16
    sig_bin_thr   <= "0010";  -- Example threshold of 2

    -- 3. Instantiate the Device Under Test
    DUT: entity work.PRE_TRIGGER
        port map (
            CLK          => clk_i,
            RESET        => rst_i,
            DATA_STR     => sig_data_str,
            ADC_DATA4    => sig_adc_data4,
            THRESH       => sig_thresh,
            HILO_WINDOW  => sig_hilo_win,
            COINC_WINDOW => sig_coinc_win,
            BIN_THR      => sig_bin_thr,
            PRE_TRIG     => sig_pre_trig
        );

    -- 4. Output Sink
    -- Directly route the single std_logic output to the physical pin
    process(clk_i)
    begin
        if rising_edge(clk_i) then
            trig_out_o <= sig_pre_trig;
        end if;
    end process;

end Behavioral;