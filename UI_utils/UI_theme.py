# UI_theme.py
# -*- coding: utf-8 -*-
"""
Unified Theme Module for TRaP Application

A modern, premium dark theme with consistent styling across all UI components.
Features:
- Large, readable fonts (16px base)
- Premium color palette with subtle gradients
- Consistent spacing and rounded corners
- Elegant shadows and hover effects
"""

from PyQt5.QtWidgets import QApplication, QGraphicsDropShadowEffect
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtCore import Qt


# =============================================================================
# Color Palette - Premium Dark Theme
# =============================================================================

class Colors:
    """Premium dark theme color palette."""

    # Background colors
    BG_DARK = "#0D1117"          # Main background (GitHub dark)
    BG_SECONDARY = "#161B22"     # Card/panel background
    BG_TERTIARY = "#21262D"      # Elevated elements
    BG_HOVER = "#30363D"         # Hover state
    BG_ACTIVE = "#388BFD20"      # Active/selected background

    # Primary accent - Electric Blue
    PRIMARY = "#58A6FF"          # Primary buttons, links
    PRIMARY_HOVER = "#79B8FF"    # Primary hover
    PRIMARY_PRESSED = "#388BFD"  # Primary pressed
    PRIMARY_MUTED = "#388BFD40"  # Muted primary for backgrounds

    # Secondary accent - Soft Purple
    SECONDARY = "#A371F7"        # Secondary accent
    SECONDARY_HOVER = "#BD8BFB"

    # Success - Green
    SUCCESS = "#3FB950"          # Success states
    SUCCESS_HOVER = "#56D364"
    SUCCESS_BG = "#23863620"

    # Warning - Orange/Yellow
    WARNING = "#D29922"
    WARNING_HOVER = "#E3B341"
    WARNING_BG = "#9E6A0320"

    # Error/Danger - Red
    DANGER = "#F85149"
    DANGER_HOVER = "#FF6B61"
    DANGER_BG = "#F8514920"

    # Text colors
    TEXT_PRIMARY = "#F0F6FC"     # Main text
    TEXT_SECONDARY = "#8B949E"   # Secondary/muted text
    TEXT_TERTIARY = "#6E7681"    # Disabled/hint text
    TEXT_LINK = "#58A6FF"        # Links

    # Border colors
    BORDER = "#30363D"           # Default border
    BORDER_MUTED = "#21262D"     # Subtle border
    BORDER_FOCUS = "#58A6FF"     # Focus state border

    # Status colors
    INFO = "#58A6FF"
    INFO_BG = "#388BFD20"


# =============================================================================
# Font Definitions
# =============================================================================

class Fonts:
    """Font definitions with larger sizes for readability."""

    FAMILY = "'Segoe UI', 'SF Pro Display', 'Helvetica Neue', Arial, sans-serif"
    FAMILY_MONO = "'JetBrains Mono', 'Fira Code', 'Consolas', monospace"

    # Font sizes (larger for better readability)
    SIZE_XS = 12
    SIZE_SM = 13
    SIZE_BASE = 15
    SIZE_MD = 16
    SIZE_LG = 18
    SIZE_XL = 22
    SIZE_XXL = 28
    SIZE_XXXL = 36


# =============================================================================
# Main Stylesheet
# =============================================================================

def get_stylesheet() -> str:
    """Generate the complete application stylesheet."""

    return f"""
    /* ========================================
       Global Styles
       ======================================== */

    QWidget {{
        font-family: {Fonts.FAMILY};
        font-size: {Fonts.SIZE_BASE}px;
        color: {Colors.TEXT_PRIMARY};
        background-color: {Colors.BG_DARK};
    }}

    QMainWindow {{
        background-color: {Colors.BG_DARK};
    }}

    QDialog {{
        background-color: {Colors.BG_DARK};
    }}

    /* ========================================
       Labels
       ======================================== */

    QLabel {{
        color: {Colors.TEXT_PRIMARY};
        font-size: {Fonts.SIZE_BASE}px;
        padding: 2px;
    }}

    QLabel[class="title"] {{
        font-size: {Fonts.SIZE_XXXL}px;
        font-weight: 700;
        color: {Colors.TEXT_PRIMARY};
        padding: 8px 0;
    }}

    QLabel[class="subtitle"] {{
        font-size: {Fonts.SIZE_LG}px;
        font-weight: 500;
        color: {Colors.TEXT_SECONDARY};
    }}

    QLabel[class="section-title"] {{
        font-size: {Fonts.SIZE_XL}px;
        font-weight: 600;
        color: {Colors.PRIMARY};
        padding: 4px 0;
    }}

    QLabel[class="hint"] {{
        font-size: {Fonts.SIZE_SM}px;
        color: {Colors.TEXT_TERTIARY};
        font-style: italic;
    }}

    QLabel[class="status-success"] {{
        color: {Colors.SUCCESS};
        font-weight: 500;
    }}

    QLabel[class="status-error"] {{
        color: {Colors.DANGER};
        font-weight: 500;
    }}

    QLabel[class="status-warning"] {{
        color: {Colors.WARNING};
        font-weight: 500;
    }}

    /* ========================================
       Push Buttons
       ======================================== */

    QPushButton {{
        font-size: {Fonts.SIZE_BASE}px;
        font-weight: 500;
        padding: 8px 16px;
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        background-color: {Colors.BG_TERTIARY};
        color: {Colors.TEXT_PRIMARY};
        min-height: 20px;
        min-width: 80px;
    }}

    QPushButton:hover {{
        background-color: {Colors.BG_HOVER};
        border-color: {Colors.TEXT_TERTIARY};
    }}

    QPushButton:pressed {{
        background-color: {Colors.BG_SECONDARY};
    }}

    QPushButton:disabled {{
        background-color: {Colors.BG_SECONDARY};
        color: {Colors.TEXT_TERTIARY};
        border-color: {Colors.BORDER_MUTED};
    }}

    QPushButton:focus {{
        border-color: {Colors.BORDER_FOCUS};
        outline: none;
    }}

    /* Primary Button */
    QPushButton[class="primary"], QPushButton[cta="true"] {{
        background-color: {Colors.PRIMARY};
        color: {Colors.BG_DARK};
        border: none;
        font-weight: 600;
    }}

    QPushButton[class="primary"]:hover, QPushButton[cta="true"]:hover {{
        background-color: {Colors.PRIMARY_HOVER};
    }}

    QPushButton[class="primary"]:pressed, QPushButton[cta="true"]:pressed {{
        background-color: {Colors.PRIMARY_PRESSED};
    }}

    QPushButton[class="primary"]:disabled, QPushButton[cta="true"]:disabled {{
        background-color: {Colors.PRIMARY_MUTED};
        color: {Colors.TEXT_TERTIARY};
    }}

    /* Success Button */
    QPushButton[class="success"] {{
        background-color: {Colors.SUCCESS};
        color: {Colors.BG_DARK};
        border: none;
        font-weight: 600;
    }}

    QPushButton[class="success"]:hover {{
        background-color: {Colors.SUCCESS_HOVER};
    }}

    /* Danger Button */
    QPushButton[class="danger"] {{
        background-color: {Colors.DANGER};
        color: {Colors.TEXT_PRIMARY};
        border: none;
        font-weight: 600;
    }}

    QPushButton[class="danger"]:hover {{
        background-color: {Colors.DANGER_HOVER};
    }}

    /* Secondary/Info Button */
    QPushButton[class="secondary"], QPushButton[class="info"] {{
        background-color: transparent;
        color: {Colors.PRIMARY};
        border: 1px solid {Colors.PRIMARY};
    }}

    QPushButton[class="secondary"]:hover, QPushButton[class="info"]:hover {{
        background-color: {Colors.PRIMARY_MUTED};
    }}

    /* ========================================
       Line Edits
       ======================================== */

    QLineEdit {{
        font-size: {Fonts.SIZE_BASE}px;
        padding: 10px 12px;
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        background-color: {Colors.BG_SECONDARY};
        color: {Colors.TEXT_PRIMARY};
        selection-background-color: {Colors.PRIMARY_MUTED};
        min-height: 20px;
    }}

    QLineEdit:hover {{
        border-color: {Colors.TEXT_TERTIARY};
    }}

    QLineEdit:focus {{
        border-color: {Colors.BORDER_FOCUS};
        background-color: {Colors.BG_TERTIARY};
    }}

    QLineEdit:disabled {{
        background-color: {Colors.BG_DARK};
        color: {Colors.TEXT_TERTIARY};
    }}

    QLineEdit::placeholder {{
        color: {Colors.TEXT_TERTIARY};
    }}

    /* ========================================
       Combo Boxes
       ======================================== */

    QComboBox {{
        font-size: {Fonts.SIZE_BASE}px;
        padding: 12px 16px;
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        background-color: {Colors.BG_SECONDARY};
        color: {Colors.TEXT_PRIMARY};
        min-height: 24px;
    }}

    QComboBox:hover {{
        border-color: {Colors.TEXT_TERTIARY};
    }}

    QComboBox:focus {{
        border-color: {Colors.BORDER_FOCUS};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 32px;
        padding-right: 8px;
    }}

    QComboBox::down-arrow {{
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid {Colors.TEXT_SECONDARY};
        margin-right: 8px;
    }}

    QComboBox QAbstractItemView {{
        font-size: {Fonts.SIZE_BASE}px;
        background-color: {Colors.BG_SECONDARY};
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        padding: 4px;
        selection-background-color: {Colors.PRIMARY_MUTED};
        selection-color: {Colors.TEXT_PRIMARY};
    }}

    QComboBox QAbstractItemView::item {{
        padding: 10px 16px;
        border-radius: 4px;
        min-height: 28px;
    }}

    QComboBox QAbstractItemView::item:hover {{
        background-color: {Colors.BG_HOVER};
    }}

    /* ========================================
       Spin Boxes
       ======================================== */

    QSpinBox, QDoubleSpinBox {{
        font-size: {Fonts.SIZE_BASE}px;
        padding: 10px 12px;
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        background-color: {Colors.BG_SECONDARY};
        color: {Colors.TEXT_PRIMARY};
    }}

    QSpinBox:hover, QDoubleSpinBox:hover {{
        border-color: {Colors.TEXT_TERTIARY};
    }}

    QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: {Colors.BORDER_FOCUS};
    }}

    QSpinBox::up-button, QDoubleSpinBox::up-button,
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        width: 24px;
        border: none;
        background-color: {Colors.BG_TERTIARY};
    }}

    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
        background-color: {Colors.BG_HOVER};
    }}

    /* ========================================
       Group Boxes
       ======================================== */

    QGroupBox {{
        font-size: {Fonts.SIZE_MD}px;
        font-weight: 600;
        border: 1px solid {Colors.BORDER};
        border-radius: 12px;
        margin-top: 20px;
        padding: 24px 16px 16px 16px;
        background-color: {Colors.BG_SECONDARY};
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 16px;
        top: 8px;
        padding: 0 12px;
        color: {Colors.PRIMARY};
        background-color: {Colors.BG_SECONDARY};
    }}

    /* ========================================
       List Widgets
       ======================================== */

    QListWidget {{
        font-size: {Fonts.SIZE_BASE}px;
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        background-color: {Colors.BG_SECONDARY};
        padding: 8px;
        outline: none;
    }}

    QListWidget::item {{
        padding: 12px 16px;
        border-radius: 6px;
        margin: 2px 0;
        color: {Colors.TEXT_PRIMARY};
    }}

    QListWidget::item:hover {{
        background-color: {Colors.BG_HOVER};
    }}

    QListWidget::item:selected {{
        background-color: {Colors.PRIMARY_MUTED};
        color: {Colors.PRIMARY};
    }}

    /* ========================================
       Text Edit
       ======================================== */

    QTextEdit {{
        font-size: {Fonts.SIZE_SM}px;
        font-family: {Fonts.FAMILY_MONO};
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        background-color: {Colors.BG_SECONDARY};
        color: {Colors.TEXT_PRIMARY};
        padding: 12px;
        selection-background-color: {Colors.PRIMARY_MUTED};
    }}

    /* ========================================
       Progress Bar
       ======================================== */

    QProgressBar {{
        font-size: {Fonts.SIZE_SM}px;
        font-weight: 500;
        border: none;
        border-radius: 8px;
        background-color: {Colors.BG_TERTIARY};
        text-align: center;
        color: {Colors.TEXT_PRIMARY};
        min-height: 24px;
    }}

    QProgressBar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {Colors.PRIMARY_PRESSED},
            stop:1 {Colors.PRIMARY});
        border-radius: 8px;
    }}

    /* ========================================
       Scroll Areas
       ======================================== */

    QScrollArea {{
        border: none;
        background-color: transparent;
    }}

    QScrollBar:vertical {{
        width: 12px;
        background-color: {Colors.BG_SECONDARY};
        border-radius: 6px;
        margin: 4px 2px;
    }}

    QScrollBar::handle:vertical {{
        background-color: {Colors.BORDER};
        border-radius: 5px;
        min-height: 40px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {Colors.TEXT_TERTIARY};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
        border: none;
    }}

    QScrollBar:horizontal {{
        height: 12px;
        background-color: {Colors.BG_SECONDARY};
        border-radius: 6px;
        margin: 2px 4px;
    }}

    QScrollBar::handle:horizontal {{
        background-color: {Colors.BORDER};
        border-radius: 5px;
        min-width: 40px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background-color: {Colors.TEXT_TERTIARY};
    }}

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
        border: none;
    }}

    /* ========================================
       Check Boxes
       ======================================== */

    QCheckBox {{
        font-size: {Fonts.SIZE_BASE}px;
        spacing: 12px;
        color: {Colors.TEXT_PRIMARY};
    }}

    QCheckBox::indicator {{
        width: 22px;
        height: 22px;
        border-radius: 6px;
        border: 2px solid {Colors.BORDER};
        background-color: {Colors.BG_SECONDARY};
    }}

    QCheckBox::indicator:hover {{
        border-color: {Colors.TEXT_TERTIARY};
    }}

    QCheckBox::indicator:checked {{
        background-color: {Colors.PRIMARY};
        border-color: {Colors.PRIMARY};
    }}

    QCheckBox::indicator:checked:hover {{
        background-color: {Colors.PRIMARY_HOVER};
        border-color: {Colors.PRIMARY_HOVER};
    }}

    /* ========================================
       Frames
       ======================================== */

    QFrame[class="card"] {{
        background-color: {Colors.BG_SECONDARY};
        border: 1px solid {Colors.BORDER};
        border-radius: 12px;
    }}

    QFrame[class="status-card"] {{
        background-color: {Colors.BG_TERTIARY};
        border-radius: 8px;
        padding: 12px;
    }}

    /* ========================================
       Splitter
       ======================================== */

    QSplitter::handle {{
        background-color: {Colors.BORDER};
    }}

    QSplitter::handle:horizontal {{
        width: 2px;
    }}

    QSplitter::handle:vertical {{
        height: 2px;
    }}

    /* ========================================
       Tab Widget
       ======================================== */

    QTabWidget::pane {{
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        background-color: {Colors.BG_SECONDARY};
        padding: 8px;
    }}

    QTabBar::tab {{
        font-size: {Fonts.SIZE_BASE}px;
        padding: 12px 24px;
        border: none;
        background-color: transparent;
        color: {Colors.TEXT_SECONDARY};
        border-bottom: 2px solid transparent;
    }}

    QTabBar::tab:hover {{
        color: {Colors.TEXT_PRIMARY};
    }}

    QTabBar::tab:selected {{
        color: {Colors.PRIMARY};
        border-bottom: 2px solid {Colors.PRIMARY};
    }}

    /* ========================================
       Status Bar
       ======================================== */

    QStatusBar {{
        font-size: {Fonts.SIZE_SM}px;
        background-color: {Colors.BG_SECONDARY};
        color: {Colors.TEXT_SECONDARY};
        border-top: 1px solid {Colors.BORDER};
        padding: 8px;
    }}

    /* ========================================
       Tool Tips
       ======================================== */

    QToolTip {{
        font-size: {Fonts.SIZE_SM}px;
        background-color: {Colors.BG_TERTIARY};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER};
        border-radius: 6px;
        padding: 8px 12px;
    }}

    /* ========================================
       Menu Bar & Menus
       ======================================== */

    QMenuBar {{
        font-size: {Fonts.SIZE_BASE}px;
        background-color: {Colors.BG_SECONDARY};
        color: {Colors.TEXT_PRIMARY};
        padding: 4px;
    }}

    QMenuBar::item {{
        padding: 8px 16px;
        border-radius: 6px;
    }}

    QMenuBar::item:selected {{
        background-color: {Colors.BG_HOVER};
    }}

    QMenu {{
        font-size: {Fonts.SIZE_BASE}px;
        background-color: {Colors.BG_SECONDARY};
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        padding: 8px;
    }}

    QMenu::item {{
        padding: 10px 24px;
        border-radius: 6px;
    }}

    QMenu::item:selected {{
        background-color: {Colors.PRIMARY_MUTED};
        color: {Colors.PRIMARY};
    }}

    /* ========================================
       Message Box
       ======================================== */

    QMessageBox {{
        background-color: {Colors.BG_SECONDARY};
    }}

    QMessageBox QLabel {{
        font-size: {Fonts.SIZE_BASE}px;
        color: {Colors.TEXT_PRIMARY};
    }}
    """


def apply_theme(app: QApplication):
    """Apply the premium dark theme to the application."""
    app.setStyleSheet(get_stylesheet())

    # Set application font
    font = QFont("Segoe UI", Fonts.SIZE_BASE)
    app.setFont(font)


def create_shadow_effect(blur_radius: int = 20, offset: tuple = (0, 4),
                         color: str = "#000000", opacity: float = 0.3):
    """Create a drop shadow effect for widgets."""
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(blur_radius)
    shadow.setOffset(offset[0], offset[1])
    shadow.setColor(QColor(color))
    return shadow


# =============================================================================
# Convenience Functions for Component Styling
# =============================================================================

def style_card(widget):
    """Apply card styling to a widget."""
    widget.setProperty("class", "card")
    widget.setGraphicsEffect(create_shadow_effect(24, (0, 8), "#000000", 0.4))


def style_primary_button(button):
    """Style a button as primary."""
    button.setProperty("class", "primary")
    button.style().unpolish(button)
    button.style().polish(button)


def style_success_button(button):
    """Style a button as success."""
    button.setProperty("class", "success")
    button.style().unpolish(button)
    button.style().polish(button)


def style_danger_button(button):
    """Style a button as danger."""
    button.setProperty("class", "danger")
    button.style().unpolish(button)
    button.style().polish(button)


def style_title_label(label):
    """Style a label as title."""
    label.setProperty("class", "title")
    label.style().unpolish(label)
    label.style().polish(label)


def style_section_title(label):
    """Style a label as section title."""
    label.setProperty("class", "section-title")
    label.style().unpolish(label)
    label.style().polish(label)
