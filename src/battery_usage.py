"""
Simple module that parses the macOS `pmset -g log` to get usage information to get "screen on" time.

Note that this is an approximation and may change between versions of macOS.
"""
import re as _re
import subprocess as _subprocess

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

_TARGET_PLATFORM = "darwin"
_TIMESTAMP_PAT_STR = r"(?P<timestamp>\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})"
_CHARGE_PAT = _re.compile(
    _TIMESTAMP_PAT_STR
    + r".*?Using (?P<type>AC|Batt|BATT).*?\(Charge:\s*(?P<charge>\d+)",
    _re.IGNORECASE,
)
_DISPLAY_PAT = _re.compile(
    _TIMESTAMP_PAT_STR + r".*?Display is turned (?P<state>\w+)", _re.IGNORECASE
)


class ChargeType(Enum):
    AC = 0
    BATT = 1


class DisplayState(Enum):
    OFF = 0
    ON = 1


@dataclass
class ChargeEvent:
    ts: datetime
    type: ChargeType
    charge: int


@dataclass
class DisplayEvent:
    ts: datetime
    state: DisplayState


_GREP_ARGS = (
    "grep",
    "-e",
    "[[:blank:]]Using[[:blank:]]",
    "-e",
    "[[:blank:]]Display is turned[[:blank:]]",
)
_PMSET_LOG_ARGS = ("pmset", "-g", "log")


def pmset_log_proc() -> _subprocess.Popen:
    """Runs `pmset -g log` pre-filtering lines with `grep` and returns the `Popen` object"""
    pmset_proc = _subprocess.Popen(_PMSET_LOG_ARGS, stdout=_subprocess.PIPE)
    grep_proc = _subprocess.Popen(
        _GREP_ARGS, encoding="UTF-8", stdin=pmset_proc.stdout, stdout=_subprocess.PIPE
    )
    return grep_proc


def main():
    import sys

    if sys.platform != _TARGET_PLATFORM:
        print(f"Expected macOS (darwin), found {sys.platform}", file=sys.stderr)
        sys.exit(1)
    with pmset_log_proc() as p:
        count = 0
        for line in p.stdout:
            count += 1
        print(f"Found {count} lines!")


if __name__ == "__main__":
    main()
