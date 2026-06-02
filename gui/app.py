# ============================================================
#  DREX - AI Desktop Assistant
#  gui/app.py  —  Root Application Window
#
#  WHAT IT DOES:
#  The main CTk window. Wires together all GUI panels:
#  - StatusBar (top)
#  - Sidebar (left)
#  - ChatPanel (center/main)
#  - InputBar (bottom)
#
#  THREAD SAFETY RULE:
#  The Orchestrator runs in background threads.
#  ALL Tkinter updates MUST happen on the main thread.
#  We use self.after() to schedule GUI updates safely.
#  NEVER call CTk widgets from background threads directly.
# ============================================================

import threading
import queue
import customtkinter as ctk
from typing import Optional

from gui.theme import Colors, Fonts, Sizing, Status, CTK_APPEARANCE, CTK_COLOR_THEME
from gui.chat_panel import ChatPanel
from gui.sidebar import Sidebar
from gui.input_bar import InputBar
from gui.status_bar import StatusBar
from gui.settings_modal import SettingsModal
from gui.widgets import Toast
from utils.logger import logger

try:
    from config import APP_NAME
except ImportError:
    APP_NAME = "Drex"


# ─────────────────────────────────────────────────────────────
#  SET UP CUSTOMTKINTER THEME
# ─────────────────────────────────────────────────────────────
ctk.set_appearance_mode(CTK_APPEARANCE)
ctk.set_default_color_theme(CTK_COLOR_THEME)


class DrexApp(ctk.CTk):
    """
    Root application window.

    Responsibilities:
    - Create and layout all GUI panels
    - Connect GUI events to orchestrator
    - Receive orchestrator responses on the main thread safely
    - Manage window lifecycle (open, minimize, close)
    """

    def __init__(self, orchestrator=None):
        super().__init__()
        self.orchestrator = orchestrator

        # Thread-safe queue for receiving responses from background threads
        # Background thread → puts response here
        # Main thread → polls this queue with after()
        self._response_queue = queue.Queue()

        # Current UI state
        self._is_voice_active = False
        self._is_processing   = False

        self._configure_window()
        self._build_layout()
        self._connect_orchestrator()
        self._start_queue_polling()

        logger.info("✅ DrexApp GUI initialized")

    # ──────────────────────────────────────────────────────────
    #  WINDOW CONFIGURATION
    # ──────────────────────────────────────────────────────────

    def _configure_window(self):
        """Set up the main window properties."""
        self.title(f"{APP_NAME} — AI Desktop Assistant")
        self.geometry(f"{Sizing.WINDOW_W}x{Sizing.WINDOW_H}")
        self.minsize(Sizing.MIN_W, Sizing.MIN_H)
        self.configure(fg_color=Colors.BG_DARK)

        # Center on screen
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - Sizing.WINDOW_W) // 2
        y = (sh - Sizing.WINDOW_H) // 2
        self.geometry(f"{Sizing.WINDOW_W}x{Sizing.WINDOW_H}+{x}+{y}")

        # Window close handler
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Set taskbar icon title
        self.iconname(APP_NAME)

    # ──────────────────────────────────────────────────────────
    #  LAYOUT CONSTRUCTION
    # ──────────────────────────────────────────────────────────

    def _build_layout(self):
        """
        Build the main window layout.

        ┌────────────────────────────────────────────┐
        │              STATUS BAR (top)              │  row 0
        ├──────────┬─────────────────────────────────┤
        │          │                                 │
        │ SIDEBAR  │      CHAT PANEL (main)          │  row 1
        │  (left)  │                                 │
        │          ├─────────────────────────────────┤
        │          │       INPUT BAR (bottom)        │  row 2
        └──────────┴─────────────────────────────────┘
        """
        self.grid_rowconfigure(1, weight=1)      # Chat panel expands
        self.grid_columnconfigure(1, weight=1)   # Chat panel expands

        # ── Status Bar ────────────────────────────────────────
        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=0, column=0, columnspan=2, sticky="ew")

        # ── Sidebar ───────────────────────────────────────────
        self.sidebar = Sidebar(
            self,
            orchestrator=self.orchestrator,
            on_nav_change=self._on_nav_change,
        )
        self.sidebar.grid(row=1, column=0, rowspan=2, sticky="ns")

        # ── Chat Panel ────────────────────────────────────────
        self.chat_panel = ChatPanel(self)
        self.chat_panel.grid(row=1, column=1, sticky="nsew")

        # ── Input Bar ─────────────────────────────────────────
        self.input_bar = InputBar(
            self,
            on_submit=self._on_user_input,
            on_voice_toggle=self._on_voice_toggle,
        )
        self.input_bar.grid(row=2, column=1, sticky="ew")

        # Update status bar with AI info
        self.after(1000, self._update_status_bar_ai)

    # ──────────────────────────────────────────────────────────
    #  ORCHESTRATOR CONNECTION
    # ──────────────────────────────────────────────────────────

    def _connect_orchestrator(self):
        """Register this GUI as a response listener with the orchestrator."""
        if not self.orchestrator:
            logger.warning("No orchestrator provided to GUI")
            return

        # Register our callbacks — called from background threads!
        self.orchestrator.register_response_callback(self._on_orchestrator_response)
        self.orchestrator.register_status_callback(self._on_orchestrator_status)
        self.orchestrator.register_stream_callback(self._on_stream_token)
        self.orchestrator.register_voice_input_callback(self._on_voice_input)
        self.orchestrator._is_running = True

        logger.info("GUI connected to orchestrator")

    def _on_orchestrator_response(self, response_text: str, provider: str = None):
        """
        Called by orchestrator (background thread) when it has a response.
        SAFETY: We put it in the queue — main thread picks it up via polling.
        Never touch Tkinter widgets here.
        """
        self._response_queue.put(("response", response_text, provider))

    def _on_orchestrator_status(self, status: str):
        """Called by orchestrator for status updates."""
        self._response_queue.put(("status", status))

    def _on_stream_token(self, token: str):
        """
        Called by orchestrator for each streaming token.
        Thread-safe: queues the token for main-thread delivery.
        """
        self._response_queue.put(("stream_token", token))

    def _on_voice_input(self, text: str):
        """
        Called by orchestrator (background thread) when voice input is transcribed.
        Thread-safe: queues the text for main-thread display.
        This ensures the user's spoken message appears in the chat before the response.
        """
        self._response_queue.put(("voice_input", text))

    def _start_queue_polling(self):
        """
        Poll the response queue every 50ms on the main thread.
        This is the thread-safe bridge between orchestrator and GUI.
        """
        self._poll_queue()

    def _poll_queue(self):
        """Check for pending responses and process them."""
        try:
            while not self._response_queue.empty():
                item = self._response_queue.get_nowait()

                if item[0] == "response":
                    _, response_text, provider = item
                    self._display_response(response_text, provider)

                elif item[0] == "status":
                    _, status_state = item
                    self._set_status(status_state)

                elif item[0] == "stream_token":
                    _, token = item
                    self._handle_stream_token(token)

                elif item[0] == "voice_input":
                    _, text = item
                    self._handle_voice_input(text)

                elif item[0] == "toast":
                    _, msg, kind = item
                    Toast(self, msg, kind=kind)

        except queue.Empty:
            pass
        except Exception as e:
            logger.error(f"Queue polling error: {e}")

        # Schedule next poll
        self.after(50, self._poll_queue)

    def _handle_voice_input(self, text: str):
        """
        Handle voice input on the main thread.
        
        Called when the orchestrator's voice pipeline transcribes speech.
        This method:
          1. Displays the user's spoken message in the chat
          2. Shows the streaming label for the upcoming response
          3. Sets the processing state
        """
        if not text or not text.strip():
            return
        
        logger.info(f"Voice input: '{text}'")
        
        # 1. Display user's spoken message in chat
        self.chat_panel.add_message("user", text)
        
        # 2. Show streaming label for the upcoming response
        self.chat_panel.show_streaming()
        
        # 3. Update processing state
        self._is_processing = True
        self._set_status(Status.PROCESSING)
        self.input_bar.set_processing(True)

    def _handle_stream_token(self, token: str):
        """Handle a streaming token — show live rendering."""
        if token == "__DREX_STREAM_START__":
            self.chat_panel.show_streaming()
        elif token == "__DREX_STREAM_END__":
            self.chat_panel.finish_streaming()
        else:
            self.chat_panel.update_streaming(token)

    # ──────────────────────────────────────────────────────────
    #  USER INPUT HANDLING
    # ──────────────────────────────────────────────────────────

    def _on_user_input(self, text: str):
        """
        Called when user submits text (Enter or send button).
        Runs on main thread.
        """
        if not text.strip():
            return

        if self._is_processing and self.orchestrator:
            self.orchestrator.cancel_pending_generation()
            if self.chat_panel._streaming_label:
                self.chat_panel.finish_streaming()

        self._is_processing = True
        logger.info(f"GUI input: '{text}'")

        # 1. Display user message immediately
        self.chat_panel.add_message("user", text)

        # 2. Show streaming label (orchestrator may also send START sentinel)
        self.chat_panel.show_streaming()

        # 3. Update status
        self._set_status(Status.PROCESSING)
        self.input_bar.set_processing(True)

        # 4. Send to orchestrator in background thread
        def process_in_background():
            if self.orchestrator:
                self.orchestrator.process(text, voice_response=False)
            else:
                # Demo mode — no orchestrator
                self._response_queue.put((
                    "response", f"Echo: {text}", "demo"
                ))

        thread = threading.Thread(
            target=process_in_background,
            daemon=True,
            name="DrexProcessThread"
        )
        thread.start()

    def _display_response(self, response_text: str, provider: str = None):
        """
        Display Drex's response in the chat.
        Always called on the main thread via queue polling.

        DEDUP LOGIC — prevents duplicate response bubbles:

        There are two paths that can create an assistant bubble:
          1. finish_streaming() — converts the streaming label into a bubble
          2. add_message("assistant", ...) — adds a standalone bubble

        We must ensure EXACTLY ONE bubble per response. The flag
        _streaming_bubble_created tracks whether path 1 already fired
        (either from __DREX_STREAM_END__ or from our finish_streaming call).

        Scenarios:
          A) Streaming active + has text → finish_streaming creates bubble → skip add_message
          B) Streaming active + no text  → finish_streaming destroys label → add_message fallback
          C) Streaming already finalized by __DREX_STREAM_END__ → _streaming_bubble_created=True → skip
          D) No streaming at all → add_message with response_text
        """
        # Step 1: Finalize streaming if still active
        if self.chat_panel._streaming_label:
            self.chat_panel.finish_streaming(provider or "")

        # Step 2: Decide whether to add a fallback message bubble
        # _streaming_bubble_created is True if finish_streaming() already
        # created a bubble (either just now, or earlier via __DREX_STREAM_END__)
        if self.chat_panel._streaming_bubble_created:
            # A bubble was already created by finish_streaming — do NOT duplicate
            logger.debug("Streaming bubble already exists — skipping fallback")
        elif response_text:
            # No bubble was created — show the full response as a message bubble
            self.chat_panel.hide_typing()
            self.chat_panel.add_message("assistant", response_text, provider or "")

        # Update status and re-enable input
        self._set_status(Status.IDLE)
        self.input_bar.set_processing(False)
        self._is_processing = False

        # Update session stats
        self._update_session_info()
        self.input_bar.focus()

    # ──────────────────────────────────────────────────────────
    #  VOICE CONTROL
    # ──────────────────────────────────────────────────────────

    def _on_voice_toggle(self):
        """Toggle voice listening on/off."""
        if not self.orchestrator:
            Toast(self, "No orchestrator connected", kind="error")
            return

        if self._is_voice_active:
            self._stop_voice()
        else:
            self._start_voice()

    def _start_voice(self):
        """Start voice listening."""
        self._is_voice_active = True
        self.input_bar.set_listening(True)
        self._set_status(Status.LISTENING)

        def start_in_thread():
            if self.orchestrator:
                self.orchestrator.start_voice_listening()

        threading.Thread(target=start_in_thread, daemon=True).start()
        Toast(self, "Listening... Speak to Drex!", kind="info")

    def _stop_voice(self):
        """Stop voice listening."""
        self._is_voice_active = False
        self.input_bar.set_listening(False)
        self._set_status(Status.IDLE)

        if self.orchestrator:
            self.orchestrator.stop_voice_listening()

    # ──────────────────────────────────────────────────────────
    #  NAVIGATION
    # ──────────────────────────────────────────────────────────

    def _on_nav_change(self, section: str):
        """Handle sidebar navigation button clicks."""
        logger.debug(f"Nav change: {section}")

        if section == "settings":
            self._open_settings()
        elif section == "memory":
            self._show_memory_panel()
        elif section == "help":
            self._show_help()
        elif section == "chat":
            pass  # Default view

    def _open_settings(self):
        """Open the settings modal dialog."""
        memory = getattr(self.orchestrator, "db", None) if self.orchestrator else None
        SettingsModal(
            self,
            memory=memory,
            orchestrator=self.orchestrator,
            on_save=self._on_settings_saved,
        )

    def _on_settings_saved(self):
        """Called after settings are saved."""
        Toast(self, "Settings saved! Restart Drex for API key changes.", kind="success")
        self.sidebar.refresh_status()
        self.after(1000, self._update_status_bar_ai)

    def _show_memory_panel(self):
        """Show memory/conversation history."""
        if not self.orchestrator or not hasattr(self.orchestrator, "db"):
            Toast(self, "Memory system not available", kind="warning")
            return

        db = self.orchestrator.db
        facts = db.get_facts()
        prefs = db.get_all_preferences()

        if not facts and not prefs:
            Toast(self, "No memories stored yet — start chatting!", kind="info")
            return

        summary_parts = []
        if prefs.get("user_name"):
            summary_parts.append(f"Your name: {prefs['user_name']}")
        if facts:
            summary_parts.append(f"Facts I know: {len(facts)}")
            for f in facts[:3]:
                summary_parts.append(f"  • {f['key']}: {f['value']}")

        self.chat_panel.add_message(
            "assistant",
            "Here's what I remember:\n" + "\n".join(summary_parts)
        )

    def _show_help(self):
        """Show help information."""
        help_text = (
            "Here's what I can do:\n"
            "• 🚀 Open apps — 'Open Chrome', 'Launch Spotify'\n"
            "• 🔍 Search web — 'Search for Python tutorials'\n"
            "• 📺 YouTube — 'Search YouTube for lo-fi music'\n"
            "• 📸 Screenshots — 'Take a screenshot'\n"
            "• 🔊 Volume — 'Volume up', 'Volume down', 'Mute'\n"
            "• 🕐 Time/Date — 'What time is it?', 'What's today's date?'\n"
            "• 📁 Files — 'Open my Downloads folder'\n"
            "• 🤖 AI chat — Ask me anything!\n"
            "• 🧠 Memory — 'My name is Ahmed' — I'll remember!"
        )
        self.chat_panel.add_message("assistant", help_text)

    # ──────────────────────────────────────────────────────────
    #  STATUS & INFO UPDATES
    # ──────────────────────────────────────────────────────────

    def _set_status(self, state: str):
        """Update the status bar (safe to call from any thread via queue)."""
        self.status_bar.set_status(state)

    def _update_session_info(self):
        """Update message count in status bar."""
        count = self.chat_panel.message_count
        self.status_bar.set_session_info(count)

    def _update_status_bar_ai(self):
        """Update the AI model indicator in the status bar."""
        if self.orchestrator and hasattr(self.orchestrator, "ai_router"):
            status = self.orchestrator.ai_router.get_status_text()
            self.status_bar.set_ai_model(status)
        else:
            self.status_bar.set_ai_model("⚠ No AI configured")

    # ──────────────────────────────────────────────────────────
    #  WINDOW LIFECYCLE
    # ──────────────────────────────────────────────────────────

    def _on_close(self):
        """Handle window close — gracefully shut down everything."""
        logger.info("GUI close requested")

        # Stop voice if active
        if self._is_voice_active and self.orchestrator:
            self.orchestrator.stop_voice_listening()

        # Shut down orchestrator
        if self.orchestrator:
            shutdown_thread = threading.Thread(
                target=self.orchestrator.shutdown,
                daemon=True
            )
            shutdown_thread.start()
            shutdown_thread.join(timeout=2.0)

        self.destroy()

    def run(self):
        """Start the GUI event loop. Blocks until window is closed."""
        logger.info("Starting GUI event loop")
        self.mainloop()


# ─────────────────────────────────────────────────────────────
#  STANDALONE DEMO  (run gui/app.py directly to test UI)
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    from utils.logger import setup_logger
    setup_logger()

    print("🖥️  Starting Drex GUI in demo mode (no orchestrator)...")
    print("   Type in the chat box to test the UI")
    print("   Settings button opens the settings modal")

    app = DrexApp(orchestrator=None)

    # Add demo messages to show how it looks
    def add_demo():
        app.chat_panel.add_message("user", "Open Chrome")
        app.after(500, lambda: app.chat_panel.add_message(
            "assistant", "Opening Chrome now!"
        ))
        app.after(1200, lambda: app.chat_panel.add_message(
            "user", "What is machine learning?"
        ))
        app.after(2000, lambda: app.chat_panel.add_message(
            "assistant",
            "Machine learning is a branch of artificial intelligence where systems learn "
            "from data to improve their performance on tasks without being explicitly programmed.\n\n"
            "Key types include:\n"
            "• Supervised learning — learns from labeled examples\n"
            "• Unsupervised learning — finds patterns in unlabeled data\n"
            "• Reinforcement learning — learns via rewards and penalties"
        ))

    app.after(300, add_demo)
    app.run()
