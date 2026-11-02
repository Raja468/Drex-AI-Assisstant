# ============================================================
#  DREX - AI Desktop Assistant
#  gui/theme.py - Premium Desktop Design System
#
#  Minimal, professional, ChatGPT / Claude / Linear vibe.
#  Dark surfaces, teal accent, Fluent icon system.
# ============================================================


# -------------------------------------------------------------
#  COLOR PALETTE
# -------------------------------------------------------------

class Colors:
    # Base surfaces — a gentle elevation ramp, warm-neutral dark
    BG_BASE     = "#0F0F10"   # main window background (deepest)
    BG_SURFACE  = "#161617"   # secondary panels (top bar, input row)
    BG_SIDEBAR  = "#131314"   # sidebar column
    BG_ELEVATED = "#1C1C1E"   # cards, chat bubbles, input container
    BG_OVERLAY  = "#252527"   # hover state
    BG_PRESSED  = "#2E2E31"   # active/pressed state

    # Aliases kept for legacy call sites
    BG_CARD    = BG_ELEVATED

    # Accent (teal)
    ACCENT       = "#14B8A6"
    ACCENT_HOVER = "#17C7B4"   # brighter on hover (feels responsive)
    ACCENT_PRESS = "#0F9C8B"   # dips on press
    ACCENT_DIM   = "#0D7F71"
    ACCENT_LIGHT = "#5EEAD4"
    ACCENT_SUBTLE = "#123A36"  # translucent-feel accent wash for chips/focus

    # Text
    TEXT_PRIMARY   = "#F5F5F6"
    TEXT_SECONDARY = "#ABABB2"
    TEXT_MUTED     = "#6E6E76"
    TEXT_FAINT     = "#4A4A50"
    TEXT_INVERSE   = "#08110F"

    # Borders
    BORDER        = "#2A2A2D"
    BORDER_LIGHT  = "#37373B"
    BORDER_FOCUS  = ACCENT

    # Chat bubble colors
    USER_BG      = "#14B8A6"   # accent for user messages
    USER_BORDER  = "#14B8A6"
    USER_TEXT    = "#06120F"
    DREX_BG      = "#1C1C1E"   # assistant messages
    DREX_BORDER  = "#2A2A2D"
    DREX_TEXT    = "#F5F5F6"

    # Status
    SUCCESS = "#22C55E"
    WARNING = "#F59E0B"
    ERROR   = "#EF4444"
    INFO    = ACCENT

    # Semantic
    LISTENING = "#EF4444"

    # Provider dot colors
    PROVIDER_GEMINI     = "#4285F4"
    PROVIDER_GROQ       = "#22C55E"
    PROVIDER_OPENROUTER = "#8B5CF6"
    PROVIDER_CEREBRAS   = "#F59E0B"

    # Button roles
    BTN_PRIMARY         = ACCENT
    BTN_PRIMARY_HOVER   = ACCENT_HOVER
    BTN_SECONDARY       = BG_ELEVATED
    BTN_SECONDARY_HOVER = BG_OVERLAY
    BTN_DANGER          = ERROR
    BTN_DANGER_HOVER    = "#DC2626"

    # Scrollbar
    SCROLLBAR       = "#2E2E31"
    SCROLLBAR_HOVER = "#3C3C40"


# -------------------------------------------------------------
#  TYPOGRAPHY
# -------------------------------------------------------------

class Fonts:
    # "Segoe UI Variable Text" is the Windows 11 UI face and reads cleaner at
    # small sizes than plain Segoe UI.  The tuple fallbacks ensure tkinter
    # degrades gracefully when a face is not installed.
    PRIMARY = "Segoe UI Variable Text"
    PRIMARY_FALLBACK = ("Segoe UI Variable Text", "Segoe UI", "Helvetica")
    DISPLAY = "Segoe UI Variable Display"
    DISPLAY_FALLBACK = ("Segoe UI Variable Display", "Segoe UI", "Helvetica")
    MONO    = "Cascadia Code"
    MONO_FALLBACK = ("Cascadia Code", "Consolas", "Courier New")
    ICON    = "Segoe Fluent Icons"   # monoline Windows 11 icon font

    XS   = 11
    SM   = 12
    BASE = 13
    MD   = 14
    LG   = 16
    XL   = 19
    XXL  = 25
    HERO = 30

    NORMAL   = "normal"
    MEDIUM   = "normal"   # tk has no medium; kept for intent/readability
    BOLD     = "bold"

    TITLE     = (DISPLAY, XL,  BOLD)
    HEADER    = (PRIMARY, MD,  BOLD)
    BODY      = (PRIMARY, MD,  NORMAL)
    BODY_BOLD = (PRIMARY, MD,  BOLD)
    SMALL     = (PRIMARY, SM,  NORMAL)
    CAPTION   = (PRIMARY, XS,  NORMAL)
    CODE      = (MONO,    SM,  NORMAL)
    INPUT     = (PRIMARY, MD,  NORMAL)
    BUTTON    = (PRIMARY, SM,  BOLD)
    TIMESTAMP = (PRIMARY, XS,  NORMAL)


# -------------------------------------------------------------
#  SPACING
# -------------------------------------------------------------

class Spacing:
    XXS  = 2
    XS   = 4
    SM   = 8
    MD   = 12
    LG   = 16
    XL   = 20
    XXL  = 28
    HERO = 40


# -------------------------------------------------------------
#  SIZING
# -------------------------------------------------------------

class Sizing:
    WINDOW_W = 1300
    WINDOW_H = 840
    MIN_W    = 980
    MIN_H    = 640

    SIDEBAR_W = 272
    TOPBAR_H  = 58

    # Chat
    CHAT_MSG_MAX_W   = 720
    CHAT_PADDING     = 36
    CHAT_MSG_PADDING = 18
    CHAT_AVATAR_SIZE = 36

    # Input
    INPUT_MIN_H  = 52
    INPUT_MAX_H  = 180
    INPUT_RADIUS = 20

    # Buttons
    BTN_HEIGHT    = 38
    BTN_RADIUS    = 10
    BTN_ICON_SIZE = 36

    # Corner radius
    RADIUS_XS   = 4
    RADIUS_SM   = 7
    RADIUS_MD   = 10
    RADIUS_LG   = 14
    RADIUS_XL   = 18
    RADIUS_PILL = 999


# -------------------------------------------------------------
#  ANIMATION DURATIONS (ms)
# -------------------------------------------------------------

class Anim:
    FAST   = 120
    NORMAL = 200
    SLOW   = 360
    PULSE  = 1000


# -------------------------------------------------------------
#  STATUS
# -------------------------------------------------------------

class Status:
    IDLE       = "idle"
    LISTENING  = "listening"
    PROCESSING = "processing"
    SPEAKING   = "speaking"
    ERROR      = "error"

    DISPLAY = {
        IDLE:       ("Ready",         Colors.TEXT_SECONDARY, "○"),
        LISTENING:  ("Listening",     Colors.LISTENING,      "●"),
        PROCESSING: ("Thinking",      Colors.WARNING,        "◎"),
        SPEAKING:   ("Speaking",      Colors.ACCENT,         "▶"),
        ERROR:      ("Error",         Colors.ERROR,          "✕"),
    }


# -------------------------------------------------------------
#  CUSTOMTKINTER DEFAULTS
# -------------------------------------------------------------

CTK_APPEARANCE  = "dark"
CTK_COLOR_THEME = "dark-blue"

WIDGET_DEFAULTS = {
    "corner_radius": Sizing.RADIUS_MD,
    "border_width":  0,
    "border_color":  Colors.BORDER,
}


# -------------------------------------------------------------
#  ICONS  (Segoe Fluent Icons — Windows 11 monoline icon font)
#
#  A single consistent icon language replaces the old mix of
#  emoji and geometric glyphs. Every codepoint below is a real
#  Segoe Fluent Icons glyph, all rendered at a uniform width.
# -------------------------------------------------------------

class Icons:
    # Codepoints are defined explicitly so the source stays readable and
    # encoding-safe. Each maps to a Segoe Fluent Icons glyph.

    # Brand / assistant
    SPARKLE   = chr(0xE945)   # spark / lightbulb — assistant mark
    ROBOT     = chr(0xE99A)

    # Actions
    SEND      = chr(0xE724)   # send (paper plane)
    MIC       = chr(0xE720)   # microphone
    MIC_OFF   = chr(0xEC54)   # microphone off
    STOP      = chr(0xE71A)   # stop (filled square)
    ATTACH    = chr(0xE723)   # paperclip
    ADD       = chr(0xE710)   # plus
    SEARCH    = chr(0xE721)
    SETTINGS  = chr(0xE713)   # gear
    COPY      = chr(0xE8C8)
    REFRESH   = chr(0xE72C)   # regenerate / retry
    EDIT      = chr(0xE70F)   # pencil
    PIN       = chr(0xE718)   # pin
    CLOCK     = chr(0xE823)   # recent / history
    CHAT      = chr(0xE8BD)   # conversation bubble
    CHEVRON_DOWN  = chr(0xE70D)
    CHEVRON_RIGHT = chr(0xE76C)
    THEME     = chr(0xE706)   # brightness / theme toggle
    FOLDER    = chr(0xE8B7)   # projects
    DOWNLOAD  = chr(0xE896)
    PLUGIN    = chr(0xEA86)   # puzzle / extensions
    USER      = chr(0xE77B)
    MORE      = chr(0xE712)   # ellipsis (horizontal)
    CHECK     = chr(0xE73E)
    CLOSE     = chr(0xE711)
    WARNING   = chr(0xE7BA)
    INFO      = chr(0xE946)
    ERROR     = chr(0xEA39)


def icon_font(size: int = 16):
    """Build a CTkFont for the Fluent icon set (lazy — needs a root window)."""
    import customtkinter as ctk
    return ctk.CTkFont(family=Fonts.ICON, size=size)


def ui_font(size: int = 13, weight: str = "normal", display: bool = False):
    """Convenience factory for the primary UI face."""
    import customtkinter as ctk
    family = Fonts.DISPLAY if display else Fonts.PRIMARY
    return ctk.CTkFont(family=family, size=size, weight=weight)
