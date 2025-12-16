# TRaP_App

A Standardized Raman Spectroscopy Processing Application with GUI

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Workflow Overview](#workflow-overview)
- [Step-by-Step Guide](#step-by-step-guide)
  - [Step 0: Configuration Manager](#step-0-configuration-manager)
  - [Step 1: X-Axis Calibration](#step-1-x-axis-calibration)
  - [Step 2: Spectral Response Correction](#step-2-spectral-response-correction)
  - [Step 3: Single Spectrum Processing](#step-3-single-spectrum-processing)
  - [Step 4: Batch Processing](#step-4-batch-processing)
- [File Format Specifications](#file-format-specifications)
- [Processing Parameters](#processing-parameters)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [Contact](#contact)

---

## Overview

TRaP_App is a PyQt5-based application for processing Raman spectroscopy data through a complete calibration and preprocessing pipeline. It provides a wizard-style interface that guides users through each step of the workflow.

---

## Features

- 5-step wizard workflow for complete spectrum processing
- X-axis calibration using Neon-Argon and Acetaminophen references
- White-Light and NIST SRM spectral response correction
- Comprehensive preprocessing pipeline (baseline, denoising, binning, normalization)
- Batch processing for multiple files
- Configuration management with save/load functionality
- Real-time visualization and before/after comparison
- Dark theme modern UI with animations

---

## Installation

### Prerequisites

- Python 3.8+

### Install Dependencies

```bash
pip install PyQt5 numpy pandas scipy matplotlib openpyxl
```

### Run Application

```bash
python TRaP_GUI.py
```

---

## Workflow Overview

```
Step 0: Config Manager
    |
    v
Step 1: X-Axis Calibration  -->  calibration.mat
    |
    v
Step 2: Spectral Response Correction  -->  correction factor
    |
    v
Step 3: Single Spectrum Processing  -->  processed spectrum
    or
Step 4: Batch Processing  -->  multiple processed spectra
```

---

## Step-by-Step Guide

### Step 0: Configuration Manager

**Purpose**: Configure instrument and system parameters.

#### Input Files

| File Type | Format | Required |
|-----------|--------|----------|
| Existing Config | `.json` | No (optional) |

#### Output Files

| File Type | Format | Location |
|-----------|--------|----------|
| Configuration | `.json` | `configs/` directory |

#### Configuration File Format

```json
{
    "Name": "MyExperiment",
    "System": "Cart",
    "Exc Wavelength": "785",
    "Detector": "256br",
    "Probe": "Microscope",
    "CCD X": 0.0,
    "CCD Y": 0.0,
    "Raman Shift Range": "Fingerprint",
    "Last Modified": "2025-12-15"
}
```

| Parameter | Options |
|-----------|---------|
| System | `Cart`, `Renishaw`, `Portable`, `MANTIS` |
| Exc Wavelength | `785`, `680`, `830`, `730` (nm) |
| Detector | `256br`, `400br`, `Blaze`, `Kaiser` |
| Probe | `Microscope`, `Handheld`, `Lensed`, `SORS`, `Classic` |
| Raman Shift Range | `Fingerprint`, `High WVN`, `Full Range`, `Custom` |

---

### Step 1: X-Axis Calibration

**Purpose**: Calibrate the wavenumber axis using reference emission spectra.

#### Two Calibration Paths

1. **Known Wavelength**: Neon-Argon spectrum + known laser wavelength
2. **Unknown Wavelength**: Neon-Argon + Acetaminophen spectra

#### Input Files

| File Type | Format | Content | Required |
|-----------|--------|---------|----------|
| Neon-Argon Spectrum | `.txt`, `.csv`, `.xlsx` | Intensity values (single column) | Yes |
| Acetaminophen Spectrum | `.txt`, `.csv`, `.xlsx` | Intensity values (single column) | Only for unknown wavelength |

#### Input File Format Examples

**Format A: Single Column (Intensity Only)** - RECOMMENDED
```
1523.45
1498.32
1512.67
1534.89
1567.23
...
```

**Format B: Two Columns (Index/Pixel, Intensity)**
```
1,1523.45
2,1498.32
3,1512.67
4,1534.89
5,1567.23
...
```

**Format C: Tab/Space Delimited**
```
1523.45
1498.32
1512.67
1534.89
```

#### Output Files

| File Type | Format | Content |
|-----------|--------|---------|
| Calibration Result | `.mat` | MATLAB binary with wavenumber array |

#### Output File Structure (.mat)

```matlab
Cal.Wvn          % [N x 1] Wavenumber axis in cm^-1 (REQUIRED)
Cal.Error        % Fitting error (optional)
Cal.Coefficients % Polynomial coefficients (optional)
```

#### Reference Libraries

| Library | Peak Count | Range (cm^-1) |
|---------|------------|---------------|
| Neon-Argon | 52 emission lines | 9678 - 12947 |
| Acetaminophen | 22 Raman peaks | 213 - 3327 |
| Naphthalene | 8 Raman peaks | 514 - 3056 |

---

### Step 2: Spectral Response Correction

**Purpose**: Correct for instrument spectral response.

#### Three Methods

1. **White-Light Correction**: Measured WL spectrum + manufacturer reference
2. **NIST SRM Correction**: NIST standard reference (built-in coefficients)
3. **Load Existing Factor**: Pre-computed correction file

#### Input Files

| File Type | Format | Content | Required |
|-----------|--------|---------|----------|
| Calibration File | `.mat` | From Step 1 (wavenumber axis) | Yes |
| WL/SRM Spectrum | `.txt`, `.csv`, `.xlsx` | Measured reference (single column) | Yes (Method 1/2) |
| True WL Reference | `.txt`, `.csv`, `.xlsx` | 2-column: wavelength, intensity | Method 1 only |
| Existing Correction | `.txt`, `.csv`, `.npy` | Pre-computed factor | Method 3 only |

#### Input File Format: White-Light Spectrum (Single Column)

```
0.8523
0.8634
0.8712
0.8856
0.8934
...
```

#### Input File Format: True WL Reference (Two Columns)

```
wavelength_nm,intensity
700.0,0.245
710.0,0.312
720.0,0.389
730.0,0.456
...
```

Or tab/space delimited:
```
700.0   0.245
710.0   0.312
720.0   0.389
```

#### Output

| Output | Format |
|--------|--------|
| Correction Factor | NumPy array (N, 1) |

---

### Step 3: Single Spectrum Processing

**Purpose**: Process a single spectrum through the complete pipeline.

#### Processing Pipeline

| Step | Operation | Description |
|------|-----------|-------------|
| 1 | Baseline Subtraction | Remove minimum intensity offset |
| 2 | Spectral Response Correction | Apply correction factor |
| 3 | Cosmic Ray Removal | Detect and remove spike noise |
| 4 | Truncation | Extract wavenumber range (default: 900-1700 cm^-1) |
| 5 | Binning | Rebin to uniform spacing (default: 3.5 cm^-1) |
| 6 | Denoising | Savitzky-Golay filter |
| 7 | Fluorescence Background | Polynomial baseline subtraction |
| 8 | Normalization | Scale to mean intensity |

#### Input Files

| File Type | Format | Content | Required |
|-----------|--------|---------|----------|
| Raw Spectrum | `.txt`, `.csv`, `.xlsx` | Intensity values (single column) | Yes |
| Calibration File | `.mat` | Wavenumber axis from Step 1 | Yes |
| WL Correction | `.txt`, `.csv` | Correction factor from Step 2 | Yes |
| Config File | `.json` | Processing parameters | No |

#### Input File Format: Raw Spectrum

**Single Column (Intensity Only)** - RECOMMENDED
```
1523.45
1498.32
1512.67
1534.89
1567.23
...
```

**Two Columns (Wavenumber, Intensity)**
```
900.0,1523.45
903.5,1498.32
907.0,1512.67
910.5,1534.89
914.0,1567.23
...
```

#### Output Files

| File Type | Format | Content |
|-----------|--------|---------|
| Processed Spectrum | `.txt` | Two columns: wavenumber, intensity |

#### Output File Format

```
# Wavenumber,SpectralIntensity
900.0,0.0523
903.5,0.0612
907.0,0.0589
910.5,0.0634
914.0,0.0701
...
```

---

### Step 4: Batch Processing

**Purpose**: Process multiple spectrum files automatically.

#### Input Files

| File Type | Format | Content | Required |
|-----------|--------|---------|----------|
| Multiple Raw Spectra | `.txt`, `.csv` | Intensity values | Yes |
| Calibration File | `.mat` | Single file for all spectra | Yes |
| WL Correction | `.txt`, `.csv` | Single file for all spectra | Yes |
| Processing Config | `.json` | Batch parameters | No |

#### Output Files

| File Type | Format | Location |
|-----------|--------|----------|
| Processed Spectra | `.txt` | Output folder or alongside inputs |

#### Output Filename Convention

```
{original_filename}_BatchPMean_Start{X}_Stop{Y}_P{Z}_DN{Method}_BW{W}_{timestamp}.txt
```

Example:
```
sample001_BatchPMean_Start900_Stop1700_P7_DNSavitzky-Golay_BW3.5_20251215_143022.txt
```

---

## File Format Specifications

### Supported Input Formats

| Extension | Delimiter | Notes |
|-----------|-----------|-------|
| `.txt` | Auto-detect (tab, space, comma) | Most common |
| `.csv` | Comma | Standard CSV |
| `.xlsx` / `.xls` | N/A | Excel (first sheet, no header) |
| `.mat` | N/A | MATLAB binary (calibration only) |

### Data Array Dimensions

All spectrum data is processed as **column vectors (N, 1)**:

| Input Shape | Handling |
|-------------|----------|
| (N,) | Reshaped to (N, 1) |
| (N, 1) | Used directly |
| (N, 2) | Second column extracted |
| (N, M) where M > 2 | Mean of columns 2+ |

### Quick Reference: Files by Step

| Step | Input Files | Input Format | Output |
|------|-------------|--------------|--------|
| 0 - Config | None or .json | JSON | config.json |
| 1 - Calibration | Neon-Argon spectrum | TXT/CSV/XLSX (1 col) | calibration.mat |
| 2 - Correction | Calibration + WL spectrum | MAT + TXT/CSV (1 col) | correction factor |
| 3 - Process | Spectrum + Cal + Correction | TXT + MAT + TXT | processed.txt |
| 4 - Batch | Spectra[] + Cal + Correction | TXT[] + MAT + TXT | processed[].txt |

---

## Processing Parameters

### Processing Config Format

```json
{
    "Start": 900,
    "Stop": 1700,
    "Polyorder": 7,
    "DenoiseMethod": "Savitzky-Golay",
    "BinWidth": 3.5,
    "SGorder": 2,
    "SGframe": 7,
    "MAWindow": 5,
    "MedianKernel": 5
}
```

### Parameter Descriptions

| Parameter | Default | Description |
|-----------|---------|-------------|
| Start | 900 | Truncation start (cm^-1) |
| Stop | 1700 | Truncation end (cm^-1) |
| Polyorder | 7 | Baseline polynomial order |
| BinWidth | 3.5 | Binning width (cm^-1) |

### Denoising Methods

| Method | Parameters |
|--------|------------|
| Savitzky-Golay | SGorder (2), SGframe (7, must be odd >= 3) |
| Moving Average | MAWindow (5) |
| Median Filter | MedianKernel (5, must be odd) |
| None | - |

---

## Project Structure

```
TRaP_App/
|-- TRaP_GUI.py                    # Main entry point
|-- README.md                      # This documentation
|-- config.json                    # Current session config
|
|-- UI_utils/                      # User Interface modules
|   |-- UI_wizard_v2.py           # Main wizard orchestrator
|   |-- UI_Config_Manager_v2.py   # Configuration management
|   |-- UI_Calibration_v2.py      # X-axis calibration
|   |-- UI_SRCF.py                # Spectral response correction
|   |-- UI_P_Mean_Process.py      # Single spectrum processing
|   |-- UI_P_Mean_Batch_Process.py # Batch processing
|
|-- utils/                         # Processing modules
|   |-- Calibration_v2.py         # Calibration algorithms
|   |-- SpectralPreprocess.py     # Processing pipeline
|   |-- WLCorrection.py           # Correction algorithms
|   |-- io/
|   |   |-- rdata.py              # File reading utilities
|   |   |-- wdata.py              # File writing utilities
|   |-- accuratePeak.py           # Peak finding
|   |-- lsqpolyfit.py             # Polynomial fitting
|   |-- savgol.py                 # Savitzky-Golay filter
|
|-- configs/                       # Configuration storage
|-- data/                          # Example data
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Calibration file not found" | Complete Step 1 and save .mat file |
| "Array dimension mismatch" | Verify spectrum length matches calibration |
| "Invalid file format" | Use .txt, .csv, .xlsx, or .mat |
| "SGframe must be odd >= 3" | Use odd number >= 3 for SG frame |

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/YourFeature`
3. Commit changes: `git commit -m "Add feature"`
4. Push: `git push origin feature/YourFeature`
5. Open a Pull Request

---

## Contact

- **Email**: [yanfan.zhu@vanderbilt.edu](mailto:yanfan.zhu@vanderbilt.edu)
- **GitHub**: [ZhaishenGForSaken](https://github.com/ZhaishenGForSaken)

Vanderbilt Biophotonics Center
