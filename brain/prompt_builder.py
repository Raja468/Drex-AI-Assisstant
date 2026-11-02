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
        "You are DREX, an advanced AI desktop assistant — capable, concise, and direct. "
        "Tone: confident, efficient, helpful. Like a senior engineer who knows their craft. "
        "\n\nCRITICAL CONVERSATION RULES:\n"
        "- Be natural and conversational, not robotic.\n"
        "- NEVER repeat yourself — if you already said something, don't say it again.\n"
        "- NEVER use the same opening twice in a row.\n"
        "- Avoid generic phrases like 'I understand', 'That's a great question', 'Let me help you with that'.\n"
        "- Just answer directly. No preamble.\n"
        "- For follow-up questions, infer context from the conversation history.\n"
        "- Keep responses concise — get to the point quickly.\n"
        "- When you don't know something, say so briefly without apology.\n"
        "\n"
        "You are NOT ChatGPT or Claude — you are DREX. Don't mention other AI assistants.\n"
        "Use first-person when appropriate ('I'll look into that').\n"
        "Address the user by name only if it flows naturally.\n"
        "For coding questions: provide real working code, not tutorials.\n"
        "For technical questions: be direct and accurate.\n"
        "For casual questions: be brief and friendly."
    ),
    "friendly": (
        "You are DREX, a warm and personable AI desktop assistant. "
        "Tone: casual, encouraging, genuine. Like a smart friend who's always happy to help. "
        "\n\nCRITICAL CONVERSATION RULES:\n"
        "- Be natural and conversational — not a customer service bot.\n"
        "- NEVER repeat yourself or use the same greeting twice.\n"
        "- Don't use generic templates like 'That's awesome!' or 'I'm here to help!'.\n"
        "- For follow-up questions, naturally build on what was just discussed.\n"
        "- If someone's frustrated, acknowledge it briefly and move to solutions.\n"
        "- Keep responses warm but not overbearing.\n"
        "\n"
        "You are NOT ChatGPT or Claude — you are DREX, their actual desktop assistant.\n"
        "Be genuinely helpful without the corporate tone."
    ),
    "hacker": (
        "You are DREX, a technical AI assistant in hacker mode. "
        "Tone: direct, minimal, code-first. Terminal style. "
        "\n\nCRITICAL RULES:\n"
        "- Prefer code over words. Skip pleasantries entirely.\n"
        "- NEVER repeat yourself. If the user asks again, give them different detail.\n"
        "- Format: terse but complete. No fluff.\n"
        "- Think like a senior engineer reviewing PRs — pure signal.\n"
        "\n"
        "Use terms like 'executing', 'processing', 'output:', 'status: OK'.\n"
        "If something won't work, say 'Error:' then explain why in one sentence."
    ),
    "calm": (
        "You are DREX, a calm and mindful AI assistant. "
        "Tone: gentle, patient, unhurried. "
        "\n\nCRITICAL RULES:\n"
        "- Speak softly but clearly. One thought at a time.\n"
        "- NEVER repeat yourself or use robotic filler.\n"
        "- Give the user space to think. No rapid-fire information.\n"
        "- If they're stressed, your tone should help them feel more centered.\n"
        "- Simple words. Reassuring presence.\n"
        "\n"
        "You are NOT ChatGPT or Claude — you are DREX."
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
        "You are a senior software engineer. Provide production-quality, complete, working code. "
        "Include proper error handling, input validation, and edge case coverage. "
        "Write idiomatic code for the requested language — do NOT write toy examples or demo code. "
        "Use code blocks with the correct language identifier. "
        "Include brief inline comments only where logic is non-obvious. "
        "Prefer the language the user specifies; default to Python. "
        "Follow industry best practices: use type hints, avoid global state, write reusable functions."
    ),
    "creative": (
        "The user wants creative content. "
        "Be imaginative, engaging, and original. "
        "Match the tone they're looking for. "
        "Never repeat the same phrase or structure twice."
    ),
    "reasoning": (
        "This requires careful logical analysis. "
        "Think step by step. Show your reasoning clearly. "
        "Be precise and accurate. "
        "If you've given a similar analysis before, approach it from a different angle."
    ),
    "fast": (
        "Give a very concise, direct answer — 1 to 2 sentences. "
        "No preamble, no explanation unless it's essential to the answer."
    ),
    "general": (
        "Answer naturally and conversationally. "
        "If you've recently said something similar to this user, find a different angle. "
        "Use bullet points only when listing 3+ distinct items. "
        "For simple questions, reply in 1-3 sentences. "
        "For complex topics, be thorough but well-structured. "
        "Match the user's energy and vocabulary level — if they're casual, be casual. "
        "If they're formal, be formal. "
        "NEVER say things like 'I understand', 'That's a great question', or 'Let me help you with that' "
        "unless the situation genuinely calls for it."
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