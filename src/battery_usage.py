"""
Simple module that parses the macOS `pmset -g log` to get usage information to get "screen on" time.

Note that this is an approximation and may change between versions of macOS.
"""
import re as _re
import sys as _sys
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


_PMSET_PS_ARGS = ("pmset", "-g", "ps")
_PMSET_PS_PATT = _re.compile(
    r"Now drawing from '(?P<source>[^']+)'.*?(?P<charge>\d+)%",
    _re.DOTALL | _re.MULTILINE | _re.IGNORECASE,
)


def pmset_ps() -> ChargeEvent:
    text = _subprocess.check_output(_PMSET_PS_ARGS, encoding="UTF-8")
    match = _PMSET_PS_PATT.search(text)
    print(f"Found: '{text}'", file=_sys.stderr)
    if not match:
        raise Exception("Could not determine battery status")

    charge_type = (
        ChargeType.BATT if match["source"] == "Battery Power" else ChargeType.AC
    )
    charge = int(match["charge"])
    return ChargeEvent(datetime.now().astimezone(), charge_type, charge)


def main():
    if _sys.platform != _TARGET_PLATFORM:
        print(f"Expected macOS (darwin), found {_sys.platform}", file=_sys.stderr)
        _sys.exit(1)
    with pmset_log_proc() as p:
        count = 0
        for line in p.stdout:
            count += 1
        print(f"Found {count} lines!")
    print(f"Current: {pmset_ps()}")


if __name__ == "__main__":
    main()
