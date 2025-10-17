import numpy as np
import pandas as pd
import os
import utils.savgol, utils.lsqpolyfit, utils.lsqpolyval
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

def read_vector_file(fp: str) -> np.ndarray:
    """Read a 1D vector (txt/csv/xlsx). Returns float array (N,)."""
    ext = os.path.splitext(fp)[1].lower()
    if ext in [".txt", ".csv"]:
        arr = np.loadtxt(fp, delimiter=None)
    elif ext in [".xlsx", ".xls"]:
        df = pd.read_excel(fp, header=None)
        arr = df.values.squeeze()
    else:
        raise ValueError("Unsupported file format for vector.")
    return np.asarray(arr, dtype=float).reshape(-1)


def read_2col_file(fp: str) -> np.ndarray:
    """Read a 2-column table (wavelength, intensity). Returns float array (N, 2)."""
    ext = os.path.splitext(fp)[1].lower()
    if ext in [".txt", ".csv"]:
        arr = np.loadtxt(fp, delimiter=None)
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
        arr = np.loadtxt(fp, delimiter=None)
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
) -> np.ndarray:
    """
    Compute White-Light correction factor using utils modules.

    Args:
        wl_measured: measured white-light spectrum (N,).
        cal_wvn: wavenumber axis (cm^-1), (N,).
        wlmax_2col: (M,2) array: manufacturer-provided True WL [wavelength, intensity].
        smooth_window: window length for Savitzky-Golay filter.
        smooth_order: polynomial order for Savitzky-Golay filter.
        poly_order: polynomial degree for true WL fitting.
        center_wavelength: normalization wavelength.

    Returns:
        correction factor (N,)
    """
    wl_measured = np.asarray(wl_measured, dtype=float).flatten()
    cal_wvn = np.asarray(cal_wvn, dtype=float).flatten()

    # Smooth user-measured White Light Spectrum
    SWL = utils.savgol.savgol_filter(wl_measured, smooth_window, smooth_order, 0)

    # Convert wavenumber (cm^-1) -> wavelength
    Cal_wvlength = 10e-7 / cal_wvn

    # Fit polynomial from manufacturer-provided true WL reference
    p = utils.lsqpolyfit.lsqpolyfit(wlmax_2col[:, 0], wlmax_2col[:, 1], None, poly_order)

    # Evaluate True WL
    true_WL = utils.lsqpolyval.lsqpolyval(p, Cal_wvlength)

    # Find approximate center index
    loc = np.searchsorted(Cal_wvlength, center_wavelength, side="left")
    loc = np.clip(loc, 0, len(Cal_wvlength) - 1)

    # Normalize and compute correction
    NTWL = true_WL / (true_WL[loc] if true_WL[loc] != 0 else 1.0)
    NWL = SWL / (SWL[loc] if SWL[loc] != 0 else 1.0)
    WL_Correction = NTWL / np.where(NWL == 0, 1.0, NWL)

    return WL_Correction.reshape(-1)


def nist_correction_from_srm(
    srm_measured: np.ndarray,
    cal_wvn: np.ndarray,
    coeffs: np.ndarray,
    smooth_window: int = 9,
    smooth_order: int = 1,
    center_wvn: float = 1100.0,
    baseline_range: tuple = (10, 25),
) -> np.ndarray:
    """
    Compute NIST/SRM correction using utils modules.

    Args:
        srm_measured: measured SRM spectrum (N,).
        cal_wvn: wavenumber axis (cm^-1), (N,).
        coeffs: NIST polynomial coefficients.
        smooth_window: Savitzky-Golay smoothing window.
        smooth_order: smoothing polynomial order.
        center_wvn: normalization wavenumber.
        baseline_range: tuple defining the baseline subtraction range (start, end).

    Returns:
        correction factor (N,)
    """
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
    SRM_correction = utils.savgol.savgol_filter(SRM_correction, smooth_window, smooth_order, 0)
    return SRM_correction.reshape(-1)