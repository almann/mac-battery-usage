"""
Simple module that parses the macOS `pmset -g log` to get usage information to get "screen on" time.

Note that this is an approximation and may change between versions of macOS.
"""
import re as _re
import sys as _sys
import subprocess as _subprocess
import collections.abc as _coll_types


from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

_TARGET_PLATFORM = "darwin"
_TIMESTAMP_PAT_STR = r"(?P<timestamp>\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\s[+-]\d{4})"
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

    def __str__(self):
        return f"{ts_to_str(self.ts)}, {self.type.name}, {self.charge}%"


@dataclass
class DisplayEvent:
    ts: datetime
    state: DisplayState

    def __str__(self):
        return f"{ts_to_str(self.ts)}, Display {self.state.name}"


def ts_to_str(ts: datetime):
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def parse_ts(ts_text: str) -> datetime:
    """Parses the `pmset` log formatted timestamp into a local `datetime`"""
    return datetime.strptime(ts_text, "%Y-%m-%d %H:%M:%S %z")


_EVENT_TYPE = ChargeEvent | DisplayEvent


def parse_log(
    log_lines: _coll_types.Iterator[str],
) -> _coll_types.Sequence[_EVENT_TYPE]:
    events = []
    for line in log_lines:
        # is this a charge line?
        match = _CHARGE_PAT.match(line)
        if match:
            charge_text = match["type"].upper()
            charge_type = ChargeType[charge_text]
            ts = parse_ts(match["timestamp"])
            charge_amount = int(match["charge"])
            events.append(ChargeEvent(ts, charge_type, charge_amount))
            continue

        # TODO probably could refactor this into one match
        # is this a display line?
        match = _DISPLAY_PAT.match(line)
        if not match:
            continue
        ts = parse_ts(match["timestamp"])
        display_text = match["state"].upper()
        display_state = DisplayState[display_text]
        events.append(DisplayEvent(ts, display_state))
    return events


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


@contextmanager
def pmset_log() -> _coll_types.Generator[_coll_types.Iterator[str], None, None]:
    with pmset_log_proc() as p:
        yield p.stdout


_PMSET_PS_ARGS = ("pmset", "-g", "ps")
_PMSET_PS_PATT = _re.compile(
    r"Now drawing from '(?P<source>[^']+)'.*?(?P<charge>\d+)%",
    _re.DOTALL | _re.MULTILINE | _re.IGNORECASE,
)


def pmset_ps() -> ChargeEvent:
    text = _subprocess.check_output(_PMSET_PS_ARGS, encoding="UTF-8")
    match = _PMSET_PS_PATT.search(text)
    if not match:
        raise Exception("Could not determine battery status")

    charge_type = (
        ChargeType.BATT if match["source"] == "Battery Power" else ChargeType.AC
    )
    charge = int(match["charge"])
    return ChargeEvent(datetime.now().astimezone(), charge_type, charge)


@dataclass
class UsageSession:
    session_type: ChargeType
    session_start: datetime
    session_end: datetime
    display_usage_secs: tuple[float]
    display_usage_charges: tuple[float]


class UsageAggregator(object):
    """Stores an aggregate for a battery session--a period of time off of AC"""

    __session_start: datetime | None
    __session_usage_secs: list[float]
    __session_usage_charges: list[float]
    __pending_usage_secs: list[float]
    __prev_charge_event: ChargeEvent
    __prev_display_event: DisplayEvent
    __stats: list[UsageSession]

    def __init__(self, charge_event: ChargeEvent, display_event: DisplayEvent):
        """Constructs the aggregator with the seed events.

        The expectation is that the `charge_event` is the first AC event and the `display_event` is the first
        known event.
        """
        self.__new_session(None)
        self.__prev_charge_event = charge_event
        self.__prev_display_event = display_event
        self.__stats = []

    def __new_session(self, session_start: datetime | None):
        self.__session_start = session_start
        self.__session_usage_secs = [0.0, 0.0]
        self.__pending_usage_secs = [0.0, 0.0]
        self.__session_usage_charges = [0.0, 0.0]

    def __make_stat(self, session_end: datetime) -> UsageSession:
        return UsageSession(
            session_type=self.charge_type,
            session_start=self.__session_start,
            session_end=session_end,
            display_usage_secs=tuple(self.__session_usage_secs),
            display_usage_charges=tuple(self.__session_usage_charges),
        )

    @property
    def stats(self) -> list[UsageSession]:
        return self.__stats

    @property
    def charge_type(self) -> ChargeType:
        return self.__prev_charge_event.type

    @property
    def charge(self) -> int:
        return self.__prev_charge_event.charge

    @property
    def display_state(self) -> DisplayState:
        return self.__prev_display_event.state

    @property
    def prev_ts(self) -> datetime:
        c_ts = self.__prev_charge_event.ts
        d_ts = self.__prev_display_event.ts
        return c_ts if c_ts > d_ts else d_ts

    def add_event(self, event: _EVENT_TYPE) -> UsageSession | None:
        if isinstance(event, ChargeEvent):
            return self.__add_charge_event(event)
        if isinstance(event, DisplayEvent):
            return self.__add_display_event(event)
        raise TypeError(f"Could not add event for: {type(event)}")

    def __add_charge_event(self, event: ChargeEvent) -> UsageSession | None:
        result = None
        prev_charge_ts = self.__prev_charge_event.ts
        curr_ts = event.ts
        prev_charge_type = self.charge_type
        prev_charge = self.charge
        curr_charge = event.charge
        # flush the pending times with the current amount of charge
        # if there are screen on/off events and no charge events in the interval, we just average out the usage
        window_charge = curr_charge - prev_charge
        window_time = (curr_ts - prev_charge_ts).total_seconds()
        pending_time = (curr_ts - self.prev_ts).total_seconds()
        # add in pending time with display
        self.__pending_usage_secs[self.display_state.value] += pending_time
        assert sum(self.__pending_usage_secs) == window_time
        pending_charges = list(
            window_charge * (usage_secs / pending_time)
            for usage_secs in self.__pending_usage_secs
        )
        self.__session_usage_secs = list(
            x + y for x, y in zip(self.__session_usage_secs, self.__pending_usage_secs)
        )
        self.__session_usage_charges = list(
            x + y for x, y in zip(self.__session_usage_charges, pending_charges)
        )

        # flush a session on transition from one type to another
        if prev_charge_type != event.type:
            result = self.__make_stat(curr_ts)
            self.__new_session(curr_ts)

        self.__prev_charge_event = event
        return result

    def __add_display_event(self, event: DisplayEvent) -> None:
        # only record on battery
        if self.charge_type == ChargeType.BATT:
            # record the previous usage up until now
            secs = (event.ts - self.prev_ts).total_seconds()
            self.__pending_usage_secs[self.display_state.value] += secs
        self.__prev_display_event = event


def calculate_usage(
    events: _coll_types.Sequence[_EVENT_TYPE],
) -> _coll_types.Sequence[UsageSession]:
    raise NotImplementedError("Implement me!")


def main():
    if _sys.platform != _TARGET_PLATFORM:
        print(f"Expected macOS (darwin), found {_sys.platform}", file=_sys.stderr)
        _sys.exit(1)
    with pmset_log() as log:
        events = parse_log(log)
    for event in events:
        print(f"Event:   {event}")
    print(f"Current: {pmset_ps()}")


if __name__ == "__main__":
    main()
