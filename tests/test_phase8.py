"""Phase 8 tests — Duplex conversation, post-processing, smarter planning, etc."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


class TestPlanningGating:
    def setup_method(self):
        from core.orchestrator import Orchestrator
        from runtime.event_bus import EventBus
        from runtime.planning.goal_decomposer import GoalDecomposer
        from runtime.planning.planner import Planner

        bus = EventBus()
        gd = GoalDecomposer()
        planner = Planner(bus, gd)
        self.orch = Orchestrator()
        self.orch.planner = planner

    @pytest.mark.parametrize("text", [
        "how are you?",
        "what is Python?",
        "compare deepseek and kimi",
        "explain how AI works",
        "tell me about your features",
        "why is the sky blue?",
        "how to use VS Code?",
        "give me a summary of this",
        "list the files in this folder",
        "who is the president?",
        "difference between python and javascript",
        "scan my PC for viruses",
        "open chrome",
        "what time is it",
        "book a meeting tomorrow",
    ])
    def test_should_not_plan(self, text):
        assert not self.orch._should_plan(text), f"'{text}' should NOT trigger a plan"

    @pytest.mark.parametrize("text", [
        "create a website then deploy it",
        "build a react app step by step",
        "setup a python api and database",
        "refactor my code first then test",
        "write a report with charts and then email it",
    ])
    def test_should_plan(self, text):
        assert self.orch._should_plan(text), f"'{text}' SHOULD trigger a plan"


class TestPostProcessor:
    def setup_method(self):
        from voice.post_processor import PostProcessor
        self.pp = PostProcessor()

    @pytest.mark.parametrize("raw,expected", [
        ("how r u", "How are you?"),
        ("im doing good thx", "I'm doing good thanks."),
        ("what is python", "What is Python?"),
        ("compare deepseek and kimi", "Compare DeepSeek and Kimi."),
        ("i dont know what u r talking about", "I don't know what you are talking about."),
        ("how to setup api with python", "How to setup API with Python?"),
        ("whats github", "What's GitHub?"),
        ("tell me about drex", "Tell me about DREX."),
        ("i cant find it pls help", "I can't find it please help."),
    ])
    def test_clean_transformations(self, raw, expected):
        result = self.pp.clean(raw)
        assert result == expected, f"Expected '{expected}', got '{result}'"

    def test_technical_terms_preserved(self):
        terms = ["DREX", "Python", "GitHub", "VS Code", "ChatGPT", "Gemini", "Groq",
                 "Cerebras", "DeepSeek", "Kimi", "Qwen", "API", "LLM", "AI"]
        for term in terms:
            result = self.pp.clean(f"tell me about {term.lower()}")
            assert term in result, f"Term '{term}' not preserved in: {result}"
