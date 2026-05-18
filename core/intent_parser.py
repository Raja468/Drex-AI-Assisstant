import re
from dataclasses import dataclass
from typing import Optional
from loguru import logger


@dataclass
class Intent:
    type: str           # e.g. "open_app", "ai_query", "system_control"
    action: str         # specific action
    target: str = ""    # what to act on
    params: dict = None # extra parameters
    confidence: float = 1.0
    raw: str = ""

    def __post_init__(self):
        if self.params is None:
            self.params = {}


INTENT_PATTERNS = {
    "open_app": [
        (r"(?:open|launch|start|run)\s+(.+)", "open"),
        (r"(?:start up|fire up)\s+(.+)", "open"),
    ],
    "close_app": [
        (r"(?:close|quit|exit|kill)\s+(.+)", "close"),
        (r"(?:shut down|stop)\s+(.+)", "close"),
    ],
    "system_control": [
        (r"(?:set |turn )volume\s+(?:to\s+)?(\d+)", "volume_set"),
        (r"volume\s+(?:up|increase|louder)", "volume_up"),
        (r"volume\s+(?:down|decrease|lower|quieter|mute)", "volume_down"),
        (r"(?:mute|unmute)", "volume_mute"),
        (r"(?:shut\s*down|power\s*off)\s*(?:computer|pc|system)?", "shutdown"),
        (r"(?:restart|reboot)\s*(?:computer|pc|system)?", "restart"),
        (r"(?:sleep|hibernate|suspend)", "sleep"),
        (r"(?:lock|lock\s+screen|lock\s+computer)", "lock"),
        (r"(?:set |change )?brightness\s+(?:to\s+)?(\d+)", "brightness_set"),
        (r"brightness\s+(?:up|increase)", "brightness_up"),
        (r"brightness\s+(?:down|decrease|lower)", "brightness_down"),
        (r"(?:take\s+a?\s*screenshot|screenshot)", "screenshot"),
        (r"(?:empty|clear)\s+(?:recycle\s+bin|trash)", "empty_trash"),
    ],
    "browser": [
        (r"(?:open|go to|navigate to|browse to)\s+(?:website\s+)?(.+\.(?:com|org|net|io|dev|co|uk|gov|edu)\S*)", "open_url"),
        (r"(?:search|google|search for|look up)\s+(.+)", "search"),
        (r"open\s+(?:a\s+)?(?:new\s+)?(?:browser|chrome|firefox|edge|browser\s+tab)", "new_tab"),
        (r"open\s+(?:youtube|yt)\s+(?:and\s+(?:search|play)\s+)?(.+)?", "youtube"),
    ],
    "file_manager": [
        (r"(?:create|make|new)\s+(?:a\s+)?(?:file|document|text file)\s+(?:called\s+|named\s+)?(.+)", "create_file"),
        (r"(?:create|make|new)\s+(?:a\s+)?folder\s+(?:called\s+|named\s+)?(.+)", "create_folder"),
        (r"(?:open|show|display)\s+(?:the\s+)?(?:file\s+)?(.+\.\w+)", "open_file"),
        (r"(?:find|search for|locate)\s+(?:file\s+)?(.+)", "find_file"),
        (r"(?:delete|remove)\s+(?:file\s+|folder\s+)?(.+)", "delete_file"),
    ],
    "memory": [
        (r"(?:remember|save|note)\s+(?:that\s+)?(.+)", "remember"),
        (r"(?:what do you know about|recall|do you remember)\s+(.+)", "recall"),
        (r"(?:forget|delete)\s+(?:that\s+)?(.+)", "forget"),
        (r"(?:my name is|call me|i am|i'm)\s+(\w+)", "set_name"),
    ],
    "small_talk": [
        (r"^(?:hi|hello|hey|yo|sup|what'?s up|howdy)[\s!.?]*$", "greeting"),
        (r"^(?:bye|goodbye|see you|later|take care|cya)[\s!.?]*$", "farewell"),
        (r"^(?:thank(?:s| you)|thx|ty|cheers)[\s!.?]*$", "thanks"),
        (r"^(?:how are you|how'?s it going|you okay)\??$", "how_are_you"),
        (r"(?:what(?:'s| is) your name|who are you)", "identity"),
        (r"(?:what can you do|help|your capabilities|what do you know)", "capabilities"),
    ],
    "media": [
        (r"(?:play|put on)\s+(.+?)(?:\s+on\s+(.+))?$", "play"),
        (r"(?:pause|stop)\s+(?:music|video|playback)?", "pause"),
        (r"(?:next|skip)\s+(?:song|track)?", "next_track"),
        (r"(?:previous|back|prev)\s+(?:song|track)?", "prev_track"),
    ],
    "weather": [
        (r"(?:weather|forecast|temperature|will it rain|is it (?:hot|cold|sunny|raining))\s*(?:in\s+(.+))?", "weather"),
    ],
    "time_date": [
        (r"(?:what(?:'s| is)(?: the)? time|current time|tell me the time)", "current_time"),
        (r"(?:what(?:'s| is)(?: the)? date|today'?s? date|what day is it)", "current_date"),
        (r"(?:set\s+(?:a\s+)?)?(?:timer|alarm|reminder)\s+(?:for\s+)?(.+)", "set_timer"),
    ],
    "personality": [
        (r"(?:switch to|change to|enable|activate|use)\s+(jarvis|friendly|hacker|calm)\s*(?:mode|personality)?", "switch"),
        (r"(?:be more|act more|become more)\s+(friendly|professional|technical|calm)", "switch"),
        (r"(jarvis|friendly|hacker|calm)\s+mode", "switch"),
    ],
}


class IntentParser:
    def __init__(self):
        self._compiled = self._compile_patterns()
        logger.debug("IntentParser loaded {} intent categories", len(INTENT_PATTERNS))

    def _compile_patterns(self) -> dict:
        compiled = {}
        for intent_type, patterns in INTENT_PATTERNS.items():
            compiled[intent_type] = [
                (re.compile(pattern, re.IGNORECASE), action)
                for pattern, action in patterns
            ]
        return compiled

    def parse(self, text: str) -> Intent:
        if not text or not text.strip():
            return Intent(type="empty", action="none", raw=text)

        clean = text.strip()

        for intent_type, patterns in self._compiled.items():
            for pattern, action in patterns:
                match = pattern.search(clean)
                if match:
                    groups = match.groups()
                    target = groups[0].strip() if groups and groups[0] else ""
                    params = {}
                    if len(groups) > 1:
                        params = {f"arg{i}": g.strip() for i, g in enumerate(groups[1:]) if g}

                    intent = Intent(
                        type=intent_type,
                        action=action,
                        target=target,
                        params=params,
                        raw=clean,
                    )
                    logger.debug("Intent parsed: type={} action={} target='{}'",
                                 intent_type, action, target)
                    return intent

        # Default: route to AI
        logger.debug("No pattern matched — routing to AI: '{}'", clean[:60])
        return Intent(type="ai_query", action="generate", target=clean, raw=clean)

    def is_automation(self, intent: Intent) -> bool:
        return intent.type in {
            "open_app", "close_app", "system_control",
            "browser", "file_manager", "media",
        }

    def is_ai_query(self, intent: Intent) -> bool:
        return intent.type in {"ai_query", "weather"}

    def is_memory_op(self, intent: Intent) -> bool:
        return intent.type == "memory"

    def requires_confirmation(self, intent: Intent) -> bool:
        dangerous = {"shutdown", "restart", "sleep", "delete_file", "empty_trash"}
        return intent.action in dangerous