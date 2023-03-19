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
from datetime import datetime, timedelta
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
) -> list[_EVENT_TYPE]:
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


_SECONDS_IN_HOUR = 3600
_SECONDS_IN_MINUTE = 60


def format_secs(total_secs: float) -> str:
    td = timedelta(seconds=total_secs)
    hours, min_secs = divmod(td.seconds, _SECONDS_IN_HOUR)
    minutes = min_secs // _SECONDS_IN_MINUTE
    return f"{td.days:>3}d {hours:02}h {minutes:02}m"


@dataclass
class UsageSession:
    """A session of battery or charging.

    Note that `display_usage_charges` is a tuple of amount of charge used (so negative for charging).
    `display_usage_charges[DisplayType.ON.value]` is the amount of battery used while the screen is on.
    `display_usage_secs[DisplayType.ON.value]` is the amount of time used when the screen is on.
    """

    session_type: ChargeType
    session_start: datetime
    session_end: datetime
    display_usage_secs: tuple[float]
    display_usage_charges: tuple[float]

    @property
    def display_desc(self) -> tuple[str]:
        return tuple(
            f"Screen {DisplayState(i).name} {usage_charge:2.0f}% used in {format_secs(secs)}"
            for i, (usage_charge, secs) in enumerate(
                zip(self.display_usage_charges, self.display_usage_secs)
            )
        )

    def __str__(self):
        return (
            f"{self.session_type.name:>4} "
            + f"{ts_to_str(self.session_start)} - {ts_to_str(self.session_end)}: "
            + f"{', '.join(self.display_desc)}"
        )


class UsageAggregator(object):
    """Stores an aggregate for a battery session--a period of time off of AC"""

    __session_start: datetime | None
    __session_usage_secs: list[float]
    __session_charge_usages: list[float]
    __pending_usage_secs: list[float]
    __prev_charge_event: ChargeEvent
    __prev_display_event: DisplayEvent

    def __init__(self, charge_event: ChargeEvent, display_event: DisplayEvent):
        """Constructs the aggregator with the seed events.

        The expectation is that the `charge_event` is the first AC event and the `display_event` is the first
        known event.
        """
        self.__new_session(charge_event.ts)
        self.__prev_charge_event = charge_event
        self.__prev_display_event = display_event

    def __new_session(self, session_start: datetime | None):
        self.__session_start = session_start
        self.__session_usage_secs = [0.0, 0.0]
        self.__pending_usage_secs = [0.0, 0.0]
        self.__session_charge_usages = [0.0, 0.0]

    def make_stat(self, session_end: datetime | None = None) -> UsageSession:
        """Constructs a session stat, if `session_end` is None, the previous charge event is used."""
        if session_end is None:
            session_end = self.__prev_charge_event.ts
        return UsageSession(
            session_type=self.charge_type,
            session_start=self.__session_start,
            session_end=session_end,
            display_usage_secs=tuple(self.__session_usage_secs),
            display_usage_charges=tuple(self.__session_charge_usages),
        )

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

    @property
    def total_pending_time(self):
        return sum(self.__pending_usage_secs)

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
        window_charge_usage = -(curr_charge - prev_charge)
        window_time = (curr_ts - prev_charge_ts).total_seconds()
        pending_time = (curr_ts - self.prev_ts).total_seconds()
        # add in pending time with display
        self.__pending_usage_secs[self.display_state.value] += pending_time
        session_time = (curr_ts - self.__session_start).total_seconds()
        assert (
            self.total_pending_time == window_time
        ), f"p_time({self.total_pending_time}) != w_time({session_time})"
        pending_charge_usages = list(
            0 if pending_time == 0 else window_charge_usage * (usage_secs / window_time)
            for usage_secs in self.__pending_usage_secs
        )
        self.__session_usage_secs = list(
            x + y for x, y in zip(self.__session_usage_secs, self.__pending_usage_secs)
        )
        self.__session_charge_usages = list(
            x + y for x, y in zip(self.__session_charge_usages, pending_charge_usages)
        )
        # reset pending
        self.__pending_usage_secs = [0.0, 0.0]

        # flush a session on transition from one type to another
        if prev_charge_type != event.type:
            result = self.make_stat(curr_ts)
            self.__new_session(curr_ts)

        self.__prev_charge_event = event
        return result

    def __add_display_event(self, event: DisplayEvent) -> None:
        # record the previous usage up until now
        secs = (event.ts - self.prev_ts).total_seconds()
        self.__pending_usage_secs[self.display_state.value] += secs
        self.__prev_display_event = event


def calculate_usage(
    events: _coll_types.Sequence[_EVENT_TYPE],
) -> _coll_types.Sequence[UsageSession]:
    """Aggregates an event log into usage stats per session.

    The last event in the log is assumed to be the known open "end" of the log, so in general it will be a charge event
    and will be used to flush the current stat for that active session.
    """
    # first we must find the first for charge events (so we know where the start is), and the "closest" display
    # state before that
    prev_charge_type = None
    start_charge_event = None
    start_display_event = None
    for i, event in enumerate(events):
        if isinstance(event, DisplayEvent):
            # just remember the closest display event before our potential charge event
            start_display_event = event
            continue
        if isinstance(event, ChargeEvent):
            if prev_charge_type is not None:
                # first charge event
                prev_charge_type = event.type
                continue
            if prev_charge_type != event.type:
                # we have a transition, so we know this is a start
                start_charge_event = event
                if start_display_event is not None and start_charge_event is not None:
                    break
                continue
    else:
        raise Exception("Could not find any start of AC/Battery session in log events")
    aggregator = UsageAggregator(start_charge_event, start_display_event)
    stats: list[UsageSession] = []
    for event in events[i:]:
        stat = aggregator.add_event(event)
        if stat is not None:
            stats.append(stat)
    # make sure the "partial session" at the end gets captured
    stats.append(aggregator.make_stat())
    return stats


def main():
    if _sys.platform != _TARGET_PLATFORM:
        print(f"Expected macOS (darwin), found {_sys.platform}", file=_sys.stderr)
        _sys.exit(1)
    with pmset_log() as log:
        events = parse_log(log)
    # add in current charge state
    events.append(pmset_ps())
    stats = calculate_usage(events)
    for stat in stats:
        # Only print out stats that have some reasonable amount of time and used battery
        if sum(stat.display_usage_secs) > 600 and sum(stat.display_usage_charges) > 1.0:
            print(f"Stat:  {stat}")


if __name__ == "__main__":
    main()
