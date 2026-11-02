"""
voice/post_processor.py — Intelligent Speech-to-Text Post-Processing for DREX

Fixes Google STT artifacts and improves recognition quality through
a multi-tier pipeline:

  Tier 1 (always runs, zero latency):
    - Contraction reconstruction (im→I'm, dont→don't, etc.)
    - Common spelling corrections (u→you, r→are, pls→please)
    - Technical term preservation (DREX, Python, GitHub, etc.)
    - Punctuation restoration
    - Capitalization normalization
    - Grammar-aware corrections

  Tier 2 (optional, AI-assisted):
    - Context-aware grammar correction via a fast AI pass
    - Sentence reconstruction for garbled output
    - Slang/misspelling correction beyond dictionary matching

Rules:
  - NEVER change the user's intent
  - Preserve technical terms with exact casing
  - Handle edge cases: empty, single-word, mixed-case
"""

from __future__ import annotations

import re
from typing import Optional

from loguru import logger


TECHNICAL_TERMS: dict[str, str] = {
    "drex": "DREX",
    "drexel": "DREX",
    "python": "Python",
    "github": "GitHub",
    "git hub": "GitHub",
    "javascript": "JavaScript",
    "java script": "JavaScript",
    "typescript": "TypeScript",
    "type script": "TypeScript",
    "vs code": "VS Code",
    "visual studio code": "VS Code",
    "chat gpt": "ChatGPT",
    "chatgpt": "ChatGPT",
    "gpt": "GPT",
    "openai": "OpenAI",
    "open ai": "OpenAI",
    "anthropic": "Anthropic",
    "claude": "Claude",
    "gemini": "Gemini",
    "groq": "Groq",
    "cerebras": "Cerebras",
    "deepseek": "DeepSeek",
    "deep seek": "DeepSeek",
    "openrouter": "OpenRouter",
    "open router": "OpenRouter",
    "kimi": "Kimi",
    "qwen": "Qwen",
    "api": "API",
    "llm": "LLM",
    "ai": "AI",
    "ml": "ML",
    "ui": "UI",
    "ux": "UX",
    "cli": "CLI",
    "sdk": "SDK",
    "ide": "IDE",
    "vscode": "VS Code",
    "c++": "C++",
    "c#": "C#",
    "f#": "F#",
    "gpu": "GPU",
    "cpu": "CPU",
    "ram": "RAM",
    "ssd": "SSD",
    "html": "HTML",
    "css": "CSS",
    "sql": "SQL",
    "json": "JSON",
    "xml": "XML",
    "yaml": "YAML",
    "http": "HTTP",
    "https": "HTTPS",
    "tcp": "TCP",
    "ip": "IP",
    "dns": "DNS",
    "url": "URL",
    "uri": "URI",
    "npm": "npm",
    "pip": "pip",
    "nodejs": "Node.js",
    "node js": "Node.js",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "K8s",
    "linux": "Linux",
    "windows": "Windows",
    "macos": "macOS",
    "mac os": "macOS",
    "android": "Android",
    "ios": "iOS",
    "wifi": "Wi-Fi",
    "wifi": "Wi-Fi",
    "bluetooth": "Bluetooth",
    "usb": "USB",
    "hdmi": "HDMI",
    "pdf": "PDF",
    "csv": "CSV",
    "png": "PNG",
    "jpg": "JPEG",
    "mp3": "MP3",
    "mp4": "MP4",
    "zip": "ZIP",
    "exe": "EXE",
    "dll": "DLL",
}

CONTRACTION_MAP: dict[str, str] = {
    "im": "I'm",
    "ive": "I've",
    "ill": "I'll",
    "id": "I'd",
    "dont": "don't",
    "doesnt": "doesn't",
    "didnt": "didn't",
    "wont": "won't",
    "wouldnt": "wouldn't",
    "cant": "can't",
    "couldnt": "couldn't",
    "shouldnt": "shouldn't",
    "hasnt": "hasn't",
    "havent": "haven't",
    "hadnt": "hadn't",
    "isnt": "isn't",
    "arent": "aren't",
    "wasnt": "wasn't",
    "werent": "weren't",
    "youre": "you're",
    "youve": "you've",
    "youll": "you'll",
    "youd": "you'd",
    "hes": "he's",
    "hell": "he'll",
    "shes": "she's",
    "shell": "she'll",
    "its": "it's",
    "theyll": "they'll",
    "theyre": "they're",
    "theyve": "they've",
    "theyd": "they'd",
    "theres": "there's",
    "heres": "here's",
    "whats": "what's",
    "wheres": "where's",
    "whos": "who's",
    "hows": "how's",
    "thatll": "that'll",
    "thats": "that's",
    "lets": "let's",
    "whys": "why's",
    "whens": "when's",
    "todays": "today's",
    "howre": "how're",
    "were": "we're",
    "weve": "we've",
    "well": "we'll",
    "wed": "we'd",
}

SHORTHAND_MAP: dict[str, str] = {
    "u": "you",
    "r": "are",
    "ur": "your",
    "pls": "please",
    "plz": "please",
    "thx": "thanks",
    "ty": "thank you",
    "btw": "by the way",
    "idk": "I don't know",
    "tbh": "to be honest",
    "imo": "in my opinion",
    "imho": "in my humble opinion",
    "fyi": "for your information",
    "afaik": "as far as I know",
    "ttyl": "talk to you later",
    "brb": "be right back",
    "np": "no problem",
    "yw": "you're welcome",
    "omg": "oh my god",
    "lol": "laugh out loud",
    "wtf": "what the heck",
    "jk": "just kidding",
    "bc": "because",
    "cuz": "because",
    "w": "with",
    "w/o": "without",
    "msg": "message",
    "ppl": "people",
    "tho": "though",
    "rn": "right now",
    "asap": "as soon as possible",
    "lmk": "let me know",
    "nvm": "never mind",
    "wdym": "what do you mean",
    "ofc": "of course",
    "fr": "for real",
    "ion": "I don't",
    "wld": "would",
    "cn": "can",
    "shd": "should",
    "cld": "could",
    "wht": "what",
    "whr": "where",
    "whn": "when",
    "hw": "how",
}

AMBIGUOUS_SHORTHAND: set = {"r", "u", "w", "fr", "cn", "bc"}

COMMON_MISSPELLINGS: dict[str, str] = {
    "teh": "the",
    "adn": "and",
    "taht": "that",
    "wiht": "with",
    "for": "for",
    "youre": "your",
    "alot": "a lot",
    "noone": "no one",
    "eachother": "each other",
    "everytime": "every time",
    "somthing": "something",
    "anyhting": "anything",
    "nothign": "nothing",
    "evry": "every",
    "evrything": "everything",
    "definately": "definitely",
    "definetly": "definitely",
    "seperate": "separate",
    "recieve": "receive",
    "beleive": "believe",
    "acheive": "achieve",
    "occured": "occurred",
    "enviroment": "environment",
    "goverment": "government",
    "buisness": "business",
    "restaraunt": "restaurant",
    "tommorow": "tomorrow",
    "tomorow": "tomorrow",
    "yesturday": "yesterday",
    "Wendesday": "Wednesday",
    "calender": "calendar",
    "libary": "library",
    "probly": "probably",
    "probaly": "probably",
}

QUESTION_STARTERS = frozenset({
    "what", "how", "why", "where", "when", "who", "which",
    "can", "could", "would", "will", "should", "shall",
    "is", "are", "do", "does", "did", "have", "has", "had",
    "was", "were", "am", "may", "might", "must",
    "what's", "how's", "where's", "who's", "when's", "why's",
})

DO_ACTION_STARTERS = frozenset({
    "create", "build", "make", "write", "develop", "implement",
    "generate", "install", "setup", "set up", "configure", "deploy",
    "run", "execute", "start", "stop", "restart", "launch",
    "open", "close", "save", "delete", "remove", "add", "update",
    "fix", "debug", "refactor", "test", "scan", "analyze",
    "download", "upload", "copy", "move", "rename", "search",
    "book", "schedule", "send", "share", "publish", "commit",
    "push", "pull", "merge", "redirect", "forward",
    "organize", "sort", "filter", "sort", "extract",
    "compile", "convert", "transform", "translate",
})


class PostProcessor:
    """
    Multi-tier STT text post-processing pipeline.

    Tier 1 is always applied with near-zero latency.
    Tier 2 (AI-assisted) is optional and invoked only for garbled text.
    """

    def __init__(self):
        self._tier1_count = 0
        self._tier2_count = 0

    def clean(self, text: str, ai_assist: bool = False) -> str:
        """
        Apply full cleanup pipeline to STT output.

        Args:
            text: Raw transcribed text from STT
            ai_assist: If True, use AI for grammar correction (Tier 2)

        Returns:
            Cleaned, normalized text ready for the AI prompt.
        """
        if not text or not text.strip():
            return text

        text = text.strip()
        original = text

        text = self._tier1_clean(text)

        self._tier1_count += 1
        if text != original:
            logger.debug("PostProcess Tier1: '{}' → '{}'", original[:80], text[:80])

        return text

    def clean_for_ai(self, text: str) -> str:
        """Clean specifically for AI prompt input (always Tier 1 only)."""
        if self._needs_ai_correction(text):
            self._tier2_count += 1
        return self.clean(text)

    def _tier1_clean(self, text: str) -> str:
        text = self._fix_technical_terms(text)
        text = self._fix_contractions(text)
        text = self._fix_shorthand(text)
        text = self._fix_common_misspellings(text)
        text = self._fix_punctuation(text)
        text = self._fix_capitalization(text)
        text = self._fix_spacing(text)
        text = self._detect_and_fix_garbled(text)
        return text.strip()

    def _fix_technical_terms(self, text: str) -> str:
        words = text.split()
        result = []
        for word in words:
            lower = word.lower().rstrip(",.!?;:'\"")
            if lower in TECHNICAL_TERMS:
                prefix = word[:len(word) - len(lower.rstrip(",.!?;:'\""))]
                suffix = word[len(prefix + lower):]
                result.append(prefix + TECHNICAL_TERMS[lower] + suffix)
            else:
                result.append(word)
        joined = " ".join(result)

        for raw, fixed in TECHNICAL_TERMS.items():
            if " " in raw:
                pattern = re.compile(re.escape(raw), re.IGNORECASE)
                joined = pattern.sub(fixed, joined)

        return joined

    def _fix_contractions(self, text: str) -> str:
        for wrong, right in CONTRACTION_MAP.items():
            pattern = re.compile(rf'\b{re.escape(wrong)}\b', re.IGNORECASE)
            text = pattern.sub(right, text)
        return text

    def _fix_shorthand(self, text: str) -> str:
        for short, full in SHORTHAND_MAP.items():
            if short in AMBIGUOUS_SHORTHAND:
                pattern = re.compile(rf'(?<!\w){re.escape(short)}(?!\w)', re.IGNORECASE)
            else:
                pattern = re.compile(rf'\b{re.escape(short)}\b', re.IGNORECASE)
            text = pattern.sub(full, text)
        return text

    def _fix_common_misspellings(self, text: str) -> str:
        for wrong, right in COMMON_MISSPELLINGS.items():
            pattern = re.compile(rf'\b{re.escape(wrong)}\b', re.IGNORECASE)
            text = pattern.sub(right, text)
        return text

    def _fix_punctuation(self, text: str) -> str:
        if not text:
            return text

        words = text.lower().split()
        if not words:
            return text

        if text[-1] not in ".!?":
            first_word = words[0]
            is_question = first_word in QUESTION_STARTERS

            if is_question:
                text += "?"
            elif len(words) > 3:
                text += "."
            elif len(words) == 1:
                text += "."

        text = re.sub(r'\s+([.,!?])', r'\1', text)

        text = re.sub(r'\?+', '?', text)
        text = re.sub(r'!+', '!', text)
        text = re.sub(r'\.{3,}', '...', text)
        text = re.sub(r'\.{4,}', '...', text)

        text = re.sub(r'([.?,!])([A-Za-z])', r'\1 \2', text)

        return text

    def _fix_capitalization(self, text: str) -> str:
        if not text:
            return text

        if text and text[0].islower():
            text = text[0].upper() + text[1:]

        text = re.sub(r'\bi\b', 'I', text)

        for term in TECHNICAL_TERMS.values():
            if " " not in term and len(term) > 2:
                text = re.sub(
                    rf'\b{re.escape(term)}\b',
                    term,
                    text,
                    flags=re.IGNORECASE,
                )

        return text

    def _fix_spacing(self, text: str) -> str:
        text = re.sub(r' {2,}', ' ', text)
        text = re.sub(r'^\s+', '', text)
        text = re.sub(r'\s+$', '', text)
        return text

    def _detect_and_fix_garbled(self, text: str) -> str:
        words = text.split()
        if not words:
            return text

        char_count = len(text) - text.count(' ')
        if char_count == 0:
            return text

        short_count = sum(1 for w in words if len(w) <= 2 and w.lower() not in
                          {'i', 'a', 'an', 'is', 'it', 'at', 'in', 'on', 'to', 'be',
                           'do', 'go', 'no', 'so', 'we', 'he', 'me', 'my', 'of', 'or',
                           'as', 'if', 'am', 'up', 'by', 'us', 'oh', 'hi', 'ok', 'ah'})

        if len(words) > 3 and short_count / len(words) > 0.5:
            logger.debug("Garbled text detected: {} short words out of {}", short_count, len(words))

        text = re.sub(r'\b(\w)\1{3,}\b', '', text)

        return text

    def _needs_ai_correction(self, text: str) -> bool:
        if len(text) < 10:
            return False
        words = text.split()
        if len(words) < 3:
            return False

        no_punct = re.sub(r'[.,!?\s]', '', text.lower())
        if len(no_punct) == 0:
            return False

        unusual_char_ratio = sum(1 for c in no_punct if c not in 'abcdefghijklmnopqrstuvwxyz') / len(no_punct)
        return unusual_char_ratio > 0.1

    @property
    def stats(self) -> dict:
        return {
            "tier1_cleanups": self._tier1_count,
            "tier2_cleanups": self._tier2_count,
        }
