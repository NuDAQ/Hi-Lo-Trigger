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
    # base_dir is analysis/scripts/
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Input data directory: analysis/data/thermal/
    data_dir = os.path.abspath(os.path.join(base_dir, "../data/thermal"))
    
    # Hardware directory (assuming it's parallel to the analysis root)
    hw_dir   = os.path.abspath(os.path.join(base_dir, "../../hw"))
    
    # CORRECTED PATH: analysis/data/false_triggered_events/
    capture_dir = os.path.abspath(os.path.join(base_dir, "../data/false_triggered_events"))
    os.makedirs(capture_dir, exist_ok=True)
    
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
    
    snr_thresholds = [4.0]
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
        
        for chunk_file in chunk_files:
            chunk_name = os.path.basename(chunk_file)
            print(f"[*] Processing: {chunk_name}")
            
            clocks_per_event = generate_stimulus_file(chunk_file, stimulus_txt_path, scale)
            
            comp_cmd = ["xvhdl", "--2008"] + rtl_files + [tb_file]
            
            # CORRECTED LOGIC: Passed ENABLE_RESET_ISOLATION=true to hardware
            elab_cmd = [
                "xelab", "-debug", "typical", "-top", "tb_hilo_trigger", 
                "-snapshot", "tb_snap", 
                "-generic_top", f"THRESHOLD={hw_thr}",
                "-generic_top", f"CLOCKS_PER_EVENT={clocks_per_event}",
                "-generic_top", "ENABLE_RESET_ISOLATION=true"
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
                
                fp_count = 0
                raw_data = None 
                
                # Iterate by strict event boundaries
                for ev_idx in range(0, len(lines), clocks_per_event):
                    event_batches = lines[ev_idx : ev_idx + clocks_per_event]
                    
                    if any(line == '1' for line in event_batches):
                        fp_count += 1
                        
                        if CAPTURE_WAVEFORM_ON_TRIGGER:
                            if raw_data is None:
                                raw_data = np.load(chunk_file)
                                raw_data = np.squeeze(raw_data)
                            
                            event_number = ev_idx // clocks_per_event
                            waveform_capture = raw_data[event_number, :, :]
                            
                            # Utilizing the corrected path
                            capture_path = os.path.join(capture_dir, f"trigger_capture_snr{snr}_{chunk_name}_ev{event_number}")
                            np.save(capture_path, waveform_capture)
                            print(f"[!] Trigger detected. Extracted event {event_number} to {capture_path}.npy")
                
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
    