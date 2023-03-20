from setuptools import setup

APP = ["BatteryUsage.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": True,
    "iconfile": "application.icns",
    "plist": {
        "LSUIElement": True,
    },
    "packages": ["rumps"],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
