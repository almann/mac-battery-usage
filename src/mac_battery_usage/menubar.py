"""Menubar application for macOS battery usage"""

import rumps as _rumps

from . import core as _core


class UsageApp(_rumps.App):
    def __init__(self):
        super(UsageApp, self).__init__(name="⚡")
        self.refresh()
        self.__timer = _rumps.Timer(self.refresh, 300)

    def refresh(self):
        try:
            stats = list(_core.battery_usage_stats())
            if len(stats) == 0:
                raise Exception("No battery usage sessions")
            items = []
            for stat in stats[-5:]:
                items.extend(stat.pretty_str().split("\n"))
                items.append(None)
            self.menu = items
        except Exception as e:
            self.menu = [str(e)]


def main():
    UsageApp().run()


if __name__ == "__main__":
    main()
