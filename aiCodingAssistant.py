""" 
Python Programming Help App

Architecture Overview:
- MainWindow acts as the central controller and manages page navigation.
- Each page (Start, Question, Accessibility, Session Manager) is a QWidget.
- Pages communicate through MainWindow (no direct page-to-page coupling).
- Sessions store UI settings and skill level in a JSON file.
- Skill level affects question difficulty via weighted random selection.
"""

import sys
import random
import math
import requests
import json
import os
import ast
import builtins
import keyword

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QLineEdit,
    QVBoxLayout,
    QStackedWidget,
    QComboBox,
    QSlider,
    QMainWindow,
    QListWidget,
    QMessageBox,
    QGridLayout,
    QTextEdit,
    QPlainTextEdit,
    QProgressBar
)

from PyQt6.QtCore import (
    Qt, QTimer, QRect, QSize,
    QThread, pyqtSignal, pyqtSlot, QObject
)

    
from PyQt6.QtCore import Qt, QTimer, QRect, QSize

from PyQt6.QtGui import (
    QFont,
    QColor,
    QPainter,
    QTextFormat,
    QTextCursor
)


import config

# <Utility functions>

def read_questions_from_file(filename):
    """
    Reads questions from file in groups of three lines:
    Line 1: (unused category placeholder)
    Line 2: difficulty label
    Line 3: question text
    NOTE:
    Difficulty values are read as strings.
    They are converted to integers when used
    for difficulty comparison.
    """
    if not os.path.exists(filename):
        return [], []

    with open(filename, "r", encoding="utf-8") as file:
        file_lines = [line.strip() for line in file]
        # Placeholder in case the category of
        # the question in case anyone will want to use it later.
        #category_list = file_lines[0::3]
        difficulty_list = file_lines[1::3]
        question_list = file_lines[2::3]

    return question_list, difficulty_list


def weighted_random_choice(choices, difficulty_bias):
    """
    difficulty_bias > 0 favours higher-indexed (harder) questions,
    difficulty_bias < 0 favours lower-indexed (easier) questions,
    difficulty_bias = 0 gives equal weight to all.
    Weights are normalized automatically by random.choices.
    
    Note: This assumes questions are roughly ordered by difficulty.
    """
    if not choices:
        return "No questions available."
    if len(choices) == 1:
        return choices[0]

    choice_count = len(choices)
    weights = [
        math.exp(difficulty_bias * (i / (choice_count - 1)))
        for i in range(choice_count)
    ]
    # Use k=1 to generate only one sample
    return random.choices(choices, weights=weights, k=1)[0]



# Timeout is set to 180 seconds (hardcoded). Ensure Ollama is running
# and accessible at OLLAMA_URL before calling this function.
# NOTE:
# All exceptions are caught and replaced with a generic message.
def ollama_generate(prompt, model=config.DEFAULT_MODEL):
    """
    Sends prompt to local Ollama server for AI grading or help.
    Requires Ollama running locally at OLLAMA_URL.
    Ollama can be run locally by using:
    ollama run [DEFAULT_MODEL]
    Should be normally:
    ollama run llama3.2:3b
    in the terminal.
    """
    try:
        http_response = requests.post(
            config.OLLAMA_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "timeout" : 180
            }
        )
        http_response.raise_for_status()
        return http_response.json()["response"]
    except Exception:
        return "Error contacting AI helper."


def load_sessions():
    """Load saved session data from JSON file."""
    if not os.path.exists(config.SESSION_STORAGE_FILE):
        return {}

    with open(config.SESSION_STORAGE_FILE, "r") as file:
        return json.load(file)


def save_sessions(session_data):
    """Persist session data to JSON file."""
    with open(config.SESSION_STORAGE_FILE, "w") as file:
    # Expected session_data format:
    # {
    #   "SessionName": {
    #       "text_size": "...",
    #       "button_size": "...",
    #       "theme_name": "Dark",
    #       "skill_level": int
    #   }
    # }
        json.dump(session_data, file, indent=4)

# UI helper function.
def build_vertical_layout(widget_list):
    """
    Creates a QVBoxLayout and adds all widgets in order.
    If the special string "STRETCH" is encountered,
    a stretch spacer is inserted at that position.
    """
    layout = QVBoxLayout()
    for widget in widget_list:
        if widget == "STRETCH":
            layout.addStretch()
        else:
            layout.addWidget(widget)
    return layout



class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        # Keep a reference to the parent editor so this
        # widget can delegate width calculation and painting logic.
        self.code_editor = editor
        self.setObjectName("LineNumberArea")

    # Qt uses sizeHint() to determine how much horizontal
    # space to reserve for the line number area.
    # Width dynamically scales based on number of digits.
    def sizeHint(self):
        return QSize(self.code_editor.line_number_area_width(), 0)

    # Delegate painting back to the main editor class.
    # This keeps all line-number rendering logic centralized.
    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    """
    Small IDE-like code editor widget with:
    - Line numbers
    - Current line highlight
    - Tab inserts spaces
    - Custom autocomplete popup
    """

    def __init__(self):
        super().__init__()
        
        # Set name of the code editor
        # for easier referencing from themes.
        self.setObjectName("CodeEditor")

        # ---------- Font Setup ----------
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(12)
        self.setFont(font)

        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))

        # ---------- Line Numbers ----------
        self.line_number_area = LineNumberArea(self)

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.error_color = QColor("#d32f2f")  # default
        self.update_line_number_area_width(0)
        self.highlight_current_line()

        # ---------- Autocomplete Setup ----------
        self.suggestion_popup = QListWidget()
        self.suggestion_popup.setWindowFlags(
            Qt.WindowType.ToolTip
        )
        self.suggestion_popup.itemClicked.connect(self.insert_completion)
        self.suggestion_popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.all_suggestions = []
        self.current_prefix = ""

        self.variable_types = {}

    # ==========================================================
    # ---------------- AUTOCOMPLETE LOGIC ----------------------
    # ==========================================================

    def set_suggestions(self, suggestions):
        """
        Called externally (from QuestionWindow)
        to update suggestion pool.
        """
        self.all_suggestions = suggestions

    def keyPressEvent(self, event):

        # ---------- If popup visible ----------
        # If autocomplete popup is open, intercept navigation keys
        # so arrow keys move inside the suggestion list instead
        # of moving the text cursor.
        if self.suggestion_popup.isVisible():

            if event.key() == Qt.Key.Key_Down:
                current_row = self.suggestion_popup.currentRow()
                self.suggestion_popup.setCurrentRow(
                    min(current_row + 1,
                        self.suggestion_popup.count() - 1)
                )
                return

            if event.key() == Qt.Key.Key_Up:
                current_row = self.suggestion_popup.currentRow()
                self.suggestion_popup.setCurrentRow(
                    max(current_row - 1, 0)
                )
                return

            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
                item = self.suggestion_popup.currentItem()
                if item:
                    self.insert_completion(item)
                    return

            if event.key() == Qt.Key.Key_Escape:
                self.suggestion_popup.hide()
                return

        # ---------- Normal typing ----------
        # Let the editor process normal typing first,
        # then compute suggestions based on updated text.
        super().keyPressEvent(event)

        # Trigger autocomplete AFTER typing
        self.trigger_autocomplete()

    def focusOutEvent(self, event):
        """Hide popup when editor loses focus (e.g., clicking another window)."""
        self.suggestion_popup.hide()
        super().focusOutEvent(event)

    def hideEvent(self, event):
        """Hide popup when editor is hidden (e.g., switching pages)."""
        self.suggestion_popup.hide()
        super().hideEvent(event)

    def wheelEvent(self, event):
        """Hide popup when user scrolls with mouse wheel."""
        self.suggestion_popup.hide()
        super().wheelEvent(event)

    def scrollContentsBy(self, dx, dy):
        """Hide popup when viewport is scrolled (e.g., via scrollbar)."""
        self.suggestion_popup.hide()
        super().scrollContentsBy(dx, dy)

    def resizeEvent(self, event):
        """Hide popup when editor is resized (window resize or zoom)."""
        super().resizeEvent(event)
        self.suggestion_popup.hide()

    # Refresh inferred variable types before computing suggestions.
    # This allows attribute autocomplete on variables defined earlier.
    def trigger_autocomplete(self):
        self.update_variable_types()
        
        expression, is_dot = self.get_object_before_dot()

        # First handle dot-attribute context (e.g., list_var.)
        # If a resolvable type is found, show attribute suggestions.
        if is_dot and expression:

            resolved = self.resolve_builtin_object(expression)
            if resolved:
                attributes = [attribute for attribute in dir(resolved)
                              if not attribute.startswith("__")]
                self.show_popup(attributes)
                return

        # Extract the word under cursor to use as autocomplete prefix.
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        prefix = cursor.selectedText()

        # Only show autocomplete for valid identifier prefixes.
        # Avoid triggering for numbers or symbols.
        if not prefix or not prefix[0].isalpha():
            self.suggestion_popup.hide()
            return

        self.current_prefix = prefix

        matches = self.rank_suggestions(prefix)
        self.show_popup(matches)



    def rank_suggestions(self, prefix):
        """
        Smart ranking strategy:

        1. Exact match prefix
        2. Startswith match
        3. Contains match
        4. Shorter names preferred
        """

        def score(word):
            if word == prefix:
                return (0, len(word))
            if word.startswith(prefix):
                return (1, len(word))
            if prefix in word:
                return (2, len(word))
            return (3, len(word))

        # Only consider words that contain the prefix at all.
        # Ranking then determines ordering preference.
        return sorted(
            (word for word in self.all_suggestions if prefix in word),
            key=score
        )

    def insert_completion(self, item):
        if not item:
            return

        # Replace the currently typed prefix with the selected suggestion.
        completion = item.text()
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        cursor.removeSelectedText()
        cursor.insertText(completion)
        self.setTextCursor(cursor)

        self.suggestion_popup.hide()

    def style_popup(self):
        """
        Adjust popup colors dynamically to match current theme.
        """
        palette = self.palette()
        background = palette.color(palette.ColorRole.Base).name()
        text_color = palette.color(palette.ColorRole.Text).name()
        highlight = palette.color(palette.ColorRole.Highlight).name()
        highlight_text = palette.color(palette.ColorRole.HighlightedText).name()

        self.suggestion_popup.setStyleSheet(f"""
            QListWidget {{
                background-color: {background};
                color: {text_color};
                border: 1px solid gray;
            }}
            QListWidget::item:selected {{
                background-color: {highlight};
                color: {highlight_text};
            }}
        """)

    # ==========================================================
    # ---------------- LINE NUMBER LOGIC -----------------------
    # ==========================================================

    # Width scales based on number of digits in total line count.
    # Ensures space increases automatically for larger files.
    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        return 3 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
        
    # If editor scrolls vertically, sync the line number area scroll.
    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(
                0, rect.y(),
                self.line_number_area.width(),
                rect.height()
            )

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(),
                  self.line_number_area_width(), cr.height())
        )

    # Custom painting routine for drawing line numbers
    # aligned with visible text blocks.
    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)

        palette = self.palette()
        background = palette.window()
        foreground = palette.text()

        painter.fillRect(event.rect(), background)
        painter.setPen(foreground.color())

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block)
                  .translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        # Iterate through visible text blocks to render line numbers.
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(Qt.GlobalColor.gray)
                
                # Draw line number right-aligned inside the reserved margin.
                painter.drawText(
                    0, top,
                    self.line_number_area.width() - 5,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    str(block_number + 1)
                )

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def highlight_current_line(self):
        extra_selections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()

            # Use theme-aware highlight colors from current palette.
            selection.format.setBackground(self.palette().highlight())
            selection.format.setForeground(self.palette().highlightedText())

            selection.format.setProperty(
                QTextFormat.Property.FullWidthSelection, True
            )
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

        self.setExtraSelections(extra_selections)

    def get_object_before_dot(self):
        """
        Detects dot context and extracts the expression before the dot.
        Returns (expression, is_dot_context)
        """

        # Determine whether the cursor is positioned immediately
        # after a dot, and if so, extract the expression preceding it.
        cursor = self.textCursor()
        position = cursor.position()
        text = self.toPlainText()

        if position < 1:
            return None, False

        if text[position - 1] != ".":
            return None, False

        i = position - 2
        
        # Ignore any accidental whitespace between expression and dot.
        while i >= 0 and text[i].isspace():
            i -= 1

        if i < 0:
            return None, False

        # If string literal
        # Handle string literal case: "hello". -> allow str methods.
        if text[i] in ['"', "'"]:
            quote = text[i]
            j = i - 1
            while j >= 0 and text[j] != quote:
                j -= 1
            if j >= 0:
                return text[j:i+1], True

        # If closing bracket literal
        # Handle literal containers like:
        #   [1,2].  {1:2}.  (1,2).
        # Walk backward to find matching opening bracket.
        if text[i] in ["]", "}", ")"]:
            closing = text[i]
            matching = {"]": "[", "}": "{", ")": "("}
            opening = matching[closing]

            depth = 1
            j = i - 1

            while j >= 0:
                if text[j] == closing:
                    depth += 1
                elif text[j] == opening:
                    depth -= 1
                    if depth == 0:
                        return text[j:i+1], True
                j -= 1

        # Otherwise parse identifier or number
        # Fallback: parse backward for identifier characters.
        # Supports simple chained attribute expressions like object.attr
        token_chars = []
        while i >= 0 and (text[i].isalnum() or text[i] in "._"):
            token_chars.append(text[i])
            i -= 1

        if not token_chars:
            return None, False

        return "".join(reversed(token_chars)), True

    # Attempt to resolve expression into a Python type
    # to provide attribute autocomplete suggestions.
    def resolve_builtin_object(self, expression):

        if not expression:
            return None

        # -------- Variable inference --------
        # Priority 1: Previously inferred variable types.
        if expression in self.variable_types:
            return self.variable_types[expression]

        # -------- Builtin names --------
        # Priority 2: Built-in names available in the builtins module.
        if hasattr(builtins, expression):
            return getattr(builtins, expression)

        # -------- Literal detection --------
        # Priority 3: Attempt to evaluate literal expressions safely via AST.
        try:
            node = ast.parse(expression, mode="eval").body
            return self.infer_type_from_node(node)
        except Exception:
            pass

        return None

    def show_popup(self, suggestions):

        if not suggestions:
            self.suggestion_popup.hide()
            return

        # Limit displayed suggestions to avoid overwhelming the user.
        self.suggestion_popup.clear()
        self.suggestion_popup.addItems(sorted(suggestions)[:20])

        self.style_popup()
        
        # Position popup just below the text cursor.
        cursor_rect = self.cursorRect()
        popup_position = self.mapToGlobal(cursor_rect.bottomRight())
        self.suggestion_popup.move(popup_position)

        self.suggestion_popup.setCurrentRow(0)
        self.suggestion_popup.show()

    def update_variable_types(self):
        """
        Parses only the valid code BEFORE the current line
        to infer variable types safely during typing.
        """

        # Reset type cache before re-inference.
        self.variable_types.clear()

        full_source = self.toPlainText()
        cursor = self.textCursor()
        current_block = cursor.blockNumber()

        lines = full_source.splitlines()
        
        # Only parse code before current cursor line.
        # Prevents errors from incomplete current line.
        safe_source = "\n".join(lines[:current_block])

        if not safe_source.strip():
            return

        try:
            tree = ast.parse(safe_source)
        except Exception:
            return  # still invalid → ignore

        # Walk AST to find simple assignment patterns:
        # var_name = <literal> 
        for node in ast.walk(tree):

            if isinstance(node, ast.Assign):

                if len(node.targets) != 1:
                    continue

                target = node.targets[0]

                if not isinstance(target, ast.Name):
                    continue

                var_name = target.id
                value = node.value

                inferred_type = self.infer_type_from_node(value)

                if inferred_type:
                    self.variable_types[var_name] = inferred_type


    # Minimal type inference:
    # Only handles simple literal cases (no deep inference).
    def infer_type_from_node(self, node):
        """
        Returns Python type for simple literals.
        """

        if isinstance(node, ast.List):
            return list

        if isinstance(node, ast.Dict):
            return dict

        if isinstance(node, ast.Tuple):
            return tuple

        if isinstance(node, ast.Set):
            return set

        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                return str
            if isinstance(node.value, int):
                return int
            if isinstance(node.value, float):
                return float
            if isinstance(node.value, bool):
                return bool

        return None
    
    def set_error_color(self, color_hex):
        self.error_color = QColor(color_hex)


# <AI Worker for async requests>
class AIWorker(QObject):
    """
    Worker object that runs the ollama_generate function in a separate thread.
    Emits finished signal with the response string.
    """
    finished = pyqtSignal(str)

    def __init__(self, prompt):
        super().__init__()
        self.prompt = prompt

    @pyqtSlot()
    def run(self):
        response = ollama_generate(self.prompt)
        self.finished.emit(response)


# <UI Pages>

class StartWindow(QWidget):
    """
    Landing page of the application.

    Displays:
    - Welcome message
    - Continue session button (if a session is active)
    - Start new session button
    - Navigation to accessibility and session manager

    This class does NOT manage session state.
    It delegates all state logic to MainWindow.
    """
    def __init__(self, app_controller):
        super().__init__()
        self.setWindowTitle("Python Programming Help App")
        self.setFixedSize(config.PAGE_WIDTH, config.PAGE_HEIGHT)
        self.app_controller = app_controller
        
        # Create widgets.
        self.title_label = QLabel("Welcome to {Program Name Pending}")
        self.title_label.setStyleSheet("font-size: 38px;")

        self.description_label = QLabel(
            "This program will allow you to learn programming anywhere and at any time.\n"
            "You will be given a question and you will have to answer it.\n"
            "You can use the hint button to get a hint,\n"
            " and you can use the send button to have your solution graded.\n"
            "Tip: You can press F11 to toggle fullscreen."
            
        )
        self.description_label.setStyleSheet("font-size: 28px;")

        self.start_session_button = QPushButton()
        self.new_session_button = QPushButton("Start New Session")
        self.new_session_button.hide()

        self.manage_sessions_button = QPushButton("Sessions")
        self.accessibility_button = QPushButton("Accessibility Options")
        
        # Connect button clicks to functions.
        self.start_session_button.clicked.connect(self.app_controller.start_session)
        self.new_session_button.clicked.connect(self.app_controller.start_new_session)
        self.accessibility_button.clicked.connect(self.app_controller.open_accessibility)
        self.manage_sessions_button.clicked.connect(self.app_controller.open_session_manager)

        # Setup Layout.
        self.setLayout(build_vertical_layout([
            self.accessibility_button,
            self.title_label,
            self.description_label,
            self.start_session_button,
            self.new_session_button,
            self.manage_sessions_button
        ]))


class QuestionWindow(QWidget):
    """
    Main learning page.

    Responsibilities:
    - Displays programming questions
    - Sends answers to AI for grading
    - Adjusts user skill level based on grading
    - Selects future questions using weighted difficulty bias
    """
    def __init__(self, app_controller):
        super().__init__()
        self.setWindowTitle("Main Page")
        self.setFixedSize(config.PAGE_WIDTH, config.PAGE_HEIGHT)
        self.app_controller = app_controller

        self.question_list, self.difficulty_levels = read_questions_from_file(config.QUESTION_FILE)
        self.user_skill_level = 0

        self.editor_expanded = False
        
        # Create widgets.
        self.manage_sessions_button = QPushButton("Sessions")
        self.skill_label = QLabel(f"Skill Level: {self.user_skill_level}")
        self.accessibility_button = QPushButton("Accessibility Options")
        self.fullscreen_toggle_button = QPushButton("Editor Focus Mode (F10)")

        self.question_title_label = QLabel("The question:")
        self.question_text_label = QLabel("")
        self.last_question = None
        # Load initial question after all setup
        self.load_new_question()
        self.help_request_input = QLineEdit()
        self.help_request_input.setPlaceholderText("Write here a clarifying question about the question given, and send it alongside your currently written code to AI Helper by pressing 'Get Help' for a better clarification.")

        self.feedback_output_label = QTextEdit()
        # Stacked widget for feedback area (normal text vs loading)
        self.feedback_stack = QStackedWidget()
        self.feedback_output_label = QTextEdit()
        self.feedback_output_label.setReadOnly(True)
        self.feedback_output_label.setText("""The help output will go in this box. You can just press the 'Get Help' button to get more clarification on the question,
but you can also write a clarifying question about the question given into the above box, and send it alongside your currently written code by pressing 'Get Help' for a better hint about how to continue.""")

        # Loading widget with text and indeterminate progress bar
        self.loading_widget = self.create_loading_widget()

        self.feedback_stack.addWidget(self.feedback_output_label)
        self.feedback_stack.addWidget(self.loading_widget)
        self.feedback_stack.setCurrentIndex(0)  # start with normal text

        self.answer_input_field = CodeEditor()
        self.answer_input_field.setPlaceholderText("Enter your answer code in this box. You can press 'Send', to get your answer graded. You can also press 'Get a Different Question' to change the current question.")

        self.error_position_label = QLabel("")
        self.error_position_label.setStyleSheet("color: red;")

        self.defined_identifiers = []
        
        # Real-time syntax validation setup.
        self.validation_timer = QTimer()
        self.validation_timer.setInterval(400)  # milliseconds (debounce delay)
        self.validation_timer.setSingleShot(True)
        self.validation_timer.timeout.connect(self.validate_code)

        self.answer_input_field.textChanged.connect(self.schedule_validation)
        self.answer_input_field.setFocus()

        self.get_help_button = QPushButton("Get Help")


        self.submit_answer_button = QPushButton("Send")
        self.next_question_button = QPushButton("Get a different question")


        # Connect button clicks to functions.
        self.fullscreen_toggle_button.clicked.connect(self.toggle_editor_fullscreen)
        self.next_question_button.clicked.connect(self.load_new_question)
        self.get_help_button.clicked.connect(self.request_ai_help)
        self.submit_answer_button.clicked.connect(self.submit_answer)

        self.accessibility_button.clicked.connect(self.app_controller.open_accessibility)
        self.manage_sessions_button.clicked.connect(self.app_controller.open_session_manager)


        # Setup Layout.
        # =========================
        # Grid Layout Structure
        # =========================
        # Grid layout chosen for flexible multi-row UI structure.
        # Rows 4 and 7 are stretchable (feedback + editor).
        grid = QGridLayout()
        grid.setSpacing(15)
        grid.setContentsMargins(20, 20, 20, 20)

        # ----- Row 1 -----
        grid.addWidget(self.accessibility_button, 0, 0)
        grid.addWidget(self.manage_sessions_button, 0, 1)
        grid.addWidget(self.fullscreen_toggle_button, 0, 2)
        grid.addWidget(self.skill_label, 0, 3)

        # ----- Row 2 -----
        grid.addWidget(self.question_title_label, 1, 0, 1, 4)
        grid.addWidget(self.question_text_label, 2, 0, 1, 4)

        # ----- Row 3 -----
        grid.addWidget(self.help_request_input, 3, 0, 1, 4)

        # ----- Row 4 (Tall Feedback Area) -----
        grid.addWidget(self.feedback_stack, 4, 0, 2, 4)

        # ----- Row 5 -----
        grid.addWidget(self.get_help_button, 6, 0, 1, 4)

        # ----- Row 6 (Tall Answer Input) -----
        grid.addWidget(self.answer_input_field, 7, 0, 2, 4)

        # ----- Row 7 -----
        grid.addWidget(self.error_position_label, 9, 0, 1, 2)
        grid.addWidget(self.submit_answer_button, 9, 2)
        grid.addWidget(self.next_question_button, 9, 3)

        # Stretch behavior
        grid.setRowStretch(4, 1)  # Feedback area grows
        grid.setRowStretch(7, 1)  # Answer area grows
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(3, 1)

        self.setLayout(grid)

        # Store Widgets to hide during full
        # screen coding mode.
        self._non_editor_widgets = [
            self.accessibility_button,
            self.manage_sessions_button,
            self.skill_label,
            self.help_request_input,
            self.feedback_stack,
            self.get_help_button,
            self.error_position_label,
            self.submit_answer_button,
            self.next_question_button
        ]
        
        # Thread and worker references for async AI calls
        self.ai_thread = None
        self.ai_worker = None

    def create_loading_widget(self):
        """Create a widget with a loading message and an indeterminate progress bar."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        label = QLabel("Generating response, please wait...")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress = QProgressBar()
        progress.setRange(0, 0)  # indeterminate mode
        layout.addWidget(label)
        layout.addWidget(progress)
        return widget

    def set_loading_text(self, text):
        """Change the text shown on the loading widget."""
        label = self.loading_widget.findChild(QLabel)
        if label:
            label.setText(text)

    def start_ai_request(self, prompt, callback_slot):
        """
        Start an asynchronous AI request in a background thread.
        Disables buttons, switches to loading widget, and connects the callback.
        """
        # Disable buttons to prevent multiple requests
        self.submit_answer_button.setEnabled(False)
        self.get_help_button.setEnabled(False)
        self.next_question_button.setEnabled(False)

        # Switch to loading widget
        self.feedback_stack.setCurrentIndex(1)

        # Create and start the worker thread
        self.ai_thread = QThread()
        self.ai_worker = AIWorker(prompt)
        self.ai_worker.moveToThread(self.ai_thread)

        self.ai_thread.started.connect(self.ai_worker.run)
        self.ai_worker.finished.connect(callback_slot)
        self.ai_worker.finished.connect(self.ai_thread.quit)
        self.ai_worker.finished.connect(self.ai_worker.deleteLater)
        self.ai_thread.finished.connect(self.ai_thread.deleteLater)

        self.ai_thread.start()

    def on_grading_response(self, response):
        """Handle the AI grading response."""
        # Switch back to normal feedback widget
        self.feedback_stack.setCurrentIndex(0)

        # Re-enable buttons
        self.submit_answer_button.setEnabled(True)
        self.get_help_button.setEnabled(True)
        self.next_question_button.setEnabled(True)

        # Process response
        if not response or response.startswith("Error contacting"):
            self.feedback_output_label.setText(
                "Unable to contact the grading service. Please try again later."
            )
            return

        self.feedback_output_label.setText(response)

        # Try to extract the first line as the grade
        first_line = response.strip().split('\n')[0].strip().rstrip('.').lower()
        if first_line == "correct":
            self.user_skill_level += config.SKILL_INCREMENT
        elif first_line == "incorrect":
            self.user_skill_level -= config.SKILL_INCREMENT
        elif first_line == "partially correct":
            # No change for partially correct
            pass
        else:
            # Fallback: keyword search
            normalized_response = response.lower()
            if "correct" in normalized_response and "partially" not in normalized_response:
                self.user_skill_level += config.SKILL_INCREMENT
            elif "incorrect" in normalized_response:
                self.user_skill_level -= config.SKILL_INCREMENT
            # else partially correct → no change

        self.update_skill_display()
        self.answer_input_field.clear()
        self.load_new_question()
    def on_help_response(self, response):
        """Handle the AI help response."""
        self.feedback_stack.setCurrentIndex(0)

        self.submit_answer_button.setEnabled(True)
        self.get_help_button.setEnabled(True)
        self.next_question_button.setEnabled(True)

        if not response or response.startswith("Error contacting"):
            self.feedback_output_label.setText(
                "Unable to contact the help service. Please try again later."
            )
            return

        self.feedback_output_label.setText(response)
        
    def submit_answer(self):
        """Handle submit button: send answer for grading asynchronously."""
        submitted_answer = self.answer_input_field.toPlainText().strip()
        displayed_question = self.question_text_label.text().strip()

        if not submitted_answer:
            self.feedback_output_label.setText("Please enter an answer before sending.")
            return

        # Construct a robust grading prompt
        prompt = (
            "You are an expert programming tutor grading a student's answer.\n\n"
            f"Question: {displayed_question}\n\n"
            f"Student's Answer:\n{submitted_answer}\n\n"
            "Please provide:\n"
            "1. A grade: either 'Correct', 'Partially Correct', or 'Incorrect'.\n"
            "2. A brief explanation of what is right or wrong.\n"
            "3. If the answer is not fully correct, give a hint that guides the student "
            "toward the right solution without revealing the complete code.\n"
            "Do not include the full correct solution in your response.\n"
            "Format your response clearly, starting with the grade on its own line."
        )

        self.set_loading_text("Grading your answer...")
        self.start_ai_request(prompt, self.on_grading_response)


    def load_new_question(self):
        # Convert user skill into exponential weighting bias.
        # Skill level is centered around 0, but exponential weighting
        # works better when beginners start with negative bias.
        # config.SKILL_BIAS_OFFSET shifts the starting bias so new users
        # are more likely to receive easier (earlier-indexed) questions.
        
        # Convert user skill into exponential weighting bias.
        difficulty_bias = self.user_skill_level + config.SKILL_BIAS_OFFSET
        # Currently filter out questions that are further than
        # config.QUESTION_DIFFICULTY_THRESHOLD from self.user_skill_level.
        threshold = config.QUESTION_DIFFICULTY_THRESHOLD

        filtered_questions = []
        for diff_str, question in zip(self.difficulty_levels, self.question_list):
            try:
                diff = int(diff_str)
            except ValueError:
                continue          # skip malformed difficulty entries
            if abs(self.user_skill_level - diff) < threshold:
                filtered_questions.append(question)

        if not filtered_questions:
            # Fallback: use all questions if filtering yields nothing
            filtered_questions = self.question_list

        # Avoid repeating the last question
        max_attempts = 10
        for _ in range(max_attempts):
            selected_question = weighted_random_choice(filtered_questions, difficulty_bias)
            if selected_question != self.last_question:
                break
        # If after max attempts still same, accept it (pool may be too small)

        self.question_text_label.setText(selected_question)
        self.last_question = selected_question

    def request_ai_help(self):
        """Handle help button: send query to AI for hints asynchronously."""
        question = self.question_text_label.text().strip()
        user_code = self.answer_input_field.toPlainText().strip()
        user_query = self.help_request_input.text().strip()

        if not user_query:
            # Generic hint request
            prompt = (
                "You are a programming tutor. The student is working on this problem:\n\n"
                f"{question}\n\n"
                "They have not asked a specific question yet. Provide a gentle hint that "
                "helps them start thinking about the problem. Do NOT give away the complete "
                "solution. Encourage them to reason step by step. Keep your hint to 2-3 sentences."
            )
        else:
            # Specific help request
            prompt = (
                "You are a programming tutor. The student asks:\n\n"
                f"{user_query}\n\n"
                f"They are solving this problem:\n{question}\n\n"
                f"Here is the code they have written so far:\n{user_code}\n\n"
                "Provide a helpful hint or explanation that addresses their question, "
                "but do NOT write the full solution. Focus on guiding them to discover "
                "the answer themselves. If their code has an error, point out the general "
                "area or concept to review. Keep your response concise and supportive."
            )

        self.set_loading_text("Getting help...")
        self.start_ai_request(prompt, self.on_help_response)

    def toggle_editor_fullscreen(self):
        """
        Toggle editor focus mode.
        Expands code editor to fill window
        without losing content.
        """

        if not self.editor_expanded:
            # Hide everything except editor + toggle button
            for widget in self._non_editor_widgets:
                widget.hide()

            # Make editor dominate layout
            layout = self.layout()
            
            # Increase editor row stretch so it occupies most vertical space.
            layout.setRowStretch(7, 10)
            layout.setRowStretch(4, 0)
            self.answer_input_field.setFocus()
            self.answer_input_field.zoomIn(2)
            

            self.fullscreen_toggle_button.setText("Exit Editor Focus (F10)")
            self.editor_expanded = True

        else:
            # Restore original layout proportions and show all widgets.
            for widget in self._non_editor_widgets:
                widget.show()
            self.answer_input_field.zoomOut(2)
            layout = self.layout()
            layout.setRowStretch(4, 1)
            layout.setRowStretch(7, 1)

            self.fullscreen_toggle_button.setText("Editor Focus Mode (F10)")
            self.editor_expanded = False


    def update_skill_display(self):
        """Clamp skill level and refresh label."""
        self.user_skill_level = max(config.SKILL_MIN,
            min(config.SKILL_MAX, self.user_skill_level))

        self.skill_label.setText(f"Skill Level: {self.user_skill_level}")

    def reset_skill(self):
        """Reset learning progress."""
        self.user_skill_level = 0
        self.update_skill_display()

    def schedule_validation(self):
        """
        Restart validation timer on each text change.
        This prevents validating on every keystroke.
        """
        self.validation_timer.start()

    # Real-time syntax validation entry point.
    # Called after debounce timer expires.
    def validate_code(self):
        """
        Validate Python syntax and highlight ALL detected syntax errors.
        Displays the first error position in the error label.
        Additionally, updates identifier list for later.
        """
        code = self.answer_input_field.toPlainText()
        # Update identifier list for auto-complete
        self.defined_identifiers = self.collect_defined_identifiers(code)

        python_keywords = keyword.kwlist
        builtin_names = dir(builtins)

        # Merge user-defined identifiers, Python keywords,
        # and built-in names into autocomplete pool.
        all_suggestions = sorted(
            set(self.defined_identifiers)
            | set(python_keywords)
            | set(builtin_names)
        )

        self.answer_input_field.set_suggestions(all_suggestions)

        # Do not validate empty or whitespace-only input.
        if not code.strip():
            self.clear_error_highlighting()
            return

        errors = self.collect_syntax_errors(code)

        if not errors:
            self.clear_error_highlighting()
            return

        # Apply highlighting for all detected syntax errors.
        self.highlight_multiple_errors(errors)

        # Show first error location and error name
        first_error = errors[0]
        self.error_position_label.setText(
            f"Error at Line {first_error['line']}, Column {first_error['column']} of type {first_error['error']}."
        )



    def is_incomplete_error(self, error):
        """
        Returns True if error is likely due to incomplete typing.
        Prevents flashing errors while user is mid-statement.
        """
        msg = str(error)
        incomplete_patterns = [
            "unexpected EOF while parsing",
            "expected an indented block",
            "was never closed",
            "invalid syntax",
            "unexpected character after line continuation",
        ]
        return any(pattern in msg for pattern in incomplete_patterns)

    def clear_error_highlighting(self):
        """
        Removes any existing error highlights
        and clearing the error label.
        """
        self.answer_input_field.setExtraSelections([])
        self.error_position_label.setText("")



    # Strategy:
    # Repeatedly parse code and remove lines with errors
    # to detect multiple independent syntax errors.
    def collect_syntax_errors(self, code):
        """
        Collect multiple syntax errors by progressively
        removing detected error lines and re-parsing.
        """
        errors = []
        remaining_code = code

        while remaining_code.strip():
            try:
                ast.parse(remaining_code)
                break
            except (SyntaxError, IndentationError) as error:
                # Make sure the error should be counted
                # and is not just due to code being
                # unfinished.
                if self.is_incomplete_error(error):
                    break

                line = getattr(error, "lineno", None)
                column = getattr(error, "offset", None)

                if line and column:
                    errors.append({"line": line, "column": column, "error":type(error).__name__})

                    # Remove problematic line and retry parsing
                    lines = remaining_code.splitlines()
                    if 0 <= line - 1 < len(lines):
                        lines.pop(line - 1)
                        remaining_code = "\n".join(lines)
                    else:
                        break
                else:
                    break
            
            # Safety guard to prevent infinite loops
            # in pathological parse cases.
            if len(errors) > 20:
                break

        return errors

    # Create visual highlights for each detected syntax error.
    # Single-character errors are highlighted with background color.
    # Multi-character tokens are underlined.
    def highlight_multiple_errors(self, errors):
        """
        Highlights multiple syntax errors at once.
        """
        self.clear_error_highlighting()

        document = self.answer_input_field.document()
        selections = []

        def is_token_char(ch):
            return ch.isalnum() or ch == "_"

        for error in errors:
            line = error["line"]
            column = error["column"]

            block = document.findBlockByNumber(line - 1)
            if not block.isValid():
                continue

            line_text = block.text()
            if not line_text:
                continue

            column = max(1, min(column, len(line_text)))
            index = column - 1

            if index >= len(line_text):
                index = len(line_text) - 1

            # Expand selection to full token for clearer visual feedback.
            start = index
            end = index
            while start > 0 and is_token_char(line_text[start - 1]):
                start -= 1

            while end < len(line_text) - 1 and is_token_char(line_text[end + 1]):
                end += 1

            if not is_token_char(line_text[index]):
                start = index
                end = index

            cursor = self.answer_input_field.textCursor()
            cursor.setPosition(block.position() + start)
            cursor.setPosition(
                block.position() + end + 1,
                cursor.MoveMode.KeepAnchor
            )

            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor

            fmt = selection.format

            error_qcolor = self.answer_input_field.error_color

            if start == end:
                fmt.setBackground(error_qcolor)
                fmt.setForeground(Qt.GlobalColor.white)
            else:
                fmt.setUnderlineStyle(fmt.UnderlineStyle.SpellCheckUnderline)
                fmt.setUnderlineColor(error_qcolor)
                

            selection.format = fmt
            selections.append(selection)
        
        # Apply all highlight selections at once.
        self.answer_input_field.setExtraSelections(selections)

    # Extract names that user defined,
    # so autocomplete can suggest them.
    def collect_defined_identifiers(self, code):
        """
        Collects user-defined identifiers from code:
        - Variables assigned a value
        - Function names
        - Class names

        Returns a sorted list of unique names.
        """
        identifiers = set()

        try:
            tree = ast.parse(code)
        except SyntaxError:
            # If code is invalid, return what we can (empty or previous state)
            return []

        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = (
                    node.targets if isinstance(node, ast.Assign)
                    else [node.target]
                )
                for target in targets:
                    if isinstance(target, ast.Name):
                        identifiers.add(target.id)

            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                identifiers.add(node.name)

        return sorted(identifiers)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F10:
            # Toggle editor fullscreen on F10
            self.toggle_editor_fullscreen()
            return
        super().keyPressEvent(event)
        
    def showEvent(self, event):
        """Ensure editor is truly empty when page is shown, so placeholder appears."""
        super().showEvent(event)
        # If the editor contains no visible text, clear any hidden characters
        if not self.answer_input_field.toPlainText():
            self.answer_input_field.clear()
            # Move cursor to the very beginning (clear already does this, but for safety)
            cursor = self.answer_input_field.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            self.answer_input_field.setTextCursor(cursor)
    




class AccessibilityPage(QWidget):
    def __init__(self, app_controller):
        super().__init__()
        self.app_controller = app_controller

        title_label = QLabel("Accessibility Settings")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Setup text size slider.
        text_size_label = QLabel("Text Size")
        self.text_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.text_size_slider.setRange(config.TEXT_SIZE_MIN, config.TEXT_SIZE_MAX)
        self.text_size_slider.setValue(config.TEXT_SIZE_DEFAULT)
        self.text_size_slider.valueChanged.connect(self.change_text_size)

        # Setup button size slider.
        button_size_label = QLabel("Button Size")
        self.button_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.button_size_slider.setRange(config.BUTTON_SIZE_MIN, config.BUTTON_SIZE_MAX)
        self.button_size_slider.setValue(config.BUTTON_SIZE_DEFAULT)
        self.button_size_slider.valueChanged.connect(self.change_button_size)

        # Setup theme drop-down menu.
        theme_selection_label = QLabel("Theme")
        self.theme_selector = QComboBox()
        self.theme_selector.addItems(config.THEMES.keys())
        self.theme_selector.currentTextChanged.connect(self.change_theme)

        back_button = QPushButton("Back")
        back_button.clicked.connect(self.app_controller.go_back)

        # Setup Layout.
        self.setLayout(build_vertical_layout([
            title_label,
            text_size_label,
            self.text_size_slider,
            button_size_label,
            self.button_size_slider,
            theme_selection_label,
            self.theme_selector,
            "STRETCH",
            back_button
        ]))

    def change_text_size(self, size):
        self.app_controller.build_font_styles(size, "text")
        self.app_controller.apply_combined_styles()

    def change_button_size(self, size):
        self.app_controller.build_font_styles(size, "button")
        self.app_controller.apply_combined_styles()

    def change_theme(self, theme_name):
        self.app_controller.change_theme(theme_name)


class SessionManagerPage(QWidget):
    """
    Allows the user to:
    - Create named sessions
    - Load saved sessions
    - Delete sessions

    Sessions store:
    - Theme settings
    - Text/button sizes
    - Skill level
    """
    def __init__(self, app_controller):
        super().__init__()
        self.app_controller = app_controller

        title_label = QLabel("Session Manager")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.session_name_input = QLineEdit()
        self.session_name_input.setPlaceholderText("Enter session name")

        self.session_list_widget = QListWidget()
        self.refresh_sessions()

        create_session_button = QPushButton("Create Session")
        load_session_button = QPushButton("Load Session")
        delete_session_button = QPushButton("Delete Session")
        explanation_label = QLabel("""
            If you want to create a new session, write the session name in the textbox, and click 'Create Session'.
            If you want to load a session, click the session you want to load, and click "Load Session".
            If you want to delete a session, click the session you want to delete and click "Delete Session".
            """)
        back_button = QPushButton("Back")

        create_session_button.clicked.connect(self.create_session)
        load_session_button.clicked.connect(self.load_session)
        delete_session_button.clicked.connect(self.delete_session)
        back_button.clicked.connect(self.app_controller.go_back)

        # Setup Layout.
        self.setLayout(build_vertical_layout([
            title_label,
            self.session_name_input,
            create_session_button,
            self.session_list_widget,
            load_session_button,
            delete_session_button,
            explanation_label,
            "STRETCH",
            back_button
        ]))

    def refresh_sessions(self):
        self.session_list_widget.clear()
        saved_sessions = load_sessions()
        self.session_list_widget.addItems(saved_sessions.keys())

    def create_session(self):
        session_name = self.session_name_input.text().strip()
        if not session_name:
            QMessageBox.warning(self, "Error", "Session name required")
            return

        saved_sessions = load_sessions()
        saved_sessions[session_name] = self.app_controller.get_current_settings()
        save_sessions(saved_sessions)

        self.refresh_sessions()
        self.session_name_input.clear()

    def load_session(self):
        selected_item = self.session_list_widget.currentItem()
        if not selected_item:
            return

        saved_sessions = load_sessions()
        session_settings = saved_sessions[selected_item.text()]

        self.app_controller.active_session_name = selected_item.text()
        self.app_controller.apply_settings(session_settings)
        self.app_controller.refresh_start_page_buttons()
        # Return to the previous page after loading a session.
        self.app_controller.go_back()

    def delete_session(self):
        selected_item = self.session_list_widget.currentItem()
        if not selected_item:
            return

        saved_sessions = load_sessions()
        del saved_sessions[selected_item.text()]
        save_sessions(saved_sessions)
        self.refresh_sessions()

# <Main Application Controller>

class MainWindow(QMainWindow):
    """
    Central application controller.

    Responsibilities:
    - Manages page navigation using QStackedWidget
    - Stores active session name
    - Coordinates session loading/saving
    - Applies global UI settings
    - Acts as communication bridge between pages
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python Programming Help App")
        self.resize(config.MAIN_WINDOW_WIDTH, config.MAIN_WINDOW_HEIGHT)

        # QStackedWidget used for page navigation without destroying pages.
        self.page_stack = QStackedWidget()
        self.setCentralWidget(self.page_stack)

        self.start_page = StartWindow(self)
        self.question_page = QuestionWindow(self)
        self.accessibility_page = AccessibilityPage(self)
        self.session_manager_page = SessionManagerPage(self)

        # Manual navigation stack used to support Back functionality.
        # Each navigation pushes the current page.
        # go_back() pops and restores the previous page.
        self.navigation_history = []
        self.active_session_name = None

        self.page_stack.addWidget(self.start_page)
        self.page_stack.addWidget(self.question_page)
        self.page_stack.addWidget(self.accessibility_page)
        self.page_stack.addWidget(self.session_manager_page)

        self.page_stack.setCurrentWidget(self.start_page)

        # Centralized UI style state.
        # Initialize default UI theme and styling state.
        # Theme includes stylesheet and error highlight color.
        self.build_font_styles(config.TEXT_SIZE_DEFAULT, "both")
        self._apply_theme("High Contrast")

        self.refresh_start_page_buttons()
        #self.apply_combined_styles()

    def navigate_to(self, page):
        """Push current page to history and switch to new page."""
        self.navigation_history.append(self.page_stack.currentWidget())
        self.page_stack.setCurrentWidget(page)

    def build_font_styles(self, size, where):
        # "text", "button", or "both" sets style respectively.
        if where in ["text", "both"]:
            self.text_stylesheet = f" QWidget {{ font-size: {size}px; }}"
        if where in ["button", "both"]:
            self.button_stylesheet = f" QPushButton {{ font-size: {size}px; }}"

    def _apply_theme(self, theme_name):
        """Set theme, error color, and apply combined styles."""
        self.current_theme_name = theme_name
        theme_data = config.THEMES[theme_name]
        self.current_theme = theme_data["stylesheet"]
        self.current_error_color = theme_data["error_color"]
        self.apply_combined_styles()

    def get_current_settings(self):
        return {
            "text_size": self.text_stylesheet,
            "button_size": self.button_stylesheet,
            "theme_name": self.current_theme_name,
            "skill_level": self.question_page.user_skill_level
        }

    def apply_settings(self, session_settings):
        """Restore UI appearance and learning progress from a saved session."""
        self.text_stylesheet = session_settings["text_size"]
        self.button_stylesheet = session_settings["button_size"]
        self._apply_theme(session_settings["theme_name"])
        if "skill_level" in session_settings:
            self.question_page.user_skill_level = session_settings["skill_level"]
            self.question_page.skill_label.setText(
                f"Skill Level: {self.question_page.user_skill_level}"
            )
            self.question_page.load_new_question()  # Update question for profile
      
    def apply_combined_styles(self):
        """
        Combines theme, text size, and button size styles
        and applies them to the entire application.
        """
        combined = self.current_theme + self.text_stylesheet + self.button_stylesheet
        self.setStyleSheet(combined)

        editor = self.question_page.answer_input_field
        editor.set_error_color(self.current_error_color)

        # Force Qt to re-apply stylesheet immediately.
        # Ensures editor colors update correctly.
        editor.style().unpolish(editor)
        editor.style().polish(editor)
        editor.update()

        # Now refresh highlight
        editor.highlight_current_line()



    def open_accessibility(self):
        self.navigate_to(self.accessibility_page)

    def open_session_manager(self):
        self.navigate_to(self.session_manager_page)
        
    # Returns to the most recently visited page.
    def go_back(self):
        if self.navigation_history:
            self.page_stack.setCurrentWidget(self.navigation_history.pop())

    def start_session(self):
        self.page_stack.setCurrentWidget(self.question_page)
        
    # Reset only learning progress.
    # Accessibility settings remain unchanged.
    def start_new_session(self):
        # Restore user learning progress.
        self.question_page.reset_skill()
        # Get a question for the session
        self.question_page.load_new_question()
        self.active_session_name = None
        self.refresh_start_page_buttons()
        self.page_stack.setCurrentWidget(self.question_page)

    def refresh_start_page_buttons(self):
        has_session = bool(self.active_session_name)
        self.start_page.start_session_button.setText(
            f"Continue ({self.active_session_name})" if has_session
            else "Start New Session"
        )
        self.start_page.new_session_button.setVisible(has_session)

    # Retrieve theme configuration safely,
    # fallback to Light if missing in _apply_theme.
    def change_theme(self, theme_name):
        """Switch theme by name."""
        self._apply_theme(theme_name)

    def toggle_fullscreen(self):
        window = self.window()
        window.showNormal() if window.isFullScreen() else window.showFullScreen()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F11:
            # Toggle window fullscreen on F11
            self.toggle_fullscreen()
            return
        super().keyPressEvent(event)

# Entry point of the application.
# Initializes Qt event loop.
def main():
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()

    # Start event loop and block until application closes.
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
