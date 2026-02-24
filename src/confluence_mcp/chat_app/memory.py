"""
Conversation memory persistence using SQLite.

This module provides the MemoryStore class for saving and loading
conversation history across sessions.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
)


class MemoryStore:
    """SQLite-backed conversation history storage.

    Stores conversation messages in a local SQLite database for persistence
    across sessions. Messages are serialized to JSON for storage.

    Storage location: ~/.confluence_mcp/memory.db
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize the memory store.

        Args:
            db_path: Path to SQLite database. If None, uses default location
                    (~/.confluence_mcp/memory.db)
        """
        if db_path is None:
            # Default storage in user's home directory
            home = Path.home()
            conf_dir = home / ".confluence_mcp"
            conf_dir.mkdir(exist_ok=True)
            db_path = str(conf_dir / "memory.db")

        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                messages_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                message_count INTEGER NOT NULL
            )
        """)

        conn.commit()
        conn.close()

    def save_session(self, session_id: str, messages: List[BaseMessage]) -> None:
        """Save conversation messages for a session.

        Args:
            session_id: Unique session identifier
            messages: List of LangChain messages to save
        """
        # Serialize messages to JSON
        messages_json = json.dumps([self._serialize_message(msg) for msg in messages])

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if session exists
        cursor.execute("SELECT created_at FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()

        if row:
            # Update existing session
            created_at = row[0]
            updated_at = datetime.now().isoformat()

            cursor.execute("""
                UPDATE sessions
                SET messages_json = ?, updated_at = ?, message_count = ?
                WHERE id = ?
            """, (messages_json, updated_at, len(messages), session_id))
        else:
            # Create new session
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO sessions (id, messages_json, created_at, updated_at, message_count)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, messages_json, now, now, len(messages)))

        conn.commit()
        conn.close()

    def load_session(self, session_id: str) -> List[BaseMessage]:
        """Load conversation messages for a session.

        Args:
            session_id: Unique session identifier

        Returns:
            List of LangChain messages. Returns empty list if session not found.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT messages_json FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return []

        # Deserialize messages from JSON
        messages_data = json.loads(row[0])
        return [self._deserialize_message(msg_data) for msg_data in messages_data]

    def list_sessions(self) -> List[Dict]:
        """List all saved sessions with metadata.

        Returns:
            List of session metadata dicts with keys:
            - id: Session ID
            - created_at: Creation timestamp (ISO format)
            - updated_at: Last update timestamp (ISO format)
            - message_count: Number of messages in session
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, created_at, updated_at, message_count
            FROM sessions
            ORDER BY updated_at DESC
        """)

        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                "id": row[0],
                "created_at": row[1],
                "updated_at": row[2],
                "message_count": row[3],
            })

        conn.close()
        return sessions

    def delete_session(self, session_id: str) -> None:
        """Delete a session from the database.

        Args:
            session_id: Unique session identifier
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        conn.close()

    def _serialize_message(self, message: BaseMessage) -> Dict:
        """Convert a LangChain message to a JSON-serializable dict.

        Args:
            message: LangChain message object

        Returns:
            Dict with message type and content
        """
        msg_dict = {
            "type": message.__class__.__name__,
            "content": message.content,
        }

        # Handle additional fields for specific message types
        if isinstance(message, AIMessage) and hasattr(message, "tool_calls"):
            msg_dict["tool_calls"] = message.tool_calls

        if isinstance(message, ToolMessage):
            msg_dict["tool_call_id"] = message.tool_call_id
            if hasattr(message, "name"):
                msg_dict["name"] = message.name

        return msg_dict

    def _deserialize_message(self, msg_data: Dict) -> BaseMessage:
        """Convert a JSON dict back to a LangChain message.

        Args:
            msg_data: Dict with message type and content

        Returns:
            LangChain message object
        """
        msg_type = msg_data["type"]
        content = msg_data["content"]

        if msg_type == "HumanMessage":
            return HumanMessage(content=content)
        elif msg_type == "AIMessage":
            tool_calls = msg_data.get("tool_calls", [])
            return AIMessage(content=content, tool_calls=tool_calls)
        elif msg_type == "SystemMessage":
            return SystemMessage(content=content)
        elif msg_type == "ToolMessage":
            return ToolMessage(
                content=content,
                tool_call_id=msg_data.get("tool_call_id", ""),
                name=msg_data.get("name", ""),
            )
        else:
            # Fallback for unknown message types
            return HumanMessage(content=content)
