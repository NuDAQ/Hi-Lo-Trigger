import os
import glob
import subprocess
import json
import numpy as np
from submodule.stimulus_generation import generate_stimulus_file

# --- CONFIGURATION ---
CAPTURE_WAVEFORM_ON_TRIGGER = True
# ---------------------

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.abspath(os.path.join(base_dir, "../data/thermal"))
    hw_dir   = os.path.abspath(os.path.join(base_dir, "../../hw"))
    
    stimulus_txt_path = os.path.join(base_dir, "stimulus.txt")
    hw_log_path = os.path.join(base_dir, "hw_resp.txt")
    output_results_path = os.path.join(base_dir, "far_results.json")
    
    rtl_files = [
        os.path.join(hw_dir, "rtl/PRE_TRIGGER_PKG.vhd"),
        os.path.join(hw_dir, "rtl/Pre_trigger_1ch.vhd"),
        os.path.join(hw_dir, "rtl/Mult_to_bin.vhd"),
        os.path.join(hw_dir, "rtl/Pre_trigger.vhd")
    ]
    tb_file = os.path.join(hw_dir, "sim/tb_hilo_trigger.vhd")
    
    for vhdl_file in rtl_files + [tb_file]:
        if not os.path.exists(vhdl_file):
            print(f"[!] CRITICAL: Hardware source file missing: {vhdl_file}")
            return

    chunk_files = sorted(glob.glob(os.path.join(data_dir, "thermal_chunk_*.npy")))
    if not chunk_files:
        print(f"[!] CRITICAL: No chunk files found in {data_dir}")
        return

    print("[*] Calculating True Noise RMS from first chunk...")
    sample_data = np.load(chunk_files[0])
    noise_rms = float(np.std(sample_data))
    
    snr_thresholds = [3.0]
    scale = 64.0 
    
    results = {
        str(snr): {
            "hw_threshold_int": int(snr * noise_rms * scale), 
            "false_positives": 0, 
            "events_processed": 0
        } for snr in snr_thresholds
    }

    for snr in snr_thresholds:
        hw_thr = results[str(snr)]["hw_threshold_int"]
        print(f"\n{'='*60}")
        print(f"[*] VERIFYING POINT: SNR {snr} (HW INT: {hw_thr})")
        print(f"{'='*60}")
        
        triggered_global = False
        
        for chunk_file in chunk_files:
            if triggered_global and CAPTURE_WAVEFORM_ON_TRIGGER:
                print("[*] Halting further processing due to captured trigger.")
                break
                
            chunk_name = os.path.basename(chunk_file)
            print(f"[*] Processing: {chunk_name}")
            
            clocks_per_event = generate_stimulus_file(chunk_file, stimulus_txt_path, scale)
            
            comp_cmd = ["xvhdl", "--2008"] + rtl_files + [tb_file]
            elab_cmd = [
                "xelab", "-debug", "typical", "-top", "tb_hilo_trigger", 
                "-snapshot", "tb_snap", 
                "-generic_top", f"THRESHOLD={hw_thr}",
                "-generic_top", f"CLOCKS_PER_EVENT={clocks_per_event}"
            ]
            sim_cmd = ["xsim", "tb_snap", "-R"]
            
            try:
                subprocess.run(comp_cmd, check=True, stdout=subprocess.DEVNULL)
                subprocess.run(elab_cmd, check=True, stdout=subprocess.DEVNULL)
                subprocess.run(sim_cmd, check=True, stdout=subprocess.DEVNULL)
            except subprocess.CalledProcessError as e:
                print(f"[!] CRITICAL: Vivado toolchain failed during {chunk_name}. {e}")
                return
            
            if os.path.exists(hw_log_path):
                with open(hw_log_path, 'r') as f:
                    lines = [l.strip() for l in f.readlines() if l.strip() in ['0', '1']]
                
                if CAPTURE_WAVEFORM_ON_TRIGGER:
                    for idx, val in enumerate(lines):
                        if val == '1':
                            print(f"[!] Trigger detected at absolute batch index {idx}.")
                            
                            # Load raw array and reshape to continuous stream
                            raw_data = np.load(chunk_file)
                            raw_data = np.squeeze(raw_data) # shape: (events, channels, samples_per_event)
                            
                            channels = raw_data.shape[1]
                            
                            # Transpose to (channels, events, samples_per_event) then flatten events
                            # Resulting shape: (channels, total_samples_in_chunk)
                            continuous_stream = np.transpose(raw_data, (1, 0, 2)).reshape(channels, -1)
                            total_batches = continuous_stream.shape[1] // 32
                            
                            # Global batch slicing logic
                            start_batch = max(0, idx - 2)
                            end_batch = min(total_batches, idx + 3)
                            
                            start_samp = start_batch * 32
                            end_samp = end_batch * 32
                            
                            waveform_capture = continuous_stream[:, start_samp:end_samp]
                            
                            capture_path = os.path.join(base_dir, f"trigger_capture_snr{snr}_{chunk_name}")
                            np.save(capture_path, waveform_capture)
                            print(f"[*] Extracted {(end_samp - start_samp)//32} contiguous batches to {capture_path}.npy")
                            
                            results[str(snr)]["false_positives"] += 1
                            triggered_global = True
                            break # Break log parsing
                else:
                    fp_count = 0
                    for ev_idx in range(0, len(lines), clocks_per_event):
                        event_batches = lines[ev_idx : ev_idx + clocks_per_event]
                        if any(line == '1' for line in event_batches):
                            fp_count += 1
                    
                    results[str(snr)]["false_positives"] += fp_count
                
                events_in_chunk = np.load(chunk_file, mmap_mode='r').shape[0]
                results[str(snr)]["events_processed"] += events_in_chunk 
                
                os.remove(hw_log_path)

        with open(output_results_path, 'w') as f:
            json.dump(results, f, indent=4)
            print(f"[*] SNR {snr} verification point saved.")

    print(f"\n[*] Point Verification Complete. Results logged to {output_results_path}")

if __name__ == "__main__":
    main()
