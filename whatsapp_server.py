# whatsapp_server.py
import os
import hmac
import hashlib
import requests
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse, HTMLResponse
from dotenv import load_dotenv

from agent import generate_reply
from config import AGENT_NAME

load_dotenv()

app = FastAPI(title="Personal AI Agent Cloud Server")

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "").strip()
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "metana_verify_token_123").strip()
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "").strip()

PROCESSED_MESSAGE_IDS: set[str] = set()


@app.get("/", response_class=HTMLResponse)
async def web_chat_playground():
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>__AGENT_NAME__ — Cloud Agent Playground</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .chat-container { width: 100%; max-width: 600px; height: 90vh; background: #1e293b; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); display: flex; flex-direction: column; overflow: hidden; border: 1px solid #334155; }
        .chat-header { background: #0284c7; padding: 16px; font-size: 1.1rem; font-weight: bold; display: flex; justify-content: space-between; align-items: center; }
        .chat-messages { flex: 1; padding: 16px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }
        .message { max-width: 80%; padding: 10px 14px; border-radius: 8px; line-height: 1.4; font-size: 0.95rem; }
        .message.user { background: #0369a1; align-self: flex-end; border-bottom-right-radius: 2px; }
        .message.assistant { background: #334155; align-self: flex-start; border-bottom-left-radius: 2px; }
        .chat-input-box { padding: 12px; background: #0f172a; display: flex; gap: 8px; border-top: 1px solid #334155; }
        input { flex: 1; padding: 10px 14px; background: #1e293b; border: 1px solid #475569; border-radius: 6px; color: #f8fafc; font-size: 0.95rem; outline: none; }
        input:focus { border-color: #0284c7; }
        button { padding: 10px 20px; background: #0284c7; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; transition: background 0.2s; }
        button:hover { background: #0369a1; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <span>🤖 __AGENT_NAME__ (Cloud Agent)</span>
            <span style="font-size: 0.8rem; background: #0369a1; padding: 4px 8px; border-radius: 4px;">Live Online</span>
        </div>
        <div class="chat-messages" id="chatMessages">
            <div class="message assistant">Hello! I'm __AGENT_NAME__, your cloud-hosted personal assistant. How can I help you manage your tasks and notes today?</div>
        </div>
        <div class="chat-input-box">
            <input type="text" id="userInput" placeholder="Type a message or try 'Add buy milk to my tasks'..." autofocus>
            <button onclick="sendMessage()">Send</button>
        </div>
    </div>
    <script>
        const messagesDiv = document.getElementById('chatMessages');
        const inputField = document.getElementById('userInput');
        
        inputField.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') sendMessage();
        });

        async function sendMessage() {
            const text = inputField.value.trim();
            if (!text) return;

            appendMessage(text, 'user');
            inputField.value = '';
            messagesDiv.scrollTop = messagesDiv.scrollHeight;

            const loadingId = appendMessage('Thinking...', 'assistant');

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text, user_id: 'web_playground_user' })
                });
                const data = await response.json();
                document.getElementById(loadingId).innerText = data.reply;
            } catch (err) {
                document.getElementById(loadingId).innerText = 'Error connecting to cloud server.';
            }
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        function appendMessage(text, sender) {
            const div = document.createElement('div');
            div.className = `message ${sender}`;
            const id = 'msg-' + Math.random().toString(36.substring(2, 9));
            div.id = id;
            div.innerText = text;
            messagesDiv.appendChild(div);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            return id;
        }
    </script>
</body>
</html>
    """
    return html.replace("__AGENT_NAME__", AGENT_NAME)


@app.post("/api/chat")
async def web_chat_endpoint(request: Request):
    data = await request.json()
    user_message = str(data.get("message", "")).strip()
    user_id = str(data.get("user_id", "web_user")).strip() or "web_user"

    if not user_message:
        return {"reply": "Please enter a message."}

    reply_text = generate_reply(user_message=user_message, user_id=user_id)
    return {"reply": reply_text, "agent_name": AGENT_NAME}


def verify_webhook_signature(raw_body: bytes, signature_header: str | None) -> bool:
    if not WHATSAPP_APP_SECRET:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        WHATSAPP_APP_SECRET.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    received = signature_header.split("sha256=", 1)[1]
    return hmac.compare_digest(expected, received)


def send_whatsapp_reply(recipient_phone: str, reply_text: str) -> dict:
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        print(f"[WhatsApp Dry-Run Reply to {recipient_phone}]: {reply_text}")
        return {"status": "dry_run", "to": recipient_phone, "text": reply_text}

    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "text",
        "text": {"body": reply_text},
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=20)
    return {"status": "sent", "http_status": resp.status_code}


def handle_incoming_whatsapp_message(sender_phone: str, message_text: str) -> str:
    return generate_reply(user_message=message_text, user_id=sender_phone)


@app.get("/webhook")
async def verify_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        print("✅ Webhook verified successfully with Meta!")
        return PlainTextResponse(content=hub_challenge or "", status_code=200)
    raise HTTPException(status_code=403, detail="Webhook verification failed: token mismatch.")


@app.post("/webhook")
async def receive_whatsapp_webhook(request: Request):
    raw_body = await request.body()
    sig_header = request.headers.get("X-Hub-Signature-256")
    if not verify_webhook_signature(raw_body, sig_header):
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    payload = await request.json()
    try:
        entries = payload.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                for msg in messages:
                    msg_id = msg.get("id")
                    if msg_id and msg_id in PROCESSED_MESSAGE_IDS:
                        continue
                    if msg_id:
                        PROCESSED_MESSAGE_IDS.add(msg_id)

                    if msg.get("type") == "text":
                        sender_phone = msg.get("from", "whatsapp_user")
                        message_text = msg.get("text", {}).get("body", "").strip()
                        if message_text:
                            print(f"📩 [WhatsApp Incoming from {sender_phone}]: {message_text}")
                            reply_text = handle_incoming_whatsapp_message(sender_phone, message_text)
                            print(f"📤 [Agent Reply to {sender_phone}]: {reply_text}")
                            send_whatsapp_reply(sender_phone, reply_text)
    except Exception as exc:
        print(f"⚠️ Error processing webhook payload: {exc}")

    return {"status": "ok"}
