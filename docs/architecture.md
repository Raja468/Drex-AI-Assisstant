# DREX Architecture

## Overview
DREX is a modular AI desktop assistant inspired by Jarvis.

The system combines:
- AI models
- Desktop automation
- Voice interaction
- Memory systems
- Tool execution
- Multi-agent architecture

---

# Core Flow

User Input
↓
Intent Detection
↓
AI Router
↓
Tool / Model Selection
↓
Execution
↓
Response Output

---

# Main Modules

## brain/
Handles:
- AI reasoning
- LLM integration
- routing logic

Supported:
- Gemini
- OpenAI
- Groq
- Local LLMs (future)

---

## automation/
Handles:
- opening applications
- browser automation
- system control
- desktop tasks

---

## voice/
Handles:
- speech-to-text
- text-to-speech
- voice commands

---

## memory/
Handles:
- conversation history
- preferences
- context memory

---

## gui/
Handles:
- desktop UI
- animations
- assistant interface

---

## plugins/
Future extensible tools system.

Examples:
- SEO tools
- coding tools
- cybersecurity tools

---

# Future Goals

- Multi-agent architecture
- AI tool calling
- Project awareness
- Computer vision
- Jarvis-style UI
- Local + cloud hybrid AI