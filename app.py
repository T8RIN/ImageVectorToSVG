import os
import re
import sys
import tempfile

import converterCLI as CLI

from PyQt6.QtCore import QSize
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPalette, QColor, QIcon
from PyQt6.QtGui import QPainter, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import (
    QMainWindow, QListWidget, QFileDialog,
    QLabel, QListWidgetItem,
    QMessageBox, QProgressDialog, QMenu
)
from PyQt6.QtWidgets import (
    QWidget, QTextEdit, QPushButton, QVBoxLayout, QHBoxLayout, QFrame
)


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
            "background: transparent;"
            "color: #cccccc;"
            "border: none;"
            "font-size: 14px;"
            "font-weight: 400;"
            "margin-top: 12px;"
            "margin-bottom: 0;"
            "qproperty-alignment: AlignLeft;"
            "}"
            "QPushButton[role=\"showcode\"] {"
            "background: rgba(255,255,255,0.12);"
            "border-radius: 14px;"
            "border: 1px solid #444;"
            "padding: 2px 8px;"
            "}"
            "QPushButton[role=\"showcode\"]:hover {"
            "background: rgba(255,255,255,0.25);"
            "border: 1.5px solid #888;"
            "}"
            "QPushButton[role=\"copybtn\"] {"
            "background: rgba(255,255,255,0.10);"
            "border-radius: 8px;"
            "color: #fff;"
            "border: 1px solid #444;"
            "padding: 4px 16px;"
            "font-size: 13px;"
            "}"
            "QPushButton[role=\"copybtn\"]:hover {"
            "background: rgba(255,255,255,0.22);"
            "border: 1.5px solid #888;"
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
        # Основной горизонтальный слой: слева иконка+название, справа глаз
        main_row = QHBoxLayout()
        main_row.setContentsMargins(0, 0, 0, 0)
        main_row.setSpacing(0)
        # Слева: вертикально иконка и название
        left_col = QVBoxLayout()
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(4)
        self.checkerboard = CheckerboardWidget(svg_path)
        left_col.addWidget(self.checkerboard, alignment=Qt.AlignmentFlag.AlignLeft)
        self.label = QLabel(os.path.basename(svg_path))
        self.label.setProperty("role", "filename")
        left_col.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignLeft)
        main_row.addLayout(left_col)
        # Справа по центру вертикально: глаз
        main_row.addStretch(1)
        self.show_code_btn = QPushButton()
        self.show_code_btn.setProperty("role", "showcode")
        self.show_code_btn.setToolTip('Показать SVG код')
        icon_eye = QIcon.fromTheme('eye')
        if icon_eye.isNull():
            icon_eye = QIcon.fromTheme('visibility')
        if not icon_eye.isNull():
            self.show_code_btn.setIcon(icon_eye)
        self.show_code_btn.setText('Показать SVG код')
        self.show_code_btn.setFixedHeight(28)
        self.show_code_btn.clicked.connect(self.toggle_code)
        main_row.addWidget(self.show_code_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.layout.addLayout(main_row)
        # Кнопка копирования — абсолютное позиционирование в правом верхнем углу блока кода
        self.code_edit = Editor()
        self.expanded = False
        self.code_edit.setVisible(False)
        self.highlighter = SvgHighlighter(self.code_edit.editor.document())
        self.layout.addWidget(self.code_edit)
        self.setLayout(self.layout)

    def toggle_code(self):
        if not self.expanded:
            with open(self.svg_path, 'r', encoding='utf-8') as f:
                svg_code = f.read()
            self.code_edit.editor.setPlainText(svg_code.strip())
            self.code_edit.setVisible(True)
            self.show_code_btn.setToolTip('Скрыть SVG код')
            icon_eye_off = QIcon.fromTheme('eye-closed')
            if icon_eye_off.isNull():
                icon_eye_off = QIcon.fromTheme('visibility-off')
            if not icon_eye_off.isNull():
                self.show_code_btn.setIcon(icon_eye_off)
            self.show_code_btn.setText('Скрыть SVG код')
            self.expanded = True
        else:
            self.code_edit.setVisible(False)
            self.show_code_btn.setToolTip('Показать SVG код')
            icon_eye = QIcon.fromTheme('eye')
            if icon_eye.isNull():
                icon_eye = QIcon.fromTheme('visibility')
            if not icon_eye.isNull():
                self.show_code_btn.setIcon(icon_eye)
            self.show_code_btn.setText('Показать SVG код')
            self.expanded = False

        self.code_edit.autoResize()
        self.update_list_item_size()

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


class Editor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Основной layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Контейнер для текста и кнопки
        frame = QFrame()
        frame.setObjectName("editorFrame")
        frame.setStyleSheet("""
            QFrame#editorFrame {
                border: 1px solid #444;
                border-radius: 10px;
            }
        """)

        frame_layout = QVBoxLayout(frame)
        frame_layout.setSpacing(0)

        # Текстовое поле
        self.editor = QTextEdit()
        self.editor.setReadOnly(True)

        font = QFont("Fira Mono, Consolas, monospace")
        font.setPointSize(12)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.editor.setFont(font)

        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Base, QColor("#1e1e1e"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#d4d4d4"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#264f78"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        self.editor.setPalette(palette)
        self.editor.setStyleSheet("QTextEdit { border: none; padding-top: 0px; }")

        # Кнопка копирования
        self.copy_btn = QPushButton()
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setToolTip("Скопировать SVG")
        self.copy_btn.setIconSize(QSize(14, 14))
        self.copy_btn.setStyleSheet("""
            QPushButton {
                min-width: 24px;
                min-height: 24px;
                max-width: 24px;
                max-height: 24px;
                border-radius: 8px;
                background: rgba(255,255,255,0.10);
                border: 1px solid #444;
                color: #fff;
                font-size: 12px;
                padding: 0;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.22);
                border: 1.5px solid #888;
            }
        """)

        icon = QIcon.fromTheme("edit-copy")
        if icon.isNull():
            icon = QIcon.fromTheme("content-copy")
        if not icon.isNull():
            self.copy_btn.setIcon(icon)
        else:
            self.copy_btn.setText("📋")

        self.copy_btn.clicked.connect(self.copy_code)

        # Кнопка поверх редактора
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch()
        button_layout.addWidget(self.copy_btn)

        frame_layout.addLayout(button_layout)
        frame_layout.addWidget(self.editor)

        layout.addWidget(frame)

        self.editor.textChanged.connect(self.autoResize)

    def copy_code(self):
        clipboard = QApplication.instance().clipboard()
        clipboard.setText(self.editor.toPlainText().strip())

    def autoResize(self):
        doc = self.editor.document()
        doc.setTextWidth(self.editor.viewport().width())
        margins = self.editor.contentsMargins()
        height = int(doc.size().height() + margins.top() + margins.bottom())
        self.setFixedHeight(height + 52)

    def setPlainText(self, text: str):
        self.editor.setPlainText(text)

    def toPlainText(self):
        return self.editor.toPlainText()

    def document(self):
        return self.editor.document()

    def resizeEvent(self, event):
        self.autoResize()
        super().resizeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('ImageVector to SVG Converter')
        self.setWindowIcon(QIcon('icon.png'))
        self.resize(700, 500)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.info_label = QLabel('Перетащите или вставьте файлы imageVector сюда\nили используйте кнопки ниже', self)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet('''
            QLabel {
                color: #aaa;
                font-size: 18px;
                font-weight: 500;
                padding: 40px 0 40px 0;
                border: 2px dashed #444;
                border-radius: 16px;
                background: #191a1c;
            }
        ''')
        self.layout.addWidget(self.info_label)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.layout.addWidget(self.list_widget)
        self.list_widget.setVisible(False)

        btn_layout = QHBoxLayout()
        self.add_button = QPushButton('Добавить')
        self.add_button.setIcon(QIcon.fromTheme('folder'))
        add_menu = QMenu(self)
        action_files = add_menu.addAction(QIcon.fromTheme('document-open'), 'Добавить файл(ы)')
        action_folder = add_menu.addAction(QIcon.fromTheme('folder'), 'Добавить папку')
        self.add_button.setMenu(add_menu)
        action_files.triggered.connect(self.open_file_dialog)
        action_folder.triggered.connect(self.open_folder_dialog)
        btn_layout.addWidget(self.add_button)
        self.save_button = QPushButton('Сохранить')
        self.save_button.setIcon(QIcon.fromTheme('document-save'))
        self.save_button.clicked.connect(self.save_all_svgs)
        btn_layout.addWidget(self.save_button)
        self.clear_button = QPushButton('Очистить список')
        self.clear_button.setIcon(QIcon.fromTheme('user-trash'))
        self.clear_button.clicked.connect(self.clear_svg_list)
        btn_layout.addWidget(self.clear_button)
        self.layout.addLayout(btn_layout)

        self.svg_files = []  # (svg_path, orig_filename)
        self.temp_dir = tempfile.mkdtemp()
        self.clear_temp_dir()

        # Включаем drag-and-drop на всё окно
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.update_info_label()

    def clear_temp_dir(self):
        for f in os.listdir(self.temp_dir):
            try:
                os.remove(os.path.join(self.temp_dir, f))
            except Exception:
                pass

    def update_info_label(self):
        is_empty = self.list_widget.count() == 0
        self.info_label.setVisible(is_empty)
        self.list_widget.setVisible(not is_empty)
        self.clear_button.setVisible(not is_empty)
        self.save_button.setVisible(not is_empty)

    def clear_svg_list(self):
        self.list_widget.clear()
        self.svg_files.clear()
        self.update_info_label()

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
            named_blocks = CLI.extract_named_vector_blocks(kotlin_code)
            svg_paths = []
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            if named_blocks:
                if len(named_blocks) == 1:
                    # Только одна иконка — имя файла без суффикса
                    svg_filename = base_name + '.svg'
                    vector_name, vector_block = named_blocks[0]
                    vector_params = CLI.extract_vector_params(vector_block)
                    path_blocks = CLI.extract_path_blocks(vector_block)
                    paths = []
                    for params_str, block in path_blocks:
                        style_dict = CLI.parse_path_params(params_str)
                        path_data = CLI.extract_path_data(block)
                        if not path_data.strip():
                            continue
                        paths.append((path_data, style_dict))
                    if not paths:
                        return None
                    svg_path = os.path.join(self.temp_dir, svg_filename)
                    svg = CLI.convert_to_svg(paths, vector_params)
                    with open(svg_path, 'w', encoding='utf-8') as f:
                        f.write(svg)
                    return [(svg_path, svg_filename)]
                else:
                    for vector_name, vector_block in named_blocks:
                        parts = vector_name.split('_', 1)
                        style = parts[0]
                        prefix = parts[1] if len(parts) > 1 else None
                        vector_params = CLI.extract_vector_params(vector_block)
                        path_blocks = CLI.extract_path_blocks(vector_block)
                        paths = []
                        for params_str, block in path_blocks:
                            style_dict = CLI.parse_path_params(params_str)
                            path_data = CLI.extract_path_data(block)
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
                        svg = CLI.convert_to_svg(paths, vector_params)
                        with open(svg_path, 'w', encoding='utf-8') as f:
                            f.write(svg)
                        svg_paths.append((svg_path, svg_filename))
                    return svg_paths if svg_paths else None
            # Если только один ImageVector (старый режим)
            vector_params = CLI.extract_vector_params(kotlin_code)
            path_blocks = CLI.extract_path_blocks(kotlin_code)
            paths = []
            for params_str, block in path_blocks:
                style = CLI.parse_path_params(params_str)
                path_data = CLI.extract_path_data(block)
                if not path_data.strip():
                    continue
                paths.append((path_data, style))
            if not paths:
                print(f"Файл {file_path} не содержит путей для SVG.")
                return None
            svg = CLI.convert_to_svg(paths, vector_params)
            svg_filename = base_name + '.svg'
            svg_path = os.path.join(self.temp_dir, svg_filename)
            with open(svg_path, 'w', encoding='utf-8') as f:
                f.write(svg)
            return [(svg_path, svg_filename)]
        except Exception as e:
            print(f"Ошибка при конвертации {file_path}: {e}")
            return None

    def on_files_dropped(self, files):
        # Фильтруем папки и файлы
        all_files = []
        for f in files:
            if os.path.isdir(f):
                for root, _, filenames in os.walk(f):
                    for name in filenames:
                        if name.endswith('.kt'):
                            all_files.append(os.path.join(root, name))
            else:
                all_files.append(f)
        self.convert_files_with_progress(all_files)

    def open_file_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, 'Выберите файлы imageVector', '',
                                                'Kotlin files (*.kt);;All files (*)')
        if files:
            self.on_files_dropped(files)

    def open_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, 'Выберите папку с .kt файлами')
        if folder:
            all_files = []
            for root, _, filenames in os.walk(folder):
                for name in filenames:
                    if name.endswith('.kt'):
                        all_files.append(os.path.join(root, name))
            self.convert_files_with_progress(all_files)

    def convert_files_with_progress(self, files):
        if not files:
            return
        progress = QProgressDialog('Конвертация файлов...', 'Отмена', 0, len(files), self)
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        idx = self.list_widget.count()
        for i, f in enumerate(files):
            progress.setValue(i)
            if progress.wasCanceled():
                break
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
        progress.setValue(len(files))
        self.update_info_label()

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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if widget and hasattr(widget, 'update_list_item_size'):
                widget.update_list_item_size()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ImageVector to SVG Converter")
    # Для macOS — иконка в Dock
    if sys.platform == "darwin":
        try:
            from AppKit import NSApplication, NSImage
            import os
            nsapp = NSApplication.sharedApplication()
            img = NSImage.alloc().initByReferencingFile_(os.path.abspath("icon.png"))
            nsapp.setApplicationIconImage_(img)
        except Exception as e:
            print("Не удалось установить иконку для Dock:", e)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
