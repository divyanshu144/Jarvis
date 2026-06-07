"""
PyQt6 HUD overlay — Tony Stark-style floating panel.
Animated arc reactor, waveform bars, conversation history, text input, menu bar icon.
"""

from __future__ import annotations

import math
import random
from typing import Any, Optional

from PyQt6.QtCore import (
    QPoint, QRectF, Qt, QTimer,
    pyqtSignal, pyqtSlot, QObject, QSize,
)
from PyQt6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPainterPath,
    QPen, QRadialGradient, QIcon, QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLineEdit, QPushButton,
    QHBoxLayout, QVBoxLayout, QTextBrowser, QLabel,
    QSystemTrayIcon, QMenu, QFrame, QScrollArea,
)


# ── Status ────────────────────────────────────────────────────────────────────

class Status:
    IDLE      = "Idle"
    LISTENING = "Listening"
    THINKING  = "Thinking"
    SPEAKING  = "Speaking"
    EXECUTING = "Executing"


_STATUS_COLORS = {
    Status.IDLE:      "#2a3a4a",
    Status.LISTENING: "#00d4ff",
    Status.THINKING:  "#f5a623",
    Status.SPEAKING:  "#7ed321",
    Status.EXECUTING: "#bd10e0",
}

_STATUS_GLOW = {
    Status.IDLE:      "#1a2a3a",
    Status.LISTENING: "#003a55",
    Status.THINKING:  "#3a2800",
    Status.SPEAKING:  "#1a3a00",
    Status.EXECUTING: "#2a0035",
}


# ── Bridge ────────────────────────────────────────────────────────────────────

class HUDBridge(QObject):
    status_changed     = pyqtSignal(str)
    transcript_changed = pyqtSignal(str)
    response_changed   = pyqtSignal(str)
    tool_changed       = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()


# ── Arc Reactor ───────────────────────────────────────────────────────────────

class ArcReactor(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(80, 80)
        self._angle  = 0
        self._pulse  = 0.0
        self._dir    = 1
        self._color  = QColor("#00d4ff")
        self._active = False
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(25)

    def set_color(self, c: str) -> None:
        self._color = QColor(c); self.update()

    def set_active(self, v: bool) -> None:
        self._active = v

    def _tick(self) -> None:
        self._angle = (self._angle + 3) % 360
        if self._active:
            self._pulse += 0.04 * self._dir
            if self._pulse >= 1.0: self._dir = -1
            elif self._pulse <= 0.0: self._dir = 1
        else:
            self._pulse = max(0.0, self._pulse - 0.03)
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2

        g = QRadialGradient(cx, cy, 38)
        gl = QColor(self._color); gl.setAlpha(int(40 + 60 * self._pulse))
        g.setColorAt(0, gl); g.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(g); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(2, 2, self.width()-4, self.height()-4))

        r1 = 36
        ring = QColor(self._color); ring.setAlpha(int(60 + 80 * self._pulse))
        p.setPen(QPen(ring, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(cx-r1, cy-r1, r1*2, r1*2))

        for r, spd, span_base, w in [(30, 1, 210, 2.5), (20, -2, 120, 1.5)]:
            arc_c = QColor(self._color); arc_c.setAlpha(200 if r == 30 else 140)
            pen = QPen(arc_c, w); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            span = int(span_base + 60 * self._pulse)
            angle = (self._angle * spd) % 360
            p.drawArc(QRectF(cx-r, cy-r, r*2, r*2), angle*16, span*16)

        hex_r = 10
        hc = QColor(self._color); hc.setAlpha(int(160 + 80 * self._pulse))
        p.setBrush(hc); p.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        for i in range(6):
            a = math.radians(i*60+30)
            x, y = cx + hex_r*math.cos(a), cy + hex_r*math.sin(a)
            path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
        path.closeSubpath(); p.drawPath(path)

        dot = QColor(255, 255, 255, int(200 + 55*self._pulse))
        p.setBrush(dot); p.drawEllipse(QRectF(cx-3, cy-3, 6, 6))


# ── Waveform ──────────────────────────────────────────────────────────────────

class WaveformWidget(QWidget):
    _N = 16; _BW = 4; _GAP = 2; _MH = 36

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(self._N*(self._BW+self._GAP)-self._GAP, self._MH+4)
        self._h = [2.0]*self._N; self._t = [2.0]*self._N
        self._color = QColor("#00d4ff"); self._active = False
        tm = QTimer(self); tm.timeout.connect(self._tick); tm.start(40)

    def set_color(self, c: str) -> None:
        self._color = QColor(c); self.update()

    def set_active(self, v: bool) -> None:
        self._active = v
        if not v: self._t = [2.0]*self._N

    def _tick(self) -> None:
        if self._active:
            for i in range(self._N):
                if random.random() < 0.3:
                    self._t[i] = random.uniform(4, self._MH)
        for i in range(self._N):
            self._h[i] += (self._t[i] - self._h[i]) * 0.35
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        mid = self.height() / 2
        for i, h in enumerate(self._h):
            x = i * (self._BW + self._GAP)
            alpha = int(80 + 160*(h/self._MH)) if self._active else 35
            g = QLinearGradient(x, mid-h/2, x, mid+h/2)
            t = QColor(self._color); t.setAlpha(alpha)
            b = QColor(self._color); b.setAlpha(alpha//3)
            g.setColorAt(0, t); g.setColorAt(0.5, t); g.setColorAt(1, b)
            p.setBrush(g); p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(x, mid-h/2, self._BW, h), 2, 2)


# ── Conversation History ──────────────────────────────────────────────────────

class HistoryView(QTextBrowser):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setOpenLinks(False)
        self.setStyleSheet("""
            QTextBrowser {
                background: transparent;
                border: none;
                color: #c8d8e8;
                font-family: Menlo, Monaco, monospace;
                font-size: 11px;
            }
            QScrollBar:vertical {
                background: #0a0c14;
                width: 4px;
                border-radius: 2px;
            }
            QScrollBar::handle:vertical {
                background: #2a4a6a;
                border-radius: 2px;
            }
        """)
        self._entries: list[tuple[str, str]] = []  # (role, text)

    def add_entry(self, role: str, text: str) -> None:
        self._entries.append((role, text))
        if len(self._entries) > 20:
            self._entries.pop(0)
        self._rebuild()

    def _rebuild(self) -> None:
        html_parts = []
        for role, text in self._entries[-12:]:
            if role == "user":
                color = "#7ab8d8"
                label = "YOU"
            else:
                color = "#00d4ff"
                label = "JARVIS"
            safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html_parts.append(
                f'<span style="color:{color};font-weight:bold">{label}</span> '
                f'<span style="color:#8898a8">{safe}</span><br/>'
            )
        self.setHtml("".join(html_parts))
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


# ── Panel widget (drawn chrome) ───────────────────────────────────────────────

class _ChromePanel(QWidget):
    """Draws the dark background, border, header, scan-line and footer."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._status    = Status.IDLE
        self._tool      = ""
        self._scan_y    = 0.0
        self._scan_a    = 0
        t = QTimer(self)
        t.timeout.connect(self._tick_scan)
        t.start(30)

    def set_status(self, s: str) -> None:
        self._status = s; self.update()

    def set_tool(self, t: str) -> None:
        self._tool = t; self.update()

    def _tick_scan(self) -> None:
        if self._status == Status.THINKING:
            self._scan_y = (self._scan_y + 2.5) % self.height()
            self._scan_a = 80
        else:
            self._scan_a = max(0, self._scan_a - 5)
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H   = self.width(), self.height()
        accent = QColor(_STATUS_COLORS.get(self._status, "#2a3a4a"))

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, W, H), 16, 16)
        p.setClipPath(path)
        p.fillRect(0, 0, W, H, QColor(8, 12, 20, 252))

        gr = QRadialGradient(55, 130, 130)
        gw = QColor(accent); gw.setAlpha(22)
        gr.setColorAt(0, gw); gr.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(0, 0, W, H, gr)

        grid = QColor(accent); grid.setAlpha(7)
        p.setPen(QPen(grid, 0.5))
        for x in range(0, W, 24): p.drawLine(x, 0, x, H)
        for y in range(0, H, 24): p.drawLine(0, y, W, y)

        if self._scan_a > 0:
            sc = QColor(accent); sc.setAlpha(self._scan_a)
            p.setPen(QPen(sc, 1))
            p.drawLine(0, int(self._scan_y), W, int(self._scan_y))

        p.setClipping(False)

        # Border
        bc = QColor(accent); bc.setAlpha(120)
        p.setPen(QPen(bc, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0.75, 0.75, W-1.5, H-1.5), 16, 16)

        # Corner marks
        mk = QColor(accent); mk.setAlpha(200)
        p.setPen(QPen(mk, 2)); cl = 12
        p.drawLine(0, cl, 0, 0); p.drawLine(0, 0, cl, 0)
        p.drawLine(W-cl, 0, W, 0); p.drawLine(W, 0, W, cl)
        p.drawLine(0, H-cl, 0, H); p.drawLine(0, H, cl, H)
        p.drawLine(W-cl, H, W, H); p.drawLine(W, H-cl, W, H)

        # Header bar
        hb = QColor(accent); hb.setAlpha(18)
        p.setBrush(hb); p.setPen(Qt.PenStyle.NoPen)
        hp = QPainterPath()
        hp.addRoundedRect(QRectF(0, 0, W, 36), 16, 16)
        rp = QPainterPath(); rp.addRect(QRectF(0, 20, W, 16))
        p.drawPath(hp.united(rp))

        # Title
        p.setPen(QColor(accent))
        tf = QFont("Helvetica Neue", 11, QFont.Weight.Bold)
        tf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
        p.setFont(tf)
        p.drawText(16, 24, "J.A.R.V.I.S")

        # Status dot + label
        dot = QColor(accent); dot.setAlpha(220)
        p.setBrush(dot); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(W-108, 14, 8, 8))
        sf = QFont("Menlo", 9, QFont.Weight.Medium)
        p.setPen(QColor(accent)); p.setFont(sf)
        p.drawText(W-96, 23, self._status.upper())

        # Header separator
        sep = QColor(accent); sep.setAlpha(50)
        p.setPen(QPen(sep, 1)); p.drawLine(0, 36, W, 36)

        # Left/right column separator
        sep2 = QColor(accent); sep2.setAlpha(28)
        p.setPen(QPen(sep2, 1)); p.drawLine(110, 42, 110, H-52)

        # Tool indicator row
        if self._tool:
            tc = QColor("#bd10e0"); tc.setAlpha(210)
            p.setPen(tc)
            p.setFont(QFont("Menlo", 8))
            p.drawText(116, H-62, f"⚙  {self._tool}")

        # Footer
        fl = QColor(accent); fl.setAlpha(28)
        p.setPen(QPen(fl, 1)); p.drawLine(0, H-48, W, H-48)
        p.setPen(QColor(accent.red(), accent.green(), accent.blue(), 55))
        p.setFont(QFont("Menlo", 7))
        p.drawText(16, H-36, "STARK INDUSTRIES  //  MARK VII  //  ONLINE")


# ── Mini pill (minimised state) ───────────────────────────────────────────────

class MiniPill(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(220, 36)
        self._status = Status.IDLE
        self._color  = QColor("#2a3a4a")

    def set_status(self, s: str) -> None:
        self._status = s
        self._color  = QColor(_STATUS_COLORS.get(s, "#2a3a4a"))
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(8, 12, 20, 240))
        bc = QColor(self._color); bc.setAlpha(180)
        p.setPen(QPen(bc, 1.5))
        p.drawRoundedRect(QRectF(0.75, 0.75, self.width()-1.5, self.height()-1.5), 18, 18)
        dot = QColor(self._color); dot.setAlpha(220)
        p.setBrush(dot); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(12, 13, 10, 10))
        p.setPen(QColor(self._color))
        f = QFont("Helvetica Neue", 10, QFont.Weight.Bold)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        p.setFont(f)
        p.drawText(30, 23, f"J.A.R.V.I.S  ·  {self._status.upper()}")

    def mousePressEvent(self, _e) -> None:
        self.clicked.emit()



# ── FDE Readiness Panel ───────────────────────────────────────────────────────

class _ClickableGapRow(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, gap_id: str, icon: str, name: str, color: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._gap_id = gap_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(20)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 1, 3, 1)
        layout.setSpacing(4)

        ico = QLabel(icon, self)
        ico.setFixedWidth(16)
        ico.setStyleSheet(f"color: {color}; font-size: 11px;")
        layout.addWidget(ico)

        label = QLabel(name, self)
        label.setToolTip(name)
        label.setStyleSheet("color: #c8d8e8; font-family: Helvetica Neue; font-size: 10px;")
        label.setWordWrap(False)
        layout.addWidget(label, 1)

        self.setStyleSheet("""
            QFrame { background: transparent; border-radius: 4px; }
            QFrame:hover { background: rgba(0, 212, 255, 26); }
        """)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._gap_id)
        super().mousePressEvent(event)


class _FDEReadinessPanel(QFrame):
    plan_requested = pyqtSignal(str)
    ask_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._expanded = True
        self._gaps: list[dict[str, Any]] = []
        self._top_gap_id = ""
        self._top_gap_name = ""
        self._top_deliverable = ""
        self._score = 0.0
        self._delta = 0.0
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            QFrame#fdePanel {
                background: rgba(0, 10, 20, 150);
                border: 1px solid rgba(0, 212, 255, 45);
                border-radius: 8px;
            }
            QLabel { background: transparent; }
            QPushButton {
                background: rgba(0, 55, 80, 150);
                color: #00d4ff;
                border: 1px solid rgba(0, 212, 255, 100);
                border-radius: 5px;
                font-size: 9px;
                font-weight: bold;
                padding: 2px 4px;
            }
            QPushButton:hover { background: rgba(0, 95, 130, 190); }
        """)
        self.setObjectName("fdePanel")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 6, 8, 6)
        self._layout.setSpacing(5)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)
        self._toggle = QPushButton("▾", self)
        self._toggle.setFixedSize(18, 16)
        self._toggle.clicked.connect(self._toggle_expanded)
        header.addWidget(self._toggle)

        title = QLabel("FDE READINESS", self)
        title.setStyleSheet("color: #00d4ff; font-family: Helvetica Neue; font-size: 10px; font-weight: bold; letter-spacing: 2px;")
        header.addWidget(title, 1)

        self._score_label = QLabel("0%", self)
        self._score_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._score_label.setStyleSheet("color: #c8d8e8; font-family: Helvetica Neue; font-size: 12px; font-weight: bold;")
        header.addWidget(self._score_label)
        self._layout.addLayout(header)

        self._body = QWidget(self)
        body = QVBoxLayout(self._body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(5)

        self._bar_bg = QFrame(self._body)
        self._bar_bg.setFixedHeight(6)
        self._bar_bg.setStyleSheet("background: rgba(42, 58, 74, 180); border-radius: 3px;")
        self._bar_fill = QFrame(self._bar_bg)
        self._bar_fill.setGeometry(0, 0, 0, 6)
        self._bar_fill.setStyleSheet("background: #f5a623; border-radius: 3px;")
        body.addWidget(self._bar_bg)

        self._delta_label = QLabel("Next review: Sunday", self._body)
        self._delta_label.setStyleSheet("color: #6f8191; font-family: Menlo; font-size: 8px;")
        body.addWidget(self._delta_label)

        self._gap_box = QWidget(self._body)
        self._gap_layout = QVBoxLayout(self._gap_box)
        self._gap_layout.setContentsMargins(0, 0, 0, 0)
        self._gap_layout.setSpacing(1)
        self._gap_scroll = QScrollArea(self._body)
        self._gap_scroll.setWidgetResizable(True)
        self._gap_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._gap_scroll.setFixedHeight(70)
        self._gap_scroll.setWidget(self._gap_box)
        self._gap_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: rgba(10, 12, 20, 180); width: 4px; border-radius: 2px; }
            QScrollBar::handle:vertical { background: #2a4a6a; border-radius: 2px; }
        """)
        body.addWidget(self._gap_scroll)

        week = QLabel("THIS WEEK →", self._body)
        week.setStyleSheet("color: #f5a623; font-family: Helvetica Neue; font-size: 9px; font-weight: bold;")
        body.addWidget(week)

        self._week_gap = QLabel("—", self._body)
        self._week_gap.setStyleSheet("color: #c8d8e8; font-family: Helvetica Neue; font-size: 10px; font-weight: bold;")
        self._week_gap.setWordWrap(False)
        body.addWidget(self._week_gap)

        self._deliverable = QLabel("No active FDE focus yet.", self._body)
        self._deliverable.setStyleSheet("color: #6f8191; font-family: Helvetica Neue; font-size: 8px;")
        self._deliverable.setWordWrap(False)
        body.addWidget(self._deliverable)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(5)
        self._plan_btn = QPushButton("Build Plan", self._body)
        self._plan_btn.clicked.connect(self._request_top_plan)
        buttons.addWidget(self._plan_btn)
        self._ask_btn = QPushButton("Ask JARVIS", self._body)
        self._ask_btn.clicked.connect(self.ask_requested.emit)
        buttons.addWidget(self._ask_btn)
        body.addLayout(buttons)

        self._layout.addWidget(self._body)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_bar()

    def set_data(self, summary: dict[str, Any], gaps: list[dict[str, Any]]) -> None:
        self._score = float(summary.get("overall_score") or 0)
        self._delta = float(summary.get("weekly_delta") or 0)
        self._gaps = gaps
        top = summary.get("top_priority_gap") or {}
        self._top_gap_id = str(top.get("id") or "")
        self._top_gap_name = str(top.get("name") or "—")
        self._top_deliverable = str(top.get("deliverable") or "No deliverable recorded.")

        self._score_label.setText(f"{round(self._score):.0f}%")
        if self._delta:
            self._delta_label.setText(f"{self._delta:+.0f}% this week")
        else:
            self._delta_label.setText("Next review: Sunday")
        self._week_gap.setText(self._top_gap_name)
        self._week_gap.setToolTip(self._top_gap_name)
        self._deliverable.setText(self._truncate(self._top_deliverable, 46))
        self._deliverable.setToolTip(self._top_deliverable)
        self._update_bar()
        self._rebuild_gaps()

    def _update_bar(self) -> None:
        if not hasattr(self, "_bar_fill"):
            return
        width = max(0, int(self._bar_bg.width() * max(0, min(self._score, 100)) / 100))
        self._bar_fill.setGeometry(0, 0, width, 6)
        color = "#d0021b" if self._score < 50 else "#f5a623" if self._score < 75 else "#7ed321"
        self._bar_fill.setStyleSheet(f"background: {color}; border-radius: 3px;")

    def _rebuild_gaps(self) -> None:
        while self._gap_layout.count():
            item = self._gap_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        for gap in self._gaps:
            icon, color = self._status_icon(str(gap.get("status", "")))
            row = _ClickableGapRow(str(gap.get("id", "")), icon, self._truncate(str(gap.get("name", "")), 27), color, self._gap_box)
            row.clicked.connect(self.plan_requested.emit)
            self._gap_layout.addWidget(row)

    def _status_icon(self, status: str) -> tuple[str, str]:
        if status in {"strong", "done"}:
            return "✅", "#7ed321"
        if status in {"in_progress", "in_plan"}:
            return "🔄", "#f5a623"
        if status == "needs_depth":
            return "⚠️", "#ff8c22"
        return "❌", "#d0021b"

    def _toggle_expanded(self) -> None:
        self._expanded = not self._expanded
        self._body.setVisible(self._expanded)
        self._toggle.setText("▾" if self._expanded else "▸")

    def _request_top_plan(self) -> None:
        if self._top_gap_id:
            self.plan_requested.emit(self._top_gap_id)

    def _truncate(self, text: str, length: int) -> str:
        return text if len(text) <= length else text[: max(0, length - 1)] + "…"


class _PlanPopup(QFrame):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame#planPopup { background: rgba(8, 12, 20, 248); border: 1px solid rgba(0, 212, 255, 140); border-radius: 8px; }
            QLabel { color: #00d4ff; font-family: Helvetica Neue; font-size: 10px; font-weight: bold; }
            QTextBrowser { background: rgba(0, 8, 16, 180); color: #c8d8e8; border: none; font-family: Menlo; font-size: 9px; }
            QPushButton { background: transparent; color: #6f8191; border: 1px solid #2a3a4a; border-radius: 4px; font-size: 10px; }
            QPushButton:hover { color: #00d4ff; border-color: #00d4ff; }
        """)
        self.setObjectName("planPopup")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 7, 8, 8)
        layout.setSpacing(5)
        header = QHBoxLayout()
        self._title = QLabel("FDE BUILD PLAN", self)
        header.addWidget(self._title, 1)
        close = QPushButton("×", self)
        close.setFixedSize(22, 18)
        close.clicked.connect(self.hide)
        header.addWidget(close)
        layout.addLayout(header)
        self._text = QTextBrowser(self)
        self._text.setOpenExternalLinks(False)
        layout.addWidget(self._text, 1)
        self.hide()

    def show_plan(self, title: str, plan: str) -> None:
        self._title.setText(title.upper())
        self._text.setPlainText(plan)
        self.show()
        self.raise_()

# ── Main HUD Window ───────────────────────────────────────────────────────────

class HUDOverlay(QWidget):
    trigger_requested = pyqtSignal()
    text_submitted    = pyqtSignal(str)   # user typed a message

    _W = 540
    _H = 620

    def __init__(self, bridge: HUDBridge) -> None:
        super().__init__()
        self._bridge     = bridge
        self._status     = Status.IDLE
        self._minimised  = False
        self._dragging   = False
        self._drag_pos   = QPoint()
        self._fde_gaps: list[dict[str, Any]] = []
        self._fde_gap_lookup: dict[str, str] = {}

        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        self._setup_tray()

    # ── Window setup ──────────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(self._W, self._H)
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - self._W - 20, screen.height() - self._H - 40)

    def _setup_ui(self) -> None:
        # Chrome panel (draws background + border)
        self._chrome = _ChromePanel(self)
        self._chrome.setGeometry(0, 0, self._W, self._H)

        # Arc reactor
        self._arc = ArcReactor(self)
        self._arc.move(15, 80)

        # Waveform
        self._wave = WaveformWidget(self)
        wx = 15 + (80 - self._wave.width()) // 2
        self._wave.move(wx, 172)

        # Conversation history (right column)
        self._history = HistoryView(self)
        self._history.setGeometry(116, 42, self._W - 128, 260)

        # Minimise button
        self._min_btn = QPushButton("—", self)
        self._min_btn.setFixedSize(28, 20)
        self._min_btn.move(self._W - 36, 8)
        self._min_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #4a6a8a;
                border: 1px solid #2a3a4a;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover { color: #00d4ff; border-color: #00d4ff; }
        """)
        self._min_btn.clicked.connect(self._toggle_minimise)

        # Text input bar
        self._input = QLineEdit(self)
        self._input.setGeometry(12, 326, self._W - 100, 32)
        self._input.setPlaceholderText("Type a message or press Cmd+Shift+J to speak…")
        self._input.setStyleSheet("""
            QLineEdit {
                background: rgba(0,10,20,180);
                color: #c8d8e8;
                border: 1px solid #2a3a5a;
                border-radius: 8px;
                padding: 4px 10px;
                font-family: Helvetica Neue;
                font-size: 11px;
            }
            QLineEdit:focus { border-color: #00d4ff; }
        """)
        self._input.returnPressed.connect(self._on_send)

        # Send button
        self._send_btn = QPushButton("Send", self)
        self._send_btn.setGeometry(self._W - 82, 326, 70, 32)
        self._send_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0,80,120,180);
                color: #00d4ff;
                border: 1px solid #00d4ff;
                border-radius: 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background: rgba(0,120,180,220); }
            QPushButton:pressed { background: rgba(0,60,100,220); }
        """)
        self._send_btn.clicked.connect(self._on_send)

        # Mini pill (hidden by default)
        self._pill = MiniPill(self)
        self._pill.hide()
        self._pill.clicked.connect(self._toggle_minimise)

        # FDE readiness panel in the left utility column.
        self._fde_panel = _FDEReadinessPanel(self)
        self._fde_panel.setGeometry(12, 372, self._W - 24, 228)
        self._fde_panel.plan_requested.connect(self._show_fde_plan)
        self._fde_panel.ask_requested.connect(self._ask_fde_today)

        self._plan_popup = _PlanPopup(self)
        self._plan_popup.setGeometry(116, 50, self._W - 128, 270)

        self._fde_timer = QTimer(self)
        self._fde_timer.timeout.connect(self._refresh_fde_panel)
        self._fde_timer.start(60_000)
        self._refresh_fde_panel()

    def _connect_signals(self) -> None:
        self._bridge.status_changed.connect(self._on_status)
        self._bridge.transcript_changed.connect(self._on_transcript)
        self._bridge.response_changed.connect(self._on_response)
        self._bridge.tool_changed.connect(self._on_tool)

    def _setup_tray(self) -> None:
        try:
            # Create a simple colored icon
            px = QPixmap(22, 22)
            px.fill(Qt.GlobalColor.transparent)
            pp = QPainter(px)
            pp.setRenderHint(QPainter.RenderHint.Antialiasing)
            pp.setBrush(QColor("#00d4ff"))
            pp.setPen(Qt.PenStyle.NoPen)
            pp.drawEllipse(2, 2, 18, 18)
            pp.setPen(QColor("white"))
            pp.setFont(QFont("Helvetica Neue", 8, QFont.Weight.Bold))
            pp.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "J")
            pp.end()

            self._tray = QSystemTrayIcon(QIcon(px), self)
            menu = QMenu()
            menu.addAction("Show / Hide", self._toggle_minimise)
            menu.addAction("Trigger JARVIS", self.trigger_requested.emit)
            menu.addSeparator()
            menu.addAction("Quit", QApplication.instance().quit)
            self._tray.setContextMenu(menu)
            self._tray.setToolTip("J.A.R.V.I.S")
            self._tray.activated.connect(self._on_tray_activated)
            self._tray.show()
        except Exception:
            pass  # tray is optional

    # ── Toggle minimise ───────────────────────────────────────────────────────

    def _toggle_minimise(self) -> None:
        self._minimised = not self._minimised
        if self._minimised:
            self._chrome.hide()
            self._arc.hide()
            self._wave.hide()
            self._history.hide()
            self._min_btn.hide()
            self._input.hide()
            self._send_btn.hide()
            self._fde_panel.hide()
            self._plan_popup.hide()
            self._pill.setGeometry(0, 0, 220, 36)
            self._pill.show()
            self.setFixedSize(220, 36)
        else:
            self.setFixedSize(self._W, self._H)
            self._pill.hide()
            self._chrome.show()
            self._arc.show()
            self._wave.show()
            self._history.show()
            self._min_btn.show()
            self._input.show()
            self._send_btn.show()
            self._fde_panel.show()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.raise_()

    # ── FDE panel ──────────────────────────────────────────────────────────────

    def _refresh_fde_panel(self) -> None:
        try:
            from jarvis.core.fde_tracker import FDETracker

            tracker = FDETracker()
            tracker.load_gaps()
            summary = tracker.get_summary()
            data = tracker._read_json()
            gaps = list(data.get("gaps", []))
            self._fde_gaps = gaps
            self._fde_gap_lookup = {str(gap.get("id")): str(gap.get("name", "")) for gap in gaps}
            self._fde_panel.set_data(summary, gaps)
        except Exception as exc:
            self._fde_panel.setToolTip(f"FDE status unavailable: {exc}")

    def _show_fde_plan(self, gap_id: str) -> None:
        gap_name = self._fde_gap_lookup.get(gap_id, gap_id)
        self._plan_popup.show_plan("FDE BUILD PLAN", f"Loading build plan for {gap_name}…")
        QApplication.processEvents()
        try:
            from jarvis.tools.fde_tool import execute as fde_execute

            plan = fde_execute(action="get_build_plan", gap_name=gap_name)
        except Exception as exc:
            plan = f"Could not load FDE build plan: {exc}"
        self._plan_popup.show_plan(f"FDE · {gap_name}", plan)
        self._refresh_fde_panel()

    def _ask_fde_today(self) -> None:
        prompt = "What should I work on for FDE today?"
        self._input.setText(prompt)
        self._input.setFocus(Qt.FocusReason.MouseFocusReason)
        self._input.selectAll()

    # ── Text input ────────────────────────────────────────────────────────────

    def _on_send(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._history.add_entry("user", text)
        self.text_submitted.emit(text)

    # ── Signal handlers ───────────────────────────────────────────────────────

    @pyqtSlot(str)
    def _on_status(self, status: str) -> None:
        self._status = status
        color = _STATUS_COLORS.get(status, "#2a3a4a")
        self._arc.set_color(color)
        self._arc.set_active(status != Status.IDLE)
        self._wave.set_color(color)
        self._wave.set_active(status == Status.LISTENING)
        self._chrome.set_status(status)
        self._pill.set_status(status)

    @pyqtSlot(str)
    def _on_transcript(self, text: str) -> None:
        self._history.add_entry("user", text[:200])

    @pyqtSlot(str)
    def _on_response(self, text: str) -> None:
        self._history.add_entry("jarvis", text[:300])
        self._chrome.set_tool("")

    @pyqtSlot(str)
    def _on_tool(self, text: str) -> None:
        self._chrome.set_tool(text)

    # ── Mouse drag ────────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:
        self._dragging = False

    def mouseDoubleClickEvent(self, event) -> None:
        self.trigger_requested.emit()
