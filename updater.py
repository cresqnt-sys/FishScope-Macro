import requests
import json
import webbrowser
from PyQt6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
import sys
import os

# Current version - update this when releasing new versions
CURRENT_VERSION = "2.0"

class UpdateChecker(QThread):
    update_available = pyqtSignal(str, str)  # latest_version, download_url
    no_update = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def run(self):
        try:
            # Check GitHub releases API
            response = requests.get(
                "https://api.github.com/repos/cresqnt-sys/FishScope-Macro/releases/latest",
                timeout=10
            )
            
            if response.status_code == 200:
                release_data = response.json()
                latest_version = release_data.get("tag_name", "").lstrip("v")
                download_url = release_data.get("html_url", "")
                
                if self.is_newer_version(latest_version, CURRENT_VERSION):
                    self.update_available.emit(latest_version, download_url)
                else:
                    self.no_update.emit()
            else:
                self.error_occurred.emit(f"Failed to check for updates: HTTP {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            self.error_occurred.emit(f"Network error while checking for updates: {str(e)}")
        except Exception as e:
            self.error_occurred.emit(f"Error checking for updates: {str(e)}")

    def is_newer_version(self, latest, current):
        """Compare version strings (e.g., "1.2.3" vs "1.2.2")"""
        try:
            latest_parts = [int(x) for x in latest.split('.')]
            current_parts = [int(x) for x in current.split('.')]
            
            # Pad shorter version with zeros
            max_len = max(len(latest_parts), len(current_parts))
            latest_parts.extend([0] * (max_len - len(latest_parts)))
            current_parts.extend([0] * (max_len - len(current_parts)))
            
            return latest_parts > current_parts
        except (ValueError, AttributeError):
            return False

class UpdateDialog(QDialog):
    def __init__(self, latest_version, download_url, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.setup_ui(latest_version)

    def setup_ui(self, latest_version):
        self.setWindowTitle("Update Available")
        self.setFixedSize(450, 200)
        self.setModal(True)
        
        # Apply dark theme
        self.setStyleSheet("""
            QDialog {
                background-color: #2d2d2d;
                color: #e0e0e0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #e0e0e0;
                background-color: transparent;
            }
            QPushButton {
                background-color: #4a4a4a;
                color: #e0e0e0;
                border: 1px solid #666666;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 500;
                font-size: 13px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
                border-color: #777777;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
                border-color: #888888;
            }
            QPushButton#update_btn {
                background-color: #28a745;
                border-color: #28a745;
            }
            QPushButton#update_btn:hover {
                background-color: #218838;
                border-color: #218838;
            }
            QPushButton#update_btn:pressed {
                background-color: #1e7e34;
                border-color: #1e7e34;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title_label = QLabel("Update Available")
        title_font = QFont("Segoe UI", 16, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Message
        message = f"A new version of FishScope Macro is available!\n\nCurrent version: {CURRENT_VERSION}\nLatest version: {latest_version}\n\nWould you like to download the update?"
        message_label = QLabel(message)
        message_label.setFont(QFont("Segoe UI", 11))
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setWordWrap(True)
        layout.addWidget(message_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        later_btn = QPushButton("Later")
        later_btn.clicked.connect(self.reject)
        button_layout.addWidget(later_btn)

        update_btn = QPushButton("Download Update")
        update_btn.setObjectName("update_btn")
        update_btn.clicked.connect(self.download_update)
        button_layout.addWidget(update_btn)

        layout.addLayout(button_layout)

    def download_update(self):
        """Open the download URL in the default browser"""
        webbrowser.open(self.download_url)
        self.accept()

class AutoUpdater:
    def __init__(self, parent_widget=None):
        self.parent_widget = parent_widget
        self.update_checker = None

    def check_for_updates(self, silent=False):
        """Check for updates. If silent=True, only show dialog if update is available."""
        if self.update_checker and self.update_checker.isRunning():
            return

        self.silent = silent
        self.update_checker = UpdateChecker()
        self.update_checker.update_available.connect(self.on_update_available)
        self.update_checker.no_update.connect(self.on_no_update)
        self.update_checker.error_occurred.connect(self.on_error)
        self.update_checker.start()

    def on_update_available(self, latest_version, download_url):
        """Called when an update is available"""
        dialog = UpdateDialog(latest_version, download_url, self.parent_widget)
        dialog.exec()

    def on_no_update(self):
        """Called when no update is available"""
        if not self.silent:
            msg = QMessageBox(self.parent_widget)
            msg.setWindowTitle("No Updates")
            msg.setText("You are running the latest version of FishScope Macro.")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #2d2d2d;
                    color: white;
                }
                QMessageBox QPushButton {
                    background-color: #4a4a4a;
                    color: white;
                    border: 1px solid #666666;
                    padding: 8px 16px;
                    border-radius: 4px;
                    min-width: 80px;
                }
                QMessageBox QPushButton:hover {
                    background-color: #5a5a5a;
                }
            """)
            msg.exec()

    def on_error(self, error_message):
        """Called when an error occurs during update check"""
        if not self.silent:
            msg = QMessageBox(self.parent_widget)
            msg.setWindowTitle("Update Check Failed")
            msg.setText(f"Failed to check for updates:\n{error_message}")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #2d2d2d;
                    color: white;
                }
                QMessageBox QPushButton {
                    background-color: #4a4a4a;
                    color: white;
                    border: 1px solid #666666;
                    padding: 8px 16px;
                    border-radius: 4px;
                    min-width: 80px;
                }
                QMessageBox QPushButton:hover {
                    background-color: #5a5a5a;
                }
            """)
            msg.exec()

    def get_current_version(self):
        """Get the current version string"""
        return CURRENT_VERSION
