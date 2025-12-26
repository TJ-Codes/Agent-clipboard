"""Clipboard state management and copy tool for AI agents."""

import re
from typing import Any
import logging

logger = logging.getLogger(__name__)


class ClipboardState:
    """Manages named clipboard slots that hold typed values."""

    def __init__(self):
        self._slots: dict[str, Any] = {}
        self._bytes_stored: dict[str, int] = {}  # Track bytes per slot
        self._usage_count: dict[str, int] = {}   # Track how many times each slot is used

    def set(self, slot: str, value: Any) -> None:
        """Store a value in a named slot."""
        self._slots[slot] = value
        # Track the size of stored content
        size = len(value) if isinstance(value, str) else len(str(value))
        self._bytes_stored[slot] = size
        self._usage_count[slot] = 0
        logger.info(f"CLIPBOARD SET [{slot}]: {_truncate(value)}")

    def get(self, slot: str) -> Any:
        """Retrieve a value from a named slot. Raises KeyError if not found."""
        if slot not in self._slots:
            raise KeyError(f"Clipboard slot '{slot}' not found. Available: {list(self._slots.keys())}")
        return self._slots[slot]

    def has(self, slot: str) -> bool:
        """Check if a slot exists."""
        return slot in self._slots

    def clear(self, slot: str = None) -> None:
        """Clear a specific slot or all slots if none specified."""
        if slot:
            self._slots.pop(slot, None)
            logger.info(f"CLIPBOARD CLEAR [{slot}]")
        else:
            self._slots.clear()
            logger.info("CLIPBOARD CLEAR ALL")

    def list_slots(self) -> list[str]:
        """Return all slot names."""
        return list(self._slots.keys())

    def record_usage(self, slot: str) -> None:
        """Record that a slot was used (for token savings tracking)."""
        if slot in self._usage_count:
            self._usage_count[slot] += 1
            logger.info(f"CLIPBOARD USAGE [{slot}]: count={self._usage_count[slot]}")

    def get_token_savings_estimate(self) -> dict:
        """Estimate token savings from clipboard usage.

        Returns dict with:
        - bytes_stored: total bytes stored in clipboard
        - bytes_substituted: total bytes that were substituted via templates
        - estimated_tokens_saved: rough estimate of output tokens saved

        Note: Uses ~4 chars/token as rough estimate for code/text.
        """
        total_bytes_stored = sum(self._bytes_stored.values())

        # Calculate bytes that were actually used (substituted)
        bytes_substituted = sum(
            self._bytes_stored.get(slot, 0) * count
            for slot, count in self._usage_count.items()
        )

        # Estimate tokens: ~4 characters per token on average
        chars_per_token = 4
        estimated_tokens_saved = bytes_substituted // chars_per_token

        # Also estimate what it "cost" to use the clipboard (the slot references like {{name}})
        # Each reference is roughly len("{{slot_name}}") = 4 + len(slot_name)
        reference_overhead = sum(
            (4 + len(slot)) * count
            for slot, count in self._usage_count.items()
        )
        reference_tokens = reference_overhead // chars_per_token

        return {
            "bytes_stored": total_bytes_stored,
            "bytes_substituted": bytes_substituted,
            "estimated_tokens_saved": estimated_tokens_saved,
            "reference_overhead_tokens": reference_tokens,
            "net_tokens_saved": estimated_tokens_saved - reference_tokens,
            "slots_usage": dict(self._usage_count),
            "slots_bytes": dict(self._bytes_stored),
        }

    def __repr__(self) -> str:
        return f"ClipboardState({list(self._slots.keys())})"


class ToolResultStore:
    """Stores tool results with simple reference names.

    Supports lookups by:
    - Tool name: "read_file" returns most recent read_file result
    - Indexed: "read_file:0" returns first, "read_file:1" returns second
    - "last" returns the most recent result of any tool
    """

    def __init__(self):
        self._by_tool: dict[str, list[dict]] = {}  # tool_name -> list of results
        self._last: dict | None = None

    def store(self, tool_name: str, result: dict) -> None:
        """Store a tool result."""
        entry = {"tool": tool_name, "result": result}

        if tool_name not in self._by_tool:
            self._by_tool[tool_name] = []
        self._by_tool[tool_name].append(entry)
        self._last = entry

        idx = len(self._by_tool[tool_name]) - 1
        logger.info(f"RESULT STORE: {tool_name}:{idx}")

    def get(self, source: str) -> dict:
        """Get a stored result by reference.

        Supports:
        - "last" - most recent result
        - "read_file" - most recent read_file result
        - "read_file:0" - first read_file result
        """
        if source == "last":
            if self._last is None:
                raise KeyError("No tool results stored yet")
            return self._last

        # Parse tool_name:index format
        if ":" in source:
            tool_name, idx_str = source.rsplit(":", 1)
            if idx_str.isdigit():
                idx = int(idx_str)
            else:
                raise KeyError(f"Invalid index in source '{source}'")
        else:
            tool_name = source
            idx = -1  # Most recent

        if tool_name not in self._by_tool:
            available = list(self._by_tool.keys())
            raise KeyError(f"No results for tool '{tool_name}'. Available: {available}")

        results = self._by_tool[tool_name]
        try:
            return results[idx]
        except IndexError:
            raise KeyError(f"Index {idx} out of range for '{tool_name}' (has {len(results)} results)")

    def list_sources(self) -> list[str]:
        """Return all available source references."""
        sources = []
        for tool_name, results in self._by_tool.items():
            if len(results) == 1:
                sources.append(tool_name)
            else:
                for i in range(len(results)):
                    sources.append(f"{tool_name}:{i}")
        return sources


def _truncate(value: Any, max_len: int = 100) -> str:
    """Truncate a value for logging."""
    s = repr(value) if not isinstance(value, str) else value
    return s[:max_len] + "..." if len(s) > max_len else s


def _get_text_content(result: dict) -> str:
    """Extract text content from a tool result."""
    if isinstance(result, str):
        return result
    if "content" in result:
        return str(result["content"])
    if "text" in result:
        return str(result["text"])
    if "data" in result:
        return str(result["data"])
    return str(result)


def _extract_by_pattern(text: str, pattern: str) -> str:
    """Extract content matching a regex pattern."""
    match = re.search(pattern, text, re.DOTALL | re.MULTILINE)
    if not match:
        raise ValueError(f"Pattern '{pattern}' not found in content")
    return match.group(0)


def _extract_by_lines(text: str, start: int, end: int) -> str:
    """Extract lines from text (1-indexed, inclusive)."""
    lines = text.split('\n')
    start_idx = max(0, start - 1)
    end_idx = min(len(lines), end)
    return '\n'.join(lines[start_idx:end_idx])


def _extract_by_json_path(result: dict, path: str) -> Any:
    """Extract value from result using a simple dot-notation path."""
    parts = path.split('.')
    current = result
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            current = current[int(part)]
        else:
            raise KeyError(f"Path '{path}' not found at '{part}'")
    return current


# Anthropic tool schema for the copy tool
copy_tool_definition = {
    "name": "copy",
    "description": """Extract content from a previous tool result into a clipboard slot.

The harness tracks all tool results automatically. Reference them by:
- "last" - the most recent tool result
- "read_file" - the most recent read_file result
- "read_file:0" - the first read_file result (if multiple)

Use pattern, start_line/end_line, or json_path to extract specific content.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "slot": {
                "type": "string",
                "description": "Name of the clipboard slot to store the extracted content"
            },
            "source": {
                "type": "string",
                "description": "Source reference: 'last', tool name like 'read_file', or indexed like 'read_file:0'"
            },
            "pattern": {
                "type": "string",
                "description": "Regex pattern to extract (DOTALL mode, returns first match)"
            },
            "start_line": {
                "type": "integer",
                "description": "Start line number (1-indexed) for line-based extraction"
            },
            "end_line": {
                "type": "integer",
                "description": "End line number (1-indexed, inclusive) for line-based extraction"
            },
            "json_path": {
                "type": "string",
                "description": "Dot-notation path to extract (e.g., 'content' or 'data.items.0')"
            }
        },
        "required": ["slot", "source"]
    }
}


def execute_copy(clipboard: ClipboardState, result_store: ToolResultStore, args: dict) -> dict:
    """Execute the copy tool - extracts content from a previous tool result."""
    slot = args["slot"]
    source_ref = args["source"]

    # Get the source tool result
    source = result_store.get(source_ref)
    result = source["result"]

    logger.info(f"COPY: Extracting from '{source_ref}' ({source['tool']})")

    # Determine extraction method
    if "json_path" in args:
        extracted = _extract_by_json_path(result, args["json_path"])
        method = f"json_path={args['json_path']}"
    elif "pattern" in args:
        text = _get_text_content(result)
        extracted = _extract_by_pattern(text, args["pattern"])
        method = f"pattern={args['pattern'][:50]}..."
    elif "start_line" in args and "end_line" in args:
        text = _get_text_content(result)
        extracted = _extract_by_lines(text, args["start_line"], args["end_line"])
        method = f"lines {args['start_line']}-{args['end_line']}"
    else:
        extracted = _get_text_content(result)
        method = "full content"

    clipboard.set(slot, extracted)

    size = len(extracted) if isinstance(extracted, str) else len(str(extracted))
    logger.info(f"COPY: Extracted {size} bytes via {method}")

    return {
        "success": True,
        "slot": slot,
        "source": source_ref,
        "method": method,
        "bytes_extracted": size,
        "preview": _truncate(extracted, 200)
    }
