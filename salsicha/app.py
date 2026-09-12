"""Salsicha Launcher — UI estilo SKLauncher (sidebar + telas).

Tela Jogar: nick, versão e botão JOGAR gigante.
Todo o resto (modpacks, servidores, contas, config) vive na sidebar.
Sem QScrollArea (foi a causa do bug do fundo branco no Lunar).
"""
from __future__ import annotations

import threading
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QObject, QSize, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit,
    QProgressBar, QSpinBox, QMessageBox, QCheckBox, QGroupBox,
    QListWidget, QListWidgetItem, QStackedWidget, QButtonGroup,
)

from . import APP_NAME
from .auth import (
    offline_options, get_login_url, complete_login,
    extract_code_from_url, save_account, load_accounts, microsoft_options,
    refresh_login, validate_profile, device_start, device_poll, device_complete,
    device_refresh_login, DevicePending, DeviceDeclined, DeviceExpired, XboxError,
    load_local_accounts, save_local_account, remove_local_account,
)

LOCAL_MODE = "Conta Local"
MS_MODE = "Microsoft"


def normalize_mode(mode: str) -> str:
    """Migra o antigo 'Offline' para 'Conta Local'. Microsoft segue igual."""
    m = (mode or "").strip()
    if m == MS_MODE:
        return MS_MODE
    return LOCAL_MODE
from .installer import (
    list_versions, latest_release, install_with_loader, launch,
    list_loaders, loader_versions,
)
from .java_utils import find_java, java_version, get_minecraft_dir
from .modrinth import PERF_MODS, FORGE_PERF_MODS, perf_mods_for, ensure_mods, latest_compat_file, download_url_to, check_mod_updates, compat_status
from .servers import DEFAULT_SERVERS, all_servers, add_custom, remove_custom, ping as ping_server
from .social import list_shots, shots_dir, fetch_avatar
from .discover import (
    search_projects, latest_mrpack_version_url, install_mrpack_from_url,
    download_icon,
)
from .config import load as load_cfg, save as save_cfg
from .netfix import force_ipv4
from .instances import game_dir_for, ensure_instance, modpack_dir
from .themes import PRESETS, BG_MODES, FONT_SCALES, FONT_FAMILIES, DEFAULT_THEME, resolve, build_qss

force_ipv4()

ACCENT = "#6abe30"
ACCENT_HOVER = "#7cd747"
BG = "#23262b"
SIDE = "#1d2024"
CARD = "#2c3036"
BORDER = "#3a3f47"
TEXT = "#e8eaed"
MUTED = "#9aa0a6"


def current_qss() -> str:
    """QSS do tema salvo em config.json (padrão Salsicha)."""
    try:
        _c = resolve(load_cfg().get("theme"))
    except Exception:
        _c = resolve(None)
    return build_qss(_c["accent"], _c["hover"], _c["bg"], _c["side"],
                     _c["card"], _c["base"], _c["grad"], _c["glow"], _c["family"])


QSS = current_qss()


class Signals(QObject):
    log = Signal(str)
    progress = Signal(int)
    max = Signal(int)
    status = Signal(str)
    quit_app = Signal()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME + " 🌭")
        self.resize(960, 620)
        self.signals = Signals()
        self._ms_state: dict = {}
        self._mp_hits: list = []
        self._mp_icons: dict = {}
        self._mp_mc: str = ""
        self._last_target_mc: str = ""
        self.modpack_launch: str = ""
        self.modpack_name: str = ""
        self._updates: list = []
        self._pulse_phase: float = 0.0
        self._pulse_timer: QTimer | None = None
        self._play_shadow = None
        self._build_ui()
        self.signals.log.connect(self._log)
        self.signals.progress.connect(self._bar.setValue)
        self.signals.max.connect(self._bar.setMaximum)
        self.signals.status.connect(lambda s: self.statusBar().showMessage(s))
        self.signals.quit_app.connect(self._quit_for_game)
        self._load_versions()
        self._prefill_account()
        self._refresh_accounts()
        try:
            self._refresh_server_label()
        except Exception:
            pass
        if self._get_installations():
            self._refresh_inst_combo()
            self._refresh_inst_list()
        try:
            self._refresh_avatar()
        except Exception:
            pass
        self._setup_anims()
        try:
            QTimer.singleShot(400, self._maybe_wizard)
            QTimer.singleShot(800, self._refresh_news)
        except Exception:
            pass

    # ---------- animações ----------
    def _goto_page(self, idx: int):
        """Troca de página (instantânea: opacity-fade conflita com o glow no Qt)."""
        try:
            self.pages.setCurrentIndex(idx)
        except Exception:
            pass

    def _setup_anims(self):
        """Liga/desliga pulsar do JOGAR conforme o tema (chamado no início e ao trocar)."""
        try:
            cur = resolve(self._theme_cfg())
            on = bool(cur.get("anim", True))
            if self._pulse_timer is not None:
                try:
                    self._pulse_timer.stop()
                except Exception:
                    pass
                self._pulse_timer = None
            if not on:
                try:
                    if hasattr(self, "b_play"):
                        self.b_play.setGraphicsEffect(None)
                except Exception:
                    pass
                self._play_shadow = None
                return
            if not hasattr(self, "b_play"):
                return
            from PySide6.QtWidgets import QGraphicsDropShadowEffect
            from PySide6.QtGui import QColor
            sh = QGraphicsDropShadowEffect(self.b_play)
            sh.setColor(QColor(cur["glow"]))
            sh.setBlurRadius(22)
            sh.setOffset(0, 0)
            self.b_play.setGraphicsEffect(sh)
            self._play_shadow = sh
            t = QTimer(self)
            t.timeout.connect(self._pulse_tick)
            t.start(70)
            self._pulse_timer = t
        except Exception:
            pass

    def _pulse_tick(self):
        try:
            import math
            if self._play_shadow is None:
                return
            self._pulse_phase += 0.18
            k = (math.sin(self._pulse_phase) + 1.0) / 2.0  # 0..1
            self._play_shadow.setBlurRadius(14 + int(20 * k))
        except Exception:
            pass

    # ---------- layout ----------
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ----- sidebar -----
        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(180)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(10, 14, 10, 14)
        sl.setSpacing(4)
        logo = QLabel("🌭 Salsicha")
        logo.setStyleSheet("font-size: 18px; font-weight: bold; background: transparent;")
        sl.addWidget(logo)
        sub = QLabel("minecraft fácil")
        sub.setProperty("class", "muted")
        sl.addWidget(sub)
        sl.addSpacing(10)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: list = []
        for i, (label, _key) in enumerate([
            ("▶  Jogar", "play"),
            ("🗂  Versões", "versions"),
            ("🛒  Loja", "store"),
            ("🌐  Servidores", "servers"),
            ("🖼  Fotos", "shots"),
            ("👤  Contas", "accounts"),
            ("🎨  Visual", "visual"),
            ("⚙️  Config", "settings"),
        ]):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _c, idx=i: self._goto_page(idx))
            self.nav_group.addButton(b, i)
            sl.addWidget(b)
            self.nav_buttons.append(b)
        self.nav_buttons[0].setChecked(True)
        self.nav_buttons[1].clicked.connect(lambda: self._versions_opened())

        sl.addStretch(1)
        self.side_avatar = QLabel()
        self.side_avatar.setFixedSize(36, 36)
        self.side_avatar.setScaledContents(True)
        sl.addWidget(self.side_avatar)
        self.side_account = QLabel("Offline")
        self.side_account.setProperty("class", "muted")
        self.side_account.setWordWrap(True)
        sl.addWidget(self.side_account)
        ver = QLabel("v0.2 • local")
        ver.setProperty("class", "muted")
        sl.addWidget(ver)
        lay.addWidget(side)

        # ----- páginas -----
        main = QWidget()
        ml = QVBoxLayout(main)
        ml.setContentsMargins(18, 14, 18, 14)
        ml.setSpacing(8)
        self.pages = QStackedWidget()
        ml.addWidget(self.pages, 1)
        self.pages.addWidget(self._page_play())
        self.pages.addWidget(self._page_versions())
        self.pages.addWidget(self._page_modpacks())
        self.pages.addWidget(self._page_servers())
        self.pages.addWidget(self._page_shots())
        self.pages.addWidget(self._page_accounts())
        self.pages.addWidget(self._page_visual())
        self.pages.addWidget(self._page_settings())
        lay.addWidget(main, 1)

    # ----- página: jogar -----
    def _page_play(self) -> QWidget:
        p = QWidget()
        l = QVBoxLayout(p)
        l.setContentsMargins(4, 4, 4, 4)
        l.setSpacing(10)

        head = QHBoxLayout()
        self.play_avatar = QLabel()
        self.play_avatar.setFixedSize(56, 56)
        self.play_avatar.setScaledContents(True)
        head.addWidget(self.play_avatar)
        hcol = QVBoxLayout()
        t = QLabel("Pronto para jogar?")
        t.setStyleSheet("font-size: 22px; font-weight: bold; background: transparent;")
        hcol.addWidget(t)
        self.play_account = QLabel("")
        self.play_account.setProperty("class", "muted")
        hcol.addWidget(self.play_account)
        head.addLayout(hcol, 1)
        l.addLayout(head)

        g = QGroupBox("Quem vai jogar")
        f = QVBoxLayout(g)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Nick:"))
        self.user = QLineEdit()
        self.user.setPlaceholderText("Seu nick (3–16 letras)")
        self.user.setMaxLength(16)
        self.user.textChanged.connect(lambda _: self._refresh_account_labels())
        self.user.textChanged.connect(lambda _: self._save_identity())
        self.user.editingFinished.connect(lambda: self._refresh_avatar())
        row1.addWidget(self.user, 3)
        self.mode = QComboBox()
        self.mode.addItems([LOCAL_MODE, MS_MODE])
        self.mode.currentTextChanged.connect(self._refresh_play_buttons)
        self.mode.currentTextChanged.connect(lambda _: self._refresh_account_labels())
        self.mode.currentTextChanged.connect(lambda _: self._save_identity())
        row1.addWidget(self.mode, 1)
        f.addLayout(row1)
        l.addWidget(g)

        # versão única estilo TLauncher: escolhe e joga
        g2 = QGroupBox("Versão para jogar")
        f2 = QVBoxLayout(g2)
        row_v = QHBoxLayout()
        self.installation = QComboBox()
        self.installation.setMinimumHeight(34)
        self.installation.currentIndexChanged.connect(lambda _: self._refresh_inst_info())
        row_v.addWidget(self.installation, 1)
        self.b_manage_versions = QPushButton("🗂")
        self.b_manage_versions.setToolTip("Gerenciar versões")
        self.b_manage_versions.setFixedWidth(44)
        self.b_manage_versions.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        row_v.addWidget(self.b_manage_versions)
        f2.addLayout(row_v)
        self.inst_info = QLabel("carregando versões…")
        self.inst_info.setProperty("class", "muted")
        self.inst_info.setWordWrap(True)
        f2.addWidget(self.inst_info)
        l.addWidget(g2)

        self.play_server_label = QLabel("Mundo local (troque em 🌐 Servidores)")
        self.play_server_label.setProperty("class", "muted")
        self.play_server_label.setWordWrap(True)
        l.addWidget(self.play_server_label)

        self.b_play = QPushButton("▶ JOGAR")
        self.b_play.setMinimumHeight(64)
        self.b_play.setCursor(Qt.PointingHandCursor)
        self.b_play.setProperty("class", "play")
        self.b_play.clicked.connect(self._play_current)
        l.addWidget(self.b_play)

        self._bar = QProgressBar()
        self._bar.setMaximum(100)
        self._bar.setValue(0)
        l.addWidget(self._bar)

        self.show_console = QCheckBox("ver console")
        self.show_console.setChecked(False)
        self.show_console.toggled.connect(lambda c: self.logview.setVisible(bool(c)))
        l.addWidget(self.show_console)
        self.logview = QTextEdit()
        self.logview.setReadOnly(True)
        self.logview.setPlaceholderText("O progresso aparece aqui…")
        self.logview.setVisible(False)
        self.logview.setMinimumHeight(120)
        l.addWidget(self.logview, 1)

        g3 = QGroupBox("📰 Novidades do Minecraft")
        f3 = QVBoxLayout(g3)
        self.news_label = QLabel("buscando novidades…")
        self.news_label.setProperty("class", "muted")
        self.news_label.setWordWrap(True)
        f3.addWidget(self.news_label)
        row_n = QHBoxLayout()
        self.b_news = QPushButton("↻ Atualizar")
        self.b_news.clicked.connect(self._refresh_news)
        row_n.addWidget(self.b_news)
        self.b_articles = QPushButton("🌐 Artigos oficiais")
        self.b_articles.clicked.connect(
            lambda: webbrowser.open("https://www.minecraft.net/en-us/articles"))
        row_n.addWidget(self.b_articles)
        f3.addLayout(row_n)
        l.addWidget(g3)
        l.addStretch(1)  # mola: impede o Qt de esticar os widgets (bug visual)
        return p

    def _refresh_news(self):
        try:
            self.news_label.setText("buscando novidades…")
        except Exception:
            pass

        def work():
            try:
                from .news import fetch_news
                n = fetch_news()
                lines = [f"Estável <b>{n['release']}</b> • snapshot <b>{n['snapshot']}</b>"]
                for vid, vtype, date in (n.get("recent") or [])[:4]:
                    tag = "🧪" if vtype == "snapshot" else "📦"
                    lines.append(f"{tag} {vid} <font color='#9aa0a6'>({date})</font>")
                if n.get("stale"):
                    lines.append("<font color='#9aa0a6'>offline — último cache</font>")
                self.signals.log.emit("__NEWS__:" + "<br>".join(lines))
            except Exception as e:
                self.signals.log.emit(f"__NEWS__:⚠ sem novidades ({e})")
        threading.Thread(target=work, daemon=True).start()

    # ----- página: versões (lista única estilo TLauncher) -----
    def _page_versions(self) -> QWidget:
        p = QWidget()
        l = QVBoxLayout(p)
        l.setContentsMargins(4, 4, 4, 4)
        l.setSpacing(8)
        t = QLabel("🗂 Versões")
        t.setStyleSheet("font-size: 20px; font-weight: bold; background: transparent;")
        l.addWidget(t)
        hint = QLabel("Cada versão guarda tudo: Minecraft, loader, mods e servidor. Para jogar, é só escolher na tela ▶ Jogar.")
        hint.setProperty("class", "muted")
        hint.setWordWrap(True)
        l.addWidget(hint)

        g = QGroupBox("Suas versões")
        f = QVBoxLayout(g)
        self.inst_list = QListWidget()
        self.inst_list.setMaximumHeight(120)
        self.inst_list.currentRowChanged.connect(lambda r: self._edit_installation(r))
        f.addWidget(self.inst_list)
        row_btns = QHBoxLayout()
        self.b_inst_new = QPushButton("＋ Nova")
        self.b_inst_new.clicked.connect(self._new_installation)
        row_btns.addWidget(self.b_inst_new)
        self.b_inst_del = QPushButton("🗑 Apagar")
        self.b_inst_del.clicked.connect(self._delete_installation)
        row_btns.addWidget(self.b_inst_del)
        f.addLayout(row_btns)
        l.addWidget(g)

        g2 = QGroupBox("Editar versão")
        f2 = QVBoxLayout(g2)
        row_n = QHBoxLayout()
        row_n.addWidget(QLabel("Nome:"))
        self.e_name = QLineEdit()
        self.e_name.setPlaceholderText("Ex.: Fabric + FPS")
        row_n.addWidget(self.e_name, 1)
        f2.addLayout(row_n)

        row_i = QHBoxLayout()
        row_i.addWidget(QLabel("Ícone:"))
        self.e_icon = QLabel()
        self.e_icon.setFixedSize(40, 40)
        self.e_icon.setScaledContents(True)
        row_i.addWidget(self.e_icon)
        self.b_icon_pick = QPushButton("🖼 Escolher…")
        self.b_icon_pick.clicked.connect(self._pick_inst_icon)
        row_i.addWidget(self.b_icon_pick)
        self.b_block_pick = QPushButton("⛏ Blocos…")
        self.b_block_pick.setToolTip("Ícones de blocos do Minecraft")
        self.b_block_pick.clicked.connect(self._pick_block_icon)
        row_i.addWidget(self.b_block_pick)
        self.b_icon_clear = QPushButton("✕")
        self.b_icon_clear.setToolTip("Tirar o ícone")
        self.b_icon_clear.setFixedWidth(36)
        self.b_icon_clear.clicked.connect(self._clear_inst_icon)
        row_i.addWidget(self.b_icon_clear)
        row_i.addStretch(1)
        f2.addLayout(row_i)
        self._editing_icon: str = ""

        row_v = QHBoxLayout()
        row_v.addWidget(QLabel("MC:"))
        self.version = QComboBox()
        self.version.setPlaceholderText("carregando…")
        self.version.setMinimumWidth(140)
        self.version.currentTextChanged.connect(lambda _: self._load_loader_versions())
        row_v.addWidget(self.version, 2)
        row_v.addWidget(QLabel("Loader:"))
        self.loader = QComboBox()
        try:
            self.loader.addItems(list_loaders())
        except Exception:
            self.loader.addItems(["vanilla", "fabric", "forge", "neoforge", "quilt"])
        self.loader.currentTextChanged.connect(lambda _: self._load_loader_versions())
        row_v.addWidget(self.loader, 1)
        self.loader_ver = QComboBox()
        self.loader_ver.setEditable(True)
        self.loader_ver.setPlaceholderText("latest")
        row_v.addWidget(self.loader_ver, 1)
        f2.addLayout(row_v)

        self.e_mods_lbl = QLabel("Mods de FPS (só os compatíveis ficam ativos):")
        self.e_mods_lbl.setProperty("class", "muted")
        f2.addWidget(self.e_mods_lbl)
        self.e_mod_checks: dict = {}
        self._mod_tips: dict = {}
        er1 = QHBoxLayout()
        er2 = QHBoxLayout()
        er3 = QHBoxLayout()
        _all_perf = list(PERF_MODS.items()) + [(s, v) for s, v in FORGE_PERF_MODS.items()]
        for i, (slug, (pretty, _desc)) in enumerate(_all_perf):
            cb = QCheckBox(pretty)
            tip = _desc + (" (Forge)" if slug in FORGE_PERF_MODS else "")
            cb.setToolTip(tip)
            self._mod_tips[slug] = tip
            self.e_mod_checks[slug] = cb
            (er1 if i < 4 else (er2 if i < 7 else er3)).addWidget(cb)
        er1.addStretch(1)
        er2.addStretch(1)
        er3.addStretch(1)
        f2.addLayout(er1)
        f2.addLayout(er2)
        f2.addLayout(er3)

        row_s = QHBoxLayout()
        row_s.addWidget(QLabel("Servidor:"))
        self.e_server = QComboBox()
        self.e_server.addItem("Mundo local", "")
        for s in DEFAULT_SERVERS:
            self.e_server.addItem(f"{s['name']} — {s['host']}", s["host"])
        row_s.addWidget(self.e_server, 1)
        self.e_direct = QCheckBox("entrar direto")
        row_s.addWidget(self.e_direct)
        f2.addLayout(row_s)

        g3 = QGroupBox("Conteúdo desta versão (mods, texturas, shaders)")
        f3 = QVBoxLayout(g3)
        self.content_list = QListWidget()
        self.content_list.setMaximumHeight(90)
        f3.addWidget(self.content_list)
        row_c = QHBoxLayout()
        self.b_content_store = QPushButton("＋ Loja")
        self.b_content_store.setToolTip("Buscar na loja para esta versão")
        self.b_content_store.clicked.connect(lambda: self.pages.setCurrentIndex(2))
        row_c.addWidget(self.b_content_store)
        self.b_content_del = QPushButton("🗑 Tirar")
        self.b_content_del.clicked.connect(self._remove_content)
        row_c.addWidget(self.b_content_del)
        f3.addLayout(row_c)
        f2.addWidget(g3)

        self.b_inst_save = QPushButton("💾 Salvar versão")
        self.b_inst_save.setProperty("class", "play")
        self.b_inst_save.clicked.connect(self._save_installation)
        f2.addWidget(self.b_inst_save)
        l.addWidget(g2)
        l.addStretch(1)
        self._editing_id: str | None = None
        return p

    # ----- página: loja (mods, texturas, shaders, modpacks) -----
    def _page_modpacks(self) -> QWidget:
        p = QWidget()
        l = QVBoxLayout(p)
        l.setContentsMargins(4, 4, 4, 4)
        l.setSpacing(8)
        t = QLabel("🛒 Loja")
        t.setStyleSheet("font-size: 20px; font-weight: bold; background: transparent;")
        l.addWidget(t)
        hint = QLabel("Do Modrinth, em 1 clique. Modpacks viram uma versão sua; o resto vai para a versão escolhida em ▶ Jogar.")
        hint.setProperty("class", "muted")
        hint.setWordWrap(True)
        l.addWidget(hint)

        row = QHBoxLayout()
        self.store_type = QComboBox()
        self.store_type.addItem("📦 Modpacks", "modpack")
        self.store_type.addItem("🧩 Mods", "mod")
        self.store_type.addItem("🎨 Texturas", "resourcepack")
        self.store_type.addItem("✨ Shaders", "shader")
        self.store_type.currentIndexChanged.connect(lambda _: self._refresh_store_target())
        self.store_type.setMinimumWidth(150)
        row.addWidget(self.store_type)
        self.store_mc = QComboBox()
        self.store_mc.setEnabled(True)
        self.store_mc.setEditable(True)
        self.store_mc.setMinimumWidth(110)
        self.store_mc.setToolTip("Escolha a versão do Minecraft p/ filtrar a busca")
        self.store_mc.addItem("todas", "")
        row.addWidget(self.store_mc, 1)
        self.mp_search = QLineEdit()
        self.mp_search.setPlaceholderText("Buscar… (vazio = populares)")
        self.mp_search.returnPressed.connect(self._mp_do_search)
        row.addWidget(self.mp_search, 1)
        self.b_mp_search = QPushButton("Buscar")
        self.b_mp_search.clicked.connect(self._mp_do_search)
        row.addWidget(self.b_mp_search)
        l.addLayout(row)

        self.store_target = QLabel("")
        self.store_target.setProperty("class", "muted")
        l.addWidget(self.store_target)

        self.mp_list = QListWidget()
        self.mp_list.setIconSize(QSize(52, 52))
        self.mp_list.setSpacing(4)
        self.mp_list.itemDoubleClicked.connect(lambda _i: self._mp_install())
        l.addWidget(self.mp_list, 1)

        row2 = QHBoxLayout()
        self.b_mp_install = QPushButton("⬇ Instalar selecionado")
        self.b_mp_install.setProperty("class", "play")
        self.b_mp_install.clicked.connect(self._mp_install)
        row2.addWidget(self.b_mp_install, 1)
        self.mp_status = QLabel("")
        self.mp_status.setProperty("class", "muted")
        row2.addWidget(self.mp_status, 1)
        l.addLayout(row2)

        row3 = QHBoxLayout()
        self.b_check_updates = QPushButton("🔄 Checar updates dos meus mods")
        self.b_check_updates.clicked.connect(self._check_updates)
        row3.addWidget(self.b_check_updates, 1)
        self.b_update_all = QPushButton("⬆ Atualizar tudo")
        self.b_update_all.setEnabled(False)
        self.b_update_all.clicked.connect(self._update_all)
        row3.addWidget(self.b_update_all, 1)
        l.addLayout(row3)
        return p

    # ----- página: servidores -----
    def _page_servers(self) -> QWidget:
        p = QWidget()
        l = QVBoxLayout(p)
        l.setContentsMargins(4, 4, 4, 4)
        l.setSpacing(8)
        t = QLabel("🌐 Servidores")
        t.setStyleSheet("font-size: 20px; font-weight: bold; background: transparent;")
        l.addWidget(t)

        g = QGroupBox("Entrar direto")
        f = QVBoxLayout(g)
        row = QHBoxLayout()
        self.server = QComboBox()
        self.server.addItem("Mundo local (sem entrar direto)", None)
        for s in DEFAULT_SERVERS:
            self.server.addItem(f"{s['name']} — {s['host']}", s)
        self.server.currentIndexChanged.connect(lambda _: self._refresh_server_label())
        row.addWidget(self.server, 3)
        self.b_ping = QPushButton("📶 Status")
        self.b_ping.clicked.connect(self._ping_server)
        row.addWidget(self.b_ping, 1)
        f.addLayout(row)
        self.server_status = QLabel("Escolha um servidor e aperte Status.")
        self.server_status.setProperty("class", "muted")
        self.server_status.setWordWrap(True)
        f.addWidget(self.server_status)
        self.direct = QCheckBox("Entrar direto no servidor ao apertar JOGAR")
        self.direct.toggled.connect(lambda _: self._refresh_server_label())
        f.addWidget(self.direct)
        l.addWidget(g)

        g2 = QGroupBox("➕ Meu servidor")
        f2 = QVBoxLayout(g2)
        row_a = QHBoxLayout()
        self.cs_name = QLineEdit()
        self.cs_name.setPlaceholderText("Nome (ex.: SMP dos amigos)")
        row_a.addWidget(self.cs_name, 2)
        self.cs_host = QLineEdit()
        self.cs_host.setPlaceholderText("IP (ex.: jogar.exemplo.com)")
        row_a.addWidget(self.cs_host, 2)
        self.cs_port = QSpinBox()
        self.cs_port.setRange(1, 65535)
        self.cs_port.setValue(25565)
        self.cs_port.setPrefix(":")
        row_a.addWidget(self.cs_port)
        f2.addLayout(row_a)
        row_b = QHBoxLayout()
        self.b_cs_add = QPushButton("＋ Adicionar")
        self.b_cs_add.clicked.connect(self._custom_add)
        row_b.addWidget(self.b_cs_add)
        self.b_cs_del = QPushButton("🗑 Remover selecionado")
        self.b_cs_del.clicked.connect(self._custom_del)
        row_b.addWidget(self.b_cs_del)
        f2.addLayout(row_b)
        self._refresh_server_combos()
        l.addWidget(g2)
        l.addStretch(1)
        return p

    def _refresh_server_combos(self):
        """Recarrega os combos de servidor (curados + seus) preservando a escolha."""
        try:
            keep_main = None
            try:
                d = self.server.currentData()
                keep_main = d.get("host") if isinstance(d, dict) else None
            except Exception:
                pass
            keep_edit = None
            try:
                keep_edit = self.e_server.currentData()
            except Exception:
                pass
            for combo in (getattr(self, "server", None),):
                if combo is None:
                    continue
                combo.blockSignals(True)
                combo.clear()
                combo.addItem("Mundo local (sem entrar direto)", None)
                for s in all_servers():
                    combo.addItem(f"{s['name']} — {s['host']}", s)
                if keep_main:
                    for n in range(combo.count()):
                        dd = combo.itemData(n)
                        if isinstance(dd, dict) and dd.get("host") == keep_main:
                            combo.setCurrentIndex(n)
                            break
                combo.blockSignals(False)
            try:
                self.e_server.blockSignals(True)
                self.e_server.clear()
                self.e_server.addItem("Mundo local", "")
                for s in all_servers():
                    self.e_server.addItem(f"{s['name']} — {s['host']}", s["host"])
                if keep_edit:
                    idx = self.e_server.findData(keep_edit)
                    if idx >= 0:
                        self.e_server.setCurrentIndex(idx)
                self.e_server.blockSignals(False)
            except Exception:
                pass
            self._refresh_server_label()
        except Exception:
            pass

    def _custom_add(self):
        try:
            name = self.cs_name.text().strip()
            host = self.cs_host.text().strip().lower().rstrip(".")
            port = int(self.cs_port.value())
            if not host or "." not in host and host != "localhost":
                QMessageBox.warning(self, APP_NAME, "Digite o IP do servidor.")
                return
            if any(c in host for c in " /"):
                QMessageBox.warning(self, APP_NAME, "IP sem espaços nem barras, senhor.")
                return
            add_custom(name or host, host, port)
            self.cs_name.clear()
            self.cs_host.clear()
            self._refresh_server_combos()
            self.signals.status.emit(f"servidor {host} adicionado")
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"Não adicionou: {e}")

    def _custom_del(self):
        try:
            d = self.server.currentData()
            if not isinstance(d, dict) or not str(d.get("id", "")).startswith("custom-"):
                QMessageBox.information(self, APP_NAME, "Escolha um servidor seu na lista.")
                return
            remove_custom(d.get("host", ""))
            self._refresh_server_combos()
            self.signals.status.emit("servidor removido")
        except Exception:
            pass

    # ----- página: fotos -----
    def _page_shots(self) -> QWidget:
        p = QWidget()
        l = QVBoxLayout(p)
        l.setContentsMargins(4, 4, 4, 4)
        l.setSpacing(8)
        t = QLabel("🖼 Fotos")
        t.setStyleSheet("font-size: 20px; font-weight: bold; background: transparent;")
        l.addWidget(t)
        self.shots_info = QLabel("")
        self.shots_info.setProperty("class", "muted")
        l.addWidget(self.shots_info)

        self.shots_list = QListWidget()
        self.shots_list.setIconSize(QSize(120, 68))
        self.shots_list.setSpacing(6)
        self.shots_list.setViewMode(QListWidget.IconMode)
        self.shots_list.setResizeMode(QListWidget.Adjust)
        self.shots_list.setMovement(QListWidget.Static)
        self.shots_list.itemDoubleClicked.connect(lambda _i: self._shot_open())
        l.addWidget(self.shots_list, 1)

        row = QHBoxLayout()
        self.b_shots_refresh = QPushButton("🔄 Atualizar")
        self.b_shots_refresh.clicked.connect(self._refresh_shots)
        row.addWidget(self.b_shots_refresh)
        self.b_shots_open = QPushButton("🔍 Abrir")
        self.b_shots_open.clicked.connect(self._shot_open)
        row.addWidget(self.b_shots_open)
        self.b_shots_del = QPushButton("🗑 Apagar")
        self.b_shots_del.clicked.connect(self._shot_del)
        row.addWidget(self.b_shots_del)
        l.addLayout(row)
        self._shots_cache: list = []
        self._refresh_shots()
        return p

    def _refresh_shots(self):
        try:
            seen: set[str] = set()
            shots: list = []
            for f in list_shots():  # compartilhados antigos
                if str(f) not in seen:
                    seen.add(str(f))
                    shots.append(f)
            try:  # de cada versão
                base = Path.home() / ".salsicha-launcher" / "instances"
                if base.exists():
                    for d in sorted(base.iterdir()):
                        sd = d / "screenshots"
                        if sd.exists():
                            for f in sorted(sd.glob("*.png"), key=lambda x: x.stat().st_mtime,
                                            reverse=True):
                                if str(f) not in seen:
                                    seen.add(str(f))
                                    shots.append(f)
            except Exception:
                pass
            self._shots_cache = shots
            self.shots_list.clear()
            for f in shots:
                try:
                    item = QListWidgetItem(QIcon(str(f)), f.name)
                except Exception:
                    item = QListWidgetItem(f.name)
                item.setData(Qt.UserRole, str(f))
                item.setToolTip(str(f))
                self.shots_list.addItem(item)
            n = len(shots)
            self.shots_info.setText("Nenhuma foto ainda — F2 no jogo salva aqui." if not n
                                    else f"{n} foto(s) — 2 cliques abre.")
        except Exception:
            pass

    def _shot_open(self):
        try:
            import subprocess as _sp
            it = self.shots_list.currentItem()
            if not it:
                QMessageBox.information(self, APP_NAME, "Escolha uma foto.")
                return
            _sp.Popen(["xdg-open", it.data(Qt.UserRole)])
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"Não abri: {e}")

    def _shot_del(self):
        try:
            it = self.shots_list.currentItem()
            if not it:
                QMessageBox.information(self, APP_NAME, "Escolha uma foto.")
                return
            path = it.data(Qt.UserRole)
            if QMessageBox.question(self, APP_NAME, f"Apagar {Path(path).name}?",
                                    QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                return
            Path(path).unlink(missing_ok=True)
            self._refresh_shots()
        except Exception:
            pass

    # ----- página: contas -----
    def _page_accounts(self) -> QWidget:
        p = QWidget()
        l = QVBoxLayout(p)
        l.setContentsMargins(4, 4, 4, 4)
        l.setSpacing(8)
        t = QLabel("👤 Contas")
        t.setStyleSheet("font-size: 20px; font-weight: bold; background: transparent;")
        l.addWidget(t)

        g = QGroupBox("Contas salvas (Microsoft)")
        f = QVBoxLayout(g)
        self.saved_list = QListWidget()
        self.saved_list.setMaximumHeight(110)
        f.addWidget(self.saved_list)
        row = QHBoxLayout()
        self.b_acc_refresh = QPushButton("Atualizar")
        self.b_acc_refresh.clicked.connect(self._refresh_accounts)
        row.addWidget(self.b_acc_refresh)
        self.b_acc_use = QPushButton("Usar selecionada")
        self.b_acc_use.clicked.connect(self._use_saved)
        row.addWidget(self.b_acc_use)
        f.addLayout(row)
        l.addWidget(g)

        g0 = QGroupBox("🟡 Contas locais (sem Microsoft — joga na hora)")
        f0 = QVBoxLayout(g0)
        self.local_list = QListWidget()
        self.local_list.setMaximumHeight(110)
        self.local_list.itemDoubleClicked.connect(lambda _i: self._local_use())
        f0.addWidget(self.local_list)
        row0 = QHBoxLayout()
        self.local_nick = QLineEdit()
        self.local_nick.setPlaceholderText("Nick local (3–16 letras)")
        self.local_nick.setMaxLength(16)
        self.local_nick.returnPressed.connect(self._local_add)
        row0.addWidget(self.local_nick, 2)
        self.b_local_add = QPushButton("＋ Criar")
        self.b_local_add.clicked.connect(self._local_add)
        row0.addWidget(self.b_local_add)
        f0.addLayout(row0)
        row0b = QHBoxLayout()
        self.b_local_use = QPushButton("Usar selecionada")
        self.b_local_use.clicked.connect(self._local_use)
        row0b.addWidget(self.b_local_use)
        self.b_local_del = QPushButton("🗑 Apagar")
        self.b_local_del.clicked.connect(self._local_del)
        row0b.addWidget(self.b_local_del)
        f0.addLayout(row0b)
        l.addWidget(g0)

        g2 = QGroupBox("🟢 Entrar com Microsoft (fácil)")
        f2 = QVBoxLayout(g2)
        trust = QLabel(
            "Sem Client ID, sem Azure: o launcher mostra um <b>código</b>, "
            "o senhor confirma em <b>microsoft.com/link</b> e pronto.<br>"
            "A Salsicha <b>nunca vê sua senha</b>."
        )
        trust.setProperty("class", "trust")
        trust.setWordWrap(True)
        f2.addWidget(trust)
        row_dev = QHBoxLayout()
        self.b_device = QPushButton("1. Gerar meu código")
        self.b_device.clicked.connect(self._device_step1)
        row_dev.addWidget(self.b_device)
        self.b_device_cancel = QPushButton("Cancelar")
        self.b_device_cancel.setEnabled(False)
        self.b_device_cancel.clicked.connect(self._device_cancel)
        row_dev.addWidget(self.b_device_cancel)
        f2.addLayout(row_dev)
        self.device_status = QLabel("Aperte gerar código quando quiser entrar.")
        self.device_status.setProperty("class", "muted")
        self.device_status.setWordWrap(True)
        self.device_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        f2.addWidget(self.device_status)
        l.addWidget(g2)

        g3 = QGroupBox("🔧 Avançado (app Azure próprio)")
        f3 = QVBoxLayout(g3)
        row_ms = QHBoxLayout()
        try:
            _mcfg = load_cfg()
        except Exception:
            _mcfg = {}
        self.client_id = QLineEdit()
        self.client_id.setPlaceholderText("Azure Client ID (do seu app)")
        self.client_id.setEchoMode(QLineEdit.Password)
        try:
            self.client_id.setText(_mcfg.get("ms_client_id", "") or "")
        except Exception:
            pass
        self.client_id.editingFinished.connect(lambda: self._save_ms_fields())
        row_ms.addWidget(self.client_id, 2)
        self.redirect = QLineEdit("http://localhost:8000")
        try:
            self.redirect.setText(_mcfg.get("ms_redirect", "") or "http://localhost:8000")
        except Exception:
            pass
        self.redirect.editingFinished.connect(lambda: self._save_ms_fields())
        row_ms.addWidget(self.redirect, 2)
        f3.addLayout(row_ms)
        btns = QHBoxLayout()
        self.b_ms = QPushButton("1. Abrir microsoft.com")
        self.b_ms.clicked.connect(self._ms_step1)
        btns.addWidget(self.b_ms)
        self.b_code = QPushButton("2. Concluir com o código")
        self.b_code.clicked.connect(self._ms_step2)
        btns.addWidget(self.b_code)
        f3.addLayout(btns)
        self.code = QLineEdit()
        self.code.setPlaceholderText("Cole a URL de retorno (?code=…)")
        f3.addWidget(self.code)
        l.addWidget(g3)
        l.addStretch(1)
        return p

    # ----- página: visual -----
    def _page_visual(self) -> QWidget:
        p = QWidget()
        l = QVBoxLayout(p)
        l.setContentsMargins(4, 4, 4, 4)
        l.setSpacing(8)
        t = QLabel("🎨 Visual")
        t.setStyleSheet("font-size: 20px; font-weight: bold; background: transparent;")
        l.addWidget(t)
        hint = QLabel("Tudo aplica na hora e fica salvo.")
        hint.setProperty("class", "muted")
        l.addWidget(hint)

        try:
            _t = load_cfg().get("theme") or {}
        except Exception:
            _t = {}
        cur = dict(DEFAULT_THEME)
        if isinstance(_t, dict):
            cur.update({k: v for k, v in _t.items() if k in cur})

        g = QGroupBox("Cor de destaque")
        f = QVBoxLayout(g)
        self.theme_group = QButtonGroup(self)
        self.theme_group.setExclusive(True)
        r1 = QHBoxLayout()
        r2 = QHBoxLayout()
        self.theme_buttons: dict = {}
        for i, (key, pr) in enumerate(PRESETS.items()):
            b = QPushButton(pr["name"])
            b.setCheckable(True)
            b.setProperty("class", "preset")
            b.setChecked(cur.get("preset") == key and not (cur.get("custom") or "").strip())
            b.clicked.connect(lambda _c, k=key: self._set_theme(preset=k, custom=""))
            self.theme_group.addButton(b, i)
            self.theme_buttons[key] = b
            (r1 if i < 4 else r2).addWidget(b)
        f.addLayout(r1)
        f.addLayout(r2)
        row_c = QHBoxLayout()
        self.b_custom = QPushButton("🎨 Cor personalizada…")
        self.b_custom.clicked.connect(self._pick_custom_color)
        row_c.addWidget(self.b_custom)
        self.b_custom_clear = QPushButton("↩ Padrão")
        self.b_custom_clear.clicked.connect(lambda: self._set_theme(custom=""))
        row_c.addWidget(self.b_custom_clear)
        self.custom_swatch = QLabel("")
        self.custom_swatch.setFixedSize(28, 28)
        row_c.addWidget(self.custom_swatch)
        row_c.addStretch(1)
        f.addLayout(row_c)
        self._refresh_swatch()
        l.addWidget(g)

        g2 = QGroupBox("Fundo e fonte")
        f2 = QVBoxLayout(g2)
        row_b = QHBoxLayout()
        row_b.addWidget(QLabel("Fundo:"))
        self.bg_combo = QComboBox()
        for key, b in BG_MODES.items():
            self.bg_combo.addItem(b["name"], key)
        try:
            self.bg_combo.setCurrentIndex(list(BG_MODES).index(cur.get("bg_mode", "padrao")))
        except Exception:
            pass
        self.bg_combo.currentIndexChanged.connect(
            lambda _: self._set_theme(bg_mode=self.bg_combo.currentData()))
        row_b.addWidget(self.bg_combo, 1)
        row_b.addWidget(QLabel("Fonte:"))
        self.font_combo = QComboBox()
        for key, fs in FONT_SCALES.items():
            self.font_combo.addItem(fs["name"], key)
        try:
            self.font_combo.setCurrentIndex(list(FONT_SCALES).index(cur.get("font", "normal")))
        except Exception:
            pass
        self.font_combo.currentIndexChanged.connect(
            lambda _: self._set_theme(font=self.font_combo.currentData()))
        row_b.addWidget(self.font_combo, 1)
        f2.addLayout(row_b)
        row_f = QHBoxLayout()
        row_f.addWidget(QLabel("Letra:"))
        self.family_combo = QComboBox()
        for key, fm in FONT_FAMILIES.items():
            self.family_combo.addItem(fm["name"], key)
        try:
            self.family_combo.setCurrentIndex(list(FONT_FAMILIES).index(cur.get("family", "noto")))
        except Exception:
            pass
        self.family_combo.currentIndexChanged.connect(
            lambda _: self._set_theme(family=self.family_combo.currentData()))
        row_f.addWidget(self.family_combo, 1)
        f2.addLayout(row_f)
        self.anim_check = QCheckBox("✨ Animações (transições + brilho do JOGAR)")
        try:
            self.anim_check.setChecked(bool(cur.get("anim", True)))
        except Exception:
            pass
        self.anim_check.toggled.connect(lambda v: self._set_theme(anim=bool(v)))
        f2.addWidget(self.anim_check)
        l.addWidget(g2)
        l.addStretch(1)
        return p

    def _theme_cfg(self) -> dict:
        try:
            t = load_cfg().get("theme") or {}
        except Exception:
            t = {}
        cur = dict(DEFAULT_THEME)
        if isinstance(t, dict):
            cur.update({k: v for k, v in t.items() if k in cur})
        return cur

    def _set_theme(self, preset: str | None = None, custom: str | None = None,
                   bg_mode: str | None = None, font: str | None = None,
                   family: str | None = None, anim: bool | None = None):
        try:
            cur = self._theme_cfg()
            if preset is not None:
                cur["preset"] = preset
            if custom is not None:
                cur["custom"] = custom
            if bg_mode is not None:
                cur["bg_mode"] = bg_mode
            if font is not None:
                cur["font"] = font
            if family is not None:
                cur["family"] = family
            if anim is not None:
                cur["anim"] = bool(anim)
            cfg = load_cfg()
            cfg["theme"] = cur
            save_cfg(cfg)
            self.apply_theme()
            self._refresh_swatch()
        except Exception:
            pass

    def _refresh_swatch(self):
        try:
            c = resolve(self._theme_cfg())
            self.custom_swatch.setStyleSheet(
                f"background: {c['accent']}; border-radius: 14px; border: 1px solid #3a3f47;")
        except Exception:
            pass

    def _pick_custom_color(self):
        try:
            from PySide6.QtWidgets import QColorDialog
            from PySide6.QtGui import QColor
            cur = resolve(self._theme_cfg())["accent"]
            col = QColorDialog.getColor(QColor(cur), self, "Cor de destaque")
            if col.isValid():
                self._set_theme(custom=col.name())
        except Exception:
            pass

    def apply_theme(self):
        """Reaplica QSS + fonte do tema salvo (tempo real)."""
        try:
            from PySide6.QtGui import QFont
            c = resolve(self._theme_cfg())
            app = QApplication.instance()
            if app is not None:
                app.setStyleSheet(build_qss(c["accent"], c["hover"], c["bg"],
                                            c["side"], c["card"], c["base"],
                                            c["grad"], c["glow"], c["family"]))
                try:
                    app.setFont(QFont(c["family"], c["qfont"]))
                except Exception:
                    pass
            self._setup_anims()
        except Exception:
            pass

    # ----- página: config -----
    def _page_settings(self) -> QWidget:
        p = QWidget()
        l = QVBoxLayout(p)
        l.setContentsMargins(4, 4, 4, 4)
        l.setSpacing(8)
        t = QLabel("⚙️ Config")
        t.setStyleSheet("font-size: 20px; font-weight: bold; background: transparent;")
        l.addWidget(t)

        g = QGroupBox("Desempenho")
        f = QVBoxLayout(g)
        row = QHBoxLayout()
        row.addWidget(QLabel("RAM:"))
        try:
            _pcfg = load_cfg()
        except Exception:
            _pcfg = {}
        self.ram = QSpinBox()
        self.ram.setRange(2, 16)
        try:
            self.ram.setValue(int(_pcfg.get("ram_gb", 4)))
        except Exception:
            self.ram.setValue(4)
        self.ram.setSuffix(" GB")
        self.ram.valueChanged.connect(lambda v: self._save_simple("ram_gb", int(v)))
        row.addWidget(self.ram)
        row.addWidget(QLabel("💡 4 GB puro; com mods 6–8."))
        row.addStretch(1)
        f.addLayout(row)
        self.snapshots = QCheckBox("mostrar snapshots na lista de versões")
        try:
            self.snapshots.setChecked(bool(_pcfg.get("snapshots", False)))
        except Exception:
            pass
        self.snapshots.toggled.connect(self._snapshots_toggled)
        f.addWidget(self.snapshots)
        self.close_on_launch = QCheckBox("fechar o launcher ao jogar (reabre ao sair do jogo)")
        try:
            if "close_v2" not in _pcfg:
                _pcfg["close_on_launch"] = True
                _pcfg["close_v2"] = True
                save_cfg(_pcfg)
            self.close_on_launch.setChecked(bool(_pcfg.get("close_on_launch", True)))
        except Exception:
            pass
        self.close_on_launch.toggled.connect(lambda v: self._save_simple("close_on_launch", bool(v)))
        f.addWidget(self.close_on_launch)
        l.addWidget(g)

        g2 = QGroupBox("⚡ Mods de FPS (padrão das novas versões)")
        f2 = QVBoxLayout(g2)
        try:
            _cfg = load_cfg()
        except Exception:
            _cfg = {}
        _sel = (_cfg.get("mods") if isinstance(_cfg, dict) else {}) or {}
        self.mod_checks: dict = {}
        r1 = QHBoxLayout()
        r2 = QHBoxLayout()
        r3 = QHBoxLayout()
        _all = list(PERF_MODS.items()) + [(s, v) for s, v in FORGE_PERF_MODS.items()]
        _defs = ("sodium", "lithium", "fabric-api", "foamfix", "vanillafix", "texfix", "surge", "clumps")
        for i, (slug, (pretty, _desc)) in enumerate(_all):
            cb = QCheckBox(pretty)
            cb.setChecked(bool(_sel.get(slug, slug in _defs)))
            cb.setToolTip(_desc + (" (Forge)" if slug in FORGE_PERF_MODS else ""))
            cb.toggled.connect(lambda _v: self._save_mods())
            self.mod_checks[slug] = cb
            (r1 if i < 4 else (r2 if i < 7 else r3)).addWidget(cb)
        r1.addStretch(1)
        r2.addStretch(1)
        r3.addStretch(1)
        f2.addLayout(r1)
        f2.addLayout(r2)
        f2.addLayout(r3)
        l.addWidget(g2)

        jv = find_java()
        try:
            from .java_utils import get_java_for_mc as _gj2, required_java_major as _jm3
            _reqs = []
            for _i in self._get_installations():
                _mc = _i.get("mc", "") or ""
                if _mc and _mc != "?":
                    _reqs.append(f"{_i.get('name', _mc)} precisa Java {_jm3(_mc)}")
            _jline = " • ".join(_reqs[:4]) if _reqs else "crie uma versão em 🗂 Versões"
        except Exception:
            _jline = ""
        jlabel = QLabel(
            f"☕ Java: {jv or 'não achado — o launcher baixa o runtime sozinho'}"
            + (f" ({java_version(jv).splitlines()[0][:60]})" if jv else "")
            + (f"<br>{_jline}" if _jline else ""))
        jlabel.setProperty("class", "muted")
        jlabel.setWordWrap(True)
        l.addWidget(jlabel)

        try:
            _has_nv = self._dedicated_gpu_available()
        except Exception:
            _has_nv = False
        if _has_nv:
            self.gpu_check = QCheckBox("🎮 Usar placa NVIDIA (prime-run) — recomendado neste PC")
            try:
                self.gpu_check.setChecked((load_cfg().get("gpu", "auto") or "auto") != "integrada")
            except Exception:
                self.gpu_check.setChecked(True)
            self.gpu_check.toggled.connect(
                lambda v: self._save_simple("gpu", "auto" if v else "integrada"))
            l.addWidget(self.gpu_check)

        g4 = QGroupBox("💾 Mundos e registros")
        f4 = QVBoxLayout(g4)
        self.backup_status = QLabel("Backup zipa os mundos da versão de ▶ Jogar (cada uma tem os seus).")
        self.backup_status.setProperty("class", "muted")
        self.backup_status.setWordWrap(True)
        f4.addWidget(self.backup_status)
        row_w = QHBoxLayout()
        self.b_backup = QPushButton("💾 Backup agora")
        self.b_backup.clicked.connect(self._backup_saves)
        row_w.addWidget(self.b_backup)
        self.b_saves = QPushButton("📂 Abrir saves")
        self.b_saves.clicked.connect(self._open_saves)
        row_w.addWidget(self.b_saves)
        self.b_logs = QPushButton("📄 Ver logs")
        self.b_logs.clicked.connect(self._show_logs)
        row_w.addWidget(self.b_logs)
        f4.addLayout(row_w)
        l.addWidget(g4)
        l.addStretch(1)
        foot = QLabel("Salsicha Launcher • roda 100% no seu PC • ~/.salsicha-launcher/")
        foot.setProperty("class", "muted")
        l.addWidget(foot)
        return p

    def _backup_saves(self):
        self.b_backup.setEnabled(False)
        self.backup_status.setText("fazendo backup…")

        def work():
            import datetime as _dt
            import shutil as _sh
            s = self.signals
            try:
                cur = self._current_inst()
                iname = (cur.get("name", "") if cur else "") or "minecraft"
                safe = "".join(c if c.isalnum() or c in ("-_.") else "-" for c in iname)[:32]
                src = (self._inst_gamedir(cur) if cur else Path(get_minecraft_dir())) / "saves"
                if not src.exists() or not any(src.iterdir()):
                    s.log.emit("__BACKUP_EMPTY__")
                    return
                dest_dir = Path.home() / ".salsicha-launcher" / "backups"
                dest_dir.mkdir(parents=True, exist_ok=True)
                ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
                zf = dest_dir / f"saves-{safe}-{ts}.zip"
                base = zf.with_suffix("")
                _sh.make_archive(str(base), "zip", root_dir=str(src.parent), base_dir="saves")
                # mantém só os 10 mais novos
                olds = sorted(dest_dir.glob("saves-*.zip"), key=lambda f: f.stat().st_mtime)
                for o in olds[:-10]:
                    try:
                        o.unlink()
                    except Exception:
                        pass
                s.log.emit(f"__BACKUP_DONE__:{zf.name}")
            except Exception as e:
                s.log.emit(f"__BACKUP_FAIL__:{e}")
        threading.Thread(target=work, daemon=True).start()

    def _open_saves(self):
        try:
            import subprocess as _sp
            cur = self._current_inst()
            d = (self._inst_gamedir(cur) if cur else Path(get_minecraft_dir())) / "saves"
            d.mkdir(parents=True, exist_ok=True)
            _sp.Popen(["xdg-open", str(d)])
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"Não abriu a pasta: {e}")

    def _show_logs(self):
        try:
            from PySide6.QtWidgets import QDialog
            dlg = QDialog(self)
            dlg.setWindowTitle("📄 Registros")
            dlg.resize(640, 440)
            lay = QVBoxLayout(dlg)
            row = QHBoxLayout()
            combo = QComboBox()
            logdir = Path.home() / ".salsicha-launcher" / "logs"
            files = sorted(logdir.glob("*.log"), key=lambda f: f.stat().st_mtime,
                           reverse=True) if logdir.exists() else []
            if not files:
                combo.addItem("(sem logs ainda — jogue uma vez)", "")
            for fl in files[:20]:
                kb = fl.stat().st_size // 1024
                combo.addItem(f"{fl.name} ({kb} KB)", str(fl))
            row.addWidget(combo, 1)
            view = QTextEdit()
            view.setReadOnly(True)

            def _load(_=None):
                p = combo.currentData()
                if not p:
                    view.setPlainText("Os logs do jogo aparecem aqui após o primeiro Jogar.")
                    return
                try:
                    txt = Path(p).read_text(encoding="utf-8", errors="replace")
                    view.setPlainText(txt[-12000:] or "(vazio)")
                    view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())
                except Exception as e:
                    view.setPlainText(f"Não li o log: {e}")

            combo.currentIndexChanged.connect(_load)
            b_close = QPushButton("Fechar")
            b_close.clicked.connect(dlg.accept)
            row.addWidget(b_close)
            lay.addLayout(row)
            lay.addWidget(view, 1)
            _load()
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"Não abri os logs: {e}")

    # ---------- rótulos ----------
    def _refresh_play_buttons(self, mode: str):
        is_ms = (normalize_mode(mode) == MS_MODE)
        try:
            self.b_play.setText("▶ JOGAR com Microsoft" if is_ms else "▶ JOGAR")
        except Exception:
            pass
        self._refresh_account_labels()

    def _refresh_account_labels(self):
        try:
            nick = self.user.text().strip() or "sem nick"
            mode = self.mode.currentText()
            self.play_account.setText(f"{mode} • {nick}")
            self.side_account.setText(f"{mode}\n{nick}")
        except Exception:
            pass

    def _refresh_avatar(self):
        try:
            nick = self.user.text().strip()
        except Exception:
            return
        if not nick:
            return

        def work(nick=nick):
            try:
                p = fetch_avatar(nick)
                if p:
                    self.signals.log.emit(f"__AVATAR__:{p}")
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()

    def _apply_avatar(self, path: str):
        try:
            from PySide6.QtGui import QPixmap
            pm = QPixmap(path)
            if pm.isNull():
                return
            self.play_avatar.setPixmap(pm)
            self.side_avatar.setPixmap(pm)
        except Exception:
            pass

    def _refresh_server_label(self):
        try:
            data = self.server.currentData()
            if data and self.direct.isChecked():
                self.play_server_label.setText(f"→ entrando direto em {data['name']}")
            elif data:
                self.play_server_label.setText(f"Servidor: {data['name']} (marque entrar direto p/ ir direto)")
            else:
                self.play_server_label.setText("Mundo local (troque em 🌐 Servidores)")
        except Exception:
            pass

    # ---------- assistente inicial ----------
    def _maybe_wizard(self):
        """Primeira abertura: guia nick + versão em 3 passos."""
        try:
            cfg = load_cfg()
            if cfg.get("installations") or (cfg.get("nick") or "").strip() or load_accounts():
                return
        except Exception:
            return
        try:
            from PySide6.QtWidgets import QDialog
            dlg = QDialog(self)
            dlg.setWindowTitle("🌭 Boas-vindas ao Salsicha!")
            dlg.resize(420, 300)
            lay = QVBoxLayout(dlg)
            stack = QStackedWidget()
            lay.addWidget(stack, 1)

            # passo 1: quem é você
            w1 = QWidget()
            f1 = QVBoxLayout(w1)
            f1.addWidget(QLabel("<b>Quem vai jogar?</b>"))
            nick = QLineEdit()
            nick.setPlaceholderText("Seu nick (3–16 letras)")
            nick.setMaxLength(16)
            f1.addWidget(nick)
            mode = QComboBox()
            mode.addItems([LOCAL_MODE, MS_MODE])
            f1.addWidget(QLabel("Conta Local joga na hora, sem Microsoft. A Microsoft é opcional, em 👤 Contas."))
            f1.addWidget(mode)
            stack.addWidget(w1)

            # passo 2: versão
            w2 = QWidget()
            f2w = QVBoxLayout(w2)
            f2w.addWidget(QLabel("<b>Qual Minecraft?</b>"))
            mc = QLineEdit()
            mc.setPlaceholderText("buscando a última estável…")
            f2w.addWidget(mc)
            loader = QComboBox()
            loader.addItems(["vanilla", "fabric"])
            f2w.addWidget(QLabel("Loader (mods só no Fabric):"))
            f2w.addWidget(loader)

            def _fill_latest():
                try:
                    v = latest_release()
                    mc.setText(v)
                    mc.setPlaceholderText("Versão do Minecraft")
                except Exception:
                    mc.setPlaceholderText("sem internet? digite ex.: 1.21")
            threading.Thread(target=_fill_latest, daemon=True).start()
            stack.addWidget(w2)

            # passo 3: pronto
            w3 = QWidget()
            f3w = QVBoxLayout(w3)
            done_lbl = QLabel("")
            done_lbl.setWordWrap(True)
            f3w.addWidget(done_lbl)
            stack.addWidget(w3)

            row = QHBoxLayout()
            b_back = QPushButton("← Voltar")
            b_next = QPushButton("Avançar →")
            b_skip = QPushButton("Pular")
            row.addWidget(b_back)
            row.addWidget(b_skip)
            row.addWidget(b_next)
            lay.addLayout(row)

            def _sync():
                i = stack.currentIndex()
                b_back.setEnabled(i > 0)
                b_next.setText("Concluir ✓" if i == 2 else "Avançar →")
                if i == 2:
                    done_lbl.setText(
                        f"Nick <b>{nick.text().strip() or 'Salsicha'}</b> • "
                        f"Minecraft <b>{mc.text().strip() or '?'}</b> + {loader.currentText()}.<br><br>"
                        "É só apertar Concluir e depois ▶ JOGAR.")

            def _go(d):
                stack.setCurrentIndex(min(2, max(0, stack.currentIndex() + d)))
                _sync()

            b_back.clicked.connect(lambda: _go(-1))
            b_skip.clicked.connect(dlg.reject)
            nick.returnPressed.connect(lambda: _go(1))

            def _finish():
                if stack.currentIndex() < 2:
                    _go(1)
                    return
                import time as _t
                name = nick.text().strip() or "Salsicha"
                mcver = mc.text().strip()
                if not mcver:
                    QMessageBox.warning(dlg, APP_NAME, "Digite a versão (ex.: 1.21).")
                    return
                ld = loader.currentText()
                data = {"id": f"v-{int(_t.time())}", "type": "standard",
                        "name": f"{'Fabric + FPS' if ld != 'vanilla' else 'Minecraft'} {mcver}",
                        "mc": mcver, "loader": ld, "loader_ver": "",
                        "mods": self._default_mods(), "server": "", "direct": False}
                self._set_installations([data], data["id"])
                cfg2 = load_cfg()
                cfg2["nick"] = name
                cfg2["mode"] = normalize_mode(mode.currentText())
                save_cfg(cfg2)
                try:
                    save_local_account(name)
                except Exception:
                    pass
                self.user.setText(name)
                self.mode.setCurrentText(normalize_mode(mode.currentText()))
                self._refresh_play_buttons(normalize_mode(mode.currentText()))
                self._refresh_inst_combo()
                self._refresh_inst_list()
                self._refresh_avatar()
                dlg.accept()

            b_next.clicked.connect(_finish)
            _sync()
            dlg.exec()
        except Exception:
            pass

    # ---------- versões (instalações estilo TLauncher) ----------
    def _get_installations(self) -> list:
        try:
            cfg = load_cfg()
            insts = cfg.get("installations") or []
            return [i for i in insts if isinstance(i, dict)]
        except Exception:
            return []

    def _set_installations(self, insts: list, last_id: str | None = None):
        cfg = load_cfg()
        cfg["installations"] = insts
        if last_id is not None:
            cfg["last_installation"] = last_id
        save_cfg(cfg)

    def _default_mods(self, loader: str = "") -> dict:
        try:
            sel = (load_cfg().get("mods") or {})
        except Exception:
            sel = {}
        try:
            pack = perf_mods_for(loader) if loader else None
            slugs = list(pack.keys()) if pack else list(PERF_MODS.keys()) + list(FORGE_PERF_MODS.keys())
        except Exception:
            slugs = list(PERF_MODS.keys())
        out: dict = {}
        for slug in slugs:
            if slug in sel:
                out[slug] = bool(sel[slug])
            else:
                out[slug] = slug in ("sodium", "lithium", "fabric-api", "foamfix", "vanillafix", "texfix", "surge", "clumps")
        return out

    def _maybe_seed_defaults(self, latest: str):
        if self._get_installations() or not latest:
            self._refresh_inst_combo()
            return
        import time as _t
        base = int(_t.time())
        insts = [
            {"id": f"vanilla-{base}", "type": "standard", "name": f"Minecraft {latest}",
             "mc": latest, "loader": "vanilla", "loader_ver": "",
             "mods": self._default_mods(), "server": "", "direct": False},
            {"id": f"fabric-{base}", "type": "standard", "name": f"Fabric + FPS {latest}",
             "mc": latest, "loader": "fabric", "loader_ver": "",
             "mods": self._default_mods(), "server": "", "direct": False},
        ]
        self._set_installations(insts, insts[0]["id"])
        self._refresh_inst_combo()
        self._refresh_inst_list()

    def _refresh_inst_combo(self):
        try:
            insts = self._get_installations()
            last = load_cfg().get("last_installation", "")
            self.installation.blockSignals(True)
            self.installation.clear()
            for i in insts:
                ic = self._inst_icon(i)
                if ic is not None:
                    self.installation.addItem(ic, i.get("name", "?"), i.get("id"))
                else:
                    self.installation.addItem(i.get("name", "?"), i.get("id"))
            self.installation.blockSignals(False)
            if insts:
                idx = next((n for n, i in enumerate(insts) if i.get("id") == last), 0)
                self.installation.setCurrentIndex(idx)
            self._refresh_inst_info()
        except Exception:
            pass

    def _refresh_inst_list(self):
        try:
            cur = self._current_inst()
            self.inst_list.blockSignals(True)
            self.inst_list.clear()
            for i in self._get_installations():
                tag = "📦 " if i.get("type") == "modpack" else ""
                it = QListWidgetItem(tag + i.get("name", "?"))
                try:
                    ic = self._inst_icon(i)
                    if ic is not None:
                        it.setIcon(ic)
                except Exception:
                    pass
                self.inst_list.addItem(it)
            self.inst_list.blockSignals(False)
            if cur:
                for n, i in enumerate(self._get_installations()):
                    if i.get("id") == cur.get("id"):
                        self.inst_list.setCurrentRow(n)
                        break
        except Exception:
            pass

    def _current_inst(self) -> dict | None:
        try:
            _id = self.installation.currentData()
            for i in self._get_installations():
                if i.get("id") == _id:
                    return i
            insts = self._get_installations()
            return insts[0] if insts else None
        except Exception:
            return None

    def _refresh_inst_info(self):
        try:
            i = self._current_inst()
            if not i:
                self.inst_info.setText("Nenhuma versão ainda — crie uma em 🗂 Versões.")
                return
            if i.get("type") == "modpack":
                base = f"📦 Modpack • {i.get('mc', '?')}"
            elif (i.get("loader") or "vanilla") == "vanilla":
                base = f"{i.get('mc', '?')} • puro (vanilla)"
            else:
                lv = i.get("loader_ver") or "latest"
                try:
                    _pack = perf_mods_for(i.get("loader", "vanilla") or "vanilla")
                    nmods = sum(1 for k, v in ((i.get("mods") or {}).items()) if v and k in _pack)
                except Exception:
                    nmods = sum(1 for v in (i.get("mods") or {}).values() if v)
                base = f"{i.get('mc', '?')} • {i.get('loader')} {lv} • {nmods} mods FPS"
            if i.get("server") and i.get("direct"):
                base += f" → {i['server']}"
            elif i.get("server"):
                base += f" • servidor: {i['server']}"
            nc = len(i.get("content") or [])
            if nc and i.get("type") != "modpack":
                base += f" • {nc} extra(s)"
            self.inst_info.setText(base)
            self._set_installations(self._get_installations(), i.get("id"))
            try:
                self._refresh_store_target()
            except Exception:
                pass
        except Exception:
            pass

    def _edit_installation(self, row: int):
        try:
            insts = self._get_installations()
            if not (0 <= row < len(insts)):
                return
            i = insts[row]
            self._editing_id = i.get("id")
            self.e_name.setText(i.get("name", ""))
            self._editing_icon = i.get("icon", "") or ""
            self._preview_inst_icon()
            if i.get("mc"):
                self.version.setCurrentText(i["mc"])
            self.loader.setCurrentText(i.get("loader", "vanilla") or "vanilla")
            self.loader_ver.setCurrentText(i.get("loader_ver", "") or "")
            mods = i.get("mods") or self._default_mods(i.get("loader", ""))
            _forge_defs = ("foamfix", "vanillafix", "texfix", "surge", "clumps")
            for slug, cb in self.e_mod_checks.items():
                if slug in mods:
                    cb.setChecked(bool(mods[slug]))
                else:
                    # Save antigo de Forge sem as chaves novas: liga o pack Forge por padrão.
                    cb.setChecked(slug in _forge_defs if (i.get("loader") == "forge") else False)
            srv = i.get("server", "") or ""
            idx = self.e_server.findData(srv)
            self.e_server.setCurrentIndex(idx if idx >= 0 else 0)
            self.e_direct.setChecked(bool(i.get("direct", False)))
            self._refresh_content_list()
        except Exception:
            pass

    def _pick_inst_icon(self):
        try:
            from PySide6.QtWidgets import QFileDialog
            p, _ = QFileDialog.getOpenFileName(
                self, "Ícone da versão", str(Path.home()),
                "Imagens (*.png *.jpg *.jpeg *.svg *.ico *.bmp)")
            if p:
                self._editing_icon = p
                self._preview_inst_icon()
        except Exception:
            pass

    def _clear_inst_icon(self):
        self._editing_icon = ""
        try:
            self.e_icon.clear()
        except Exception:
            pass

    def _preview_inst_icon(self):
        try:
            from PySide6.QtGui import QPixmap
            pm = QPixmap(self._editing_icon or "")
            if not pm.isNull():
                self.e_icon.setPixmap(pm)
            else:
                self.e_icon.clear()
        except Exception:
            pass

    def _pick_block_icon(self):
        """Galeria de blocos do Minecraft como ícone da versão."""
        try:
            from .block_icons import BLOCKS, ensure_block_icons
            paths = ensure_block_icons()
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"Não extraí os blocos: {e}")
            return
        if not paths:
            QMessageBox.information(
                self, APP_NAME,
                "Ainda não há arquivos do Minecraft aqui.\nJogue uma vez e volte — eu tiro os ícones do jogo.")
            return
        try:
            from PySide6.QtWidgets import QDialog, QDialogButtonBox
            from PySide6.QtGui import QIcon
            dlg = QDialog(self)
            dlg.setWindowTitle("⛏ Bloco de ícone")
            dlg.resize(460, 380)
            lay = QVBoxLayout(dlg)
            grid = QListWidget()
            grid.setIconSize(QSize(48, 48))
            grid.setSpacing(4)
            grid.setViewMode(QListWidget.IconMode)
            grid.setResizeMode(QListWidget.Adjust)
            grid.setMovement(QListWidget.Static)
            grid.itemDoubleClicked.connect(lambda _i: dlg.accept())
            for bid, pretty, _c in BLOCKS:
                p = paths.get(bid)
                if not p:
                    continue
                try:
                    it = QListWidgetItem(QIcon(str(p)), pretty)
                except Exception:
                    it = QListWidgetItem(pretty)
                it.setData(Qt.UserRole, str(p))
                grid.addItem(it)
            lay.addWidget(grid, 1)
            btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)
            lay.addWidget(btns)
            if dlg.exec() and grid.currentItem() and grid.currentItem().data(Qt.UserRole):
                self._editing_icon = grid.currentItem().data(Qt.UserRole)
                self._preview_inst_icon()
        except Exception:
            pass

    @staticmethod
    def _inst_icon(inst) -> object:
        """QIcon do ícone guardado, ou None."""
        try:
            from PySide6.QtGui import QIcon
            p = (inst or {}).get("icon", "") if isinstance(inst, dict) else ""
            if p and Path(p).exists():
                return QIcon(p)
        except Exception:
            pass
        return None

    @staticmethod
    def _store_inst_icon(inst_id: str, src: str) -> str:
        """Copia o ícone p/ dentro do launcher (não quebra se o original sumir)."""
        try:
            base = Path.home() / ".salsicha-launcher" / "icons" / "versions"
            base.mkdir(parents=True, exist_ok=True)
            for old in base.glob(f"{inst_id}.*"):
                try:
                    if not src or Path(src).resolve() != old.resolve():
                        old.unlink()
                except Exception:
                    pass
            if not src:
                return ""
            s = Path(src)
            if not s.exists():
                return ""
            ext = s.suffix.lower()
            if ext not in (".png", ".jpg", ".jpeg", ".svg", ".ico", ".bmp"):
                ext = ".png"
            dst = base / f"{inst_id}{ext}"
            if s.resolve() != dst.resolve():
                import shutil as _sh
                _sh.copy2(s, dst)
                return str(dst)
            return str(s)
        except Exception:
            return src or ""

    def _new_installation(self):
        try:
            self._editing_id = None
            self._editing_icon = ""
            try:
                self.e_icon.clear()
            except Exception:
                pass
            self.e_name.setText("")
            self.e_name.setPlaceholderText("Ex.: Hypixel 1.8.9")
            self.e_name.setFocus()
            self.loader.setCurrentText("vanilla")
            for slug, cb in self.e_mod_checks.items():
                cb.setChecked(slug in ("sodium", "lithium", "fabric-api", "foamfix", "vanillafix", "texfix", "surge", "clumps"))
            self.e_server.setCurrentIndex(0)
            self.e_direct.setChecked(False)
            self.inst_list.clearSelection()
            try:
                self.content_list.clear()
            except Exception:
                pass
        except Exception:
            pass

    def _save_installation(self):
        try:
            import time as _t
            name = self.e_name.text().strip()
            mc = self.version.currentText().strip()
            if not name:
                QMessageBox.warning(self, APP_NAME, "Dê um nome para a versão.")
                return
            if not mc:
                QMessageBox.warning(self, APP_NAME, "A lista do Minecraft ainda está carregando. Aguarde.")
                return
            insts = self._get_installations()
            iid = self._editing_id or f"v-{int(_t.time())}"
            data = {
                "id": iid,
                "type": "standard",
                "name": name,
                "mc": mc,
                "icon": self._store_inst_icon(iid, (self._editing_icon or "").strip()),
                "loader": self.loader.currentText() or "vanilla",
                "loader_ver": self.loader_ver.currentText().strip(),
                "mods": {s: cb.isChecked() for s, cb in self.e_mod_checks.items()},
                "server": self.e_server.currentData() or "",
                "direct": self.e_direct.isChecked(),
            }
            for n, i in enumerate(insts):
                if i.get("id") == data["id"]:
                    if i.get("type") == "modpack":
                        # Modpack não vira versão normal: preserva o pack,
                        # atualiza só nome, ícone e servidor.
                        i["name"] = data["name"]
                        i["icon"] = data.get("icon", i.get("icon", ""))
                        i["server"] = data.get("server", "")
                        i["direct"] = data.get("direct", False)
                        data = i
                    else:
                        insts[n] = data
                    break
            else:
                insts.append(data)
                self._editing_id = data["id"]
            self._set_installations(insts, data["id"])
            self._refresh_inst_combo()
            self._refresh_inst_list()
            self.signals.status.emit(f"versão '{name}' salva")
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"Não salvou: {e}")

    def _delete_installation(self):
        try:
            row = self.inst_list.currentRow()
            insts = self._get_installations()
            if not (0 <= row < len(insts)):
                return
            name = insts[row].get("name", "?")
            del insts[row]
            self._editing_id = None
            self._set_installations(insts, (insts[0].get("id", "") if insts else ""))
            self._refresh_inst_combo()
            self._refresh_inst_list()
            self._new_installation()
            self.signals.status.emit(f"versão '{name}' apagada")
        except Exception:
            pass

    CONTENT_FOLDERS = {"mod": "mods", "resourcepack": "resourcepacks", "shader": "shaderpacks"}
    CONTENT_NAMES = {"mod": "🧩", "resourcepack": "🎨", "shader": "✨"}

    def _versions_opened(self):
        """Ao abrir 🗂 Versões, carrega a versão de ▶ Jogar no editor."""
        try:
            if self._editing_id:
                return
            cur = self._current_inst()
            if not cur:
                return
            for n, i in enumerate(self._get_installations()):
                if i.get("id") == cur.get("id"):
                    self.inst_list.setCurrentRow(n)
                    break
        except Exception:
            pass

    def _editing_inst(self) -> dict | None:
        try:
            for i in self._get_installations():
                if i.get("id") == self._editing_id:
                    return i
        except Exception:
            pass
        return None

    def _refresh_content_list(self):
        try:
            self.content_list.clear()
            inst = self._editing_inst()
            if not inst:
                return
            for c in inst.get("content") or []:
                icon = self.CONTENT_NAMES.get(c.get("kind", "mod"), "•")
                QListWidgetItem(f"{icon} {c.get('title', c.get('slug', '?'))}", self.content_list)
        except Exception:
            pass

    def _content_add(self, inst_id: str, entry: dict):
        try:
            insts = self._get_installations()
            for i in insts:
                if i.get("id") == inst_id:
                    items = [c for c in (i.get("content") or []) if c.get("slug") != entry.get("slug")]
                    items.append(entry)
                    i["content"] = items
                    break
            self._set_installations(insts, inst_id)
            self._refresh_content_list()
            self._refresh_inst_info()
        except Exception:
            pass

    def _remove_content(self):
        try:
            inst = self._editing_inst()
            if not inst:
                QMessageBox.information(self, APP_NAME, "Escolha uma versão na lista acima.")
                return
            row = self.content_list.currentRow()
            items = inst.get("content") or []
            if not (0 <= row < len(items)):
                QMessageBox.information(self, APP_NAME, "Escolha um item do conteúdo.")
                return
            gone = items.pop(row)
            try:
                folder = self.CONTENT_FOLDERS.get(gone.get("kind", "mod"), "mods")
                gdir = self._inst_gamedir(inst)
                f = gdir / folder / gone.get("file", "")
                if f.name and f.exists():
                    f.unlink()
            except Exception:
                pass
            insts = self._get_installations()
            for i in insts:
                if i.get("id") == inst.get("id"):
                    i["content"] = items
                    break
            self._set_installations(insts, inst.get("id", ""))
            self._refresh_content_list()
            self._refresh_inst_info()
            self.signals.status.emit(f"'{gone.get('title', '?')}' removido da versão")
        except Exception:
            pass

    def _play_current(self):
        if normalize_mode(self.mode.currentText()) == MS_MODE:
            self._play_microsoft()
        else:
            self._play_local()

    def _prefill_account(self):
        try:
            cfg = load_cfg()
            nick = (cfg.get("nick") or "").strip()
            mode = normalize_mode(cfg.get("mode") or "")
            if nick:
                self.user.blockSignals(True)
                self.user.setText(nick)
                self.user.blockSignals(False)
                self.mode.setCurrentText(mode)
                if mode == LOCAL_MODE:
                    try:
                        save_local_account(nick)
                    except Exception:
                        pass
            else:
                locals_ = load_local_accounts()
                if locals_:
                    last = list(locals_.keys())[-1]
                    self.user.setText(last)
                    self.mode.setCurrentText(LOCAL_MODE)
                else:
                    accs = load_accounts()
                    if accs:
                        last = list(accs.keys())[-1]
                        self.user.setText(last)
                        self.mode.setCurrentText(MS_MODE)
                    else:
                        self.mode.setCurrentText(LOCAL_MODE)
            self._refresh_play_buttons(self.mode.currentText())
        except Exception:
            pass
        self._refresh_account_labels()

    def _save_identity(self):
        try:
            cfg = load_cfg()
            cfg["nick"] = self.user.text().strip()
            cfg["mode"] = normalize_mode(self.mode.currentText())
            save_cfg(cfg)
        except Exception:
            pass

    def _save_simple(self, key: str, value):
        try:
            cfg = load_cfg()
            cfg[key] = value
            save_cfg(cfg)
        except Exception:
            pass

    @staticmethod
    def _dedicated_gpu_available() -> bool:
        """True se há NVIDIA com offload (prime-run ou nvidia-smi)."""
        try:
            import shutil as _sh
            if _sh.which("prime-run") or _sh.which("nvidia-smi"):
                return True
        except Exception:
            pass
        try:
            from pathlib import Path as _P
            if list(_P("/dev").glob("nvidia*")):
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _gpu_env_extra() -> dict:
        """Offload p/ NVIDIA quando ativado em ⚙️ Config (padrão: auto)."""
        try:
            if (load_cfg().get("gpu", "auto") or "auto") == "integrada":
                return {}
        except Exception:
            pass
        try:
            import shutil as _sh
            if _sh.which("nvidia-smi") or _sh.which("prime-run"):
                return {"__NV_PRIME_RENDER_OFFLOAD": "1",
                        "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
                        "__VK_LAYER_NV_optimus": "NVIDIA_only"}
        except Exception:
            pass
        return {}

    def _snapshots_toggled(self, checked: bool):
        self._save_simple("snapshots", bool(checked))
        self._load_versions()

    def _save_ms_fields(self):
        try:
            cfg = load_cfg()
            cfg["ms_client_id"] = self.client_id.text().strip()
            cfg["ms_redirect"] = self.redirect.text().strip() or "http://localhost:8000"
            save_cfg(cfg)
        except Exception:
            pass

    # ---------- contas salvas ----------
    def _refresh_accounts(self):
        try:
            self.saved_list.clear()
            for name in load_accounts().keys():
                QListWidgetItem(name, self.saved_list)
        except Exception:
            pass
        try:
            self._refresh_local_accounts()
        except Exception:
            pass

    def _use_saved(self):
        try:
            it = self.saved_list.currentItem()
            if not it:
                QMessageBox.information(self, APP_NAME, "Escolha uma conta na lista.")
                return
            self.user.setText(it.text())
            self.mode.setCurrentText(MS_MODE)
            self._refresh_play_buttons(MS_MODE)
            self._refresh_avatar()
            self.pages.setCurrentIndex(0)
        except Exception:
            pass

    # ---------- contas locais ----------
    def _refresh_local_accounts(self):
        try:
            self.local_list.clear()
            for name in load_local_accounts().keys():
                QListWidgetItem(name, self.local_list)
        except Exception:
            pass

    def _local_add(self):
        try:
            nick = self.local_nick.text().strip() or self.user.text().strip()
            if not (3 <= len(nick) <= 16):
                QMessageBox.warning(self, APP_NAME, "Nick com 3–16 letras, senhor.")
                return
            save_local_account(nick)
            self.local_nick.clear()
            self.user.setText(nick)
            self.mode.setCurrentText(LOCAL_MODE)
            self._refresh_play_buttons(LOCAL_MODE)
            self._refresh_local_accounts()
            self._refresh_avatar()
            self.signals.status.emit(f"conta local {nick} pronta ✓")
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"Não criei: {e}")

    def _local_use(self):
        try:
            it = self.local_list.currentItem()
            if not it:
                QMessageBox.information(self, APP_NAME, "Escolha uma conta local.")
                return
            self.user.setText(it.text())
            self.mode.setCurrentText(LOCAL_MODE)
            self._refresh_play_buttons(LOCAL_MODE)
            self._refresh_avatar()
            self.pages.setCurrentIndex(0)
        except Exception:
            pass

    def _local_del(self):
        try:
            it = self.local_list.currentItem()
            if not it:
                QMessageBox.information(self, APP_NAME, "Escolha uma conta local.")
                return
            name = it.text()
            if QMessageBox.question(self, APP_NAME, f"Apagar conta local {name}?",
                                    QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                return
            remove_local_account(name)
            self._refresh_local_accounts()
        except Exception:
            pass

    # ---------- helpers ----------
    def _log(self, msg: str):
        if msg.startswith("__VERSIONS__:"):
            self._apply_versions_from_log(msg)
            return
        if msg.startswith("__LOADERS__:"):
            self._apply_loaders_from_log(msg)
            return
        if msg.startswith("__MODSUP__:"):
            self._apply_modsup_from_log(msg)
            return
        if msg.startswith("__SERVER_STATUS__:"):
            try:
                self.server_status.setText(msg.split("__SERVER_STATUS__:", 1)[1])
            except Exception:
                pass
            return
        if msg.startswith("__AVATAR__:"):
            try:
                self._apply_avatar(msg.split("__AVATAR__:", 1)[1])
            except Exception:
                pass
            return
        if msg.startswith("__NEWS__:"):
            try:
                self.news_label.setText(msg.split("__NEWS__:", 1)[1])
            except Exception:
                pass
            return
        if msg == "__PING_DONE__":
            try:
                self.b_ping.setEnabled(True)
            except Exception:
                pass
            return
        if msg.startswith("__CONTENT_ADDED__:"):
            try:
                parts = msg.split("__CONTENT_ADDED__:", 1)[1].split(":", 4)
                inst_id, kind, slug, fname = parts[0], parts[1], parts[2], parts[3]
                title = parts[4] if len(parts) > 4 else slug
                self._content_add(inst_id, {"slug": slug, "title": title,
                                            "kind": kind, "file": fname})
            except Exception:
                pass
            return
        if msg == "__MP_INSTALL_DONE__":
            try:
                self.b_mp_install.setEnabled(True)
                if self.mp_status.text().endswith("…"):
                    self.mp_status.setText("pronto ✓")
            except Exception:
                pass
            return
        if msg.startswith("__UPDATES__:"):
            try:
                n = int(msg.split("__UPDATES__:", 1)[1])
                self.b_check_updates.setEnabled(True)
                self.b_update_all.setEnabled(n > 0)
                self.mp_status.setText(f"{n} update(s)" if n else "tudo atualizado ✓")
            except Exception:
                pass
            return
        if msg == "__UPDATES_DONE__":
            try:
                self.b_update_all.setEnabled(False)
                self.mp_status.setText("pronto ✓")
            except Exception:
                pass
            return
        if msg.startswith("__DEVICE_OK__:"):
            try:
                name = msg.split("__DEVICE_OK__:", 1)[1]
                self.user.setText(name)
                self.mode.setCurrentText("Microsoft")
                self._refresh_play_buttons("Microsoft")
                self._refresh_accounts()
                self._refresh_avatar()
                self.device_status.setText(f"✓ Logado como {name} — pode jogar.")
                self.signals.status.emit(f"logado: {name}")
            except Exception:
                pass
            return
        if msg.startswith("__DEVICE_FAIL__:"):
            try:
                self.device_status.setText(f"⚠ {msg.split('__DEVICE_FAIL__:', 1)[1]}")
            except Exception:
                pass
            return
        if msg == "__DEVICE_DONE__":
            try:
                self.b_device.setEnabled(True)
                self.b_device_cancel.setEnabled(False)
            except Exception:
                pass
            return
        if msg == "__BACKUP_EMPTY__":
            try:
                self.b_backup.setEnabled(True)
                self.backup_status.setText("Nenhum mundo ainda — jogue e salve um mundo primeiro.")
            except Exception:
                pass
            return
        if msg.startswith("__BACKUP_DONE__:"):
            try:
                self.b_backup.setEnabled(True)
                name = msg.split("__BACKUP_DONE__:", 1)[1]
                self.backup_status.setText(f"✓ {name} guardado em backups/ (máx. 10).")
                self.signals.status.emit("backup pronto ✓")
            except Exception:
                pass
            return
        if msg.startswith("__BACKUP_FAIL__:"):
            try:
                self.b_backup.setEnabled(True)
                self.backup_status.setText(f"⚠ {msg.split('__BACKUP_FAIL__:', 1)[1]}")
            except Exception:
                pass
            return
        if msg.startswith("__MODPACKS__:") or msg == "__MP_SEARCH_DONE__":
            self._apply_modpacks_from_log(msg)
            return
        if msg.startswith("__MODPACK_DONE__:"):
            try:
                parts = msg.split("__MODPACK_DONE__:", 1)[1].split(":", 1)
                if len(parts) != 2:
                    return
                slug, ver = parts
            except ValueError:
                return
            try:
                import time as _t
                insts = self._get_installations()
                data = {
                    "id": f"mp-{int(_t.time())}", "type": "modpack",
                    "name": f"{slug} (modpack)", "mc": self._mp_mc or "?",
                    "loader": "", "loader_ver": "", "mods": {},
                    "server": "", "direct": False, "launch": ver,
                    "gamedir": str(modpack_dir(slug)),
                }
                insts.append(data)
                self._set_installations(insts, data["id"])
                self._refresh_inst_combo()
                self._refresh_inst_list()
                self.mp_status.setText(f"✓ {slug} virou uma versão! Indo para ▶ Jogar…")
                self.pages.setCurrentIndex(0)
            except Exception:
                pass
            return
        try:
            self.logview.append(msg)
        except Exception:
            pass

    def _on_status(self, msg: str):
        pass

    def _load_versions(self):
        def work():
            try:
                self.signals.status.emit("buscando versões…")
                kind = "all" if self.snapshots.isChecked() else "release"
                vs = list_versions(kind)
                ids = [v["id"] for v in vs[:150]]
                lr = ""
                try:
                    lr = latest_release()
                except Exception:
                    pass
                self.signals.log.emit(f"__VERSIONS__:{len(ids)}:{lr}:" + ",".join(ids))
                self.signals.status.emit(f"{len(ids)} versões" + (f" • última: {lr}" if lr else ""))
            except Exception as e:
                self.signals.log.emit(f"⚠ erro ao listar versões: {e}")
        threading.Thread(target=work, daemon=True).start()

    def _apply_versions_from_log(self, msg: str):
        try:
            _, rest = msg.split("__VERSIONS__:", 1)
            n, lr, ids_s = rest.split(":", 2)
            ids = [i for i in ids_s.split(",") if i]
            self.version.blockSignals(True)
            self.version.clear()
            self.version.addItems(ids)
            self.version.blockSignals(False)
            if lr and lr in ids:
                self.version.setCurrentText(lr)
            try:  # mesmo catálogo no filtro da loja
                keep = self._store_search_mc()
                self.store_mc.blockSignals(True)
                self.store_mc.clear()
                self.store_mc.addItem("todas", "")
                for i in ids:
                    self.store_mc.addItem(i, i)
                if keep and keep in ids:
                    self.store_mc.setCurrentIndex(self.store_mc.findData(keep))
                self.store_mc.blockSignals(False)
            except Exception:
                pass
            self._maybe_seed_defaults(lr)
            self._refresh_inst_list()
        except Exception:
            pass

    def _load_loader_versions(self):
        if not hasattr(self, "loader"):
            return
        loader = self.loader.currentText()
        mc = self.version.currentText()
        if loader == "vanilla" or not mc:
            try:
                self.loader_ver.clear()
            except Exception:
                pass
            try:  # versão pura: nenhum mod se aplica
                self._apply_modsupport(loader or "vanilla", mc,
                                       {s: "0" for s in self.e_mod_checks})
            except Exception:
                pass
            return

        def work(loader=loader, mc=mc):
            try:
                vs = loader_versions(loader, mc)
                self.signals.log.emit(f"__LOADERS__:{loader}:{mc}:" + ",".join(vs[:30]))
                if vs:
                    self.signals.log.emit(f"✓ {loader}: {len(vs)} builds para {mc}")
                else:
                    self.signals.log.emit(f"ℹ {loader} ainda sem build para {mc}.")
            except Exception:
                self.signals.log.emit(f"ℹ {loader} sem suporte para {mc}.")
                self.signals.log.emit(f"__LOADERS__:{loader}:{mc}:")
            try:  # compatibilidade dos mods de FPS com (mc, loader)
                try:
                    slugs = list(self.e_mod_checks.keys())
                except Exception:
                    slugs = []
                if slugs:
                    self.signals.log.emit(f"__MODSUP__:{loader}:{mc}:" + ",".join(
                        f"{s}={self._modsup_one(s, mc, loader)}" for s in slugs))
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()

    @staticmethod
    def _modsup_one(slug: str, mc: str, loader: str) -> str:
        """'1' compatível, '0' incompatível, '?' offline."""
        try:
            lds = [loader]
            if slug == "fabric-api" and loader in ("fabric", "quilt"):
                lds = ["fabric", "quilt"]
            r = compat_status(slug, mc, lds)
            return "1" if r is True else ("0" if r is False else "?")
        except Exception:
            return "?"

    def _apply_modsupport(self, loader: str, mc: str, d: dict):
        """Apaga (desativa) os mods sem build p/ (mc, loader)."""
        try:
            n_ok = 0
            for slug, cb in self.e_mod_checks.items():
                v = d.get(slug, "?")
                if v == "1":
                    n_ok += 1
                    cb.setEnabled(True)
                    try:
                        cb.setToolTip(self._mod_tips.get(slug, ""))
                    except Exception:
                        pass
                elif v == "0":
                    cb.setEnabled(False)
                    if cb.isChecked():
                        cb.setChecked(False)
                    why = "versão pura (sem loader)" if loader == "vanilla" else f"sem build para {mc} {loader}"
                    cb.setToolTip(f"Indisponível — {why}.")
                else:
                    cb.setEnabled(True)
                    try:
                        cb.setToolTip((self._mod_tips.get(slug, "") + " (não verificado — offline?)").strip())
                    except Exception:
                        pass
                    n_ok += 1
            try:
                if loader == "vanilla":
                    self.e_mods_lbl.setText("Mods de FPS (versão pura — nenhum se aplica):")
                else:
                    self.e_mods_lbl.setText(f"Mods de FPS ({n_ok} compatíveis com {mc} {loader}):")
            except Exception:
                pass
        except Exception:
            pass

    def _apply_modsup_from_log(self, msg: str):
        try:
            _, rest = msg.split("__MODSUP__:", 1)
            loader, mc, pairs = rest.split(":", 2)
            if self.loader.currentText() != loader or self.version.currentText().strip() != mc:
                return  # resposta velha — o senhor já trocou de versão
            d = dict(p.split("=") for p in pairs.split(",") if "=" in p)
            self._apply_modsupport(loader, mc, d)
        except Exception:
            pass

    def _apply_loaders_from_log(self, msg: str):
        try:
            _, rest = msg.split("__LOADERS__:", 1)
            parts = rest.split(":")
            vs = [v for v in parts[2].split(",") if v] if len(parts) > 2 else []
            self.loader_ver.clear()
            self.loader_ver.addItems(vs)
        except Exception:
            pass

    # ---------- loja ----------
    def _store_kind(self) -> str:
        try:
            return self.store_type.currentData() or "modpack"
        except Exception:
            return "modpack"

    def _store_mc_loader(self):
        """(mc, loader) da versão escolhida em ▶ Jogar."""
        try:
            cur = self._current_inst()
            if cur and cur.get("type") == "standard":
                return (cur.get("mc", "") or "", cur.get("loader", "vanilla") or "vanilla")
            if cur and cur.get("type") == "modpack":
                return (cur.get("mc", "") or "",
                        self._loader_from_launch(cur.get("launch", "")) or "")
        except Exception:
            pass
        try:
            return (self.version.currentText(), "vanilla")
        except Exception:
            return ("", "vanilla")

    @staticmethod
    def _loader_from_launch(launch: str) -> str:
        """Adivinha o loader pelo id de launch (vale p/ modpacks)."""
        try:
            low = (launch or "").lower()
            for cand in ("fabric", "quilt", "forge", "neoforge"):
                if cand in low:
                    return cand
        except Exception:
            pass
        return ""

    def _refresh_store_target(self):
        try:
            kind = self._store_kind()
            mc, loader = self._store_mc_loader()
            picked = ""
            try:
                picked = self._store_search_mc()
            except Exception:
                picked = ""
            show_mc = picked or mc
            if mc and mc != getattr(self, "_last_target_mc", ""):
                self._last_target_mc = mc
                try:
                    # Só espelha a versão de ▶ Jogar se o senhor ainda não escolheu outra no filtro.
                    if not picked:
                        idx = self.store_mc.findData(mc)
                        self.store_mc.blockSignals(True)
                        if idx >= 0:
                            self.store_mc.setCurrentIndex(idx)
                        else:
                            self.store_mc.setEditText(mc)
                        self.store_mc.blockSignals(False)
                except Exception:
                    pass
            fmc = show_mc
            onde = f" (para {fmc})" if fmc else ""
            if kind == "modpack":
                self.store_target.setText("Modpacks viram uma versão sua ao instalar." + onde)
            elif kind == "mod":
                aviso = "" if loader in ("fabric", "quilt", "forge", "neoforge") else " (use uma versão com loader — veja 🗂 Versões)"
                self.store_target.setText(f"Mods para: {show_mc or '?'} • {loader}{aviso}{onde}")
            else:
                nome = {"resourcepack": "Texturas", "shader": "Shaders"}.get(kind, kind)
                self.store_target.setText(f"{nome} para: Minecraft {show_mc or '?'}{onde}")
        except Exception:
            pass

    def _store_search_mc(self) -> str:
        """Filtro de MC da busca (combo da loja). '' = todas."""
        try:
            d = self.store_mc.currentData()
            if d:
                return d
            t = self.store_mc.currentText().strip()
            if not t or t.lower().startswith("todas"):
                return ""
            return t
        except Exception:
            return ""

    def _mp_do_search(self):
        q = self.mp_search.text().strip()
        kind = self._store_kind()
        # O filtro da loja manda na busca; vazio = segue a versão de ▶ Jogar.
        mc, loader = self._store_mc_loader()
        try:
            picked = self._store_search_mc()
        except Exception:
            picked = ""
        search_mc = picked or mc
        loaders: list[str] | None = None
        if kind == "mod" and loader in ("fabric", "quilt", "forge", "neoforge"):
            loaders = [loader]
        self.b_mp_search.setEnabled(False)
        self.mp_status.setText(f"buscando para {search_mc or '…'}…")

        def work(query=q, kind=kind, mc=search_mc, loaders=loaders):
            try:
                hits = search_projects(query, kind, 12, loaders=loaders, game_version=mc)
                self._mp_hits = hits
                icons: dict = {}
                try:
                    cdir = Path.home() / ".salsicha-launcher" / "icons" / "store"
                    for h in hits:
                        slug, url = h.get("slug", ""), h.get("icon_url", "")
                        if slug and url:
                            p = download_icon(url, cdir, slug)
                            if p:
                                icons[slug] = str(p)
                except Exception:
                    pass
                self._mp_icons = icons
                slugs = [h.get("slug", "") for h in hits]
                self.signals.log.emit("__MODPACKS__:" + ",".join(slugs))
                self.signals.status.emit(f"{len(hits)} achados")
            except Exception as e:
                self.signals.log.emit(f"⚠ busca falhou: {e}")
            finally:
                self.signals.log.emit("__MP_SEARCH_DONE__")
        threading.Thread(target=work, daemon=True).start()

    def _apply_modpacks_from_log(self, msg: str):
        if msg == "__MP_SEARCH_DONE__":
            try:
                self.b_mp_search.setEnabled(True)
                self.mp_status.setText(f"{len(self._mp_hits)} achados (2 cliques instala)")
            except Exception:
                pass
            return
        if not msg.startswith("__MODPACKS__:"):
            return
        try:
            self.mp_list.clear()
            by_slug = {h.get("slug", ""): h for h in self._mp_hits}
            rest = msg.split("__MODPACKS__:", 1)[1]
            for slug in [s for s in rest.split(",") if s]:
                h = by_slug.get(slug, {})
                title = h.get("title", slug)
                dl = h.get("downloads", 0)
                desc = (h.get("description") or "")[:90]
                item = QListWidgetItem(f"{title}\n⬇ {dl:,} • {desc}".replace(",", "."))
                item.setData(Qt.UserRole, slug)
                item.setToolTip((h.get("description") or "")[:200])
                try:
                    icon = (self._mp_icons or {}).get(slug, "")
                    if icon and Path(icon).exists():
                        item.setIcon(QIcon(icon))
                except Exception:
                    pass
                self.mp_list.addItem(item)
        except Exception:
            pass

    def _mp_install(self):
        it = self.mp_list.currentItem()
        kind = self._store_kind()
        nomes = {"modpack": "um modpack", "mod": "um mod",
                 "resourcepack": "uma textura", "shader": "um shader"}
        if not it:
            QMessageBox.information(self, APP_NAME, f"Escolha {nomes.get(kind, 'um item')} na lista.")
            return
        if kind == "modpack":
            self._install_modpack(it.data(Qt.UserRole))
        else:
            self._install_store_file(it.data(Qt.UserRole), kind)

    def _install_modpack(self, slug: str):
        cur = self._current_inst()
        mc = (cur.get("mc", "") if cur and cur.get("type") == "standard" else "") or self.version.currentText().strip()
        if not mc:
            QMessageBox.warning(self, APP_NAME, "A lista do Minecraft ainda está carregando. Aguarde.")
            return
        self._mp_mc = mc
        self.b_mp_install.setEnabled(False)
        self.mp_status.setText(f"instalando {slug}…")
        if not self.show_console.isChecked():
            self.show_console.setChecked(True)

        def work(slug=slug, mc=mc):
            s = self.signals
            try:
                url = latest_mrpack_version_url(slug, mc)
                if not url:
                    try:
                        from .discover import mrpack_release as _rel
                        _r = _rel(slug, "")
                        sup = ", ".join((_r.get("mc") or [])[:8]) if _r else ""
                    except Exception:
                        sup = ""
                    detalhe = f" Suporta: {sup}." if sup else ""
                    s.log.emit(f"⚠ {slug}: sem .mrpack para {mc}.{detalhe}")
                    s.status.emit(f"{slug} não suporta {mc}")
                    return
                cb = {
                    "setStatus": lambda t: s.log.emit("• " + str(t)),
                    "setProgress": lambda v: s.progress.emit(int(v)),
                    "setMax": lambda v: s.max.emit(int(v)),
                }
                ver = install_mrpack_from_url(
                    url, slug, Path(get_minecraft_dir()),
                    Path.home() / ".salsicha-launcher" / "modpacks",
                    log=lambda m: s.log.emit(str(m)), progress_cb=cb)
                s.log.emit(f"__MODPACK_DONE__:{slug}:{ver}")
                s.status.emit(f"modpack {slug} pronto")
            except Exception as e:
                s.log.emit(f"⚠ ERRO no modpack: {e}")
            finally:
                s.log.emit("__MP_INSTALL_DONE__")
        threading.Thread(target=work, daemon=True).start()

    def _install_store_file(self, slug: str, kind: str):
        cur = self._current_inst()
        if not cur:
            QMessageBox.warning(self, APP_NAME, "Escolha uma versão em ▶ Jogar primeiro.")
            self.pages.setCurrentIndex(0)
            return
        is_mp = cur.get("type") == "modpack"
        mc, loader = self._store_mc_loader()
        nomes = {"mod": "mod", "resourcepack": "textura", "shader": "shader"}
        if not mc:
            QMessageBox.warning(self, APP_NAME, "A lista do Minecraft ainda está carregando. Aguarde.")
            return
        if kind == "mod" and loader not in ("fabric", "quilt", "forge", "neoforge"):
            if is_mp:
                QMessageBox.warning(
                    self, APP_NAME,
                    "Não identifiquei o loader deste modpack.\nMods manuais vão para 🗂 Versões normais.")
            else:
                QMessageBox.warning(
                    self, APP_NAME,
                    "Mods precisam de uma versão com loader (Fabric, Quilt, Forge ou NeoForge).\nCrie uma em 🗂 Versões.")
            self.pages.setCurrentIndex(1)
            return
        title = slug
        try:
            for h in self._mp_hits:
                if h.get("slug") == slug:
                    title = h.get("title", slug)
                    break
        except Exception:
            pass
        if kind == "mod":
            loaders = [loader]
        elif kind == "resourcepack":
            loaders = ["minecraft"]
        else:  # shader: iris/optifine/etc — qualquer loader, só a MC importa
            loaders: list[str] = []
        pasta = self.CONTENT_FOLDERS[kind]
        inst_id = cur.get("id", "")
        inst_name = cur.get("name", mc)
        try:
            gdir = self._inst_gamedir(cur)
            (gdir / pasta).mkdir(parents=True, exist_ok=True)
        except Exception:
            gdir = Path(get_minecraft_dir())
        self.b_mp_install.setEnabled(False)
        self.mp_status.setText(f"baixando {slug} para {mc}…")

        def work(slug=slug, mc=mc, loaders=loaders, pasta=pasta, kind=kind,
                 title=title, inst_id=inst_id, inst_name=inst_name, gdir=gdir):
            s = self.signals
            try:
                found = latest_compat_file(slug, mc, loaders)
                if not found:
                    try:
                        from .modrinth import supported_versions as _sup
                        sup = _sup(slug)
                    except Exception:
                        sup = []
                    detalhe = f" Suporta: {', '.join(sup[:8])}." if sup else ""
                    s.log.emit(f"⚠ {slug}: sem arquivo para {mc} (versão '{inst_name}').{detalhe}")
                    s.status.emit(f"{slug} não suporta {mc}")
                    return
                fname, url = found
                dest = gdir / pasta / fname
                if dest.exists():
                    s.log.emit(f"✓ {fname} já instalado.")
                else:
                    if kind == "mod":
                        for old in dest.parent.glob(f"{slug}*.jar"):
                            try:
                                old.unlink()
                            except Exception:
                                pass
                    if not download_url_to(url, dest, log=lambda m: s.log.emit(str(m))):
                        return
                    s.log.emit(f"✓ {nomes[kind]} instalado: {fname}")
                s.log.emit(f"__CONTENT_ADDED__:{inst_id}:{kind}:{slug}:{fname}:{title}")
                s.status.emit(f"{slug} pronto")
            except Exception as e:
                s.log.emit(f"⚠ ERRO na loja: {e}")
            finally:
                s.log.emit("__MP_INSTALL_DONE__")
        threading.Thread(target=work, daemon=True).start()

    def _check_updates(self):
        cur = self._current_inst()
        if not cur or cur.get("type") != "standard":
            QMessageBox.information(self, APP_NAME, "Escolha uma versão normal em ▶ Jogar.")
            return
        mc, loader = self._store_mc_loader()
        if not mc or loader not in ("fabric", "quilt", "forge", "neoforge"):
            QMessageBox.information(
                self, APP_NAME, "Updates valem para versões com loader e MC conhecida.")
            return
        self.b_check_updates.setEnabled(False)
        self.b_update_all.setEnabled(False)
        self.mp_status.setText("checando updates…")
        if not self.show_console.isChecked():
            self.show_console.setChecked(True)

        def work(mc=mc, loader=loader, inst=dict(cur)):
            s = self.signals
            try:
                mods_dir = self._inst_gamedir(inst) / "mods"
                wanted = {slug for slug, w in (inst.get("mods") or {}).items() if w}
                store = {c.get("slug"): c for c in (inst.get("content") or [])
                         if c.get("kind", "mod") == "mod" and c.get("slug")}
                found: list = []
                if mods_dir.exists():
                    for f in mods_dir.glob("*.jar"):
                        slug = None
                        for w in wanted:
                            if f.name.lower().startswith(w.lower()):
                                slug = w
                                break
                        if slug is None:
                            for sl in store:
                                if sl.lower() in f.name.lower():
                                    slug = sl
                                    break
                        if slug is None:
                            continue
                        try:
                            up = check_mod_updates(slug, mc, loader, f.name)
                        except Exception:
                            up = None
                        if up:
                            up["dest_dir"] = str(mods_dir)
                            found.append(up)
                self._updates = found
                if found:
                    names = ", ".join(u["slug"] for u in found)
                    s.log.emit(f"⬆ {len(found)} update(s): {names}")
                    for u in found:
                        s.log.emit(f"  • {u['slug']}: {u['old']} → {u['new']}")
                else:
                    s.log.emit("✓ Tudo atualizado para " + mc + ".")
                s.log.emit(f"__UPDATES__:{len(found)}")
            except Exception as e:
                s.log.emit(f"⚠ checagem falhou: {e}")
                s.log.emit("__UPDATES__:0")
        threading.Thread(target=work, daemon=True).start()

    def _update_all(self):
        if not self._updates:
            return
        self.b_update_all.setEnabled(False)
        self.mp_status.setText("atualizando…")

        def work(items=list(self._updates)):
            s = self.signals
            try:
                from .modrinth import download_url_to as _dl
                n = 0
                for u in items:
                    dest = Path(u["dest_dir"]) / u["new"]
                    old = Path(u["dest_dir"]) / u["old"]
                    if _dl(u["url"], dest, log=lambda m: s.log.emit(str(m))):
                        try:
                            if old.exists() and old != dest:
                                old.unlink()
                        except Exception:
                            pass
                        n += 1
                self._updates = []
                s.log.emit(f"✓ {n} mod(s) atualizados.")
            except Exception as e:
                s.log.emit(f"⚠ update falhou: {e}")
            finally:
                s.log.emit("__UPDATES_DONE__")
        threading.Thread(target=work, daemon=True).start()

    # ---------- microsoft ----------
    def _ms_step1(self):
        try:
            self._save_ms_fields()
        except Exception:
            pass
        cid = self.client_id.text().strip()
        red = self.redirect.text().strip() or "http://localhost:8000"
        if not cid:
            QMessageBox.warning(
                self, APP_NAME,
                "Preencha o Client ID do seu app Azure.\n\n"
                "A Salsicha nunca pede sua senha — o login acontece no site da Microsoft.")
            return
        try:
            url, state, verifier = get_login_url(cid, red)
            self._ms_state = {"client_id": cid, "redirect": red, "verifier": verifier}
            self._log("🌐 Abrindo login.microsoftonline.com no seu navegador…")
            self._log("Confira o cadeado e o domínio antes de digitar a senha.")
            webbrowser.open(url)
            self.signals.status.emit("aguardando você no navegador…")
        except Exception as e:
            self._log(f"⚠ erro no login: {e}")

    def _ms_step2(self):
        try:
            st = self._ms_state
            code_raw = self.code.text().strip()
            if not st or not code_raw:
                QMessageBox.warning(self, APP_NAME, "Passo 1 primeiro, depois cole o retorno.")
                return
            code = extract_code_from_url(code_raw)
            data = complete_login(st["client_id"], None, st["redirect"], code, st["verifier"])
            data["_client_id"] = st["client_id"]
            data["_redirect"] = st["redirect"]
            save_account(data["name"], data)
            self.user.setText(data["name"])
            self.mode.setCurrentText("Microsoft")
            self._refresh_play_buttons("Microsoft")
            self._refresh_accounts()
            self._refresh_avatar()
            self._log(f"✓ Logado como {data['name']} — senha nunca passou por aqui.")
            self.signals.status.emit(f"logado: {data['name']}")
            self.code.clear()
        except Exception as e:
            self._log(f"⚠ falha ao concluir login: {e}\nVerifique se colou a URL completa de retorno.")

    # ---------- microsoft fácil (código de dispositivo) ----------
    def _device_step1(self):
        try:
            info = device_start()
        except Exception as e:
            self.device_status.setText(f"⚠ Não gerou o código: {e}")
            return
        self._device_code = info.get("device_code", "")
        self._device_cancel = False
        code = info.get("user_code", "?")
        uri = info.get("verification_uri", "microsoft.com/link")
        interval = int(info.get("interval", 5))
        self.device_status.setText(f"Digite {code} em {uri} — já abri no navegador.")
        try:
            webbrowser.open(f"https://{uri}" if "://" not in uri else uri)
        except Exception:
            pass
        self.b_device.setEnabled(False)
        self.b_device_cancel.setEnabled(True)
        self._log(f"🔑 Código Microsoft: {code} (confirme em {uri})")

        def work(device_code=self._device_code, step=interval):
            import time as _t
            s = self.signals
            try:
                while not getattr(self, "_device_cancel", False):
                    _t.sleep(max(step, 3))
                    if getattr(self, "_device_cancel", False):
                        break
                    try:
                        tokens = device_poll(device_code)
                    except DevicePending:
                        continue
                    except (DeviceDeclined, DeviceExpired) as e:
                        s.log.emit(f"__DEVICE_FAIL__:{e}")
                        return
                    try:
                        data = device_complete(tokens)
                    except (DeviceDeclined, DeviceExpired, XboxError) as e:
                        s.log.emit(f"__DEVICE_FAIL__:{e}")
                        return
                    save_account(data["name"], data)
                    s.log.emit(f"__DEVICE_OK__:{data['name']}")
                    return
            except (DeviceDeclined, DeviceExpired) as e:
                s.log.emit(f"__DEVICE_FAIL__:{e}")
            except Exception as e:
                s.log.emit(f"__DEVICE_FAIL__:{e}")
            finally:
                s.log.emit("__DEVICE_DONE__")
        threading.Thread(target=work, daemon=True).start()

    def _device_cancel(self):
        self._device_cancel = True
        self.device_status.setText("Cancelado — gere outro código quando quiser.")
        self.b_device.setEnabled(True)
        self.b_device_cancel.setEnabled(False)

    # ---------- mods + servidores ----------
    def _save_mods(self):
        try:
            cfg = load_cfg()
            cfg["mods"] = {s: cb.isChecked() for s, cb in self.mod_checks.items()}
            save_cfg(cfg)
        except Exception:
            pass

    def _ping_server(self):
        data = self.server.currentData()
        if not data:
            self.server_status.setText("Mundo local selecionado — nada para pingar.")
            return
        host, port = data["host"], int(data.get("port", 25565))
        self.server_status.setText(f"Pingando {host}…")
        self.b_ping.setEnabled(False)

        def work(h=host, p=port, name=data["name"]):
            try:
                r = ping_server(h, p)
                if r["online"]:
                    msg = f"🟢 {name}: {r['players']}/{r['max']} online • {r['version']} • {r['motd']}"
                else:
                    msg = f"🔴 {name}: offline ({r['motd']})"
                self.signals.log.emit(msg)
                self.signals.status.emit(msg)
                self.signals.log.emit(f"__SERVER_STATUS__:{msg}")
            except Exception as e:
                self.signals.log.emit(f"⚠ ping falhou: {e}")
            finally:
                self.signals.log.emit("__PING_DONE__")
        threading.Thread(target=work, daemon=True).start()

    def _quit_for_game(self):
        """Fecha o launcher (o vigia reabre ao sair do jogo)."""
        try:
            app = QApplication.instance()
            if app is not None:
                app.quit()
        except Exception:
            pass

    @staticmethod
    def _spawn_reopen_watcher(pid: int) -> bool:
        """Vigia destacado: quando o jogo morre, relança o Salsicha e sai."""
        import subprocess as _sp
        import sys as _sys
        from pathlib import Path as _P
        try:
            root = _P(__file__).resolve().parent.parent
            cmd = [str(_P.home() / ".local" / "bin" / "salsicha-launcher")]
            if not _P(cmd[0]).exists():
                cmd = [_sys.executable, str(root / "main.py")]
            watcher = "\n".join([
                "import subprocess as s, sys, time, os",
                "pid = int(sys.argv[1])",
                "cmd = sys.argv[2:]",
                "while True:",
                "    try:",
                "        os.kill(pid, 0)",
                "    except Exception:",
                "        break",
                "    time.sleep(3)",
                "s.Popen(cmd, start_new_session=True,",
                "        stdout=s.DEVNULL, stderr=s.DEVNULL, stdin=s.DEVNULL)",
            ])
            _sp.Popen([_sys.executable, "-c", watcher, str(pid), *cmd],
                      start_new_session=True, stdin=_sp.DEVNULL,
                      stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
            return True
        except Exception:
            return False

    # ---------- jogar (usa a versão escolhida, estilo TLauncher) ----------
    @staticmethod
    def _inst_fingerprint(inst: dict) -> str:
        """Assinatura do que precisa estar instalado (mudou → reinstala; igual → vai direto)."""
        import hashlib as _h
        import json as _j
        try:
            payload = {"mc": inst.get("mc", ""), "loader": inst.get("loader", "vanilla"),
                       "loader_ver": inst.get("loader_ver", ""),
                       "mods": inst.get("mods") or {},
                       "content": [(c.get("slug"), c.get("file"), c.get("kind"))
                                   for c in (inst.get("content") or [])]}
            return _h.sha1(_j.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]
        except Exception:
            return ""

    def _inst_gamedir(self, inst: dict) -> Path:
        """Pasta de jogo da instalação (modpack usa a própria; senão instances/<id>)."""
        try:
            if inst.get("type") == "modpack":
                g = Path(inst.get("gamedir") or "")
                if g.name and g.exists():
                    return g
        except Exception:
            pass
        return game_dir_for(inst)

    def _run_game(self, options: dict):
        inst = self._current_inst()
        if not inst:
            QMessageBox.warning(self, APP_NAME, "Crie uma versão primeiro em 🗂 Versões.")
            self.pages.setCurrentIndex(1)
            return
        ram = self.ram.value()
        is_mp = inst.get("type") == "modpack"
        ver = inst.get("mc", "")
        loader = inst.get("loader", "vanilla") or "vanilla"
        loader_ver = (inst.get("loader_ver") or "").strip()
        mods_sel = inst.get("mods") or {}
        srv_host = inst.get("server") or None
        if not inst.get("direct"):
            srv_host = None
        srv_port = 25565
        # Override global da aba 🌐 Servidores: se marcado, vale mais que o da versão.
        try:
            g = self.server.currentData() if hasattr(self, "server") else None
            if g and hasattr(self, "direct") and self.direct.isChecked():
                srv_host = g.get("host")
                srv_port = int(g.get("port", 25565))
        except Exception:
            pass
        if not ver and not (is_mp and inst.get("launch")):
            QMessageBox.warning(self, APP_NAME, "A lista do Minecraft ainda está carregando. Aguarde.")
            return
        try:  # última versão jogada (volta nela ao abrir)
            self._set_installations(self._get_installations(), inst.get("id", ""))
        except Exception:
            pass
        if not self.show_console.isChecked():
            self.show_console.setChecked(True)

        def work():
            s = self.signals
            try:
                cb = {
                    "setStatus": lambda t: s.log.emit("• " + str(t)),
                    "setProgress": lambda v: s.progress.emit(int(v)),
                    "setMax": lambda v: s.max.emit(int(v)),
                }
                # Pasta própria da instalação (mundos isolados por versão)
                try:
                    if is_mp:
                        gdir = self._inst_gamedir(inst)
                        gdir.mkdir(parents=True, exist_ok=True)
                    else:
                        gdir = ensure_instance(inst, log=lambda m: s.log.emit(str(m)))
                except Exception:
                    gdir = Path(get_minecraft_dir())
                if is_mp:
                    label = f"📦 {inst.get('name')}"
                    if srv_host:
                        label += f" → {srv_host}"
                    s.status.emit(f"preparando {label}…")
                    real_ver = inst.get("launch") or ver
                    # Java do modpack: deriva a MC do id de launch ("...-1.21") ou usa a MC base
                    try:
                        import re as _re
                        _m = _re.search(r"1\.\d+(?:\.\d+)?", str(real_ver))
                        _mc_guess = _m.group(0) if _m else (ver if ver and ver != "?" else "")
                        if _mc_guess:
                            from .java_utils import get_java_for_mc as _gj, required_java_major as _jm2
                            _j2 = _gj(_mc_guess)
                            if _j2:
                                options["executablePath"] = _j2
                                s.log.emit(f"☕ Java {_jm2(_mc_guess)} para {_mc_guess}: {_j2}")
                    except Exception:
                        pass
                else:
                    label = ver if loader == "vanilla" else f"{ver} + {loader} {loader_ver or 'latest'}"
                    if srv_host:
                        label += f" → {srv_host}"
                    fp = self._inst_fingerprint(inst)
                    inst_launch = inst.get("installed_launch", "")
                    if (fp and inst.get("installed_fp") == fp and inst_launch
                            and (Path(get_minecraft_dir()) / "versions" / inst_launch).exists()):
                        s.status.emit(f"preparando {label}…")
                        s.log.emit("✓ Versão pronta — indo direto, sem baixar nada.")
                        real_ver = inst_launch
                    else:
                        s.status.emit(f"preparando {label}…")
                        # Java certo para a MC (1.8→8, 26.x→21), via runtime da Mojang
                        try:
                            from .java_utils import get_java_for_mc, required_java_major as _jm
                            _j = get_java_for_mc(ver)
                            if _j:
                                options["executablePath"] = _j
                                s.log.emit(f"☕ Java {_jm(ver)} para {ver}: {_j}")
                        except Exception:
                            pass
                        # Aviso honesto p/ MC antiga no Wayland (LWJGL2 trava sem X11/xrandr).
                        try:
                            import os as _os
                            import shutil as _sh
                            _parts = [int(p) for p in str(ver).split(".") if p.isdigit()]
                            _old = len(_parts) >= 2 and _parts[0] == 1 and _parts[1] <= 12
                            if _old:
                                if not _sh.which("xrandr"):
                                    s.log.emit("⚠ MC ≤1.12 usa motor gráfico antigo (LWJGL2): instale o xrandr — `sudo pacman -S xorg-xrandr` — e se travar, jogue numa sessão X11 (Xorg) em vez de Wayland.")
                                elif (_os.environ.get("WAYLAND_DISPLAY") or "") and not (_os.environ.get("DISPLAY") or ""):
                                    s.log.emit("⚠ MC ≤1.12 no Wayland puro trava (tela preta/crash). Se falhar, entre numa sessão X11 no login.")
                        except Exception:
                            pass
                        if mods_sel and loader in ("fabric", "quilt", "forge", "neoforge"):
                            try:
                                # Save antigo de Forge sem as chaves do pack: completa com o padrão.
                                if loader == "forge":
                                    try:
                                        from .modrinth import FORGE_PERF_MODS as _fpm
                                        for _k in _fpm:
                                            mods_sel.setdefault(_k, True)
                                    except Exception:
                                        pass
                                mods_dir = gdir / "mods"
                                mods_dir.mkdir(parents=True, exist_ok=True)
                                n = ensure_mods(ver, loader, mods_sel, mods_dir,
                                                log=lambda m: s.log.emit(str(m)))
                                if n:
                                    s.log.emit(f"✓ {n} mod(s) de performance prontos.")
                            except Exception as e:
                                s.log.emit(f"ℹ mods pulados: {e}")
                        content = inst.get("content") or []
                        if content:
                            try:
                                from .modrinth import latest_compat_file as _lcf, download_url_to as _dl
                                got = 0
                                for c in content:
                                    ck = c.get("kind", "mod")
                                    folder = {"mod": "mods", "resourcepack": "resourcepacks",
                                              "shader": "shaderpacks"}.get(ck, "mods")
                                    dest = gdir / folder / (c.get("file") or "")
                                    if not dest.name or dest.exists():
                                        got += 1 if dest.name else 0
                                        continue
                                    if ck == "mod":
                                        if loader not in ("fabric", "quilt", "forge", "neoforge"):
                                            continue
                                        lds = [loader]
                                    elif ck == "resourcepack":
                                        lds = ["minecraft"]
                                    else:  # shader: qualquer loader
                                        lds = []
                                    found = _lcf(c.get("slug", ""), ver, lds)
                                    if found and _dl(found[1], dest, log=lambda m: s.log.emit(str(m))):
                                        c["file"] = found[0]
                                        got += 1
                                if got:
                                    s.log.emit(f"✓ {got} extra(s) da versão prontos.")
                            except Exception as e:
                                s.log.emit(f"ℹ extras pulados: {e}")
                        real_ver = install_with_loader(ver, loader, loader_ver or None, callback=cb)
                        try:  # carimba: próxima vez vai direto
                            _insts = self._get_installations()
                            for _i in _insts:
                                if _i.get("id") == inst.get("id"):
                                    _i["installed_fp"] = fp
                                    _i["installed_launch"] = real_ver
                                    break
                            self._set_installations(_insts, inst.get("id", ""))
                        except Exception:
                            pass
                    # Isola mods: guarda os de outras versões antes de jogar
                    try:
                        from .modrinth import reconcile_mods_for_launch as _rec
                        _store_files = [c.get("file", "") for c in (inst.get("content") or [])
                                        if c.get("kind", "mod") == "mod"]
                        _rec(mods_sel, _store_files, loader,
                             gdir / "mods",
                             log=lambda m: s.log.emit(str(m)))
                    except Exception:
                        pass
                    # Java também no caminho direto (pode ter mudado o runtime)
                    if "executablePath" not in options:
                        try:
                            from .java_utils import get_java_for_mc as _gj3
                            _j3 = _gj3(ver)
                            if _j3:
                                options["executablePath"] = _j3
                        except Exception:
                            pass
                s.log.emit("🚀 Iniciando o jogo…")
                try:
                    _gpu_env = self._gpu_env_extra()
                except Exception:
                    _gpu_env = {}
                if _gpu_env:
                    s.log.emit("🎮 Placa dedicada (NVIDIA) ativada p/ esta sessão.")
                p = launch(real_ver, options, ram, server=srv_host, port=srv_port,
                           game_dir=str(gdir), env_extra=_gpu_env or None)
                s.status.emit(f"rodando (pid {p.pid}) — bom jogo!")
                s.log.emit(f"✓ Jogo rodando (pid {p.pid}). Pode minimizar o launcher.")
                try:
                    if load_cfg().get("close_on_launch", True):
                        if self._spawn_reopen_watcher(p.pid):
                            s.log.emit("👋 Fechando o launcher — reabro ao sair do jogo.")
                            s.quit_app.emit()
                        else:
                            s.log.emit("ℹ Não fechei sozinho (sem vigia) — pode minimizar.")
                except Exception:
                    pass
            except Exception as e:
                s.log.emit(f"⚠ ERRO: {e}")
                s.status.emit("erro — veja o console acima")
        threading.Thread(target=work, daemon=True).start()

    def _play_local(self):
        nick = self.user.text().strip() or "Salsicha"
        if not (3 <= len(nick) <= 16):
            QMessageBox.warning(self, APP_NAME, "Nick com 3–16 letras, senhor.")
            return
        try:
            save_local_account(nick)
        except Exception:
            pass
        try:
            self._refresh_local_accounts()
        except Exception:
            pass
        self._log(f"Conta Local {nick} (sem Microsoft: mundos locais e servidores offline).")
        self._run_game(offline_options(nick))

    def _play_offline(self):
        """Alias antigo — agora é Conta Local."""
        return self._play_local()

    def _play_microsoft(self):
        accs = load_accounts()
        nick = self.user.text().strip()
        data = accs.get(nick)
        if not data:
            QMessageBox.warning(self, APP_NAME, "Conta não encontrada. Vá em 👤 Contas e faça os passos 1 e 2.")
            self.pages.setCurrentIndex(5)  # 👤 Contas
            return
        if not validate_profile(data.get("access_token", "")):
            self._log("Sessão expirada, renovando sozinho…")
            try:
                if data.get("_client_id") == "DEVICE":
                    new = device_refresh_login(data)
                else:
                    cid = data.get("_client_id") or self.client_id.text().strip()
                    red = data.get("_redirect") or self.redirect.text().strip()
                    new = refresh_login(cid, red, data)
                    new["_client_id"] = cid
                    new["_redirect"] = red
                save_account(new["name"], new)
                data = new
                self._log(f"✓ Sessão renovada: {data['name']}")
            except Exception:
                self._log("Sessão expirou de vez — refaça os passos 1 e 2 em 👤 Contas.")
                QMessageBox.warning(self, APP_NAME, "Sessão expirada. Refaça o login em 👤 Contas.")
                self.pages.setCurrentIndex(5)  # 👤 Contas
                return
        self._log(f"Modo Microsoft como {data['name']}.")
        self._run_game(microsoft_options(data))


def run():
    import sys
    from PySide6.QtGui import QFont, QIcon
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    try:
        _c = resolve(load_cfg().get("theme"))
    except Exception:
        _c = resolve(None)
    try:
        app.setFont(QFont(_c["family"], _c["qfont"]))
    except Exception:
        pass
    try:
        app.setStyleSheet(build_qss(_c["accent"], _c["hover"], _c["bg"],
                                    _c["side"], _c["card"], _c["base"],
                                    _c["grad"], _c["glow"], _c["family"]))
    except Exception:
        app.setStyleSheet(QSS)
    try:
        ico = Path(__file__).parent / "assets" / "icon.svg"
        if ico.exists():
            app.setWindowIcon(QIcon(str(ico)))
    except Exception:
        pass
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
