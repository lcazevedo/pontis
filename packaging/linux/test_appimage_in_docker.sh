#!/usr/bin/env bash
# Verify the built AppImage in a clean Ubuntu 24.04 Docker container without Python.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
APPIMAGE_PATH="${1:-}"

if [[ -z "$APPIMAGE_PATH" ]]; then
    APPIMAGE_PATH="$(ls -1 "${ROOT_DIR}"/dist/Pontis-*-x86_64.AppImage 2>/dev/null | head -n 1 || true)"
fi

if [[ -z "$APPIMAGE_PATH" || ! -f "$APPIMAGE_PATH" ]]; then
    echo "Error: AppImage not found in dist/. Run packaging/linux/build_appimage.sh first." >&2
    exit 1
fi

IMAGE_TAG="pontis-appimage-test:ubuntu2404"

echo "==> Building clean test container (no Python): ${IMAGE_TAG}"
docker build -t "$IMAGE_TAG" -f "${SCRIPT_DIR}/Dockerfile.test" "$SCRIPT_DIR"

echo "==> Running AppImage verification inside container: ${APPIMAGE_PATH}"
docker run --rm \
    -v "${APPIMAGE_PATH}:/opt/Pontis.AppImage:ro" \
    "$IMAGE_TAG" \
    bash -ceu '
        echo "1) Confirm no Python is installed in container..."
        ! command -v python3
        ! command -v python

        echo "2) Confirm external rclone is available..."
        rclone version | head -n 2

        echo "3) Run Pontis CLI --help..."
        APPIMAGE_EXTRACT_AND_RUN=1 /opt/Pontis.AppImage --help >/tmp/help.txt
        grep -q "Pontis" /tmp/help.txt

        echo "4) Run real local <-> local sync via AppImage CLI..."
        mkdir -p /tmp/dir_a /tmp/dir_b
        echo "hello from clean container" > /tmp/dir_a/hello.txt
        APPIMAGE_EXTRACT_AND_RUN=1 /opt/Pontis.AppImage --db /tmp/test.db profile add clean_test --a /tmp/dir_a --b /tmp/dir_b
        APPIMAGE_EXTRACT_AND_RUN=1 /opt/Pontis.AppImage --db /tmp/test.db profile list | grep -q "clean_test"
        APPIMAGE_EXTRACT_AND_RUN=1 /opt/Pontis.AppImage --db /tmp/test.db run clean_test --dry-run
        APPIMAGE_EXTRACT_AND_RUN=1 /opt/Pontis.AppImage --db /tmp/test.db run clean_test
        grep -q "hello from clean container" /tmp/dir_b/hello.txt

        echo "5) Confirm default language falls back to English in C/unset locale..."
        OUT_EN="$(LANG=C APPIMAGE_EXTRACT_AND_RUN=1 /opt/Pontis.AppImage --db /tmp/test.db profile list)"
        echo "$OUT_EN"
        APPIMAGE_EXTRACT_AND_RUN=1 /opt/Pontis.AppImage --db /tmp/empty.db profile list | grep -q "No profiles yet"

        echo "6) Verify PySide6 GUI startup under QT_QPA_PLATFORM=offscreen..."
        set +e
        QT_QPA_PLATFORM=offscreen HOME=/tmp/fakehome APPIMAGE_EXTRACT_AND_RUN=1 \
            timeout 4s /opt/Pontis.AppImage >/tmp/gui_out.txt 2>/tmp/gui_err.txt
        RC=$?
        set -e
        cat /tmp/gui_err.txt
        if [[ "$RC" -ne 124 && "$RC" -ne 0 ]]; then
            echo "GUI exited unexpectedly with code $RC" >&2
            exit 1
        fi
        if grep -Eqi "Traceback|ImportError|ModuleNotFoundError|error while loading shared libraries|Could not load the Qt platform plugin" /tmp/gui_err.txt; then
            echo "Detected fatal error in GUI startup!" >&2
            exit 1
        fi

        echo "==> All clean-container AppImage checks passed!"
    '
