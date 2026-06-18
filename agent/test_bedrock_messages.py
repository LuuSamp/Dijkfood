"""Tests for Bedrock Converse message normalization."""

from agent.bedrock_messages import (
    merge_tool_result_messages,
    sanitize_bedrock_messages,
    trim_bedrock_messages,
)


def _tool_use(tool_id: str, name: str = "get_order") -> dict:
    return {"toolUse": {"toolUseId": tool_id, "name": name, "input": {}}}


def _tool_result(tool_id: str) -> dict:
    return {
        "toolResult": {
            "toolUseId": tool_id,
            "content": [{"json": {"ok": True}}],
            "status": "success",
        }
    }


def test_merge_split_parallel_tool_results():
    messages = [
        {"role": "user", "content": [{"text": "hi"}]},
        {"role": "assistant", "content": [_tool_use("a"), _tool_use("b")]},
        {"role": "user", "content": [_tool_result("a")]},
        {"role": "user", "content": [_tool_result("b")]},
    ]
    merged = merge_tool_result_messages(messages)
    assert len(merged) == 3
    assert len(merged[2]["content"]) == 2


def test_sanitize_drops_orphaned_tool_use():
    messages = [
        {"role": "assistant", "content": [_tool_use("x")]},
        {"role": "user", "content": [{"text": "follow up"}]},
    ]
    cleaned = sanitize_bedrock_messages(messages)
    assert cleaned == [{"role": "user", "content": [{"text": "follow up"}]}]


def test_sanitize_keeps_complete_tool_turn():
    messages = [
        {"role": "user", "content": [{"text": "order?"}]},
        {"role": "assistant", "content": [_tool_use("x")]},
        {"role": "user", "content": [_tool_result("x")]},
        {"role": "assistant", "content": [{"text": "done"}]},
    ]
    cleaned = sanitize_bedrock_messages(messages)
    assert cleaned == messages


def test_sanitize_strips_trailing_tool_result():
    messages = [
        {"role": "user", "content": [{"text": "order?"}]},
        {"role": "assistant", "content": [_tool_use("x")]},
        {"role": "user", "content": [_tool_result("x")]},
    ]
    cleaned = sanitize_bedrock_messages(messages)
    assert cleaned == [{"role": "user", "content": [{"text": "order?"}]}]


def test_trim_does_not_start_on_orphan_tool_result():
    messages = [
        {"role": "user", "content": [{"text": f"msg{i}"}]}
        for i in range(6)
    ]
    messages.extend(
        [
            {"role": "assistant", "content": [_tool_use("t")]},
            {"role": "user", "content": [_tool_result("t")]},
            {"role": "assistant", "content": [{"text": "answer"}]},
        ]
    )
    trimmed = trim_bedrock_messages(messages, max_count=4)
    assert trimmed[0]["role"] != "user" or "toolResult" not in trimmed[0]["content"][0]
    assert any(block.get("toolUse") for block in trimmed[0].get("content", [])) or trimmed[0]["content"][0].get("text")
