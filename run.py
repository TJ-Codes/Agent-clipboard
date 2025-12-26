#!/usr/bin/env python3
"""CLI test harness for the clipboard agent experiment."""

import argparse
import json
import logging
import sys

from agent import ClipboardAgent
from test_logger import TestLogger


def setup_logging(verbose: bool = False):
    """Configure logging for the experiment."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def print_separator(title: str = ""):
    """Print a visual separator."""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}\n")
    else:
        print(f"\n{'-'*60}\n")


def print_tool_calls(agent: ClipboardAgent):
    """Print a summary of all tool calls."""
    print_separator("TOOL CALL SUMMARY")

    for i, call in enumerate(agent.tool_calls, 1):
        clipboard_indicator = " [CLIPBOARD]" if call["used_clipboard"] else ""
        print(f"{i}. {call['tool']}{clipboard_indicator}")

        # Truncate input for display
        input_str = json.dumps(call["input"], indent=2)
        if len(input_str) > 500:
            input_str = input_str[:500] + "\n   ... (truncated)"
        print(f"   Input: {input_str}")

        # Truncate result for display
        result_str = json.dumps(call["result"], indent=2)
        if len(result_str) > 300:
            result_str = result_str[:300] + "\n   ... (truncated)"
        print(f"   Result: {result_str}")
        print()


def print_stats(agent: ClipboardAgent):
    """Print agent statistics."""
    stats = agent.get_stats()

    print_separator("STATISTICS")

    print(f"Total tool calls: {stats['total_tool_calls']}")
    print(f"  - copy calls: {stats['copy_calls']}")
    print(f"  - template_invoke calls: {stats['template_invoke_calls']}")
    print(f"  - other tool calls: {stats['total_tool_calls'] - stats['copy_calls'] - stats['template_invoke_calls']}")
    print()
    print(f"Clipboard slots used: {stats['clipboard_slots']}")
    print()
    print(f"Token usage:")
    print(f"  - Input tokens:  {stats['token_usage']['input']:,}")
    print(f"  - Output tokens: {stats['token_usage']['output']:,}")
    print(f"  - Total tokens:  {stats['token_usage']['input'] + stats['token_usage']['output']:,}")

    # Print token savings estimate
    savings = stats.get('token_savings', {})
    if savings.get('bytes_substituted', 0) > 0:
        print_separator("TOKEN SAVINGS ESTIMATE")
        print(f"Bytes stored in clipboard:     {savings['bytes_stored']:,}")
        print(f"Bytes substituted via slots:   {savings['bytes_substituted']:,}")
        print()
        print(f"Estimated output tokens saved: {savings['estimated_tokens_saved']:,}")
        print(f"Reference overhead tokens:     {savings['reference_overhead_tokens']:,}")
        print(f"Net tokens saved:              {savings['net_tokens_saved']:,}")
        print()

        # Show slot-by-slot breakdown
        if savings.get('slots_usage'):
            print("Slot usage breakdown:")
            for slot, count in savings['slots_usage'].items():
                slot_bytes = savings['slots_bytes'].get(slot, 0)
                if count > 0:
                    print(f"  - {slot}: {count} use(s), {slot_bytes:,} bytes each = {slot_bytes * count:,} bytes saved")

        # Calculate percentage of output tokens saved
        actual_output = stats['token_usage']['output']
        if actual_output > 0:
            # What would output have been without clipboard?
            hypothetical_output = actual_output + savings['net_tokens_saved']
            pct_saved = (savings['net_tokens_saved'] / hypothetical_output) * 100 if hypothetical_output > 0 else 0
            print()
            print(f"Actual output tokens:          {actual_output:,}")
            print(f"Hypothetical without copy:     ~{hypothetical_output:,}")
            print(f"Estimated savings:             ~{pct_saved:.1f}% of output tokens")


def main():
    parser = argparse.ArgumentParser(
        description="Run the clipboard agent experiment"
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="The prompt to send to the agent"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-20250514",
        help="Model to use (default: claude-sonnet-4-20250514)"
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="JSON log file name (default: auto-generated with timestamp)"
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Disable JSON logging"
    )

    args = parser.parse_args()

    setup_logging(args.verbose)

    # Get prompt from argument or stdin
    if args.prompt:
        prompt = args.prompt
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()
    else:
        print("Enter your prompt (Ctrl+D to finish):")
        prompt = sys.stdin.read().strip()

    if not prompt:
        print("Error: No prompt provided")
        sys.exit(1)

    print_separator("CLIPBOARD AGENT EXPERIMENT")
    print(f"Model: {args.model}")
    print(f"Prompt: {prompt}")
    print_separator()

    # Initialize test logger
    test_logger = None if args.no_log else TestLogger(log_file=args.log_file)

    # Run the agent
    agent = ClipboardAgent(model=args.model)
    success = True
    error_msg = None
    result = None

    try:
        result = agent.run(prompt)
    except Exception as e:
        logging.exception("Agent failed")
        success = False
        error_msg = str(e)

    # Log the test result
    if test_logger:
        stats = agent.get_stats() if agent else {}
        tool_calls = agent.tool_calls if agent else []
        entry = test_logger.log_test(
            prompt=prompt,
            model=args.model,
            result=result or "",
            tool_calls=tool_calls,
            stats=stats,
            success=success,
            error=error_msg,
        )
        print_separator("TEST LOGGED")
        print(f"Log file: {test_logger.get_log_path()}")
        print(f"Entry ID: {entry['id']}")

    if not success:
        sys.exit(1)

    # Print results
    print_separator("AGENT RESPONSE")
    print(result)

    print_tool_calls(agent)
    print_stats(agent)


if __name__ == "__main__":
    main()
