from PyQt5.QtWidgets import (
    QWidget,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFileDialog,
    QTextEdit,
    QProgressBar,
    QMessageBox,
    QListWidget,
)
from PyQt5.QtCore import Qt
from migration_thread import ImageMigrationThread


class App(QWidget):
    def __init__(self):
        super().__init__()
        self.title = "Firebase Image Migration App"
        self.json_files = []
        self.initUI()

    def initUI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet(
            """
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                font-family: Arial;
            }
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 10px 20px;
                text-align: center;
                text-decoration: none;
                font-size: 16px;
                margin: 4px 2px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QLabel {
                font-size: 14px;
            }
            QTextEdit, QListWidget {
                background-color: #3b3b3b;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 5px;
                color: #ffffff;
            }
            QProgressBar {
                border: 2px solid #555;
                border-radius: 5px;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                width: 10px;
                margin: 0.5px;
            }
        """
        )

        layout = QVBoxLayout()

        # JSON Files Selection
        json_layout = QHBoxLayout()
        self.json_label = QLabel("Selected JSON Files:")
        self.json_button = QPushButton("Add JSON Files")
        self.json_button.clicked.connect(self.selectJsonFiles)
        json_layout.addWidget(self.json_label)
        json_layout.addWidget(self.json_button)
        layout.addLayout(json_layout)

        # List of selected JSON files
        self.json_list = QListWidget()
        layout.addWidget(self.json_list)

        # Start Migration Button
        self.start_button = QPushButton("Start Migration")
        self.start_button.clicked.connect(self.startMigration)
        layout.addWidget(self.start_button)

        # Progress Bar
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        # Status Text
        layout.addWidget(QLabel("Status:"))
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        layout.addWidget(self.status_text)

        self.setLayout(layout)

    def selectJsonFiles(self):
        filenames, _ = QFileDialog.getOpenFileNames(
            self, "Select JSON Files", "", "JSON Files (*.json)"
        )
        if filenames:
            self.json_files.extend(filenames)
            self.updateJsonList()

    def updateJsonList(self):
        self.json_list.clear()
        for file in self.json_files:
            self.json_list.addItem(file)

    def startMigration(self):
        if self.json_files:
            self.migration_thread = ImageMigrationThread(self.json_files)
            self.migration_thread.progress_update.connect(self.updateProgress)
            self.migration_thread.status_update.connect(self.updateStatus)
            self.migration_thread.file_finished.connect(self.fileFinished)
            self.migration_thread.start()
            self.start_button.setEnabled(False)
        else:
            QMessageBox.warning(
                self,
                "Input Error",
                "Please select JSON files.",
            )

    def updateProgress(self, value):
        self.progress_bar.setValue(value)

    def updateStatus(self, message):
        self.status_text.append(message)

    def fileFinished(self, file):
        self.updateStatus(f"Finished processing: {file}")
        self.json_files.remove(file)
        self.updateJsonList()
        if not self.json_files:
            self.migrationFinished()

    def migrationFinished(self):
        self.updateStatus("All files processed. Migration completed!")
        self.start_button.setEnabled(True)
        QMessageBox.information(
            self,
            "Migration Complete",
            "Image migration for all files has been completed successfully!",
        )
