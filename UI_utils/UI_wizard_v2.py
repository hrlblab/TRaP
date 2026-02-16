# UI_wizard_v2.py
# -*- coding: utf-8 -*-

"""
Raman Process Wizard v2 - Optimized version

A step-by-step wizard for Raman spectroscopy data processing workflow.
Improvements over v1:
  - Dynamic button text that reflects current step
  - Better status tracking and visual feedback
  - Cleaner layout and improved user experience
  - All UI text and comments in English

Workflow Steps:
  0. Config Manager - Configure instrument/system parameters
  1. X-axis Calibration - Calibrate wavenumber axis
  2. Spectral Response Correction - Apply spectral response correction
  3. Spectrum Process - Process individual spectra
  4. Batch Process - Batch processing of multiple spectra
"""

from PyQt5.QtCore import Qt, QEasingCurve, QPropertyAnimation, QRect, QParallelAnimationGroup, QSequentialAnimationGroup, QTimer
from PyQt5.QtGui import QPixmap, QFont, QIcon, QColor
from PyQt5.QtWidgets import (
    QApplication, QWidget, QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QMessageBox, QFrame, QScrollArea, QGraphicsDropShadowEffect, QSizePolicy,
    QCheckBox, QGroupBox, QGridLayout, QGraphicsOpacityEffect
)

from UI_utils.UI_theme import get_stylesheet, Colors, Fonts


def apply_modern_style(app):
    """Apply unified premium dark theme stylesheet."""
    # Use the unified theme with wizard-specific additions
    base_style = get_stylesheet()
    wizard_additions = f"""
        /* Wizard-specific styles */
        QLabel#Title {{
            font-size: {Fonts.SIZE_XXXL}px;
            font-weight: 700;
            color: {Colors.TEXT_PRIMARY};
        }}
        QLabel#StepTitle {{
            font-size: {Fonts.SIZE_XL}px;
            font-weight: 600;
            color: {Colors.PRIMARY};
        }}
        QLabel#Subtitle {{
            color: {Colors.TEXT_SECONDARY};
            font-size: {Fonts.SIZE_BASE}px;
        }}
        QLabel#Description {{
            color: {Colors.TEXT_SECONDARY};
            font-size: {Fonts.SIZE_SM}px;
            line-height: 1.5;
        }}

        QPushButton.step {{
            text-align: left;
            padding: 14px 18px;
            border-radius: 10px;
            background: transparent;
            font-size: {Fonts.SIZE_BASE}px;
        }}
        QPushButton.step:hover {{
            background: {Colors.BG_HOVER};
        }}
        QPushButton.step[active="true"] {{
            background: {Colors.PRIMARY_MUTED};
            color: {Colors.PRIMARY_HOVER};
            font-weight: 600;
        }}
        QPushButton.step[completed="true"] {{
            color: {Colors.SUCCESS};
        }}
        QPushButton.step[skipped="true"] {{
            color: {Colors.TEXT_TERTIARY};
            background: {Colors.BG_TERTIARY};
            opacity: 0.5;
        }}

        QFrame#card {{
            background: {Colors.BG_SECONDARY};
            border-radius: 16px;
        }}
        QFrame#statusCard {{
            background: {Colors.BG_TERTIARY};
            border-radius: 10px;
            padding: 10px;
        }}
    """
    app.setStyleSheet(base_style + wizard_additions)


class ModernCard(QFrame):
    """Rounded card with shadow effect."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 6)
        shadow.setColor(Qt.black)
        self.setGraphicsEffect(shadow)


class ModernShell(QWidget):
    """Main shell with left navigation rail and right content area."""

    def __init__(self, content_widget: QWidget, step_titles, on_step_request):
        super().__init__()
        self.content_widget = content_widget
        self.step_titles = step_titles
        self.on_step_request = on_step_request
        self.step_buttons = []
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # Left navigation rail - wrapped in scroll area for small windows
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setMinimumWidth(180)
        left_scroll.setMaximumWidth(260)
        left_scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        left_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #444;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        left_widget = QWidget()
        left = QVBoxLayout(left_widget)
        left.setContentsMargins(4, 4, 4, 4)
        left.setSpacing(8)

        # Logo
        logo = QLabel()
        pix = QPixmap('vanderbilt_biophotonics_center_logo.jpg')
        if not pix.isNull():
            logo.setPixmap(pix.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        left.addWidget(logo)

        # Title
        title = QLabel("Raman Processing")
        title.setObjectName("Title")
        title.setWordWrap(True)
        left.addWidget(title)

        # Subtitle
        subtitle = QLabel("Step-by-step workflow")
        subtitle.setObjectName("Subtitle")
        left.addWidget(subtitle)
        left.addSpacing(8)

        # Step buttons
        for i, t in enumerate(self.step_titles):
            b = QPushButton(f"  {i}. {t}")
            b.setCursor(Qt.PointingHandCursor)
            b.setProperty("class", "step")
            b.setProperty("active", False)
            b.setProperty("completed", False)
            b.setMinimumHeight(36)
            b.setObjectName("stepBtn")
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.clicked.connect(lambda _, idx=i: self._on_nav_clicked(idx))
            self.step_buttons.append(b)
            left.addWidget(b)

        left.addStretch(1)
        left_scroll.setWidget(left_widget)

        # Right content card
        right_card = ModernCard()
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(self.content_widget)
        right_layout.addWidget(scroll)

        root.addWidget(left_scroll, 1)
        root.addWidget(right_card, 3)

    def _on_nav_clicked(self, idx: int):
        if callable(self.on_step_request):
            self.on_step_request(idx)

    def set_active_step(self, idx: int):
        """Update navigation rail to highlight active step."""
        for i, b in enumerate(self.step_buttons):
            b.setProperty("active", i == idx)
            b.style().unpolish(b)
            b.style().polish(b)

    def set_step_completed(self, idx: int, completed: bool = True):
        """Mark a step as completed in navigation rail."""
        if 0 <= idx < len(self.step_buttons):
            b = self.step_buttons[idx]
            b.setProperty("completed", completed)
            b.style().unpolish(b)
            b.style().polish(b)

    def set_step_skipped(self, idx: int, skipped: bool = True):
        """Mark a step as skipped (dimmed) in navigation rail."""
        if 0 <= idx < len(self.step_buttons):
            b = self.step_buttons[idx]
            b.setProperty("skipped", skipped)
            b.setEnabled(not skipped)
            b.style().unpolish(b)
            b.style().polish(b)


class AnimationManager:
    """Manages smooth animations for UI transitions."""

    _active_animations = []

    @staticmethod
    def slide_in(widget: QWidget, direction: str = "right", duration: int = 300):
        """Animate widget sliding in from a direction."""
        offset = 40
        if direction == "right":
            start_x, start_y = widget.x() + offset, widget.y()
        elif direction == "left":
            start_x, start_y = widget.x() - offset, widget.y()
        elif direction == "up":
            start_x, start_y = widget.x(), widget.y() - offset
        else:  # down
            start_x, start_y = widget.x(), widget.y() + offset

        start_rect = QRect(start_x, start_y, widget.width(), widget.height())
        end_rect = QRect(widget.x(), widget.y(), widget.width(), widget.height())

        anim = QPropertyAnimation(widget, b"geometry", widget)
        anim.setDuration(duration)
        anim.setStartValue(start_rect)
        anim.setEndValue(end_rect)
        anim.setEasingCurve(QEasingCurve.OutCubic)

        AnimationManager._active_animations.append(anim)
        anim.finished.connect(lambda: AnimationManager._cleanup(anim))
        anim.start()
        return anim

    @staticmethod
    def fade_in(widget: QWidget, duration: int = 250):
        """Animate widget fading in."""
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutQuad)

        AnimationManager._active_animations.append(anim)
        # Clean up effect after animation to prevent click offset issues
        def on_finished():
            AnimationManager._cleanup(anim)
            widget.setGraphicsEffect(None)
        anim.finished.connect(on_finished)
        anim.start()
        return anim

    @staticmethod
    def fade_out(widget: QWidget, duration: int = 200):
        """Animate widget fading out."""
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(duration)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.InQuad)

        AnimationManager._active_animations.append(anim)
        # Clean up effect after animation to prevent click offset issues
        def on_finished():
            AnimationManager._cleanup(anim)
            widget.setGraphicsEffect(None)
        anim.finished.connect(on_finished)
        anim.start()
        return anim

    @staticmethod
    def pulse(widget: QWidget, duration: int = 400):
        """Create a subtle pulse/scale animation."""
        start_rect = widget.geometry()
        # Slightly shrink then expand back
        mid_rect = QRect(
            start_rect.x() + 3, start_rect.y() + 2,
            start_rect.width() - 6, start_rect.height() - 4
        )

        group = QSequentialAnimationGroup(widget)

        shrink = QPropertyAnimation(widget, b"geometry", widget)
        shrink.setDuration(duration // 2)
        shrink.setStartValue(start_rect)
        shrink.setEndValue(mid_rect)
        shrink.setEasingCurve(QEasingCurve.OutQuad)

        expand = QPropertyAnimation(widget, b"geometry", widget)
        expand.setDuration(duration // 2)
        expand.setStartValue(mid_rect)
        expand.setEndValue(start_rect)
        expand.setEasingCurve(QEasingCurve.OutBounce)

        group.addAnimation(shrink)
        group.addAnimation(expand)

        AnimationManager._active_animations.append(group)
        group.finished.connect(lambda: AnimationManager._cleanup(group))
        group.start()
        return group

    @staticmethod
    def slide_and_fade(widget: QWidget, direction: str = "right", duration: int = 350):
        """Combined slide and fade animation for step transitions."""
        group = QParallelAnimationGroup(widget)

        # Slide animation
        offset = 50
        if direction == "right":
            start_x, start_y = widget.x() + offset, widget.y()
        elif direction == "left":
            start_x, start_y = widget.x() - offset, widget.y()
        else:
            start_x, start_y = widget.x(), widget.y() + offset

        start_rect = QRect(start_x, start_y, widget.width(), widget.height())
        end_rect = QRect(widget.x(), widget.y(), widget.width(), widget.height())

        slide = QPropertyAnimation(widget, b"geometry", widget)
        slide.setDuration(duration)
        slide.setStartValue(start_rect)
        slide.setEndValue(end_rect)
        slide.setEasingCurve(QEasingCurve.OutCubic)

        # Fade animation
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

        fade = QPropertyAnimation(effect, b"opacity", widget)
        fade.setDuration(duration)
        fade.setStartValue(0.3)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.OutQuad)

        group.addAnimation(slide)
        group.addAnimation(fade)

        AnimationManager._active_animations.append(group)
        # Clean up effect after animation to prevent click offset issues
        def on_finished():
            AnimationManager._cleanup(group)
            widget.setGraphicsEffect(None)
        group.finished.connect(on_finished)
        group.start()
        return group

    @staticmethod
    def _cleanup(anim):
        """Clean up finished animation."""
        if anim in AnimationManager._active_animations:
            AnimationManager._active_animations.remove(anim)


def animate_step_change(widget: QWidget, direction: str = "right"):
    """Animate widget transition when changing steps with combined effects."""
    return AnimationManager.slide_and_fade(widget, direction)


# Import UI modules
from UI_utils.UI_Config_Manager_v2 import ConfigManagerUI, ConfigManager
from UI_utils.UI_SRCF import SRCF_UI
# from UI_utils.UI_Calibration import WaveformSelectionUI  # Old calibration UI
from UI_utils.UI_Calibration_v2 import CalibrationUI  # New calibration UI with library selection
from UI_utils.UI_P_Mean_Process import P_Mean_Process_UI
from UI_utils.UI_P_Mean_Batch_Process import BatchPMeanUI


class SystemSelectWizard(QWidget):
    """
    Main wizard widget for Raman processing workflow.

    Features:
    - Step-by-step workflow guidance
    - Dynamic button text based on current step
    - Progress tracking with step completion status
    - Skip options for users with existing calibration/correction files
    """

    # Step definitions
    STEPS = [
        "Config Manager",
        "X-axis Calibration",
        "Spectral Response Correction",
        "Spectrum Process",
        "Batch Process"
    ]

    # Step descriptions
    STEP_DESCRIPTIONS = {
        0: "Configure your instrument and system parameters. Save or load configurations "
           "for different setups. If you already have calibration or correction files, "
           "use the checkboxes below to skip those steps.",
        1: "Calibrate the X-axis (wavenumber). Upload reference spectra and perform "
           "wavelength-to-wavenumber calibration. Save the calibration as a .mat file "
           "for future use.",
        2: "Apply spectral response correction using White-Light or NIST/SRM method. "
           "Upload raw spectra to see before/after comparison and save corrected results.",
        3: "Process individual spectra through the complete pipeline: baseline subtraction, "
           "response correction, truncation, binning, denoising, and normalization.",
        4: "Apply batch processing to multiple spectra using the same configuration. "
           "Ideal for processing large datasets with consistent parameters."
    }

    # Button text for each step
    BUTTON_TEXTS = {
        0: "Open Config Manager",
        1: "Start X-axis Calibration",
        2: "Open Response Correction",
        3: "Process Single Spectrum",
        4: "Start Batch Processing"
    }

    def __init__(self, shell_bridge=None):
        super().__init__()
        self.setWindowTitle("Raman Process Wizard v2")
        self.setMinimumSize(480, 400)

        # State
        self.step = 0
        self.opened_windows = []
        self.config = ConfigManager()
        self._shell_sync = shell_bridge
        self._shell = None  # Reference to ModernShell for step skipping

        # Step completion tracking
        self.step_completed = [False] * len(self.STEPS)

        # Skip flags
        self.has_calibration_file = False
        self.has_response_correction = False

        # Hidden trigger buttons (for internal step handling)
        self.buttons = [QPushButton(t, self) for t in self.STEPS]
        for b in self.buttons:
            b.clicked.connect(self._on_step)
            b.hide()

        self._build_ui()
        self._update_ui()

    def _build_ui(self):
        """Build the main UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # Main card
        card = ModernCard()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        # Header section
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)

        self.lbl_step_indicator = QLabel()
        self.lbl_step_indicator.setObjectName("Subtitle")
        header_layout.addWidget(self.lbl_step_indicator)

        self.lbl_step_title = QLabel()
        self.lbl_step_title.setObjectName("StepTitle")
        header_layout.addWidget(self.lbl_step_title)

        self.lbl_description = QLabel()
        self.lbl_description.setObjectName("Description")
        self.lbl_description.setWordWrap(True)
        self.lbl_description.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.lbl_description.setMinimumHeight(60)
        header_layout.addWidget(self.lbl_description)

        card_layout.addLayout(header_layout)

        # Options section (only visible on step 0)
        self.options_group = QGroupBox("Quick Options")
        options_layout = QVBoxLayout(self.options_group)

        self.chk_has_cal = QCheckBox("I already have X-axis Calibration (.mat file)")
        self.chk_has_cal.stateChanged.connect(self._on_toggle_calibration)
        options_layout.addWidget(self.chk_has_cal)

        self.chk_has_resp = QCheckBox("I already have Spectral Response Correction factor")
        self.chk_has_resp.stateChanged.connect(self._on_toggle_response)
        options_layout.addWidget(self.chk_has_resp)

        card_layout.addWidget(self.options_group)

        # Current Configuration Display
        self.config_group = QGroupBox("Current Configuration")
        config_layout = QGridLayout(self.config_group)
        config_layout.setSpacing(6)
        config_layout.setContentsMargins(12, 12, 12, 12)

        # Config parameter labels (will be populated dynamically)
        self.config_labels = {}
        config_params = [
            ("config_name", "Configuration:"),
            ("system", "System:"),
            ("wavelength", "Wavelength:"),
            ("detector", "Detector:"),
            ("probe", "Probe:"),
            ("range", "Raman Range:"),
        ]
        for i, (key, label_text) in enumerate(config_params):
            row = i // 2
            col = (i % 2) * 2
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #888; font-size: 11px;")
            config_layout.addWidget(lbl, row, col)

            value_lbl = QLabel("N/A")
            value_lbl.setStyleSheet("color: #EAEAEA; font-size: 11px; font-weight: 500;")
            self.config_labels[key] = value_lbl
            config_layout.addWidget(value_lbl, row, col + 1)

        card_layout.addWidget(self.config_group)

        # Status section
        self.status_frame = QFrame()
        self.status_frame.setObjectName("statusCard")
        status_layout = QHBoxLayout(self.status_frame)
        status_layout.setContentsMargins(12, 8, 12, 8)

        self.lbl_status = QLabel("Status: Ready")
        self.lbl_status.setStyleSheet("color: #888;")
        status_layout.addWidget(self.lbl_status)
        status_layout.addStretch()

        card_layout.addWidget(self.status_frame)

        # Action buttons section
        action_layout = QHBoxLayout()
        action_layout.setSpacing(12)

        self.btn_back = QPushButton("Back to Step 0")
        self.btn_back.clicked.connect(self._go_to_step_0)
        action_layout.addWidget(self.btn_back)

        action_layout.addStretch()

        self.btn_primary = QPushButton()
        self.btn_primary.setProperty("cta", True)
        self.btn_primary.setMinimumWidth(200)
        self.btn_primary.clicked.connect(self._on_primary_click)
        action_layout.addWidget(self.btn_primary)

        card_layout.addLayout(action_layout)

        # Navigation hint
        nav_hint = QLabel("Tip: Use the left sidebar to navigate between steps")
        nav_hint.setStyleSheet("color: #555; font-size: 11px;")
        nav_hint.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(nav_hint)

        card_layout.addStretch()
        layout.addWidget(card)

    def _update_ui(self):
        """Update all UI elements based on current state."""
        # Update step indicator
        self.lbl_step_indicator.setText(f"Step {self.step} of {len(self.STEPS) - 1}")

        # Update step title
        self.lbl_step_title.setText(self.STEPS[self.step])

        # Update description
        self.lbl_description.setText(self.STEP_DESCRIPTIONS.get(self.step, ""))

        # Update primary button text
        self.btn_primary.setText(self.BUTTON_TEXTS.get(self.step, "Continue"))

        # Show/hide options group (only on step 0)
        self.options_group.setVisible(self.step == 0)

        # Show/hide back button (hidden on step 0)
        self.btn_back.setVisible(self.step > 0)

        # Update configuration display
        self._update_config_display()

        # Update status
        self._update_status()

        # Sync with shell if available
        if callable(self._shell_sync):
            self._shell_sync(self.step)

        # Enable/disable buttons based on workflow
        self._update_button_states()

    def _update_config_display(self):
        """Update the configuration display panel."""
        params = self.config.params

        # Update config labels
        self.config_labels["config_name"].setText(params.get("Name", "Not Set") or "Not Set")
        self.config_labels["system"].setText(params.get("System", "N/A"))
        self.config_labels["wavelength"].setText(f"{params.get('Exc Wavelength', 'N/A')} nm")
        self.config_labels["detector"].setText(params.get("Detector", "N/A") or "N/A")
        self.config_labels["probe"].setText(params.get("Probe", "N/A"))
        self.config_labels["range"].setText(params.get("Raman Shift Range", "N/A"))

    def _update_status(self):
        """Update status label based on current state."""
        status_parts = []

        if self.has_calibration_file or self.step_completed[1]:
            status_parts.append("Calibration: Ready")
        else:
            status_parts.append("Calibration: Pending")

        if self.has_response_correction or self.step_completed[2]:
            status_parts.append("Response Correction: Ready")
        else:
            status_parts.append("Response Correction: Pending")

        self.lbl_status.setText(" | ".join(status_parts))

    def _update_button_states(self):
        """Update button enable/disable states based on workflow."""
        # Primary button is always enabled for current step
        self.btn_primary.setEnabled(True)

        # Update hidden trigger buttons
        for i, btn in enumerate(self.buttons):
            if i == 0:
                btn.setEnabled(True)
            elif self.step >= 3 and i in (3, 4):
                btn.setEnabled(True)
            elif i == self.step:
                btn.setEnabled(True)
            else:
                btn.setEnabled(False)

    def _on_toggle_calibration(self, state):
        """Handle calibration checkbox toggle."""
        self.has_calibration_file = self.chk_has_cal.isChecked()
        self._update_status()
        # Update shell step appearance
        if self._shell is not None:
            self._shell.set_step_skipped(1, self.has_calibration_file)

    def _on_toggle_response(self, state):
        """Handle response correction checkbox toggle."""
        self.has_response_correction = self.chk_has_resp.isChecked()
        self._update_status()
        # Update shell step appearance
        if self._shell is not None:
            self._shell.set_step_skipped(2, self.has_response_correction)

    def _go_to_step_0(self):
        """Navigate back to step 0."""
        self.step = 0
        self._update_ui()
        animate_step_change(self)

    def _on_primary_click(self):
        """Handle primary action button click."""
        self._request_step(self.step)

    def request_step_from_shell(self, idx: int):
        """Called by ModernShell when user clicks navigation."""
        self._request_step(idx)

    def _request_step(self, idx: int):
        """Request to execute a specific step."""
        # Validate step accessibility
        if idx != self.step and not (self.step >= 3 and idx in (3, 4)):
            return
        self.buttons[idx].click()

    def _on_step(self):
        """Handle step execution."""
        idx = self.buttons.index(self.sender())

        if idx == 0:
            self._execute_step_0()
        elif idx == 1:
            self._execute_step_1()
        elif idx == 2:
            self._execute_step_2()
        elif idx == 3:
            self._execute_step_3()
        elif idx == 4:
            self._execute_step_4()

    def _execute_step_0(self):
        """Step 0: Config Manager"""
        win = ConfigManagerUI()
        win.config_updated.connect(self._after_config_saved)
        win.show()
        self.opened_windows.append(win)

    def _execute_step_1(self):
        """Step 1: X-axis Calibration"""
        if self.has_calibration_file:
            QMessageBox.information(
                self, "Calibration",
                "Calibration file already provided. Skipping to Response Correction."
            )
            self.step_completed[1] = True
            self.step = 2
            self._update_ui()
            animate_step_change(self)
            return

        # Use new CalibrationUI dialog
        cal_dlg = CalibrationUI(self)
        result = cal_dlg.exec_()

        if result == QDialog.Accepted:
            # Calibration completed successfully
            self.step_completed[1] = True
            self.step = 2
            self._update_ui()
            animate_step_change(self)
            QMessageBox.information(
                self, "Calibration Complete",
                "X-axis calibration completed successfully.\n"
                "Proceeding to Spectral Response Correction."
            )
        # else: User cancelled, stay on current step
        animate_step_change(self)

    def _execute_step_2(self):
        """Step 2: Spectral Response Correction"""
        if self.has_response_correction:
            QMessageBox.information(
                self, "Response Correction",
                "Response correction already provided. Skipping to Spectrum Process."
            )
            self.step_completed[2] = True
            self.step = 3
            self._update_ui()
            animate_step_change(self)
            return

        dlg = SRCF_UI(self)
        dlg.exec_()

        # Check result after dialog closes
        result = getattr(dlg, "result", None)
        has_correction = dlg.corr is not None

        if result == "RequireXAxisCalibration" and not self.has_calibration_file:
            # Need calibration first
            QMessageBox.warning(
                self, "Calibration Required",
                "X-axis calibration is required for this correction method.\n"
                "Please complete calibration first."
            )
            self.step = 1
            self._update_ui()
            animate_step_change(self)
        elif has_correction or result in ["CorrComputed", "UseExistingFactor"]:
            # Correction completed successfully
            self.step_completed[2] = True
            self.step = 3
            self._update_ui()
            animate_step_change(self)
            QMessageBox.information(
                self, "Success",
                "Spectral Response Correction completed successfully.\n"
                "Proceeding to Spectrum Process."
            )
        # else: User cancelled, stay on current step

    def _execute_step_3(self):
        """Step 3: Spectrum Process"""
        sp_win = P_Mean_Process_UI()
        sp_win.show()
        self.opened_windows.append(sp_win)

    def _execute_step_4(self):
        """Step 4: Batch Process"""
        batch_win = BatchPMeanUI()
        batch_win.show()
        self.opened_windows.append(batch_win)

    def _after_config_saved(self):
        """Called after config is saved in Config Manager."""
        self.step_completed[0] = True

        # Determine next step based on skip flags
        if self.has_calibration_file and self.has_response_correction:
            self.step = 3
            msg = "Configuration saved. Calibration and Response Correction ready.\n" \
                  "Proceeding to Spectrum Process."
        elif self.has_calibration_file:
            self.step = 2
            msg = "Configuration saved. Calibration ready.\n" \
                  "Proceeding to Response Correction."
        else:
            self.step = 1
            msg = "Configuration saved.\n" \
                  "Proceeding to X-axis Calibration."

        self._update_ui()
        animate_step_change(self)
        QMessageBox.information(self, "Next Step", msg)

    def closeEvent(self, event):
        """Clean up opened windows on close."""
        for win in getattr(self, "opened_windows", []):
            try:
                win.close()
            except Exception:
                pass
        event.accept()


# Quick test
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    apply_modern_style(app)

    wizard = SystemSelectWizard()
    shell = ModernShell(
        wizard,
        SystemSelectWizard.STEPS,
        wizard.request_step_from_shell
    )
    shell.setWindowTitle("TRaP - Raman Processing Application")
    shell.resize(1000, 650)
    shell.show()

    # Sync shell with wizard
    wizard._shell_sync = shell.set_active_step
    wizard._shell = shell  # For step skipping functionality

    sys.exit(app.exec_())
