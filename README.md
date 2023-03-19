# Battery Usage for macOS

This is a simple utility that is based on [this question][stack] on Stack Overflow and the associated [script][script]
in Github by [DudNr33](https://github.com/DudeNr33).  I started by fixing up the script, but wanted to change a lot
of the mechanics of the script to make it a bit easier to test and embed in other contexts (such as a menu bar app).

[stack]: https://apple.stackexchange.com/questions/423962/get-total-screen-on-usage-since-last-full-charge
[script]: https://github.com/DudeNr33/screen-on-time

## Usage

The script has a pretty straightforward invocation and should not require anything beyond the standard library to run:

```shell
$ python3 ./src/mac-battery-usage.py
```

## Development

Using virtual environments is recommended along with installing Python via `pyenv`, however the built-in Python
interpreter _should_ be sufficient:

```shell
$ (python3 -m venv ./venv && \
    source ./venv/bin/activate && \
    pip3 --require-virtualenv install -U pip setuptools wheel build black pytest && \
    pip3 --require-virtualenv install -e .)
```

Within the virtual ennvironments, the script can be run as a module:

```shell
$ python3 -m mac_battery_usage
```

Cleaning up the editable install can be done via:

```shell
$ (source ./venv/bin/activate && \
    pip3 --require-virtual-env uninstall mac-battery-usage && \
    git clean -d -X -f src)
```