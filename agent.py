# agent.py
import json
from config import AGENT_NAME, SYSTEM_INSTRUCTION, call_model_api
from tools import add_task, list_tasks, complete_task, save_note, search_notes, get_current_time

MAX_STEPS = 5
MAX_HISTORY_MESSAGES = 10
CONVERSATION_HISTORY: dict[str, list[dict]] = {}

TOOL_SCHEMAS = [
    {
        "name": "add_task",
        "description": "Adds a new task to the user's task list.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "The title or description of the task."
                }
            },
            "required": ["title"]
        }
    },
    {
        "name": "list_tasks",
        "description": "Lists all tasks currently stored in the user's task list.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "complete_task",
        "description": "Marks a task as completed using its unique integer ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "The numeric ID of the task to complete."
                }
            },
            "required": ["task_id"]
        }
    },
    {
        "name": "save_note",
        "description": "Saves a new personal note for the user.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The text content of the note to save."
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "search_notes",
        "description": "Searches the user's saved notes by keyword, or returns all notes if query is empty.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The keyword to search for in notes (leave empty string to list all notes)."
                }
            },
            "required": []
        }
    },
    {
        "name": "get_current_time",
        "description": "Returns the current server date and time when the user asks for the time or date.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]

AVAILABLE_TOOLS = {
    "add_task": add_task,
    "list_tasks": list_tasks,
    "complete_task": complete_task,
    "save_note": save_note,
    "search_notes": search_notes,
    "get_current_time": get_current_time,
}


def reset_conversation(user_id: str = "default_user") -> str:
    CONVERSATION_HISTORY[user_id] = []
    return "Conversation history has been reset. Your saved tasks and notes remain intact."


def execute_tool_call(tool_name: str, arguments: dict, user_id: str = "default_user") -> dict:
    if tool_name not in AVAILABLE_TOOLS:
        return {
            "status": "error",
            "message": f"Unknown tool '{tool_name}'. Available tools: {list(AVAILABLE_TOOLS.keys())}"
        }

    tool_function = AVAILABLE_TOOLS[tool_name]
    try:
        call_args = dict(arguments or {})
        call_args["user_id"] = user_id
        return tool_function(**call_args)
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Error executing tool '{tool_name}': {str(exc)}"
        }


def generate_reply(user_message: str, user_id: str = "default_user") -> str:
    cleaned_input = user_message.strip()
    if cleaned_input.lower() in ["/reset", "reset"]:
        return reset_conversation(user_id)

    user_history = CONVERSATION_HISTORY.get(user_id, [])
    messages = list(user_history) + [{"role": "user", "content": cleaned_input}]

    for step in range(MAX_STEPS):
        response = call_model_api(
            system_instruction=SYSTEM_INSTRUCTION,
            messages=messages,
            tools=TOOL_SCHEMAS
        )

        if response.get("type") != "tool_call":
            final_text = response.get("content", "I'm not sure how to respond to that.")
            updated_history = user_history + [
                {"role": "user", "content": cleaned_input},
                {"role": "assistant", "content": final_text},
            ]
            CONVERSATION_HISTORY[user_id] = updated_history[-MAX_HISTORY_MESSAGES:]
            return final_text

        tool_name = response["tool_name"]
        tool_args = response.get("arguments", {})

        tool_result = execute_tool_call(tool_name, tool_args, user_id=user_id)

        messages.append({
            "role": "assistant",
            "tool_call": {"name": tool_name, "arguments": tool_args}
        })
        messages.append({
            "role": "tool",
            "name": tool_name,
            "content": json.dumps(tool_result)
        })

    return "I reached my maximum step limit while working on your request. Please try breaking it into smaller steps."
