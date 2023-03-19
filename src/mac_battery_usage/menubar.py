"""Menubar application for macOS battery usage"""
import rumps
import rumps as _rumps
import concurrent.futures as _futures

from datetime import datetime

from . import core as _core

# the amount of lines and menu item space the status text uses
_STAT_TEXT_LEN = 3
# the number of previous stats to display
_STAT_LEN = 5
# menu placeholder for stat lines that don't exist
_PLACEHOLDER_TEXT = " " * 70


def now_str() -> str:
    return _core.ts_to_str(datetime.now().astimezone())


def update_formatted_menu_item(menu_item: _rumps.MenuItem, text: str):
    """Updates the text of a menu item with formatted text."""
    # Adapted from https://github.com/jaredks/rumps/issues/30#issuecomment-70348881
    from AppKit import NSAttributedString
    from PyObjCTools.Conversion import propertyListFromPythonCollection
    from Cocoa import (
        NSFont,
        NSColor,
        NSFontAttributeName,
        NSForegroundColorAttributeName,
    )

    font = NSFont.fontWithName_size_("Monaco", 12.0)
    color = NSColor.blueColor()
    attributes = propertyListFromPythonCollection(
        {NSFontAttributeName: font, NSForegroundColorAttributeName: color},
        conversionHelper=lambda x: x,
    )

    string = NSAttributedString.alloc().initWithString_attributes_(text, attributes)
    menu_item._menuitem.setAttributedTitle_(string)


def formatted_menu_item(text) -> rumps.MenuItem:
    """Creates a menu item with formatted text."""
    menu_item = _rumps.MenuItem("")
    update_formatted_menu_item(menu_item, text)
    return menu_item


def fetch_stats() -> list[str]:
    stats = list(_core.battery_usage_stats())
    if len(stats) == 0:
        raise Exception("No battery usage sessions")
    # display from newest to oldest
    stats = list(reversed(stats[-_STAT_LEN:]))
    lines = []
    for i, stat in enumerate(stats):
        stat_lines = stat.pretty_str().split("\n")
        if len(stat_lines) != _STAT_TEXT_LEN:
            raise Exception(f"Malformed battery stats line length: {len(stat_lines)}")
        lines.extend(stat_lines)
    for i in range((_STAT_LEN - len(stats)) * _STAT_TEXT_LEN):
        lines.append(_PLACEHOLDER_TEXT)
    assert len(lines) == _STAT_LEN * _STAT_TEXT_LEN
    return lines


class UsageApp(_rumps.App):
    def __init__(self):
        super(UsageApp, self).__init__(name="📉")

        # setup placeholder menu items
        self.__stat_menu_items = []
        for x in range(_STAT_LEN):
            for y in range(_STAT_TEXT_LEN):
                self.__stat_menu_items.append(formatted_menu_item(_PLACEHOLDER_TEXT))
        self.__status_menu_item = _rumps.MenuItem("Loading...")
        self.menu.add(self.__status_menu_item)
        for i in range(0, len(self.__stat_menu_items), _STAT_TEXT_LEN):
            for j in range(_STAT_TEXT_LEN):
                self.menu.add(self.__stat_menu_items[i + j])
            self.menu.add(_rumps.separator)

        # setup threadpool to get the update
        self.__pool = _futures.ThreadPoolExecutor(max_workers=1)
        self.__run_update()

        # set up UI update
        self.__update_ui_timer = _rumps.Timer(self.__update_ui, 5)
        self.__update_ui_timer.start()

        # set up refresh
        self.__refresh_timer = _rumps.Timer(self.__refresh, 120)
        self.__refresh_timer.start()

    def __run_update(self):
        """Spawns a task to fetch battery status unconditionally."""
        self.__pending = self.__pool.submit(fetch_stats)

    def __update_ui(self, _: _rumps.Timer):
        if self.__pending is None or not self.__pending.done():
            return
        try:
            lines = self.__pending.result()
            for line, menu_item in zip(lines, self.__stat_menu_items):
                update_formatted_menu_item(menu_item, line)
            self.__status_menu_item.title = f"Updated: {now_str()}"
        except Exception as e:
            self.__status_menu_item.title = f"Error: {now_str()} - {str(e)}"
        # reset for refresh
        self.__pending = None

    def __refresh(self, _: _rumps.Timer):
        if self.__pending is not None:
            return
        self.__run_update()


def main():
    UsageApp().run()


if __name__ == "__main__":
    main()
