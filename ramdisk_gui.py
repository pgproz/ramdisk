#!/usr/bin/env python3

import os
import re
import subprocess
import json

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QListWidget, QHBoxLayout, QMessageBox, QInputDialog,
    QLabel, QProgressBar, QTextEdit, QDialog, QCheckBox, QDialogButtonBox,
    QFileDialog, QLineEdit
)
from PySide6.QtCore import QTimer, Qt, QDateTime

VERSION="3.3"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAMDISK_CMD = os.path.join(SCRIPT_DIR, "ramdisk.sh")
BASE_DIR = os.path.expanduser("~/ramdisks")
META_DIR = os.path.join(BASE_DIR, ".meta")
SNAPSHOT_DIR = os.path.join(BASE_DIR, ".snapshots")
SETTINGS_FILE = os.path.join(BASE_DIR, ".gui_settings.json")
SIZE_PATTERN = re.compile(r"^\s*\d+(?:\.\d+)?\s*(?:[kKmMgGtT](?:[bB])?)?\s*$")
DEFAULT_SETTINGS = {
    "default_size": "512M",
    "default_persist": True,
    "default_encrypt": False,
}


def run_cmd(args):
    try:
        p = subprocess.run(
            ["bash", RAMDISK_CMD] + args,
            capture_output=True,
            text=True
        )

        output = (p.stdout or "") + (p.stderr or "")

        if p.returncode != 0:
            return f"[ERROR]\n{output}"

        return output

    except Exception as e:
        return f"[EXCEPTION] {str(e)}"


def get_usage(path):
    try:
        out = subprocess.check_output(["df", "-h", path]).decode().splitlines()[1]
        parts = out.split()
        percent = int(parts[4].replace("%", ""))
        return percent, f"{parts[2]}/{parts[1]}"
    except:
        return 0, "N/A"


def is_valid_size(size):
    return bool(SIZE_PATTERN.fullmatch(size))


def list_mounted_disks():
    mounted = set()
    try:
        with open("/proc/mounts", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 2:
                    continue
                mount_path = parts[1]
                if mount_path.startswith(BASE_DIR + "/"):
                    name = os.path.basename(mount_path)
                    if name and not name.startswith("."):
                        mounted.add(name)
    except Exception:
        pass
    return mounted


def list_persistent_disks():
    disks = set()

    if os.path.isdir(META_DIR):
        for entry in os.listdir(META_DIR):
            if entry.endswith(".conf"):
                disks.add(entry[:-5])

    if os.path.isdir(SNAPSHOT_DIR):
        for entry in os.listdir(SNAPSHOT_DIR):
            if entry.endswith(".tar.gz"):
                disks.add(entry[:-7])

    return disks


def is_disk_persistent(name):
    conf_path = os.path.join(META_DIR, f"{name}.conf")
    if not os.path.isfile(conf_path):
        return False

    try:
        with open(conf_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip() == "PERSIST=1":
                    return True
    except Exception:
        return False

    return False


class App(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(f"RAMDisk Manager v{VERSION}")
        self.settings = self.load_settings()

        layout = QVBoxLayout()

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.MultiSelection)

        self.label = QLabel("No selection")
        self.bar = QProgressBar()

        main_btns = QHBoxLayout()
        util_btns = QHBoxLayout()

        start_btn = QPushButton("Create")
        mount_btn = QPushButton("Mount")
        stop_btn = QPushButton("Stop")
        delete_btn = QPushButton("Delete")
        settings_btn = QPushButton("Settings")
        import_btn = QPushButton("Import")
        export_btn = QPushButton("Export")
        copy_log_btn = QPushButton("Copy Log")
        clear_log_btn = QPushButton("Clear Log")
        refresh_btn = QPushButton("Refresh")
        about_btn = QPushButton("About")

        start_btn.clicked.connect(self.start_disk)
        mount_btn.clicked.connect(self.mount_disks)
        stop_btn.clicked.connect(self.stop_disks)
        delete_btn.clicked.connect(self.delete_disks)
        settings_btn.clicked.connect(self.open_settings)
        import_btn.clicked.connect(self.import_configs)
        export_btn.clicked.connect(self.export_configs)
        copy_log_btn.clicked.connect(self.copy_log)
        clear_log_btn.clicked.connect(self.clear_log)
        refresh_btn.clicked.connect(self.refresh)
        about_btn.clicked.connect(self.about)

        main_btns.addWidget(start_btn)
        main_btns.addWidget(mount_btn)
        main_btns.addWidget(stop_btn)
        main_btns.addWidget(delete_btn)

        util_btns.addWidget(settings_btn)
        util_btns.addWidget(import_btn)
        util_btns.addWidget(export_btn)
        util_btns.addWidget(copy_log_btn)
        util_btns.addWidget(clear_log_btn)
        util_btns.addWidget(refresh_btn)
        util_btns.addWidget(about_btn)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Command output log")
        self.log_box.setMaximumHeight(140)

        layout.addWidget(self.list)
        layout.addWidget(self.label)
        layout.addWidget(self.bar)
        layout.addLayout(main_btns)
        layout.addLayout(util_btns)
        layout.addWidget(self.log_box)

        self.setLayout(layout)

        self.list.itemSelectionChanged.connect(self.update_status)
        self.list.itemDoubleClicked.connect(self.open_disk_entry)

        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(3000)

        self.log("Application started")
        self.refresh()

    def load_settings(self):
        settings = dict(DEFAULT_SETTINGS)

        try:
            if os.path.isfile(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    settings.update(data)
        except Exception:
            pass

        return settings

    def save_settings(self):
        os.makedirs(BASE_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=2)

    def log(self, message):
        ts = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        self.log_box.append(f"[{ts}] {message}")

    def run_cmd_logged(self, args):
        self.log(f"$ ramdisk.sh {' '.join(args)}")
        result = run_cmd(args)
        output = result.strip()
        if output:
            self.log(output)
        return result

    def clear_log(self):
        self.log_box.clear()
        self.log("Log cleared")

    def copy_log(self):
        text = self.log_box.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Copy log", "Log is empty.")
            return

        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copy log", "Log copied to clipboard.")

    def read_disk_config(self, name):
        config = {
            "name": name,
            "size": "",
            "persist": False,
        }

        conf_path = os.path.join(META_DIR, f"{name}.conf")
        if not os.path.isfile(conf_path):
            return config

        try:
            with open(conf_path, "r", encoding="utf-8") as f:
                for line in f:
                    key, _, value = line.partition("=")
                    key = key.strip().upper()
                    value = value.strip()
                    if key == "PERSIST":
                        config["persist"] = value == "1"
                    elif key == "SIZE":
                        config["size"] = value
        except Exception:
            pass

        return config

    def write_disk_config(self, name, size, persist):
        os.makedirs(META_DIR, exist_ok=True)
        conf_path = os.path.join(META_DIR, f"{name}.conf")
        with open(conf_path, "w", encoding="utf-8") as f:
            f.write(f"PERSIST={'1' if persist else '0'}\n")
            f.write(f"SIZE={size}\n")

    def open_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")

        layout = QVBoxLayout(dialog)

        size_label = QLabel("Default size:")
        size_edit = QLineEdit(self.settings.get("default_size", "512M"))
        persist_cb = QCheckBox("Default: persistent")
        persist_cb.setChecked(bool(self.settings.get("default_persist", True)))
        encrypt_cb = QCheckBox("Default: encryption")
        encrypt_cb.setChecked(bool(self.settings.get("default_encrypt", False)))

        layout.addWidget(size_label)
        layout.addWidget(size_edit)
        layout.addWidget(persist_cb)
        layout.addWidget(encrypt_cb)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return

        size_value = size_edit.text().strip()
        if not is_valid_size(size_value):
            QMessageBox.warning(self, "Invalid size", "Use a value like 512M, 1G, or 0.5G.")
            return

        self.settings["default_size"] = size_value
        self.settings["default_persist"] = persist_cb.isChecked()
        self.settings["default_encrypt"] = encrypt_cb.isChecked()
        self.save_settings()
        self.log("Settings saved")

    def export_configs(self):
        os.makedirs(META_DIR, exist_ok=True)

        config_names = sorted(
            entry[:-5]
            for entry in os.listdir(META_DIR)
            if entry.endswith(".conf")
        )

        if not config_names:
            QMessageBox.information(self, "Export", "No disk configurations to export.")
            return

        default_path = os.path.join(BASE_DIR, "ramdisk-configs.json")
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export disk configurations",
            default_path,
            "JSON files (*.json)"
        )
        if not file_path:
            return

        payload = {
            "version": 1,
            "configs": [self.read_disk_config(name) for name in config_names],
        }

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            self.log(f"Exported {len(config_names)} config(s) to {file_path}")
            QMessageBox.information(self, "Export", f"Exported {len(config_names)} config(s).")
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))

    def import_configs(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import disk configurations",
            BASE_DIR,
            "JSON files (*.json)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Import failed", f"Could not read file: {e}")
            return

        if isinstance(payload, dict):
            configs = payload.get("configs", [])
        elif isinstance(payload, list):
            configs = payload
        else:
            QMessageBox.critical(self, "Import failed", "Invalid JSON format.")
            return

        imported = 0
        skipped = 0
        for cfg in configs:
            if not isinstance(cfg, dict):
                skipped += 1
                continue

            name = str(cfg.get("name", "")).strip()
            size = str(cfg.get("size", "")).strip()
            persist = bool(cfg.get("persist", False))

            if not name:
                skipped += 1
                continue

            if not size:
                size = self.settings.get("default_size", "512M")

            if not is_valid_size(size):
                skipped += 1
                continue

            self.write_disk_config(name, size, persist)
            imported += 1

        self.refresh()
        self.log(f"Imported {imported} config(s), skipped {skipped}")
        QMessageBox.information(
            self,
            "Import",
            f"Imported {imported} config(s). Skipped {skipped}."
        )

    def ask_disk_options(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Disk options")

        layout = QVBoxLayout(dialog)

        persist_cb = QCheckBox("Keep data for next start (persistent)")
        encrypt_cb = QCheckBox("Enable encryption")
        persist_cb.setChecked(bool(self.settings.get("default_persist", True)))
        encrypt_cb.setChecked(bool(self.settings.get("default_encrypt", False)))

        layout.addWidget(persist_cb)
        layout.addWidget(encrypt_cb)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return None

        return persist_cb.isChecked(), encrypt_cb.isChecked()

#    def refresh(self):
#        self.list.clear()

#        if not os.path.exists(BASE_DIR):
#            os.makedirs(BASE_DIR, exist_ok=True)

#        for d in os.listdir(BASE_DIR):
#            if not d.endswith(".enc"):
#                self.list.addItem(d)
    def refresh(self):
        if not os.path.exists(BASE_DIR):
            os.makedirs(BASE_DIR, exist_ok=True)

        current_selected = {
            item.data(Qt.UserRole)
            for item in self.list.selectedItems()
            if item.data(Qt.UserRole)
        }

        existing_items = {
            self.list.item(i).data(Qt.UserRole): self.list.item(i)
            for i in range(self.list.count())
            if self.list.item(i).data(Qt.UserRole)
        }

        mounted_disks = list_mounted_disks()
        persistent_disks = list_persistent_disks()
        disk_names = sorted(mounted_disks | persistent_disks)

        # add new items
        for name in disk_names:
            if name not in existing_items:
                self.list.addItem(name)

        # remove missing items
        for name in list(existing_items.keys()):
            if name not in disk_names:
                row = self.list.row(existing_items[name])
                self.list.takeItem(row)

        # refresh labels and metadata
        for i in range(self.list.count()):
            item = self.list.item(i)
            name = item.data(Qt.UserRole) or item.text()

            mounted = name in mounted_disks
            persistent = is_disk_persistent(name)

            status = "mounted" if mounted else "not mounted"
            if persistent:
                status = f"{status}, persistent"

            item.setText(f"{name} [{status}]")
            item.setData(Qt.UserRole, name)

        # restore selection
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.data(Qt.UserRole) in current_selected:
                item.setSelected(True)

    def update_status(self):
        items = self.list.selectedItems()
        if not items:
            self.bar.setValue(0)
            self.label.setText("No selection")
            return

        name = items[0].data(Qt.UserRole) or items[0].text()
        path = os.path.join(BASE_DIR, name)

        if not os.path.ismount(path):
            self.bar.setValue(0)
            self.label.setText(f"{name}: not mounted")
            return

        percent, info = get_usage(path)

        self.bar.setValue(percent)
        self.label.setText(f"{name}: {info}")

    def start_disk(self):
        name, ok = QInputDialog.getText(self, "Start Disk", "Name:")
        if not ok or not name:
            return

        size, ok = QInputDialog.getText(
            self,
            "Size",
            "Size (examples: 512M, 1G, 0.5G):",
            text=self.settings.get("default_size", "512M")
        )
        if not ok:
            return

        size = size.strip()
        if not size or not is_valid_size(size):
            QMessageBox.warning(
                self,
                "Invalid size",
                "Use a value like 512M, 1G, or 0.5G."
            )
            return

        options = self.ask_disk_options()
        if options is None:
            return

        persist, enc = options

        args = ["start", name, "--size", size]

        if persist:
            args.append("--persist")
        else:
            args.append("--no-persist")

        if enc:
            args.append("--encrypted")

        result = self.run_cmd_logged(args)

        QMessageBox.information(self, "Result", result)
        self.refresh()

#    def stop_disks(self):
#        items = self.list.selectedItems()
#        if not items:
#            return

#        for i in items:
#            run_cmd(["stop", i.text()])

#        self.refresh()
    def stop_disks(self):
        items = self.list.selectedItems()
        if not items:
            return

        for i in items:
            name = i.data(Qt.UserRole) or i.text()
            result = self.run_cmd_logged(["stop", name])

            # 🔥 show errors immediately
            if "[ERROR]" in result:
                QMessageBox.critical(self, "Stop failed", result)

        self.refresh()

    def open_terminal_at(self, path):
        terminal_cmds = [
            ["x-terminal-emulator", "--working-directory", path],
            ["gnome-terminal", "--working-directory", path],
            ["konsole", "--workdir", path],
            ["xfce4-terminal", "--working-directory", path],
            ["kitty", "--directory", path],
            ["alacritty", "--working-directory", path],
            ["tilix", "--working-directory", path],
        ]

        for cmd in terminal_cmds:
            try:
                subprocess.Popen(cmd)
                return True
            except FileNotFoundError:
                continue
            except Exception:
                continue

        return False

    def open_file_manager_at(self, path):
        try:
            subprocess.Popen(["xdg-open", path])
            return True
        except Exception:
            return False

    def open_disk_entry(self, item):
        name = item.data(Qt.UserRole) or item.text()
        path = os.path.join(BASE_DIR, name)

        if not os.path.ismount(path):
            reply = QMessageBox.question(
                self,
                "Disk not mounted",
                f"{name} is not mounted. Mount it now?"
            )
            if reply != QMessageBox.Yes:
                return

            result = self.run_cmd_logged(["mount", name])
            if "[ERROR]" in result:
                QMessageBox.critical(self, "Mount failed", result)
                return

            self.refresh()

        action = QMessageBox(self)
        action.setWindowTitle("Open disk")
        action.setText(f"Choose how to open {name}.")
        terminal_btn = action.addButton("Open terminal", QMessageBox.ActionRole)
        manager_btn = action.addButton("Open file manager", QMessageBox.ActionRole)
        cancel_btn = action.addButton(QMessageBox.Cancel)
        action.exec()

        clicked = action.clickedButton()
        if clicked == cancel_btn:
            return

        if clicked == terminal_btn:
            if not self.open_terminal_at(path):
                QMessageBox.warning(
                    self,
                    "No terminal found",
                    "Could not find a supported terminal emulator."
                )
        elif clicked == manager_btn:
            if not self.open_file_manager_at(path):
                QMessageBox.warning(
                    self,
                    "Open failed",
                    "Could not open a file manager for this path."
                )

        self.refresh()

    def mount_disks(self):
        items = self.list.selectedItems()
        if not items:
            return

        for i in items:
            name = i.data(Qt.UserRole) or i.text()
            path = os.path.join(BASE_DIR, name)

            if os.path.ismount(path):
                continue

            result = self.run_cmd_logged(["mount", name])

            if "[ERROR]" in result:
                QMessageBox.critical(self, "Mount failed", result)

        self.refresh()

    def delete_disks(self):
        items = self.list.selectedItems()
        if not items:
            return

        names = [i.data(Qt.UserRole) or i.text() for i in items]
        names_text = "\n".join(names)

        confirm = QMessageBox.question(
            self,
            "Delete disk",
            "Delete selected disk(s)? This removes saved snapshots and metadata.\n\n"
            f"{names_text}"
        )
        if confirm != QMessageBox.Yes:
            return

        had_errors = False
        for name in names:
            result = self.run_cmd_logged(["delete", name])
            if "[ERROR]" in result:
                had_errors = True
                QMessageBox.critical(self, "Delete failed", result)

        if not had_errors:
            QMessageBox.information(self, "Delete", "Selected disk(s) deleted.")

        self.refresh()

    def about(self):
        QMessageBox.information(
        self,
        "About",
        f"RAMDisk Manager\nVersion {VERSION}"
    )

if __name__ == "__main__":
    app = QApplication([])
    w = App()
    w.resize(420, 400)
    w.show()
    app.exec()
