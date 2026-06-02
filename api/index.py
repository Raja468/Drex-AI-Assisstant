"""DREX - Vercel serverless API entry point"""
import os
import sys
import json
from typing import Optional

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
        os.environ["DREX_LOG_LEVEL"] = "WARNING"

        from core.orchestrator import Orchestrator
        _orchestrator = Orchestrator()
    return _orchestrator


@app.on_event("startup")
async def startup():
    try:
        get_orchestrator()
    except Exception as e:
        print(f"Orchestrator init warning: {e}")


APP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DREX AI Assistant</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  *{margin:0;padding:0;box-sizing:border-box}
  body{
    font-family:'Inter',system-ui,-apple-system,sans-serif;
    background:linear-gradient(135deg,#0a0c10 0%,#1a1b2e 50%,#0a0c10 100%);
    min-height:100vh;display:flex;align-items:center;justify-content:center;padding:16px;
    color:#e8edf5
  }
  .container{
    background:rgba(255,255,255,0.03);backdrop-filter:blur(24px);
    border:1px solid rgba(255,255,255,0.08);border-radius:28px;
    width:100%;max-width:820px;height:85vh;max-height:850px;
    display:flex;flex-direction:column;overflow:hidden;
    box-shadow:0 32px 64px rgba(0,0,0,0.6),inset 0 1px 0 rgba(255,255,255,0.05)
  }
  .header{padding:20px 28px;border-bottom:1px solid rgba(255,255,255,0.06);display:flex;align-items:center;gap:14px}
  .logo{width:38px;height:38px;border-radius:12px;
    background:linear-gradient(135deg,#00d4ff,#7b2ff7);
    display:flex;align-items:center;justify-content:center;font-weight:700;font-size:18px;color:#fff;flex-shrink:0;
    box-shadow:0 4px 12px rgba(0,212,255,0.3)
  }
  h1{font-size:18px;font-weight:600;color:#e8edf5;flex:1}
  .status{display:flex;align-items:center;gap:6px;font-size:12px;color:rgba(255,255,255,0.4)}
  .dot{width:7px;height:7px;border-radius:50%;background:#22c55e;display:inline-block}
  .dot.pulse{animation:pulse 2s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}
  .provider-bar{padding:10px 28px;border-bottom:1px solid rgba(255,255,255,0.04);display:flex;align-items:center;gap:10px}
  .provider-bar label{font-size:11px;color:rgba(255,255,255,0.35);text-transform:uppercase;letter-spacing:0.8px;font-weight:500}
  .provider-bar select{
    background:rgba(255,255,255,0.06);color:rgba(255,255,255,0.8);border:1px solid rgba(255,255,255,0.08);
    border-radius:8px;padding:5px 12px;font-size:12px;font-family:inherit;cursor:pointer;outline:none;transition:border .2s
  }
  .provider-bar select:focus{border-color:#00d4ff}
  .messages{flex:1;overflow-y:auto;padding:20px 28px;display:flex;flex-direction:column;gap:10px}
  .messages::-webkit-scrollbar{width:4px}
  .messages::-webkit-scrollbar-track{background:transparent}
  .messages::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.1);border-radius:2px}
  .msg{max-width:82%;padding:14px 18px;border-radius:18px;font-size:14px;line-height:1.6;animation:fadeIn .3s ease}
  @keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
  .msg.user{align-self:flex-end;background:linear-gradient(135deg,#00d4ff,#7b2ff7);color:#fff;border-bottom-right-radius:4px}
  .msg.assistant{align-self:flex-start;background:rgba(255,255,255,0.06);color:#e8edf5;border-bottom-left-radius:4px;border:1px solid rgba(255,255,255,0.04)}
  .msg .meta{font-size:10px;color:rgba(255,255,255,0.3);margin-top:8px}
  .msg.user .meta{color:rgba(255,255,255,0.5)}
  .typing{align-self:flex-start;display:flex;gap:5px;padding:16px 20px;
    background:rgba(255,255,255,0.05);
    border-radius:18px;border-bottom-left-radius:4px}
  .typing span{width:8px;height:8px;background:rgba(255,255,255,0.3);border-radius:50%;animation:bounce 1.4s infinite both}
  .typing span:nth-child(2){animation-delay:.2s}
  .typing span:nth-child(3){animation-delay:.4s}
  @keyframes bounce{0%,80%,100%{transform:scale(0.6)}40%{transform:scale(1)}}
  .input-area{padding:16px 28px 20px;border-top:1px solid rgba(255,255,255,0.06);display:flex;gap:10px}
  .input-area input{
    flex:1;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);
    border-radius:14px;padding:12px 18px;color:#e8edf5;font-size:14px;font-family:inherit;outline:none;transition:border .2s
  }
  .input-area input::placeholder{color:rgba(255,255,255,0.2)}
  .input-area input:focus{border-color:#00d4ff;background:rgba(0,212,255,0.04)}
  .input-area button{
    background:linear-gradient(135deg,#00d4ff,#7b2ff7);color:#fff;border:none;
    border-radius:14px;padding:12px 24px;font-size:14px;font-weight:500;cursor:pointer;
    transition:opacity .2s,transform .1s;white-space:nowrap
  }
  .input-area button:hover{opacity:0.9}
  .input-area button:active{transform:scale(0.97)}
  .input-area button:disabled{opacity:0.3;cursor:not-allowed}
  .empty-state{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;color:rgba(255,255,255,0.15)}
  .empty-state .icon{font-size:48px;opacity:0.4;background:linear-gradient(135deg,#00d4ff,#7b2ff7);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
  .empty-state p{font-size:14px;color:rgba(255,255,255,0.2)}
  .error-msg{align-self:center;background:rgba(255,77,109,0.1);color:#ff4d6d;border:1px solid rgba(255,77,109,0.2);
    border-radius:12px;padding:10px 16px;font-size:13px}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="logo">D</div>
    <h1>DREX</h1>
    <div class="status"><span class="dot pulse" id="statusDot"></span><span id="statusText">Ready</span></div>
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
const statusDot = document.getElementById('statusDot');

function addMessage(role, text, meta) {
  if (emptyState) emptyState.remove();
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.innerHTML = '<div class="text">' + escapeHtml(text) + '</div>';
  if (meta) div.innerHTML += '<div class="meta">' + escapeHtml(meta) + '</div>';
  msgBox.appendChild(div);
  msgBox.scrollTop = msgBox.scrollHeight;
}

function showTyping() {
  const div = document.createElement('div');
  div.className = 'typing'; div.id = 'typingIndicator';
  div.innerHTML = '<span></span><span></span><span></span>';
  msgBox.appendChild(div);
  input.disabled = true; sendBtn.disabled = true;
  msgBox.scrollTop = msgBox.scrollHeight;
}

function hideTyping() {
  const el = document.getElementById('typingIndicator');
  if (el) el.remove();
  input.disabled = false; sendBtn.disabled = false;
  input.focus();
}

function escapeHtml(t) {
  const d = document.createElement('div'); d.textContent = t; return d.innerHTML;
}

function setStatus(text, ok) {
  statusText.textContent = text;
  statusDot.className = 'dot' + (ok ? ' pulse' : '');
  statusDot.style.background = ok ? '#22c55e' : '#ef4444';
}

providerSelect.addEventListener('change', () => {
  provider = providerSelect.value;
  fetch(BASE + '/api/switch_provider', {
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
    const res = await fetch(BASE + '/api/chat', {
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
    let errorMsg = err.message;
    try {
      const errData = JSON.parse(err.message);
      if (errData.detail) errorMsg = errData.detail;
    } catch(e) {}
    addMessage('assistant', '⚠️ ' + errorMsg);
    setStatus('Error', false);
  }
}

sendBtn.addEventListener('click', sendMessage);
input.addEventListener('keydown', e => { if (e.key === 'Enter') sendMessage(); });

// Load providers on start
fetch(BASE + '/api/providers')
  .then(r => r.json())
  .then(data => {
    if (data.available_providers && data.available_providers.length) {
      const sel = document.getElementById('providerSelect');
      sel.innerHTML = '';
      data.available_providers.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p; opt.textContent = p.charAt(0).toUpperCase() + p.slice(1);
        sel.appendChild(opt);
      });
      if (data.default && data.available_providers.includes(data.default)) sel.value = data.default;
    }
  })
  .catch(() => {});
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def root():
    return APP_HTML


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/api/providers")
async def providers():
    try:
        from brain.ai_router import AIRouter
        router = AIRouter()
        status = router.get_status()
        available = [p for p, info in status.get("providers", {}).items() if info.get("available")]
        return {"available_providers": available, "default": status.get("default")}
    except Exception as e:
        return {"available_providers": [], "default": None, "error": str(e)}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    try:
        orch = get_orchestrator()
        if request.provider:
            try:
                orch.switch_ai_provider(request.provider)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to switch provider: {e}")
        response = orch.process(request.message, voice_response=False)
        from config import get_config
        current_provider = get_config().ai.default_provider
        return ChatResponse(response=response, provider=current_provider, session_id=request.session_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/switch_provider")
async def switch_provider(request: ProviderRequest):
    try:
        from config import get_config
        cfg = get_config()
        cfg.ai.default_provider = request.provider
        return {"status": "ok", "provider": request.provider}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))