# PyInstaller spec — builds a windowed Carrom app for macOS, Windows and Linux.
#   pyinstaller carrom.spec
import sys
from pathlib import Path

APP_NAME = "Carrom"
VERSION = "1.0.0"
ROOT = Path(SPECPATH)
ASSETS = ROOT / "assets"

if sys.platform == "darwin":
    icon = str(ASSETS / "icon.icns")
elif sys.platform == "win32":
    icon = str(ASSETS / "icon.ico")
else:
    icon = str(ASSETS / "icon.png")

a = Analysis(
    ["carrom.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ASSETS / "icon.png"), "assets")],
    hiddenimports=["physics", "theming"],
    excludes=["numpy", "pytest", "PIL", "matplotlib", "setuptools", "pip"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    console=False,          # GUI app: no terminal window
    icon=icon,
    upx=False,
    strip=False,
    disable_windowed_traceback=False,
    target_arch=None,       # set by CI for universal2 builds
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name=f"{APP_NAME}.app",
        icon=icon,
        bundle_identifier="com.jayacpc9.carrom",
        version=VERSION,
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            # Let macOS hand the app light/dark appearance changes.
            "NSRequiresAquaSystemAppearance": False,
            "LSMinimumSystemVersion": "11.0",
            "LSApplicationCategoryType": "public.app-category.board-games",
        },
    )
