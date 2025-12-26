"""Example file for testing the clipboard agent."""

import os
import sys


def helper_function():
    """A helper function that does something."""
    return "helper result"


def main():
    """Main entry point for the application.

    This function demonstrates a typical main function that:
    1. Parses command line arguments
    2. Sets up configuration
    3. Runs the main logic
    """
    print("Starting application...")

    # Get config from environment
    debug = os.environ.get("DEBUG", "false").lower() == "true"

    if debug:
        print("Debug mode enabled")

    # Run main logic
    result = helper_function()
    print(f"Result: {result}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
