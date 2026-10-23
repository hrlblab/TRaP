import warnings

import numpy as np
import pandas as pd
import os
import utils.savgol, utils.lsqpolyfit, utils.lsqpolyval

# NIST SRM 2241, relative spectral irradiance as a polynomial in Raman shift,
# certified for 785 nm excitation over roughly 200-3500 cm-1.
#
# The last coefficient used to read 1.515596e-17 here. That is wrong, and the
# fifth-power term makes it badly wrong at the top of the range: against a
# collaborator's own SRM measurement and the correction factor his pipeline
# derived from it, the two differ by up to x1.14 across a 264-2008 cm-1 window
# and by up to x5.9 across 2230-3974 cm-1. Scored the only way that is
# meaningful -- a correct curve may differ from his by a constant scale, so the
# test is whether the ratio is FLAT -- the value below holds the ratio to 3.4%
# where the old one spread it over 13.0%.
SRM2241_785_COEFFS = [9.71937e-02, 2.28325e-04, -5.86762e-08,
                      2.16023e-10, -9.77171e-14, 1.15596e-17]
SRM2241_EXCITATION_NM = 785.0
SRM2241_VALID_RANGE = (200.0, 3500.0)
WLMax = []
# def WLCorrection(WL, Cal_wvn):
#     # Smooth user-measured White Light Spectrum
#     SWL = utils.savgol.savgol_filter(WL, 15, 1, 0)
#
#     # Change X-axis Calibration File to the wavelength
#     Cal_wvlength = 10e-7 / Cal_wvn
#
#     # Create Polynomial from the True White Light Coefficients that were provided by the lamp manufacturer
#     p = utils.lsqpolyfit.lsqpolyfit(WLMax[:, 0], WLMax[:, 1], None, 8)
#
#     # Match X-axis indices of the user-measured WL to the True WL (both are already in wavelength, but the actual indices might not match up)
#     true_WL = utils.lsqpolyval.lsqpolyval(p, Cal_wvlength)
#
#     # Choose the approximate center of the WL spectrum
#     loc = np.searchsorted(Cal_wvlength, 860, side="left")
#
#     # Normalization to the center location that we determined in the previous step
#     # Formula is WLcorrected = Normalize(WLtrue) / Normalize(WLuser-measured)
#     # where Normalize is the function which normalizes the spectrum to the approximate center
#     NTWL = true_WL / true_WL[loc]
#     NWL = SWL / SWL[loc]
#     WL_Correction = NTWL / NWL
#
#     return WL_Correction
#
light_curve_coeff = []
# def NISTCorrection(SRM, Cal_wvn):
#     SRM_1 = SRM - np.mean(SRM[10:25])
#     true_SRM = light_curve_coeff[0] + light_curve_coeff[1] * Cal_wvn + light_curve_coeff[2] * Cal_wvn ^ 2 + light_curve_coeff[3] * Cal_wvn ^ 3 + light_curve_coeff[4] * Cal_wvn ^ 4 + light_curve_coeff[5] * Cal_wvn ^ 5
#     loc = np.searchsorted(Cal_wvn, 1100, side="left")
#     NSRM = SRM_1 / SRM_1[loc]
#     NTSRM = true_SRM/true_SRM[loc]
#     SRM_correction = NTSRM / NSRM
#     SRM_correction = utils.savgol.savgol_filter(SRM_correction, 9, 1, 0)
#     return SRM_correction
#

def _read_text_robust(fp: str) -> np.ndarray:
    """
    Robustly read a numeric text file (txt/csv).

    Handles:
      - Header rows (non-numeric first lines are skipped)
      - European decimal format: "1,1214" means 1.1214
      - Tab / space / comma delimiters
    """
    with open(fp, 'r', encoding='utf-8') as f:
        raw_lines = f.readlines()

    # Strip empty / whitespace-only lines
    lines = [l.strip() for l in raw_lines if l.strip()]
    if not lines:
        raise ValueError(f"File is empty: {fp}")

    # Skip header lines (lines where first token is not numeric)
    data_start = 0
    for i, line in enumerate(lines):
        token = line.split(',')[0].split('\t')[0].split()[0]
        try:
            float(token)
            data_start = i
            break
        except ValueError:
            continue
    else:
        raise ValueError(f"No numeric data found in: {fp}")

    data_lines = lines[data_start:]

    # Detect if file uses European decimal (comma as decimal separator).
    # Heuristic: if a data line has exactly one comma AND no tab/semicolon,
    # and both sides of the comma are digits, treat comma as decimal point.
    sample = data_lines[0]
    use_european = False
    if '\t' not in sample and ';' not in sample:
        parts = sample.split(',')
        if len(parts) == 2:
            # Could be "1,1214" (european) or "1.0,2.0" (two-column csv)
            left, right = parts[0].strip(), parts[1].strip()
            # If left part has a dot, it's regular CSV like "1.0,2.0"
            if '.' not in left and '.' not in right:
                try:
                    float(left)
                    float(right)
                    # Both parseable as int-like → likely European decimal
                    use_european = True
                except ValueError:
                    pass

    if use_european:
        # Replace comma with dot for decimal
        converted = '\n'.join(l.replace(',', '.') for l in data_lines)
        from io import StringIO
        arr = np.loadtxt(StringIO(converted))
    else:
        # Detect delimiter from first data line
        if '\t' in sample:
            delimiter = '\t'
        elif ';' in sample:
            # Semicolon-delimited (common in European CSV with comma decimal)
            # Also replace comma→dot in values
            converted = '\n'.join(l.replace(',', '.') for l in data_lines)
            from io import StringIO
            arr = np.loadtxt(StringIO(converted), delimiter=';')
            return arr
        elif ',' in sample:
            delimiter = ','
        else:
            delimiter = None  # whitespace

        from io import StringIO
        text = '\n'.join(data_lines)
        arr = np.loadtxt(StringIO(text), delimiter=delimiter)

    return arr


def read_vector_file(fp: str) -> np.ndarray:
    """
    Read a single-column vector (txt/csv/xlsx).

    Returns:
        np.ndarray: Column vector (N, 1) for consistency across the workflow
    """
    ext = os.path.splitext(fp)[1].lower()
    if ext in [".txt", ".csv"]:
        arr = _read_text_robust(fp)
    elif ext in [".xlsx", ".xls"]:
        df = pd.read_excel(fp, header=None)
        arr = df.values.squeeze()
    else:
        raise ValueError("Unsupported file format for vector.")
    return np.asarray(arr, dtype=float).reshape(-1, 1)


def read_2col_file(fp: str) -> np.ndarray:
    """Read a 2-column table (wavelength, intensity). Returns float array (N, 2)."""
    ext = os.path.splitext(fp)[1].lower()
    if ext in [".txt", ".csv"]:
        arr = _read_text_robust(fp)
    elif ext in [".xlsx", ".xls"]:
        df = pd.read_excel(fp, header=None)
        arr = df.values
    else:
        raise ValueError("Unsupported file format for two-column data.")
    arr = np.asarray(arr, dtype=float)
    if arr.ndim != 2 or arr.shape[1] < 2:
        raise ValueError("Two-column data (wavelength, intensity) required.")
    return arr[:, :2]


def read_coeffs_file(fp: str) -> np.ndarray:
    """Read polynomial coefficients (one per line or single row). Returns float array (N,)."""
    ext = os.path.splitext(fp)[1].lower()
    if ext in [".txt", ".csv"]:
        arr = _read_text_robust(fp)
    elif ext in [".xlsx", ".xls"]:
        df = pd.read_excel(fp, header=None)
        arr = df.values.squeeze()
    else:
        raise ValueError("Unsupported file format for coefficients.")
    return np.asarray(arr, dtype=float).reshape(-1)

def wl_correction_from_true_and_measured(
    wl_measured: np.ndarray,
    cal_wvn: np.ndarray,
    wlmax_2col: np.ndarray,
    smooth_window: int = 15,
    smooth_order: int = 1,
    poly_order: int = 8,
    center_wavelength: float = 860.0,
    laser_wavelength: float = 785.0,
) -> np.ndarray:
    """
    Compute White-Light correction factor using utils modules.

    Args:
        wl_measured: measured white-light spectrum (N,) or (N,1).
        cal_wvn: wavenumber axis (cm^-1), (N,) or (N,1).
        wlmax_2col: (M,2) array: manufacturer-provided True WL [wavelength, intensity].
        smooth_window: window length for Savitzky-Golay filter.
        smooth_order: polynomial order for Savitzky-Golay filter.
        poly_order: polynomial degree for true WL fitting.
        center_wavelength: normalization wavelength.

    Returns:
        correction factor (N, 1) column vector
    """
    wl_measured = np.asarray(wl_measured, dtype=float).flatten()
    cal_wvn = np.asarray(cal_wvn, dtype=float).flatten()

    # Smooth user-measured White Light Spectrum
    # savgol_filter expects (m, n) format where m=signals, n=length
    # Reshape to row vector (1, n), then flatten result
    wl_row = wl_measured.reshape(1, -1)
    SWL, _ = utils.savgol.savgol_filter(wl_row, smooth_window, smooth_order, 0)
    SWL = SWL.flatten()

    # Convert Raman shift (cm^-1) -> scattered wavelength (nm)
    # λ_scattered = 1e7 / (1e7/λ_laser - Δν)
    Cal_wvlength = 1e7 / (1e7 / laser_wavelength - cal_wvn)

    # Fit polynomial from manufacturer-provided true WL reference
    p = utils.lsqpolyfit.lsqpolyfit(wlmax_2col[:, 0], wlmax_2col[:, 1], None, poly_order)

    # Evaluate True WL (lsqpolyval returns (yy, erryy) tuple)
    true_WL, _ = utils.lsqpolyval.lsqpolyval(p, Cal_wvlength)
    true_WL = true_WL.flatten()

    # Find approximate center index
    loc = np.searchsorted(Cal_wvlength, center_wavelength, side="left")
    loc = np.clip(loc, 0, len(Cal_wvlength) - 1)

    # Normalize and compute correction
    NTWL = true_WL / (true_WL[loc] if true_WL[loc] != 0 else 1.0)
    NWL = SWL / (SWL[loc] if SWL[loc] != 0 else 1.0)
    WL_Correction = NTWL / np.where(NWL == 0, 1.0, NWL)

    return _clamp_factor(WL_Correction, cal_wvn).reshape(-1, 1)


def nist_correction_from_srm(
    srm_measured: np.ndarray,
    cal_wvn: np.ndarray,
    coeffs: np.ndarray = None,
    smooth_window: int = 9,
    smooth_order: int = 1,
    center_wvn: float = 1100.0,
    baseline_range: tuple = (10, 25),
    excitation_nm: float = None,
) -> np.ndarray:
    """
    Compute NIST/SRM correction using utils modules.

    Args:
        srm_measured: measured SRM spectrum (N,) or (N,1).
        cal_wvn: wavenumber axis (cm^-1), (N,) or (N,1).
        coeffs: NIST polynomial coefficients, lowest order first. Defaults
            to the SRM 2241 certificate values.
        excitation_nm: Laser wavelength the spectrum was taken at. Only used to
            warn when it does not match what the standard is certified for.
        smooth_window: Savitzky-Golay smoothing window.
        smooth_order: smoothing polynomial order.
        center_wvn: normalization wavenumber.
        baseline_range: tuple defining the baseline subtraction range (start, end).

    Returns:
        correction factor (N, 1) column vector
    """

    if coeffs is None:
        coeffs = SRM2241_785_COEFFS
    # The certificate is written in Raman shift for its own excitation, so the
    # curve only means anything at that excitation.
    if excitation_nm is not None and abs(excitation_nm - SRM2241_EXCITATION_NM) > 1.0:
        warnings.warn(
            f"SRM 2241 is certified for {SRM2241_EXCITATION_NM:g} nm excitation; "
            f"this spectrum was taken at {excitation_nm:g} nm. The relative "
            f"irradiance curve does not transfer between excitations, so the "
            f"correction below is not traceable. Measure a standard certified "
            f"for this laser, or derive the correction in wavelength.",
            UserWarning, stacklevel=2,
        )

    srm_measured = np.asarray(srm_measured, dtype=float).flatten()
    cal_wvn = np.asarray(cal_wvn, dtype=float).flatten()
    coeffs = np.asarray(coeffs, dtype=float).flatten()

    # Baseline correction
    start, end = baseline_range
    if len(srm_measured) >= end:
        baseline = np.mean(srm_measured[start:end])
    else:
        baseline = np.mean(srm_measured)
    SRM_1 = srm_measured - baseline

    # Evaluate true SRM polynomial
    # Using standard polynomial: coeff[0] + coeff[1]*x + coeff[2]*x^2 + ...
    true_SRM = np.polyval(coeffs[::-1], cal_wvn)

    # Normalize and compute correction
    loc = np.searchsorted(cal_wvn, center_wvn, side="left")
    loc = np.clip(loc, 0, len(cal_wvn) - 1)

    NSRM = SRM_1 / (SRM_1[loc] if SRM_1[loc] != 0 else 1.0)
    NTSRM = true_SRM / (true_SRM[loc] if true_SRM[loc] != 0 else 1.0)
    SRM_correction = NTSRM / np.where(NSRM == 0, 1.0, NSRM)

    # Final smoothing
    # savgol_filter expects (m, n) format where m=signals, n=length
    srm_row = SRM_correction.reshape(1, -1)
    SRM_correction, _ = utils.savgol.savgol_filter(srm_row, smooth_window, smooth_order, 0)
    SRM_correction = SRM_correction.flatten()
    return _clamp_factor(SRM_correction, cal_wvn,
                         valid=SRM2241_VALID_RANGE).reshape(-1, 1)

def _clamp_factor(factor, cal_wvn, valid=None, lo=0.0, hi=1e3):
    """Keep a correction factor to values that can be applied.

    The factor is a ratio, so wherever the measured standard crosses zero --
    the detector edges, where it has almost no signal -- it runs away or turns
    negative. Multiplying a spectrum by a negative factor silently flips it.
    Points outside `valid` are outside what the standard certifies at all.

    Runs of bad points at the ends are held at the nearest good value, and any
    interior ones are interpolated across, so the returned factor is finite and
    positive everywhere and the array keeps its length.
    """
    factor = np.asarray(factor, dtype=float).flatten()
    cal_wvn = np.asarray(cal_wvn, dtype=float).flatten()
    good = np.isfinite(factor) & (factor > lo) & (factor < hi)
    if valid is not None and len(cal_wvn) == len(factor):
        good &= (cal_wvn >= valid[0]) & (cal_wvn <= valid[1])
    if not good.any():
        warnings.warn(
            "The correction factor has no usable points: the measured standard "
            "never rises clear of zero. Check that the right file was loaded "
            "and that it matches the calibration axis.",
            UserWarning, stacklevel=2,
        )
        return np.ones_like(factor)
    if not good.all():
        idx = np.arange(len(factor))
        factor = np.interp(idx, idx[good], factor[good])
        warnings.warn(
            f"{int((~good).sum())} of {len(factor)} correction points were not "
            f"usable (non-positive, non-finite, or outside the standard's "
            f"certified range) and were filled from their neighbours.",
            UserWarning, stacklevel=2,
        )
    return factor


def correction_table(cal_wvn, factor):
    """Pair a correction factor with the axis it was derived on.

    Every reference correction file this project has been given is two columns,
    and the pipeline interpolates the factor onto the spectrum by wavenumber.
    A bare column of factors can only be applied by row index, which is correct
    only when the spectrum happens to have been acquired on the identical axis.
    """
    cal_wvn = np.asarray(cal_wvn, dtype=float).flatten()
    factor = np.asarray(factor, dtype=float).flatten()
    n = min(len(cal_wvn), len(factor))
    if len(cal_wvn) != len(factor):
        warnings.warn(
            f"Axis has {len(cal_wvn)} points and the factor {len(factor)}; "
            f"writing the first {n}.", UserWarning, stacklevel=2,
        )
    return np.column_stack((cal_wvn[:n], factor[:n]))
