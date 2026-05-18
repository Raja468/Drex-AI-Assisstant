# ============================================================
#  DREX - AI Desktop Assistant
#  gui/theme.py  —  Design System & Visual Identity
#
#  All colors, fonts, spacing, and animation constants
#  live here. Change here → changes everywhere.
#
#  DESIGN PHILOSOPHY:
#  Deep charcoal base with electric cyan accents.
#  Clean, technical, AI-forward. Like a terminal upgraded
#  into a premium product. Every pixel intentional.
# ============================================================


# ─────────────────────────────────────────────────────────────
#  COLOR PALETTE
# ─────────────────────────────────────────────────────────────

class Colors:
    # ── Backgrounds ───────────────────────────────────────────
    BG_DARKEST   = "#0A0C0F"   # Outer shell, deepest background
    BG_DARK      = "#0F1117"   # Main window background
    BG_PANEL     = "#141820"   # Panels, sidebars
    BG_CARD      = "#1A2030"   # Cards, message bubbles
    BG_ELEVATED  = "#1E2535"   # Hovered cards, inputs
    BG_BORDER    = "#252D3D"   # Subtle borders, dividers

    # ── Accent — Electric Cyan ────────────────────────────────
    ACCENT       = "#00D4FF"   # Primary accent — electric cyan
    ACCENT_DIM   = "#0099CC"   # Slightly dimmed accent
    ACCENT_DARK  = "#004D66"   # Background-safe accent tint
    ACCENT_GLOW  = "#00D4FF22" # Very transparent for glow effects

    # ── User vs AI bubble colors ──────────────────────────────
    USER_BG      = "#1A2A3A"   # User message background
    USER_BORDER  = "#2A4A6A"   # User message border
    AI_BG        = "#141E2A"   # AI message background
    AI_BORDER    = "#1E3040"   # AI message border

    # ── Text ──────────────────────────────────────────────────
    TEXT_PRIMARY   = "#E8EDF5"  # Main text — slightly warm white
    TEXT_SECONDARY = "#8A95A8"  # Labels, hints, timestamps
    TEXT_MUTED     = "#4A5568"  # Placeholder, disabled text
    TEXT_ACCENT    = "#00D4FF"  # Highlighted/accent text

    # ── Status colors ─────────────────────────────────────────
    SUCCESS      = "#00D084"   # Green — success, connected
    WARNING      = "#FFB800"   # Amber — warning, processing
    ERROR        = "#FF4D6D"   # Red — error, disconnected
    INFO         = "#7B8FFF"   # Purple-blue — informational

    # ── Listening indicator ───────────────────────────────────
    LISTENING    = "#FF4D6D"   # Red pulse when mic is active

    # ── Button states ─────────────────────────────────────────
    BTN_PRIMARY        = "#00D4FF"
    BTN_PRIMARY_HOVER  = "#33DDFF"
    BTN_PRIMARY_PRESS  = "#0099CC"
    BTN_SECONDARY      = "#1E2535"
    BTN_SECONDARY_HOVER= "#252D3D"
    BTN_DANGER         = "#FF4D6D"
    BTN_DANGER_HOVER   = "#FF6B85"


# ─────────────────────────────────────────────────────────────
#  TYPOGRAPHY
# ─────────────────────────────────────────────────────────────

class Fonts:
    # Font families — Segoe UI is clean on Windows
    # Falls back gracefully on other systems
    PRIMARY   = "Segoe UI"
    MONO      = "Consolas"       # For code blocks
    DISPLAY   = "Segoe UI Light" # For headers/titles

    # Sizes
    XS   = 10
    SM   = 11
    BASE = 13
    MD   = 14
    LG   = 16
    XL   = 20
    XXL  = 26
    HERO = 32

    # Weight names for CTk
    NORMAL = "normal"
    BOLD   = "bold"

    # Pre-built tuples for CTkFont or tkFont
    TITLE       = (DISPLAY, XL,   BOLD)
    HEADER      = (PRIMARY, MD,   BOLD)
    BODY        = (PRIMARY, BASE, NORMAL)
    BODY_BOLD   = (PRIMARY, BASE, BOLD)
    SMALL       = (PRIMARY, SM,   NORMAL)
    CAPTION     = (PRIMARY, XS,   NORMAL)
    CODE        = (MONO,    SM,   NORMAL)
    INPUT       = (PRIMARY, MD,   NORMAL)
    BUTTON      = (PRIMARY, SM,   BOLD)
    TIMESTAMP   = (PRIMARY, XS,   NORMAL)


# ─────────────────────────────────────────────────────────────
#  SPACING & SIZING
# ─────────────────────────────────────────────────────────────

class Spacing:
    XS   = 4
    SM   = 8
    MD   = 12
    LG   = 16
    XL   = 24
    XXL  = 32
    HERO = 48


class Sizing:
    # Window
    WINDOW_W     = 1000
    WINDOW_H     = 700
    MIN_W        = 780
    MIN_H        = 500

    # Sidebar
    SIDEBAR_W    = 220
    SIDEBAR_W_COLLAPSED = 60

    # Chat
    CHAT_MSG_MAX_W   = 640  # Max width of a message bubble
    CHAT_PADDING     = 16
    CHAT_MSG_PADDING = 14
    CHAT_AVATAR_SIZE = 32

    # Input bar
    INPUT_HEIGHT = 52
    INPUT_RADIUS = 26

    # Buttons
    BTN_HEIGHT       = 36
    BTN_RADIUS       = 8
    BTN_ICON_SIZE    = 32

    # Status bar
    STATUS_HEIGHT    = 32

    # Corner radius values
    RADIUS_SM  = 6
    RADIUS_MD  = 10
    RADIUS_LG  = 16
    RADIUS_XL  = 20
    RADIUS_PILL = 999


# ─────────────────────────────────────────────────────────────
#  ANIMATION DURATIONS (ms)
# ─────────────────────────────────────────────────────────────

class Anim:
    FAST    = 150   # Quick feedback (hover, press)
    NORMAL  = 250   # Standard transitions
    SLOW    = 400   # Deliberate reveals
    PULSE   = 1000  # Pulse animations (listening indicator)


# ─────────────────────────────────────────────────────────────
#  STATUS STATES
# ─────────────────────────────────────────────────────────────

class Status:
    IDLE        = "idle"
    LISTENING   = "listening"
    PROCESSING  = "processing"
    SPEAKING    = "speaking"
    ERROR       = "error"

    # Display labels and colors for each state
    DISPLAY = {
        IDLE:       ("Ready",       Colors.TEXT_SECONDARY, "●"),
        LISTENING:  ("Listening...", Colors.LISTENING,     "●"),
        PROCESSING: ("Thinking...", Colors.WARNING,        "◉"),
        SPEAKING:   ("Speaking...", Colors.ACCENT,         "▶"),
        ERROR:      ("Error",       Colors.ERROR,          "✕"),
    }


# ─────────────────────────────────────────────────────────────
#  CUSTOMTKINTER THEME CONFIG
# Used with: ctk.set_appearance_mode() and ctk.set_default_color_theme()
# ─────────────────────────────────────────────────────────────

CTK_APPEARANCE  = "dark"
CTK_COLOR_THEME = "dark-blue"   # Built-in CTk theme as base

# Override values passed to individual CTk widgets
WIDGET_DEFAULTS = {
    "corner_radius": Sizing.RADIUS_MD,
    "border_width":  1,
    "border_color":  Colors.BG_BORDER,
}
