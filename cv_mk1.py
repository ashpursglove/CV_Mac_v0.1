#!/usr/bin/env python3
"""
live_cam_processor.py

A PyQt5 app that shows a live USB-camera feed in the top-left panel.
When you click “Capture”, it freezes the frame and runs your HSV-mask +
morphology + contour pipeline on it, displaying results in the other panes.
"""

import sys
import time
import os
import cv2
import numpy as np

from PyQt5.QtCore import Qt, QTimer, QRect
from PyQt5.QtGui import QPixmap, QImage, QPainter, QFont, QIcon
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QMessageBox,
    QVBoxLayout, QWidget, QHBoxLayout, QLineEdit, QFileDialog, QSplashScreen
)

def resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller.
    """
    try:
        base_path = sys._MEIPASS  # type: ignore
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class ImageProcessorApp(QMainWindow):
    def __init__(self, camera_index=0, fps=30):
        super().__init__()
        self.camera_index = camera_index
        self.fps = fps

        self.cap = None                  # OpenCV VideoCapture
        self.current_frame = None        # latest BGR frame grabbed
        self.timer = QTimer(self)        # drives live feed

        self.init_ui()
        self.showMaximized()

    def init_ui(self):
        self.setWindowTitle("Live Spirulina Cell Counter - V0.5")
        self.setWindowIcon(QIcon(resource_path("icon.ico")))

        # Central widget + layouts
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(5,5,5,5)
        self.main_layout.setSpacing(5)

        # -------------- 2x2 Image Grid --------------
        self.images_layout = QHBoxLayout()
        self.main_layout.addLayout(self.images_layout)
        self.left_col = QVBoxLayout(); self.right_col = QVBoxLayout()
        self.images_layout.addLayout(self.left_col)
        self.images_layout.addLayout(self.right_col)

        # Labels for four panels
        self.original_label = QLabel("Live Feed")
        self.mask_label     = QLabel()
        self.morph_label    = QLabel()
        self.contour_label  = QLabel()
        for lbl in (self.original_label, self.mask_label,
                    self.morph_label, self.contour_label):
            lbl.setFixedSize(600, 400)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("border:1px solid #BBBBBB;")
        self.left_col.addWidget(self.original_label)
        self.left_col.addWidget(self.mask_label)
        self.right_col.addWidget(self.morph_label)
        self.right_col.addWidget(self.contour_label)

        # -------------- Controls Row A (Camera) --------------
        row_a = QHBoxLayout()
        self.start_cam_btn   = QPushButton("Start Camera")
        self.stop_cam_btn    = QPushButton("Stop Camera")
        self.capture_btn     = QPushButton("Capture")
        self.stop_cam_btn.setEnabled(False)
        row_a.addWidget(self.start_cam_btn)
        row_a.addWidget(self.stop_cam_btn)
        row_a.addWidget(self.capture_btn)
        self.main_layout.addLayout(row_a)

        # Hook up camera controls
        self.start_cam_btn.clicked.connect(self.start_camera)
        self.stop_cam_btn.clicked.connect(self.stop_camera)
        self.capture_btn.clicked.connect(self.capture_frame)
        self.timer.timeout.connect(self.update_live_frame)

        # -------------- Controls Row B (Parameters) --------------
        row_b = QHBoxLayout()
        self.main_layout.addLayout(row_b)
        def make_param(label, default, tip, w=60):
            box = QHBoxLayout()
            lbl = QLabel(label); edit = QLineEdit(str(default))
            lbl.setToolTip(tip); edit.setToolTip(tip)
            edit.setFixedWidth(w)
            box.addWidget(lbl); box.addWidget(edit)
            return box, edit

        # Hue/Sat/Val + kernel + area
        params = [
            ("Low Hue:", 23, "Lower HSV hue bound"), 
            ("High Hue:",179,"Upper HSV hue bound"),
            ("Low Sat:", 38, "Lower HSV sat bound"),
            ("High Sat:",255,"Upper HSV sat bound"),
            ("Low Val:", 43, "Lower HSV val bound"),
            ("High Val:",187,"Upper HSV val bound"),
            ("Kernel:",   7, "Morph close kernel size"),
            ("Min A:",   20, "Minimum contour area"),
            ("Max A:", 3515, "Maximum contour area"),
        ]
        self.param_edits = []
        for lbl, val, tip in params:
            box, edit = make_param(lbl, val, tip, w=60)
            row_b.addLayout(box)
            self.param_edits.append(edit)

        # -------------- Controls Row C (Status) --------------
        row_c = QHBoxLayout()
        self.status_label   = QLabel("Cell Count: 0")
        row_c.addStretch()
        row_c.addWidget(self.status_label)
        row_c.addStretch()
        self.main_layout.addLayout(row_c)

        self.apply_dark_blue_theme()

    def apply_dark_blue_theme(self):
        qss = """
          QMainWindow, QWidget { background: #2F3E4C; color:#E0E0E0;
                               font:18px 'Segoe UI'; }
          QLabel { background:transparent; }
          QLineEdit { background:#3E5060; border:1px solid #888; }
          QPushButton { font:18px 'Segoe UI'; border-radius:4px; padding:6px;}
          QPushButton:hover { background:#186618; }
        """
        self.setStyleSheet(qss)

    # === Camera control slots ===
    def start_camera(self):
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_ANY)
        if not self.cap.isOpened():
            QMessageBox.critical(self, "Error", "Cannot open camera.")
            return
        self.start_cam_btn.setEnabled(False); self.stop_cam_btn.setEnabled(True)
        interval = int(1000/self.fps)
        self.timer.start(interval)

    def stop_camera(self):
        self.timer.stop()
        if self.cap:
            self.cap.release()
        self.cap = None
        self.start_cam_btn.setEnabled(True); self.stop_cam_btn.setEnabled(False)
        self.original_label.setText("Live Feed Stopped")

    def update_live_frame(self):
        """Grab frame from camera and display in the top-left."""
        ret, frame = self.cap.read()
        if not ret:
            self.stop_camera()
            QMessageBox.warning(self, "Warning", "Failed to read from camera.")
            return
        self.current_frame = frame.copy()  # BGR
        # convert to RGB and display
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self.update_label_image(self.original_label, rgb)

    def capture_frame(self):
        """Freeze current_frame and run CV on it."""
        if self.current_frame is None:
            QMessageBox.warning(self, "Warning", "No frame to capture.")
            return
        self.process_frame(self.current_frame)

    # === Core processing ===
    def process_frame(self, image_bgr):
        """Run your HSV→morph→contours pipeline on a BGR image."""
        # read params
        try:
            low_hue, high_hue = int(self.param_edits[0].text()), int(self.param_edits[1].text())
            low_sat, high_sat = int(self.param_edits[2].text()), int(self.param_edits[3].text())
            low_val, high_val = int(self.param_edits[4].text()), int(self.param_edits[5].text())
            kernel_size      = int(self.param_edits[6].text())
            min_area, max_area = float(self.param_edits[7].text()), float(self.param_edits[8].text())
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Enter valid numeric parameters.")
            return

        if kernel_size % 2 == 0: kernel_size += 1

        # 1) HSV mask
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (low_hue,low_sat,low_val), (high_hue,high_sat,high_val))
        m_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        cv2.putText(m_bgr, "Mask", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,0,255),2)
        self.update_label_image(self.mask_label, cv2.cvtColor(m_bgr, cv2.COLOR_BGR2RGB))

        # 2) Morph close
        kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size,kernel_size))
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kern, iterations=2)
        c_bgr = cv2.cvtColor(closed, cv2.COLOR_GRAY2BGR)
        cv2.putText(c_bgr, "Morph", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,0,255),2)
        self.update_label_image(self.morph_label, cv2.cvtColor(c_bgr, cv2.COLOR_BGR2RGB))

        # 3) Contours
        cnts, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        good = [c for c in cnts if min_area <= cv2.contourArea(c) <= max_area]
        out = image_bgr.copy()
        cv2.drawContours(out, good, -1, (0,255,0),2)
        for i,c in enumerate(good,1):
            M = cv2.moments(c)
            if M["m00"]:
                cx = int(M["m10"]/M["m00"]); cy = int(M["m01"]/M["m00"])
                cv2.putText(out, str(i),(cx-10,cy-10), cv2.FONT_HERSHEY_SIMPLEX,0.7,(255,0,0),2)
        cv2.putText(out, f"Contours (Count: {len(good)})",(10,30),
                    cv2.FONT_HERSHEY_SIMPLEX,1.2,(0,0,255),2)
        self.status_label.setText(f"Cell Count: {len(good)}")
        self.update_label_image(self.contour_label,
                                cv2.cvtColor(out, cv2.COLOR_BGR2RGB))

    def update_label_image(self, label: QLabel, rgb_img):
        """Convert an RGB numpy array to QPixmap and display it."""
        h, w, _ = rgb_img.shape
        qimg = QImage(rgb_img.data, w, h, 3*w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        pix = pix.scaled(label.width(), label.height(),
                         Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setPixmap(pix)

    def closeEvent(self, event):
        """Ensure camera is released on exit."""
        self.stop_camera()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("icon.ico")))

    # Splash screen (optional)
    splash_pix = QPixmap(800,400)
    splash_pix.fill(Qt.darkGreen)
    painter = QPainter(splash_pix)
    painter.setPen(Qt.white)
    # ... your splash drawing code here ...
    painter.end()

    splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint|Qt.FramelessWindowHint)
    splash.show(); app.processEvents()
    time.sleep(3)  # shorten as you like

    window = ImageProcessorApp(camera_index=0, fps=30)
    window.show()
    splash.finish(window)
    sys.exit(app.exec_())
