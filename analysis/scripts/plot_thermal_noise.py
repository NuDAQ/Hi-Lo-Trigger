#!/usr/bin/env python3
import os
import numpy as np
import ROOT

def main():
    ROOT.gROOT.SetBatch(True)

    data_path = '../data/thermal/thermal_chunk_0000.npy'
    output_path = 'noise_distribution_sigma.root'

    if not os.path.exists(data_path):
        print(f"Error: Input file {data_path} not found.")
        return

    data = np.load(data_path)

    n_events = 1000
    if data.shape[0] < n_events:
        n_events = data.shape[0]

    raw_samples = data[:n_events].flatten().astype(np.float64)
    weights = np.ones(len(raw_samples), dtype=np.float64)

    temp_hist = ROOT.TH1D("h_temp", "temp", 160, -8.0, 8.0)
    temp_hist.FillN(len(raw_samples), raw_samples, weights)
    
    temp_hist.Fit("gaus", "Q0", "", -2.5, 2.5)
    core_fit = temp_hist.GetFunction("gaus")
    
    if not core_fit:
        print("Error: Preliminary core fit failed.")
        return

    core_mu = core_fit.GetParameter(1)
    core_sigma = core_fit.GetParameter(2)

    sigma_samples = (raw_samples - core_mu) / core_sigma

    hist = ROOT.TH1D("h_noise_sigma", "Normalized Noise Distribution;Noise Level [#sigma];Counts", 160, -8.0, 8.0)
    hist.FillN(len(sigma_samples), sigma_samples, weights)

    hist.Fit("gaus", "S", "", -2.5, 2.5)
    fit_func = hist.GetFunction("gaus")
    if fit_func:
        fit_func.SetRange(-8.0, 8.0)
        fit_func.SetLineColor(ROOT.kRed)

    hist.SetLineColor(ROOT.kBlue)
    hist.SetMarkerStyle(20)
    hist.SetMarkerSize(0.5)

    canvas = ROOT.TCanvas("c1", "Normalized Thermal Noise Canvas", 1200, 600)
    canvas.Divide(2, 1)

    pad1 = canvas.cd(1)
    pad1.SetGrid()
    hist.Draw("E")

    pad2 = canvas.cd(2)
    pad2.SetLogy()
    pad2.SetGrid()
    hist_log = hist.Clone("h_noise_sigma_log")
    hist_log.Draw("E")

    root_file = ROOT.TFile(output_path, "RECREATE")
    hist.Write()
    hist_log.Write()
    canvas.Write()
    root_file.Close()

    print(f"Core baseline used for normalization: Mu = {core_mu:.5e}, Sigma = {core_sigma:.5f}")

if __name__ == "__main__":
    main()