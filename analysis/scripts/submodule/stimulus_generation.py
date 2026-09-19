import numpy as np
from pathlib import Path
import re


def source_profile():
    """Read the same source-time dimensions consumed by VHDL/Bender."""
    package = Path(__file__).resolve().parents[3] / "hw/rtl/PRE_TRIGGER_PKG.vhd"
    text = package.read_text()
    return {name: int(re.search(rf"constant\s+{name}\s*:\s*positive\s*:=\s*(\d+)",
                               text, re.IGNORECASE).group(1))
            for name in ("N_SAMPLES", "N_BITS", "N_CHANNEL", "N_WIN_WIDTH")}

def generate_stimulus_file(input_npy_path, output_txt_path, scale_factor=64.0):
    if not Path(input_npy_path).exists():
        raise FileNotFoundError(f"Cannot find data file: {input_npy_path}")

    data = np.load(input_npy_path)
    # Historical arrays may have a trailing singleton axis. Keep the event
    # dimension even for a single event; saved channel x sample captures work too.
    if data.ndim == 4 and data.shape[-1] == 1:
        data = data[..., 0]
    if data.ndim == 2:
        data = data[np.newaxis, ...]
    profile = source_profile()
    samples_per_clock = profile["N_SAMPLES"]
    if data.ndim != 3 or data.shape[1] != profile["N_CHANNEL"]:
        raise ValueError("expected events x channels x samples (or one channel x sample capture)")
    if data.shape[2] % samples_per_clock:
        raise ValueError("event length must be a multiple of N_SAMPLES; refusing to drop samples")
    
    data = np.round(data * scale_factor).astype(int)
    limit = 2 ** (profile["N_BITS"] - 1)
    data = np.clip(data, -limit, limit - 1)
    
    events, channels, samples = data.shape
    clocks_per_event = samples // samples_per_clock
    
    with open(output_txt_path, 'w') as f:
        for ev in range(events):
            for clk in range(clocks_per_event):
                start_idx = clk * samples_per_clock
                end_idx = start_idx + samples_per_clock
                
                chunk = data[ev, :, start_idx:end_idx] 
                flat_chunk = chunk.flatten()
                
                f.write(" ".join(map(str, flat_chunk)) + "\n")
                
    return clocks_per_event
