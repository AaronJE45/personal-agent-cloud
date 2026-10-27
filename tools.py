# tools.py
from datetime import datetime
from storage import (
    db_add_task,
    db_list_tasks,
    db_complete_task,
    db_save_note,
    db_search_notes,
)


def get_current_time(**kwargs) -> dict:
    """Returns the current server date and time."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    return {
        "status": "success",
        "current_time": now
    }


def add_task(title: str, user_id: str = "default_user") -> dict:
    if not isinstance(title, str) or not title.strip():
        return {
            "status": "error",
            "message": "Task title cannot be empty."
        }

    clean_title = title.strip()
    task = db_add_task(title=clean_title, user_id=user_id)
    return {
        "status": "success",
        "message": f"Added task #{task['id']}: '{clean_title}'",
        "task": task
    }


def list_tasks(user_id: str = "default_user") -> dict:
    tasks = db_list_tasks(user_id=user_id)
    return {
        "status": "success",
        "count": len(tasks),
        "tasks": tasks
    }


def complete_task(task_id: int, user_id: str = "default_user") -> dict:
    try:
        target_id = int(task_id)
    except (ValueError, TypeError):
        return {
            "status": "error",
            "message": f"Invalid task_id '{task_id}'. Please provide a valid number."
        }

    updated_task = db_complete_task(task_id=target_id, user_id=user_id)
    if not updated_task:
        return {
            "status": "error",
            "message": f"Task with ID {target_id} was not found."
        }

    return {
        "status": "success",
        "message": f"Completed task #{target_id}: '{updated_task['title']}'",
        "task": updated_task
    }


def save_note(content: str, user_id: str = "default_user") -> dict:
    if not isinstance(content, str) or not content.strip():
        return {
            "status": "error",
            "message": "Note content cannot be empty."
        }

    clean_content = content.strip()
    note = db_save_note(content=clean_content, user_id=user_id)
    return {
        "status": "success",
        "message": f"Saved note #{note['id']}.",
        "note": note
    }


def search_notes(query: str = "", user_id: str = "default_user") -> dict:
    if query is None:
        query = ""
    query_clean = str(query).strip()
    matches = db_search_notes(query=query_clean, user_id=user_id)
    return {
        "status": "success",
        "query": query_clean,
        "count": len(matches),
        "notes": matches
    }
