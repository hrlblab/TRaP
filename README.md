# TRaP: An open-source, reproducible framework for Raman spectral processing across heterogeneous systems

Developed at **Vanderbilt University**.

## Features

- **5-step wizard workflow** guiding users through the complete processing pipeline
- **X-axis calibration** using Neon-Argon and Acetaminophen reference spectra
- **Spectral response correction** via White-Light, NIST SRM, or pre-computed factors
- **Full preprocessing pipeline**: baseline subtraction, SRC, truncation, binning, noise smoothing (SG / MA / Median), fluorescence background subtraction, and normalization
- **Configurable pipeline parameters**: truncation range, bin width, FBS polynomial order and max iterations, normalization method (Mean / Max / Area), and smoothing settings
- **Detector auto-fill**: selecting a detector model pre-fills CCD spectral and spatial pixel dimensions
- **Spectrum Batch Processing** for multiple spectrum files with shared configuration
- **Configuration persistence**: save/load JSON config files with field validation
- **Interactive cursor** on processing plots: snaps to nearest data point and displays wavenumber and intensity
- **Real-time visualization** with before/after dual-panel comparison
- **Modern dark-themed UI** with smooth animations

## Quick Start

### Requirements

- Python 3.8+

### Install & Run

```bash
pip install PyQt5 numpy pandas scipy matplotlib openpyxl
python TRaP_GUI.py
```

## Workflow

```
Step 0: Configuration Manager
       Configure instrument & system parameters
                    |
Step 1: X-Axis Calibration
       Neon-Argon + known/unknown laser wavelength  -->  calibration.mat
                    |
Step 2: Spectral Response Correction
       White-Light / NIST SRM / existing factor  -->  correction factor
                    |
Step 3: Spectrum Processing           \
       or                              }--> processed spectra (.txt)
Step 4: Spectrum Batch Processing     /
```

### Processing Pipeline (Steps 3 & 4)

| Order | Operation | Description |
|-------|-----------|-------------|
| 1 | Baseline Subtraction | Remove minimum intensity offset |
| 2 | Spectral Response Correction | Apply correction factor from Step 2 |
| 3 | Cosmic Ray Removal | Reserved placeholder for future integration |
| 4 | Truncation | Extract wavenumber range of interest |
| 5 | Binning | Rebin to uniform wavenumber spacing |
| 6 | Noise Smoothing | Savitzky-Golay / Moving Average / Median filter |
| 7 | Fluorescence Background | Iterative polynomial baseline subtraction |
| 8 | Normalization | Scale spectrum by mean / max / area |

## Supported File Formats

| Extension | Notes |
|-----------|-------|
| `.txt` | Auto-detect delimiter (tab, space, comma) |
| `.csv` | Standard CSV |
| `.xlsx` / `.xls` | Excel (first sheet) |
| `.mat` | MATLAB binary (calibration files) |

## Configuration

System parameters are stored as JSON:

```json
{
    "Name": "MyExperiment",
    "System": "Cart",
    "Exc Wavelength": "785",
    "Detector": "256br",
    "Probe": "Microscope",
    "Raman Shift Range": "Fingerprint"
}
```

| Parameter | Options |
|-----------|---------|
| System | Cart, Renishaw, Portable |
| Exc Wavelength | 785, 680, 830, 730 (nm) |
| Detector | 256br, 400br, Blaze, Kaiser |
| Probe | Microscope, Handheld, Lensed, SORS, Classic |
| Raman Shift Range | Fingerprint, High WVN, Full Range, Custom |

## Project Structure

```
TRaP_App/
|-- TRaP_GUI.py                       # Main entry point
|-- build_exe.py                      # Build automation (PyInstaller / Nuitka)
|
|-- UI_utils/                         # GUI modules
|   |-- UI_wizard_v2.py              # Wizard orchestrator with navigation shell
|   |-- UI_Config_Manager.py         # Configuration management
|   |-- UI_Calibration_v2.py         # X-axis calibration UI
|   |-- UI_SRCF.py                   # Spectral response correction UI
|   |-- UI_P_Mean_Process.py         # Single spectrum processing UI
|   |-- UI_P_Mean_Batch_Process.py   # Batch processing UI
|   |-- UI_theme.py                  # Dark theme styling
|
|-- utils/                            # Processing & algorithm modules
|   |-- Calibration_v2.py            # Calibration algorithms
|   |-- SpectralPreprocess.py        # Processing pipeline
|   |-- WLCorrection.py              # White-Light / NIST correction
|   |-- io/rdata.py, wdata.py        # File I/O with format auto-detection
|   |-- accuratePeak.py              # Peak detection
|   |-- savgol.py                    # Savitzky-Golay filter
|   |-- spectralBin.py              # Spectral binning
|   |-- lsqpolyfit.py / lsqpolyval.py  # Polynomial fitting
```

## Build Standalone Executable

```bash
pip install pyinstaller
python build_exe.py              # PyInstaller (default)
python build_exe.py nuitka       # Nuitka (alternative)
```

Output: `dist/TRaP/TRaP.exe`

## Changelog

### v1.0.5 — 2026-07-13

**New Features**
- **Save non-normalized intensities alongside normalized**: Processed spectra are now saved with an extra `Intensity_NoNorm` / `SpectralIntensity_NoNorm` column holding the fully processed spectrum *before* the normalization step. This applies to both single-spectrum "Save Data" (`Wavenumber, Intensity, Intensity_NoNorm`) and batch output files (`Wavenumber, SpectralIntensity, SpectralIntensity_NoNorm`). On-screen preview and comparison plots are unchanged (still normalized).

**Internal**
- `utils/ProcessingPipeline.py` `run_pipeline()` gains a `return_prenorm` flag that additionally returns the pre-normalization spectrum. The default 2-tuple return is unchanged, so existing callers are unaffected.

---

### v1.0.4 — 2026-07-10

**New Features**
- **Redesigned X-axis calibration (v3)**: The calibration step now shows three parts at once — your input spectrum (top) and the library reference spectrum (bottom) stacked for visual pattern comparison, plus a reference peak library on the right. Commonly-used peaks are always marked; all peaks are selectable. Pairing is explicit: activate a reference peak (click it on the reference spectrum or the library list), then click the matching peak on your input spectrum to form one (reference wavenumber ↔ input pixel) pair. A moving crosshair with a live coordinate readout tracks the cursor on both spectra.
- **Excel-backed reference data**: Reference spectra and peak lists (with per-peak spectral indices) are loaded from `data/TRaP Xcal Data.xlsx`, covering Ne-Ar (785/830 nm) and Acetaminophen (Fingerprint / High Wavenumber). The correct reference is auto-selected from the configured excitation wavelength and Raman shift range, with a dropdown to override.

**Notes**
- The v3 calibration UI (`UI_Calibration_v3.py`, `Calibration_v3.py`, `XcalReference.py`) reuses the v2 calibration math unchanged. The previous v2 UI is retained in the codebase.

---

### v1.0.3 — 2026-07-06

**New Features**
- **Real-time processing preview**: In single-spectrum processing, changing any parameter now re-runs the entire pipeline from the raw data and refreshes the result automatically — no button press needed. Because the whole chain is replayed from the untouched raw spectrum, every preceding and following step updates together. Edits are debounced (300 ms) so rapid typing does not thrash the computation.

**Refactor**
- **Unified pipeline module**: The P-Mean preprocessing chain now lives in a single source of truth, `utils/ProcessingPipeline.py` (`run_pipeline()`), shared by both single-spectrum and batch processing. This guarantees interactive preview and batch output stay byte-for-byte identical and removes ~80 lines of duplicated logic from the batch UI.

---

### v1.0.2 — 2026-06-04

**Bug Fixes**
- **Calibration file compatibility**: `.mat` files generated by external systems (e.g., MATLAB) are now loaded correctly even when the top-level struct key is not `Cal` (e.g., `Cal_HW`). Both the SRCF loader and the P Mean `getwvnfrompath()` path are fixed.
- **Calibration UI crash on "Clear Selected Peaks"**: Calling `ax.clear()` detached crosshair artists before `_init_crosshair()` tried to remove them, raising `ValueError: Failed to remove artist` and closing the application. Fixed by nullifying crosshair references before `ax.clear()`.
- **Neon-Argon peaks persisting into Acetaminophen step**: The crash above prevented `selected_points` from being reset, leaving stale neon peaks visible when advancing to the acetaminophen selection step. Fixed as part of the same change.

**New Features**
- **Raman Shift Range → truncation range linkage**: Selecting a range mode in Config Manager now auto-fills Start/Stop in P Mean and Batch Processing on data load. Defaults: Fingerprint 900–1800 cm⁻¹, High WVN 2000–3200 cm⁻¹, Full Range 100–4000 cm⁻¹. Custom mode leaves user values unchanged and fields remain editable at any time.

---

### v1.0.1 — 2026-06-04

**New Features**
- **Light theme**: Added `LightColors` palette and `get_light_stylesheet()` in `UI_theme.py`. All UI modules now use `get_current_colors()` for theme-aware styling instead of hardcoded `Colors.*` references.

**Other**
- MANTIS system temporarily disabled in Config Manager.
- Removed unused `Cal230806.mat` calibration file.

---

### v1.0.0 — 2026-04-05

Initial public release.

## Contact

- **Email**: yanfan.zhu@vanderbilt.edu
- **GitHub**: [ZhaishenGForSaken](https://github.com/ZhaishenGForSaken)
