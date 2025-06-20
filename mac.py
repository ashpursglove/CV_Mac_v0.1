#!/usr/bin/env python3
"""
usb_cam_viewer.py

A PyQt5 application that shows a live video feed from a USB camera
(using OpenCV). Replace `camera_index` if your device isn’t at 0.
"""

import sys
import cv2
import numpy as np
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QMessageBox
)

class CameraViewer(QWidget):
    def __init__(self, camera_index=0, fps=30):
        super().__init__()
        self.camera_index = camera_index
        self.fps = fps

        # --- UI SETUP ---
        self.setWindowTitle("USB Camera Live Feed")
        self.video_label = QLabel("Initializing camera...")
        self.video_label.setAlignment(Qt.AlignCenter)

        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.video_label)
        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)

        # --- SIGNALS ---
        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)

        # --- TIMER for frame updates ---
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

        # VideoCapture object (not yet opened)
        self.cap = None

    def start(self):
        """Open the camera and start the update timer."""
        if self.cap is None:
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_ANY)
        if not self.cap.isOpened():
            QMessageBox.critical(self, "Error", f"Cannot open camera #{self.camera_index}")
            return

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        interval_ms = int(1000 / self.fps)
        self.timer.start(interval_ms)

    def stop(self):
        """Stop timer and release camera."""
        self.timer.stop()
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.cap = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.video_label.setText("Camera stopped.")

    def update_frame(self):
        """Grab a frame from the camera and display it."""
        ret, frame = self.cap.read()
        if not ret:
            # error or camera disconnected
            self.stop()
            QMessageBox.warning(self, "Warning", "Failed to read frame from camera.")
            return

        # Convert BGR (OpenCV) → RGB (Qt)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w

        # Build QImage and set on label
        qimg = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self.video_label.setPixmap(pixmap.scaled(
            self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))

    def closeEvent(self, event):
        """Ensure camera is released on window close."""
        self.stop()
        event.accept()

def main():
    app = QApplication(sys.argv)
    viewer = CameraViewer(camera_index=0, fps=30)
    viewer.resize(800, 600)
    viewer.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
