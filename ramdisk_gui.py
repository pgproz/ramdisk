#!/usr/bin/env python3

import os
import subprocess

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QListWidget, QHBoxLayout, QMessageBox, QInputDialog,
    QLabel, QProgressBar, QTextEdit, QDialog
)
from PySide6.QtCore import QTimer

VERSION="3.1.2"
RAMDISK_CMD = "ramdisk.sh"
BASE_DIR = os.path.expanduser("~/ramdisks")


def run_cmd(args):
    try:
        p = subprocess.run(
            [RAMDISK_CMD] + args,
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


class App(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(f"RAMDisk Manager v{VERSION}")

        layout = QVBoxLayout()

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.MultiSelection)

        self.label = QLabel("No selection")
        self.bar = QProgressBar()

        btns = QHBoxLayout()

        start_btn = QPushButton("Start")
        stop_btn = QPushButton("Stop")
        refresh_btn = QPushButton("Refresh")
        about_btn = QPushButton("About")

        start_btn.clicked.connect(self.start_disk)
        stop_btn.clicked.connect(self.stop_disks)
        refresh_btn.clicked.connect(self.refresh)
        about_btn.clicked.connect(self.about)

        btns.addWidget(start_btn)
        btns.addWidget(stop_btn)
        btns.addWidget(refresh_btn)
        btns.addWidget(about_btn)

        layout.addWidget(self.list)
        layout.addWidget(self.label)
        layout.addWidget(self.bar)
        layout.addLayout(btns)

        self.setLayout(layout)

        self.list.itemSelectionChanged.connect(self.update_status)

        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(3000)

        self.refresh()

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
            item.text() for item in self.list.selectedItems()
        }

        existing_items = {
            self.list.item(i).text(): self.list.item(i)
            for i in range(self.list.count())
        }

        disk_names = [
            d for d in os.listdir(BASE_DIR)
            if os.path.isdir(os.path.join(BASE_DIR, d))
        ]

        # add new items
        for name in disk_names:
            if name not in existing_items:
                self.list.addItem(name)

        # remove missing items
        for name in list(existing_items.keys()):
            if name not in disk_names:
                row = self.list.row(existing_items[name])
                self.list.takeItem(row)

        # restore selection
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.text() in current_selected:
                item.setSelected(True)

    def update_status(self):
        items = self.list.selectedItems()
        if not items:
            return

        name = items[0].text()
        path = os.path.join(BASE_DIR, name)

        percent, info = get_usage(path)

        self.bar.setValue(percent)
        self.label.setText(f"{name}: {info}")

    def start_disk(self):
        name, ok = QInputDialog.getText(self, "Start Disk", "Name:")
        if not ok or not name:
            return

        size, ok = QInputDialog.getText(self, "Size", "Size:", text="1G")
        if not ok:
            return

        # 🔥 Encryption dialog restored
        enc = QMessageBox.question(
            self,
            "Encryption",
            "Enable encryption for this RAM disk?"
        ) == QMessageBox.Yes

        args = ["start", name, "--size", size]

        if enc:
            args.append("--encrypted")

        result = run_cmd(args)

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
            result = run_cmd(["stop", i.text()])

            # 🔥 show errors immediately
            if "[ERROR]" in result:
                QMessageBox.critical(self, "Stop failed", result)

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
