import numpy as np
import os

def generate_stimulus_file(input_npy_path, output_txt_path, scale_factor=64.0):
    if not os.path.exists(input_npy_path):
        raise FileNotFoundError(f"Cannot find data file: {input_npy_path}")

    # Load only the 102MB chunk
    data = np.load(input_npy_path)
    data = np.squeeze(data) 
    
    data = np.round(data * scale_factor).astype(int)
    data = np.clip(data, -2048, 2047)
    
    events, channels, samples = data.shape
    samples_per_clock = 32
    clocks_per_event = samples // samples_per_clock
    
    # Stream directly to disk
    with open(output_txt_path, 'w') as f:
        for ev in range(events):
            for clk in range(clocks_per_event):
                start_idx = clk * samples_per_clock
                end_idx = start_idx + samples_per_clock
                
                chunk = data[ev, :, start_idx:end_idx] 
                flat_chunk = chunk.flatten()
                
                f.write(" ".join(map(str, flat_chunk)) + "\n")