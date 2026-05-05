#!/usr/bin/env bash
set -euo pipefail
VERSION="3.1.2"
BASE="$HOME/ramdisks"

mkdir -p "$BASE"

usage() {
    echo "Usage:"
    echo "  ramdisk.sh start <name> --size <size>"
    echo "  ramdisk.sh stop <name>"
    echo "  ramdisk.sh status <name>"
    echo ""
    echo "Size examples: 512M, 1G, 0.5G"
}

normalize_size() {
    local raw="$1"
    local cleaned value unit factor bytes

    cleaned="${raw//[[:space:]]/}"

    if [[ "$cleaned" =~ ^([0-9]+([.][0-9]+)?)([KkMmGgTt]?)([Bb]?)$ ]]; then
        value="${BASH_REMATCH[1]}"
        unit="${BASH_REMATCH[3]}"

        case "$unit" in
            "" ) factor=1048576 ;;
            [Kk]) factor=1024 ;;
            [Mm]) factor=1048576 ;;
            [Gg]) factor=1073741824 ;;
            [Tt]) factor=1099511627776 ;;
            *) return 1 ;;
        esac

        bytes="$(awk -v v="$value" -v f="$factor" 'BEGIN { printf "%.0f", v * f }')"

        if [[ "$bytes" -lt 1048576 ]]; then
            return 1
        fi

        echo "$bytes"
        return 0
    fi

    return 1
}

start() {
    NAME="$1"
    shift

    SIZE="1G"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --size)
                SIZE="$2"
                shift 2
                ;;
            *)
                shift
                ;;
        esac
    done

    MOUNT="$BASE/$NAME"

    SIZE_BYTES="$(normalize_size "$SIZE")" || {
        echo "[ERROR] Invalid size '$SIZE'. Use values like 512M, 1G, or 0.5G (minimum 1M)."
        exit 1
    }

    mkdir -p "$MOUNT"

    echo "[INFO] Mounting $NAME ($SIZE) at $MOUNT"

    if mountpoint -q "$MOUNT"; then
        echo "[WARN] Already mounted"
        exit 0
    fi

    sudo mount -t tmpfs -o size="$SIZE_BYTES" tmpfs "$MOUNT"

    if mountpoint -q "$MOUNT"; then
        echo "[OK] Mounted"
    else
        echo "[ERROR] Mount failed"
        exit 1
    fi
}

#stop() {
#    NAME="$1"
#    MOUNT="$BASE/$NAME"

#    if mountpoint -q "$MOUNT"; then
#        sudo umount "$MOUNT"
#        echo "[OK] Unmounted $NAME"
#    else
#        echo "[INFO] Not mounted"
#    fi
#}
stop() {
    NAME="$1"
    MOUNT="$HOME/ramdisks/$NAME"

    if mountpoint -q "$MOUNT"; then
        sudo umount "$MOUNT"

        if mountpoint -q "$MOUNT"; then
            echo "[ERROR] Unmount failed"
            exit 1
        fi

        echo "[OK] Unmounted $NAME"

        # 🔥 ADD THIS: cleanup folder
        rmdir "$MOUNT" 2>/dev/null || true
    else
        echo "[INFO] Not mounted"
    fi
}

status() {
    NAME="$1"
    MOUNT="$BASE/$NAME"

    if mountpoint -q "$MOUNT"; then
        echo "$NAME: mounted"
        df -h "$MOUNT"
    else
        echo "$NAME: not mounted"
    fi
}

case "$1" in
    start) shift; start "$@" ;;
    stop) shift; stop "$@" ;;
    status) shift; status "$@" ;;
    version)
        echo "ramdisk.sh version $VERSION"
        ;;
    *) usage ;;
esac
