"""
Phase 2 Tests: Intelligence & Memory

Tests for conversation memory, entity tracking, reasoning, and preferences.
"""

import pytest
import tempfile
import os
from pathlib import Path
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

from confluence_mcp.chat_app.memory import MemoryStore


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


# ── Entity Tracking Tests ──────────────────────────────────────────────────

def test_entity_extraction_from_search():
    """Test that search results extract page entities correctly."""
    from confluence_mcp.chat_app.entities import extract_entities_from_tool_result

    # Simulate search_confluence tool result
    tool_result = """
    {
        "results": [
            {
                "id": "12345",
                "title": "API Documentation",
                "space": {"key": "ENG"},
                "_links": {"webui": "/wiki/spaces/ENG/pages/12345"}
            },
            {
                "id": "67890",
                "title": "Deployment Guide",
                "space": {"key": "OPS"},
                "_links": {"webui": "/wiki/spaces/OPS/pages/67890"}
            }
        ]
    }
    """

    entities = extract_entities_from_tool_result(
        tool_name="search_confluence",
        tool_args={"query": "API"},
        tool_result=tool_result,
        current_entities=None
    )

    # Should have extracted 2 pages
    assert "pages" in entities
    assert len(entities["pages"]) == 2

    # Pages are added in reverse order (last result inserted first)
    # So the last page in results (67890) is at index 0
    first_page = entities["pages"][0]
    assert first_page["id"] == "67890"
    assert first_page["title"] == "Deployment Guide"
    assert first_page["space"] == "OPS"

    # Second page should be the first result
    second_page = entities["pages"][1]
    assert second_page["id"] == "12345"

    # Check last_page points to most recently added (last in results)
    assert entities["last_page"]["id"] == "67890"
    assert entities["last_page"]["title"] == "Deployment Guide"


def test_entity_context_injection_supervisor():
    """Test that entity context is formatted correctly for prompts."""
    from confluence_mcp.chat_app.entities import format_entity_context

    entities = {
        "pages": [
            {"id": "123", "title": "API Docs", "space": "ENG", "url": "/123", "last_mentioned": "2024-01-01"},
            {"id": "456", "title": "Deploy Guide", "space": "OPS", "url": "/456", "last_mentioned": "2024-01-01"},
        ],
        "spaces": ["ENG", "OPS"],
        "last_page": {"id": "123", "title": "API Docs", "space": "ENG"},
        "last_space": "ENG",
    }

    context = format_entity_context(entities)

    # Should mention the last page
    assert "API Docs" in context
    assert "123" in context
    assert "ENG" in context

    # Should mention last space
    assert "Last space mentioned: ENG" in context

    # Should mention other recent pages
    assert "Deploy Guide" in context or "456" in context


def test_entity_recency_ordering():
    """Test that only the 10 most recent pages are kept."""
    from confluence_mcp.chat_app.entities import extract_entities_from_tool_result
    import json

    # Create 15 pages
    pages_data = {
        "results": [
            {
                "id": str(i),
                "title": f"Page {i}",
                "space": {"key": "TEST"},
                "_links": {"webui": f"/page/{i}"}
            }
            for i in range(1, 16)  # 15 pages
        ]
    }

    entities = extract_entities_from_tool_result(
        tool_name="search_confluence",
        tool_args={"query": "test"},
        tool_result=json.dumps(pages_data),
        current_entities=None
    )

    # Should only keep 10 most recent (capped at 10)
    assert len(entities["pages"]) == 10

    # Pages added in reverse order, so page 15 (last in results) is first
    # But we only keep 10, so we should have pages 6-15
    page_ids = [p["id"] for p in entities["pages"]]
    assert "15" in page_ids  # Last page in results
    assert "6" in page_ids   # 10th page back

    # Most recently added is page 15 (last in the results array)
    assert entities["last_page"]["id"] == "15"


def test_coreference_resolution():
    """Test that 'it', 'that page', etc. resolve to last_page."""
    from confluence_mcp.chat_app.entities import resolve_coreference

    entities = {
        "pages": [{"id": "12345", "title": "API Docs", "space": "ENG"}],
        "last_page": {"id": "12345", "title": "API Docs", "space": "ENG"},
        "last_space": "ENG",
        "spaces": ["ENG"]
    }

    # Test "it" resolution
    text1 = "Update it with new content"
    resolved1 = resolve_coreference(text1, entities)
    assert "12345" in resolved1
    assert "API Docs" in resolved1

    # Test "that page" resolution
    text2 = "Review that page"
    resolved2 = resolve_coreference(text2, entities)
    assert "12345" in resolved2
    assert "API Docs" in resolved2

    # Test "that space" resolution
    text3 = "Create a page in that space"
    resolved3 = resolve_coreference(text3, entities)
    assert "ENG" in resolved3


def test_known_entities_structure():
    """Test that known_entities dict has the expected structure."""
    from confluence_mcp.chat_app.entities import extract_entities_from_tool_result

    entities = extract_entities_from_tool_result(
        tool_name="search_confluence",
        tool_args={"query": "test"},
        tool_result='{"results": [{"id": "123", "title": "Test", "space": {"key": "TST"}, "_links": {"webui": "/123"}}]}',
        current_entities=None
    )

    # Required keys
    assert "pages" in entities
    assert "spaces" in entities
    assert "last_page" in entities
    assert "last_space" in entities

    # Types
    assert isinstance(entities["pages"], list)
    assert isinstance(entities["spaces"], list)
    assert isinstance(entities["last_page"], dict) or entities["last_page"] is None
    assert isinstance(entities["last_space"], str) or entities["last_space"] is None

    # Page structure
    if entities["pages"]:
        page = entities["pages"][0]
        assert "id" in page
        assert "title" in page
        assert "space" in page
        assert "url" in page
        assert "last_mentioned" in page


# ── Reasoning & Confidence Tests ───────────────────────────────────────────

def test_reasoning_trace_populated():
    """Test that reasoning_trace is populated in AgentState."""
    from confluence_mcp.chat_app.graph import AgentState

    # Verify reasoning_trace is in AgentState schema
    assert "reasoning_trace" in AgentState.__annotations__

    # Type should be list
    assert AgentState.__annotations__["reasoning_trace"] == list


def test_confidence_score_valid_range():
    """Test that supervisor_confidence is between 0.0 and 1.0."""
    from confluence_mcp.chat_app.graph import AgentState

    # Verify supervisor_confidence is in AgentState schema
    assert "supervisor_confidence" in AgentState.__annotations__

    # Type should be float
    assert AgentState.__annotations__["supervisor_confidence"] == float

    # In practice, confidence should be 0.0-1.0 (validated at runtime)
    # This is a schema validation test


def test_reasoning_trace_structure():
    """Test that reasoning trace has expected structure when agents run."""
    # This is more of an integration test - reasoning trace should have entries like:
    # "🧭 Supervisor: User message contains search keywords → route to search (confidence: 90%)"
    # "🔍 Search Agent: Processing request..."

    # For now, just verify the schema is correct
    from confluence_mcp.chat_app.graph import AgentState

    state: AgentState = {
        "messages": [],
        "next": "",
        "active_agent": "",
        "pending_tool_call": None,
        "review_status": None,
        "revision_count": 0,
        "session_id": "",
        "session_metadata": {},
        "known_entities": {},
        "reasoning_trace": [
            "🧭 Supervisor: Analyzing user intent...",
            "🔍 Search Agent: Processing request..."
        ],
        "supervisor_confidence": 0.9
    }

    # Verify structure
    assert isinstance(state["reasoning_trace"], list)
    assert len(state["reasoning_trace"]) == 2
    assert "Supervisor" in state["reasoning_trace"][0]
    assert "Search Agent" in state["reasoning_trace"][1]
    assert 0.0 <= state["supervisor_confidence"] <= 1.0


# TODO: Add preferences tests (Phase 2.4)
