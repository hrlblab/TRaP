# UI_Calibration_v3.py
# -*- coding: utf-8 -*-

"""
X-Axis Calibration UI v3

Three-part interface:
  1. Input spectrum (top canvas)     - the user's uploaded spectrum; click to
                                        pick the peak that matches the active
                                        reference peak.
  2. Reference spectrum (bottom canvas) - the library reference curve with
                                        commonly-used peaks always marked and all
                                        peaks selectable; click a peak to activate
                                        it for pairing.
  3. Reference peak library (right list) - all reference peaks; common ones
                                        flagged; click a row to activate; shows
                                        pairing status.

Input and reference spectra are stacked top/bottom so their peak patterns can be
compared vertically. Pairing is explicit: activate a reference peak, then click
the matching peak on the input spectrum to form one (reference wavenumber <->
input pixel) pair.

Reference data comes from utils/XcalReference (Excel-backed). Calibration math is
reused from Calibration_v3 / v2 unchanged.
"""

import os
import sys
import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QDialog, QWidget, QLabel, QPushButton, QComboBox,
    QVBoxLayout, QHBoxLayout, QGridLayout, QFileDialog, QMessageBox,
    QListWidget, QListWidgetItem, QGroupBox, QSplitter, QFrame, QScrollArea,
    QDoubleSpinBox, QProgressBar, QStatusBar, QSizePolicy, QStackedWidget
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QColor

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from scipy.io import savemat

from utils.XcalReference import XcalReference
from utils.Calibration_v3 import CalibrationProcessorV3
from UI_utils.UI_Calibration_v2 import load_spectrum_file
from UI_utils.UI_theme import get_current_stylesheet, get_current_colors, Fonts


def _C():
    return get_current_colors()


# ----------------------------------------------------------------------------
# Input spectrum canvas: click to pick input peaks (snaps to local maximum)
# ----------------------------------------------------------------------------
class InputSpectrumCanvas(FigureCanvas):
    """Top canvas — the user's uploaded spectrum. Click picks a peak for the
    currently active reference peak (snaps to nearest local maximum)."""

    input_peak_picked = pyqtSignal(int, float)  # (pixel, intensity)

    def __init__(self, parent=None):
        self.fig = Figure(figsize=(6, 2.6), dpi=100)
        self.fig.set_facecolor(_C().BG_SECONDARY)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(140)

        self.spectrum = None
        self.norm = None
        self.selection_enabled = False
        self._pairs = []  # list of dicts with 'input_pixel' and 'num'

        # Crosshair tracking (red cross + coordinate readout), as in v2
        self.crosshair_v = None
        self.crosshair_h = None
        self.coord_text = None

        self.mpl_connect('button_press_event', self._on_click)
        self.mpl_connect('motion_notify_event', self._on_mouse_move)
        self.mpl_connect('axes_leave_event', self._on_mouse_leave)
        self._style()
        self.fig.tight_layout(pad=1.5)
        self.draw()

    def _style(self):
        self.ax.set_facecolor(_C().BG_TERTIARY)
        self.ax.grid(True, alpha=0.2, linestyle='--', color=_C().BORDER)
        self.ax.tick_params(labelsize=8, colors=_C().TEXT_SECONDARY)
        for s in self.ax.spines.values():
            s.set_color(_C().BORDER)

    def _init_crosshair(self):
        """Create (invisible) crosshair lines and coordinate text after a redraw."""
        self.crosshair_v = self.ax.axvline(x=0, color=_C().DANGER, linewidth=1,
                                            linestyle='--', alpha=0.8, visible=False)
        self.crosshair_h = self.ax.axhline(y=0, color=_C().DANGER, linewidth=1,
                                            linestyle='--', alpha=0.8, visible=False)
        self.coord_text = self.ax.text(
            0.02, 0.98, '', transform=self.ax.transAxes, fontsize=8,
            verticalalignment='top', fontfamily='monospace', color=_C().TEXT_PRIMARY,
            bbox=dict(boxstyle='round,pad=0.4', facecolor=_C().BG_DARK,
                      edgecolor=_C().PRIMARY, alpha=0.9), visible=False)

    def _on_mouse_move(self, event):
        if self.spectrum is None or self.crosshair_v is None:
            return
        if event.inaxes != self.ax or event.xdata is None:
            return
        pixel = int(round(event.xdata))
        if 0 <= pixel < len(self.spectrum):
            self.crosshair_v.set_xdata([pixel, pixel])
            self.crosshair_h.set_ydata([self.norm[pixel], self.norm[pixel]])
            self.crosshair_v.set_visible(True)
            self.crosshair_h.set_visible(True)
            self.coord_text.set_text(f'Pixel: {pixel}\nInt:   {self.spectrum[pixel]:.2f}')
            self.coord_text.set_visible(True)
            self.draw_idle()

    def _on_mouse_leave(self, event):
        for artist in (self.crosshair_v, self.crosshair_h, self.coord_text):
            if artist is not None:
                artist.set_visible(False)
        self.draw_idle()

    def load_spectrum(self, spectrum):
        self.spectrum = np.asarray(spectrum, dtype=float).flatten()
        lo, hi = float(np.min(self.spectrum)), float(np.max(self.spectrum))
        self.norm = (self.spectrum - lo) / (hi - lo) if hi > lo else self.spectrum * 0
        self._pairs = []
        self._redraw()

    def enable_selection(self, enabled=True):
        self.selection_enabled = enabled

    def set_pairs(self, pairs):
        """pairs: list of dicts each with 'input_pixel' and 'num' (label)."""
        self._pairs = [p for p in pairs if p.get('input_pixel') is not None]
        self._redraw()

    def _redraw(self):
        # Nullify crosshair refs before ax.clear() detaches them (avoids the
        # "Failed to remove artist" crash seen in v2).
        self.crosshair_v = None
        self.crosshair_h = None
        self.coord_text = None
        self.ax.clear()
        self._style()
        if self.norm is None:
            self.draw()
            return
        self.ax.plot(self.norm, color=_C().PRIMARY, linewidth=1.0)
        self.ax.set_title("Input Spectrum (click matching peak)",
                          fontsize=10, fontweight='bold', color=_C().TEXT_PRIMARY)
        self.ax.set_xlabel("Pixel", fontsize=8, color=_C().TEXT_SECONDARY)
        self.ax.set_ylabel("Norm. Intensity", fontsize=8, color=_C().TEXT_SECONDARY)
        for p in self._pairs:
            px = p['input_pixel']
            if 0 <= px < len(self.norm):
                self.ax.plot(px, self.norm[px], 'o', color=_C().DANGER,
                             markersize=9, markeredgecolor='white', markeredgewidth=1.5)
                self.ax.annotate(str(p['num']), (px, self.norm[px]),
                                 textcoords="offset points", xytext=(0, 10),
                                 ha='center', fontsize=8, fontweight='bold',
                                 color=_C().DANGER,
                                 bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                                           edgecolor=_C().DANGER, alpha=0.9))
        self._init_crosshair()
        self.fig.tight_layout(pad=1.5)
        self.draw()

    def _on_click(self, event):
        if not self.selection_enabled or self.spectrum is None:
            return
        if event.inaxes != self.ax or event.xdata is None:
            return
        clicked = int(round(event.xdata))
        w = 5
        s, e = max(0, clicked - w), min(len(self.spectrum), clicked + w + 1)
        region = self.spectrum[s:e]
        if len(region) == 0:
            return
        peak = s + int(np.argmax(region))
        self.input_peak_picked.emit(peak, float(self.spectrum[peak]))


# ----------------------------------------------------------------------------
# Reference spectrum canvas: curve + common/all peak markers, click to activate
# ----------------------------------------------------------------------------
class ReferenceSpectrumCanvas(FigureCanvas):
    """Bottom canvas — the library reference spectrum. Common peaks are filled,
    all peaks are open circles; clicking near a peak activates it for pairing."""

    ref_peak_clicked = pyqtSignal(int)  # index into all_peaks

    def __init__(self, parent=None):
        self.fig = Figure(figsize=(6, 2.6), dpi=100)
        self.fig.set_facecolor(_C().BG_SECONDARY)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(140)

        self.refdata = None
        self.norm = None
        self._active_idx = None
        self._paired_idx = set()

        # Crosshair tracking (red cross + coordinate readout), as in v2
        self.crosshair_v = None
        self.crosshair_h = None
        self.coord_text = None

        self.mpl_connect('button_press_event', self._on_click)
        self.mpl_connect('motion_notify_event', self._on_mouse_move)
        self.mpl_connect('axes_leave_event', self._on_mouse_leave)
        self._style()
        self.fig.tight_layout(pad=1.5)
        self.draw()

    def _style(self):
        self.ax.set_facecolor(_C().BG_TERTIARY)
        self.ax.grid(True, alpha=0.2, linestyle='--', color=_C().BORDER)
        self.ax.tick_params(labelsize=8, colors=_C().TEXT_SECONDARY)
        for s in self.ax.spines.values():
            s.set_color(_C().BORDER)

    def _init_crosshair(self):
        """Create (invisible) crosshair lines and coordinate text after a redraw."""
        self.crosshair_v = self.ax.axvline(x=0, color=_C().DANGER, linewidth=1,
                                            linestyle='--', alpha=0.8, visible=False)
        self.crosshair_h = self.ax.axhline(y=0, color=_C().DANGER, linewidth=1,
                                            linestyle='--', alpha=0.8, visible=False)
        self.coord_text = self.ax.text(
            0.02, 0.98, '', transform=self.ax.transAxes, fontsize=8,
            verticalalignment='top', fontfamily='monospace', color=_C().TEXT_PRIMARY,
            bbox=dict(boxstyle='round,pad=0.4', facecolor=_C().BG_DARK,
                      edgecolor=_C().PRIMARY, alpha=0.9), visible=False)

    def _on_mouse_move(self, event):
        if self.refdata is None or self.crosshair_v is None:
            return
        if event.inaxes != self.ax or event.xdata is None:
            return
        pixel = int(round(event.xdata))
        if 0 <= pixel < len(self.norm):
            self.crosshair_v.set_xdata([pixel, pixel])
            self.crosshair_h.set_ydata([self.norm[pixel], self.norm[pixel]])
            self.crosshair_v.set_visible(True)
            self.crosshair_h.set_visible(True)
            self.coord_text.set_text(
                f'Pixel: {pixel}\nWvn:   {self.refdata.wvn[pixel]:.1f}\n'
                f'Int:   {self.refdata.intensity[pixel]:.1f}')
            self.coord_text.set_visible(True)
            self.draw_idle()

    def _on_mouse_leave(self, event):
        for artist in (self.crosshair_v, self.crosshair_h, self.coord_text):
            if artist is not None:
                artist.set_visible(False)
        self.draw_idle()

    def load_reference(self, refdata):
        self.refdata = refdata
        inten = refdata.intensity
        lo, hi = float(np.min(inten)), float(np.max(inten))
        self.norm = (inten - lo) / (hi - lo) if hi > lo else inten * 0
        self._active_idx = None
        self._paired_idx = set()
        self._redraw()

    def set_state(self, active_idx, paired_idx):
        self._active_idx = active_idx
        self._paired_idx = set(paired_idx)
        self._redraw()

    def _common_pixels(self):
        return {p['pixel'] for p in self.refdata.common_peaks} if self.refdata else set()

    def _redraw(self):
        # Nullify crosshair refs before ax.clear() detaches them.
        self.crosshair_v = None
        self.crosshair_h = None
        self.coord_text = None
        self.ax.clear()
        self._style()
        if self.refdata is None:
            self.draw()
            return
        self.ax.plot(self.norm, color=_C().TEXT_SECONDARY, linewidth=0.9, alpha=0.8)
        self.ax.set_title(f"Reference Spectrum — {self.refdata.label}",
                          fontsize=10, fontweight='bold', color=_C().TEXT_PRIMARY)
        self.ax.set_xlabel("Pixel", fontsize=8, color=_C().TEXT_SECONDARY)
        self.ax.set_ylabel("Norm. Intensity", fontsize=8, color=_C().TEXT_SECONDARY)

        common_px = self._common_pixels()
        for i, pk in enumerate(self.refdata.all_peaks):
            px = pk['pixel']
            y = self.norm[px] if 0 <= px < len(self.norm) else 0
            is_common = px in common_px
            if i == self._active_idx:
                color, size, filled = _C().WARNING, 12, True
            elif i in self._paired_idx:
                color, size, filled = _C().SUCCESS, 9, True
            elif is_common:
                color, size, filled = _C().PRIMARY, 8, True
            else:
                color, size, filled = _C().TEXT_TERTIARY, 7, False
            self.ax.plot(px, y, 'o', markersize=size,
                         markerfacecolor=color if filled else 'none',
                         markeredgecolor=color, markeredgewidth=1.5)
        self._init_crosshair()
        self.fig.tight_layout(pad=1.5)
        self.draw()

    def _on_click(self, event):
        if self.refdata is None or event.inaxes != self.ax or event.xdata is None:
            return
        # Find nearest peak marker in pixel-x within tolerance
        xs = np.array([pk['pixel'] for pk in self.refdata.all_peaks], dtype=float)
        if len(xs) == 0:
            return
        d = np.abs(xs - event.xdata)
        j = int(np.argmin(d))
        tol = max(8, len(self.norm) * 0.01)
        if d[j] <= tol:
            self.ref_peak_clicked.emit(j)


# ----------------------------------------------------------------------------
# Pairing panel: input canvas (top) + reference canvas (bottom) + library + pairs
# ----------------------------------------------------------------------------
class PairingPanel(QWidget):
    """Reusable 3-part pairing widget for one material (neon / acetaminophen)."""

    pairs_changed = pyqtSignal()

    def __init__(self, material, default_ref_key, parent=None):
        super().__init__(parent)
        self.material = material
        self.refdata = None
        self.input_spectrum = None
        self.input_file = None
        # pairs: list of dicts {'ref_idx', 'ref_wvn', 'input_pixel'}
        self.pairs = []
        self._active_ref_idx = None

        self._build_ui()
        # Populate reference dropdown and select default
        for key, label in XcalReference.available(material):
            self.combo_ref.addItem(label, key)
        idx = self.combo_ref.findData(default_ref_key)
        self.combo_ref.setCurrentIndex(max(0, idx))
        self._on_ref_changed()

    # ---- UI construction ----
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Top controls: reference selector + upload
        top = QHBoxLayout()
        top.addWidget(QLabel("Reference:"))
        self.combo_ref = QComboBox()
        self.combo_ref.setMinimumWidth(220)
        self.combo_ref.currentIndexChanged.connect(self._on_ref_changed)
        top.addWidget(self.combo_ref)
        top.addSpacing(12)
        btn_upload = QPushButton("Upload Input Spectrum")
        btn_upload.clicked.connect(self._upload_input)
        top.addWidget(btn_upload)
        self.lbl_file = QLabel("No file loaded")
        self.lbl_file.setStyleSheet(f"color: {_C().TEXT_TERTIARY};")
        top.addWidget(self.lbl_file)
        top.addStretch()
        layout.addLayout(top)

        # Middle: [ vertical splitter: input / reference ] | library
        mid = QSplitter(Qt.Horizontal)
        mid.setChildrenCollapsible(False)

        canvas_split = QSplitter(Qt.Vertical)
        canvas_split.setChildrenCollapsible(False)
        self.input_canvas = InputSpectrumCanvas(self)
        self.input_canvas.input_peak_picked.connect(self._on_input_peak)
        self.ref_canvas = ReferenceSpectrumCanvas(self)
        self.ref_canvas.ref_peak_clicked.connect(self._activate_ref_peak)
        canvas_split.addWidget(self.input_canvas)
        canvas_split.addWidget(self.ref_canvas)
        canvas_split.setSizes([300, 300])
        mid.addWidget(canvas_split)

        # Right: reference peak library
        lib_group = QGroupBox("Reference Peak Library")
        lib_layout = QVBoxLayout(lib_group)
        lib_layout.setContentsMargins(6, 6, 6, 6)
        hint = QLabel("Click a peak to activate, then click the\nmatching peak on the input spectrum.")
        hint.setStyleSheet(f"color: {_C().TEXT_TERTIARY}; font-size: {Fonts.SIZE_SM}px;")
        hint.setWordWrap(True)
        lib_layout.addWidget(hint)
        self.list_lib = QListWidget()
        self.list_lib.itemClicked.connect(self._on_lib_item_clicked)
        lib_layout.addWidget(self.list_lib)
        lib_group.setMaximumWidth(260)
        mid.addWidget(lib_group)
        mid.setStretchFactor(0, 1)
        mid.setStretchFactor(1, 0)
        mid.setSizes([700, 250])
        layout.addWidget(mid, 1)

        # Bottom: pairs
        pairs_group = QGroupBox("Pairs (reference wavenumber ↔ input pixel)")
        pairs_layout = QHBoxLayout(pairs_group)
        self.list_pairs = QListWidget()
        self.list_pairs.setMaximumHeight(90)
        pairs_layout.addWidget(self.list_pairs, 1)
        pbtns = QVBoxLayout()
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(self._delete_selected_pair)
        btn_clr = QPushButton("Clear All")
        btn_clr.clicked.connect(self._clear_pairs)
        self.lbl_count = QLabel("Pairs: 0 (need ≥ 4)")
        self.lbl_count.setStyleSheet(f"color: {_C().TEXT_SECONDARY};")
        pbtns.addWidget(btn_del)
        pbtns.addWidget(btn_clr)
        pbtns.addWidget(self.lbl_count)
        pbtns.addStretch()
        pairs_layout.addLayout(pbtns)
        layout.addWidget(pairs_group)

    # ---- Reference selection ----
    def _on_ref_changed(self):
        key = self.combo_ref.currentData()
        if key is None:
            return
        self.refdata = XcalReference.get(key)
        # Changing reference invalidates existing pairs
        self.pairs = []
        self._active_ref_idx = None
        self.ref_canvas.load_reference(self.refdata)
        self._rebuild_library_list()
        self._refresh_all()
        self.pairs_changed.emit()

    def _rebuild_library_list(self):
        self.list_lib.clear()
        if self.refdata is None:
            return
        common_px = {p['pixel'] for p in self.refdata.common_peaks}
        for i, pk in enumerate(self.refdata.all_peaks):
            star = "★ " if pk['pixel'] in common_px else "   "
            item = QListWidgetItem(f"{star}{pk['wvn']:.1f}")
            item.setData(Qt.UserRole, i)
            self.list_lib.addItem(item)

    # ---- Input spectrum ----
    def _upload_input(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select Input Spectrum", "",
            "Data Files (*.txt *.csv *.xlsx);;All Files (*)")
        if not filepath:
            return
        try:
            spectrum = load_spectrum_file(filepath)
            self.input_spectrum = np.asarray(spectrum, dtype=float).flatten()
            self.input_file = filepath
            self.input_canvas.load_spectrum(self.input_spectrum)
            self.input_canvas.enable_selection(True)
            # Reloading input clears input-pixel assignments
            for p in self.pairs:
                p['input_pixel'] = None
            self.pairs = [p for p in self.pairs if p.get('input_pixel') is not None]
            self.lbl_file.setText(f"Loaded: {os.path.basename(filepath)}")
            self.lbl_file.setStyleSheet(f"color: {_C().SUCCESS};")
            self._refresh_all()
            self.pairs_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load spectrum:\n{e}")

    # ---- Activation & pairing ----
    def _activate_ref_peak(self, idx):
        self._active_ref_idx = idx
        # Select the matching library row
        self.list_lib.setCurrentRow(idx)
        self._refresh_canvases()

    def _on_lib_item_clicked(self, item):
        idx = item.data(Qt.UserRole)
        self._activate_ref_peak(int(idx))

    def _on_input_peak(self, pixel, intensity):
        if self._active_ref_idx is None:
            QMessageBox.information(
                self, "Select a reference peak first",
                "Activate a reference peak (click it on the reference spectrum "
                "or in the library list) before picking the input peak.")
            return
        pk = self.refdata.all_peaks[self._active_ref_idx]
        # Replace any existing pair for this reference peak
        self.pairs = [p for p in self.pairs if p['ref_idx'] != self._active_ref_idx]
        self.pairs.append({
            'ref_idx': self._active_ref_idx,
            'ref_wvn': pk['wvn'],
            'input_pixel': int(pixel),
        })
        self._active_ref_idx = None
        self._refresh_all()
        self.pairs_changed.emit()

    def _delete_selected_pair(self):
        row = self.list_pairs.currentRow()
        if 0 <= row < len(self._sorted_pairs()):
            target = self._sorted_pairs()[row]
            self.pairs = [p for p in self.pairs if p is not target]
            self._refresh_all()
            self.pairs_changed.emit()

    def _clear_pairs(self):
        self.pairs = []
        self._active_ref_idx = None
        self._refresh_all()
        self.pairs_changed.emit()

    # ---- Refresh helpers ----
    def _sorted_pairs(self):
        return sorted(self.pairs, key=lambda p: p['ref_idx'])

    def _refresh_canvases(self):
        paired_idx = {p['ref_idx'] for p in self.pairs}
        self.ref_canvas.set_state(self._active_ref_idx, paired_idx)
        # Number input markers by sorted pair order
        markers = []
        for n, p in enumerate(self._sorted_pairs(), start=1):
            markers.append({'input_pixel': p['input_pixel'], 'num': n})
        self.input_canvas.set_pairs(markers)

    def _refresh_pairs_list(self):
        self.list_pairs.clear()
        common_px = {p['pixel'] for p in self.refdata.common_peaks} if self.refdata else set()
        for n, p in enumerate(self._sorted_pairs(), start=1):
            pk = self.refdata.all_peaks[p['ref_idx']]
            star = "★" if pk['pixel'] in common_px else " "
            self.list_pairs.addItem(f"#{n}  {star} {p['ref_wvn']:.1f} cm⁻¹  ↔  px {p['input_pixel']}")
        n = len(self.pairs)
        color = _C().SUCCESS if n >= 4 else _C().WARNING
        self.lbl_count.setText(f"Pairs: {n} (need ≥ 4)")
        self.lbl_count.setStyleSheet(f"color: {color};")

    def _refresh_library_marks(self):
        paired = {p['ref_idx']: p for p in self.pairs}
        common_px = {p['pixel'] for p in self.refdata.common_peaks} if self.refdata else set()
        for row in range(self.list_lib.count()):
            item = self.list_lib.item(row)
            i = int(item.data(Qt.UserRole))
            pk = self.refdata.all_peaks[i]
            star = "★ " if pk['pixel'] in common_px else "   "
            if i in paired:
                item.setText(f"{star}{pk['wvn']:.1f}  → px {paired[i]['input_pixel']}")
                item.setForeground(QColor(_C().SUCCESS))
            else:
                item.setText(f"{star}{pk['wvn']:.1f}")
                item.setForeground(QColor(_C().TEXT_PRIMARY))

    def _refresh_all(self):
        self._refresh_canvases()
        self._refresh_pairs_list()
        self._refresh_library_marks()

    # ---- Public accessors for the dialog ----
    def get_reference_wavenumbers(self):
        return [p['ref_wvn'] for p in self._sorted_pairs()]

    def get_input_pixels(self):
        return [p['input_pixel'] for p in self._sorted_pairs()]

    def get_input_spectrum(self):
        return self.input_spectrum

    def pair_count(self):
        return len(self.pairs)


# ----------------------------------------------------------------------------
# Main dialog
# ----------------------------------------------------------------------------
class CalibrationUIV3(QDialog):
    """X-Axis Calibration dialog (v3) with the three-part pairing interface."""

    calibration_completed = pyqtSignal(dict)

    STEP_NEON = 0
    STEP_WAVELENGTH = 1
    STEP_ACET = 2
    STEP_CALIBRATE = 3

    def __init__(self, parent=None, exc_wavelength=None, raman_range=None):
        super().__init__(parent)
        self.setWindowTitle("X-Axis Calibration (v3)")
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint |
                            Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.setMinimumSize(800, 600)
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1300, int(screen.width() * 0.92)),
                    min(900, int(screen.height() * 0.92)))
        self.move(screen.center() - self.rect().center())
        self.setStyleSheet(get_current_stylesheet())

        self.exc_wavelength = exc_wavelength
        self.raman_range = raman_range
        self.processor = CalibrationProcessorV3()
        self.current_step = self.STEP_NEON
        self.wavelength_known = None
        self.saved_path = None

        self._build_ui()
        self._update_step()

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(10, 10, 10, 10)

        # Header
        header = QHBoxLayout()
        title = QLabel("X-Axis Wavenumber Calibration")
        title.setFont(QFont("Segoe UI", Fonts.SIZE_XL, QFont.Bold))
        title.setStyleSheet(f"color: {_C().TEXT_PRIMARY};")
        header.addWidget(title)
        header.addStretch()
        self.lbl_step = QLabel("")
        self.lbl_step.setFont(QFont("Segoe UI", Fonts.SIZE_LG, QFont.Bold))
        self.lbl_step.setStyleSheet(f"color: {_C().PRIMARY};")
        header.addWidget(self.lbl_step)
        main.addLayout(header)

        self.lbl_instructions = QLabel("")
        self.lbl_instructions.setWordWrap(True)
        self.lbl_instructions.setStyleSheet(
            f"color: {_C().TEXT_SECONDARY}; font-size: {Fonts.SIZE_BASE}px;")
        main.addWidget(self.lbl_instructions)

        # Stacked pages
        self.stack = QStackedWidget()

        neon_key = XcalReference.for_config("neon", self.exc_wavelength, self.raman_range)
        self.neon_panel = PairingPanel("neon", neon_key)
        self.neon_panel.pairs_changed.connect(self._on_pairs_changed)
        self.stack.addWidget(self.neon_panel)

        self.stack.addWidget(self._build_wavelength_page())

        acet_key = XcalReference.for_config("acetaminophen", self.exc_wavelength, self.raman_range)
        self.acet_panel = PairingPanel("acetaminophen", acet_key)
        self.acet_panel.pairs_changed.connect(self._on_pairs_changed)
        self.stack.addWidget(self.acet_panel)

        self.stack.addWidget(self._build_calibrate_page())

        main.addWidget(self.stack, 1)

        # Status bar
        self.status_bar = QStatusBar()
        main.addWidget(self.status_bar)

        # Navigation
        nav = QHBoxLayout()
        self.btn_prev = QPushButton("< Previous")
        self.btn_prev.clicked.connect(self._prev_step)
        nav.addWidget(self.btn_prev)
        nav.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        nav.addWidget(btn_cancel)
        self.btn_next = QPushButton("Next >")
        self.btn_next.clicked.connect(self._next_step)
        nav.addWidget(self.btn_next)
        self.btn_finish = QPushButton("Finish")
        self.btn_finish.setProperty("class", "primary")
        self.btn_finish.clicked.connect(self.accept)
        self.btn_finish.setEnabled(False)
        nav.addWidget(self.btn_finish)
        main.addLayout(nav)

    def _build_wavelength_page(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel(
            "Do you know the exact laser excitation wavelength?"))
        known = QGroupBox("Option A: Known Wavelength (Recommended)")
        kl = QHBoxLayout(known)
        kl.addWidget(QLabel("Wavelength (nm):"))
        self.input_wavelength = QDoubleSpinBox()
        self.input_wavelength.setRange(400, 1200)
        self.input_wavelength.setDecimals(3)
        try:
            self.input_wavelength.setValue(float(self.exc_wavelength) if self.exc_wavelength else 785.0)
        except (TypeError, ValueError):
            self.input_wavelength.setValue(785.0)
        kl.addWidget(self.input_wavelength)
        btn_known = QPushButton("Use This Wavelength →")
        btn_known.setProperty("class", "success")
        btn_known.clicked.connect(self._use_known_wavelength)
        kl.addWidget(btn_known)
        lay.addWidget(known)

        unknown = QGroupBox("Option B: Estimate from Acetaminophen (less accurate)")
        ul = QVBoxLayout(unknown)
        btn_acet = QPushButton("Use Acetaminophen Spectrum →")
        btn_acet.clicked.connect(self._use_acetaminophen)
        ul.addWidget(btn_acet)
        lay.addWidget(unknown)
        lay.addStretch()
        return w

    def _build_calibrate_page(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        self.lbl_summary = QLabel("Calibration Summary")
        self.lbl_summary.setWordWrap(True)
        lay.addWidget(self.lbl_summary)
        self.btn_calibrate = QPushButton("Run Calibration")
        self.btn_calibrate.setProperty("class", "primary")
        self.btn_calibrate.clicked.connect(self._run_calibration)
        lay.addWidget(self.btn_calibrate)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        lay.addWidget(self.progress)
        self.lbl_result = QLabel("")
        self.lbl_result.setWordWrap(True)
        lay.addWidget(self.lbl_result)
        self.btn_save = QPushButton("Save Calibration (.mat)")
        self.btn_save.setProperty("class", "success")
        self.btn_save.clicked.connect(self._save_calibration)
        self.btn_save.setEnabled(False)
        lay.addWidget(self.btn_save)
        lay.addStretch()
        return w

    # ---- Step navigation ----
    def _update_step(self):
        self.stack.setCurrentIndex(self.current_step)
        info = {
            self.STEP_NEON: ("Step 1: Neon-Argon Pairing",
                             "Upload your Neon-Argon spectrum. Activate a reference peak "
                             "(click it on the reference spectrum or the library list), then "
                             "click the matching peak on your input spectrum. Pair at least 4."),
            self.STEP_WAVELENGTH: ("Step 2: Laser Wavelength",
                                   "Enter a known wavelength (recommended) or estimate it from "
                                   "an Acetaminophen spectrum."),
            self.STEP_ACET: ("Step 3: Acetaminophen Pairing",
                             "Pair Acetaminophen reference peaks with your Acetaminophen spectrum "
                             "to estimate the laser wavelength."),
            self.STEP_CALIBRATE: ("Step 4: Run Calibration",
                                  "Review and run the calibration, then save the .mat file."),
        }
        title, instr = info[self.current_step]
        self.lbl_step.setText(title)
        self.lbl_instructions.setText(instr)

        self.btn_prev.setEnabled(self.current_step > 0)
        self.btn_next.setVisible(self.current_step in (self.STEP_NEON, self.STEP_ACET))
        if self.current_step == self.STEP_CALIBRATE:
            self._update_summary()

    def _prev_step(self):
        if self.current_step == self.STEP_CALIBRATE:
            self.current_step = self.STEP_WAVELENGTH if self.wavelength_known else self.STEP_ACET
        elif self.current_step == self.STEP_ACET:
            self.current_step = self.STEP_WAVELENGTH
        elif self.current_step > 0:
            self.current_step -= 1
        self._update_step()

    def _next_step(self):
        if self.current_step == self.STEP_NEON:
            if self.neon_panel.get_input_spectrum() is None:
                QMessageBox.warning(self, "Spectrum Required", "Please upload a Neon-Argon spectrum.")
                return
            if self.neon_panel.pair_count() < 4:
                QMessageBox.warning(self, "More Pairs Needed",
                                    "Please create at least 4 reference/input peak pairs.")
                return
            self.current_step = self.STEP_WAVELENGTH
        elif self.current_step == self.STEP_ACET:
            if self.acet_panel.get_input_spectrum() is None:
                QMessageBox.warning(self, "Spectrum Required", "Please upload an Acetaminophen spectrum.")
                return
            if self.acet_panel.pair_count() < 4:
                QMessageBox.warning(self, "More Pairs Needed",
                                    "Please create at least 4 reference/input peak pairs.")
                return
            self.current_step = self.STEP_CALIBRATE
        self._update_step()

    def _on_pairs_changed(self):
        if self.current_step == self.STEP_NEON:
            self.status_bar.showMessage(f"Neon pairs: {self.neon_panel.pair_count()}")
        elif self.current_step == self.STEP_ACET:
            self.status_bar.showMessage(f"Acetaminophen pairs: {self.acet_panel.pair_count()}")

    def _use_known_wavelength(self):
        self.processor.set_known_wavelength(self.input_wavelength.value())
        self.wavelength_known = True
        self.current_step = self.STEP_CALIBRATE
        self._update_step()

    def _use_acetaminophen(self):
        self.wavelength_known = False
        self.current_step = self.STEP_ACET
        self._update_step()

    def _update_summary(self):
        s = "Calibration Configuration:\n\n"
        s += f"Neon-Argon: {self.neon_panel.pair_count()} pairs\n"
        if self.wavelength_known:
            s += f"Method: Known wavelength ({self.input_wavelength.value():.3f} nm)\n"
            s += "Acetaminophen: not used\n"
        else:
            s += f"Method: Estimate from Acetaminophen ({self.acet_panel.pair_count()} pairs)\n"
        self.lbl_summary.setText(s)

    def _run_calibration(self):
        try:
            self.progress.setVisible(True)
            self.progress.setValue(20)
            QApplication.processEvents()

            # Feed neon data
            self.processor.set_neon_reference_values(self.neon_panel.get_reference_wavenumbers())
            self.processor.set_neon_spectrum(self.neon_panel.get_input_spectrum().reshape(-1, 1))
            self.processor.set_neon_selected_peaks(self.neon_panel.get_input_pixels())

            if self.wavelength_known:
                wvn = self.processor.calibrate_with_known_wavelength()
            else:
                self.processor.set_acet_reference_values(self.acet_panel.get_reference_wavenumbers())
                self.processor.set_acet_spectrum(self.acet_panel.get_input_spectrum().reshape(-1, 1))
                self.processor.set_acet_selected_peaks(self.acet_panel.get_input_pixels())
                wvn = self.processor.calibrate_with_acetaminophen()

            self.progress.setValue(80)
            QApplication.processEvents()
            errors = self.processor.get_calibration_error()
            self.progress.setValue(100)

            txt = "Calibration completed successfully!\n\n"
            txt += f"Wavenumber range: {wvn.min():.1f} to {wvn.max():.1f} cm⁻¹\n"
            txt += f"Spectrum length: {len(wvn)} points\n"
            if self.processor.laser_wavelength:
                txt += f"Laser wavelength: {self.processor.laser_wavelength:.3f} nm\n"
            if 'neon_mean_abs_error' in errors:
                txt += f"\nMean absolute error: {errors['neon_mean_abs_error']:.4f} cm⁻¹\n"
                txt += f"Max error: {errors['neon_max_error']:.4f} cm⁻¹\n"
            self.lbl_result.setText(txt)
            self.lbl_result.setStyleSheet(f"color: {_C().SUCCESS};")
            self.btn_save.setEnabled(True)
            self.status_bar.showMessage("Calibration completed successfully")
        except Exception as e:
            self.progress.setVisible(False)
            QMessageBox.critical(self, "Calibration Error", f"Calibration failed:\n{e}")

    def _save_calibration(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Calibration", "calibration.mat", "MAT Files (*.mat);;All Files (*)")
        if not filepath:
            return
        if not filepath.endswith('.mat'):
            filepath += '.mat'
        try:
            result = self.processor.get_calibration_result()
            savemat(filepath, {'Cal': result})
            QMessageBox.information(self, "Saved", f"Calibration saved to:\n{filepath}")
            self.status_bar.showMessage(f"Calibration saved: {filepath}")
            self.saved_path = filepath
            self.btn_finish.setEnabled(True)
            self.calibration_completed.emit(result)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save:\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(get_current_stylesheet())
    dlg = CalibrationUIV3(exc_wavelength=785, raman_range="Fingerprint")
    dlg.exec_()
    sys.exit(app.exec_())
