#!/usr/bin/env python3
import os
import numpy as np
import ROOT

def main():
    ROOT.gROOT.SetBatch(True)

    data_path = '../data/thermal/thermal_chunk_0000.npy'
    output_path = 'noise_distribution.root'

    if not os.path.exists(data_path):
        print(f"Error: Input file {data_path} not found.")
        return

    data = np.load(data_path)

    n_events = 1000
    if data.shape[0] < n_events:
        print(f"Warning: File contains fewer than {n_events} events. Using available events.")
        n_events = data.shape[0]

    samples = data[:n_events].flatten().astype(np.float64)

    hist = ROOT.TH1D("h_noise", "Noise Sample Distribution;Sample Value;Counts", 160, -8.0, 8.0)

    weights = np.ones(len(samples), dtype=np.float64)
    hist.FillN(len(samples), samples, weights)

    hist.Fit("gaus", "S", "", -2.5, 2.5)
    fit_func = hist.GetFunction("gaus")
    if fit_func:
        fit_func.SetRange(-8.0, 8.0)
        fit_func.SetLineColor(ROOT.kRed)

    hist.SetLineColor(ROOT.kBlue)
    hist.SetMarkerStyle(20)
    hist.SetMarkerSize(0.5)

    canvas = ROOT.TCanvas("c1", "Thermal Noise Distribution Canvas", 1200, 600)
    canvas.Divide(2, 1)

    pad1 = canvas.cd(1)
    pad1.SetGrid()
    hist.Draw("E")

    pad2 = canvas.cd(2)
    pad2.SetLogy()
    pad2.SetGrid()
    hist_log = hist.Clone("h_noise_log")
    hist_log.Draw("E")

    root_file = ROOT.TFile(output_path, "RECREATE")
    
    hist.Write()
    hist_log.Write()
    canvas.Write()

    root_file.Close()
    print(f"Analysis complete. ROOT file saved to: {os.path.abspath(output_path)}")

if __name__ == "__main__":
    main()
