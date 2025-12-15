# Calibration_v2.py
# -*- coding: utf-8 -*-

"""
X-Axis Calibration Utility v2

Flexible calibration utility that allows:
  - Dynamic selection of library reference values
  - Configurable number of peaks to select
  - Interactive peak selection on plots
  - Support for both known and unknown laser wavelength workflows

All comments in English.
"""

import numpy as np
from scipy.sparse import diags
from scipy.linalg import cholesky, solve
from datetime import datetime

# Import custom utilities
from utils.accuratePeak import accuratepeak2
from utils.lsqpolyfit import lsqpolyfit
from utils.lsqpolyval import lsqpolyval
from utils.savgol import savgol_filter


class ReferenceLibrary:
    """
    Reference library containing standard peak positions for calibration.

    Provides:
    - Neon-Argon emission lines (wavenumbers in cm^-1)
    - Acetaminophen Raman peaks (wavenumbers in cm^-1)
    - Naphthalene Raman peaks (wavenumbers in cm^-1)
    """

    # Neon-Argon emission lines (cm^-1)
    # Index: 0-51
    NEON_ARGON = np.array([
        12947.060, 12946.313, 12581.503, 12476.939, 12372.474, 12322.387,  # 0-5
        12290.439, 12099.913, 12097.637, 12047.720, 11953.502, 11936.584,  # 6-11
        11893.138, 11878.703, 11869.932, 11815.641, 11786.276, 11771.132,  # 12-17
        11735.103, 11703.167, 11666.771, 11639.738, 11581.249, 11554.839,  # 18-23
        11536.761, 11518.188, 11488.823, 11400.360, 11388.716, 11323.865,  # 24-29
        11294.500, 11279.600, 11211.390, 11125.240, 10961.346, 10930.551,  # 30-35
        10781.067, 10762.489, 10751.705, 10722.124, 10690.362, 10668.590,  # 36-41
        10609.652, 10571.707, 10541.096, 10488.601, 10474.056, 10354.340,  # 42-47
        10220.243, 9948.210, 9713.060, 9677.994                            # 48-51
    ])

    # Acetaminophen Raman peaks (cm^-1)
    # Index: 0-21
    ACETAMINOPHEN = np.array([
        3326.6, 3102.4, 3064.6, 2931.1, 1648.4, 1561.5, 1371.5, 1323.9,   # 0-7
        1278.5, 1236.8, 1168.5, 1105.5, 968.7, 857.9, 834.5, 797.2,       # 8-15
        710.8, 651.6, 465.1, 390.9, 329.2, 213.3                          # 16-21
    ])

    # Naphthalene Raman peaks (cm^-1)
    # Index: 0-7
    NAPHTHALENE = np.array([
        3056.4, 1576.6, 1464.5, 1382.2, 1147.2, 1021.6, 763.8, 513.8      # 0-7
    ])

    @classmethod
    def get_library(cls, name: str) -> np.ndarray:
        """Get a copy of the specified library."""
        libraries = {
            'neon': cls.NEON_ARGON.copy(),
            'neon_argon': cls.NEON_ARGON.copy(),
            'acetaminophen': cls.ACETAMINOPHEN.copy(),
            'acet': cls.ACETAMINOPHEN.copy(),
            'naphthalene': cls.NAPHTHALENE.copy(),
            'naph': cls.NAPHTHALENE.copy(),
        }
        return libraries.get(name.lower(), np.array([]))

    @classmethod
    def get_library_with_indices(cls, name: str) -> list:
        """
        Get library values with their indices for UI display.

        Returns:
            List of tuples: [(index, wavenumber), ...]
        """
        lib = cls.get_library(name)
        return [(i, val) for i, val in enumerate(lib)]

    @classmethod
    def get_selected_values(cls, name: str, indices: list) -> np.ndarray:
        """Get library values at specified indices."""
        lib = cls.get_library(name)
        indices = np.array(indices)
        valid = (indices >= 0) & (indices < len(lib))
        return lib[indices[valid]]


class CalibrationProcessor:
    """
    Calibration processor with flexible configuration.

    Supports:
    - Custom library index selection
    - Variable peak counts
    - Both known and unknown wavelength workflows
    """

    def __init__(self):
        """Initialize the calibration processor."""
        # Selected library indices
        self.neon_indices = []
        self.acet_indices = []

        # Peak counts (will match selected indices length)
        self.neon_peak_count = 0
        self.acet_peak_count = 0

        # Spectrum data
        self.neon_spectrum = None
        self.acet_spectrum = None

        # Selected peaks from user interaction
        self.neon_selected_pixels = []
        self.acet_selected_pixels = []

        # Calibration results
        self.polynomial = None
        self.wavenumber_axis = None
        self.laser_wavelength = None

        # Working copy of libraries (modified during processing)
        self._neon_lib = None
        self._acet_lib = None

    def set_neon_library_selection(self, indices: list):
        """
        Set which Neon-Argon library values to use for calibration.

        Args:
            indices: List of indices into the Neon-Argon library
        """
        self.neon_indices = sorted(indices)
        self.neon_peak_count = len(indices)
        self._neon_lib = ReferenceLibrary.NEON_ARGON.copy()

    def set_acet_library_selection(self, indices: list):
        """
        Set which Acetaminophen library values to use for calibration.

        Args:
            indices: List of indices into the Acetaminophen library
        """
        self.acet_indices = sorted(indices)
        self.acet_peak_count = len(indices)
        self._acet_lib = ReferenceLibrary.ACETAMINOPHEN.copy()

    def get_selected_neon_values(self) -> np.ndarray:
        """Get the selected Neon-Argon reference wavenumbers."""
        return ReferenceLibrary.get_selected_values('neon', self.neon_indices)

    def get_selected_acet_values(self) -> np.ndarray:
        """Get the selected Acetaminophen reference wavenumbers."""
        return ReferenceLibrary.get_selected_values('acet', self.acet_indices)

    def set_neon_spectrum(self, spectrum: np.ndarray):
        """Set the measured Neon-Argon spectrum."""
        self.neon_spectrum = self._normalize(spectrum.flatten())

    def set_acet_spectrum(self, spectrum: np.ndarray):
        """Set the measured Acetaminophen spectrum."""
        spectrum = spectrum.flatten()
        baseline = self._baseline_correction(spectrum)
        corrected = spectrum - baseline
        self.acet_spectrum = self._normalize(corrected)

    def set_neon_selected_peaks(self, pixel_positions: list):
        """
        Set the user-selected peak pixel positions for Neon-Argon.

        Args:
            pixel_positions: List of (x, y) tuples or just x values
        """
        if pixel_positions and isinstance(pixel_positions[0], (tuple, list)):
            self.neon_selected_pixels = [int(p[0]) for p in pixel_positions]
        else:
            self.neon_selected_pixels = [int(p) for p in pixel_positions]

    def set_acet_selected_peaks(self, pixel_positions: list):
        """
        Set the user-selected peak pixel positions for Acetaminophen.

        Args:
            pixel_positions: List of (x, y) tuples or just x values
        """
        if pixel_positions and isinstance(pixel_positions[0], (tuple, list)):
            self.acet_selected_pixels = [int(p[0]) for p in pixel_positions]
        else:
            self.acet_selected_pixels = [int(p) for p in pixel_positions]

    def set_known_wavelength(self, wavelength: float):
        """Set the known laser excitation wavelength."""
        self.laser_wavelength = wavelength

    @staticmethod
    def _normalize(data: np.ndarray) -> np.ndarray:
        """Normalize data to [0, 1] range."""
        min_val = np.min(data)
        max_val = np.max(data)
        if max_val - min_val == 0:
            return np.zeros_like(data)
        return (data - min_val) / (max_val - min_val)

    @staticmethod
    def _baseline_correction(spectrum: np.ndarray, lambda_val=1e3, p=1e-5) -> np.ndarray:
        """Asymmetric least squares baseline correction."""
        m = len(spectrum)
        D = diags([1, -2, 1], [0, 1, 2], shape=(m - 2, m))
        w = np.ones(m)
        for _ in range(10):
            w = w.flatten()
            W = diags(w, 0, shape=(m, m))
            temp = W + lambda_val * (D.T @ D).toarray()
            C = cholesky(temp)
            z = solve(C, solve(C.T, W @ spectrum))
            w = p * (spectrum > z) + (1 - p) * (spectrum < z)
        return z

    def _compute_subpixel_peaks(self, spectrum: np.ndarray, peak_pixels: np.ndarray) -> np.ndarray:
        """
        Compute subpixel-accurate peak positions.

        Args:
            spectrum: Normalized spectrum
            peak_pixels: Approximate peak pixel positions

        Returns:
            Array of subpixel peak positions
        """
        # Compute spans using Savitzky-Golay derivative
        y = spectrum.reshape(1, -1)
        z, _ = savgol_filter(y, 5, 1, 1)

        spans = []
        for p in peak_pixels:
            idx = int(p)
            # Find left boundary
            k = idx
            while k > 0 and (z[0, k] - z[0, k - 1]) < 0:
                k -= 1
            kleft = k
            # Find right boundary
            k = idx
            while k < len(z[0]) - 1 and (z[0, k] - z[0, k + 1]) > 0:
                k += 1
            kright = k
            spans.append(kright - kleft)

        spans = np.array(spans)

        # Convert to 1-based indexing for accuratepeak2
        peaks_1based = peak_pixels + 1
        x_axis = np.arange(1, len(spectrum) + 1)

        subpixel = accuratepeak2(x_axis, spectrum.reshape(1, -1), peaks_1based, spans)
        return subpixel

    def calibrate_with_known_wavelength(self) -> np.ndarray:
        """
        Perform calibration when laser wavelength is known.

        Returns:
            Wavenumber axis array
        """
        if self.neon_spectrum is None:
            raise ValueError("Neon spectrum not set")
        if not self.neon_selected_pixels:
            raise ValueError("No Neon peaks selected")
        if self.laser_wavelength is None:
            raise ValueError("Laser wavelength not set")
        if len(self.neon_selected_pixels) != len(self.neon_indices):
            raise ValueError(
                f"Number of selected peaks ({len(self.neon_selected_pixels)}) "
                f"does not match library selection ({len(self.neon_indices)})"
            )

        # Get reference wavenumbers
        ref_wavenumbers = self.get_selected_neon_values()

        # Compute subpixel peak positions
        peak_pixels = np.array(self.neon_selected_pixels)
        subpixel_peaks = self._compute_subpixel_peaks(self.neon_spectrum, peak_pixels)

        # Polynomial fit: pixel -> absolute wavenumber
        P = lsqpolyfit(subpixel_peaks, ref_wavenumbers, None, 3)
        self.polynomial = P

        # Compute absolute wavenumber axis
        pixel_axis = np.arange(1, len(self.neon_spectrum) + 1)
        abs_wvn, _ = lsqpolyval(P, pixel_axis)

        # Convert to Raman shift using known wavelength
        excitation_wvn = 1e7 / self.laser_wavelength
        self.wavenumber_axis = excitation_wvn - abs_wvn.flatten()

        return self.wavenumber_axis

    def calibrate_with_acetaminophen(self) -> np.ndarray:
        """
        Perform calibration when laser wavelength is unknown,
        using Acetaminophen spectrum to estimate it.

        Returns:
            Wavenumber axis array
        """
        if self.neon_spectrum is None:
            raise ValueError("Neon spectrum not set")
        if self.acet_spectrum is None:
            raise ValueError("Acetaminophen spectrum not set")
        if not self.neon_selected_pixels:
            raise ValueError("No Neon peaks selected")
        if not self.acet_selected_pixels:
            raise ValueError("No Acetaminophen peaks selected")
        if len(self.neon_selected_pixels) != len(self.neon_indices):
            raise ValueError("Neon peak count mismatch")
        if len(self.acet_selected_pixels) != len(self.acet_indices):
            raise ValueError("Acetaminophen peak count mismatch")

        # Step 1: Neon calibration for absolute wavenumber
        neon_ref = self.get_selected_neon_values()
        neon_pixels = np.array(self.neon_selected_pixels)
        neon_subpixel = self._compute_subpixel_peaks(self.neon_spectrum, neon_pixels)

        P = lsqpolyfit(neon_subpixel, neon_ref, None, 3)
        self.polynomial = P

        # Step 2: Use Acetaminophen to estimate wavelength
        acet_ref = self.get_selected_acet_values()
        acet_pixels = np.array(self.acet_selected_pixels)
        acet_subpixel = self._compute_subpixel_peaks(self.acet_spectrum, acet_pixels)

        # Calculate wavelength for each Acetaminophen peak
        acet_abs_wvn, _ = lsqpolyval(P, acet_subpixel)
        acet_abs_wvn = acet_abs_wvn.flatten()

        # λ = 1e7 / (abs_wvn + raman_shift)
        wavelengths = 1e7 / (acet_abs_wvn + acet_ref)
        self.laser_wavelength = np.mean(wavelengths)

        # Step 3: Compute final wavenumber axis
        pixel_axis = np.arange(1, len(self.neon_spectrum) + 1)
        abs_wvn, _ = lsqpolyval(P, pixel_axis)

        excitation_wvn = 1e7 / self.laser_wavelength
        self.wavenumber_axis = excitation_wvn - abs_wvn.flatten()

        return self.wavenumber_axis

    def get_calibration_result(self) -> dict:
        """
        Get calibration results as a dictionary.

        Returns:
            Dictionary containing calibration data suitable for saving
        """
        return {
            'Wvn': self.wavenumber_axis.reshape(-1, 1) if self.wavenumber_axis is not None else None,
            'Wavelength': self.laser_wavelength,
            'Polynomial': self.polynomial,
            'CalibrationDate': datetime.now().strftime("%Y-%m-%d"),
            'CalibrationTime': datetime.now().strftime("%H:%M:%S"),
            'NeonIndices': self.neon_indices,
            'AcetIndices': self.acet_indices,
            'NeonPeakPixels': self.neon_selected_pixels,
            'AcetPeakPixels': self.acet_selected_pixels,
        }

    def get_calibration_error(self) -> dict:
        """
        Calculate calibration fitting error.

        Returns:
            Dictionary with error statistics
        """
        if self.polynomial is None:
            return {}

        # Neon error
        neon_ref = self.get_selected_neon_values()
        neon_pixels = np.array(self.neon_selected_pixels)
        neon_subpixel = self._compute_subpixel_peaks(self.neon_spectrum, neon_pixels)
        neon_fitted, _ = lsqpolyval(self.polynomial, neon_subpixel)
        neon_error = neon_fitted.flatten() - neon_ref

        result = {
            'neon_error': neon_error,
            'neon_mean_abs_error': np.mean(np.abs(neon_error)),
            'neon_max_error': np.max(np.abs(neon_error)),
        }

        # Acetaminophen error (if used)
        if self.acet_selected_pixels and self.acet_spectrum is not None:
            acet_ref = self.get_selected_acet_values()
            acet_pixels = np.array(self.acet_selected_pixels)
            acet_subpixel = self._compute_subpixel_peaks(self.acet_spectrum, acet_pixels)
            acet_abs, _ = lsqpolyval(self.polynomial, acet_subpixel)

            # Wavelength consistency
            wavelengths = 1e7 / (acet_abs.flatten() + acet_ref)
            result['wavelength_estimates'] = wavelengths
            result['wavelength_std'] = np.std(wavelengths)

        return result


# Convenience function for quick calibration
def quick_calibrate(
    neon_spectrum: np.ndarray,
    neon_peaks: list,
    neon_library_indices: list,
    laser_wavelength: float = None,
    acet_spectrum: np.ndarray = None,
    acet_peaks: list = None,
    acet_library_indices: list = None
) -> np.ndarray:
    """
    Quick calibration function.

    Args:
        neon_spectrum: Measured Neon-Argon spectrum
        neon_peaks: Selected peak pixel positions
        neon_library_indices: Indices into Neon-Argon library
        laser_wavelength: Known laser wavelength (if available)
        acet_spectrum: Acetaminophen spectrum (if wavelength unknown)
        acet_peaks: Acetaminophen peak positions (if wavelength unknown)
        acet_library_indices: Indices into Acetaminophen library

    Returns:
        Wavenumber axis array
    """
    proc = CalibrationProcessor()
    proc.set_neon_library_selection(neon_library_indices)
    proc.set_neon_spectrum(neon_spectrum)
    proc.set_neon_selected_peaks(neon_peaks)

    if laser_wavelength is not None:
        proc.set_known_wavelength(laser_wavelength)
        return proc.calibrate_with_known_wavelength()
    else:
        if acet_spectrum is None or acet_peaks is None or acet_library_indices is None:
            raise ValueError("Acetaminophen data required when wavelength is unknown")
        proc.set_acet_library_selection(acet_library_indices)
        proc.set_acet_spectrum(acet_spectrum)
        proc.set_acet_selected_peaks(acet_peaks)
        return proc.calibrate_with_acetaminophen()
