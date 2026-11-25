# Linux Packaging

This directory contains the build assets for packaging **Pontis** on Linux (`x86_64`).

> **Note for v1:** `rclone` (`>= 1.66.0`) is **not** bundled inside the package. Users install `rclone` on their system (`PATH` or custom path in Preferences).

---

## 1. Building the AppImage

### Prerequisites
- Python `3.12` (Conda environment `pontis-dev`) with packaging dependencies installed:
  ```bash
  conda activate pontis-dev
  pip install -e ".[dev,packaging]"
  ```
- `curl` (to download `appimagetool` automatically if not already in `PATH` or `build/tools/`).

### Build Command

```bash
./packaging/linux/build_appimage.sh
```

This script:
1. Ensures `packaging/linux/io.github.lcazevedo.Pontis.png` is rendered from the SVG icon.
2. Bundles Pontis + PySide6 using `packaging/pyinstaller.spec` (onedir mode).
3. Assembles `build/AppDir` with `AppRun`, `.desktop`, `hicolor` SVG/PNG icons, and AppStream `.metainfo.xml`.
4. Packages `dist/Pontis-<version>-x86_64.AppImage` and writes its `.sha256` checksum.

> **glibc compatibility note:** AppImages link against the build host's `glibc`. Building locally on Ubuntu 24.04 / Linux Mint 22.1 targets `glibc >= 2.39`; CI workflows (Part 13) should build on `ubuntu-22.04` for broader distribution compatibility.

---

## 2. Verifying in a Clean Container (No Python)

To prove the AppImage works on a machine without Python or any development packages installed, run the Docker verification script:

```bash
./packaging/linux/test_appimage_in_docker.sh
```

The script builds a minimal `ubuntu:24.04` container with **no Python interpreter** (only X11/Wayland/GL runtime libraries and external `rclone`), then mounts the AppImage read-only and verifies:
- `python` / `python3` are absent from the container;
- `rclone` is detected externally (`clean_subprocess_env` strips PyInstaller's `LD_LIBRARY_PATH`);
- CLI profile creation, `--dry-run`, and real `bisync` synchronization work end-to-end;
- Default language follows the system locale with English fallback;
- PySide6 GUI starts cleanly under `QT_QPA_PLATFORM=offscreen`.

---

## 3. Flatpak Manifest (Alternative)

A starter Flatpak manifest is provided at [flatpak/io.github.lcazevedo.Pontis.yml](flatpak/io.github.lcazevedo.Pontis.yml) (`app-id: io.github.lcazevedo.Pontis`, `org.kde.Platform//6.8`).

Before building offline with `flatpak-builder`, generate the Python wheel sources for pure/runtime dependencies (`platformdirs`, `keyring`, `watchdog`, and `PySide6` or a KDE PySide6 BaseApp) using `flatpak-pip-generator` and add `rclone` if targeting a fully sandboxed Flatpak bundle.
