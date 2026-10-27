# config.py
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

AGENT_NAME = "Atlas"

SYSTEM_INSTRUCTION = f"""
You are {AGENT_NAME}, a sharp, reliable personal AI assistant on WhatsApp and the web.
Your job is to help the user manage their daily tasks and save personal notes.

Guidelines:
- Keep responses concise (1-3 sentences) so they are easy to read on a phone screen.
- Always use `add_task`, `list_tasks`, `complete_task`, `save_note`, `search_notes`, and `get_current_time` when managing tasks, notes, or time.
- Never claim a task or note was saved unless you actually called the tool.
- When listing tasks, always show the task ID (e.g., ID: 1) so the user can complete it easily.
""".strip()

LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash").strip()


def check_api_configuration() -> bool:
    if not LLM_API_KEY or LLM_API_KEY == "your_actual_api_key_here":
        print("⚠️ Configuration Error: Please set a valid LLM_API_KEY in your .env file.")
        return False
    return True


def call_model_api(
    system_instruction: str,
    user_message: str = "",
    messages: list | None = None,
    tools: list | None = None,
):
    return_structured = (messages is not None) or (tools is not None)

    if not check_api_configuration():
        err_msg = "API key is missing or invalid. Check your .env file."
        return {"type": "text", "content": err_msg} if return_structured else err_msg

    if messages is None:
        messages = [{"role": "user", "content": user_message}]

    contents = []
    for msg in messages:
        role = msg.get("role", "user")
        if role == "user":
            contents.append({"role": "user", "parts": [{"text": str(msg.get("content", ""))}]})
        elif role == "assistant":
            if "tool_call" in msg:
                tc = msg["tool_call"]
                contents.append({
                    "role": "model",
                    "parts": [{"functionCall": {"name": tc["name"], "args": tc.get("arguments", {})}}]
                })
            else:
                contents.append({"role": "model", "parts": [{"text": str(msg.get("content", ""))}]})
        elif role == "tool":
            try:
                parsed_resp = json.loads(msg.get("content", "{}"))
            except Exception:
                parsed_resp = {"result": msg.get("content", "")}
            contents.append({
                "role": "user",
                "parts": [{
                    "functionResponse": {
                        "name": msg.get("name", "tool"),
                        "response": parsed_resp
                    }
                }]
            })

    payload: dict = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": contents,
    }

    if tools:
        payload["tools"] = [{"functionDeclarations": tools}]

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{LLM_MODEL}:generateContent?key={LLM_API_KEY}"

    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code in (401, 403):
            err = "Authentication error (401/403): Check your LLM_API_KEY in .env."
            return {"type": "text", "content": err} if return_structured else err
        if resp.status_code == 429:
            err = "Rate limit reached (429): Please wait 30-60 seconds and try again."
            return {"type": "text", "content": err} if return_structured else err
        resp.raise_for_status()
        data = resp.json()

        candidates = data.get("candidates", [])
        if not candidates:
            err = "Model returned no candidates."
            return {"type": "text", "content": err} if return_structured else err

        parts = candidates[0].get("content", {}).get("parts", [])
        for part in parts:
            if "functionCall" in part:
                fc = part["functionCall"]
                return {
                    "type": "tool_call",
                    "tool_name": fc.get("name", ""),
                    "arguments": fc.get("args", {}) or {},
                }

        text_reply = "".join(part.get("text", "") for part in parts).strip()
        if return_structured:
            return {"type": "text", "content": text_reply}
        return text_reply

    except requests.RequestException as exc:
        err = f"Network or API error: {exc}"
        return {"type": "text", "content": err} if return_structured else err
