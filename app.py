import sys
import os
import tempfile
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QListWidget, QPushButton, QFileDialog, QLabel, QListWidgetItem, QHBoxLayout
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtGui import QPainter, QColor, QBrush
import converterScript

class CheckerboardWidget(QWidget):
    def __init__(self, svg_path, parent=None):
        super().__init__(parent)
        self.svg_path = svg_path
        self.svg_widget = QSvgWidget()
        self.svg_widget.load(svg_path)
        self.setFixedSize(100, 100)

    def paintEvent(self, event):
        painter = QPainter(self)
        size = 10
        color1 = QColor(220, 220, 220)
        color2 = QColor(180, 180, 180)
        for y in range(0, self.height(), size):
            for x in range(0, self.width(), size):
                if ((x // size) + (y // size)) % 2 == 0:
                    painter.fillRect(x, y, size, size, color1)
                else:
                    painter.fillRect(x, y, size, size, color2)
        # SVG рисуется поверх
        self.svg_widget.renderer().render(painter)

class SvgPreviewWidget(QWidget):
    def __init__(self, svg_path, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.checkerboard = CheckerboardWidget(svg_path)
        layout.addWidget(self.checkerboard)
        self.label = QLabel(os.path.basename(svg_path))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        self.setLayout(layout)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('ImageVector to SVG Converter')
        self.resize(700, 500)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.info_label = QLabel('Перетащите файлы imageVector в любое место окна или используйте кнопку ниже', self)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.info_label)

        self.list_widget = QListWidget()
        self.layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.add_button = QPushButton('Добавить файл(ы)')
        self.add_button.clicked.connect(self.open_file_dialog)
        btn_layout.addWidget(self.add_button)
        self.save_button = QPushButton('Сохранить все SVG в папку...')
        self.save_button.clicked.connect(self.save_all_svgs)
        btn_layout.addWidget(self.save_button)
        self.layout.addLayout(btn_layout)

        self.svg_files = []  # (svg_path, orig_filename)
        self.temp_dir = tempfile.mkdtemp()

        # Включаем drag-and-drop на всё окно
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        files = [url.toLocalFile() for url in urls]
        print(f"Файлы перетащены: {files}")
        self.on_files_dropped(files)

    def convert_file_to_svg(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                kotlin_code = f.read()
            named_blocks = converterScript.extract_named_vector_blocks(kotlin_code)
            svg_paths = []
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            if named_blocks:
                for vector_name, vector_block in named_blocks:
                    parts = vector_name.split('_', 1)
                    style = parts[0]
                    prefix = parts[1] if len(parts) > 1 else None
                    vector_params = converterScript.extract_vector_params(vector_block)
                    path_blocks = converterScript.extract_path_blocks(vector_block)
                    paths = []
                    for params_str, block in path_blocks:
                        style_dict = converterScript.parse_path_params(params_str)
                        # Для Outlined больше не трогаем fill/stroke — только оригинальные параметры
                        path_data = converterScript.extract_path_data(block)
                        if not path_data.strip():
                            continue
                        paths.append((path_data, style_dict))
                    if not paths:
                        continue
                    svg_filename = f"{base_name}_{style}"
                    if prefix and prefix.lower() != base_name.lower():
                        svg_filename += f"_{prefix}"
                    svg_filename += ".svg"
                    svg_path = os.path.join(self.temp_dir, svg_filename)
                    svg = converterScript.convert_to_svg(paths, vector_params)
                    with open(svg_path, 'w', encoding='utf-8') as f:
                        f.write(svg)
                    svg_paths.append((svg_path, svg_filename))
                return svg_paths if svg_paths else None
            # Если только один ImageVector (старый режим)
            vector_params = converterScript.extract_vector_params(kotlin_code)
            path_blocks = converterScript.extract_path_blocks(kotlin_code)
            paths = []
            for params_str, block in path_blocks:
                style = converterScript.parse_path_params(params_str)
                path_data = converterScript.extract_path_data(block)
                if not path_data.strip():
                    continue
                paths.append((path_data, style))
            if not paths:
                print(f"Файл {file_path} не содержит путей для SVG.")
                return None
            svg = converterScript.convert_to_svg(paths, vector_params)
            svg_filename = base_name + '.svg'
            svg_path = os.path.join(self.temp_dir, svg_filename)
            with open(svg_path, 'w', encoding='utf-8') as f:
                f.write(svg)
            return [(svg_path, svg_filename)]
        except Exception as e:
            print(f"Ошибка при конвертации {file_path}: {e}")
            return None

    def on_files_dropped(self, files):
        for f in files:
            svg_paths = self.convert_file_to_svg(f)
            if svg_paths:
                for svg_path, svg_filename in svg_paths:
                    item = QListWidgetItem()
                    widget = SvgPreviewWidget(svg_path)
                    item.setSizeHint(widget.sizeHint())
                    self.list_widget.addItem(item)
                    self.list_widget.setItemWidget(item, widget)
                    self.svg_files.append((svg_path, svg_filename))

    def open_file_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, 'Выберите файлы imageVector', '', 'Kotlin files (*.kt);;All files (*)')
        if files:
            self.on_files_dropped(files)

    def save_all_svgs(self):
        folder = QFileDialog.getExistingDirectory(self, 'Выберите папку для сохранения SVG')
        if folder:
            for svg_path, orig_filename in self.svg_files:
                dest_path = os.path.join(folder, os.path.basename(svg_path))
                with open(svg_path, 'r', encoding='utf-8') as src, open(dest_path, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 