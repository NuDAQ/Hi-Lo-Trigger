import os
import glob
import subprocess
import json
import numpy as np
from submodule.stimulus_generation import generate_stimulus_file

def main():
    # 1. Directory Path Resolution
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.abspath(os.path.join(base_dir, "../data/thermal"))
    hw_dir   = os.path.abspath(os.path.join(base_dir, "../../hw"))
    
    # Working files (generated in analysis/scripts/)
    stimulus_txt_path = os.path.join(base_dir, "stimulus.txt")
    hw_log_path = os.path.join(base_dir, "hw_resp.txt")
    output_results_path = os.path.join(base_dir, "far_results.json")
    
    # Target VHDL Files (Dependency Order is Critical)
    rtl_files = [
        os.path.join(hw_dir, "rtl/PRE_TRIGGER_PKG.vhd"),
        os.path.join(hw_dir, "rtl/Pre_trigger_1ch.vhd"),
        os.path.join(hw_dir, "rtl/Mult_to_bin.vhd"),
        os.path.join(hw_dir, "rtl/Pre_trigger.vhd")
    ]
    tb_file = os.path.join(hw_dir, "sim/tb_hilo_trigger.vhd")
    
    # Validate VHDL files
    for vhdl_file in rtl_files + [tb_file]:
        if not os.path.exists(vhdl_file):
            print(f"[!] CRITICAL: Hardware source file missing: {vhdl_file}")
            return

    chunk_files = sorted(glob.glob(os.path.join(data_dir, "thermal_chunk_*.npy")))
    if not chunk_files:
        print(f"[!] CRITICAL: No chunk files found in {data_dir}")
        return

    # Calculate True Noise RMS from the first chunk for accurate SNR scaling
    print("[*] Calculating True Noise RMS from first chunk...")
    sample_data = np.load(chunk_files[0])
    noise_rms = float(np.std(sample_data))
    print(f"[*] Detected Noise RMS: {noise_rms:.6f}")

    # OPTIMIZED: Narrow sweep for point-verification
    snr_thresholds = [2.0, 3.0, 4.0]
    scale = 64.0 
    
    # Initialize results with scaled hardware thresholds
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
            
            # Step A: Stream Stimulus to Disk
            generate_stimulus_file(chunk_file, stimulus_txt_path, scale)
            
            # Step B: Hardware Co-Simulation Execution via Vivado CLI
            comp_cmd = ["xvhdl", "--2008"] + rtl_files + [tb_file]
            elab_cmd = [
                "xelab", "-debug", "typical", "-top", "tb_hilo_trigger", 
                "-snapshot", "tb_snap", "-generic_top", f"THRESHOLD={hw_thr}"
            ]
            sim_cmd = ["xsim", "tb_snap", "-R"]
            
            try:
                subprocess.run(comp_cmd, check=True, stdout=subprocess.DEVNULL)
                subprocess.run(elab_cmd, check=True, stdout=subprocess.DEVNULL)
                subprocess.run(sim_cmd, check=True, stdout=subprocess.DEVNULL)
            except subprocess.CalledProcessError as e:
                print(f"[!] CRITICAL: Vivado toolchain failed during {chunk_name}. {e}")
                return
            
            # Step C: Data Extraction
            if os.path.exists(hw_log_path):
                with open(hw_log_path, 'r') as f:
                    fp_count = sum(1 for line in f if '1' in line.strip())
                
                results[str(snr)]["false_positives"] += fp_count
                
                # Fetch exact event count safely using memmap
                events_in_chunk = np.load(chunk_file, mmap_mode='r').shape[0]
                results[str(snr)]["events_processed"] += events_in_chunk 
                
                os.remove(hw_log_path)
            else:
                print(f"[!] WARNING: {hw_log_path} missing.")
            
            # Clean up text stimulus to save disk space
            if os.path.exists(stimulus_txt_path):
                os.remove(stimulus_txt_path)

        # Output JSON after every full dataset sweep (Checkpoint)
        with open(output_results_path, 'w') as f:
            json.dump(results, f, indent=4)
            print(f"[*] SNR {snr} verification point saved.")

    print(f"\n[*] Point Verification Complete. Results logged to {output_results_path}")

if __name__ == "__main__":
    main()
