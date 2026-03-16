# TRaP - Raman Spectroscopy Processing Application

A standardized Raman spectroscopy data processing tool with a wizard-style GUI, built with PyQt5.

Developed at **Vanderbilt Biophotonics Center**.

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
| System | Cart, Renishaw, Portable, MANTIS |
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

## Contact

- **Email**: yanfan.zhu@vanderbilt.edu
- **GitHub**: [ZhaishenGForSaken](https://github.com/ZhaishenGForSaken)
