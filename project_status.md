# Project Status - Raman_APP (TRaP)

Date: 2026-02-23

## Summary
TRaP is a PyQt5 desktop application for standardized Raman spectroscopy processing. It provides a wizard-driven GUI that guides users through configuration, x-axis calibration, spectral response correction, and single/batch spectrum preprocessing. The codebase is organized into UI modules under `UI_utils/` and processing algorithms under `utils/`, with example calibration and sample data included in `data/`.

## Current Capabilities
- Wizard-style workflow with a modern shell and single-instance guard (`TRaP_GUI.py`).
- X-axis calibration using reference spectra and calibration algorithms (`UI_utils/UI_Calibration_v2.py`, `utils/Calibration_v2.py`).
- Spectral response correction (white-light/NIST/precomputed factors) (`UI_utils/UI_SRCF.py`, `utils/WLCorrection.py`).
- Preprocessing pipeline: baseline subtraction, cosmic ray removal, truncation, binning, fluorescence background subtraction, noise smoothing, and normalization (`utils/SpectralPreprocess.py`, `UI_utils/UI_P_Mean_Process.py`, `UI_utils/UI_P_Mean_Batch_Process.py`).
- Single spectrum processing and batch processing UIs (`UI_utils/UI_P_Mean_Process.py`, `UI_utils/UI_P_Mean_Batch_Process.py`).
- Config management with JSON presets (`configs/`, `config.json`, `UI_utils/UI_Config_Manager*.py`).
- Build automation for PyInstaller and Nuitka (`build_exe.py`).

## Project Structure (Key Areas)
- Entry point: `TRaP_GUI.py`.
- UI: `UI_utils/` (wizard, theme, configuration, calibration, processing).
- Algorithms: `utils/` (calibration, preprocessing, filters, I/O in `utils/io/`).
- Data samples: `data/` (calibration files, example spectra).
- Docs: `docs/Document.pdf` (not analyzed in this summary).

## Status Assessment
- Core functionality appears implemented and wired end-to-end via the wizard shell.
- Pipeline order updated: fluorescence background subtraction now precedes noise smoothing in p-mean processing.
- Build script is present and configured to bundle data and resources.
- No automated test suite or CI configuration is present in the repository.

## Known Gaps / Risks
- No tests or CI to validate spectral algorithms or UI flows.
- Requirements are documented in README but not pinned (no `requirements.txt`/`pyproject.toml`).
- `docs/Document.pdf` may contain critical usage or algorithm details; not yet summarized here.

## Suggested Next Steps
1. Add a `requirements.txt` or `pyproject.toml` with pinned versions for reproducibility.
2. Introduce lightweight tests for key utilities (calibration, preprocessing, I/O).
3. Decide whether to keep `__pycache__` and IDE files tracked; consider updating `.gitignore`.
4. Summarize or link `docs/Document.pdf` into the README for easier onboarding.

## Notes
- Build instructions exist in README and `build_exe.py` for PyInstaller/Nuitka packaging.
- The app targets Windows (AppUserModelID handling) but should run cross-platform with PyQt5.
