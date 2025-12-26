"""JSON logging mechanism for test results."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


class TestLogger:
    """Logger that writes test results to a JSON log file."""

    def __init__(self, log_dir: str = "logs", log_file: str = None):
        """
        Initialize the test logger.

        Args:
            log_dir: Directory to store log files
            log_file: Optional specific log file name. If None, uses timestamped name.
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        if log_file:
            self.log_file = self.log_dir / log_file
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_file = self.log_dir / f"test_results_{timestamp}.json"

        # Initialize log file with empty array if it doesn't exist
        if not self.log_file.exists():
            self._write_entries([])

    def _read_entries(self) -> list[dict]:
        """Read existing log entries from file."""
        try:
            with open(self.log_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write_entries(self, entries: list[dict]):
        """Write log entries to file."""
        with open(self.log_file, "w") as f:
            json.dump(entries, f, indent=2, default=str)

    def log_test(
        self,
        prompt: str,
        model: str,
        result: str,
        tool_calls: list[dict],
        stats: dict,
        success: bool = True,
        error: str = None,
        metadata: dict = None,
    ) -> dict:
        """
        Log a single test result.

        Args:
            prompt: The user prompt sent to the agent
            model: The model used for the test
            result: The agent's final response
            tool_calls: List of tool call records from the agent
            stats: Statistics from agent.get_stats()
            success: Whether the test completed successfully
            error: Error message if the test failed
            metadata: Optional additional metadata

        Returns:
            The logged entry
        """
        entry = {
            "id": self._generate_id(),
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "model": model,
            "success": success,
            "result": result,
            "error": error,
            "tool_calls": tool_calls,
            "statistics": stats,
            "metadata": metadata or {},
        }

        entries = self._read_entries()
        entries.append(entry)
        self._write_entries(entries)

        return entry

    def _generate_id(self) -> str:
        """Generate a unique ID for the log entry."""
        entries = self._read_entries()
        return f"test_{len(entries) + 1:04d}"

    def get_log_path(self) -> str:
        """Return the path to the current log file."""
        return str(self.log_file)

    def get_all_entries(self) -> list[dict]:
        """Get all log entries."""
        return self._read_entries()

    def get_summary(self) -> dict:
        """
        Generate a summary of all logged tests.

        Returns:
            Dictionary with summary statistics
        """
        entries = self._read_entries()

        if not entries:
            return {
                "total_tests": 0,
                "successful_tests": 0,
                "failed_tests": 0,
                "total_tool_calls": 0,
                "total_tokens": {"input": 0, "output": 0},
                "token_savings": {
                    "total_bytes_substituted": 0,
                    "total_tokens_saved": 0,
                    "average_savings_pct": 0,
                },
                "models_used": [],
            }

        successful = sum(1 for e in entries if e.get("success", False))
        total_tool_calls = sum(
            len(e.get("tool_calls", [])) for e in entries
        )
        total_input_tokens = sum(
            e.get("statistics", {}).get("token_usage", {}).get("input", 0)
            for e in entries
        )
        total_output_tokens = sum(
            e.get("statistics", {}).get("token_usage", {}).get("output", 0)
            for e in entries
        )
        models = list(set(e.get("model", "unknown") for e in entries))

        # Aggregate token savings
        total_bytes_substituted = sum(
            e.get("statistics", {}).get("token_savings", {}).get("bytes_substituted", 0)
            for e in entries
        )
        total_net_tokens_saved = sum(
            e.get("statistics", {}).get("token_savings", {}).get("net_tokens_saved", 0)
            for e in entries
        )

        # Calculate average savings percentage
        savings_pcts = []
        for e in entries:
            savings = e.get("statistics", {}).get("token_savings", {})
            output = e.get("statistics", {}).get("token_usage", {}).get("output", 0)
            net_saved = savings.get("net_tokens_saved", 0)
            if output > 0 and net_saved > 0:
                hypothetical = output + net_saved
                pct = (net_saved / hypothetical) * 100
                savings_pcts.append(pct)

        avg_savings_pct = sum(savings_pcts) / len(savings_pcts) if savings_pcts else 0

        return {
            "total_tests": len(entries),
            "successful_tests": successful,
            "failed_tests": len(entries) - successful,
            "total_tool_calls": total_tool_calls,
            "total_tokens": {
                "input": total_input_tokens,
                "output": total_output_tokens,
            },
            "token_savings": {
                "total_bytes_substituted": total_bytes_substituted,
                "total_tokens_saved": total_net_tokens_saved,
                "average_savings_pct": round(avg_savings_pct, 1),
            },
            "models_used": models,
        }


# Convenience function for simple logging
def log_test_result(
    prompt: str,
    model: str,
    result: str,
    tool_calls: list[dict],
    stats: dict,
    success: bool = True,
    error: str = None,
    log_file: str = None,
) -> str:
    """
    Log a test result to a JSON file.

    Args:
        prompt: The user prompt sent to the agent
        model: The model used for the test
        result: The agent's final response
        tool_calls: List of tool call records from the agent
        stats: Statistics from agent.get_stats()
        success: Whether the test completed successfully
        error: Error message if the test failed
        log_file: Optional specific log file name

    Returns:
        Path to the log file
    """
    logger = TestLogger(log_file=log_file)
    logger.log_test(
        prompt=prompt,
        model=model,
        result=result,
        tool_calls=tool_calls,
        stats=stats,
        success=success,
        error=error,
    )
    return logger.get_log_path()
