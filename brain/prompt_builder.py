# ============================================================
#  DREX - AI Desktop Assistant
#  brain/prompt_builder.py  —  AI Prompt Assembler + Personality Engine
#
#  Personalities:
#  - jarvis    : Professional, precise, efficient (default)
#  - friendly  : Casual, warm, encouraging, uses light humor
#  - hacker    : Technical, terminal-style, minimal
#  - calm      : Minimal, zen, short responses
# ============================================================

from utils.logger import logger

try:
    from config import get_config
    cfg = get_config()
except ImportError:
    cfg = None


# ─────────────────────────────────────────────────────────────
#  PERSONALITY SYSTEM PROMPTS
# ─────────────────────────────────────────────────────────────

PERSONALITY_PROMPTS = {
    "jarvis": (
        "You are DREX, an advanced AI desktop assistant — precise, professional, and efficient. "
        "Think of yourself as Jarvis from Iron Man. "
        "You are calm under pressure, highly capable, and always one step ahead. "
        "Speak formally but not stiffly. Be concise. Never waste words. "
        "When you don't know something, say so directly. "
        "Always address the user respectfully."
    ),
    "friendly": (
        "You are DREX, a warm and friendly AI desktop assistant. "
        "You're like a smart, helpful friend who genuinely cares. "
        "Use casual language, light humor when appropriate, and be encouraging. "
        "Keep responses conversational and easy to read. "
        "Use 'Hey!', 'Sure thing!', 'Great question!' naturally — but don't overdo it. "
        "Make the user feel comfortable and supported."
    ),
    "hacker": (
        "You are DREX, a technical AI assistant operating in hacker mode. "
        "Be extremely precise and technical. Use terminal-style language. "
        "Prefer code over explanations. Skip pleasantries entirely. "
        "Format: direct, minimal, efficient. "
        "Use terms like 'executing', 'processing', 'output:', 'status: OK'. "
        "Think like a senior engineer — no fluff, pure signal."
    ),
    "calm": (
        "You are DREX, a calm and mindful AI assistant. "
        "Speak gently, clearly, and without rushing. "
        "Keep responses short and peaceful. No jargon, no urgency. "
        "Be like a patient teacher or a quiet advisor. "
        "One thought at a time. Simple words. Reassuring tone."
    ),
}

# Personality display names and confirmations
PERSONALITY_META = {
    "jarvis": {
        "name": "Jarvis Mode",
        "confirm": "Switching to Jarvis mode. Professional and precise, at your service.",
        "icon": "🤖",
    },
    "friendly": {
        "name": "Friendly Mode",
        "confirm": "Switching to friendly mode! Great to chat with you! 😊",
        "icon": "😊",
    },
    "hacker": {
        "name": "Hacker Mode",
        "confirm": ">> MODE: HACKER | Initializing... | Status: ACTIVE",
        "icon": "💻",
    },
    "calm": {
        "name": "Calm Mode",
        "confirm": "Switching to calm mode. I am here, whenever you need me.",
        "icon": "🧘",
    },
}

# ─────────────────────────────────────────────────────────────
#  TASK-SPECIFIC PROMPT ADDITIONS
# ─────────────────────────────────────────────────────────────

TASK_PROMPTS = {
    "coding": (
        "The user is asking a coding/programming question. "
        "Provide clean, working code with brief explanations. "
        "Use code blocks. Prefer Python unless another language is specified."
    ),
    "creative": (
        "The user wants creative content. "
        "Be imaginative, engaging, and original. "
        "Match the tone they're looking for."
    ),
    "reasoning": (
        "This requires careful logical analysis. "
        "Think step by step. Show your reasoning clearly. "
        "Be precise and accurate."
    ),
    "fast": (
        "Give a very concise, direct answer. "
        "No more than 2-3 sentences unless more is truly necessary."
    ),
    "general": (
        "Answer helpfully and concisely. "
        "Use bullet points only when listing 3+ items."
    ),
}


# ─────────────────────────────────────────────────────────────
#  PROMPT BUILDER CLASS
# ─────────────────────────────────────────────────────────────

class PromptBuilder:
    """
    Constructs optimized prompts for each AI model call.
    Injects personality, memory, and task-specific instructions.
    """

    def __init__(self, memory_manager=None):
        self.memory = memory_manager
        self._personality = self._load_personality()
        logger.info("✅ PromptBuilder initialized")

    def _load_personality(self) -> str:
        """Load personality from config or default to jarvis."""
        try:
            from config import get_config
            return get_config().app.personality
        except Exception:
            return "jarvis"

    def set_personality(self, mode: str) -> str:
        """
        Switch personality mode.
        Returns confirmation message to show the user.
        """
        mode = mode.lower().strip()
        if mode not in PERSONALITY_PROMPTS:
            available = ", ".join(PERSONALITY_PROMPTS.keys())
            return f"Unknown mode '{mode}'. Available: {available}"

        self._personality = mode

        # Save to config and .env preference
        try:
            from config import get_config
            get_config().app.personality = mode
        except Exception:
            pass

        # Save to memory if available
        if self.memory:
            try:
                self.memory.set_preference("personality_mode", mode)
            except Exception:
                pass

        meta = PERSONALITY_META[mode]
        logger.info("🎭 Personality switched to: {}", meta["name"])
        return meta["confirm"]

    def get_personality(self) -> str:
        """Return current personality mode name."""
        return self._personality

    def get_personality_display(self) -> str:
        """Return display name of current personality."""
        return PERSONALITY_META.get(self._personality, {}).get("name", "Jarvis Mode")

    def build(
        self,
        user_input: str,
        session_id: str,
        task_type: str = "general",
        extra_context: str = ""
    ) -> dict:
        """
        Build a complete prompt ready to send to any AI API.

        Returns:
            Dict with 'system' and 'messages' keys
        """
        # 1. Build system prompt with personality
        system_prompt = self._build_system_prompt(task_type, extra_context)

        # 2. Get conversation history from memory
        history = []
        if self.memory:
            try:
                limit = cfg.ai.max_history if cfg else 20
                history = self.memory.get_recent_context(session_id, limit=limit)
            except Exception:
                history = []

        # 3. Add current user input at the end
        messages = history + [{"role": "user", "content": user_input}]

        logger.debug(
            "Prompt built | personality={} | task={} | history={} msgs",
            self._personality, task_type, len(history)
        )

        return {
            "system": system_prompt,
            "messages": messages,
        }

    def _build_system_prompt(self, task_type: str, extra_context: str = "") -> str:
        """Assemble the system prompt from personality + task + memory."""
        parts = []

        # 1. Personality base prompt
        personality_prompt = PERSONALITY_PROMPTS.get(
            self._personality,
            PERSONALITY_PROMPTS["jarvis"]
        )
        parts.append(personality_prompt)

        # 2. Task-specific addition
        task_addition = TASK_PROMPTS.get(task_type, TASK_PROMPTS["general"])
        parts.append(f"\nTask context: {task_addition}")

        # 3. User facts from memory
        if self.memory:
            try:
                facts = self.memory.get_facts()
                if facts:
                    facts_text = "User Facts:\n" + "\n".join(
                        [f"- {f['key']}: {f['value']}" for f in facts[:10]]
                    )
                    parts.append(f"\n{facts_text}")
            except Exception:
                pass

        # 4. User preferences from memory
        if self.memory:
            try:
                prefs = self.memory.get_all_preferences()
                if prefs:
                    skip_keys = {"gemini_api_key", "groq_api_key", "openrouter_api_key",
                                 "cerebras_api_key", "personality_mode"}
                    pref_lines = [
                        f"- {k}: {v}" for k, v in prefs.items()
                        if k not in skip_keys
                    ]
                    if pref_lines:
                        parts.append("\nUser preferences:\n" + "\n".join(pref_lines))
            except Exception:
                pass

        # 5. Extra context
        if extra_context:
            parts.append(f"\nAdditional context: {extra_context}")

        return "\n".join(parts)

    def build_simple(self, user_input: str, task_type: str = "general") -> dict:
        """Build a prompt WITHOUT memory (fast path)."""
        return {
            "system": self._build_system_prompt(task_type),
            "messages": [{"role": "user", "content": user_input}],
        }

    def extract_facts_from_response(self, user_input: str, response: str) -> list[dict]:
        """
        Extract memory facts from the interaction.
        Currently checks for name mentions only.
        Full implementation in Phase 2.
        """
        facts = []
        import re

        # Detect name: "my name is X" or "call me X"
        name_match = re.search(
            r"(?:my name is|call me|i am|i'm)\s+([A-Z][a-z]+)",
            user_input,
            re.IGNORECASE
        )
        if name_match:
            name = name_match.group(1).capitalize()
            facts.append({"category": "identity", "key": "name", "value": name})

        return facts