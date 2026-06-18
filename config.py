"""
Central configuration file for Python Programming Help App.

Contains:
- Window sizes
- Skill system tuning
- Accessibility defaults
- Question selection behavior
- File paths
- AI configuration
- Theme registry
"""

# ==============================
# Window Sizes
# ==============================

MAIN_WINDOW_WIDTH = 500
MAIN_WINDOW_HEIGHT = 400
PAGE_WIDTH = 1500
PAGE_HEIGHT = 800


# ==============================
# Skill System
# ==============================

SKILL_INCREMENT = 5
SKILL_MIN = -20
SKILL_MAX = 60
SKILL_BIAS_OFFSET = -20
QUESTION_DIFFICULTY_THRESHOLD = 100


# ==============================
# Accessibility Defaults
# ==============================

TEXT_SIZE_MIN = 8
TEXT_SIZE_MAX = 30
TEXT_SIZE_DEFAULT = 12

BUTTON_SIZE_MIN = 20
BUTTON_SIZE_MAX = 60
BUTTON_SIZE_DEFAULT = 30


# ==============================
# File Paths
# ==============================

SESSION_STORAGE_FILE = "sessions.txt"
QUESTION_FILE = "questions.txt"


# ==============================
# AI Configuration
# ==============================

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.2:3b"


# ==============================
# Theme Registry
# Add new themes here only.
# ==============================

THEMES = {
    "High Contrast": {
        "stylesheet": """
            QWidget {
                background-color: #000000;
                color: #ffffff;
            }
            QWidget#LineNumberArea {
                background-color: #000000;
                color: #ffff00;
            }
            QPushButton {
                background-color: #ffff00;
                color: #000000;
                font-weight: bold;
                border: 2px solid white;
            }
            QPlainTextEdit#CodeEditor {
                selection-background-color: #3d5a80;
                selection-color: #ffffff;
            }
        """,
        "error_color": "#ffff00"
    },
    "Light": {
        "stylesheet": """
            QWidget {
                background-color: #f0f0f0;
                color: #000000;
            }
            QWidget#LineNumberArea {
                background-color: #e0e0e0;
                color: #444444;
            }
            QPushButton {
                padding: 6px;
            }

            QPlainTextEdit#CodeEditor {
                selection-background-color: #d6ebff;
                selection-color: #000000;
            }
        """,
        "error_color": "#d32f2f"
    },

    "Dark": {
        "stylesheet": """
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QWidget#LineNumberArea {
                background-color: #313335;
                color: #aaaaaa;
            }
            QPushButton {
                background-color: #3c3f41;
                border: 1px solid #555;
                padding: 6px;
            }
            QPlainTextEdit#CodeEditor {
                selection-background-color: #ffff00;
                selection-color: #000000;
            }
        """,
        "error_color": "#ff6b6b"
    },

    "Ocean Blue": {
        "stylesheet": """
            QWidget {
                background-color: #dceeff;
                color: #002b45;
            }
            QWidget#LineNumberArea {
                background-color: #b9ddf5;
                color: #003c66;
            }
            QPushButton {
                background-color: #5fa8d3;
                color: white;
                border-radius: 4px;
                padding: 6px;
            }
            QPlainTextEdit#CodeEditor {
                selection-background-color: #a0d2ff;
                selection-color: #002b45;
            }
        """,
        "error_color": "#ff4d4d"
    },

    "Minimal": {
        "stylesheet": """
            QWidget {
                background-color: #ffffff;
                color: #333333;
            }
            QWidget#LineNumberArea {
                background-color: #f5f5f5;
                color: #777777;
            }
            QPushButton {
                background-color: #e0e0e0;
                border: none;
                padding: 6px;
            }
            QPlainTextEdit#CodeEditor {
                selection-background-color: #eeeeee;
                selection-color: #333333;
            }
        """,
        "error_color": "#cc0000"
    }
}
