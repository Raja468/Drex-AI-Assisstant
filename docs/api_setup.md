# API Setup Guide

# Supported APIs

## Gemini API
Used for:
- reasoning
- coding help
- chat responses

Environment Variable:
GEMINI_API_KEY=

---

## OpenAI API
Used for:
- advanced reasoning
- premium responses

Environment Variable:
OPENAI_API_KEY=

---

## Groq API
Used for:
- fast inference
- backup AI responses

Environment Variable:
GROQ_API_KEY=

---

# Environment Setup

Create `.env` file:

Example:

GEMINI_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here

---

# Important Notes

- Never upload `.env` to GitHub
- Keep API keys private
- Use `.gitignore`

---

# Future APIs

Planned:
- Ollama
- OpenRouter
- DeepSeek
- Qwen