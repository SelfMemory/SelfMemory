#!/usr/bin/env python3
"""
Commit message validator for format: #[card-number] | [@[who worked], @[if need multiple]] [commit message]
"""

import re
import sys
from pathlib import Path


def validate_commit_message(commit_msg: str) -> tuple[bool, str]:
    """
    Validate commit message format.

    Expected format: #[card-number] | [@[who worked], @[if need multiple]] [commit message]

    Examples:
        ✓ #123 | [@john] Fix login bug
        ✓ #456 | [@jane, @bob] Add new feature
        ✓ #789 | [@alice] Update documentation

    Returns:
        tuple: (is_valid, error_message)
    """
    # Pattern breakdown:
    # ^#\d+ - starts with # followed by one or more digits (card number)
    # \s*\|\s* - pipe separator with optional whitespace
    # \[@\w+(,\s*@\w+)*\] - bracket with one or more @mentions (e.g., [@username] or [@user1, @user2])
    # (,\s*\[@\w+(,\s*@\w+)*\])* - optional additional bracket groups
    # \s+ - at least one space before message
    # .+ - actual commit message (at least one character)
    # $ - end of string
    pattern = r"^#\d+\s*\|\s*\[@\w+(,\s*@\w+)*\](,\s*\[@\w+(,\s*@\w+)*\])*\s+.+$"

    # Remove leading/trailing whitespace
    commit_msg = commit_msg.strip()

    # Skip merge commits and other special commits
    if commit_msg.startswith("Merge ") or commit_msg.startswith("Revert "):
        return True, ""

    if not re.match(pattern, commit_msg):
        error_msg = f"""
❌ Invalid commit message format!

Required format:
    #[card-number] | [@[who worked], @[if need multiple]] [commit message]

Examples:
    ✓ #123 | [@john] Fix login bug
    ✓ #456 | [@jane, @bob] Add new feature
    ✓ #789 | [@alice] Update documentation

Your message:
    {commit_msg}

Format rules:
    1. Start with # followed by card number (digits only)
    2. Use | as separator
    3. Include at least one @mention in square brackets: [@username]
    4. Multiple mentions can be:
       - In one bracket: [@user1, @user2]
       - Or separate brackets: [@user1], [@user2]
    5. End with descriptive commit message
"""
        return False, error_msg

    return True, ""


def main():
    """Main entry point for commit-msg hook."""
    if len(sys.argv) < 2:
        print("Error: No commit message file provided")
        sys.exit(1)

    commit_msg_file = sys.argv[1]

    try:
        commit_msg = Path(commit_msg_file).read_text(encoding="utf-8").strip()
    except Exception as e:
        print(f"Error reading commit message file: {e}")
        sys.exit(1)

    # Skip empty commit messages
    if not commit_msg:
        print("❌ Commit message cannot be empty!")
        sys.exit(1)

    is_valid, error_msg = validate_commit_message(commit_msg)

    if not is_valid:
        print(error_msg)
        sys.exit(1)

    # Success
    sys.exit(0)


if __name__ == "__main__":
    main()
