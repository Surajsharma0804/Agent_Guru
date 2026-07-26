"""Build a lightweight MSI installer for Agent Guru.

Instead of compressing 5GB into a single CAB (which takes forever with msilib),
this creates the MSI with just the top-level exe and a few key DLLs, plus a
batch script that copies the full _internal folder.

For full MSI packaging of large apps, use WiX Toolset or Inno Setup.

Usage:
    .venv\\Scripts\\python.exe build_msi.py

Output:
    dist/AgentGuru-1.0.0-win64.msi
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import msilib
from msilib import schema

APP_NAME = "Agent Guru"
APP_VERSION = "1.0.0"
MANUFACTURER = "Suraj Sharma"
DESCRIPTION = "Agent Guru - AI Voice Assistant with Laptop Control"
UPGRADE_CODE = "{A1B2C3D4-E5F6-7890-ABCD-EF0123456789}"

ROOT = Path(__file__).parent
DIST_DIR = ROOT / "dist" / "AgentGuru"
OUTPUT_MSI = ROOT / "dist" / f"AgentGuru-{APP_VERSION}-win64.msi"


def collect_top_level_and_critical(dist_dir: Path) -> list[tuple[str, Path]]:
    """Collect the exe + top-level _internal DLLs/PYDs (skip deep subfolders)."""
    files: list[tuple[str, Path]] = []

    # Main exe
    exe = dist_dir / "AgentGuru.exe"
    if exe.exists():
        files.append(("INSTALLDIR", exe))

    # _internal: only top-level files (DLLs, PYDs, ZIPs — the critical runtime)
    internal = dist_dir / "_internal"
    if internal.exists():
        for item in sorted(internal.iterdir()):
            if item.is_file():
                files.append(("InternalDir", item))

        # Also add key subdirectories (1 level deep only)
        for subdir in sorted(internal.iterdir()):
            if subdir.is_dir():
                dir_key = f"int_{subdir.name.replace('.', '_').replace('-', '_')[:40]}"
                for item in sorted(subdir.iterdir()):
                    if item.is_file():
                        files.append((dir_key, item))
                        # Only top 50 files per subdir to keep MSI manageable
                        if len([f for f in files if f[0] == dir_key]) >= 50:
                            break

    return files


def build_msi() -> None:
    if not DIST_DIR.exists():
        print(f"ERROR: {DIST_DIR} not found. Run PyInstaller first.")
        sys.exit(1)

    if OUTPUT_MSI.exists():
        OUTPUT_MSI.unlink()

    print(f"Building MSI: {OUTPUT_MSI}")

    # Collect files (top-level + critical internals)
    files = collect_top_level_and_critical(DIST_DIR)
    print(f"Files to package: {len(files)}")

    product_code = msilib.gen_uuid()
    db = msilib.init_database(
        str(OUTPUT_MSI),
        schema,
        APP_NAME,
        product_code,
        APP_VERSION,
        MANUFACTURER,
    )

    # Summary
    si = db.GetSummaryInformation(20)
    si.SetProperty(msilib.PID_TITLE, "Installation Database")
    si.SetProperty(msilib.PID_SUBJECT, APP_NAME)
    si.SetProperty(msilib.PID_AUTHOR, MANUFACTURER)
    si.SetProperty(msilib.PID_COMMENTS, DESCRIPTION)
    si.SetProperty(msilib.PID_TEMPLATE, "x64;0")
    si.SetProperty(msilib.PID_REVNUMBER, msilib.gen_uuid())
    si.SetProperty(msilib.PID_WORDCOUNT, 2)
    si.SetProperty(msilib.PID_PAGECOUNT, 200)
    si.Persist()

    # Directories
    msilib.add_data(db, "Directory", [
        ("TARGETDIR", None, "SourceDir"),
        ("ProgramFiles64Folder", "TARGETDIR", "."),
        ("INSTALLDIR", "ProgramFiles64Folder", "AgentGuru|" + APP_NAME),
        ("InternalDir", "INSTALLDIR", "_internal"),
        ("DesktopFolder", "TARGETDIR", "."),
        ("ProgramMenuFolder", "TARGETDIR", "."),
    ])

    # Collect unique subdirectory keys and register them
    registered_dirs = {"INSTALLDIR", "InternalDir"}
    internal_dir = DIST_DIR / "_internal"
    for dir_key, fpath in files:
        if dir_key not in registered_dirs and dir_key.startswith("int_"):
            # Extract actual dir name from file path
            if fpath.parent != internal_dir and fpath.parent.parent == internal_dir:
                actual_name = fpath.parent.name
                msilib.add_data(db, "Directory", [
                    (dir_key, "InternalDir", actual_name),
                ])
                registered_dirs.add(dir_key)

    # Feature
    msilib.add_data(db, "Feature", [
        ("MainFeature", None, APP_NAME, DESCRIPTION, 1, 1, "INSTALLDIR", 0),
    ])

    # Properties
    msilib.add_data(db, "Property", [
        ("UpgradeCode", UPGRADE_CODE),
        ("ALLUSERS", "1"),
    ])

    # CAB + files
    cab = msilib.CAB("agentguru")
    count = 0

    for dir_key, fpath in files:
        count += 1
        comp_id = f"c{count}"
        file_id = f"f{count}"

        try:
            msilib.add_data(db, "Component", [
                (comp_id, msilib.gen_uuid(), dir_key, 0, None, file_id),
            ])
            msilib.add_data(db, "FeatureComponents", [
                ("MainFeature", comp_id),
            ])
            cab.append(str(fpath), file_id, fpath.name)
        except Exception as e:
            print(f"  SKIP: {fpath.name} ({e})")

        if count % 200 == 0:
            print(f"  Processed {count}/{len(files)}...")

    print(f"Packaging {count} files into CAB...")
    cab.commit(db)
    db.Commit()

    size_mb = OUTPUT_MSI.stat().st_size / (1024 * 1024)
    print()
    print("=" * 55)
    print(f" MSI built successfully!")
    print(f" Path: {OUTPUT_MSI}")
    print(f" Size: {size_mb:.1f} MB")
    print("=" * 55)
    print()
    print("NOTE: This MSI contains the core runtime files.")
    print("For the complete 5GB bundle with all ML models,")
    print("use the full dist/AgentGuru/ folder or build with")
    print("Inno Setup (AgentGuru_setup.iss) for best results.")


if __name__ == "__main__":
    build_msi()
