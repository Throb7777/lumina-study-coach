import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

project_root = Path(SPECPATH).resolve().parent
backend_root = project_root / "backend"
console_build = os.environ.get("LUMINA_CONSOLE_BUILD") == "1"
version_file = os.environ.get("LUMINA_VERSION_FILE")
ocr_runtime = project_root / "installer" / "ocr-runtime"
required_ocr_files = (
    ocr_runtime / "tesseract.exe",
    ocr_runtime / "tessdata" / "eng.traineddata",
    ocr_runtime / "tessdata" / "chi_sim.traineddata",
    ocr_runtime / "tessdata" / "chi_sim_vert.traineddata",
)
missing_ocr_files = [str(path) for path in required_ocr_files if not path.is_file()]
if missing_ocr_files:
    raise SystemExit(
        "Bundled OCR runtime is incomplete. Run launcher/prepare-ocr-runtime.ps1 first. "
        f"Missing: {', '.join(missing_ocr_files)}"
    )

datas = [
    (str(project_root / "frontend" / "dist"), "frontend/dist"),
    (str(backend_root / "alembic.ini"), "."),
    (str(backend_root / "alembic" / "env.py"), "alembic"),
    (str(backend_root / "alembic" / "script.py.mako"), "alembic"),
    (str(ocr_runtime), "ocr"),
]
datas += [
    (str(migration), "alembic/versions")
    for migration in sorted((backend_root / "alembic" / "versions").glob("*.py"))
]
binaries = []
hiddenimports = collect_submodules("app")

for package in ("fastembed", "pypdfium2", "yt_dlp"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

for distribution in ("alembic", "fastembed", "pypdfium2", "yt-dlp"):
    datas += copy_metadata(distribution)

analysis = Analysis(
    [str(project_root / "launcher" / "release_entry.py")],
    pathex=[str(project_root), str(backend_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Lumina",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=console_build,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "launcher" / "assets" / "lumina.ico"),
    version=version_file,
)

bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Lumina",
)
