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

import warnings

import numpy as np
from scipy.signal import medfilt


class BinWidthTooFine(UserWarning):
    """Raised as a warning when BinWidth is finer than the detector's sampling.

    Bins that catch no sample are interpolated from their neighbours to keep the
    output axis uniform, so the result is usable — but those points are not
    measured, and the caller should know.
    """

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


def cosmic_params(config: dict) -> dict:
    """Pull the cosmic-ray parameters out of a config, using paper defaults.

    Whitaker-Hayes keys come first, then Li-Dai's (named as in the paper, with
    its Table III values).
    """
    return {
        "z_thresh":    float(config.get("CRZThresh", 15.0)),
        "max_width":   int(config.get("CRMaxWidth", 3)),
        "fill_window": int(config.get("CRFillWindow", 5)),
        "rp":          float(config.get("CRPartitionRatio", 0.33)),
        "t":           float(config.get("CRIntensityThresh", 5.0)),
        "w":           int(config.get("CRCorrWindow", 3)),
        "Rt":          float(config.get("CRCorrThresh", 0.6)),
        "tr":          float(config.get("CRResizeThresh", 4.0)),
        "nr":          int(config.get("CRNeighborPixels", 3)),
        "polyorder":   int(config.get("Polyorder", 7)),
        "fbs_maxiter": int(config.get("FBSMaxIter", 50)),
    }


def run_pipeline(data: np.ndarray, wl_corr: np.ndarray, wvn: np.ndarray, config: dict,
                 skip_wl_correction: bool = False, skip_baseline: bool = False,
                 return_prenorm: bool = False, msn_data: np.ndarray = None,
                 return_cosmic: bool = False):
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
        return_prenorm: If True, also return the pre-normalization spectrum (the
            fully processed result of every step *except* normalization).
        msn_data: Raw data of a neighbouring acquisition of the same sample,
            used by the "Li-Dai" cosmic ray method. It is put through the same
            baseline and response correction as `data` so the two are compared
            on equal footing. Without it Li-Dai falls back to Whitaker-Hayes.
        return_cosmic: If True, also return (replaced_mask, method_used) from
            the cosmic ray step.

    Returns:
        (new_wvn, finalSpect) by default. `return_prenorm` appends the
        pre-normalization spectrum, and `return_cosmic` appends the cosmic-ray
        mask and the method actually applied — in that order.
    """
    # 1) Baseline, response correction, cosmic ray removal
    spect = data if skip_baseline else subtractBaseline(data)
    if not skip_wl_correction and wl_corr is not None:
        # Pass the wavenumber axis so a two-column [wavenumber, factor] file is
        # interpolated onto the spectrum instead of aligned by row index.
        spect = SpectralResponseCorrection(wl_corr, spect, wvn=wvn)

    # Cosmic ray removal runs here, before truncation and binning: once binned,
    # a spike is averaged across its bin and can no longer be identified.
    msn = None
    if msn_data is not None:
        msn = msn_data if skip_baseline else subtractBaseline(msn_data)
        if not skip_wl_correction and wl_corr is not None:
            msn = SpectralResponseCorrection(wl_corr, msn, wvn=wvn)
    spect, cosmic_mask, cosmic_used = CosmicRayRemoval(
        spect, method=str(config.get("CosmicRayMethod", "None")),
        msn_spect=msn, params=cosmic_params(config), return_mask=True
    )

    # 2) Truncate
    start = float(config.get("Start", 900))
    stop = float(config.get("Stop", 1700))
    wvn_trunc, spect_trunc = Truncate(start, stop, wvn, spect)

    # 3) Binning - flatten arrays to ensure 1D input
    wvn_trunc = wvn_trunc.flatten()
    spect_trunc = spect_trunc.flatten()
    binwidth = float(config.get("BinWidth", 3.5))
    binned_spect, new_wvn, bin_info = Binning(wvn_trunc[0], wvn_trunc[-1], wvn_trunc,
                                              spect_trunc, binwidth=binwidth,
                                              return_info=True)
    if bin_info["starved"] and len(wvn_trunc) > 1:
        # The requested bin width is finer than the detector samples, so some
        # bins carry interpolated values rather than measured ones. Say so.
        step = np.diff(wvn_trunc)
        bin_info["max_native_step"] = float(step.max())
        bin_info["median_native_step"] = float(np.median(step))
        warnings.warn(
            f"BinWidth {binwidth:g} cm-1 is finer than the data supports: "
            f"{bin_info['n_filled']} of {bin_info['n_bins']} bins caught no sample "
            f"and were interpolated. The axis spacing reaches "
            f"{bin_info['max_native_step']:.3f} cm-1 (median "
            f"{bin_info['median_native_step']:.3f}). Set BinWidth at or above the "
            f"maximum spacing to bin only measured points.",
            BinWidthTooFine, stacklevel=2
        )

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
    #    Keep the pre-normalization spectrum so callers can save both the
    #    normalized result and the raw-scale (non-normalized) intensities.
    prenorm_spect = finalSpect
    norm_method = str(config.get("NormalizeMethod", "Mean")).lower()
    finalSpect = Normalize(prenorm_spect, method=norm_method)

    out = [new_wvn, finalSpect]
    if return_prenorm:
        out.append(prenorm_spect)
    if return_cosmic:
        out += [cosmic_mask, cosmic_used]
    return tuple(out) if len(out) > 2 else (new_wvn, finalSpect)


# Backwards-compatible alias (batch UI historically used this name).
p_mean_process = run_pipeline
