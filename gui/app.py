# ============================================================
#  DREX - AI Desktop Assistant
#  gui/app.py - Root application window
#
#  Layout:
#    +--------------------------------------------------+
#    |                TopBar (56px)                     |
#    +----------+---------------------------------------+
#    | Sidebar  |          ChatPanel                    |
#    | (260px)  |                                       |
#    |          |---------------------------------------|
#    |          |            InputBar                   |
#    +----------+---------------------------------------+
# ============================================================

import threading
import queue
import time
import customtkinter as ctk

from gui.theme import Colors, Sizing, Fonts, Icons, CTK_APPEARANCE, CTK_COLOR_THEME
from gui.chat_panel import ChatPanel
from gui.sidebar import Sidebar
from gui.input_bar import InputBar
from gui.top_bar import TopBar
from gui.settings_modal import SettingsModal
from gui.widgets import Toast
from utils.logger import logger

try:
    from config import APP_NAME
except ImportError:
    APP_NAME = "DREX"


ctk.set_appearance_mode(CTK_APPEARANCE)
ctk.set_default_color_theme(CTK_COLOR_THEME)


class DrexApp(ctk.CTk):
    """Premium desktop shell for DREX."""

    def __init__(self, orchestrator=None):
        super().__init__()
        self.orchestrator = orchestrator

        self._response_queue = queue.Queue()
        self._is_voice_active = False
        self._is_processing   = False
        self._ready           = False
        self._start_time      = time.time()
        self._last_user_message = ""
        self._stream_start_time = 0.0
        self._stream_timeout_ms = 30000
        self._send_seq        = 0

        self._configure_window()
        self._build_layout()
        self._connect_orchestrator()
        self._start_queue_polling()

        self.after(100, self._check_loading_state)

        logger.info("DrexApp GUI initialized")

    # -----------------------------------------------------
    #  Window
    # -----------------------------------------------------

    def _configure_window(self):
        self.title(f"{APP_NAME} - AI Desktop Assistant")
        self.geometry(f"{Sizing.WINDOW_W}x{Sizing.WINDOW_H}")
        self.minsize(Sizing.MIN_W, Sizing.MIN_H)
        self.configure(fg_color=Colors.BG_BASE)

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - Sizing.WINDOW_W) // 2
        y = (sh - Sizing.WINDOW_H) // 2
        self.geometry(f"{Sizing.WINDOW_W}x{Sizing.WINDOW_H}+{x}+{y}")

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.iconname(APP_NAME)

    def _build_layout(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Top bar spans full width
        self.top_bar = TopBar(
            self,
            on_title_change=self._on_title_changed,
            on_settings=self._open_settings,
            on_theme_toggle=self._on_theme_toggle,
            on_provider_click=self._open_settings,
        )
        self.top_bar.grid(row=0, column=0, columnspan=2, sticky="ew")

        # Sidebar (left, spans chat+input rows)
        self.sidebar = Sidebar(
            self,
            on_nav_change=self._on_nav_change,
            on_chat_select=self._on_chat_select,
        )
        self.sidebar.grid(row=1, column=0, rowspan=2, sticky="ns")

        # Chat panel
        self.center_panel = ctk.CTkFrame(self, fg_color=Colors.BG_BASE, corner_radius=0)
        self.center_panel.grid(row=1, column=1, sticky="nsew")
        self.center_panel.grid_rowconfigure(0, weight=1)
        self.center_panel.grid_columnconfigure(0, weight=1)

        self.chat_panel = ChatPanel(
            self.center_panel,
            on_suggestion=self._on_suggestion_click,
            on_regenerate=self._on_regenerate,
        )
        self.chat_panel.grid(row=0, column=0, sticky="nsew")

        # Input bar
        self.input_bar = InputBar(
            self,
            on_submit=self._on_user_input,
            on_voice_toggle=self._on_voice_toggle,
            on_attach=self._on_attach,
            on_model_click=self._open_settings,
        )
        self.input_bar.grid(row=2, column=1, sticky="ew")

        self.after(1000, self._update_status_bar_ai)

    # -----------------------------------------------------
    #  Orchestrator wiring
    # -----------------------------------------------------

    def _connect_orchestrator(self):
        if not self.orchestrator:
            logger.warning("No orchestrator provided to GUI")
            return

        self.orchestrator.register_response_callback(self._on_orchestrator_response)
        self.orchestrator.register_status_callback(self._on_orchestrator_status)
        self.orchestrator.register_stream_callback(self._on_stream_token)
        self.orchestrator.register_voice_input_callback(self._on_voice_input)
        self.orchestrator._is_running = True

        voice_agent = getattr(self.orchestrator, "_voice_engine", None)
        if voice_agent and hasattr(voice_agent, "on_state_change"):
            voice_agent.on_state_change = lambda state: self.after(
                0, lambda s=state: self._on_voice_state_changed(s)
            )

        self.after(800, self._load_chat_list)
        logger.info("GUI connected to orchestrator")

    def _on_orchestrator_response(self, response_text, provider=None):
        self._response_queue.put(("response", response_text, provider))

    def _on_orchestrator_status(self, status):
        self._response_queue.put(("status", status))

    def _on_stream_token(self, token):
        self._response_queue.put(("stream_token", token))

    def _on_voice_input(self, text):
        self._response_queue.put(("voice_input", text))

    def _start_queue_polling(self):
        self._poll_queue()

    def _poll_queue(self):
        try:
            while not self._response_queue.empty():
                item = self._response_queue.get_nowait()
                kind = item[0]

                if kind == "response":
                    _, response_text, provider = item
                    self._display_response(response_text, provider)
                elif kind == "status":
                    _, status = item
                    self._set_status(status)
                elif kind == "stream_token":
                    _, token = item
                    self._handle_stream_token(token)
                elif kind == "voice_input":
                    _, text = item
                    self._handle_voice_input(text)
                elif kind == "toast":
                    _, msg, k = item
                    Toast(self, msg, kind=k)
        except queue.Empty:
            pass
        except Exception as e:
            logger.error(f"Queue polling error: {e}")

        self.after(100, self._poll_queue)

    # -----------------------------------------------------
    #  Handlers
    # -----------------------------------------------------

    def _on_suggestion_click(self, prompt: str):
        # Prefill the input bar so the user can edit before sending.
        try:
            self.input_bar.insert_text(prompt)
            self.input_bar.focus()
        except Exception:
            pass

    def _on_regenerate(self):
        """Re-process the last user message for regeneration."""
        if self._last_user_message and not self._is_processing:
            self._on_user_input(self._last_user_message)

    def _handle_voice_input(self, text):
        if not text or not text.strip():
            return
        logger.info(f"Voice input: '{text}'")
        self.chat_panel.add_message("user", text)
        self.chat_panel.show_streaming()
        self._is_processing = True
        self._set_status("processing")
        self.input_bar.set_processing(True)

    def _handle_stream_token(self, token):
        if token == "__DREX_STREAM_START__":
            self._stream_start_time = time.time()
            self._start_stream_timeout_watchdog()
            self.chat_panel.show_streaming()
        elif token == "__DREX_STREAM_END__":
            logger.info("LIFECYCLE | STREAM COMPLETE (GUI)")
            self._stream_start_time = 0.0
            # Do NOT finalize here — _display_response() handles the
            # finish/cancel when it receives the response callback.
            # Finalizing here would set _streaming_label = None, causing
            # _display_response to think no streaming happened and add a
            # duplicate assistant bubble via add_message().
        else:
            self.chat_panel.update_streaming(token)

    def _start_stream_timeout_watchdog(self):
        """Periodically check if streaming exceeded timeout."""
        def check():
            if self._stream_start_time == 0.0:
                return
            elapsed_ms = (time.time() - self._stream_start_time) * 1000
            if elapsed_ms > self._stream_timeout_ms:
                self.chat_panel.finish_streaming()
                self._set_status("idle")
                self.input_bar.set_processing(False)
                self._is_processing = False
            elif self._stream_start_time > 0.0:
                self.after(1000, check)
        self.after(1000, check)

    def _on_user_input(self, text):
        if not text.strip():
            return

        if self._is_processing and self.orchestrator:
            try:
                self.orchestrator.cancel_pending_generation()
            except Exception:
                pass
            if self.chat_panel._streaming_label:
                self.chat_panel.finish_streaming()

        self._is_processing = True
        self._send_seq += 1
        send_seq = self._send_seq
        self._last_user_message = text
        logger.info(f"LIFECYCLE | SEND | '{text[:80]}'")
        try:
            self.chat_panel.add_message("user", text)
            self.chat_panel.show_streaming()
        except Exception as e:
            # A display failure must never block the request pipeline.
            logger.error(f"Chat display failed, request continues: {e}")
        self._set_status("processing")
        self.input_bar.set_processing(True)

        def process_in_background():
            try:
                if self.orchestrator:
                    result = self.orchestrator.process(text, voice_response=False)
                else:
                    result = None
                    self._response_queue.put(
                        ("response", f"Echo: {text}", "demo")
                    )
                # process() returned without delivering a response
                # (dedup early-exit, empty result). If this send is still
                # the latest one, release the UI so it can never wedge.
                if not result and send_seq == self._send_seq and self._is_processing:
                    logger.warning("LIFECYCLE | EMPTY RESULT | releasing UI state")
                    self._response_queue.put(("response", "", "none"))
            except Exception as e:
                logger.error(f"Processing thread failed: {e}")
                if send_seq == self._send_seq:
                    self._response_queue.put(
                        ("response",
                         "I hit an internal error processing that. Please try again.",
                         "system")
                    )

        threading.Thread(
            target=process_in_background,
            daemon=True,
            name="DrexProcessThread",
        ).start()

    def _display_response(self, response_text, provider=None):
        # Capture BEFORE calling finish/cancel — both of those set
        # _streaming_label back to None, so checking the attribute
        # afterward always looked like "no streaming happened" and
        # caused every response to be added a second time via
        # add_message() right after finish_streaming() had already
        # displayed it. That was producing duplicate assistant bubbles.
        had_streaming = self.chat_panel._streaming_label is not None

        if had_streaming:
            if response_text:
                self.chat_panel.finish_streaming(provider or "", final_text=response_text)
            else:
                # No content ever arrived (dedup/empty generation) —
                # drop the empty streaming bubble instead of rendering blank.
                self.chat_panel.cancel_streaming()

        if response_text and not had_streaming:
            self.chat_panel.hide_typing()
            self.chat_panel.add_message("assistant", response_text, provider or "")

        self._set_status("idle")
        self.input_bar.set_processing(False)
        self._is_processing = False
        self.input_bar.focus()
        logger.info("LIFECYCLE | READY")

    # -----------------------------------------------------
    #  Voice
    # -----------------------------------------------------

    def _on_voice_toggle(self):
        if not self.orchestrator:
            Toast(self, "Voice engine unavailable", kind="error")
            return
        if self._is_voice_active:
            self._stop_voice()
        else:
            self._start_voice()

    def _start_voice(self):
        self._is_voice_active = True
        self.input_bar.set_listening(True)
        self._set_status("listening")

        def start_in_thread():
            if self.orchestrator:
                self.orchestrator.start_voice_listening()

        threading.Thread(target=start_in_thread, daemon=True).start()
        Toast(self, "Listening...", kind="info")

    def _stop_voice(self):
        self._is_voice_active = False
        self.input_bar.set_listening(False)
        self._set_status("idle")
        if self.orchestrator:
            try:
                self.orchestrator.stop_voice_listening()
            except Exception:
                pass

    def _on_voice_state_changed(self, state):
        try:
            state_str = str(state).lower()
            self._set_status(state_str if state_str in {"idle", "listening", "processing", "speaking"} else "idle")
        except Exception as e:
            logger.debug(f"Voice state update error: {e}")

    # -----------------------------------------------------
    #  Nav / Modals
    # -----------------------------------------------------

    def _on_nav_change(self, section):
        logger.debug(f"Nav change: {section}")
        if section == "settings":
            self._open_settings()
        elif section == "new_chat":
            self._new_chat()

    def _abandon_active_generation(self, reason: str):
        """Explicitly abandon an in-flight generation (user navigated away).

        This is an intended cancellation: it prevents a late response from
        being rendered into — or saved under — the wrong session.
        """
        if self._is_processing and self.orchestrator:
            logger.info(f"LIFECYCLE | CANCEL | {reason}")
            try:
                self.orchestrator.cancel_pending_generation()
            except Exception:
                pass
        if self.chat_panel._streaming_label:
            self.chat_panel.cancel_streaming()
        self._stream_start_time = 0.0
        self._is_processing = False
        self.input_bar.set_processing(False)

    def _on_chat_select(self, session_id: str):
        """Load a previous session into the chat panel with AI context."""
        if not self.orchestrator or session_id == self.orchestrator.session_id:
            return
        self._abandon_active_generation("session switch")
        self.orchestrator.switch_session(session_id)
        self.chat_panel.clear_messages()
        try:
            db = self.orchestrator._ensure_db()
            messages = db.get_session_messages(session_id, limit=100)
            for msg in messages:
                self.chat_panel.add_message(
                    role=msg["role"],
                    content=msg["content"],
                    timestamp=msg.get("timestamp", ""),
                )
            title = db.get_session_title(session_id) or f"Chat {session_id[:6]}"
            self.top_bar.set_title(title)
        except Exception as e:
            logger.debug(f"Failed to load session messages: {e}")
        self._load_chat_list()
        self.chat_panel.update_idletasks()
        self.chat_panel._scroll_to_bottom(force=True)

    def _load_chat_list(self):
        """Populate sidebar with sessions from the database."""
        if not self.orchestrator:
            return
        try:
            db = self.orchestrator._ensure_db()
            sessions = db.get_all_sessions()
            current_id = self.orchestrator.session_id
            self.sidebar.clear_chats()
            for s in sessions:
                sid = s["id"]
                title = s.get("summary") or db.get_session_title(sid) or f"Chat {sid[:6]}"
                if title:
                    title = title[:50]
                self.sidebar.add_chat(
                    chat_id=sid,
                    title=title,
                    preview="",
                    timestamp=None,
                    active=(sid == current_id),
                )
        except Exception as e:
            logger.debug(f"Failed to load chat list: {e}")

    def _on_title_changed(self, title):
        logger.debug(f"Title changed: {title}")

    def _new_chat(self):
        self._abandon_active_generation("new chat")
        if self.orchestrator:
            self.orchestrator.new_session()

        self.chat_panel.clear_messages()
        self.top_bar.set_title("New Chat")
        self.input_bar.focus()
        self._load_chat_list()

    def _open_settings(self):
        memory = getattr(self.orchestrator, "db", None) if self.orchestrator else None
        SettingsModal(
            self,
            memory=memory,
            orchestrator=self.orchestrator,
            on_save=self._on_settings_saved,
        )

    def _on_settings_saved(self):
        Toast(self, "Settings saved. Restart DREX for API key changes.", kind="success")
        self.after(500, self._update_status_bar_ai)

    def _on_attach(self):
        Toast(self, "Attachments coming soon", kind="info")

    def _on_theme_toggle(self):
        # Palette locked to spec; toggle reserved for future light theme.
        Toast(self, "Light theme coming soon", kind="info")

    # -----------------------------------------------------
    #  Status
    # -----------------------------------------------------

    def _set_status(self, state):
        # Reserved: status is reflected via input state + top bar chips.
        _ = state

    def _update_status_bar_ai(self):
        if not (self.orchestrator and hasattr(self.orchestrator, "ai_router")):
            return
        try:
            router = self.orchestrator.ai_router
            status = router.get_status() if hasattr(router, "get_status") else {}
            default = status.get("default", "")
            providers = status.get("providers", {}) or {}
            info = providers.get(default, {}) if default else {}
            provider_name = default.capitalize() if default and default != "none" else ""
            model = info.get("model", "") if isinstance(info, dict) else ""

            self.top_bar.set_provider(provider=provider_name, model=model)
            self.input_bar.set_model(model or "Auto")
        except Exception as e:
            logger.debug(f"Status bar update failed: {e}")

    # -----------------------------------------------------
    #  Lifecycle
    # -----------------------------------------------------

    def _check_loading_state(self):
        elapsed = (time.time() - self._start_time) * 1000
        if elapsed > 500 and not self._ready:
            self._show_loading()
        self.after(500, self._check_ready)

    def _check_ready(self):
        if self._ready:
            return
        if (
            self.orchestrator
            and getattr(self.orchestrator, "_is_running", False)
        ):
            self._hide_loading()
            self._ready = True
            logger.info(f"GUI ready in {(time.time() - self._start_time)*1000:.0f}ms")
        else:
            self.after(500, self._check_ready)

    def _show_loading(self):
        if getattr(self, "_loading_overlay", None) is not None:
            return
        overlay = ctk.CTkFrame(self, fg_color=Colors.BG_BASE, corner_radius=0)
        overlay.grid(row=0, column=0, rowspan=3, columnspan=2, sticky="nsew")
        overlay.grid_rowconfigure(0, weight=1)
        overlay.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(overlay, fg_color="transparent")
        inner.grid(row=0, column=0)

        ctk.CTkLabel(
            inner,
            text=Icons.SPARKLE,
            width=72,
            height=72,
            font=ctk.CTkFont(family=Fonts.ICON, size=34),
            fg_color=Colors.ACCENT,
            text_color=Colors.TEXT_INVERSE,
            corner_radius=36,
        ).pack(pady=(0, 16))

        ctk.CTkLabel(
            inner,
            text="Starting DREX...",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=Colors.TEXT_SECONDARY,
        ).pack(pady=(12, 0))

        self._loading_overlay = overlay
        self._loading_overlay.tkraise()

    def _hide_loading(self):
        overlay = getattr(self, "_loading_overlay", None)
        if overlay is not None:
            try:
                overlay.destroy()
            except Exception:
                pass
            self._loading_overlay = None

    def _on_close(self):
        logger.info("GUI close requested")
        if self._is_voice_active and self.orchestrator:
            try:
                self.orchestrator.stop_voice_listening()
            except Exception:
                pass
        try:
            self.destroy()
        except Exception:
            pass

    def run(self):
        logger.info("Starting DrexApp mainloop")
        self.mainloop()


# ===============================================================
#  STANDALONE DEMO
# ===============================================================

if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    from utils.logger import setup_logger
    setup_logger()

    print("Starting Drex GUI in demo mode (no orchestrator)...")
    app = DrexApp(orchestrator=None)

    def add_demo():
        app.chat_panel.add_message("user", "Open Chrome")
        app.after(500, lambda: app.chat_panel.add_message(
            "assistant", "Opening Chrome now."
        ))
        app.after(1200, lambda: app.chat_panel.add_message(
            "user", "What is machine learning?"
        ))
        app.after(2000, lambda: app.chat_panel.add_message(
            "assistant",
            "Machine learning is a branch of AI where systems learn "
            "from data to improve their performance on tasks without being "
            "explicitly programmed.\n\nKey types:\n"
            "- Supervised learning\n"
            "- Unsupervised learning\n"
            "- Reinforcement learning"
        ))

    app.after(300, add_demo)
    app.run()