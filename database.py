import csv
import sqlite3
import threading
from datetime import datetime, timezone

_lock = threading.Lock()


class Database:
    def __init__(self, path: str):
        self.path = path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.path, check_same_thread=False)

    def _init_db(self):
        with _lock, self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    chat_id INTEGER PRIMARY KEY,
                    title TEXT,
                    added_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    source_chat_id INTEGER,
                    source_chat_title TEXT,
                    topic_id INTEGER,
                    first_seen_at TEXT
                )
            """)
            conn.commit()

    # ---------- Группы ----------

    def add_group(self, chat_id: int, title: str):
        with _lock, self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO groups (chat_id, title, added_at) VALUES (?, ?, ?)",
                (chat_id, title, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def remove_group(self, chat_id: int):
        with _lock, self._connect() as conn:
            conn.execute("DELETE FROM groups WHERE chat_id = ?", (chat_id,))
            conn.commit()

    def list_groups(self):
        with _lock, self._connect() as conn:
            cur = conn.execute("SELECT chat_id, title, added_at FROM groups")
            return cur.fetchall()

    # ---------- Сотрудники ----------

    def user_exists(self, user_id: int) -> bool:
        with _lock, self._connect() as conn:
            cur = conn.execute("SELECT 1 FROM employees WHERE user_id = ?", (user_id,))
            return cur.fetchone() is not None

    def add_employee(self, user_id, username, first_name, last_name,
                      source_chat_id, source_chat_title, topic_id):
        with _lock, self._connect() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO employees
                (user_id, username, first_name, last_name, source_chat_id,
                 source_chat_title, topic_id, first_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, username, first_name, last_name,
                source_chat_id, source_chat_title, topic_id,
                datetime.now(timezone.utc).isoformat(),
            ))
            conn.commit()

    def count_employees(self) -> int:
        with _lock, self._connect() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM employees")
            return cur.fetchone()[0]

    def export_csv(self, path: str) -> str:
        with _lock, self._connect() as conn:
            cur = conn.execute("""
                SELECT user_id, username, first_name, last_name,
                       source_chat_title, topic_id, first_seen_at
                FROM employees
                ORDER BY first_seen_at
            """)
            rows = cur.fetchall()
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "user_id", "username", "first_name", "last_name",
                "source_chat", "topic_id", "first_seen_at",
            ])
            writer.writerows(rows)
        return path
