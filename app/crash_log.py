"""
Crash logger — catches and logs every swallowed exception.
The game keeps running (fallbacks work), but every real failure
gets written to crash_log.txt so we can diagnose what's broken.
"""
import traceback
import datetime
import os

# Log file lives in the project root
LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "crash_log.txt")

def log_crash(function_name, args_summary, exception, fallback_used="unknown"):
    """
    Call this inside every try/except block that uses a fallback.
    Writes the full error to crash_log.txt without interrupting the game.

    Usage:
        try:
            result = some_engine_function(arg1, arg2)
        except Exception as e:
            log_crash("some_engine_function", f"arg1={arg1}, arg2={arg2}", e, "used default result")
            result = default_result
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tb = traceback.format_exc()

    entry = (
        f"\n{'='*70}\n"
        f"[{timestamp}] CAUGHT EXCEPTION in {function_name}\n"
        f"  Args: {args_summary[:300]}\n"  # truncate long args
        f"  Error: {type(exception).__name__}: {exception}\n"
        f"  Fallback: {fallback_used}\n"
        f"  Traceback:\n{tb}\n"
    )

    try:
        with open(LOG_PATH, "a") as f:
            f.write(entry)
    except Exception:
        pass  # if we can't even write the log, don't crash the game over it


def clear_log():
    """Clear the crash log at game start."""
    try:
        with open(LOG_PATH, "w") as f:
            f.write(f"# Crash log — started {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    except Exception:
        pass


def get_crash_summary():
    """Read the log and return a count + last few entries for display."""
    try:
        if not os.path.exists(LOG_PATH):
            return "No crashes logged."
        with open(LOG_PATH, "r") as f:
            content = f.read()
        count = content.count("CAUGHT EXCEPTION")
        if count == 0:
            return "No crashes logged."
        # Get the last entry
        entries = content.split("=" * 70)
        last = entries[-1].strip() if entries else ""
        return f"{count} exception(s) caught. Most recent:\n{last[:500]}"
    except Exception:
        return "Could not read crash log."
