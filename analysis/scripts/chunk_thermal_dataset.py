import numpy as np
import os

def slice_thermal_dataset():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.abspath(os.path.join(script_dir, "../data/thermal"))
    
    input_path = "/home/work1/Downloads/thermal_background_2100000.npy"
    
    events_per_chunk = 25000

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"[*] Created target directory: {output_dir}")

    print(f"[*] Mapping {input_path} into virtual memory...")
    try:
        data = np.lib.format.open_memmap(input_path, mode='r')
    except FileNotFoundError:
        print(f"[!] CRITICAL: Source file not found at {input_path}")
        return

    total_events = data.shape[0]
    print(f"[*] Detected shape: {data.shape}, dtype: {data.dtype}")
    
    chunk_index = 0
    for start_idx in range(0, total_events, events_per_chunk):
        end_idx = min(start_idx + events_per_chunk, total_events)
        
        chunk_data = data[start_idx:end_idx]
        
        output_filename = f"thermal_chunk_{chunk_index:04d}.npy"
        output_filepath = os.path.join(output_dir, output_filename)
        
        np.save(output_filepath, chunk_data)
        print(f"[*] Saved {output_filename} | Events: {start_idx} to {end_idx - 1}")
        
        chunk_index += 1

    print(f"\n[*] Complete. {chunk_index} chunks saved to {output_dir}")

if __name__ == "__main__":
    slice_thermal_dataset()
