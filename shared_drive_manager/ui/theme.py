"""Sentinel dark theme — color constants and global ttk style configuration."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class Theme:
    BG       = "#090E14"
    SIDEBAR  = "#070B10"
    PANEL    = "#101820"
    PANEL_2  = "#13202B"
    PANEL_3  = "#182633"
    BORDER   = "#243849"
    TEXT     = "#E6EEF5"
    MUTED    = "#8DA2B3"
    DIM      = "#526878"
    CYAN     = "#00D5FF"
    GREEN    = "#43FF9B"
    AMBER    = "#FFB020"
    RED      = "#FF4D5E"
    BLUE     = "#4C8DFF"
    ENTRY_BG = "#0C131B"
    SELECT   = "#1E3A4A"

    # Typography
    FONT_BODY    = ("Segoe UI", 9)
    FONT_BODY_SB = ("Segoe UI Semibold", 9)
    FONT_H3      = ("Segoe UI Semibold", 10)
    FONT_H2      = ("Segoe UI Semibold", 11)
    FONT_METRIC  = ("Segoe UI Semibold", 22)
    FONT_CAPTION = ("Segoe UI", 8)
    FONT_MONO    = ("Consolas", 9)

    # Spacing
    PAD_SM = 4
    PAD_MD = 8
    PAD_LG = 16
    PAD_XL = 24


def configure_styles(root: tk.Tk) -> None:
    root.configure(bg=Theme.BG)

    style = ttk.Style(root)
    style.theme_use("clam")

    # Base frames / labels
    style.configure("TFrame", background=Theme.PANEL)
    style.configure("TLabel",
                    background=Theme.PANEL,
                    foreground=Theme.TEXT,
                    font=("Segoe UI", 9))
    style.configure("Muted.TLabel",
                    background=Theme.PANEL,
                    foreground=Theme.MUTED,
                    font=("Segoe UI", 9))

    # Buttons
    style.configure("TButton",
                    background=Theme.PANEL_2,
                    foreground=Theme.TEXT,
                    bordercolor=Theme.BORDER,
                    focuscolor=Theme.PANEL_2,
                    lightcolor=Theme.PANEL_2,
                    darkcolor=Theme.PANEL_2,
                    relief="flat",
                    font=("Segoe UI", 9),
                    padding=(8, 4))
    style.map("TButton",
              background=[("active", Theme.PANEL_3), ("pressed", Theme.PANEL_3)],
              foreground=[("active", Theme.CYAN)])

    style.configure("Accent.TButton",
                    background=Theme.CYAN,
                    foreground=Theme.BG,
                    bordercolor=Theme.CYAN,
                    focuscolor=Theme.CYAN,
                    lightcolor=Theme.CYAN,
                    darkcolor=Theme.CYAN,
                    relief="flat",
                    font=("Segoe UI", 9, "bold"),
                    padding=(8, 4))
    style.map("Accent.TButton",
              background=[("active", "#00B8DC"), ("pressed", "#009EC0")],
              foreground=[("active", Theme.BG)])

    style.configure("Danger.TButton",
                    background=Theme.RED,
                    foreground=Theme.BG,
                    bordercolor=Theme.RED,
                    focuscolor=Theme.RED,
                    lightcolor=Theme.RED,
                    darkcolor=Theme.RED,
                    relief="flat",
                    font=("Segoe UI", 9, "bold"),
                    padding=(8, 4))
    style.map("Danger.TButton",
              background=[("active", "#E03040"), ("pressed", "#C02030")],
              foreground=[("active", Theme.BG)])

    # Entry / Combobox / Spinbox
    style.configure("TEntry",
                    fieldbackground=Theme.ENTRY_BG,
                    foreground=Theme.TEXT,
                    insertcolor=Theme.CYAN,
                    bordercolor=Theme.BORDER,
                    lightcolor=Theme.BORDER,
                    darkcolor=Theme.BORDER,
                    selectbackground=Theme.SELECT,
                    selectforeground=Theme.TEXT)
    style.map("TEntry",
              bordercolor=[("focus", Theme.CYAN)])

    style.configure("TCombobox",
                    fieldbackground=Theme.ENTRY_BG,
                    background=Theme.PANEL_2,
                    foreground=Theme.TEXT,
                    insertcolor=Theme.CYAN,
                    bordercolor=Theme.BORDER,
                    arrowcolor=Theme.MUTED,
                    selectbackground=Theme.SELECT,
                    selectforeground=Theme.TEXT)
    style.map("TCombobox",
              fieldbackground=[("readonly", Theme.ENTRY_BG)],
              foreground=[("readonly", Theme.TEXT)])

    style.configure("TSpinbox",
                    fieldbackground=Theme.ENTRY_BG,
                    foreground=Theme.TEXT,
                    insertcolor=Theme.CYAN,
                    bordercolor=Theme.BORDER,
                    arrowcolor=Theme.MUTED,
                    background=Theme.PANEL_2)

    # Checkbutton
    style.configure("TCheckbutton",
                    background=Theme.PANEL,
                    foreground=Theme.TEXT,
                    indicatorbackground=Theme.ENTRY_BG,
                    indicatorforeground=Theme.CYAN,
                    focuscolor=Theme.PANEL)
    style.map("TCheckbutton",
              background=[("active", Theme.PANEL)],
              indicatorbackground=[("selected", Theme.CYAN)])

    # Scrollbar
    style.configure("Vertical.TScrollbar",
                    background=Theme.PANEL_2,
                    troughcolor=Theme.BG,
                    arrowcolor=Theme.MUTED,
                    bordercolor=Theme.BG,
                    lightcolor=Theme.PANEL_2,
                    darkcolor=Theme.PANEL_2)
    style.map("Vertical.TScrollbar",
              background=[("active", Theme.PANEL_3)])
    style.configure("Horizontal.TScrollbar",
                    background=Theme.PANEL_2,
                    troughcolor=Theme.BG,
                    arrowcolor=Theme.MUTED,
                    bordercolor=Theme.BG,
                    lightcolor=Theme.PANEL_2,
                    darkcolor=Theme.PANEL_2)
    style.map("Horizontal.TScrollbar",
              background=[("active", Theme.PANEL_3)])

    # Treeview
    style.configure("Treeview",
                    background=Theme.PANEL,
                    foreground=Theme.TEXT,
                    fieldbackground=Theme.PANEL,
                    bordercolor=Theme.BORDER,
                    rowheight=22,
                    font=("Segoe UI", 9))
    style.configure("Treeview.Heading",
                    background=Theme.PANEL_2,
                    foreground=Theme.MUTED,
                    bordercolor=Theme.BORDER,
                    relief="flat",
                    font=("Segoe UI", 9, "bold"))
    style.map("Treeview",
              background=[("selected", Theme.SELECT)],
              foreground=[("selected", Theme.CYAN)])
    style.map("Treeview.Heading",
              background=[("active", Theme.PANEL_3)])

    # Progressbar
    style.configure("Horizontal.TProgressbar",
                    background=Theme.CYAN,
                    troughcolor=Theme.PANEL_2,
                    bordercolor=Theme.BORDER,
                    lightcolor=Theme.CYAN,
                    darkcolor=Theme.CYAN)

    # LabelFrame
    style.configure("TLabelframe",
                    background=Theme.PANEL,
                    bordercolor=Theme.BORDER,
                    relief="flat")
    style.configure("TLabelframe.Label",
                    background=Theme.PANEL,
                    foreground=Theme.CYAN,
                    font=("Segoe UI Semibold", 9))

    # Separator
    style.configure("TSeparator", background=Theme.BORDER)

    # Notebook (for nested notebooks in reports_page)
    style.configure("TNotebook",
                    background=Theme.BG,
                    bordercolor=Theme.BORDER,
                    tabmargins=[0, 0, 0, 0])
    style.configure("TNotebook.Tab",
                    background=Theme.PANEL,
                    foreground=Theme.MUTED,
                    bordercolor=Theme.BORDER,
                    padding=[10, 4],
                    font=("Segoe UI", 9))
    style.map("TNotebook.Tab",
              background=[("selected", Theme.PANEL_2)],
              foreground=[("selected", Theme.CYAN)])

    # Panedwindow
    style.configure("TPanedwindow", background=Theme.BG)
    style.configure("Sash", sashrelief="flat", sashthickness=4,
                    background=Theme.BORDER)
