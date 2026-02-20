"""
Phase 2 Tests: Intelligence & Memory

Tests for conversation memory, entity tracking, reasoning, and preferences.
"""

import pytest
import tempfile
import os
from pathlib import Path
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

from confluence_mcp.agent.memory import MemoryStore


# ── Memory Tests ────────────────────────────────────────────────────────────

def test_memory_store_save_and_load():
    """Test saving and loading messages to/from SQLite database."""
    # Use temporary database
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        db_path = tmp.name

    try:
        store = MemoryStore(db_path=db_path)

        # Create test messages
        messages = [
            HumanMessage(content="Hello, can you help me?"),
            AIMessage(content="Of course! What do you need?"),
            HumanMessage(content="Search for API docs"),
            AIMessage(
                content="Found API docs",
                tool_calls=[{"name": "search_confluence", "args": {"query": "API"}, "id": "call_1"}]
            ),
            ToolMessage(content="Search results...", tool_call_id="call_1", name="search_confluence"),
        ]

        # Save session
        session_id = "test-session-123"
        store.save_session(session_id, messages)

        # Load session
        loaded_messages = store.load_session(session_id)

        # Verify round-trip
        assert len(loaded_messages) == len(messages)
        assert loaded_messages[0].content == "Hello, can you help me?"
        assert loaded_messages[1].content == "Of course! What do you need?"
        assert loaded_messages[2].content == "Search for API docs"
        assert loaded_messages[3].content == "Found API docs"
        assert loaded_messages[4].content == "Search results..."

        # Verify message types
        assert isinstance(loaded_messages[0], HumanMessage)
        assert isinstance(loaded_messages[1], AIMessage)
        assert isinstance(loaded_messages[2], HumanMessage)
        assert isinstance(loaded_messages[3], AIMessage)
        assert isinstance(loaded_messages[4], ToolMessage)

        # Verify tool calls preserved
        assert len(loaded_messages[3].tool_calls) == 1
        assert loaded_messages[3].tool_calls[0]["name"] == "search_confluence"

        # Verify ToolMessage fields
        assert loaded_messages[4].tool_call_id == "call_1"
        assert loaded_messages[4].name == "search_confluence"

    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_memory_store_empty_session():
    """Test that loading a non-existent session returns empty list."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        db_path = tmp.name

    try:
        store = MemoryStore(db_path=db_path)

        # Load non-existent session
        messages = store.load_session("nonexistent-session")

        # Should return empty list
        assert messages == []

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_memory_store_list_sessions():
    """Test listing sessions with correct metadata."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        db_path = tmp.name

    try:
        store = MemoryStore(db_path=db_path)

        # Create multiple sessions
        session1_messages = [
            HumanMessage(content="First session message 1"),
            AIMessage(content="Response 1"),
        ]
        session2_messages = [
            HumanMessage(content="Second session message 1"),
            AIMessage(content="Response 1"),
            HumanMessage(content="Second session message 2"),
        ]

        store.save_session("session-1", session1_messages)
        store.save_session("session-2", session2_messages)

        # List sessions
        sessions = store.list_sessions()

        # Should have 2 sessions
        assert len(sessions) == 2

        # Check metadata structure
        for session in sessions:
            assert "id" in session
            assert "created_at" in session
            assert "updated_at" in session
            assert "message_count" in session

        # Find our sessions
        session1_meta = next(s for s in sessions if s["id"] == "session-1")
        session2_meta = next(s for s in sessions if s["id"] == "session-2")

        # Verify message counts
        assert session1_meta["message_count"] == 2
        assert session2_meta["message_count"] == 3

        # Verify timestamps are valid ISO format strings
        from datetime import datetime
        datetime.fromisoformat(session1_meta["created_at"])  # Should not raise
        datetime.fromisoformat(session2_meta["updated_at"])  # Should not raise

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_memory_store_delete_session():
    """Test deleting a session from the database."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        db_path = tmp.name

    try:
        store = MemoryStore(db_path=db_path)

        # Create a session
        messages = [HumanMessage(content="Test message")]
        store.save_session("delete-me", messages)

        # Verify it exists
        loaded = store.load_session("delete-me")
        assert len(loaded) == 1

        # Delete it
        store.delete_session("delete-me")

        # Verify it's gone
        loaded_after = store.load_session("delete-me")
        assert loaded_after == []

        # Verify it's not in the list
        sessions = store.list_sessions()
        assert not any(s["id"] == "delete-me" for s in sessions)

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


# TODO: Add entity tracking tests (Phase 2.2)
# TODO: Add reasoning/confidence tests (Phase 2.3)
# TODO: Add preferences tests (Phase 2.4)
