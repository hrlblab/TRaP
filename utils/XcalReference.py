# XcalReference.py
# -*- coding: utf-8 -*-

"""
X-axis calibration reference data loader.

Reads reference spectra and peak lists from ``data/TRaP Xcal Data.xlsx`` for the
v3 calibration UI, which shows the reference spectrum alongside the user's input
spectrum. Each Excel sheet provides, for one reference material / configuration:

    - a reference spectrum (wavenumber axis + intensity),
    - a curated list of "commonly used" peaks (always shown),
    - the full list of "all" selectable peaks,
    - a 1-based spectral index for every peak (its pixel in the reference
      spectrum), verified against the wavenumber axis.

The peak wavenumbers are the trusted library values (a subset of the hardcoded
ReferenceLibrary in Calibration_v2), so calibration fits stay unchanged; the
Excel only adds the spectrum curve, the common/all split, and pixel indices for
plotting markers.

Data is loaded once and cached.
"""

import os
import numpy as np
import pandas as pd


# Fixed column layout of every sheet (verified):
#   0: wavenumber (Abs. for Ne-Ar, Rel. for Acetaminophen)
#   1: intensity
#   2: (blank separator)
#   3: Commonly Used Peaks   4: Spectral Index (1-based)
#   5: (blank separator)
#   6: All Peaks             7: Spectral Index (1-based)
_COL_WVN = 0
_COL_INTENSITY = 1
_COL_COMMON_WVN = 3
_COL_COMMON_IDX = 4
_COL_ALL_WVN = 6
_COL_ALL_IDX = 7

_DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "TRaP Xcal Data.xlsx")


class XcalRefData:
    """Reference data for a single sheet (one material / configuration)."""

    def __init__(self, key, label, material, xtype, wvn, intensity,
                 common_peaks, all_peaks):
        self.key = key                # short key, e.g. "NeAr785"
        self.label = label            # display label, e.g. "Ne-Ar (785 nm)"
        self.material = material      # "neon" or "acetaminophen"
        self.xtype = xtype            # "Abs" (absolute) or "Rel" (Raman shift)
        self.wvn = wvn                # reference spectrum wavenumber axis (N,)
        self.intensity = intensity    # reference spectrum intensity (N,)
        # Peaks: list of dicts {"wvn": float, "pixel": int (0-based),
        #                        "intensity": float}
        self.common_peaks = common_peaks
        self.all_peaks = all_peaks

    def __repr__(self):
        return (f"<XcalRefData {self.key}: {len(self.wvn)} pts, "
                f"{len(self.common_peaks)} common / {len(self.all_peaks)} all peaks>")


# Sheet registry: key -> (excel sheet name, display label, material)
_SHEETS = {
    "NeAr785": ("NeAr 785nm System", "Ne-Ar (785 nm)", "neon"),
    "NeAr830": ("NeAr 830nm System", "Ne-Ar (830 nm)", "neon"),
    "AcetFP":  ("Acet FP",           "Acetaminophen (Fingerprint)", "acetaminophen"),
    "AcetHW":  ("Acet HW",           "Acetaminophen (High Wavenumber)", "acetaminophen"),
}

_cache = {}  # key -> XcalRefData


def _peaks_from_columns(df, wvn_col, idx_col, intensity):
    """Build a peak list from a (wavenumber, 1-based spectral index) column pair."""
    wvns = df.iloc[:, wvn_col]
    idxs = df.iloc[:, idx_col]
    peaks = []
    for w, i in zip(wvns, idxs):
        if pd.isna(w) or pd.isna(i):
            continue
        pixel = int(round(float(i))) - 1  # spectral index is 1-based
        pixel = max(0, min(pixel, len(intensity) - 1))
        peaks.append({
            "wvn": float(w),
            "pixel": pixel,
            "intensity": float(intensity[pixel]),
        })
    return peaks


def _load_sheet(key):
    """Load and cache one sheet's reference data."""
    if key in _cache:
        return _cache[key]
    if key not in _SHEETS:
        raise KeyError(f"Unknown reference key: {key!r}")

    sheet_name, label, material = _SHEETS[key]
    df = pd.read_excel(_DATA_FILE, sheet_name=sheet_name, header=0)

    wvn = df.iloc[:, _COL_WVN].to_numpy(dtype=float)
    intensity = df.iloc[:, _COL_INTENSITY].to_numpy(dtype=float)
    # Drop trailing NaN rows from the spectrum (peak columns are shorter)
    valid = ~(np.isnan(wvn) | np.isnan(intensity))
    wvn = wvn[valid]
    intensity = intensity[valid]

    xtype = "Rel" if material == "acetaminophen" else "Abs"
    common_peaks = _peaks_from_columns(df, _COL_COMMON_WVN, _COL_COMMON_IDX, intensity)
    all_peaks = _peaks_from_columns(df, _COL_ALL_WVN, _COL_ALL_IDX, intensity)

    data = XcalRefData(key, label, material, xtype, wvn, intensity,
                       common_peaks, all_peaks)
    _cache[key] = data
    return data


class XcalReference:
    """Access point for calibration reference data."""

    @staticmethod
    def available(material=None):
        """List available references as (key, label), optionally filtered by material."""
        return [
            (k, v[1]) for k, v in _SHEETS.items()
            if material is None or v[2] == material
        ]

    @staticmethod
    def get(key):
        """Get the XcalRefData for a reference key (cached)."""
        return _load_sheet(key)

    @staticmethod
    def for_config(material, exc_wavelength=None, raman_range=None):
        """Auto-select a reference key from the current configuration.

        Args:
            material: "neon" or "acetaminophen".
            exc_wavelength: excitation wavelength (nm) — picks Ne-Ar 785 vs 830.
            raman_range: Raman shift range mode — picks Acet Fingerprint vs HW.

        Returns:
            A reference key string (always a valid, existing sheet).
        """
        if material == "neon":
            try:
                wl = float(exc_wavelength) if exc_wavelength is not None else 785.0
            except (TypeError, ValueError):
                wl = 785.0
            # 830 nm sheet for long-wavelength systems; otherwise 785 nm.
            return "NeAr830" if wl >= 807.5 else "NeAr785"
        elif material == "acetaminophen":
            rr = str(raman_range or "").lower()
            if "high" in rr or "hw" in rr:
                return "AcetHW"
            return "AcetFP"
        raise ValueError(f"Unknown material: {material!r}")
