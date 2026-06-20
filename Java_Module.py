import sys
import re
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPlainTextEdit, QToolBar,
    QFileDialog, QMessageBox
)
from PyQt6.QtGui import QAction, QKeySequence, QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PyQt6.QtCore import Qt, QRegularExpression


class JavaHighlighter(QSyntaxHighlighter):
    """Apply simple syntax highlighting for Java code."""

    KEYWORDS = [
        "abstract", "assert", "boolean", "break", "byte", "case", "catch",
        "char", "class", "const", "continue", "default", "do", "double",
        "else", "enum", "extends", "final", "finally", "float", "for",
        "goto", "if", "implements", "import", "instanceof", "int",
        "interface", "long", "native", "new", "package", "private",
        "protected", "public", "return", "short", "static", "strictfp",
        "super", "switch", "synchronized", "this", "throw", "throws",
        "transient", "try", "void", "volatile", "while",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        # Format for keywords
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor("#000080"))
        self.keyword_format.setFontWeight(QFont.Weight.Bold)

        # Format for single-line comments (//)
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#008000"))
        self.comment_format.setFontItalic(True)

        # Format for multi-line comments (/* ... */)
        self.multiline_comment_format = QTextCharFormat()
        self.multiline_comment_format.setForeground(QColor("#008000"))
        self.multiline_comment_format.setFontItalic(True)

        # Format for strings
        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("#800000"))

        # Build QRegularExpression patterns
        # Keywords: whole words only
        keyword_pattern = "\\b(" + "|".join(self.KEYWORDS) + ")\\b"
        self.keyword_re = QRegularExpression(keyword_pattern)

        # Single-line comment
        self.comment_re = QRegularExpression("//[^\n]*")

        # Strings (simple double-quoted, does not handle escaped quotes inside)
        self.string_re = QRegularExpression("\"[^\"]*\"")

        # Multi-line comment start and end patterns (used in highlightBlock)
        self.comment_start_re = QRegularExpression("/\\*")
        self.comment_end_re = QRegularExpression("\\*/")

    def highlightBlock(self, text):
        """Apply highlighting to the given block of text."""

        # --- Keywords ---
        it = self.keyword_re.globalMatch(text)
        while it.hasNext():
            match = it.next()
            self.setFormat(match.capturedStart(), match.capturedLength(),
                           self.keyword_format)

        # --- Single-line comments ---
        # We need to apply string highlighting only before a comment starts,
        # so we first find the earliest single-line comment.
        comment_match = self.comment_re.match(text)   # finds first match
        if comment_match.hasMatch():
            comment_start = comment_match.capturedStart()
            self.setFormat(comment_start, comment_match.capturedLength(),
                           self.comment_format)
            text_before_comment = text[:comment_start]
        else:
            text_before_comment = text

        # --- Strings (only up to the start of a single-line comment) ---
        str_it = self.string_re.globalMatch(text_before_comment)
        while str_it.hasNext():
            match = str_it.next()
            self.setFormat(match.capturedStart(), match.capturedLength(),
                           self.string_format)

        # --- Multi-line comments (/* ... */) ---
        self.setCurrentBlockState(0)

        start_index = 0
        if self.previousBlockState() != 1:
            # Not already inside a multi-line comment: find first /*
            start_match = self.comment_start_re.match(text)
            if start_match.hasMatch():
                start_index = start_match.capturedStart()
            else:
                start_index = -1
        # else: inside a comment from previous block – start at beginning

        while start_index >= 0:
            end_match = self.comment_end_re.match(text, start_index + 2)  # search for */
            if not end_match.hasMatch():
                # No end found: comment continues to end of block
                self.setCurrentBlockState(1)
                comment_length = len(text) - start_index
                self.setFormat(start_index, comment_length,
                               self.multiline_comment_format)
                break
            else:
                end_index = end_match.capturedStart()
                comment_length = end_index - start_index + 2  # include */
                self.setFormat(start_index, comment_length,
                               self.multiline_comment_format)
                # Look for another start after this comment
                next_start_match = self.comment_start_re.match(text, end_index + 2)
                if next_start_match.hasMatch():
                    start_index = next_start_match.capturedStart()
                else:
                    start_index = -1

class JavaEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file = None          # full path of the current file
        self.text_modified = False        # track unsaved changes

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Basic Java Code Editor")
        self.resize(900, 700)

        # Editor widget
        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("Courier New", 11))
        self.editor.textChanged.connect(self.on_text_changed)
        self.setCentralWidget(self.editor)

        # Syntax highlighter
        self.highlighter = JavaHighlighter(self.editor.document())

        # Menu bar
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")

        # New action
        new_action = QAction("&New", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self.new_file)
        file_menu.addAction(new_action)

        # Open action
        open_action = QAction("&Open...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        # Save action
        save_action = QAction("&Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)

        # Save As action
        save_as_action = QAction("Save &As...", self)
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_action.triggered.connect(self.save_file_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        # Exit action
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Toolbar with Open and Save buttons
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        # Open button
        open_tool = QAction("Open", self)
        open_tool.triggered.connect(self.open_file)
        toolbar.addAction(open_tool)

        # Save button
        save_tool = QAction("Save", self)
        save_tool.triggered.connect(self.save_file)
        toolbar.addAction(save_tool)

        self.statusBar().showMessage("Ready")

    def on_text_changed(self):
        """Mark that the document has been modified."""
        self.text_modified = True

    def maybe_save(self):
        """If there are unsaved changes, ask the user to save. Returns True if we can proceed."""
        if self.text_modified:
            ret = QMessageBox.warning(
                self, "Unsaved Changes",
                "The document has been modified.\nDo you want to save your changes?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel
            )
            if ret == QMessageBox.StandardButton.Save:
                return self.save_file()
            elif ret == QMessageBox.StandardButton.Cancel:
                return False
        return True

    def new_file(self):
        if self.maybe_save():
            self.editor.clear()
            self.current_file = None
            self.text_modified = False
            self.setWindowTitle("Basic Java Code Editor - Untitled")
            self.statusBar().showMessage("New file created")

    def open_file(self):
        if self.maybe_save():
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Open Java File", "",
                "Java Files (*.java);;All Files (*)"
            )
            if file_path:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    self.editor.setPlainText(content)
                    self.current_file = file_path
                    self.text_modified = False
                    self.setWindowTitle(f"Basic Java Code Editor - {file_path}")
                    self.statusBar().showMessage(f"Opened {file_path}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Could not open file:\n{e}")

    def save_file(self):
        if self.current_file is None:
            return self.save_file_as()
        else:
            try:
                with open(self.current_file, "w", encoding="utf-8") as f:
                    f.write(self.editor.toPlainText())
                self.text_modified = False
                self.setWindowTitle(f"Basic Java Code Editor - {self.current_file}")
                self.statusBar().showMessage(f"Saved {self.current_file}")
                return True
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save file:\n{e}")
                return False

    def save_file_as(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Java File As", "",
            "Java Files (*.java);;All Files (*)"
        )
        if file_path:
            # If no extension provided, append .java
            if not file_path.endswith(".java"):
                file_path += ".java"
            self.current_file = file_path
            return self.save_file()
        return False

    def closeEvent(self, event):
        """Handle window close event, prompt to save if needed."""
        if self.maybe_save():
            event.accept()
        else:
            event.ignore()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = JavaEditor()
    editor.show()
    sys.exit(app.exec())