"""Temas do Salsicha Launcher — personalização completa.

Presets de destaque + modos de fundo + escala de fonte.
Tudo persiste em config.json sob a chave "theme".
"""
from __future__ import annotations


PRESETS: dict[str, dict] = {
    "salsicha": {"name": "🌭 Salsicha", "accent": "#6abe30", "hover": "#8ce83f",
                 "grad": "#b8ff5e", "glow": "#6abe30"},
    "ambar": {"name": "🟠 Âmbar", "accent": "#ff9d2e", "hover": "#ffbe5c",
              "grad": "#ffe45e", "glow": "#ff9d2e"},
    "violeta": {"name": "🟣 Violeta", "accent": "#9d7bff", "hover": "#c0a8ff",
                "grad": "#ff7bff", "glow": "#9d7bff"},
    "oceano": {"name": "🔵 Oceano", "accent": "#2ea8ff", "hover": "#5cc8ff",
               "grad": "#5effe4", "glow": "#2ea8ff"},
    "sangue": {"name": "🔴 Sangue", "accent": "#ff4d5e", "hover": "#ff7b85",
               "grad": "#ff9d5e", "glow": "#ff4d5e"},
    "menta": {"name": "🩵 Menta", "accent": "#2ee6a8", "hover": "#5ff2c0",
              "grad": "#c0ff5e", "glow": "#2ee6a8"},
    "por-do-sol": {"name": "🌅 Pôr do sol", "accent": "#ff5e3a", "hover": "#ff7b5e",
                   "grad": "#ff2e88", "glow": "#ff5e3a"},
    "cyber": {"name": "🤖 Cyber", "accent": "#00e5ff", "hover": "#5ef2ff",
              "grad": "#ff2ee5", "glow": "#00e5ff"},
}

BG_MODES: dict[str, dict] = {
    "padrao": {"name": "Padrão", "bg": "#23262b", "side": "#1d2024", "card": "#2c3036"},
    "escuro": {"name": "Breu", "bg": "#141518", "side": "#0f1013", "card": "#1d2024"},
    "cinza": {"name": "Grafite", "bg": "#2e3238", "side": "#26292f", "card": "#383d45"},
    "meia-noite": {"name": "🌙 Meia-noite", "bg": "#1a2233", "side": "#141b29", "card": "#232f47"},
    "floresta": {"name": "🌲 Floresta", "bg": "#1c2620", "side": "#151d18", "card": "#26332b"},
    "vinho": {"name": "🍷 Vinho", "bg": "#2a1c22", "side": "#21161b", "card": "#38262e"},
}

FONT_SCALES: dict[str, dict] = {
    "miuda": {"name": "Miúda", "base": 11, "qfont": 8},
    "compacta": {"name": "Compacta", "base": 12, "qfont": 9},
    "normal": {"name": "Normal", "base": 13, "qfont": 10},
    "grande": {"name": "Grande", "base": 15, "qfont": 11},
    "gigante": {"name": "Gigante", "base": 17, "qfont": 12},
}

FONT_FAMILIES: dict[str, dict] = {
    "noto": {"name": "Noto (padrão)", "family": "Noto Sans"},
    "ubuntu": {"name": "Ubuntu", "family": "Ubuntu"},
    "dejavu": {"name": "DejaVu", "family": "DejaVu Sans"},
    "mono": {"name": "Mono gamer", "family": "Noto Sans Mono"},
}

BORDER = "#3a3f47"
TEXT = "#e8eaed"
MUTED = "#9aa0a6"

DEFAULT_THEME = {"preset": "salsicha", "custom": "", "bg_mode": "padrao",
                 "font": "normal", "family": "noto", "anim": True}


def resolve(theme: dict | None) -> dict:
    """Retorna cores finais {accent, hover, grad, glow, bg, side, card, base, qfont, family, anim}."""
    t = dict(DEFAULT_THEME)
    if isinstance(theme, dict):
        t.update({k: v for k, v in theme.items() if k in t})
    p = PRESETS.get(t.get("preset", "salsicha"), PRESETS["salsicha"])
    accent = (t.get("custom") or "").strip() or p["accent"]
    if (t.get("custom") or "").strip():
        hover, grad, glow = accent, accent, accent
    else:
        hover, grad, glow = p["hover"], p.get("grad", p["accent"]), p.get("glow", p["accent"])
    bg = BG_MODES.get(t.get("bg_mode", "padrao"), BG_MODES["padrao"])
    fs = FONT_SCALES.get(t.get("font", "normal"), FONT_SCALES["normal"])
    fam = FONT_FAMILIES.get(t.get("family", "noto"), FONT_FAMILIES["noto"])
    return {"accent": accent, "hover": hover, "grad": grad, "glow": glow,
            "bg": bg["bg"], "side": bg["side"], "card": bg["card"],
            "base": fs["base"], "qfont": fs["qfont"],
            "family": fam["family"], "anim": bool(t.get("anim", True))}


def build_qss(accent: str, hover: str, bg: str, side: str, card: str, base: int,
              grad: str | None = None, glow: str | None = None,
              family: str = "Noto Sans") -> str:
    grad = grad or accent
    glow = glow or accent
    return f"""
QMainWindow, QWidget {{ background: {bg}; color: {TEXT}; font-size: {base}px; font-family: "{family}", sans-serif; }}
#sidebar {{ background: {side}; }}
#sidebar QLabel {{ background: transparent; }}
#sidebar QPushButton {{
  background: transparent; border: none; border-radius: 8px;
  padding: 10px 12px; font-size: 14px; text-align: left;
}}
#sidebar QPushButton:hover {{ background: {card}; color: {hover}; }}
#sidebar QPushButton:checked {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {accent}, stop:1 transparent);
  color: {hover}; font-weight: bold; border-left: 3px solid {glow};
}}
QGroupBox {{
  background: {card}; border: 1px solid {BORDER}; border-radius: 10px;
  margin-top: 14px; padding-top: 10px; font-weight: bold;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {accent}; }}
QLabel {{ background: transparent; }}
QLabel[class="muted"] {{ color: {MUTED}; font-size: 12px; }}
QLabel[class="trust"] {{ color: #8fce8f; font-size: 12px; }}
QLineEdit, QComboBox, QSpinBox, QListWidget {{
  background: #1a1d21; border: 1px solid {BORDER}; border-radius: 8px; padding: 7px 10px;
}}
QListWidget::item {{ padding: 6px; border-radius: 8px; }}
QListWidget::item:hover {{ background: {card}; }}
QListWidget::item:selected {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {accent}, stop:1 {card}); }}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {accent}; }}
QPushButton {{
  background: #33373e; border: 1px solid {BORDER}; border-radius: 8px; padding: 9px 14px;
}}
QPushButton:hover {{ border: 1px solid {accent}; color: {hover}; }}
QPushButton[class="play"] {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {accent}, stop:1 {grad});
  color: #10140c; font-weight: bold; font-size: 20px;
  border: none; border-radius: 12px; padding: 14px;
}}
QPushButton[class="play"]:hover {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {hover}, stop:1 {grad});
}}
QPushButton[class="preset"] {{ border: 2px solid {BORDER}; border-radius: 8px; padding: 10px 6px; }}
QPushButton[class="preset"]:checked {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {accent}, stop:1 {grad});
  color: #10140c; font-weight: bold; border: 2px solid {glow};
}}
QTextEdit {{
  background: #141518; border: 1px solid {BORDER}; border-radius: 8px;
  font-family: "Noto Sans Mono", "DejaVu Sans Mono", monospace; font-size: 12px;
}}
QProgressBar {{ border: 1px solid {BORDER}; border-radius: 6px; background: #141518; height: 10px; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {accent}, stop:1 {grad}); border-radius: 5px; }}
"""
