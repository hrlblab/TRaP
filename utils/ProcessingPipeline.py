#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Processing Pipeline - single source of truth for the P-Mean preprocessing chain.

This module exposes a *pure*, replayable pipeline function that maps
(raw data, correction factor, wavenumber axis, config) -> (wvn, spectrum).

It is shared by:
- Single-spectrum processing UI (UI_P_Mean_Process.py) - for live preview
- Batch processing UI (UI_P_Mean_Batch_Process.py) - per-file processing

Keeping the chain in one place guarantees that interactive preview and batch
output stay identical, and makes real-time re-computation safe: any parameter
change simply calls run_pipeline() again on the untouched raw data, which
re-runs the whole chain and refreshes every intermediate/final result.
"""

import numpy as np
from scipy.signal import medfilt

from utils.SpectralPreprocess import (
    Binning, Denoise, Truncate, CosmicRayRemoval,
    SpectralResponseCorrection, subtractBaseline,
    FluorescenceBackgroundSubtraction, Normalize
)


def parse_exclude_mask(wvn: np.ndarray, exclude_text: str):
    """Build a boolean exclude mask from a wavenumber array and a range string."""
    if not exclude_text or not exclude_text.strip():
        return None
    mask = np.zeros(len(wvn), dtype=bool)
    for part in exclude_text.split(','):
        part = part.strip()
        if '-' in part:
            try:
                lo, hi = part.split('-', 1)
                mask |= (wvn >= float(lo)) & (wvn <= float(hi))
            except ValueError:
                pass
    return mask if mask.any() else None


def run_pipeline(data: np.ndarray, wl_corr: np.ndarray, wvn: np.ndarray, config: dict,
                 skip_wl_correction: bool = False, skip_baseline: bool = False):
    """Run the full P-Mean preprocessing pipeline on raw data.

    This is a *pure* function: it does not mutate its inputs, so it is safe to
    call repeatedly on the same raw data for live preview.

    Args:
        data: Raw spectrum data
        wl_corr: WL correction factor (ignored if skip_wl_correction=True)
        wvn: Wavenumber array
        config: Processing configuration
        skip_wl_correction: If True, skip spectral response correction
        skip_baseline: If True, skip dark baseline subtraction (Renishaw/microscope)

    Returns:
        (new_wvn, finalSpect): processed wavenumber axis and spectrum
    """
    # 1) Baseline, response correction, cosmic ray removal
    spect = data if skip_baseline else subtractBaseline(data)
    if not skip_wl_correction and wl_corr is not None:
        spect = SpectralResponseCorrection(wl_corr, spect)
    spect = CosmicRayRemoval(spect)

    # 2) Truncate
    start = float(config.get("Start", 900))
    stop = float(config.get("Stop", 1700))
    wvn_trunc, spect_trunc = Truncate(start, stop, wvn, spect)

    # 3) Binning - flatten arrays to ensure 1D input
    wvn_trunc = wvn_trunc.flatten()
    spect_trunc = spect_trunc.flatten()
    binwidth = float(config.get("BinWidth", 3.5))
    binned_spect, new_wvn = Binning(wvn_trunc[0], wvn_trunc[-1], wvn_trunc, spect_trunc, binwidth=binwidth)

    # 4) Fluorescence background subtraction (with optional exclusion regions)
    polyorder = int(config.get("Polyorder", 7))
    fbs_maxiter = int(config.get("FBSMaxIter", 50))
    exclude_mask = parse_exclude_mask(new_wvn, str(config.get("FBSExclude", "")))
    _, fbs_spect = FluorescenceBackgroundSubtraction(binned_spect, polyorder, max_iter=fbs_maxiter,
                                                      exclude_mask=exclude_mask)

    # 5) Noise smoothing
    method = str(config.get("DenoiseMethod", "Savitzky-Golay"))
    if method == "Savitzky-Golay":
        SGorder = int(config.get("SGorder", 2))
        SGframe = int(config.get("SGframe", 7))
        finalSpect = Denoise(fbs_spect, SGorder=SGorder, SGframe=SGframe)
    elif method == "Moving Average":
        MAWindow = max(1, int(config.get("MAWindow", 5)))
        kernel = np.ones(MAWindow, dtype=np.float64) / MAWindow
        finalSpect = np.convolve(fbs_spect, kernel, mode='same')
    elif method == "Median Filter":
        MedianKernel = int(config.get("MedianKernel", 5))
        if MedianKernel % 2 == 0:
            MedianKernel += 1
        finalSpect = medfilt(fbs_spect, kernel_size=MedianKernel)
    else:
        finalSpect = fbs_spect

    # 6) Optional second truncation (before normalization)
    if config.get("Truncate2Enabled", False):
        start2 = float(config.get("Start2", 900))
        stop2  = float(config.get("Stop2", 1700))
        if stop2 > start2:
            new_wvn, finalSpect = Truncate(start2, stop2, new_wvn, finalSpect)

    # 7) Normalization
    norm_method = str(config.get("NormalizeMethod", "Mean")).lower()
    finalSpect = Normalize(finalSpect, method=norm_method)

    return new_wvn, finalSpect


# Backwards-compatible alias (batch UI historically used this name).
p_mean_process = run_pipeline
