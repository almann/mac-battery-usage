import sys as _sys

from . import core as _core

_TARGET_PLATFORM = "darwin"


def main():
    if _sys.platform != _TARGET_PLATFORM:
        print(f"Expected macOS (darwin), found {_sys.platform}", file=_sys.stderr)
        _sys.exit(1)
    with _core.pmset_log() as log:
        events = _core.parse_log(log)
    # add in current charge state
    events.append(_core.pmset_ps())
    stats = _core.calculate_usage(events)
    for stat in stats:
        # Only print out stats that have some reasonable amount of time and used battery
        if sum(stat.display_usage_secs) > 300 and sum(stat.display_usage_charges) > 1.0:
            print(f"{stat.pretty_str()}")


main()
