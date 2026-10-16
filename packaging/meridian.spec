# PyInstaller spec for Meridian. Build from the project root:  pyinstaller packaging/meridian.spec --noconfirm
# Produces dist/Meridian/ (a folder; zip it to share). One-folder builds start faster and trip antivirus less than one-file.
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH).parent

a = Analysis(
    [str(root / "run_meridian.py")],
    pathex=[str(root)],
    datas=[(str(root / "meridian" / "ui"), "meridian/ui")],  # HTML, CSS, JS and the bundled fonts
    # keyring finds its OS backend through entry points, which PyInstaller cannot see
    hiddenimports=collect_submodules("keyring.backends") + ["win32ctypes.core"],
    excludes=["tkinter", "matplotlib", "numpy", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Meridian",
    console=False,  # no terminal window; logs go to ~/.meridian/meridian.log
)
coll = COLLECT(exe, a.binaries, a.datas, name="Meridian")
