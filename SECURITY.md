# DREX Security Guide

## ⚠️ CRITICAL: API Key Security

### Immediate Action Required

If you have distributed the `.env` file with your repository or any archive, **your API keys are exposed**.

**You must rotate all exposed keys immediately:**

1. **Gemini API Key**: Visit https://aistudio.google.com → API Keys → Revoke & create new
2. **Groq API Key**: Visit https://console.groq.com → API Keys → Revoke & create new  
3. **OpenRouter API Key**: Visit https://openrouter.ai → Keys → Revoke & create new
4. **Cerebras API Key**: Visit https://cloud.cerebras.ai → API Keys → Revoke & create new

### After Rotating Keys

1. Update the `.env` file with the new keys
2. **Never** commit or share `.env` files
3. Verify `.env` is in `.gitignore` (it is by default)
4. Consider using environment variables instead of `.env` in production

## 🔒 Automation Security Layer

DREX includes a built-in permission/approval system (`core/permission.py`) that:

### Risk Classification
| Risk Level | Examples | Behavior |
|-----------|---------|----------|
| ✅ SAFE | Volume up, Open YouTube, Search web | Executes immediately — no confirmation needed |
| ⚠️ DANGEROUS | Close app, Screenshot, Sleep | Requests user confirmation before executing |
| 🔴 CRITICAL | Shutdown, Restart, Delete file | Requires explicit user approval via dialog |

### How It Works

1. `PermissionManager` classifies every automation action by risk level
2. If the action requires approval, it prompts the user via callback
3. If no approval handler is registered (e.g., CLI mode without GUI), dangerous actions are **automatically denied** (fail-safe)
4. All decisions are logged for audit trail

### GUI Integration

The Orchestrator exposes a `permission` attribute that the GUI can use to register approval dialogs:

```python
orchestrator.permission.register_approval_handler(
    lambda action, risk, target, approve_fn, deny_fn: show_dialog(
        f"DREX wants to: {action} {target}\nRisk: {risk}",
        on_yes=lambda: approve_fn(),
        on_no=lambda: deny_fn(),
    )
)
```

## 📁 Repository Cleanup Checklist

Before distributing DREX:

- [ ] Remove `venv/` directory from archives
- [ ] Remove `.git/` directory from archives  
- [ ] Remove `__pycache__/` and `.pytest_cache/` directories
- [ ] Remove `logs/` directory
- [ ] Verify `.env` is **not** included
- [ ] Remove `*.db` and `*.db-wal` and `*.db-shm` files
- [ ] Use `git archive` or a proper build script for distribution

## 🛡️ Security Best Practices

### For Developers
1. **Never** commit `.env` files — use `.env.example` instead
2. Add API keys via system environment variables in production
3. Use the PermissionManager for all automation actions
4. Keep dependencies updated
5. Review automation actions before adding to the dispatch system

### For Users
1. Treat DREX like any powerful assistant — verify its actions
2. Review any automation confirmation dialogs before approving
3. Don't share your `.env` file with anyone
4. Keep your API keys confidential

## 🔐 Database Security

- DREX uses local SQLite with WAL mode enabled for performance
- Database is stored in `data/` directory (local only)
- No remote database access
- Database contains conversation history — treat as sensitive data

## 📋 Reporting Security Issues

For security concerns, please review the code directly or contact the project maintainer.