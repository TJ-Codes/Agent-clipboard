"""Main agent loop using Anthropic SDK with clipboard primitives."""

import json
import logging
from typing import Any

import anthropic

from clipboard import ClipboardState, ToolResultStore, copy_tool_definition, execute_copy
from template import template_invoke_tool_definition, execute_template_invoke
from tools import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger(__name__)


class ClipboardAgent:
    """Agent that uses clipboard primitives for efficient content handling."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic()
        self.model = model
        self.clipboard = ClipboardState()
        self.result_store = ToolResultStore()
        self.token_usage = {"input": 0, "output": 0}
        self.tool_calls = []

    def _get_all_tools(self) -> list[dict]:
        """Get all tool definitions including clipboard tools."""
        return [
            copy_tool_definition,
            template_invoke_tool_definition,
            *TOOL_DEFINITIONS,
        ]

    def _execute_tool_call(self, tool_name: str, tool_input: dict) -> dict:
        """Execute a tool call and return the result."""
        logger.info(f"TOOL CALL: {tool_name}")
        logger.info(f"TOOL INPUT: {json.dumps(tool_input, indent=2)}")

        # Track the tool call
        call_record = {
            "tool": tool_name,
            "input": tool_input,
            "used_clipboard": False,
        }

        if tool_name == "copy":
            call_record["used_clipboard"] = True
            result = execute_copy(self.clipboard, self.result_store, tool_input)

        elif tool_name == "template_invoke":
            call_record["used_clipboard"] = True
            result = execute_template_invoke(
                tool_input["template"],
                self.clipboard,
                execute_tool
            )

        else:
            result = execute_tool(tool_name, tool_input)
            # Store result for future reference by copy tool
            self.result_store.store(tool_name, result)

        call_record["result"] = result
        self.tool_calls.append(call_record)

        logger.info(f"TOOL RESULT: {json.dumps(result, indent=2)}")
        return result

    def run(self, user_prompt: str) -> str:
        """Run the agent loop with the given user prompt."""
        messages = [{"role": "user", "content": user_prompt}]

        system_prompt = """You are an AI agent with clipboard primitives for ZERO-COPY content handling.

CRITICAL: Never synthesize/re-type content. Use references instead.

## Tools

1. **copy** - Extract content by REFERENCE
   - `source`: "last", "read_file", or "read_file:0" (the harness tracks all results)
   - `pattern`: regex to extract specific content (optional)
   - `start_line`/`end_line`: line range to extract (optional)
   - `json_path`: path like "content" (optional)

   Example: copy(slot="code", source="read_file", start_line=10, end_line=25)

2. **template_invoke** - Execute a tool with clipboard substitutions
   - Use {{slot_name}} to reference clipboard content

   Example: template_invoke(template={"tool": "create_file", "parameters": {"path": "out.py", "content": "{{code}}"}})

## Workflow
1. Call a tool (e.g., read_file)
2. Use copy with source="read_file" to extract content into a slot
3. Use template_invoke with {{slot}} to use the content

You NEVER need to re-type file contents - just reference them by tool name."""

        turn = 0
        max_turns = 20

        while turn < max_turns:
            turn += 1
            logger.info(f"\n{'='*60}\nTURN {turn}\n{'='*60}")

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                tools=self._get_all_tools(),
                messages=messages,
            )

            # Track token usage
            self.token_usage["input"] += response.usage.input_tokens
            self.token_usage["output"] += response.usage.output_tokens

            logger.info(f"TOKENS: input={response.usage.input_tokens}, output={response.usage.output_tokens}")
            logger.info(f"STOP REASON: {response.stop_reason}")

            # Process response content
            assistant_content = []
            tool_results = []

            for block in response.content:
                if block.type == "text":
                    logger.info(f"ASSISTANT TEXT: {block.text}")
                    assistant_content.append(block)

                elif block.type == "tool_use":
                    assistant_content.append(block)

                    # Execute the tool
                    result = self._execute_tool_call(block.name, block.input)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })

            # Add assistant message to conversation
            messages.append({"role": "assistant", "content": assistant_content})

            # If there were tool calls, add results and continue
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            else:
                # No tool calls - agent is done
                break

        # Extract final text response
        final_text = ""
        for block in response.content:
            if block.type == "text":
                final_text += block.text

        return final_text

    def get_stats(self) -> dict:
        """Get statistics about the agent run."""
        clipboard_calls = sum(1 for c in self.tool_calls if c["tool"] == "copy")
        template_calls = sum(1 for c in self.tool_calls if c["tool"] == "template_invoke")

        # Get token savings estimate from clipboard
        token_savings = self.clipboard.get_token_savings_estimate()

        return {
            "total_tool_calls": len(self.tool_calls),
            "copy_calls": clipboard_calls,
            "template_invoke_calls": template_calls,
            "clipboard_slots": self.clipboard.list_slots(),
            "stored_results": self.result_store.list_sources(),
            "token_usage": self.token_usage,
            "token_savings": token_savings,
        }
