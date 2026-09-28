"""System theme detection and colour palettes for the carrom board game."""

from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import dataclass
from tkinter import ttk


@dataclass(frozen=True)
class Palette:
    name: str
    app_bg: str
    panel_bg: str
    text: str
    muted_text: str
    accent: str
    accent_text: str
    button_bg: str
    button_active: str
    frame_outer: str
    frame_inner: str
    board: str
    board_shade: str
    board_line: str
    pocket: str
    pocket_rim: str
    coin_light: str
    coin_light_edge: str
    coin_dark: str
    coin_dark_edge: str
    queen: str
    queen_edge: str
    striker: str
    striker_edge: str
    aim_line: str
    power_low: str
    power_high: str


LIGHT = Palette(
    name="light",
    app_bg="#f2ece1",
    panel_bg="#e8dfcd",
    text="#2b2118",
    muted_text="#6f6355",
    accent="#a8501e",
    accent_text="#ffffff",
    button_bg="#dccfb6",
    button_active="#cbbb9c",
    frame_outer="#5d3a1a",
    frame_inner="#7b4d23",
    board="#f0d9a7",
    board_shade="#e3c489",
    board_line="#8a6231",
    pocket="#2a1a0c",
    pocket_rim="#c8a86a",
    coin_light="#f7edd6",
    coin_light_edge="#b99b62",
    coin_dark="#4a3520",
    coin_dark_edge="#241a0f",
    queen="#c62828",
    queen_edge="#7f1616",
    striker="#fafafa",
    striker_edge="#8d8d8d",
    aim_line="#1f6f4a",
    power_low="#3f9d5a",
    power_high="#d4452c",
)

DARK = Palette(
    name="dark",
    app_bg="#14161a",
    panel_bg="#1d2026",
    text="#e8eaed",
    muted_text="#9aa0a6",
    accent="#e0873f",
    accent_text="#14161a",
    button_bg="#2a2e36",
    button_active="#3a404a",
    frame_outer="#2c1c10",
    frame_inner="#3d2a18",
    board="#2f3a35",
    board_shade="#273129",
    board_line="#6f8b7c",
    pocket="#05070a",
    pocket_rim="#4e6a5c",
    coin_light="#ece7d8",
    coin_light_edge="#8a9184",
    coin_dark="#1b2128",
    coin_dark_edge="#93a39a",
    queen="#e2544c",
    queen_edge="#8e2a25",
    striker="#cfd6dd",
    striker_edge="#79828c",
    aim_line="#6fd3a2",
    power_low="#57c98a",
    power_high="#ef6a52",
)

PALETTES = {"light": LIGHT, "dark": DARK}


def detect_system_theme() -> str:
    """Best-effort detection of the OS/desktop colour scheme. Returns 'light' or 'dark'."""
    system = platform.system()
    try:
        if system == "Darwin":
            out = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=2,
            )
            return "dark" if "dark" in out.stdout.strip().lower() else "light"

        if system == "Windows":
            import winreg  # type: ignore

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "light" if value else "dark"

        # Linux / BSD: try the XDG desktop portal first, then GNOME settings.
        out = subprocess.run(
            ["gdbus", "call", "--session", "--dest", "org.freedesktop.portal.Desktop",
             "--object-path", "/org/freedesktop/portal/desktop",
             "--method", "org.freedesktop.portal.Settings.Read",
             "org.freedesktop.appearance", "color-scheme"],
            capture_output=True, text=True, timeout=2,
        )
        if out.returncode == 0 and out.stdout.strip():
            # Response looks like: (<<uint32 1>>,)  -> 1 = prefer dark, 2 = prefer light
            digits = "".join(ch for ch in out.stdout if ch.isdigit())
            if digits:
                return "dark" if digits[-1] == "1" else "light"

        for schema, key in (
            ("org.gnome.desktop.interface", "color-scheme"),
            ("org.gnome.desktop.interface", "gtk-theme"),
        ):
            out = subprocess.run(["gsettings", "get", schema, key],
                                 capture_output=True, text=True, timeout=2)
            if out.returncode == 0 and "dark" in out.stdout.strip().lower():
                return "dark"
            if out.returncode == 0 and key == "color-scheme" and "light" in out.stdout.lower():
                return "light"
    except Exception:
        pass

    env = (os.environ.get("GTK_THEME", "") + os.environ.get("QT_STYLE_OVERRIDE", "")).lower()
    if "dark" in env:
        return "dark"
    return "light"


def apply_ttk_theme(root, style: ttk.Style, palette: Palette) -> None:
    """Restyle the ttk widgets so the chrome matches the board."""
    try:
        style.theme_use("clam")
    except Exception:
        pass

    root.configure(background=palette.app_bg)
    style.configure(".", background=palette.app_bg, foreground=palette.text,
                    fieldbackground=palette.panel_bg, bordercolor=palette.panel_bg,
                    focuscolor=palette.accent)
    style.configure("App.TFrame", background=palette.app_bg)
    style.configure("Panel.TFrame", background=palette.panel_bg)
    style.configure("App.TLabel", background=palette.app_bg, foreground=palette.text)
    style.configure("Panel.TLabel", background=palette.panel_bg, foreground=palette.text)
    style.configure("Muted.TLabel", background=palette.panel_bg, foreground=palette.muted_text)
    style.configure("Title.TLabel", background=palette.app_bg, foreground=palette.accent,
                    font=("Helvetica", 17, "bold"))
    style.configure("Score.TLabel", background=palette.panel_bg, foreground=palette.text,
                    font=("Helvetica", 20, "bold"))
    style.configure("Status.TLabel", background=palette.app_bg, foreground=palette.muted_text,
                    font=("Helvetica", 11))
    style.configure("Turn.TLabel", background=palette.panel_bg, foreground=palette.accent,
                    font=("Helvetica", 11, "bold"))
    style.configure("App.TButton", background=palette.button_bg, foreground=palette.text,
                    bordercolor=palette.button_bg, lightcolor=palette.button_bg,
                    darkcolor=palette.button_bg, padding=(12, 6), relief="flat")
    style.map("App.TButton",
              background=[("active", palette.button_active), ("pressed", palette.accent)],
              foreground=[("pressed", palette.accent_text)])
    style.configure("App.TMenubutton", background=palette.button_bg, foreground=palette.text,
                    arrowcolor=palette.text, padding=(10, 5), relief="flat")
    style.map("App.TMenubutton", background=[("active", palette.button_active)])
    style.configure("App.TSeparator", background=palette.muted_text)
