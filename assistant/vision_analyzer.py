"""
DREX - AI Desktop Assistant
assistant/vision_analyzer.py — Multimodal Vision Analysis

Analyzes screen content using DREX's AI router (Gemini Vision primary).
Uses Gemini as the primary vision provider since it supports image input natively.
Falls back gracefully if AI router is not available.

Exports:
    VisionAnalyzer: Main class for vision analysis
"""

__all__ = ["VisionAnalyzer"]

import base64
from PIL import Image
import io
from loguru import logger
from typing import Optional


class VisionAnalyzer:
    """
    Analyzes screen content using AI vision capabilities.
    Uses Gemini as primary (supports vision), falls back gracefully.
    """

    def __init__(self, ai_router=None):
        self.ai_router = ai_router
        self.available = ai_router is not None
        logger.info(f"VisionAnalyzer initialized | AI available: {self.available}")

    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 JPEG string."""
        try:
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=85, optimize=True)
            b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return b64
        except Exception as e:
            logger.error("_image_to_base64 failed: {}", e)
            return ""

    def _build_vision_prompt(self, task: str, context: str = "") -> str:
        """Build a clear prompt for vision analysis tasks."""
        parts = ["You are DREX, an AI desktop assistant analyzing a screenshot."]
        if context:
            parts.append(f"Context: {context}")
        parts.append(f"Task: {task}")
        parts.append(
            "Be specific, concise, and accurate. Describe what you actually see."
        )
        return "\n".join(parts)

    def _call_vision_api(self, image: Image.Image, prompt: str) -> str:
        """
        Send image + prompt to the AI router's vision-capable provider.
        Uses Gemini as primary (via its native vision API).
        Returns empty string on failure.
        """
        if not self.available or not self.ai_router:
            return ""

        b64 = self._image_to_base64(image)
        if not b64:
            return ""

        try:
            # Check if Gemini is available and supports vision
            gemini = getattr(self.ai_router, "gemini", None)
            if gemini and hasattr(gemini, "client") and gemini.client:
                try:
                    from google.genai import types
                    image_bytes = base64.b64decode(b64)
                    image_part = types.Part.from_bytes(
                        data=image_bytes,
                        mime_type="image/jpeg",
                    )
                    text_part = types.Part.from_text(text=prompt)
                    response = gemini.client.models.generate_content(
                        model=gemini.model,
                        contents=[image_part, text_part],
                    )
                    if response and response.text:
                        return response.text.strip()
                except Exception as e:
                    logger.warning("Gemini vision call failed: {}", e)

            # Fallback: try the openrouter client (supports vision models)
            openrouter = getattr(self.ai_router, "openrouter", None)
            if openrouter and hasattr(openrouter, "client") and openrouter.client:
                try:
                    response = openrouter.client.chat.completions.create(
                        model=openrouter.model if hasattr(openrouter, "model") else "openai/gpt-4o-mini",
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{b64}"
                                        },
                                    },
                                ],
                            }
                        ],
                        max_tokens=1000,
                    )
                    if response and response.choices:
                        return response.choices[0].message.content.strip()
                except Exception as e:
                    logger.warning("OpenRouter vision call failed: {}", e)

            return ""

        except Exception as e:
            logger.error("_call_vision_api failed: {}", e)
            return ""

    def analyze_screenshot(self, image: Image.Image) -> dict:
        """
        Analyzes a screenshot using Gemini vision.
        Returns dict: {
            "description": str,
            "active_app": str,
            "visible_text": str,
            "ui_elements": list,
            "suggested_actions": list
        }
        Returns empty dict with error key on failure.

        Args:
            image: PIL Image of the screenshot to analyze.
        """
        try:
            prompt = self._build_vision_prompt(
                "Analyze this screenshot in detail. Provide the following information "
                "separated by clear sections:\n"
                "1. SCENE DESCRIPTION: What is shown in this screenshot overall?\n"
                "2. ACTIVE APPLICATION: What application or website is currently open/active?\n"
                "3. VISIBLE TEXT: What text content is visible on screen?\n"
                "4. UI ELEMENTS: List the key UI elements visible (buttons, menus, dialogs, etc.)\n"
                "5. SUGGESTED ACTIONS: What actions could a user take based on what's visible?",
                context="Analyzing desktop screenshot for user assistance",
            )
            result = self._call_vision_api(image, prompt)

            if not result:
                return {"error": "Vision analysis unavailable", "description": ""}

            # Parse sections from the response
            description = ""
            active_app = ""
            visible_text = ""
            ui_elements_list = []
            suggested_actions_list = []

            sections = result.split("\n")
            current_section = ""
            for line in sections:
                line_lower = line.lower().strip()
                if "scene description" in line_lower or "1." in line_lower[:3]:
                    current_section = "description"
                elif "active application" in line_lower or "2." in line_lower[:3]:
                    current_section = "app"
                elif "visible text" in line_lower or "3." in line_lower[:3]:
                    current_section = "text"
                elif "ui elements" in line_lower or "4." in line_lower[:3]:
                    current_section = "ui"
                elif "suggested actions" in line_lower or "5." in line_lower[:3]:
                    current_section = "actions"
                elif current_section == "description":
                    description += line + "\n"
                elif current_section == "app":
                    active_app += line + "\n"
                elif current_section == "text":
                    visible_text += line + "\n"
                elif current_section == "ui":
                    if line.strip() and not line.startswith("-"):
                        ui_elements_list.append(line.strip())
                elif current_section == "actions":
                    if line.strip() and not line.startswith("-"):
                        suggested_actions_list.append(line.strip())

            return {
                "description": description.strip() or result[:500],
                "active_app": active_app.strip(),
                "visible_text": visible_text.strip(),
                "ui_elements": ui_elements_list or [result[:200]],
                "suggested_actions": suggested_actions_list,
            }

        except Exception as e:
            logger.error("analyze_screenshot failed: {}", e)
            return {"error": str(e), "description": ""}

    def extract_text_from_image(self, image: Image.Image) -> str:
        """
        Extracts all visible text from image using AI vision.
        Returns plain text string.
        Falls back to empty string if unavailable.

        Args:
            image: PIL Image to extract text from.
        """
        try:
            prompt = self._build_vision_prompt(
                "Extract ALL visible text from this screenshot. "
                "Return ONLY the text content, preserving line breaks. "
                "Do not add any commentary or description.",
                context="Text extraction task",
            )
            result = self._call_vision_api(image, prompt)
            return result or ""
        except Exception as e:
            logger.error("extract_text_from_image failed: {}", e)
            return ""

    def describe_screen_content(self, image: Image.Image) -> str:
        """
        Returns a natural language description of what's on screen.
        Example: "You have VS Code open with a Python file. Chrome is visible in the taskbar."

        Args:
            image: PIL Image of the screen.
        """
        try:
            prompt = self._build_vision_prompt(
                "Describe what's on this screen in 2-3 concise sentences. "
                "Focus on: what application is active, what content is visible, "
                "and any notable UI elements or dialogs.",
                context="Quick screen description for user",
            )
            result = self._call_vision_api(image, prompt)
            if result:
                return result
            return "I cannot see any screen content right now."
        except Exception as e:
            logger.error("describe_screen_content failed: {}", e)
            return "Screen content description unavailable."

    def find_ui_elements(self, image: Image.Image) -> list:
        """
        Returns list of detected UI elements.
        Example: [{"type": "button", "text": "Submit", "position": "bottom-right"}]

        Args:
            image: PIL Image of the screen.
        """
        try:
            prompt = self._build_vision_prompt(
                "List all interactive UI elements visible on this screen. "
                "For each element, provide: type (button, text field, checkbox, menu, link, etc.), "
                "the visible text or label, and approximate position (top-left, center, bottom-right, etc.). "
                "Format each element as: type | text | position",
                context="UI element detection",
            )
            result = self._call_vision_api(image, prompt)

            if not result:
                return []

            # Parse lines into structured elements
            elements = []
            for line in result.split("\n"):
                line = line.strip()
                if not line or line.startswith("-") or line.startswith("#"):
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 1:
                    element = {
                        "type": parts[0] if len(parts) > 0 else "unknown",
                        "text": parts[1] if len(parts) > 1 else "",
                        "position": parts[2] if len(parts) > 2 else "unknown",
                    }
                    elements.append(element)

            return elements[:20]  # Limit to 20 elements

        except Exception as e:
            logger.error("find_ui_elements failed: {}", e)
            return []

    def answer_screen_question(self, image: Image.Image, question: str) -> str:
        """
        Answers a specific question about screen content.
        Example question: "What tab is open in Chrome?"
        Returns natural language answer string.

        Args:
            image: PIL Image of the screen.
            question: Natural language question about the screen content.
        """
        try:
            prompt = self._build_vision_prompt(
                f"Answer this question about the screenshot: {question}\n\n"
                "Be concise and specific. If you cannot determine the answer from "
                "what's visible on screen, say so clearly.",
                context=f"User asked: {question}",
            )
            result = self._call_vision_api(image, prompt)
            if result:
                return result
            return "I cannot answer that question based on what I see on your screen."
        except Exception as e:
            logger.error("answer_screen_question failed: {}", e)
            return "Sorry, I encountered an error analyzing your screen."