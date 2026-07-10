# Calibration_v3.py
# -*- coding: utf-8 -*-

"""
X-Axis Calibration Utility v3

Thin extension of the v2 CalibrationProcessor for the v3 UI, where the user
picks reference peaks directly from the Excel-backed reference spectrum
(see utils/XcalReference) instead of by index into the hardcoded library.

The calibration math (subpixel peak finding, polynomial fit, Raman-shift
conversion) is inherited unchanged from CalibrationProcessor — only the source
of the reference wavenumbers differs: they are set explicitly as values rather
than looked up from hardcoded array indices.
"""

import numpy as np

from utils.Calibration_v2 import CalibrationProcessor


class CalibrationProcessorV3(CalibrationProcessor):
    """Calibration processor driven by explicit reference wavenumbers.

    Usage mirrors v2, except reference values are provided directly:
        proc.set_neon_reference_values([11936.58, 11893.14, ...])
        proc.set_neon_spectrum(spectrum)
        proc.set_neon_selected_peaks([px1, px2, ...])   # paired, same order
    """

    def __init__(self):
        super().__init__()
        self._neon_ref_values = np.array([])
        self._acet_ref_values = np.array([])

    # --- Reference wavenumbers set explicitly (from Excel peak selection) ---

    def set_neon_reference_values(self, wavenumbers):
        """Set the Neon-Argon reference wavenumbers (in selection/pairing order)."""
        self._neon_ref_values = np.asarray(wavenumbers, dtype=float).flatten()
        # Keep the inherited count-consistency checks meaningful.
        self.neon_indices = list(range(len(self._neon_ref_values)))
        self.neon_peak_count = len(self._neon_ref_values)

    def set_acet_reference_values(self, wavenumbers):
        """Set the Acetaminophen reference wavenumbers (in selection/pairing order)."""
        self._acet_ref_values = np.asarray(wavenumbers, dtype=float).flatten()
        self.acet_indices = list(range(len(self._acet_ref_values)))
        self.acet_peak_count = len(self._acet_ref_values)

    # --- Override value lookups to use the explicit values ---

    def get_selected_neon_values(self) -> np.ndarray:
        return self._neon_ref_values

    def get_selected_acet_values(self) -> np.ndarray:
        return self._acet_ref_values
