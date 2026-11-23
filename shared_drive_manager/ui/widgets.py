"""Shared custom widget helpers used across all pages."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class LabeledEntry(ttk.Frame):
    """A label/entry pair packed side-by-side."""

    def __init__(
        self,
        parent: tk.Widget,
        label: str,
        width: int = 40,
        **entry_kw,
    ) -> None:
        super().__init__(parent)
        ttk.Label(self, text=label, width=22, anchor="w").pack(side="left")
        self.var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.var, width=width, **entry_kw)
        self.entry.pack(side="left", fill="x", expand=True)

    def get(self) -> str:
        return self.var.get()

    def set(self, value: str) -> None:
        self.var.set(value)


class LabeledSpinbox(ttk.Frame):
    """A label/spinbox pair for integer settings."""

    def __init__(
        self,
        parent: tk.Widget,
        label: str,
        from_: int,
        to: int,
        width: int = 8,
    ) -> None:
        super().__init__(parent)
        ttk.Label(self, text=label, width=22, anchor="w").pack(side="left")
        self.var = tk.IntVar()
        self.spin = ttk.Spinbox(
            self, from_=from_, to=to, textvariable=self.var, width=width
        )
        self.spin.pack(side="left")

    def get(self) -> int:
        return self.var.get()

    def set(self, value: int) -> None:
        self.var.set(value)


class LabeledCheckbutton(ttk.Frame):
    """A checkbutton with a leading label."""

    def __init__(self, parent: tk.Widget, label: str) -> None:
        super().__init__(parent)
        self.var = tk.BooleanVar()
        self.check = ttk.Checkbutton(self, text=label, variable=self.var)
        self.check.pack(side="left")

    def get(self) -> bool:
        return self.var.get()

    def set(self, value: bool) -> None:
        self.var.set(value)

    def configure_state(self, state: str) -> None:
        self.check.configure(state=state)


class ScrolledText(ttk.Frame):
    """Text widget with vertical scrollbar."""

    def __init__(self, parent: tk.Widget, height: int = 10, **text_kw) -> None:
        from shared_drive_manager.ui.theme import Theme
        super().__init__(parent)
        sb = ttk.Scrollbar(self, orient="vertical")
        text_kw.setdefault("wrap", "none")
        text_kw.setdefault("bg", Theme.ENTRY_BG)
        text_kw.setdefault("fg", Theme.TEXT)
        text_kw.setdefault("insertbackground", Theme.CYAN)
        text_kw.setdefault("selectbackground", Theme.SELECT)
        text_kw.setdefault("relief", "flat")
        text_kw.setdefault("font", ("Consolas", 9))
        self.text = tk.Text(
            self,
            height=height,
            yscrollcommand=sb.set,
            **text_kw,
        )
        sb.config(command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

    def append(self, text: str, tag: str | None = None) -> None:
        self.text.configure(state="normal")
        if tag:
            self.text.insert("end", text, tag)
        else:
            self.text.insert("end", text)
        self.text.see("end")
        self.text.configure(state="disabled")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")


class StatusBar(tk.Frame):
    """Three-column dark status bar: [● READY] [engine status] [clock]."""

    def __init__(self, parent: tk.Widget) -> None:
        from shared_drive_manager.ui.theme import Theme
        super().__init__(parent, bg=Theme.PANEL, pady=3)

        self._left_var = tk.StringVar(value="● READY")
        self._center_var = tk.StringVar(value="SCAN ENGINE: IDLE  |  POLICY ENGINE: LOADED  |  DB: CONNECTED")
        self._clock_var = tk.StringVar()

        _font = ("Consolas", 9)

        self._left_label = tk.Label(self, textvariable=self._left_var, bg=Theme.PANEL,
                                    fg=Theme.GREEN, font=_font, anchor="w", padx=8)
        self._left_label.pack(side="left")

        tk.Label(self, textvariable=self._center_var, bg=Theme.PANEL,
                 fg=Theme.MUTED, font=_font, anchor="center").pack(side="left", expand=True)

        self._clock_label = tk.Label(self, textvariable=self._clock_var, bg=Theme.PANEL,
                                     fg=Theme.CYAN, font=_font, anchor="e", padx=8)
        self._clock_label.pack(side="right")

        self._tick()

    def _tick(self) -> None:
        import datetime
        self._clock_var.set(datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))
        self.after(1000, self._tick)

    def set(self, text: str) -> None:
        self._center_var.set(text)

    def set_ready(self, ready: bool) -> None:
        from shared_drive_manager.ui.theme import Theme
        if ready:
            self._left_var.set("● READY")
            self._left_label.configure(fg=Theme.GREEN)
        else:
            self._left_var.set("● BUSY")
            self._left_label.configure(fg=Theme.AMBER)


def section_header(parent: tk.Widget, text: str) -> tk.Label:
    from shared_drive_manager.ui.theme import Theme
    lbl = tk.Label(parent, text=text, bg=Theme.PANEL, fg=Theme.CYAN,
                   font=("Segoe UI Semibold", 10), anchor="w")
    lbl.pack(anchor="w", pady=(10, 2))
    return lbl


def separator(parent: tk.Widget) -> ttk.Separator:
    sep = ttk.Separator(parent, orient="horizontal")
    sep.pack(fill="x", pady=4)
    return sep


def panel(parent: tk.Widget, title: str) -> tuple[tk.Frame, tk.Frame]:
    """Return (outer_border_frame, body_frame) matching the Sentinel bordered-panel pattern."""
    from shared_drive_manager.ui.theme import Theme
    outer = tk.Frame(parent, bg=Theme.BORDER, padx=1, pady=1)
    header = tk.Frame(outer, bg=Theme.PANEL_2)
    header.pack(fill="x")
    tk.Label(header, text="● ● ●", bg=Theme.PANEL_2, fg=Theme.DIM,
             font=("Consolas", 7), anchor="w", padx=6).pack(side="left")
    tk.Label(header, text=title.upper(), bg=Theme.PANEL_2, fg=Theme.CYAN,
             font=("Segoe UI Semibold", 9), anchor="w", padx=4).pack(side="left")
    body = tk.Frame(outer, bg=Theme.PANEL)
    body.pack(fill="both", expand=True)
    return outer, body


# ---------------------------------------------------------------------------
# Canvas chart widgets
# ---------------------------------------------------------------------------

class StatCard(tk.Frame):
    """Bordered card with a large colored metric value and a small caption label."""

    def __init__(
        self,
        parent: tk.Widget,
        label: str,
        value: str = "—",
        color: str | None = None,
    ) -> None:
        from shared_drive_manager.ui.theme import Theme
        self._theme = Theme
        _color = color or Theme.CYAN
        super().__init__(
            parent,
            bg=Theme.PANEL,
            highlightbackground=Theme.BORDER,
            highlightthickness=1,
        )
        self._value_var = tk.StringVar(value=value)
        tk.Label(
            self,
            textvariable=self._value_var,
            bg=Theme.PANEL,
            fg=_color,
            font=Theme.FONT_METRIC,
            anchor="center",
        ).pack(padx=Theme.PAD_LG, pady=(Theme.PAD_MD, 2))
        tk.Label(
            self,
            text=label.upper(),
            bg=Theme.PANEL,
            fg=Theme.MUTED,
            font=Theme.FONT_CAPTION,
            anchor="center",
        ).pack(padx=Theme.PAD_LG, pady=(0, Theme.PAD_MD))

    def update_value(self, text: str) -> None:
        self._value_var.set(text)


class MiniHBarChart(tk.Canvas):
    """Horizontal bar chart drawn on a Canvas from a {label: value} dict."""

    _BAR_H = 14
    _ROW_H = 22
    _LABEL_W = 110
    _VALUE_W = 50
    _PAD = 6

    def __init__(
        self,
        parent: tk.Widget,
        data: dict[str, int | float] | None = None,
        colors: list[str] | None = None,
        width: int = 340,
    ) -> None:
        from shared_drive_manager.ui.theme import Theme
        self._theme = Theme
        rows = max(len(data), 1) if data else 1
        h = rows * self._ROW_H + self._PAD * 2
        super().__init__(parent, bg=Theme.PANEL, highlightthickness=0,
                         width=width, height=h)
        self._width = width
        self._colors = colors or [Theme.CYAN, Theme.BLUE, Theme.GREEN,
                                   Theme.AMBER, Theme.RED]
        if data:
            self._draw(data)

    def update_data(self, data: dict[str, int | float]) -> None:
        rows = max(len(data), 1)
        h = rows * self._ROW_H + self._PAD * 2
        self.configure(height=h)
        self.delete("all")
        self._draw(data)

    def _draw(self, data: dict[str, int | float]) -> None:
        from shared_drive_manager.ui.theme import Theme
        if not data:
            self.create_text(
                self._width // 2, self._PAD + self._ROW_H // 2,
                text="No data", fill=Theme.DIM, font=Theme.FONT_CAPTION,
            )
            return
        max_val = max(data.values()) or 1
        bar_area = self._width - self._LABEL_W - self._VALUE_W - self._PAD * 3
        for i, (label, value) in enumerate(data.items()):
            y_mid = self._PAD + i * self._ROW_H + self._ROW_H // 2
            color = self._colors[i % len(self._colors)]
            # label
            self.create_text(
                self._PAD, y_mid,
                text=label[:18], fill=Theme.MUTED, font=Theme.FONT_CAPTION,
                anchor="w",
            )
            # bar background
            bx = self._LABEL_W + self._PAD
            by1 = y_mid - self._BAR_H // 2
            by2 = y_mid + self._BAR_H // 2
            self.create_rectangle(bx, by1, bx + bar_area, by2,
                                  fill=Theme.PANEL_2, outline="")
            # filled bar
            fill_w = int(bar_area * value / max_val)
            if fill_w > 0:
                self.create_rectangle(bx, by1, bx + fill_w, by2,
                                      fill=color, outline="")
            # value
            vx = bx + bar_area + self._PAD
            self.create_text(
                vx, y_mid,
                text=f"{value:,}", fill=Theme.TEXT, font=Theme.FONT_CAPTION,
                anchor="w",
            )


class DonutChart(tk.Canvas):
    """Proportional arc donut chart with a right-side legend."""

    _SIZE = 140
    _RING_W = 22
    _GAP = 2

    def __init__(
        self,
        parent: tk.Widget,
        data: dict[str, int | float] | None = None,
        colors: list[str] | None = None,
    ) -> None:
        from shared_drive_manager.ui.theme import Theme
        self._theme = Theme
        super().__init__(parent, bg=Theme.PANEL, highlightthickness=0,
                         width=self._SIZE + 140, height=self._SIZE)
        self._colors = colors or [Theme.RED, Theme.AMBER, Theme.BLUE,
                                   Theme.CYAN, Theme.GREEN]
        if data:
            self._draw(data)

    def update_data(
        self,
        data: dict[str, int | float],
        colors: list[str] | None = None,
    ) -> None:
        if colors:
            self._colors = colors
        self.delete("all")
        self._draw(data)

    def _draw(self, data: dict[str, int | float]) -> None:
        from shared_drive_manager.ui.theme import Theme
        total = sum(data.values())
        if total == 0:
            self.create_text(
                self._SIZE // 2, self._SIZE // 2,
                text="No data", fill=Theme.DIM, font=Theme.FONT_CAPTION,
            )
            return
        pad = 10
        x0, y0 = pad, pad
        x1, y1 = self._SIZE - pad, self._SIZE - pad
        start = 90.0
        for i, (label, value) in enumerate(data.items()):
            if value == 0:
                continue
            color = self._colors[i % len(self._colors)]
            extent = 360.0 * value / total - self._GAP
            self.create_arc(
                x0, y0, x1, y1,
                start=start, extent=extent,
                style="arc", outline=color, width=self._RING_W,
            )
            start += 360.0 * value / total
        # legend
        lx = self._SIZE + 8
        for i, (label, value) in enumerate(data.items()):
            color = self._colors[i % len(self._colors)]
            ly = 16 + i * 22
            self.create_oval(lx, ly, lx + 10, ly + 10, fill=color, outline="")
            self.create_text(
                lx + 16, ly + 5,
                text=f"{label}: {value:,}",
                fill=Theme.TEXT, font=Theme.FONT_CAPTION, anchor="w",
            )


class SparkLine(tk.Canvas):
    """Compact time-series sparkline with optional filled area."""

    _MAX_POINTS = 60

    def __init__(
        self,
        parent: tk.Widget,
        points: list[float] | None = None,
        color: str | None = None,
        height: int = 40,
        width: int = 400,
    ) -> None:
        from shared_drive_manager.ui.theme import Theme
        self._theme = Theme
        self._color = color or Theme.CYAN
        super().__init__(parent, bg=Theme.PANEL, highlightthickness=0,
                         height=height, width=width)
        self._points: list[float] = list(points or [])
        self._h = height
        self._width = width
        if self._points:
            self._redraw()

    def append_point(self, value: float) -> None:
        self._points.append(value)
        if len(self._points) > self._MAX_POINTS:
            self._points = self._points[-self._MAX_POINTS:]
        self._redraw()

    def _redraw(self) -> None:
        from shared_drive_manager.ui.theme import Theme
        self.delete("all")
        pts = self._points
        if len(pts) < 2:
            return
        min_v = min(pts)
        max_v = max(pts)
        span = max_v - min_v or 1
        pad = 4
        w = self.winfo_width() or self._width
        h = self.winfo_height() or self._h

        def _x(i: int) -> float:
            return pad + i * (w - pad * 2) / (len(pts) - 1)

        def _y(v: float) -> float:
            return pad + (1 - (v - min_v) / span) * (h - pad * 2)

        coords = [(_x(i), _y(v)) for i, v in enumerate(pts)]
        # filled polygon
        poly = [pad, h - pad]
        for cx, cy in coords:
            poly += [cx, cy]
        poly += [w - pad, h - pad]
        self.create_polygon(poly, fill=self._color, stipple="gray25", outline="")
        # line
        flat = [c for xy in coords for c in xy]
        self.create_line(flat, fill=self._color, width=1, smooth=True)
