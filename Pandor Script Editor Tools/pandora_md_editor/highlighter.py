# -*- coding: utf-8 -*-
"""
highlighter.py
Pandora® md Editor - Markdown-Syntax-Highlighting fuer QTextEdit
by AKI_SystemDown®
"""

import re
from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont


class MarkdownHighlighter(QSyntaxHighlighter):
    """Einfacher, performanter Markdown-Highlighter im Pandora-Darkred-Stil."""

    def __init__(self, document):
        super().__init__(document)
        self._rules = []
        self._build_formats()
        self._build_rules()

    # ------------------------------------------------------------------
    def _fmt(self, color, bold=False, italic=False, monospace=False):
        f = QTextCharFormat()
        f.setForeground(QColor(color))
        if bold:
            f.setFontWeight(QFont.Weight.Bold)
        if italic:
            f.setFontItalic(True)
        if monospace:
            f.setFontFamily("Consolas")
        return f

    def _build_formats(self):
        self.fmt_h1 = self._fmt("#ff6b5c", bold=True)
        self.fmt_h2 = self._fmt("#ff8b7a", bold=True)
        self.fmt_h3 = self._fmt("#ffab9e", bold=True)
        self.fmt_bold = self._fmt("#ffffff", bold=True)
        self.fmt_italic = self._fmt("#e0a8a8", italic=True)
        self.fmt_code = self._fmt("#ff9d8a", monospace=True)
        self.fmt_codeblock = self._fmt("#d99a6c", monospace=True)
        self.fmt_link = self._fmt("#ff8b7a")
        self.fmt_list = self._fmt("#b32d2d", bold=True)
        self.fmt_quote = self._fmt("#c99")
        self.fmt_hr = self._fmt("#7a1c1c", bold=True)
        self.fmt_image = self._fmt("#e8a87c")

    def _build_rules(self):
        self._rules = [
            (QRegularExpression(r"^######\s.*"), self.fmt_h3),
            (QRegularExpression(r"^#####\s.*"), self.fmt_h3),
            (QRegularExpression(r"^####\s.*"), self.fmt_h3),
            (QRegularExpression(r"^###\s.*"), self.fmt_h2),
            (QRegularExpression(r"^##\s.*"), self.fmt_h2),
            (QRegularExpression(r"^#\s.*"), self.fmt_h1),
            (QRegularExpression(r"\*\*[^*]+\*\*"), self.fmt_bold),
            (QRegularExpression(r"__[^_]+__"), self.fmt_bold),
            (QRegularExpression(r"(?<!\*)\*[^*]+\*(?!\*)"), self.fmt_italic),
            (QRegularExpression(r"(?<!_)_[^_]+_(?!_)"), self.fmt_italic),
            (QRegularExpression(r"`[^`]+`"), self.fmt_code),
            (QRegularExpression(r"!\[[^\]]*\]\([^)]*\)"), self.fmt_image),
            (QRegularExpression(r"\[[^\]]+\]\([^)]*\)"), self.fmt_link),
            (QRegularExpression(r"^\s*[-*+]\s"), self.fmt_list),
            (QRegularExpression(r"^\s*\d+\.\s"), self.fmt_list),
            (QRegularExpression(r"^>.*"), self.fmt_quote),
            (QRegularExpression(r"^(-{3,}|\*{3,}|_{3,})$"), self.fmt_hr),
        ]
        self._fence_re = QRegularExpression(r"^```")

    # ------------------------------------------------------------------
    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)

        # Mehrzeilige Codebloecke ```...```
        self.setCurrentBlockState(0)
        start = 0
        if self.previousBlockState() != 1:
            match = self._fence_re.match(text)
            start = match.capturedStart() if match.hasMatch() else -1
        else:
            start = 0

        if self.previousBlockState() == 1:
            end_match = self._fence_re.match(text)
            if end_match.hasMatch():
                self.setFormat(0, end_match.capturedStart() + 3, self.fmt_codeblock)
                self.setCurrentBlockState(0)
            else:
                self.setFormat(0, len(text), self.fmt_codeblock)
                self.setCurrentBlockState(1)
        else:
            fence_match = self._fence_re.match(text)
            if fence_match.hasMatch() and text.strip() == "```":
                self.setCurrentBlockState(1)
