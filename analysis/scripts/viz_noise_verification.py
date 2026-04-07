import os
import json
import glob
import numpy as np
import array
import ROOT

def generate_thermal_verification():
    # 1. Path Resolution
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.abspath(os.path.join(script_dir, "../data/thermal"))
    json_path = os.path.join(script_dir, "far_results.json")
    output_root = os.path.abspath(os.path.join(script_dir, "../thermal_verification.root"))

    if not os.path.exists(json_path):
        print(f"[!] CRITICAL: Missing VHDL results file at {json_path}")
        return

    chunk_files = sorted(glob.glob(os.path.join(data_dir, "thermal_chunk_*.npy")))
    if not chunk_files:
        print(f"[!] CRITICAL: No chunk files found in {data_dir}")
        return

    # 2. Base Noise RMS Extraction
    print("[*] Calculating True Noise RMS from the first chunk...")
    sample_data = np.load(chunk_files[0])
    noise_rms = float(np.std(sample_data))
    print(f"[*] Base Noise RMS: {noise_rms:.6f}")

    # 3. Parse Hardware VHDL Data
    print("\n[*] Parsing VHDL Hardware Data...")
    with open(json_path, 'r') as f:
        vhdl_results = json.load(f)

    hw_snr_vals = array.array('d')
    hw_far_vals = array.array('d')

    for snr_str, data in vhdl_results.items():
        events = data.get("events_processed", 0)
        if events > 0:
            snr = float(snr_str)
            fp = data.get("false_positives", 0)
            far = fp / events
            
            hw_snr_vals.append(snr)
            hw_far_vals.append(max(far, 1e-8)) # Log-scale floor
            print(f"    VHDL SNR {snr}: {fp} FPs over {events} events (FAR: {far:.4e})")

    # 4. Continuous Python Emulation (Optimized Chunk-First Architecture)
    total_py_events = len(chunk_files) * 25000
    
    # Sweep from SNR 1.5 to 4.5 in 0.1 increments
    snr_sweep = np.round(np.arange(1.5, 4.6, 0.1), 1)
    fp_totals = {snr: 0 for snr in snr_sweep}
    all_max_amps_rms = []

    BIN_THR = 2
    HILO_WINDOW = 5
    COINCIDENCE_WINDOW = 32

    print(f"\n[*] Running Python emulation across FULL {total_py_events} events...")
    
    # I/O OPTIMIZATION: Load chunk once, process all thresholds, then drop.
    for chunk_idx, chunk in enumerate(chunk_files):
        if chunk_idx % 10 == 0:
            print(f"    Processing chunk {chunk_idx}/{len(chunk_files)}...")
            
        X_test = np.squeeze(np.load(chunk))
        X_int = np.round(X_test * 64.0).astype(np.int32)
        
        # Extract amplitude distribution data while the chunk is in RAM
        max_amps_per_event_hw = np.max(np.abs(X_int), axis=(1, 2))
        max_amps_per_event_rms = (max_amps_per_event_hw / 64.0) / noise_rms
        all_max_amps_rms.extend(max_amps_per_event_rms)
        
        # Emulate all SNR thresholds for this specific chunk
        for snr in snr_sweep:
            thresh_hw_int = int(snr * noise_rms * 64.0)
            
            crossed_hi = (X_int > thresh_hw_int)
            crossed_lo = (X_int < -thresh_hw_int)
            
            gates_hi = np.zeros_like(crossed_hi)
            gates_lo = np.zeros_like(crossed_lo)
            
            for shift in range(HILO_WINDOW):
                if shift == 0:
                    gates_hi |= crossed_hi
                    gates_lo |= crossed_lo
                else:
                    gates_hi[:, :, shift:] |= crossed_hi[:, :, :-shift]
                    gates_lo[:, :, shift:] |= crossed_lo[:, :, :-shift]
                    
            bipolar_trigger = gates_hi & gates_lo
            
            coincidence_gates = np.zeros_like(bipolar_trigger)
            for shift in range(COINCIDENCE_WINDOW):
                if shift == 0:
                    coincidence_gates |= bipolar_trigger
                else:
                    coincidence_gates[:, :, shift:] |= bipolar_trigger[:, :, :-shift]
            
            multiplicity = np.sum(coincidence_gates, axis=1)
            event_triggered = np.any(multiplicity >= BIN_THR, axis=1)
            
            fp_totals[snr] += np.sum(event_triggered)

    # 5. Compile Python Metrics
    py_snr_vals = array.array('d')
    py_far_vals = array.array('d')
    
    for snr in snr_sweep:
        far = fp_totals[snr] / total_py_events
        py_snr_vals.append(snr)
        py_far_vals.append(max(far, 1e-8))

    max_amp_overall_rms = max(all_max_amps_rms) if all_max_amps_rms else 5.0

    # 6. ROOT Plotting
    print(f"\n[*] Generating ROOT file at {output_root}...")
    ROOT.gROOT.SetBatch(True)
    root_file = ROOT.TFile(output_root, "RECREATE")

    # --- Canvas 1: Amplitude Distribution ---
    c_hist = ROOT.TCanvas("c_hist", "Noise Amplitude Distribution", 800, 600)
    h_noise = ROOT.TH1F("h_noise", "Max Absolute Amplitude per Event;Maximum Amplitude (Multiples of Noise RMS);Events", 100, 0, max_amp_overall_rms)
    
    for val in all_max_amps_rms: 
        h_noise.Fill(val)
        
    h_noise.SetFillColorAlpha(ROOT.kRed, 0.3)
    h_noise.SetLineColor(ROOT.kRed)
    h_noise.SetMinimum(0.5)
    
    h_noise.Draw("HIST")
    ROOT.gPad.SetLogy()
    
    leg_hist = ROOT.TLegend(0.65, 0.75, 0.88, 0.88)
    leg_hist.SetBorderSize(1)
    leg_hist.AddEntry(h_noise, "Thermal Background Noise", "f")
    leg_hist.Draw()
    c_hist.Write()

    # --- Canvas 2: FAR Verification (Python vs VHDL) ---
    c_rate = ROOT.TCanvas("c_rate", "False Alarm Rate", 800, 600)
    mg_rate = ROOT.TMultiGraph()
    mg_rate.SetTitle("Hi-Lo Trigger FAR: Python Emulation vs. VHDL;Threshold (SNR);False Alarm Rate (Triggers / Event)")
    
    g_py_rate = ROOT.TGraph(len(py_snr_vals), py_snr_vals, py_far_vals)
    g_py_rate.SetName("g_py_rate")
    g_py_rate.SetLineColor(ROOT.kBlue)
    g_py_rate.SetLineWidth(2)
    
    g_hw_rate = ROOT.TGraph(len(hw_snr_vals), hw_snr_vals, hw_far_vals)
    g_hw_rate.SetName("g_hw_rate")
    g_hw_rate.SetMarkerStyle(29) # ROOT.kFullStar
    g_hw_rate.SetMarkerSize(2.5)
    g_hw_rate.SetMarkerColor(ROOT.kRed)
    
    mg_rate.Add(g_py_rate, "L")
    mg_rate.Add(g_hw_rate, "P")
    mg_rate.Draw("A")
    mg_rate.SetMinimum(1e-6)
    
    leg_rate = ROOT.TLegend(0.55, 0.65, 0.88, 0.85)
    leg_rate.SetBorderSize(1)
    leg_rate.AddEntry(g_py_rate, "Python Emulation (Line)", "l")
    leg_rate.AddEntry(g_hw_rate, "VHDL Simulation (Stars)", "p")
    leg_rate.Draw()
    
    ROOT.gPad.SetLogy()
    c_rate.Write()

    root_file.Close()
    print("[*] Execution complete.")

if __name__ == "__main__":
    generate_thermal_verification()
