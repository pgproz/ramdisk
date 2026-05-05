#!/usr/bin/env bash
set -euo pipefail
VERSION="3.3"
BASE="$HOME/ramdisks"
META_DIR="$BASE/.meta"
SNAPSHOT_DIR="$BASE/.snapshots"

mkdir -p "$BASE"
mkdir -p "$META_DIR"
mkdir -p "$SNAPSHOT_DIR"

usage() {
    echo "Usage:"
    echo "  ramdisk.sh start <name> --size <size> [--persist|--no-persist]"
    echo "  ramdisk.sh mount <name>"
    echo "  ramdisk.sh stop <name>"
    echo "  ramdisk.sh delete <name>"
    echo "  ramdisk.sh status <name>"
    echo ""
    echo "Size examples: 512M, 1G, 0.5G"
}

load_persist_flag() {
    local name="$1"
    local meta_file="$META_DIR/$name.conf"

    if [[ -f "$meta_file" ]]; then
        # shellcheck disable=SC1090
        source "$meta_file"
        echo "${PERSIST:-0}"
    else
        echo "0"
    fi
}

load_size_value() {
    local name="$1"
    local meta_file="$META_DIR/$name.conf"

    if [[ -f "$meta_file" ]]; then
        # shellcheck disable=SC1090
        source "$meta_file"
        echo "${SIZE:-}"
    else
        echo ""
    fi
}

save_disk_config() {
    local name="$1"
    local persist="$2"
    local size="$3"
    local meta_file="$META_DIR/$name.conf"

    cat > "$meta_file" <<EOF
PERSIST=$persist
SIZE=$size
EOF
}

save_snapshot() {
    local name="$1"
    local mount_dir="$2"
    local snapshot_file="$SNAPSHOT_DIR/$name.tar.gz"

    if [[ -d "$mount_dir" ]]; then
        tar -C "$mount_dir" -czf "$snapshot_file" .
        echo "[INFO] Snapshot saved to $snapshot_file"
    fi
}

restore_snapshot() {
    local name="$1"
    local mount_dir="$2"
    local snapshot_file="$SNAPSHOT_DIR/$name.tar.gz"

    if [[ -f "$snapshot_file" ]]; then
        if tar -C "$mount_dir" -xzf "$snapshot_file" \
            --touch --no-same-owner --no-same-permissions --no-overwrite-dir; then
            echo "[INFO] Snapshot restored from $snapshot_file"
        else
            echo "[WARN] Snapshot restore had permission issues; mounted without full restore"
        fi
    fi
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

    SIZE=""
    PERSIST=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --size)
                SIZE="$2"
                shift 2
                ;;
            --persist)
                PERSIST="1"
                shift
                ;;
            --no-persist)
                PERSIST="0"
                shift
                ;;
            *)
                shift
                ;;
        esac
    done

    if [[ -z "$SIZE" ]]; then
        SIZE="$(load_size_value "$NAME")"
    fi

    if [[ -z "$SIZE" ]]; then
        SIZE="1G"
    fi

    if [[ -z "$PERSIST" ]]; then
        PERSIST="$(load_persist_flag "$NAME")"
    fi

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

    sudo mount -t tmpfs -o "size=$SIZE_BYTES,uid=$(id -u),gid=$(id -g),mode=700" tmpfs "$MOUNT"

    save_disk_config "$NAME" "$PERSIST" "$SIZE"

    if [[ "$PERSIST" == "1" ]]; then
        restore_snapshot "$NAME" "$MOUNT"
    fi

    if mountpoint -q "$MOUNT"; then
        echo "[OK] Mounted"
    else
        echo "[ERROR] Mount failed"
        exit 1
    fi
}

mount_disk() {
    NAME="$1"
    start "$NAME"
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
    PERSIST="$(load_persist_flag "$NAME")"

    if mountpoint -q "$MOUNT"; then
        if [[ "$PERSIST" == "1" ]]; then
            save_snapshot "$NAME" "$MOUNT"
        fi

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

delete_disk() {
    NAME="$1"
    MOUNT="$BASE/$NAME"
    META_FILE="$META_DIR/$NAME.conf"
    SNAPSHOT_FILE="$SNAPSHOT_DIR/$NAME.tar.gz"

    if mountpoint -q "$MOUNT"; then
        echo "[ERROR] Disk is mounted. Stop it first."
        exit 1
    fi

    rm -f "$META_FILE"
    rm -f "$SNAPSHOT_FILE"
    rm -rf "$MOUNT"

    echo "[OK] Deleted $NAME"
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
    mount) shift; mount_disk "$@" ;;
    stop) shift; stop "$@" ;;
    delete) shift; delete_disk "$@" ;;
    status) shift; status "$@" ;;
    version)
        echo "ramdisk.sh version $VERSION"
        ;;
    *) usage ;;
esac
