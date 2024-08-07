import sys
import json
import re
import os
import requests
import tempfile
from urllib.parse import urlparse
import firebase_admin
from firebase_admin import credentials, storage
from PyQt5.QtWidgets import (
    QApplication,
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
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import cv2
import numpy as np


def hex_to_bgr(hex_color):
    hex_color = hex_color.lstrip("#")
    rgb = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return rgb[::-1]


def remove_specific_color(input_path, output_path, target_color, tolerance=30):
    img = cv2.imread(input_path)

    if img is None:
        print(f"Error: Could not read the image at {input_path}")
        return None

    target_color = hex_to_bgr(target_color)

    lower_bound = np.array([max(0, c - tolerance) for c in target_color])
    upper_bound = np.array([min(255, c + tolerance) for c in target_color])
    mask = cv2.inRange(img, lower_bound, upper_bound)

    mask = cv2.bitwise_not(mask)
    result = cv2.bitwise_and(img, img, mask=mask)
    result[mask == 0] = 255

    return result


def increase_contrast(image, alpha=1.5, beta=0):
    return cv2.convertScaleAbs(image, alpha=alpha, beta=beta)


def make_greys_darker(image, gamma=0.7):
    invGamma = 1.0 / gamma
    table = np.array(
        [((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]
    ).astype("uint8")
    return cv2.LUT(image, table)


def process_image(input_path, output_path, target_color, contrast_alpha=1.5, gamma=0.2):
    # Remove watermark
    result = remove_specific_color(input_path, output_path, target_color)
    if result is None:
        return

    # Increase contrast
    result = increase_contrast(result, alpha=contrast_alpha)

    # Convert to grayscale
    result = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)

    # Make greys darker
    result = make_greys_darker(result, gamma=gamma)

    # Save the final result
    cv2.imwrite(output_path, result)
    print(f"Processed image saved to {output_path}")


class ImageMigrationThread(QThread):
    progress_update = pyqtSignal(int)
    status_update = pyqtSignal(str)
    file_finished = pyqtSignal(str)

    def __init__(self, json_files):
        QThread.__init__(self)
        self.json_files = json_files
        self.bucket = None

    def run(self):
        try:
            self.setup_firebase()
            for json_file in self.json_files:
                self.status_update.emit(
                    f"Processing file: {os.path.basename(json_file)}"
                )
                data, image_urls = self.extract_image_urls(json_file)
                url_mapping = {}

                with tempfile.TemporaryDirectory() as temp_dir:
                    for i, url in enumerate(image_urls):
                        self.status_update.emit(
                            f"Processing image {i+1} of {len(image_urls)}"
                        )
                        local_path = self.download_image(url, temp_dir)
                        if local_path:
                            if "cdn.testbook.com" not in url:
                                # Apply image processing
                                processed_path = os.path.join(
                                    temp_dir,
                                    f"p_{os.path.basename(local_path)}",
                                )
                                target_color = "#EBF3F3"  # The color to remove
                                process_image(local_path, processed_path, target_color)
                                upload_path = processed_path
                            else:
                                upload_path = local_path

                            file_name = os.path.basename(upload_path)
                            remote_path = f"migrated_images/{file_name}"
                            firebase_url = self.upload_to_firebase(
                                upload_path, remote_path
                            )
                            url_mapping[url] = firebase_url
                        self.progress_update.emit(int((i + 1) / len(image_urls) * 100))

                # Replace old URLs with new Firebase URLs in the JSON data
                for i, item in enumerate(data):
                    if isinstance(item, str):
                        for old_url, new_url in url_mapping.items():
                            item = item.replace(old_url, new_url)
                        data[i] = item

                # Save updated JSON
                output_file = os.path.join(
                    os.path.dirname(json_file), "updated_" + os.path.basename(json_file)
                )
                with open(output_file, "w", encoding="utf-8") as file:
                    json.dump(data, file, ensure_ascii=False, indent=2)

                self.file_finished.emit(json_file)

        except Exception as e:
            self.status_update.emit(f"An error occurred: {str(e)}")

    def setup_firebase(self):
        firebase_config = {
            "type": "service_account",
            "project_id": "gquiz-2",
            "private_key_id": "7f8b0ecc956b8d2eea7c62aa3d5df2f33bbf363c",
            "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCc9w+iNREyhQpN\nqpdY960xmfDscXJm/hC8ZioDnJXAQRC+08e+9eFpf1P/P58gXaRmcrmhUP5a+xhX\nB7MpvapbWIISWEwBEij4k1WgpLPoLgefup0tYOSgjg40zDzTT6fgr1zqhpSFMonN\nFNTw/wOwou+zCtWdoOBB1ValElDopXxzd9pOulnYNmWdauToz3qBdda5Gjbrtmi/\nHA7aoz8ztt8ZX+dPCtDiLMwppSeRlM/lEvqcWNFAtRcVxgTQD9rlVpGPY58gLZCm\nOBSwHC9pZNftXFRMjpCyrCzC2NB4rkgql+dZEO0Dob+mj4R06HLlNYEpOgpc0DUE\n+37kwfcTAgMBAAECggEABR63atUA2cjsQh2ROVnKJOs7v2qrjrypkAAG8HKsqOlk\n9ljnZVjDsizOE/nUHTqcXcIJKbRdFi0DI2ubJmdQ8Va/qCRCdDs3Urrzlf1pXCx0\n7NfkHMyMNyXz0CGezweQC3svy7WFAuFvaXRNI1HYW/fTLT0Y9ieWPW+AUcDWYG1g\nYiFBuue8jThFduD7n8Vc4ISG7E8bumfk6GplXAfUVm3cPNzm8NmGj6+BRDyCy/TO\nK3AKkzY9izyc7qiLWA4ywJoB8ftBEufW1QMrLIbFqf4L8Ri98iL3sIZR7GcqXyB8\n1T0bNu1xH35A72c1bweRmOhVewYHMLlDN7YWQWyxKQKBgQDNIONPjh0g0mR2KH75\nzLlDFtv7nZpgNI3vIFUbowAcxnRWxyMYtYL2fqAaGjQpB5tDvxUSsgbWfXtScchp\nhZVgBKqaOagAzLp1JrdaJconbJKKSQYEI1affXW3vnrzlIm880G9b2DK4vZti02t\n/TzhO47SToydJwj8VbTNvC0krQKBgQDD5GVVGCnNULV4zoULYrA6kOrPkL66AAvI\npyrDopN9YvhWEaFTS1zr2PnlAhwu5WIkchB6ICe2ziiqrRFHTf7GqXNdv0FX+p0s\nGKJ3RoOK8FjswVVkwFjDutARmbtickvDLHqcyPBCuByyl7JDHBHI+apcGvqAGHMh\nAmGTPvtCvwKBgBLgduqoSlft5J7XBTBZvabF4MKb80vtKi6aTBq5+lWrkaM2ui0Y\n7w9eAb/FL42jDI/Ect0Akw6EB6hDnkzPpTpr04NT0PkZ3gLP6EmcdqkAHdAp/iq9\nUchllEKvfcMSpUZFIISdTkv9bO4Rxrk/N64GfBMwdVI0+Ge4P2Y7bfAVAoGAVHVE\nu0uPulXx6AQimKYUFSwmERf3I3qhmgF5DqAptwXUzEcNpzv29Di4hWRDgnSju9Ly\nB7WVadu47N1xdazLDBxDAUhUg/opibmVUpe0X1MBBBLXHnlPzBPfYbdGc0uUHrIu\nqyp3bEy1EssUsJqJkH0UVmHLXy8rdC/yoemlq0ECgYEAn/g7eNaZ3BIU5PPqax7J\nryRb3EniwPEU6g5uRHgs/WB+z0XfrG5zuPad/BqH14UZ+xM6cim057HUaTsY0AIf\nA3mzuQbVjL51teFOVhJqp/A07IMxVC1d/MgI1tlL9UMxb7GzWeX8kfn7+yd9ez4T\nPuktNddUR/e0Uihju2sGrbM=\n-----END PRIVATE KEY-----\n",
            "client_email": "firebase-adminsdk-7s2bo@gquiz-2.iam.gserviceaccount.com",
            "client_id": "103601390977401602210",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-7s2bo%40gquiz-2.iam.gserviceaccount.com",
            "universe_domain": "googleapis.com",
        }
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(
            cred,
            {"storageBucket": "gquiz-2.appspot.com"},
        )
        self.bucket = storage.bucket()

    def extract_image_urls(self, json_file):
        with open(json_file, "r", encoding="utf-8") as file:
            data = json.load(file)

        image_urls = []
        img_pattern = r'<img\s+[^>]*src\s*=\s*["\']([^"\']+)["\'][^>]*>'

        for item in data:
            if isinstance(item, str):
                img_tags = re.findall(img_pattern, item, re.IGNORECASE)
                for url in img_tags:
                    if url.startswith("//"):
                        url = "https:" + url
                    image_urls.append(url)

        return data, image_urls

    def download_image(self, url, temp_dir):
        response = requests.get(url)
        if response.status_code == 200:
            file_name = os.path.basename(urlparse(url).path)
            file_path = os.path.join(temp_dir, file_name)
            with open(file_path, "wb") as file:
                file.write(response.content)
            return file_path
        return None

    def upload_to_firebase(self, local_path, remote_path):
        blob = self.bucket.blob(remote_path)
        blob.upload_from_filename(local_path)
        blob.make_public()
        return blob.public_url


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
            self.json_list.addItem(os.path.basename(file))

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
        self.updateStatus(f"Finished processing: {os.path.basename(file)}")
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = App()
    ex.show()
    sys.exit(app.exec_())
