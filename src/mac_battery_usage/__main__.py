import sys as _sys

from . import core as _core

_TARGET_PLATFORM = "darwin"


def main():
    if _sys.platform != _TARGET_PLATFORM:
        print(f"Expected macOS (darwin), found {_sys.platform}", file=_sys.stderr)
        _sys.exit(1)
    for stat in _core.battery_usage_stats():
        print(f"{stat.pretty_str()}")
        print()


main()
