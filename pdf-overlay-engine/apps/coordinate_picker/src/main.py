# path: apps/coordinate_picker/main.py
"""
MP4-1 Coordinate Picker
- 샘플 PDF를 열고 페이지 위에서 네모 영역을 드래그 선택
- 선택한 영역의 PDF 좌표(x, y, width, height)를 overlay_config.json에 저장
- 선택 영역에 서명/체크/날짜 이미지 파일을 미리 매칭해서 화면에 표시

실행:
  poetry run python apps/coordinate_picker/main.py
또는
  python apps/coordinate_picker/main.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QAction, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = BASE_DIR / "configs" / "overlay_config.json"


@dataclass
class OverlayBox:
    id: str
    page: int
    kind: str
    x: float
    y: float
    width: float
    height: float
    image_path: str = ""


class PdfCanvas(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.pdf_pixmap: Optional[QPixmap] = None
        self.preview_pixmap: Optional[QPixmap] = None
        self.scale: float = 1.0
        self.page_width_pt: float = 0
        self.page_height_pt: float = 0
        self.start_pos: Optional[QPoint] = None
        self.current_rect: Optional[QRect] = None
        self.boxes: List[OverlayBox] = []
        self.selected_image: Optional[QPixmap] = None
        self.on_selection_changed = None

    def load_page_image(self, pixmap: QPixmap, scale: float, page_size_pt: Tuple[float, float]):
        self.pdf_pixmap = pixmap
        self.preview_pixmap = pixmap.copy()
        self.scale = scale
        self.page_width_pt, self.page_height_pt = page_size_pt
        self.setPixmap(self.preview_pixmap)
        self.resize(self.preview_pixmap.size())
        self.current_rect = None
        self.boxes = []

    def set_boxes(self, boxes: List[OverlayBox]):
        self.boxes = boxes
        self.repaint_overlay()

    def set_selected_image(self, image_path: str):
        if image_path and Path(image_path).exists():
            self.selected_image = QPixmap(image_path)
        else:
            self.selected_image = None
        self.repaint_overlay()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.pdf_pixmap:
            self.start_pos = event.position().toPoint()
            self.current_rect = QRect(self.start_pos, QSize())
            self.repaint_overlay()

    def mouseMoveEvent(self, event):
        if self.start_pos and self.pdf_pixmap:
            end_pos = event.position().toPoint()
            self.current_rect = QRect(self.start_pos, end_pos).normalized()
            self.repaint_overlay()
            if self.on_selection_changed:
                self.on_selection_changed(self.current_rect)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.start_pos:
            end_pos = event.position().toPoint()
            self.current_rect = QRect(self.start_pos, end_pos).normalized()
            self.start_pos = None
            self.repaint_overlay()
            if self.on_selection_changed:
                self.on_selection_changed(self.current_rect)

    def qt_rect_to_pdf_rect(self, rect: QRect) -> Tuple[float, float, float, float]:
        # PyMuPDF 좌표계와 Qt 화면 좌표계 모두 좌상단 원점 기준이므로 scale만 환산
        return (
            round(rect.x() / self.scale, 2),
            round(rect.y() / self.scale, 2),
            round(rect.width() / self.scale, 2),
            round(rect.height() / self.scale, 2),
        )

    def pdf_box_to_qt_rect(self, box: OverlayBox) -> QRect:
        return QRect(
            int(box.x * self.scale),
            int(box.y * self.scale),
            int(box.width * self.scale),
            int(box.height * self.scale),
        )

    def repaint_overlay(self):
        if not self.pdf_pixmap:
            return
        canvas = self.pdf_pixmap.copy()
        painter = QPainter(canvas)

        # 저장된 박스 표시
        saved_pen = QPen(Qt.blue, 2, Qt.SolidLine)
        painter.setPen(saved_pen)
        for box in self.boxes:
            rect = self.pdf_box_to_qt_rect(box)
            painter.drawRect(rect)
            painter.drawText(rect.topLeft() + QPoint(4, -4), f"{box.id} ({box.kind})")
            if box.image_path and Path(box.image_path).exists():
                img = QPixmap(box.image_path).scaled(
                    rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                x = rect.x() + (rect.width() - img.width()) // 2
                y = rect.y() + (rect.height() - img.height()) // 2
                painter.drawPixmap(x, y, img)

        # 현재 드래그 중인 박스 표시
        if self.current_rect and self.current_rect.width() > 2 and self.current_rect.height() > 2:
            current_pen = QPen(Qt.red, 2, Qt.DashLine)
            painter.setPen(current_pen)
            painter.drawRect(self.current_rect)
            if self.selected_image:
                img = self.selected_image.scaled(
                    self.current_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                x = self.current_rect.x() + (self.current_rect.width() - img.width()) // 2
                y = self.current_rect.y() + (self.current_rect.height() - img.height()) // 2
                painter.drawPixmap(x, y, img)

        painter.end()
        self.preview_pixmap = canvas
        self.setPixmap(canvas)


class CoordinatePickerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MP4-1 PDF 좌표 선택기")
        self.resize(1280, 900)

        self.doc: Optional[fitz.Document] = None
        self.pdf_path: Optional[Path] = None
        self.current_page_index: int = 0
        self.zoom: float = 1.5
        self.config: Dict = {"pages": {}}
        self.current_image_path: str = ""

        self.canvas = PdfCanvas()
        self.canvas.on_selection_changed = self.update_selection_fields

        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.valueChanged.connect(self.change_page)

        self.kind_combo = QComboBox()
        self.kind_combo.addItems(["signature", "check", "date", "image"])

        self.id_edit = QLineEdit("signature_1")
        self.x_edit = QLineEdit()
        self.y_edit = QLineEdit()
        self.w_edit = QLineEdit()
        self.h_edit = QLineEdit()
        for e in [self.x_edit, self.y_edit, self.w_edit, self.h_edit]:
            e.setReadOnly(True)

        open_pdf_btn = QPushButton("PDF 열기")
        open_pdf_btn.clicked.connect(self.open_pdf)
        open_img_btn = QPushButton("매칭 이미지 선택")
        open_img_btn.clicked.connect(self.open_image)
        save_box_btn = QPushButton("선택 영역 저장")
        save_box_btn.clicked.connect(self.save_current_box)
        save_config_btn = QPushButton("JSON 저장")
        save_config_btn.clicked.connect(self.save_config)
        load_config_btn = QPushButton("JSON 불러오기")
        load_config_btn.clicked.connect(self.load_config)

        toolbar = QHBoxLayout()
        toolbar.addWidget(open_pdf_btn)
        toolbar.addWidget(QLabel("페이지"))
        toolbar.addWidget(self.page_spin)
        toolbar.addWidget(load_config_btn)
        toolbar.addWidget(save_config_btn)
        toolbar.addStretch()

        form = QFormLayout()
        form.addRow("영역 ID", self.id_edit)
        form.addRow("종류", self.kind_combo)
        form.addRow("x", self.x_edit)
        form.addRow("y", self.y_edit)
        form.addRow("width", self.w_edit)
        form.addRow("height", self.h_edit)
        form.addRow(open_img_btn)
        form.addRow(save_box_btn)

        side = QWidget()
        side.setLayout(form)
        side.setFixedWidth(280)

        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(False)

        body = QHBoxLayout()
        body.addWidget(scroll, 1)
        body.addWidget(side)

        root = QVBoxLayout()
        root.addLayout(toolbar)
        root.addLayout(body, 1)

        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)

        self._setup_menu()
        self.load_config(silent=True)

    def _setup_menu(self):
        act_open = QAction("PDF 열기", self)
        act_open.triggered.connect(self.open_pdf)
        self.menuBar().addAction(act_open)

    def open_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "샘플 PDF 선택", str(BASE_DIR), "PDF Files (*.pdf)")
        if not path:
            return
        self.pdf_path = Path(path)
        self.doc = fitz.open(str(self.pdf_path))
        self.page_spin.setMaximum(len(self.doc))
        self.page_spin.setValue(1)
        self.render_page(0)

    def open_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "서명/체크/날짜 이미지 선택", str(BASE_DIR), "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        if not path:
            return
        self.current_image_path = path
        self.canvas.set_selected_image(path)

    def render_page(self, page_index: int):
        if not self.doc:
            return
        self.current_page_index = page_index
        page = self.doc[page_index]
        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
        qpix = QPixmap.fromImage(image.copy())
        self.canvas.load_page_image(qpix, self.zoom, (page.rect.width, page.rect.height))
        self.refresh_boxes_for_page()

    def change_page(self, page_no: int):
        self.render_page(page_no - 1)

    def update_selection_fields(self, rect: QRect):
        if not rect or rect.width() <= 0 or rect.height() <= 0:
            return
        x, y, w, h = self.canvas.qt_rect_to_pdf_rect(rect)
        self.x_edit.setText(str(x))
        self.y_edit.setText(str(y))
        self.w_edit.setText(str(w))
        self.h_edit.setText(str(h))

    def save_current_box(self):
        if not self.canvas.current_rect:
            QMessageBox.warning(self, "확인", "PDF 위에서 먼저 네모 영역을 드래그하세요.")
            return
        box_id = self.id_edit.text().strip()
        if not box_id:
            QMessageBox.warning(self, "확인", "영역 ID를 입력하세요.")
            return

        x, y, w, h = self.canvas.qt_rect_to_pdf_rect(self.canvas.current_rect)
        page_key = str(self.current_page_index + 1)
        self.config.setdefault("pages", {}).setdefault(page_key, {}).setdefault("positions", [])
        positions = self.config["pages"][page_key]["positions"]

        new_item = {
            "id": box_id,
            "type": self.kind_combo.currentText(),
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "image_path": self.current_image_path,
        }

        # 같은 id는 덮어쓰기
        replaced = False
        for idx, item in enumerate(positions):
            if item.get("id") == box_id:
                positions[idx] = new_item
                replaced = True
                break
        if not replaced:
            positions.append(new_item)

        self.refresh_boxes_for_page()
        QMessageBox.information(self, "저장", f"{box_id} 영역을 저장했습니다.")

    def refresh_boxes_for_page(self):
        page_key = str(self.current_page_index + 1)
        raw = self.config.get("pages", {}).get(page_key, {}).get("positions", [])
        boxes = [
            OverlayBox(
                id=item.get("id", ""),
                page=self.current_page_index + 1,
                kind=item.get("type", item.get("kind", "image")),
                x=float(item.get("x", 0)),
                y=float(item.get("y", 0)),
                width=float(item.get("width", 0)),
                height=float(item.get("height", 0)),
                image_path=item.get("image_path", ""),
            )
            for item in raw
        ]
        self.canvas.set_boxes(boxes)

    def save_config(self):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")
        QMessageBox.information(self, "JSON 저장", f"저장 완료:\n{CONFIG_PATH}")

    def load_config(self, silent: bool = False):
        if CONFIG_PATH.exists():
            self.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if self.doc:
                self.refresh_boxes_for_page()
            if not silent:
                QMessageBox.information(self, "JSON 불러오기", f"불러오기 완료:\n{CONFIG_PATH}")
        else:
            self.config = {"pages": {}}
            if not silent:
                QMessageBox.information(self, "JSON 불러오기", "기존 overlay_config.json이 없어 새로 시작합니다.")


def main():
    app = QApplication(sys.argv)
    win = CoordinatePickerWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
