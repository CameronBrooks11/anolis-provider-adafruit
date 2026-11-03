# PyInstaller spec: one self-contained executable, bin/anolis-provider-adafruit in
# the release tarball. Build with `just freeze`; the result is dist/anolis-provider-adafruit.
# -*- mode: python -*-

from importlib.metadata import distribution

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

# Blinka picks its platform module at run time from the board it detects, so a
# static import scan cannot see which one the target needs: take them all.
# Modules whose optional backends are absent (FTDI, Binho, MCP2221...) are skipped
# with a warning; the Linux I2C path this provider uses has no such dependency.
hiddenimports = collect_submodules("adafruit_blinka") + collect_submodules("adafruit_platformdetect")
blinka = distribution("adafruit-blinka")
datas = (
    # Blinka installs board_imports.json and microcontroller_imports.json at the
    # top of site-packages and opens them beside its board/digitalio modules;
    # without them, constructing a driver fails with FileNotFoundError.
    [(str(blinka.locate_file(f)), ".") for f in blinka.files or [] if "/" not in str(f) and f.name.endswith(".json")]
    + collect_data_files("adafruit_platformdetect")
    # importlib.metadata lookups: the provider and the SDK report their versions from these.
    + copy_metadata("anolis-provider-adafruit")
    + copy_metadata("anolis-provider-sdk")
)

a = Analysis(
    ["entry.py"],
    hiddenimports=hiddenimports,
    datas=datas,
    excludes=["tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="anolis-provider-adafruit",
    console=True,
    strip=False,
    upx=False,
)
