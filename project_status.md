# Project Status - Raman_APP (TRaP)

Date: 2026-03-04

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
- Core functionality implemented and wired end-to-end via the wizard shell.
- Pipeline order updated: fluorescence background subtraction now precedes noise smoothing in p-mean processing.
- Build script is present and configured to bundle data and resources.
- No automated test suite or CI configuration is present in the repository.

## Recent Changes (2026-03-04 continued)

### Bug Fix — Renishaw X-axis starting from 0 (`UI_P_Mean_Process.py`)
- **Root cause**: `rdata.load_spectrum_data()` always strips column 0 (wavenumber) and returns intensity-only `(N,1)`. The Renishaw load branch used this function and could never recover the wavenumber, falling back to `np.arange(...)`.
- **Fix**: Renishaw branch now uses `rdata.read_txt_file()` which returns the full two-column DataFrame; wavenumber (col 0) and intensity (col 1) are extracted separately.

### Feature — Interactive cursor readout on spectrum plots (`UI_P_Mean_Process.py`)
- Added hover crosshair to both subplots (Current Spectrum + Processing Comparison).
- On mouse move, the cursor snaps to the nearest data point on the X-axis and displays the true `Wvn (cm⁻¹)` and `I` values from the spectrum array.
- Visual elements: dashed vertical line, orange dot marker on the curve, floating tooltip near the data point.
- Tooltip position is adaptive: flips offset direction when the cursor is near the right or top edge of the axes to avoid clipping.
- Elements are hidden when the cursor leaves the axes.

### Bug Fix — White-Light correction 报错 tuple index out of range (`utils/WLCorrection.py`, `UI_utils/UI_SRCF.py`)
- **Bug 1**：`lsqpolyval` 返回 `(yy, erryy)` tuple，原代码直接赋值给 `true_WL` 导致后续索引越界。修复：解包为 `true_WL, _ = lsqpolyval(...)` 并 `.flatten()`。
- **Bug 2**：Raman shift → 散射波长换算公式错误。原代码 `10e-7 / cal_wvn` 结果约 `5e-10`，远超参考文件范围（750–980 nm）。正确公式：`1e7 / (1e7/laser_wavelength - cal_wvn)`。
- **Bug 3**：`UI_SRCF.py` 加载校准文件时未读取激光波长字段。现从 `Cal['Wavelength']` 提取并存入 `self.laser_wavelength`，传入计算函数。默认值保留 785.0 nm 作为兜底。

## Known Gaps / Risks
- No tests or CI to validate spectral algorithms or UI flows.
- Requirements are documented in README but not pinned (no `requirements.txt`/`pyproject.toml`).
- `docs/Document.pdf` may contain critical usage or algorithm details; not yet summarized here.
- Build outputs are generated locally and should not be committed.

## Build Output Hygiene (Do Not Commit)
When running `build_exe.py`, the following artifacts are created locally and should be kept out of version control:
- `build/`
- `dist/`
- `TRaP.spec`

## Suggested Next Steps
1. Add a `requirements.txt` or `pyproject.toml` with pinned versions for reproducibility.
2. Introduce lightweight tests for key utilities (calibration, preprocessing, I/O).
3. Decide whether to keep `__pycache__` and IDE files tracked; consider updating `.gitignore`.
4. Summarize or link `docs/Document.pdf` into the README for easier onboarding.

## Notes
- Build instructions exist in README and `build_exe.py` for PyInstaller/Nuitka packaging.
- The app targets Windows (AppUserModelID handling) but should run cross-platform with PyQt5.
