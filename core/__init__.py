"""
DREX - Core Module
core/ — Orchestration, Intent Parsing, and Task Dispatch

Exports:
    Orchestrator: Main application orchestrator
    IntentParser: Natural language intent parsing
    TaskDispatcher: Task routing and dispatch
"""

from core.orchestrator import Orchestrator
from core.intent_parser import IntentParser
from core.task_dispatcher import TaskDispatcher

__all__ = ["Orchestrator", "IntentParser", "TaskDispatcher"]