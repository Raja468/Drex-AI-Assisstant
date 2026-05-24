"""DREX - Vercel serverless API entry point"""
import os
import sys
import json
from typing import Optional

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# Disable GUI/voice modules for serverless
os.environ["DREX_GUI_ENABLED"] = "false"
os.environ["DREX_VOICE_ENABLED"] = "false"

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

app = FastAPI(
    title="DREX AI Assistant API",
    version="1.0.0",
    description="AI-powered desktop assistant - Web API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    provider: Optional[str] = None
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    provider: str
    session_id: Optional[str] = None


class ProviderRequest(BaseModel):
    provider: str


# Lazy-init orchestrator singleton
_orchestrator = None


def get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        try:
            from utils.logger import setup_logger
            setup_logger()
        except Exception:
            pass

        from config import get_config
        cfg = get_config()
        cfg.app.gui_enabled = False
        cfg.app.voice_enabled = False

        # Suppress noisy logs in serverless
        os.environ["DREX_LOG_LEVEL"] = "WARNING"

        from core.orchestrator import Orchestrator
        _orchestrator = Orchestrator()
    return _orchestrator


@app.on_event("startup")
async def startup():
    """Initialize orchestrator on cold start."""
    try:
        get_orchestrator()
    except Exception as e:
        print(f"Orchestrator init warning (non-fatal): {e}")


# ── Frontend UI ─────────────────────────────────────────────

HTML_UI = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DREX AI Assistant</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:opsz@14..32&display=swap');
  *{margin:0;padding:0;box-sizing:border-box}
  body{
    font-family:'Inter',system-ui,-apple-system,sans-serif;
    background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);
    min-height:100vh;display:flex;align-items:center;justify-content:center;padding:16px
  }
  .container{
    background:rgba(255,255,255,0.05);backdrop-filter:blur(20px);
    border:1px solid rgba(255,255,255,0.1);border-radius:24px;
    width:100%;max-width:720px;height:80vh;max-height:800px;
    display:flex;flex-direction:column;overflow:hidden;
    box-shadow:0 25px 60px rgba(0,0,0,0.5)
  }
  .header{
    padding:20px 24px;border-bottom:1px solid rgba(255,255,255,0.08);
    display:flex;align-items:center;gap:12px
  }
  .header .logo{width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#667eea,#764ba2);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px;color:#fff;flex-shrink:0}
  .header h1{font-size:18px;font-weight:600;color:#fff;flex:1}
  .header .status{display:flex;align-items:center;gap:6px;font-size:12px;color:rgba(255,255,255,0.5)}
  .header .status .dot{width:8px;height:8px;border-radius:50%;background:#22c55e;display:inline-block;animation:pulse 2s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}
  .provider-bar{
    padding:8px 24px;border-bottom:1px solid rgba(255,255,255,0.05);
    display:flex;align-items:center;gap:8px;flex-wrap:wrap
  }
  .provider-bar label{font-size:11px;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.5px}
  .provider-bar select{
    background:rgba(255,255,255,0.08);color:rgba(255,255,255,0.8);border:1px solid rgba(255,255,255,0.1);
    border-radius:8px;padding:4px 10px;font-size:12px;font-family:inherit;cursor:pointer;outline:none
  }
  .provider-bar select:focus{border-color:#667eea}
  .messages{
    flex:1;overflow-y:auto;padding:20px 24px;display:flex;flex-direction:column;gap:12px
  }
  .messages::-webkit-scrollbar{width:5px}
  .messages::-webkit-scrollbar-track{background:transparent}
  .messages::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.15);border-radius:3px}
  .msg{max-width:85%;padding:12px 16px;border-radius:16px;font-size:14px;line-height:1.5;animation:fadeIn .25s ease}
  @keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
  .msg.user{align-self:flex-end;background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;border-bottom-right-radius:4px}
  .msg.assistant{align-self:flex-start;background:rgba(255,255,255,0.08);color:rgba(255,255,255,0.9);border-bottom-left-radius:4px}
  .msg .meta{font-size:10px;color:rgba(255,255,255,0.35);margin-top:6px}
  .msg.user .meta{color:rgba(255,255,255,0.5)}
  .typing{
    align-self:flex-start;display:flex;gap:4px;padding:16px;background:rgba(255,255,255,0.06);
    border-radius:16px;border-bottom-left-radius:4px
  }
  .typing span{width:7px;height:7px;background:rgba(255,255,255,0.4);border-radius:50%;animation:bounce 1.4s infinite both}
  .typing span:nth-child(2){animation-delay:.2s}
  .typing span:nth-child(3){animation-delay:.4s}
  @keyframes bounce{0%,80%,100%{transform:scale(0.6)}40%{transform:scale(1)}}
  .input-area{
    padding:16px 24px;border-top:1px solid rgba(255,255,255,0.08);
    display:flex;gap:10px
  }
  .input-area input{
    flex:1;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);
    border-radius:14px;padding:12px 16px;color:#fff;font-size:14px;font-family:inherit;outline:none;transition:border .2s
  }
  .input-area input::placeholder{color:rgba(255,255,255,0.3)}
  .input-area input:focus{border-color:#667eea}
  .input-area button{
    background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;border:none;
    border-radius:14px;padding:12px 20px;font-size:14px;font-weight:500;cursor:pointer;transition:opacity .2s;white-space:nowrap
  }
  .input-area button:hover{opacity:0.85}
  .input-area button:disabled{opacity:0.4;cursor:not-allowed}
  .empty-state{
    flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;color:rgba(255,255,255,0.25)
  }
  .empty-state .icon{font-size:48px;opacity:0.3}
  .empty-state p{font-size:14px}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="logo">D</div>
    <h1>DREX</h1>
    <div class="status"><span class="dot"></span><span id="statusText">Ready</span></div>
  </div>
  <div class="provider-bar">
    <label>AI Provider</label>
    <select id="providerSelect">
      <option value="gemini">Gemini</option>
      <option value="groq">Groq</option>
      <option value="openrouter">OpenRouter</option>
      <option value="cerebras">Cerebras</option>
    </select>
  </div>
  <div class="messages" id="messages">
    <div class="empty-state" id="emptyState">
      <div class="icon">✦</div>
      <p>Ask me anything — I'm your AI assistant.</p>
    </div>
  </div>
  <div class="input-area">
    <input type="text" id="userInput" placeholder="Type your message..." autofocus>
    <button id="sendBtn">Send</button>
  </div>
</div>

<script>
const BASE = '';
let provider = 'gemini';
let sessionId = 'sess_' + Math.random().toString(36).slice(2,10);

const msgBox = document.getElementById('messages');
const emptyState = document.getElementById('emptyState');
const input = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const providerSelect = document.getElementById('providerSelect');
const statusText = document.getElementById('statusText');

function addMessage(role, text, meta) {
  emptyState?.remove();
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.innerHTML = '<div class="text">' + escapeHtml(text) + '</div>';
  if (meta) {
    div.innerHTML += '<div class="meta">' + escapeHtml(meta) + '</div>';
  }
  msgBox.appendChild(div);
  msgBox.scrollTop = msgBox.scrollHeight;
}

function showTyping() {
  const div = document.createElement('div');
  div.className = 'typing';
  div.id = 'typingIndicator';
  div.innerHTML = '<span></span><span></span><span></span>';
  msgBox.appendChild(div);
  input.disabled = true;
  sendBtn.disabled = true;
  msgBox.scrollTop = msgBox.scrollHeight;
}

function hideTyping() {
  const el = document.getElementById('typingIndicator');
  if (el) el.remove();
  input.disabled = false;
  sendBtn.disabled = false;
  input.focus();
}

function escapeHtml(text) {
  const d = document.createElement('div');
  d.textContent = text;
  return d.innerHTML;
}

function setStatus(status, ok) {
  statusText.textContent = status;
  const dot = document.querySelector('.status .dot');
  dot.style.background = ok ? '#22c55e' : '#ef4444';
}

providerSelect.addEventListener('change', () => {
  provider = providerSelect.value;
  fetch(BASE + '/switch_provider', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({provider})
  }).catch(() => {});
});

async function sendMessage() {
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  addMessage('user', text);
  showTyping();
  try {
    const res = await fetch(BASE + '/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text, provider, session_id: sessionId})
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    hideTyping();
    addMessage('assistant', data.response, 'via ' + data.provider);
    setStatus('Ready', true);
  } catch (err) {
    hideTyping();
    addMessage('assistant', '⚠️ Error: ' + err.message);
    setStatus('Error', false);
  }
}

sendBtn.addEventListener('click', sendMessage);
input.addEventListener('keydown', e => { if (e.key === 'Enter') sendMessage(); });

// Load providers on start
fetch(BASE + '/providers')
  .then(r => r.json())
  .then(data => {
    const sel = document.getElementById('providerSelect');
    if (data.available_providers && data.available_providers.length) {
      sel.innerHTML = '';
      data.available_providers.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p;
        opt.textContent = p.charAt(0).toUpperCase() + p.slice(1);
        sel.appendChild(opt);
      });
      if (data.default && data.available_providers.includes(data.default)) {
        sel.value = data.default;
      }
    }
  })
  .catch(() => {});
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML_UI


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/status")
async def status():
    try:
        from brain.ai_router import AIRouter
        router_status = AIRouter().get_status()
        return {"status": "ok", "providers": router_status}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/providers")
async def providers():
    try:
        from brain.ai_router import AIRouter
        router = AIRouter()
        status_data = router.get_status()
        available = [
            p for p, info in status_data.get("providers", {}).items()
            if info.get("available")
        ]
        return {"available_providers": available, "default": status_data.get("default")}
    except Exception as e:
        return {"available_providers": [], "default": None, "error": str(e)}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        orch = get_orchestrator()

        # Switch provider if specified
        if request.provider:
            try:
                orch.switch_ai_provider(request.provider)
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to switch provider: {e}"
                )

        # Get AI response
        response = orch.process(request.message, voice_response=False)

        # Get current provider info
        try:
            from config import get_config
            current_provider = get_config().ai.default_provider
        except Exception:
            current_provider = "unknown"

        return ChatResponse(
            response=response,
            provider=current_provider,
            session_id=request.session_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/switch_provider")
async def switch_provider(request: ProviderRequest):
    try:
        from config import get_config
        cfg = get_config()
        cfg.ai.default_provider = request.provider
        return {"status": "ok", "provider": request.provider}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))