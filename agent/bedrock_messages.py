"""Normalize and validate Bedrock Converse message history for tool calling."""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def _tool_use_ids(msg: dict[str, Any]) -> list[str]:
    if msg.get("role") != "assistant":
        return []
    return [
        str(block["toolUse"]["toolUseId"])
        for block in msg.get("content", [])
        if "toolUse" in block and block["toolUse"].get("toolUseId")
    ]


def _tool_result_ids(msg: dict[str, Any]) -> list[str]:
    if msg.get("role") != "user":
        return []
    return [
        str(block["toolResult"]["toolUseId"])
        for block in msg.get("content", [])
        if "toolResult" in block and block["toolResult"].get("toolUseId")
    ]


def _is_tool_result_only_user(msg: dict[str, Any]) -> bool:
    if msg.get("role") != "user":
        return False
    content = msg.get("content") or []
    return bool(content) and all("toolResult" in block for block in content)


def merge_tool_result_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group consecutive user messages that contain only toolResult blocks."""
    merged: list[dict[str, Any]] = []
    for msg in messages:
        if _is_tool_result_only_user(msg) and merged and _is_tool_result_only_user(merged[-1]):
            merged[-1] = {
                "role": "user",
                "content": list(merged[-1].get("content", [])) + list(msg.get("content", [])),
            }
        else:
            merged.append(msg)
    return merged


def sanitize_bedrock_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Repair history for Bedrock Converse:
    - merge split parallel tool results into one user message
    - drop incomplete tool_use / toolResult pairs
    - drop orphaned toolResult-only user messages
    - drop trailing incomplete tool turns
    """
    if not messages:
        return []

    msgs = merge_tool_result_messages(messages)
    cleaned: list[dict[str, Any]] = []
    i = 0
    while i < len(msgs):
        msg = msgs[i]
        tool_ids = _tool_use_ids(msg)
        if tool_ids:
            if i + 1 >= len(msgs):
                log.warning("dropping trailing assistant tool_use without toolResult")
                break
            nxt = msgs[i + 1]
            if not _is_tool_result_only_user(nxt):
                log.warning("dropping assistant tool_use without matching toolResult user message")
                i += 1
                continue
            if set(tool_ids) != set(_tool_result_ids(nxt)):
                log.warning("dropping mismatched tool_use/toolResult pair")
                i += 2
                continue
            cleaned.append(msg)
            cleaned.append(nxt)
            i += 2
            continue

        if _is_tool_result_only_user(msg):
            log.warning("dropping orphaned toolResult user message")
            i += 1
            continue

        cleaned.append(msg)
        i += 1

    while cleaned and _is_tool_result_only_user(cleaned[-1]):
        log.warning("dropping trailing incomplete toolResult message")
        cleaned.pop()

    while cleaned and _tool_use_ids(cleaned[-1]):
        log.warning("dropping trailing incomplete assistant tool_use message")
        cleaned.pop()

    return cleaned


def trim_bedrock_messages(messages: list[dict[str, Any]], max_count: int) -> list[dict[str, Any]]:
    """Keep the most recent messages without splitting tool_use/toolResult pairs."""
    msgs = sanitize_bedrock_messages(messages)
    if len(msgs) <= max_count:
        return msgs

    start = len(msgs) - max_count
    while start < len(msgs):
        msg = msgs[start]
        if _is_tool_result_only_user(msg):
            start += 1
            continue
        if _tool_use_ids(msg):
            if start + 1 < len(msgs) and _is_tool_result_only_user(msgs[start + 1]):
                break
            start += 1
            continue
        break

    if start >= len(msgs):
        return []

    return sanitize_bedrock_messages(msgs[start:])
