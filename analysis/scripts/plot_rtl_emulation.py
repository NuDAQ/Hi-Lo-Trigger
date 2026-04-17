import numpy as np
import matplotlib.pyplot as plt
import os

def plot_rtl_emulation(npy_path, output_pdf_path, global_sigma=1.020833, snr_target=3.0):
    if not os.path.exists(npy_path):
        print(f"[!] Error: File not found at {npy_path}")
        return

    data = np.load(npy_path)
    channels, samples = data.shape
    
    # 1. Replicate exact hardware quantization threshold
    scale_factor = 64.0
    hw_thr_int = int(snr_target * global_sigma * scale_factor)
    effective_sigma_thr = hw_thr_int / scale_factor / global_sigma
    data_sigma = data / global_sigma

    print(f"[*] Hardware Int Threshold: {hw_thr_int}")
    print(f"[*] Effective Sigma Threshold: {effective_sigma_thr:.4f}")

    # VHDL Generic/Config Parameters (assuming standard values based on code)
    HILO_WINDOW = 16
    COINC_WINDOW = 32
    BIN_THR = 2  # Assuming multiplicity trigger requires 2 channels

    # 2. Evaluate instant threshold crossings (Hardware uses strictly greater/less than)
    v_ot_hi = data_sigma > effective_sigma_thr
    v_ot_lo = data_sigma < -effective_sigma_thr

    gate = np.zeros((channels, samples), dtype=bool)
    coinc = np.zeros((channels, samples), dtype=bool)

    # 3. Emulate PRE_TRIGGER_1CH.vhd (Hi-Lo window AND logic)
    for c in range(channels):
        for i in range(samples):
            hi_valid = np.any(v_ot_hi[c, max(0, i - HILO_WINDOW + 1):i + 1])
            lo_valid = np.any(v_ot_lo[c, max(0, i - HILO_WINDOW + 1):i + 1])
            if hi_valid and lo_valid:
                gate[c, i] = True

    # 4. Emulate PRE_TRIGGER.vhd (Coincidence smearing & carry-over)
    for c in range(channels):
        for i in range(samples):
            if np.any(gate[c, max(0, i - COINC_WINDOW + 1):i + 1]):
                coinc[c, i] = True

    # 5. Emulate MULT2BIN.vhd
    multiplicity = np.sum(coinc, axis=0)

    # --- Plotting Architecture ---
    fig, axes = plt.subplots(channels + 1, 1, figsize=(12, 2.5 * (channels + 1)), sharex=True)
    time_axis = np.arange(samples)
    batch_boundaries = np.arange(32, samples, 32)

    for c in range(channels):
        ax = axes[c]
        
        # Shade regions where the Coincidence Gate is held active
        ax.fill_between(time_axis, -5, 5, where=coinc[c], color='green', alpha=0.15, label='Coinc Gate Active')
        
        # Mark threshold cross points
        hi_idx = np.where(v_ot_hi[c])[0]
        lo_idx = np.where(v_ot_lo[c])[0]
        if len(hi_idx) > 0:
            ax.scatter(hi_idx, data_sigma[c, hi_idx], color='red', marker='^', zorder=3, s=30)
        if len(lo_idx) > 0:
            ax.scatter(lo_idx, data_sigma[c, lo_idx], color='blue', marker='v', zorder=3, s=30)
            
        ax.axhline(y=effective_sigma_thr, color='purple', linestyle='-', linewidth=1.2, alpha=0.8)
        ax.axhline(y=-effective_sigma_thr, color='purple', linestyle='-', linewidth=1.2, alpha=0.8)
        
        ax.plot(time_axis, data_sigma[c, :], color='black', linewidth=1.0, zorder=2)
        ax.set_ylabel(f'Ch {c} ($\\sigma$)')
        ax.set_ylim(-4.5, 4.5)
        ax.grid(True, axis='y', linestyle='--', alpha=0.5)
        
        for boundary in batch_boundaries:
            ax.axvline(x=boundary, color='blue', linestyle=':', linewidth=1.0, alpha=0.6)
            
        if c == 0:
            ax.legend(loc='upper right', fontsize='8')

    # Bottom Subplot: Multiplicity evaluation
    ax_mult = axes[-1]
    ax_mult.plot(time_axis, multiplicity, color='darkorange', linewidth=2.0, drawstyle='steps-post')
    ax_mult.fill_between(time_axis, 0, multiplicity, color='orange', alpha=0.3, step='post')
    ax_mult.axhline(y=BIN_THR, color='red', linestyle='--', linewidth=1.5, label=f'BIN_THR = {BIN_THR}')
    
    # Identify and mark true trigger instances
    trigger_points = np.where(multiplicity >= BIN_THR)[0]
    if len(trigger_points) > 0:
        ax_mult.scatter(trigger_points, multiplicity[trigger_points], color='red', marker='x', s=50, zorder=3)
        for pt in trigger_points:
            ax_mult.axvline(x=pt, color='red', linestyle='-', alpha=0.3, linewidth=1.0)
            
    ax_mult.set_ylabel('Multiplicity')
    ax_mult.set_yticks(range(channels + 1))
    ax_mult.set_ylim(0, channels + 0.5)
    ax_mult.grid(True, axis='y', linestyle='--', alpha=0.5)
    ax_mult.legend(loc='upper left', fontsize='8')
    ax_mult.set_xlabel('Sample Index (Vertical blue lines = 32-sample batch boundaries)')
    
    for boundary in batch_boundaries:
        ax_mult.axvline(x=boundary, color='blue', linestyle=':', linewidth=1.0, alpha=0.6)

    plt.suptitle(f'RTL Boolean Emulation & Trigger Analysis\nFile: {os.path.basename(npy_path)}', fontsize=12)
    plt.tight_layout()
    plt.savefig(output_pdf_path, format='pdf', bbox_inches='tight')
    plt.close()
    print(f"[*] Saved precise RTL emulation plot to: {output_pdf_path}")

if __name__ == "__main__":
    input_file = "trigger_capture_snr3.0_thermal_chunk_0000.npy"
    output_file = "trigger_capture_snr3.0_thermal_chunk_0000_rtl_emulation.pdf"
    plot_rtl_emulation(input_file, output_file)