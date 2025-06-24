import os
import re
import sys
import tempfile

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QIcon, QFont, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtGui import QPalette
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QListWidget, QPushButton, QFileDialog, QLabel, QListWidgetItem,
    QHBoxLayout, QTextEdit, QFrame, QMessageBox
)

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


class SvgHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tag_format = QTextCharFormat()
        self.tag_format.setForeground(QColor("#569CD6"))
        self.tag_format.setFontWeight(QFont.Weight.Bold)

        self.attr_format = QTextCharFormat()
        self.attr_format.setForeground(QColor("#9CDCFE"))

        self.value_format = QTextCharFormat()
        self.value_format.setForeground(QColor("#CE9178"))

    def highlightBlock(self, text):
        # Теги
        for match in re.finditer(r"</?\w+", text):
            self.setFormat(match.start(), match.end() - match.start(), self.tag_format)
        # Атрибуты
        for match in re.finditer(r"\b\w+(?==)", text):
            self.setFormat(match.start(), match.end() - match.start(), self.attr_format)
        # Значения
        for match in re.finditer(r'"[^"]*"', text):
            self.setFormat(match.start(), match.end() - match.start(), self.value_format)


class SvgPreviewWidget(QFrame):
    def __init__(self, svg_path, index=0, parent=None):
        super().__init__(parent)
        self.svg_path = svg_path
        self.expanded = False
        self.index = index
        even_bg = '#242426'
        odd_bg = '#1c1e1f'
        bg = even_bg if index % 2 == 0 else odd_bg
        css = (
            "QFrame {"
            f"background: {bg};"
            "}"
            "QLabel[role=\"filename\"] {"
            "background: #22262c;"
            "color: #fff;"
            "border-radius: 8px;"
            "padding: 2px 12px;"
            "font-size: 13px;"
            "font-weight: 500;"
            "margin-top: 6px;"
            "margin-bottom: 6px;"
            "qproperty-alignment: AlignCenter;"
            "}"
            "QPushButton {"
            "background: #23272e;"
            "color: #fff;"
            "border-radius: 6px;"
            "padding: 2px 10px;"
            "font-size: 12px;"
            "min-width: 80px;"
            "margin-left: 6px;"
            "}"
            "QPushButton:hover {"
            "background: #2a2d32;"
            "}"
            "QPlainTextEdit {"
            "background: #23272e;"
            "color: #e0e0e0;"
            "font-family: 'Fira Mono', 'Consolas', monospace;"
            "font-size: 12px;"
            "border-radius: 8px;"
            "border: 1px solid #333;"
            "margin-top: 8px;"
            "margin-bottom: 8px;"
            "padding: 6px;"
            "}"
        )
        self.setStyleSheet(css)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 14, 18, 14)
        self.layout.setSpacing(8)
        self.checkerboard = CheckerboardWidget(svg_path)
        self.layout.addWidget(self.checkerboard, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.label = QLabel(os.path.basename(svg_path))
        self.label.setProperty("role", "filename")
        self.layout.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignHCenter)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.show_code_btn = QPushButton()
        self.show_code_btn.setText('Показать код SVG')
        self.show_code_btn.setIcon(QIcon.fromTheme('document-preview'))
        self.show_code_btn.clicked.connect(self.toggle_code)
        btn_row.addWidget(self.show_code_btn)
        self.copy_btn = QPushButton()
        self.copy_btn.setText('Скопировать')
        self.copy_btn.setIcon(QIcon.fromTheme('edit-copy'))
        self.copy_btn.clicked.connect(self.copy_code)
        self.copy_btn.setVisible(False)
        btn_row.addWidget(self.copy_btn)
        btn_row.addStretch(1)
        self.layout.addLayout(btn_row)
        self.code_edit = Editor()
        self.code_edit.setVisible(False)
        # Подключаем подсветку
        self.highlighter = SvgHighlighter(self.code_edit.document())
        self.layout.addWidget(self.code_edit)
        self.setLayout(self.layout)

    def toggle_code(self):
        if not self.expanded:
            with open(self.svg_path, 'r', encoding='utf-8') as f:
                svg_code = f.read()
            self.code_edit.setPlainText(svg_code)
            self.code_edit.setVisible(True)
            self.copy_btn.setVisible(True)
            self.show_code_btn.setText('Скрыть код SVG')
            self.expanded = True
        else:
            self.code_edit.setVisible(False)
            self.copy_btn.setVisible(False)
            self.show_code_btn.setText('Показать код SVG')
            self.expanded = False
        self.update_list_item_size()

    def copy_code(self):
        clipboard = QApplication.instance().clipboard()
        clipboard.setText(self.code_edit.toPlainText())

    def update_list_item_size(self):
        parent = self.parent()
        while parent and not isinstance(parent, QListWidget):
            parent = parent.parent()
        if isinstance(parent, QListWidget):
            list_widget = parent
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if list_widget.itemWidget(item) is self:
                    item.setSizeHint(self.sizeHint())
                    break


class Editor(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)

        # Шрифт
        font = QFont("Fira Mono, Consolas, monospace")
        font.setPointSize(12)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

        # Цветовая палитра
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Base, QColor("#1e1e1e"))  # Фон
        palette.setColor(QPalette.ColorRole.Text, QColor("#d4d4d4"))  # Текст
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#264f78"))  # Выделение
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))  # Выделенный текст
        self.setPalette(palette)

        # Стиль через CSS
        self.setStyleSheet("""
            QTextEdit {
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                padding: 6px;
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Fira Mono', 'Consolas', monospace;
            }
        """)

        self.textChanged.connect(self.autoResize)

    def autoResize(self):
        self.document().setTextWidth(self.viewport().width())
        margins = self.contentsMargins()
        height = int(self.document().size().height() + margins.top() + margins.bottom())
        self.setFixedHeight(height)

    def resizeEvent(self, event):
        self.autoResize()
        super().resizeEvent(event)


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
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
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
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

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
                if len(named_blocks) == 1:
                    # Только одна иконка — имя файла без суффикса
                    svg_filename = base_name + '.svg'
                    vector_name, vector_block = named_blocks[0]
                    vector_params = converterScript.extract_vector_params(vector_block)
                    path_blocks = converterScript.extract_path_blocks(vector_block)
                    paths = []
                    for params_str, block in path_blocks:
                        style_dict = converterScript.parse_path_params(params_str)
                        path_data = converterScript.extract_path_data(block)
                        if not path_data.strip():
                            continue
                        paths.append((path_data, style_dict))
                    if not paths:
                        return None
                    svg_path = os.path.join(self.temp_dir, svg_filename)
                    svg = converterScript.convert_to_svg(paths, vector_params)
                    with open(svg_path, 'w', encoding='utf-8') as f:
                        f.write(svg)
                    return [(svg_path, svg_filename)]
                else:
                    for vector_name, vector_block in named_blocks:
                        parts = vector_name.split('_', 1)
                        style = parts[0]
                        prefix = parts[1] if len(parts) > 1 else None
                        vector_params = converterScript.extract_vector_params(vector_block)
                        path_blocks = converterScript.extract_path_blocks(vector_block)
                        paths = []
                        for params_str, block in path_blocks:
                            style_dict = converterScript.parse_path_params(params_str)
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
        idx = self.list_widget.count()
        for f in files:
            svg_paths = self.convert_file_to_svg(f)
            if svg_paths:
                for svg_path, svg_filename in svg_paths:
                    item = QListWidgetItem()
                    widget = SvgPreviewWidget(svg_path, idx)
                    item.setSizeHint(widget.sizeHint())
                    self.list_widget.addItem(item)
                    self.list_widget.setItemWidget(item, widget)
                    self.svg_files.append((svg_path, svg_filename))
                    idx += 1

    def open_file_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, 'Выберите файлы imageVector', '',
                                                'Kotlin files (*.kt);;All files (*)')
        if files:
            self.on_files_dropped(files)

    def save_all_svgs(self):
        folder = QFileDialog.getExistingDirectory(self, 'Выберите папку для сохранения SVG')
        if folder:
            for svg_path, orig_filename in self.svg_files:
                dest_path = os.path.join(folder, os.path.basename(svg_path))
                with open(svg_path, 'r', encoding='utf-8') as src, open(dest_path, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())

    def keyPressEvent(self, event):
        # Поддержка Ctrl+V (Cmd+V) для вставки файлов
        ctrl = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        cmd = event.modifiers() & Qt.KeyboardModifier.MetaModifier
        if (ctrl or cmd) and event.key() == Qt.Key.Key_V:
            clipboard = QApplication.instance().clipboard()
            mime = clipboard.mimeData()
            files = []
            if mime.hasUrls():
                files = [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]
            elif mime.hasText():
                # Иногда путь к файлу просто как текст
                text = mime.text().strip()
                if os.path.isfile(text):
                    files = [text]
            if files:
                self.on_files_dropped(files)
            else:
                QMessageBox.information(self, 'Вставка файлов', 'В буфере обмена нет файлов для вставки.')
        else:
            super().keyPressEvent(event)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
