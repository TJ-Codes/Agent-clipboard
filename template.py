"""Template rendering and tool dispatch for clipboard-based invocation."""

import re
import logging
from typing import Any, Callable

from clipboard import ClipboardState

logger = logging.getLogger(__name__)

# Regex to match {{slot_name}} placeholders
SLOT_PATTERN = re.compile(r"\{\{(\w+)\}\}")


# Anthropic tool schema for template_invoke
template_invoke_tool_definition = {
    "name": "template_invoke",
    "description": "Render a tool call template with clipboard substitutions, then execute it. Use {{slot_name}} syntax to reference clipboard slots. The content flows directly from clipboard to tool without re-generation.",
    "input_schema": {
        "type": "object",
        "properties": {
            "template": {
                "type": "object",
                "description": "The tool call template with {{slot}} placeholders",
                "properties": {
                    "tool": {
                        "type": "string",
                        "description": "Name of the tool to invoke"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Tool parameters, may contain {{slot}} references"
                    }
                },
                "required": ["tool", "parameters"]
            }
        },
        "required": ["template"]
    }
}


def render_template(template: Any, clipboard: ClipboardState) -> Any:
    """
    Recursively walk the template and replace {{slot_name}} references.

    Type preservation: if a slot contains a dict/list and the entire string
    is just {{slot}}, substitute the actual object. Otherwise do string interpolation.
    """
    if isinstance(template, str):
        # Check if the entire string is a single slot reference
        match = SLOT_PATTERN.fullmatch(template.strip())
        if match:
            slot_name = match.group(1)
            value = clipboard.get(slot_name)
            clipboard.record_usage(slot_name)  # Track for token savings
            logger.info(f"TEMPLATE SUBSTITUTE [{slot_name}] (full value, type={type(value).__name__})")
            return value

        # Otherwise, do string interpolation for embedded references
        def replace_slot(m):
            slot_name = m.group(1)
            value = clipboard.get(slot_name)
            clipboard.record_usage(slot_name)  # Track for token savings
            logger.info(f"TEMPLATE INTERPOLATE [{slot_name}] into string")
            return str(value)

        return SLOT_PATTERN.sub(replace_slot, template)

    elif isinstance(template, dict):
        return {k: render_template(v, clipboard) for k, v in template.items()}

    elif isinstance(template, list):
        return [render_template(item, clipboard) for item in template]

    else:
        # Numbers, booleans, None - return as-is
        return template


def execute_template_invoke(
    template: dict,
    clipboard: ClipboardState,
    tool_executor: Callable[[str, dict], dict]
) -> dict:
    """
    Render the template with clipboard substitutions and dispatch to the actual tool.

    Args:
        template: The template dict with 'tool' and 'parameters' keys
        clipboard: The clipboard state for substitution
        tool_executor: Function that takes (tool_name, args) and returns result

    Returns:
        The result from the executed tool
    """
    tool_name = template["tool"]
    raw_params = template["parameters"]

    logger.info(f"TEMPLATE_INVOKE: Rendering template for tool '{tool_name}'")
    logger.info(f"TEMPLATE_INVOKE: Raw parameters: {raw_params}")

    # Render the parameters with clipboard substitutions
    rendered_params = render_template(raw_params, clipboard)

    logger.info(f"TEMPLATE_INVOKE: Rendered parameters: {_summarize(rendered_params)}")

    # Execute the actual tool
    result = tool_executor(tool_name, rendered_params)

    return {
        "tool_executed": tool_name,
        "substitutions_applied": True,
        "result": result
    }


def _summarize(obj: Any, max_len: int = 200) -> str:
    """Create a summary of an object for logging."""
    s = repr(obj)
    return s[:max_len] + "..." if len(s) > max_len else s
