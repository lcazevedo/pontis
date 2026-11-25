#!/usr/bin/env bash
# Build Pontis x86_64 AppImage using PyInstaller (onedir) and appimagetool.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "$ROOT_DIR"

if [[ -n "${PONTIS_PYTHON:-}" ]]; then
    PYTHON_BIN="$PONTIS_PYTHON"
elif [[ -x "${HOME}/miniconda3/envs/pontis-dev/bin/python" ]]; then
    PYTHON_BIN="${HOME}/miniconda3/envs/pontis-dev/bin/python"
else
    PYTHON_BIN="$(command -v python3)"
fi

echo "==> Using Python: $PYTHON_BIN"
VERSION="$("$PYTHON_BIN" -c 'import pontis; print(pontis.__version__)')"
ARCH="${ARCH:-x86_64}"
APP_ID="io.github.lcazevedo.Pontis"
APPDIR="${ROOT_DIR}/build/AppDir"
TOOLS_DIR="${ROOT_DIR}/build/tools"
OUTPUT_APPIMAGE="${ROOT_DIR}/dist/Pontis-${VERSION}-${ARCH}.AppImage"

if [[ ! -f "${SCRIPT_DIR}/${APP_ID}.png" ]]; then
    echo "==> Rendering PNG icon..."
    QT_QPA_PLATFORM=offscreen "$PYTHON_BIN" "${SCRIPT_DIR}/render_icon.py"
fi

echo "==> Running PyInstaller..."
rm -rf "${ROOT_DIR}/build/pyinstaller" "${ROOT_DIR}/dist/pontis" "$APPDIR"
"$PYTHON_BIN" -m PyInstaller --noconfirm --clean "${ROOT_DIR}/packaging/pyinstaller.spec"

echo "==> Assembling AppDir..."
mkdir -p \
    "${APPDIR}/usr/lib/pontis" \
    "${APPDIR}/usr/bin" \
    "${APPDIR}/usr/share/applications" \
    "${APPDIR}/usr/share/icons/hicolor/256x256/apps" \
    "${APPDIR}/usr/share/icons/hicolor/scalable/apps" \
    "${APPDIR}/usr/share/metainfo"

cp -a "${ROOT_DIR}/dist/pontis/." "${APPDIR}/usr/lib/pontis/"
ln -s "../lib/pontis/pontis" "${APPDIR}/usr/bin/pontis"

install -m 0755 "${SCRIPT_DIR}/AppRun" "${APPDIR}/AppRun"
install -m 0644 "${SCRIPT_DIR}/${APP_ID}.desktop" "${APPDIR}/${APP_ID}.desktop"
install -m 0644 "${SCRIPT_DIR}/${APP_ID}.desktop" "${APPDIR}/usr/share/applications/${APP_ID}.desktop"
install -m 0644 "${SCRIPT_DIR}/${APP_ID}.png" "${APPDIR}/${APP_ID}.png"
install -m 0644 "${SCRIPT_DIR}/${APP_ID}.png" "${APPDIR}/.DirIcon"
install -m 0644 "${SCRIPT_DIR}/${APP_ID}.png" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/${APP_ID}.png"
install -m 0644 "${SCRIPT_DIR}/${APP_ID}.svg" "${APPDIR}/usr/share/icons/hicolor/scalable/apps/${APP_ID}.svg"
install -m 0644 "${SCRIPT_DIR}/${APP_ID}.metainfo.xml" "${APPDIR}/usr/share/metainfo/${APP_ID}.metainfo.xml"

if command -v appimagetool >/dev/null 2>&1; then
    APPIMAGETOOL="$(command -v appimagetool)"
else
    mkdir -p "$TOOLS_DIR"
    APPIMAGETOOL="${TOOLS_DIR}/appimagetool-${ARCH}.AppImage"
    if [[ ! -x "$APPIMAGETOOL" ]]; then
        echo "==> Downloading appimagetool for ${ARCH}..."
        curl -fsSL -o "$APPIMAGETOOL" \
            "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"
        chmod +x "$APPIMAGETOOL"
    fi
fi

echo "==> Building AppImage: ${OUTPUT_APPIMAGE}"
mkdir -p "${ROOT_DIR}/dist"
ARCH="$ARCH" APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" "$APPDIR" "$OUTPUT_APPIMAGE"
chmod +x "$OUTPUT_APPIMAGE"

(
    cd "${ROOT_DIR}/dist"
    sha256sum "$(basename "$OUTPUT_APPIMAGE")" > "$(basename "$OUTPUT_APPIMAGE").sha256"
)

echo "==> AppImage built successfully:"
ls -lh "$OUTPUT_APPIMAGE" "${OUTPUT_APPIMAGE}.sha256"
