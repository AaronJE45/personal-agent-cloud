# storage.py
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "agent_data.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'default_user',
                title TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'default_user',
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def db_add_task(title: str, user_id: str = "default_user") -> dict:
    init_db()
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (user_id, title, done) VALUES (?, ?, 0)",
            (user_id, title),
        )
        conn.commit()
        task_id = cursor.lastrowid
    return {"id": task_id, "user_id": user_id, "title": title, "done": False}


def db_list_tasks(user_id: str = "default_user") -> list[dict]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, user_id, title, done FROM tasks WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "user_id": row["user_id"],
            "title": row["title"],
            "done": bool(row["done"]),
        }
        for row in rows
    ]


def db_complete_task(task_id: int, user_id: str = "default_user") -> dict | None:
    init_db()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, user_id, title, done FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE tasks SET done = 1 WHERE id = ? AND user_id = ?",
            (task_id, user_id),
        )
        conn.commit()
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "title": row["title"],
        "done": True,
    }


def db_save_note(content: str, user_id: str = "default_user") -> dict:
    init_db()
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO notes (user_id, content) VALUES (?, ?)",
            (user_id, content),
        )
        conn.commit()
        note_id = cursor.lastrowid
    return {"id": note_id, "user_id": user_id, "content": content}


def db_search_notes(query: str = "", user_id: str = "default_user") -> list[dict]:
    init_db()
    query_clean = (query or "").strip().lower()
    with get_connection() as conn:
        if not query_clean:
            rows = conn.execute(
                "SELECT id, user_id, content FROM notes WHERE user_id = ? ORDER BY id ASC",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, user_id, content FROM notes WHERE user_id = ? AND LOWER(content) LIKE ? ORDER BY id ASC",
                (user_id, f"%{query_clean}%"),
            ).fetchall()
    return [
        {"id": row["id"], "user_id": row["user_id"], "content": row["content"]}
        for row in rows
    ]
