import pytest
import collections.abc as _coll_abc

from mac_battery_usage.core import *

from dataclasses import dataclass


@dataclass
class EventCase:
    desc: str
    log_lines: _coll_abc.Sequence[str]
    events: _coll_abc.Sequence[ChargeEvent | DisplayEvent]

    def __str__(self) -> str:
        return self.desc


_SINGLE_AC_CASE = EventCase(
    desc="single AC event",
    log_lines=(
        "2023-03-13 20:02:28 -0700 Assertions           Summary- [System: PrevIdle] Using AC(Charge: 36)",
    ),
    events=(ChargeEvent(parse_ts("2023-03-13 20:02:28 -0700"), ChargeType.AC, 36),),
)
_SINGLE_BATT_1_CASE = EventCase(
    desc="single BATT event (1)",
    log_lines=(
        "2023-03-13 20:02:28 -0700 Assertions           Summary- [System: PrevIdle] Using Batt(Charge: 36)",
    ),
    events=(ChargeEvent(parse_ts("2023-03-13 20:02:28 -0700"), ChargeType.BATT, 36),),
)
_SINGLE_BATT_2_CASE = EventCase(
    desc="single BATT event (2)",
    log_lines=(
        "2023-03-13 20:02:28 -0700 Assertions           Summary- [System: PrevIdle] Using BATT(Charge: 36)",
    ),
    events=(ChargeEvent(parse_ts("2023-03-13 20:02:28 -0700"), ChargeType.BATT, 36),),
)
_SAMPLE_CASE = EventCase(
    desc="mixed sample",
    log_lines=(
        "2023-03-13 14:43:29 -0700 Assertions          Summary- Using AC(Charge: 100)",
        "2023-03-13 15:06:22 -0700 Notification        Display is turned off",
        "2023-03-13 15:06:22 -0700 Notification        Display is turned on",
        "2023-03-13 15:38:02 -0700 Assertions          Summary- [System: PrevIdle] Using AC(Charge: 100)",
        "2023-03-13 15:38:12 -0700 Notification        Display is turned off",
        "2023-03-13 15:55:02 -0700 Notification        Display is turned on",
        "2023-03-13 16:28:05 -0700 Notification        Display is turned off",
        "2023-03-13 16:47:35 -0700 Notification        Display is turned on",
        "2023-03-13 17:01:26 -0700 Assertions          Summary- [System: PrevIdle] Using Batt(Charge: 100)",
        "2023-03-13 19:18:29 -0700 Notification        Display is turned off",
        "2023-03-13 19:18:34 -0700 Assertions          Summary- [System: PrevIdle] Using Batt(Charge: 36)",
    ),
    events=(
        ChargeEvent(parse_ts("2023-03-13 14:43:29 -0700"), ChargeType.AC, 100),
        DisplayEvent(parse_ts("2023-03-13 15:06:22 -0700"), DisplayState.OFF),
        DisplayEvent(parse_ts("2023-03-13 15:06:22 -0700"), DisplayState.ON),
        ChargeEvent(parse_ts("2023-03-13 15:38:02 -0700"), ChargeType.AC, 100),
        DisplayEvent(parse_ts("2023-03-13 15:38:12 -0700"), DisplayState.OFF),
        DisplayEvent(parse_ts("2023-03-13 15:55:02 -0700"), DisplayState.ON),
        DisplayEvent(parse_ts("2023-03-13 16:28:05 -0700"), DisplayState.OFF),
        DisplayEvent(parse_ts("2023-03-13 16:47:35 -0700"), DisplayState.ON),
        ChargeEvent(parse_ts("2023-03-13 17:01:26 -0700"), ChargeType.BATT, 100),
        DisplayEvent(parse_ts("2023-03-13 19:18:29 -0700"), DisplayState.OFF),
        ChargeEvent(parse_ts("2023-03-13 19:18:34 -0700"), ChargeType.BATT, 36),
    ),
)


@pytest.mark.parametrize(
    "case",
    (_SINGLE_AC_CASE, _SINGLE_BATT_1_CASE, _SINGLE_BATT_2_CASE, _SAMPLE_CASE),
    ids=EventCase.__str__,
)
def test_event_parsing(case: EventCase):
    assert case.events == tuple(parse_log(case.log_lines))
