# RAMDisk Manager 3.3

RAMDisk Manager is a Linux RAM disk utility with both a graphical interface and a command line tool.
It helps you create fast tmpfs-based disks, mount and unmount them quickly, and optionally persist data between sessions.

## What This Project Contains

- ramdisk_gui.py: PySide6 desktop GUI
- ramdisk.sh: CLI backend script used by the GUI and terminal usage

## Main Features

- Create RAM disks with custom sizes (for example 32M, 512M, 1G, 0.5G)
- Manage disks from GUI: create, mount, stop, delete, refresh
- Persistent mode with snapshot save on stop and restore on mount/start
- Keep known persistent disks visible in GUI even when unmounted
- Disk status display in GUI (mounted or not mounted)
- Double-click a disk to mount if needed and open:
	- terminal in disk folder
	- file manager in disk folder
- GUI settings for default size, persistence, and encryption checkbox defaults
- Import and export disk configuration JSON files
- Built-in GUI log panel with copy and clear actions

## Requirements

- Linux
- bash
- sudo privileges for mount and umount operations
- tmpfs support
- Python 3
- PySide6

Install GUI dependency:

pip install PySide6

## GUI Usage

Start the GUI from the project folder:

python ramdisk_gui.py

Typical workflow:

1. Click Create
2. Enter disk name and size
3. Choose options in checkbox dialog (persistent, encryption)
4. Use Mount and Stop to activate or deactivate
5. Double-click disk for quick open actions
6. Use Settings to change defaults
7. Use Import or Export to manage saved disk configs

## CLI Usage

General syntax:

./ramdisk.sh <command> [options]

Commands:

- start <name> --size <size> [--persist|--no-persist]
- mount <name>
- stop <name>
- delete <name>
- status <name>
- version

CLI examples:

Create and mount a 512M disk:

./ramdisk.sh start work --size 512M

Create and mount a persistent 32M disk:

./ramdisk.sh start test --size 32M --persist

Mount an existing disk using saved config:

./ramdisk.sh mount test

Check status:

./ramdisk.sh status test

Stop disk (saves snapshot if persistent):

./ramdisk.sh stop test

Delete disk config and snapshot:

./ramdisk.sh delete test

Show script version:

./ramdisk.sh version

## Notes

- The script mounts tmpfs with user uid and gid options for better file access after mount.
- Persistent data is saved as tar.gz snapshots under ~/ramdisks/.snapshots.
- Disk metadata is stored under ~/ramdisks/.meta.
