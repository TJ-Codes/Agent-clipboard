"""Sample tools to demonstrate the clipboard system."""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Output directory for file operations
OUTPUT_DIR = Path("./output")


# --- create_file tool ---

create_file_tool_definition = {
    "name": "create_file",
    "description": "Create a file with the given path and content",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path for the new file (relative to output directory)"
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file"
            }
        },
        "required": ["path", "content"]
    }
}


def execute_create_file(args: dict) -> dict:
    """Create a file with given path and content."""
    path = args["path"]
    content = args["content"]

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Resolve path within output directory
    file_path = OUTPUT_DIR / path.lstrip("/")
    file_path.parent.mkdir(parents=True, exist_ok=True)

    file_path.write_text(content)

    logger.info(f"CREATE_FILE: Created {file_path} ({len(content)} bytes)")

    return {
        "success": True,
        "path": str(file_path),
        "bytes_written": len(content)
    }


# --- read_file tool ---

read_file_tool_definition = {
    "name": "read_file",
    "description": "Read the contents of a file",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read"
            }
        },
        "required": ["path"]
    }
}


def execute_read_file(args: dict) -> dict:
    """Read a file and return its content."""
    path = args["path"]

    # Try reading from multiple locations
    file_path = Path(path)
    if not file_path.exists():
        # Try in output directory
        file_path = OUTPUT_DIR / path.lstrip("/")

    if not file_path.exists():
        return {
            "success": False,
            "error": f"File not found: {path}"
        }

    content = file_path.read_text()

    logger.info(f"READ_FILE: Read {file_path} ({len(content)} bytes)")

    return {
        "success": True,
        "path": str(file_path),
        "content": content
    }


# --- http_request tool ---

http_request_tool_definition = {
    "name": "http_request",
    "description": "Make an HTTP request (mock implementation - logs what would be sent)",
    "input_schema": {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                "description": "HTTP method"
            },
            "url": {
                "type": "string",
                "description": "URL to request"
            },
            "headers": {
                "type": "object",
                "description": "Request headers"
            },
            "body": {
                "description": "Request body (for POST/PUT/PATCH)"
            }
        },
        "required": ["method", "url"]
    }
}


def execute_http_request(args: dict) -> dict:
    """Mock HTTP request - logs what would be sent."""
    method = args["method"]
    url = args["url"]
    headers = args.get("headers", {})
    body = args.get("body")

    logger.info(f"HTTP_REQUEST: {method} {url}")
    logger.info(f"HTTP_REQUEST: Headers: {headers}")
    if body:
        logger.info(f"HTTP_REQUEST: Body: {_truncate(body)}")

    # Mock response
    return {
        "success": True,
        "mock": True,
        "message": f"Would send {method} to {url}",
        "request": {
            "method": method,
            "url": url,
            "headers": headers,
            "body": body
        }
    }


def _truncate(value: Any, max_len: int = 200) -> str:
    """Truncate a value for logging."""
    s = repr(value) if not isinstance(value, str) else value
    return s[:max_len] + "..." if len(s) > max_len else s


# --- Tool registry ---

TOOL_DEFINITIONS = [
    create_file_tool_definition,
    read_file_tool_definition,
    http_request_tool_definition,
]

TOOL_EXECUTORS = {
    "create_file": execute_create_file,
    "read_file": execute_read_file,
    "http_request": execute_http_request,
}


def execute_tool(tool_name: str, args: dict) -> dict:
    """Execute a tool by name with given arguments."""
    if tool_name not in TOOL_EXECUTORS:
        return {"error": f"Unknown tool: {tool_name}"}

    return TOOL_EXECUTORS[tool_name](args)
