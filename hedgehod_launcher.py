import json
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tkinter as tk
import tkinter.font as tkfont
import urllib.parse
import urllib.request
import webbrowser
import zipfile
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageSequence, ImageTk

BASE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
GAME_DATA_DIR = BASE / "Data Games"
LEGACY_GAME_DATA_DIR = BASE / "Game Data"
CONFIG_DIR = BASE / "configs"
GAME_NAMES = ("Sonic 1", "Sonic 2", "Sonic 3", "Sonic CD", "Sonic Mania")
GAME_DIR_NAMES = {name: name for name in GAME_NAMES}
CONFIG = CONFIG_DIR / "hedgehod-launcher.json"
LEGACY_CONFIG = BASE / "hedgehod-launcher.json"
DEFAULT_COVER = BASE / "sonic-japan-cover.png"
SONIC2_COVER = BASE / "sonic-2-japan-cover.png"
MANIA_COVER = BASE / "sonic-mania-cover.png"
DEFAULT_BACKGROUND = BASE / "sonic-grid-tile.png"
SONIC_GRID_TILE = DEFAULT_BACKGROUND
SONIC_SYMBOL = BASE / "sonic-symbol.png"
LIBRESPRITE_RELEASE = "https://github.com/LibreSprite/LibreSprite/releases/tag/v1.3"
RSDK_REPO = "https://github.com/RSDKModding/RSDKv4-Decompilation"
RSDK_RELEASES_API = "https://api.github.com/repos/RSDKModding/RSDKv4-Decompilation/releases/latest"
RSDK_LICENSE_URL = "https://raw.githubusercontent.com/RSDKModding/RSDKv4-Decompilation/main/LICENSE.md"
BG = "#071322"
PANEL = "#10223a"
CYAN = "#56dcff"
YELLOW = "#ffe36e"
WHITE = "#f2f6ff"
MUTED = "#9badc5"


def read_config():
    try:
        source = CONFIG if CONFIG.is_file() else LEGACY_CONFIG
        return json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


class HedgehodLauncher:
    def __init__(self, root):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        GAME_DATA_DIR.mkdir(parents=True, exist_ok=True)
        for game in GAME_NAMES:
            old_dir = LEGACY_GAME_DATA_DIR / GAME_DIR_NAMES[game]
            new_dir = GAME_DATA_DIR / GAME_DIR_NAMES[game]
            if old_dir.is_dir() and not new_dir.exists():
                shutil.move(str(old_dir), str(new_dir))
            new_dir.mkdir(parents=True, exist_ok=True)
            (new_dir / "mods").mkdir(exist_ok=True)
            (new_dir / "Mod Projects").mkdir(exist_ok=True)
        self.root = root
        self.root.title("Hedgehod Launcher")
        self.root.geometry("1050x760")
        self.root.minsize(900, 680)
        self.root.configure(bg=BG)
        self.config = read_config()
        self.settings = self.config.get("settings", {})
        saved_background = self.settings.get("background", "")
        if not saved_background or Path(saved_background).name.lower() == "sonic-adventure2-background.png":
            saved_background = str(DEFAULT_BACKGROUND)
        self.background_path = tk.StringVar(value=saved_background)
        self.font_family = tk.StringVar(value=self.settings.get("font", "Segoe UI"))
        self.refresh_hz = tk.IntVar(value=int(self.settings.get("refresh_hz", 60)))
        self.libresprite_exe = tk.StringVar(value=self.settings.get("libresprite_exe", ""))
        self.frame_interval_ms = max(8, round(1000 / max(30, self.refresh_hz.get())))
        old_game_dir = self.config.get("game_dir", "")
        managed_sonic1 = GAME_DATA_DIR / "Sonic 1"
        if (managed_sonic1 / "Data.rsdk").is_file():
            old_game_dir = str(managed_sonic1)
        legacy_profile = {"game_dir": old_game_dir,
                          "engine_exe": self.config.get("engine_exe", ""),
                          "cover": self.config.get("cover", str(DEFAULT_COVER)),
                          "mod_covers": self.config.get("mod_covers", {})}
        self.profiles = self.config.get("profiles") or {"Sonic 1": legacy_profile}
        self.profiles.setdefault("Sonic 1", legacy_profile)
        self.profiles.setdefault("Sonic 2", {"game_dir": str(GAME_DATA_DIR / "Sonic 2"), "engine_exe": legacy_profile["engine_exe"],
                                              "cover": str(SONIC2_COVER), "mod_covers": {}})
        for game in ("Sonic 3", "Sonic CD"):
            self.profiles.setdefault(game, {"game_dir": str(GAME_DATA_DIR / GAME_DIR_NAMES[game]),
                                            "engine_exe": "", "cover": str(DEFAULT_COVER), "mod_covers": {}})
        mania_folder = GAME_DATA_DIR / GAME_DIR_NAMES["Sonic Mania"]
        self.profiles.setdefault("Sonic Mania", {"game_dir": str(mania_folder), "engine_exe": "",
                                                  "cover": str(MANIA_COVER), "mod_covers": {}})
        if self.profiles["Sonic Mania"].get("cover", "").endswith("sonic-japan-cover.png"):
            self.profiles["Sonic Mania"]["cover"] = str(MANIA_COVER)
        for game in GAME_NAMES:
            if not self.profiles[game].get("game_dir"):
                self.profiles[game]["game_dir"] = str(GAME_DATA_DIR / GAME_DIR_NAMES[game])
            old_dir = LEGACY_GAME_DATA_DIR / GAME_DIR_NAMES[game]
            new_dir = GAME_DATA_DIR / GAME_DIR_NAMES[game]
            if not old_dir.exists():
                for key in ("game_dir", "asset_data_dir"):
                    value = self.profiles[game].get(key, "")
                    try:
                        old_path = Path(value).expanduser()
                        relative = old_path.relative_to(old_dir)
                        self.profiles[game][key] = str(new_dir / relative)
                    except (ValueError, OSError):
                        pass
        self.profile_name = tk.StringVar(value=self.config.get("active_profile", "Sonic 1"))
        if self.profile_name.get() not in self.profiles:
            self.profile_name.set("Sonic 1")
        self.loaded_profile_name = self.profile_name.get()
        current = self.profiles[self.profile_name.get()]
        self.game_dir = tk.StringVar(value=current.get("game_dir", ""))
        self.engine_exe = tk.StringVar(value=current.get("engine_exe", ""))
        self.cover_path = tk.StringVar(value=current.get("cover", str(DEFAULT_COVER)))
        self.mod_covers = current.get("mod_covers", {})
        self.root.title(f"Hedgehod Launcher — {self.profile_name.get()}")
        self.cover_image = None
        self.background_image = None
        self.background_key = None
        self.background_fade_id = None
        self.background_transition = 0
        self.background_render_size = None
        self.wallpaper_cache = {}
        self.gallery_image_cache = {}
        self.background_file_cache = {}
        self.logo_image = None
        self.wallpaper_photo = None
        self.tiled_wallpaper_photo = None
        self.tiled_wallpaper_size = None
        self.background_offset = (0, 0)
        self.background_tile_size = (16, 16)
        self.background_anim_id = None
        self.cover_anim_items = []
        self.cover_anim_phase = 0
        self.cover_anim_id = None
        self.content_wallpaper = None
        self.content_wallpaper_label = None
        self.content = None
        self.details_panel = None
        self.details_wallpaper_label = None
        self.bg_canvas = tk.Canvas(root, highlightthickness=0, bd=0, bg=BG)
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.bg_item = self.bg_canvas.create_image(0, 0, anchor="center")
        self.root.bind("<Configure>", self._resize_background)
        self.make_ui()
        self.load_cover()
        self.set_background(self.background_path.get())
        self.refresh_mods()
        self.apply_font_family()
        self._animate_covers()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def label(self, parent, text, **kwargs):
        return tk.Label(parent, text=text, bg=kwargs.pop("bg", BG), fg=kwargs.pop("fg", WHITE),
                        font=kwargs.pop("font", (self.font_family.get(), 11)), **kwargs)

    def update_profile_labels(self):
        self.root.title(f"Hedgehod Launcher — {self.profile_name.get()}")

    def switch_profile(self):
        self.save_config()
        current = self.profiles[self.profile_name.get()]
        self.game_dir.set(current.get("game_dir", ""))
        self.engine_exe.set(current.get("engine_exe", ""))
        default_cover = {"Sonic 1": DEFAULT_COVER, "Sonic 2": SONIC2_COVER,
                         "Sonic Mania": MANIA_COVER}.get(self.profile_name.get(), DEFAULT_COVER)
        self.cover_path.set(current.get("cover", str(default_cover)))
        self.mod_covers = current.setdefault("mod_covers", {})
        self.loaded_profile_name = self.profile_name.get()
        self.update_profile_labels()
        self.refresh_mods()
        self.set_background(self.background_path.get())
        self.render_gallery()
        self.save_config()

    def button(self, parent, text, command, primary=False, **kwargs):
        return tk.Button(parent, text=text, command=command, relief="flat", borderwidth=0,
                         bg=YELLOW if primary else "#1a304b", fg="#122139" if primary else WHITE,
                         activebackground="#fff0a4" if primary else "#284967",
                         activeforeground="#122139" if primary else WHITE,
                         font=(self.font_family.get(), 10, "bold"), padx=16, pady=10,
                         cursor="hand2", **kwargs)

    def make_ui(self):
        self.root.geometry("1260x900")
        self.root.minsize(1000, 780)
        shell = tk.Frame(self.root, bg=BG)
        shell.place(x=0, y=0, relwidth=1, relheight=1)
        sidebar = tk.Frame(shell, bg="#081626", width=184,
                           highlightbackground="#213750", highlightthickness=1)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        logo = tk.Frame(sidebar, bg="#081626")
        logo.pack(fill="x", padx=14, pady=(22, 28))
        tk.Label(logo, text="HG", bg="#081626", fg="#4ebeff",
                 font=("Segoe UI", 23, "bold italic")).pack(side="left")
        if SONIC_SYMBOL.is_file():
            try:
                symbol = tk.PhotoImage(file=str(SONIC_SYMBOL))
                self.logo_image = symbol.subsample(max(1, (symbol.width()+27)//28, (symbol.height()+27)//28))
                tk.Label(logo, image=self.logo_image, bg="#081626").pack(side="left", padx=5)
            except tk.TclError:
                pass
        self.label(sidebar, "TU ESPACIO", fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16)
        self.button(sidebar, "▦   Biblioteca", lambda: None).pack(fill="x", padx=9, pady=(7, 3))
        self.button(sidebar, "✦   Workspace", self.open_visual_workspace).pack(fill="x", padx=9, pady=3)
        self.button(sidebar, "＋   Crear mod", self.create_mod_project).pack(fill="x", padx=9, pady=3)
        self.button(sidebar, "⇄   Mods / compartir", self.open_mod_hub).pack(fill="x", padx=9, pady=3)
        self.button(sidebar, "⚙   Ajustes", self.open_settings).pack(fill="x", padx=9, pady=3)
        self.button(sidebar, "✎   Editar sprite", self.open_visual_workspace).pack(fill="x", padx=9, pady=3)
        self.label(sidebar, "PERFIL DE JUEGO", fg=MUTED,
                   font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16, pady=(22, 5))
        self.profile_menu = tk.OptionMenu(sidebar, self.profile_name, *self.profiles.keys(),
                                          command=lambda _value: self.switch_profile())
        self.profile_menu.configure(bg="#142b46", fg=WHITE, activebackground="#1d3c5e",
                                    relief="flat", highlightthickness=0)
        self.profile_menu["menu"].configure(bg="#142b46", fg=WHITE)
        self.profile_menu.pack(fill="x", padx=10)
        self.label(sidebar, "PERFIL LOCAL\nTus archivos permanecen en tu equipo",
                   fg=MUTED, font=("Segoe UI", 8), justify="left", wraplength=150).pack(
                       side="bottom", anchor="w", padx=15, pady=18)

        content = tk.Frame(shell, bg=BG)
        self.content = content
        content.pack(side="left", fill="both", expand=True, padx=24, pady=15)
        self.content_wallpaper_label = tk.Label(content, bg=BG, bd=0)
        self.content_wallpaper_label.place(x=0, y=0, relwidth=1, relheight=1)
        self.content_wallpaper_label.lower()
        top = tk.Frame(content, bg=BG)
        top.pack(fill="x")
        self.label(top, "HEDGEHOD  /  BIBLIOTECA", fg=MUTED,
                   font=("Segoe UI", 8, "bold")).pack(side="left")
        self.button(top, "Abrir Data Games", self.open_game_data).pack(side="right")

        hero = tk.Frame(content, bg="#122a47", highlightbackground="#315678", highlightthickness=1)
        hero.pack(fill="x", pady=(14, 15))
        self.label(hero, "TU COLECCIÓN RSDK · CONSTRUYE A TU MANERA", fg=CYAN,
                   font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=18, pady=(12, 1))
        self.label(hero, "Elige una aventura. Hazla tuya.",
                   font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=18)
        self.label(hero, "Biblioteca con profundidad y perfiles locales para tus juegos y mods.",
                   fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", padx=18, pady=(2, 7))
        self.button(hero, "✦  Abrir Workspace Sonic 1", self.open_visual_workspace,
                    primary=True).pack(anchor="w", padx=18, pady=(0, 12))

        heading = tk.Frame(content, bg=BG)
        heading.pack(fill="x", pady=(0, 5))
        self.label(heading, "Biblioteca", font=("Segoe UI", 14, "bold")).pack(side="left")
        self.label(heading, "Al pasar el cursor: ⚙ Ajustes   ✎ Editar / Mods   ▶ Play",
                   fg=MUTED, font=("Segoe UI", 8)).pack(side="right")
        self.gallery_canvas = tk.Canvas(content, height=226, bg=BG, highlightthickness=0, bd=0)
        self.gallery_canvas.pack(fill="x")
        self.gallery_canvas.bind("<Motion>", self.gallery_motion)
        self.gallery_canvas.bind("<Leave>", self.gallery_leave)
        self.gallery_canvas.bind("<Button-1>", self.gallery_click)
        self.gallery_hovered = -1
        self.gallery_hover_after = None
        self.pending_gallery_hover = -1
        self.gallery_images = []
        self.root.update_idletasks()
        self.render_gallery()
        self.update_profile_labels()

    def render_gallery(self):
        if not hasattr(self, "gallery_canvas"):
            return
        c = self.gallery_canvas
        c.delete("all")
        self.gallery_images = []
        self.gallery_rects = []
        names = list(self.profiles)
        cw, ch, gap = max(128, min(176, (self.root.winfo_width()-260)//5)), 190, 13
        for i, name in enumerate(names):
            x, y = 4 + i * (cw + gap), 5 + (i % 2) * 3
            x2, y2 = x + cw, y + ch
            self.gallery_rects.append((x, y, x2, y2))
            active = i == self.gallery_hovered or name == self.profile_name.get()
            accent = YELLOW if i == self.gallery_hovered else (CYAN if active else "#44617e")
            # Layered offset shadows and a luminous border give each game tile
            # the raised, selectable feel of the 3DS HOME Menu.
            c.create_rectangle(x+5, y+7, x2+5, y2+7, fill="#020711", outline="")
            c.create_rectangle(x+2, y+3, x2+2, y2+3, fill="#18304b", outline="#284765", width=1)
            c.create_rectangle(x, y, x2, y2, fill="#10233d", outline=accent,
                               width=2 if active else 1)
            cover = Path(self.profiles[name].get("cover", str(DEFAULT_COVER))).expanduser()
            if not cover.is_file():
                cover = DEFAULT_COVER
            try:
                cover_w, cover_h = cw-28, ch-57
                key = (str(cover.resolve()), cover_w, cover_h)
                image = self.gallery_image_cache.get(key)
                if image is None:
                    with Image.open(cover) as source:
                        thumb = source.convert("RGBA")
                        thumb.thumbnail((cover_w, cover_h), Image.Resampling.LANCZOS)
                        image = ImageTk.PhotoImage(thumb, master=self.root)
                    self.gallery_image_cache[key] = image
                self.gallery_images.append(image)
                c.create_rectangle(x+8, y+8, x2-8, y+ch-49, fill="#09172a", outline="#385575")
                cover_item = c.create_image(x+cw//2, y+10, image=image, anchor="n")
                if name == "Sonic 1":
                    self.cover_anim_items.append((cover_item, x+cw//2, y+10))
            except tk.TclError:
                c.create_text(x+cw//2, y+ch//2, text="PORTADA", fill=CYAN)
            c.create_rectangle(x+1, y2-40, x2-1, y2-1, fill="#081526", outline="")
            engine = {"Sonic 1":"RSDKv4", "Sonic 2":"RSDKv4", "Sonic 3":"RSDK compatible",
                      "Sonic CD":"RSDKv3", "Sonic Mania":"RSDKv5"}.get(name, "RSDK")
            c.create_text(x+9, y2-27, text=engine, anchor="w", fill=CYAN,
                          font=("Segoe UI", 7, "bold"))
            c.create_text(x+9, y2-12, text=name, anchor="w", fill=WHITE,
                          font=("Segoe UI", 9, "bold"))
        c.configure(height=ch+17)
        if self.gallery_hovered >= 0:
            self.draw_gallery_actions(self.gallery_hovered)

    def _animate_covers(self):
        self.cover_anim_id = None
        if not self.root.winfo_exists():
            return
        offsets = (0, -1, -2, -1, 0, 1, 2, 1)
        self.cover_anim_phase = (self.cover_anim_phase + 1) % len(offsets)
        dy = offsets[self.cover_anim_phase]
        if hasattr(self, "gallery_canvas"):
            for item, x, y in self.cover_anim_items:
                try:
                    self.gallery_canvas.coords(item, x, y+dy)
                except tk.TclError:
                    pass
        self.cover_anim_id = self.root.after(110, self._animate_covers)

    def draw_gallery_actions(self, index):
        x1,y1,x2,y2 = self.gallery_rects[index]
        actions = (("⚙", "SET"), ("✎", "EDIT"), ("▶", "PLAY"))
        w = (x2-x1-18)//3
        for j,(icon,label) in enumerate(actions):
            xa=x1+6+j*(w+3); xb=xa+w; ya=y1+8; yb=ya+37
            self.gallery_canvas.create_rectangle(xa,ya,xb,yb,fill="#081526",outline="#59dcff",width=1)
            self.gallery_canvas.create_text((xa+xb)//2,ya+12,text=icon,
                fill=YELLOW if j==2 else WHITE,font=(self.font_family.get(),11,"bold"))
            self.gallery_canvas.create_text((xa+xb)//2,ya+29,text=label,
                fill=WHITE,font=(self.font_family.get(),6,"bold"))

    def gallery_motion(self, event):
        i=next((j for j,(x1,y1,x2,y2) in enumerate(self.gallery_rects)
                if x1<=event.x<=x2 and y1<=event.y<=y2),-1)
        self.pending_gallery_hover = i
        if self.gallery_hover_after is None and i != self.gallery_hovered:
            self.gallery_hover_after = self.root.after(self.frame_interval_ms, self._apply_gallery_hover)

    def _apply_gallery_hover(self):
        self.gallery_hover_after = None
        if self.pending_gallery_hover != self.gallery_hovered:
            self.gallery_hovered = self.pending_gallery_hover
            self.render_gallery()

    def gallery_leave(self, _event):
        if self.gallery_hover_after is not None:
            self.root.after_cancel(self.gallery_hover_after)
            self.gallery_hover_after = None
        self.pending_gallery_hover = -1
        self.gallery_hovered=-1
        self.render_gallery()

    def gallery_click(self, event):
        i=next((j for j,(x1,y1,x2,y2) in enumerate(self.gallery_rects)
                if x1<=event.x<=x2 and y1<=event.y<=y2),-1)
        if i<0: return
        x1,y1,x2,y2=self.gallery_rects[i]
        action="select"
        if self.gallery_hovered == i and y1+8<=event.y<=y1+45:
            action=("settings","edit","play")[min(2,max(0,(event.x-x1-6)//((x2-x1-18)//3+3)))]
        name=list(self.profiles)[i]
        if self.profile_name.get()!=name:
            self.profile_name.set(name)
            self.switch_profile()
        if action=="settings": self.open_settings()
        elif action=="edit": self.show_edit_mod_menu(event)
        elif action=="play": self.launch_game()
        else: self.render_gallery()

    def show_edit_mod_menu(self, event):
        menu = tk.Menu(self.root, tearoff=False, bg="#142b46", fg=WHITE,
                       activebackground="#284967", activeforeground=WHITE,
                       font=(self.font_family.get(), 10))
        menu.add_command(label="✎  Abrir editor / Workspace", command=lambda: self.open_visual_workspace(self.profile_name.get()))
        menu.add_command(label="▤  Ver mods instalados", command=self.show_mods)
        menu.add_command(label="▧  Editar carátula", command=self.choose_cover)
        menu.tk_popup(event.x_root, event.y_root)

    def show_mods(self):
        folder=Path(self.game_dir.get()).expanduser()/"mods"
        mods=sorted(p.name for p in folder.iterdir() if p.is_dir() and (p/"mod.ini").is_file()) if folder.is_dir() else []
        messagebox.showinfo("Mods del perfil", "Mods detectados:\n"+"\n".join(mods) if mods else
                            f"Aún no hay mods detectados para {self.profile_name.get()}. Añádelos en mods/ con mod.ini.",
                            parent=self.root)

    def field(self, parent, row, title, variable, help_text, browse):
        block = tk.Frame(parent, bg=PANEL)
        block.grid(row=row, column=1, sticky="ew", padx=(0, 24), pady=7)
        block.grid_columnconfigure(0, weight=1)
        self.label(block, title, fg=WHITE, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        line = tk.Frame(block, bg=PANEL)
        line.grid(row=1, column=0, sticky="ew", pady=(5, 3))
        line.grid_columnconfigure(0, weight=1)
        entry = tk.Entry(line, textvariable=variable, bg="#09172a", fg=WHITE, insertbackground=WHITE,
                         relief="flat", font=("Consolas", 9), highlightthickness=1,
                         highlightbackground="#2b405c", highlightcolor=CYAN)
        entry.grid(row=0, column=0, sticky="ew", ipady=9, padx=(0, 8))
        self.button(line, "Examinar…", browse).grid(row=0, column=1)
        self.label(block, help_text, fg=MUTED, font=("Segoe UI", 8)).grid(row=2, column=0, sticky="w")

    def load_cover(self):
        self.render_gallery()

    def set_background(self, path):
        try:
            key = str(Path(path).expanduser().resolve())
            if key == self.background_key:
                return
            image = self.background_file_cache.get(key)
            if image is None:
                image = tk.PhotoImage(file=key)
                self.background_file_cache[key] = image
            self.background_image = image
            self.background_key = key
            self.background_render_size = None
            self.bg_canvas.itemconfigure(self.bg_item, image=image)
            self._resize_background()
        except (tk.TclError, OSError):
            messagebox.showerror("Fondo no compatible", "Elige una imagen PNG, GIF, PPM o PGM válida.", parent=self.root)

    def _resize_background(self, _event=None):
        if _event is not None and _event.widget is not self.root:
            return
        if not self.background_image:
            return
        width = max(1, self.root.winfo_width())
        height = max(1, self.root.winfo_height())
        tiled = False
        try:
            tiled = Path(self.background_key).resolve() == SONIC_GRID_TILE.resolve()
        except (TypeError, OSError):
            pass
        if tiled:
            tile_key = (width, height, self.background_key)
            if tile_key != self.tiled_wallpaper_size:
                tile_path = Path(self.background_key)
                with Image.open(tile_path) as source:
                    tile = source.convert("RGBA")
                tw, th = tile.size
                self.background_tile_size = (tw, th)
                wallpaper = Image.new("RGBA", (width+tw, height+th), (7, 19, 34, 255))
                for y in range(0, wallpaper.height, th):
                    for x in range(0, wallpaper.width, tw):
                        wallpaper.alpha_composite(tile, (x, y))
                self.tiled_wallpaper_photo = ImageTk.PhotoImage(wallpaper, master=self.root)
                self.tiled_wallpaper_size = tile_key
                self.wallpaper_photo = self.tiled_wallpaper_photo
                self.background_offset = (0, 0)
                self.bg_canvas.itemconfigure(self.bg_item, image=self.tiled_wallpaper_photo)
                if self.content_wallpaper_label:
                    self.content_wallpaper_label.configure(image=self.tiled_wallpaper_photo, anchor="nw")
                    self.content_wallpaper = self.tiled_wallpaper_photo
                if self.background_anim_id is None:
                    self.background_anim_id = self.root.after(60, self._animate_background)
            ox, oy = self.background_offset
            self.bg_canvas.coords(self.bg_item, ox, oy)
            if self.content_wallpaper_label and self.content:
                cx = self.content.winfo_rootx()-self.root.winfo_rootx()
                cy = self.content.winfo_rooty()-self.root.winfo_rooty()
                self.content_wallpaper_label.place_configure(x=-cx+ox, y=-cy+oy,
                    width=self.tiled_wallpaper_photo.width(), height=self.tiled_wallpaper_photo.height(),
                    relwidth=0, relheight=0)
                self.content_wallpaper_label.lower()
            return

        if self.background_anim_id is not None:
            try:
                self.root.after_cancel(self.background_anim_id)
            except tk.TclError:
                pass
            self.background_anim_id = None
        if self.content_wallpaper_label:
            self.content_wallpaper_label.configure(anchor="center")
            self.content_wallpaper_label.place(x=0, y=0, relwidth=1, relheight=1)
        self.bg_canvas.coords(self.bg_item, width//2, height//2)
        render_size = (width, height, self.background_key)
        if render_size == self.background_render_size:
            return
        self.background_render_size = render_size
        wallpaper = self.wallpaper_cache.get(render_size)
        if wallpaper is None:
            scale = max(width / self.background_image.width(), height / self.background_image.height())
            if scale >= 1:
                zoom = max(1, round(scale * 2))
                wallpaper = self.background_image.zoom(zoom, zoom).subsample(2, 2)
            else:
                factor = max(1, round(1 / scale))
                wallpaper = self.background_image.subsample(factor, factor)
            self.wallpaper_cache.clear()
            self.wallpaper_cache[render_size] = wallpaper
        self.wallpaper_photo = wallpaper
        self.bg_canvas.itemconfigure(self.bg_item, image=wallpaper)
        if self.content_wallpaper_label:
            self.content_wallpaper = wallpaper
            self.content_wallpaper_label.configure(image=wallpaper)
            self.content_wallpaper_label.lower()

    def _animate_background(self):
        self.background_anim_id = None
        if not self.root.winfo_exists() or self.tiled_wallpaper_photo is None:
            return
        tw, th = self.background_tile_size
        ox, oy = self.background_offset
        ox, oy = (ox+1) % tw, (oy+1) % th
        self.background_offset = (ox, oy)
        self.bg_canvas.coords(self.bg_item, ox, oy)
        if self.content_wallpaper_label and self.content:
            cx = self.content.winfo_rootx()-self.root.winfo_rootx()
            cy = self.content.winfo_rooty()-self.root.winfo_rooty()
            self.content_wallpaper_label.place_configure(x=-cx+ox, y=-cy+oy)
        self.background_anim_id = self.root.after(60, self._animate_background)

    def choose_cover(self):
        selected = filedialog.askopenfilename(title="Elige una portada", filetypes=[
            ("Imágenes compatibles", "*.png *.gif *.ppm *.pgm"), ("Todos los archivos", "*.*")])
        if selected:
            self.cover_path.set(selected)
            self.gallery_image_cache.clear()
            self.render_gallery()
            self.save_config()

    def refresh_mods(self):
        folder = Path(self.game_dir.get().strip()).expanduser() / "mods"
        self.detected_mods = sorted(path.name for path in folder.iterdir()
                                    if path.is_dir() and (path / "mod.ini").is_file()) if folder.is_dir() else []

    def choose_game_dir(self):
        selected = filedialog.askdirectory(title=f"Elige la carpeta de {self.profile_name.get()}")
        if selected:
            self.game_dir.set(selected)
            self.refresh_mods()
            self.save_config()

    def choose_engine(self):
        selected = filedialog.askopenfilename(title=f"Elige el ejecutable compatible con {self.profile_name.get()}", filetypes=[
            ("Aplicación", "*.exe"), ("Todos los archivos", "*.*")])
        if selected:
            self.engine_exe.set(selected)
            self.save_config()

    def save_config(self):
        self.profiles[self.loaded_profile_name] = {
            "game_dir": self.game_dir.get().strip(), "engine_exe": self.engine_exe.get().strip(),
            "cover": self.cover_path.get().strip(), "mod_covers": self.mod_covers,
            "asset_data_dir": self.profiles.get(self.loaded_profile_name, {}).get("asset_data_dir", ""),
            "sprite_actions": self.profiles.get(self.loaded_profile_name, {}).get("sprite_actions", {})}
        data = {"profiles": self.profiles, "active_profile": self.loaded_profile_name,
                "settings": {"background": self.background_path.get(),
                             "font": self.font_family.get(),
                             "refresh_hz": int(self.refresh_hz.get()),
                             "libresprite_exe": self.libresprite_exe.get().strip()},
                "game_dir": self.profiles["Sonic 1"].get("game_dir", ""),
                "engine_exe": self.profiles["Sonic 1"].get("engine_exe", ""),
                "cover": self.profiles["Sonic 1"].get("cover", str(DEFAULT_COVER)),
                "mod_covers": self.profiles["Sonic 1"].get("mod_covers", {})}
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return True
        except OSError as exc:
            messagebox.showerror("No se pudo guardar", str(exc), parent=self.root)
            return False

    def open_game_data(self):
        try:
            os.startfile(str(GAME_DATA_DIR))
        except OSError as exc:
            messagebox.showerror("No se pudo abrir Data Games", str(exc), parent=self.root)

    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Ajustes del launcher")
        win.geometry("660x650")
        win.minsize(600, 600)
        win.configure(bg=BG)
        win.transient(self.root)
        win.grab_set()
        self.label(win, "PERSONALIZACIÓN", fg=CYAN,
                   font=(self.font_family.get(), 9, "bold")).pack(anchor="w", padx=22, pady=(18, 3))
        self.label(win, "Ajustes del launcher", font=(self.font_family.get(), 20, "bold")).pack(anchor="w", padx=22)

        form = tk.Frame(win, bg=PANEL, highlightbackground="#284565", highlightthickness=1)
        form.pack(fill="both", expand=True, padx=18, pady=15)
        background_var = tk.StringVar(value=self.background_path.get())
        game_dir_var = tk.StringVar(value=self.game_dir.get())
        engine_var = tk.StringVar(value=self.engine_exe.get())
        sprite_editor_var = tk.StringVar(value=self.libresprite_exe.get())
        font_var = tk.StringVar(value=self.font_family.get())
        hz_var = tk.StringVar(value=str(self.refresh_hz.get()))

        self.label(form, "Fondo normal", bg=PANEL, font=(self.font_family.get(), 10, "bold")).pack(anchor="w", padx=15, pady=(14, 3))
        row = tk.Frame(form, bg=PANEL); row.pack(fill="x", padx=15)
        tk.Entry(row, textvariable=background_var, bg="#09172a", fg=WHITE, insertbackground=WHITE,
                 relief="flat", font=(self.font_family.get(), 9)).pack(side="left", fill="x", expand=True, ipady=8)
        self.button(row, "Elegir…", lambda: self._choose_image_into(background_var)).pack(side="left", padx=(8, 0))

        options = tk.Frame(form, bg=PANEL); options.pack(fill="x", padx=15, pady=(14, 0))
        self.label(options, "Fuente", bg=PANEL, font=(self.font_family.get(), 10, "bold")).grid(row=0, column=0, sticky="w")
        families = set(tkfont.families(self.root))
        font_choices = [name for name in ("Segoe UI", "Arial", "Trebuchet MS", "Verdana", "Tahoma") if name in families]
        if font_var.get() not in font_choices:
            font_choices.append(font_var.get())
        tk.OptionMenu(options, font_var, *font_choices).grid(row=1, column=0, sticky="w", pady=(3, 0))
        self.label(options, "Ritmo de interfaz", bg=PANEL, font=(self.font_family.get(), 10, "bold")).grid(row=0, column=1, sticky="w", padx=(30, 0))
        tk.OptionMenu(options, hz_var, "60", "120").grid(row=1, column=1, sticky="w", padx=(30, 0), pady=(3, 0))
        self.label(options, f"Interfaz: {self.refresh_hz.get()} Hz · predeterminado: 60 Hz", bg=PANEL, fg=MUTED,
                   font=(self.font_family.get(), 8)).grid(row=2, column=1, sticky="w", padx=(30, 0), pady=3)
        self.button(options, "Ajustes avanzados del monitor…", self.open_display_settings).grid(row=3, column=1, sticky="w", padx=(30, 0), pady=(6, 0))

        self.label(form, "Perfil actual · " + self.profile_name.get(), bg=PANEL,
                   font=(self.font_family.get(), 10, "bold")).pack(anchor="w", padx=15, pady=(16, 3))
        for title, variable, picker in (("Carpeta del juego", game_dir_var, self._choose_folder_into),
                                        ("Ejecutable RSDK", engine_var, self._choose_exe_into)):
            line = tk.Frame(form, bg=PANEL); line.pack(fill="x", padx=15, pady=4)
            tk.Entry(line, textvariable=variable, bg="#09172a", fg=WHITE, insertbackground=WHITE,
                     relief="flat", font=(self.font_family.get(), 9)).pack(side="left", fill="x", expand=True, ipady=7)
            self.button(line, title, lambda v=variable, fn=picker: fn(v)).pack(side="left", padx=(7, 0))

        self.label(form, "Editor externo · Aseprite o LibreSprite (opcional)", bg=PANEL,
                   font=(self.font_family.get(), 10, "bold")).pack(anchor="w", padx=15, pady=(12, 3))
        sprite_line = tk.Frame(form, bg=PANEL); sprite_line.pack(fill="x", padx=15)
        tk.Entry(sprite_line, textvariable=sprite_editor_var, bg="#09172a", fg=WHITE,
                 insertbackground=WHITE, relief="flat", font=(self.font_family.get(), 9)).pack(
                     side="left", fill="x", expand=True, ipady=7)
        self.button(sprite_line, "Elegir editor…",
                    lambda: self._choose_libresprite_into(sprite_editor_var)).pack(side="left", padx=(7, 0))
        self.button(sprite_line, "Descargar v1.3",
                    lambda: webbrowser.open(LIBRESPRITE_RELEASE)).pack(side="left", padx=(7, 0))

        self.label(form, "La frecuencia de interfaz limita las animaciones del launcher. El refresco físico del monitor se cambia en Windows.",
                   bg=PANEL, fg=MUTED, font=(self.font_family.get(), 8), wraplength=560,
                   justify="left").pack(anchor="w", padx=15, pady=(8, 2))

        def save_settings():
            try:
                target_hz = int(hz_var.get())
                if target_hz not in (60, 120):
                    raise ValueError
            except ValueError:
                messagebox.showerror("Frecuencia no válida", "Elige 60 o 120 Hz.", parent=win)
                return
            self.background_path.set(background_var.get().strip() or str(DEFAULT_BACKGROUND))
            self.font_family.set(font_var.get())
            self.refresh_hz.set(target_hz)
            self.frame_interval_ms = max(8, round(1000 / target_hz))
            self.game_dir.set(game_dir_var.get().strip())
            self.engine_exe.set(engine_var.get().strip())
            self.libresprite_exe.set(sprite_editor_var.get().strip())
            self.refresh_mods()
            self.background_file_cache.clear()
            self.wallpaper_cache.clear()
            self.gallery_image_cache.clear()
            self.set_background(self.background_path.get())
            self.apply_font_family()
            self.render_gallery()
            self.save_config()
            win.destroy()

        footer = tk.Frame(win, bg=BG); footer.pack(fill="x", padx=18, pady=(0, 16))
        self.button(footer, "Cancelar", win.destroy).pack(side="right", padx=(7, 0))
        self.button(footer, "Guardar ajustes", save_settings, primary=True).pack(side="right")

    def _choose_image_into(self, variable):
        path = filedialog.askopenfilename(parent=self.root, title="Elige el fondo del launcher",
            filetypes=[("Imágenes Tk", "*.png *.gif *.ppm *.pgm"), ("Todos los archivos", "*.*")])
        if path:
            variable.set(path)

    def _choose_folder_into(self, variable):
        path = filedialog.askdirectory(parent=self.root, title="Elige la carpeta del juego")
        if path:
            variable.set(path)

    def _choose_exe_into(self, variable):
        path = filedialog.askopenfilename(parent=self.root, title="Elige RSDK.exe",
            filetypes=[("Aplicación", "*.exe"), ("Todos los archivos", "*.*")])
        if path:
            variable.set(path)

    def _choose_libresprite_into(self, variable):
        path = filedialog.askopenfilename(parent=self.root, title="Selecciona Aseprite o LibreSprite",
            filetypes=[("Aseprite o LibreSprite", "*.exe"), ("Todos los archivos", "*.*")])
        if path:
            variable.set(path)

    def choose_sprite_for_libresprite(self):
        sprite_path = filedialog.askopenfilename(parent=self.root, title="Elige el sprite para editar",
            filetypes=[("Sprites e imágenes", "*.png *.gif *.ase *.aseprite *.bmp *.jpg *.jpeg *.tga"),
                       ("Todos los archivos", "*.*")])
        if not sprite_path:
            return
        editor = Path(self.libresprite_exe.get().strip()).expanduser()
        if not editor.is_file():
            editor_path = filedialog.askopenfilename(parent=self.root, title="Selecciona Aseprite.exe o LibreSprite.exe",
                filetypes=[("Aseprite o LibreSprite", "*.exe"), ("Aplicación", "*.exe")])
            if not editor_path:
                messagebox.showinfo("Configura un editor externo", "Puedes configurar Aseprite o LibreSprite desde Ajustes y volver a intentarlo.", parent=self.root)
                return
            editor = Path(editor_path)
            self.libresprite_exe.set(str(editor))
            self.save_config()
        try:
            subprocess.Popen([str(editor), str(Path(sprite_path).resolve())], cwd=str(editor.parent))
        except OSError as exc:
            messagebox.showerror("No se pudo abrir el editor externo", str(exc), parent=self.root)

    def open_display_settings(self):
        try:
            os.startfile("ms-settings:display-advanced")
        except OSError as exc:
            messagebox.showerror("No se pudo abrir Pantalla avanzada", str(exc), parent=self.root)

    def apply_font_family(self):
        family = self.font_family.get()
        def apply(widget):
            try:
                current = tkfont.Font(root=self.root, font=widget.cget("font"))
                widget.configure(font=(family, current.cget("size"),
                                       current.cget("weight"), current.cget("slant")))
            except (tk.TclError, TypeError):
                pass
            for child in widget.winfo_children():
                apply(child)
        apply(self.root)
        if hasattr(self, "gallery_canvas"):
            self.render_gallery()

    def create_mod_project(self):
        """Collect mod metadata, create a clean local project, then open its tools."""
        win = tk.Toplevel(self.root)
        win.title("Crear proyecto de mod")
        win.geometry("580x720")
        win.minsize(540, 680)
        win.configure(bg=BG)
        win.transient(self.root)
        self.label(win, "NUEVO PROYECTO", fg=CYAN, font=(self.font_family.get(), 10, "bold")).pack(anchor="w", padx=22, pady=(20, 4))
        self.label(win, "Prepara un mod para este juego", font=(self.font_family.get(), 20, "bold")).pack(anchor="w", padx=22)
        form = tk.Frame(win, bg=PANEL, padx=18, pady=14, highlightbackground="#284565", highlightthickness=1)
        form.pack(fill="both", expand=True, padx=18, pady=16)
        name_var = tk.StringVar()
        version_var = tk.StringVar(value="1.0.0")
        author_var = tk.StringVar()
        type_var = tk.StringVar(value="Skins")
        description_var = tk.StringVar()
        game_var = tk.StringVar(value=self.profile_name.get())
        fields = (("Nombre del proyecto", name_var), ("Versión", version_var), ("Autor", author_var), ("Descripción", description_var))
        for row, (title, variable) in enumerate(fields):
            self.label(form, title, bg=PANEL, fg=WHITE, font=(self.font_family.get(), 9, "bold")).grid(row=row*2, column=0, sticky="w", pady=(2, 3))
            tk.Entry(form, textvariable=variable, bg="#09172a", fg=WHITE, insertbackground=WHITE,
                     relief="flat", font=("Segoe UI", 10)).grid(row=row*2+1, column=0, sticky="ew", ipady=7, pady=(0, 9))
        row = len(fields)*2
        self.label(form, "Tipo de mod", bg=PANEL, fg=WHITE, font=(self.font_family.get(), 9, "bold")).grid(row=row, column=0, sticky="w", pady=(2, 3))
        tk.OptionMenu(form, type_var, "Skins", "New Char", "New Stages", "Music", "Movements", "Complete").grid(row=row+1, column=0, sticky="ew", pady=(0, 9))
        self.label(form, "Juego objetivo", bg=PANEL, fg=WHITE, font=(self.font_family.get(), 9, "bold")).grid(row=row+2, column=0, sticky="w", pady=(2, 3))
        tk.OptionMenu(form, game_var, *GAME_NAMES).grid(row=row+3, column=0, sticky="ew")
        form.grid_columnconfigure(0, weight=1)
        self.label(form, "El proyecto se crea en Mod Projects con carpetas Data y Scripts. No incluye archivos del juego.",
                   bg=PANEL, fg=MUTED, font=(self.font_family.get(), 8), wraplength=490, justify="left").grid(row=row+4, column=0, sticky="w", pady=(12, 0))
        footer = tk.Frame(win, bg=BG)
        footer.pack(fill="x", padx=18, pady=(0, 16))
        self.button(footer, "Cancelar", win.destroy).pack(side="right", padx=(8, 0))

        def create():
            name = name_var.get().strip()
            version = version_var.get().strip()
            author = author_var.get().strip()
            if not name or not version or not author:
                messagebox.showwarning("Faltan datos", "Completa nombre, versión y autor.", parent=win)
                return
            metadata = {"name": name, "version": version, "author": author,
                        "type": type_var.get(), "description": description_var.get().strip(), "game": game_var.get()}
            try:
                project = self._create_project_files(metadata)
            except OSError as exc:
                messagebox.showerror("No se pudo crear el proyecto", str(exc), parent=win)
                return
            win.destroy()
            self.open_mod_project(project)

        self.button(footer, "Crear proyecto", create, primary=True).pack(side="right")

    @staticmethod
    def _safe_slug(text):
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", text.strip()).strip("-_").lower()
        return slug[:64] or "mod-sin-nombre"

    def _create_project_files(self, metadata):
        project_root = GAME_DATA_DIR / metadata["game"] / "Mod Projects"
        project_root.mkdir(parents=True, exist_ok=True)
        slug = self._safe_slug(metadata["name"])
        project = project_root / slug
        suffix = 2
        while project.exists():
            project = project_root / f"{slug}-{suffix}"
            suffix += 1
        project.mkdir()
        (project / "Data").mkdir()
        (project / "Scripts").mkdir()
        game_id = self._game_id(metadata["game"])
        engine = {"Sonic 1":"RSDKv4", "Sonic 2":"RSDKv4", "Sonic CD":"RSDKv3",
                  "Sonic Mania":"RSDKv5", "Sonic 3":"UNVERIFIED"}.get(metadata["game"], "UNVERIFIED")
        metadata.update({"format": "HedgehodMod", "formatVersion": 1, "gameId": game_id,
                         "signature": f"{'SMMD' if metadata['game'] == 'Sonic Mania' else 'HMOD'}:{game_id}:{engine}:v1"})
        (project / "project.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
        ini = (f"Name={metadata['name']}\nDescription={metadata.get('description') or metadata['type']}\n"
               f"Author={metadata['author']}\nVersion={metadata['version']}\n")
        if metadata["game"] in ("Sonic 1", "Sonic 2"):
            ini += "TargetVersion=4\n"
        (project / "mod.ini").write_text(ini, encoding="utf-8")
        return project

    @staticmethod
    def _game_id(game):
        return {"Sonic 1":"SONIC_1", "Sonic 2":"SONIC_2", "Sonic 3":"SONIC_3",
                "Sonic CD":"SONIC_CD", "Sonic Mania":"SONIC_MANIA"}.get(game, "SONIC_1")

    def open_mod_project(self, project):
        project = Path(project)
        try:
            metadata = json.loads((project / "project.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            metadata = {"name": project.name, "version": "?", "author": "?", "type": "Mod", "game": self.profile_name.get()}
        win = tk.Toplevel(self.root)
        win.title(f"Proyecto · {metadata.get('name', project.name)}")
        win.geometry("720x500")
        win.configure(bg=BG)
        win.transient(self.root)
        self.label(win, f"{metadata.get('game', '')}  /  {metadata.get('type', 'Mod').upper()}", fg=CYAN,
                   font=(self.font_family.get(), 9, "bold")).pack(anchor="w", padx=22, pady=(22, 4))
        self.label(win, metadata.get("name", project.name), font=(self.font_family.get(), 22, "bold")).pack(anchor="w", padx=22)
        info = f"Versión {metadata.get('version', '?')}   ·   Autor: {metadata.get('author', '?')}\n{metadata.get('description', '')}\n\n{project}"
        self.label(win, info, fg=MUTED, justify="left", wraplength=660).pack(anchor="w", padx=22, pady=(8, 18))
        card = tk.Frame(win, bg=PANEL, padx=18, pady=18, highlightbackground="#284565", highlightthickness=1)
        card.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        self.label(card, "ARCHIVOS DEL MOD", bg=PANEL, fg=CYAN, font=(self.font_family.get(), 9, "bold")).pack(anchor="w")
        self.label(card, "Data/  · recursos gráficos, audio y contenido compatible\nScripts/  · código/script del proyecto\nmod.ini  · metadatos del loader",
                   bg=PANEL, fg=WHITE, justify="left", font=("Consolas", 10)).pack(anchor="w", pady=(10, 16))
        row = tk.Frame(card, bg=PANEL); row.pack(anchor="w")
        self.button(row, "Editor de código", lambda: self.open_code_editor(project)).pack(side="left", padx=(0, 8))
        self.button(row, "Workspace de sprites", lambda: self.open_visual_workspace(metadata.get("game", self.profile_name.get()))).pack(side="left", padx=(0, 8))
        self.button(row, "Abrir carpeta", lambda: os.startfile(str(project))).pack(side="left")
        footer = tk.Frame(win, bg=BG); footer.pack(fill="x", padx=18, pady=(0, 16))
        self.button(footer, "Instalar en el juego", lambda: self._install_mod_project(project, metadata)).pack(side="left")
        self.button(footer, "Exportar para compartir…", lambda: self._export_mod_package(project, metadata), primary=True).pack(side="right")

    def open_mod_hub(self):
        win = tk.Toplevel(self.root)
        win.title("Mods y proyectos locales")
        win.geometry("820x560")
        win.minsize(680, 460)
        win.configure(bg=BG)
        win.transient(self.root)
        self.label(win, "BIBLIOTECA LOCAL Y COMPARTIR", fg=CYAN,
                   font=(self.font_family.get(), 10, "bold")).pack(anchor="w", padx=20, pady=(18, 3))
        self.label(win, "Tus proyectos y paquetes de la comunidad", font=(self.font_family.get(), 20, "bold")).pack(anchor="w", padx=20)
        self.label(win, "Importa .hmod/.smmd o exporta un paquete para compartirlo. La publicación en línea requiere un servicio web externo.",
                   fg=MUTED, wraplength=760, justify="left").pack(anchor="w", padx=20, pady=(5, 12))
        list_frame = tk.Frame(win, bg=PANEL, padx=8, pady=8)
        list_frame.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        scrollbar = tk.Scrollbar(list_frame); scrollbar.pack(side="right", fill="y")
        listing = tk.Listbox(list_frame, bg="#09172a", fg=WHITE, selectbackground="#15516d", relief="flat",
                             font=("Segoe UI", 10), yscrollcommand=scrollbar.set)
        listing.pack(side="left", fill="both", expand=True); scrollbar.configure(command=listing.yview)
        projects = self._list_mod_projects()
        for project, metadata in projects:
            listing.insert("end", f"{metadata.get('name', project.name)}  ·  {metadata.get('game', '?')}  ·  v{metadata.get('version', '?')}  ·  {metadata.get('author', '?')}")
        if not projects:
            listing.insert("end", "Aún no hay proyectos. Pulsa Crear mod para empezar o importa un paquete .hmod/.smmd.")
        row = tk.Frame(win, bg=BG); row.pack(fill="x", padx=18, pady=(0, 18))
        def selected_project():
            sel = listing.curselection()
            return projects[sel[0]] if sel and sel[0] < len(projects) else None
        self.button(row, "Crear mod", lambda: (win.destroy(), self.create_mod_project()), primary=True).pack(side="left")
        self.button(row, "Importar .hmod / .smmd…", lambda: self._import_mod_package(win)).pack(side="left", padx=7)
        self.button(row, "Abrir seleccionado", lambda: self.open_mod_project(selected_project()[0]) if selected_project() else None).pack(side="left")
        self.button(row, "Exportar seleccionado…", lambda: self._export_mod_package(*selected_project()) if selected_project() else None).pack(side="left", padx=7)
        self.button(row, "Instalar…", lambda: self._install_mod_project(*selected_project()) if selected_project() else None).pack(side="left")

    def _list_mod_projects(self):
        projects = []
        for game in GAME_NAMES:
            root = GAME_DATA_DIR / game / "Mod Projects"
            if not root.is_dir():
                continue
            for metadata_file in root.rglob("project.json"):
                try:
                    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
                    projects.append((metadata_file.parent, metadata))
                except (OSError, json.JSONDecodeError):
                    continue
        return sorted(projects, key=lambda item: item[1].get("name", item[0].name).casefold())

    def _export_mod_package(self, project, metadata):
        project = Path(project)
        ext = ".smmd" if metadata.get("game") == "Sonic Mania" else ".hmod"
        target = filedialog.asksaveasfilename(parent=self.root, title="Exportar paquete para compartir",
            initialfile=self._safe_slug(metadata.get("name", project.name)) + ext,
            defaultextension=ext, filetypes=[("Paquete Hedgehod", "*.hmod *.smmd")])
        if not target:
            return
        files = [path for path in project.rglob("*") if path.is_file() and path.name != "package_manifest.json"]
        hashes = {path.relative_to(project).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
        package_meta = {"format": "HedgehodModPackage", "formatVersion": 1,
                        "game": metadata.get("game"), "gameId": metadata.get("gameId", self._game_id(metadata.get("game", "Sonic 1"))),
                        "extension": ext, "signature": metadata.get("signature", ""), "filesSha256": hashes}
        try:
            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("package_manifest.json", json.dumps(package_meta, indent=2, ensure_ascii=False))
                for path in files:
                    archive.write(path, path.relative_to(project).as_posix())
        except OSError as exc:
            messagebox.showerror("No se pudo exportar", str(exc), parent=self.root)
            return
        messagebox.showinfo("Paquete listo", f"Paquete creado para compartir:\n{target}\n\nEste archivo no contiene los datos comerciales del juego.", parent=self.root)

    def _import_mod_package(self, parent=None):
        source = filedialog.askopenfilename(parent=parent or self.root, title="Importar mod de la comunidad",
            filetypes=[("Paquetes de mod", "*.hmod *.smmd"), ("Todos los archivos", "*.*")])
        if not source:
            return
        source = Path(source)
        project = None
        try:
            with zipfile.ZipFile(source) as archive:
                infos = archive.infolist()
                if len(infos) > 10000 or sum(item.file_size for item in infos) > 512*1024*1024:
                    raise ValueError("El paquete supera los límites de tamaño admitidos.")
                manifest = json.loads(archive.read("package_manifest.json").decode("utf-8"))
                game = manifest.get("game")
                if game not in GAME_NAMES:
                    raise ValueError("El paquete declara un juego no compatible.")
                expected_ext = ".smmd" if game == "Sonic Mania" else ".hmod"
                if manifest.get("format") != "HedgehodModPackage" or manifest.get("formatVersion") != 1:
                    raise ValueError("Formato de paquete Hedgehod desconocido.")
                if source.suffix.lower() != expected_ext:
                    raise ValueError(f"El paquete indica {game}, así que debe usar la extensión {expected_ext}.")
                if manifest.get("extension") != expected_ext:
                    raise ValueError("La extensión del paquete no coincide con el juego indicado.")
                file_map = manifest.get("filesSha256", {})
                safe = []
                seen = set()
                for info in infos:
                    if info.filename == "package_manifest.json":
                        continue
                    member = Path(info.filename)
                    if member.is_absolute() or ".." in member.parts or not member.parts:
                        raise ValueError("El paquete contiene una ruta no permitida.")
                    normalized_name = member.as_posix().casefold()
                    if normalized_name in seen:
                        raise ValueError("El paquete contiene rutas duplicadas.")
                    seen.add(normalized_name)
                    mode = info.external_attr >> 16
                    if mode & 0o170000 == 0o120000:
                        raise ValueError("El paquete contiene un enlace simbólico no permitido.")
                    if not info.is_dir():
                        payload = archive.read(info)
                        expected = file_map.get(member.as_posix())
                        if not expected or hashlib.sha256(payload).hexdigest() != expected:
                            raise ValueError(f"No coincide la suma de integridad de {member.name}.")
                    safe.append((info, member))
                if "mod.ini" not in seen:
                    raise ValueError("El paquete no contiene mod.ini.")
                root = GAME_DATA_DIR / game / "Mod Projects" / "Imported"
                root.mkdir(parents=True, exist_ok=True)
                project = root / self._safe_slug(source.stem)
                index = 2
                while project.exists():
                    project = root / f"{self._safe_slug(source.stem)}-{index}"; index += 1
                project.mkdir()
                for info, member in safe:
                    destination = (project / member).resolve()
                    if project.resolve() not in destination.parents and destination != project.resolve():
                        raise ValueError("El paquete intenta escribir fuera de su carpeta.")
                    if info.is_dir():
                        destination.mkdir(parents=True, exist_ok=True)
                    else:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes(archive.read(info))
                project_data = project / "project.json"
                if not project_data.is_file():
                    metadata = {"name": source.stem, "game": game, "gameId": manifest.get("gameId"),
                                "version": "1.0", "author": "Importado", "type": "Mod",
                                "signature": manifest.get("signature"), "format": "HedgehodMod", "formatVersion": 1}
                    project_data.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
                else:
                    metadata = json.loads(project_data.read_text(encoding="utf-8"))
                    if metadata.get("game") != game:
                        raise ValueError("Los metadatos del proyecto no coinciden con el juego declarado en el paquete.")
        except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError, ValueError) as exc:
            if project is not None and project.exists():
                shutil.rmtree(project, ignore_errors=True)
            messagebox.showerror("No se pudo importar el mod", str(exc), parent=parent or self.root)
            return
        messagebox.showinfo("Mod importado", f"El proyecto se añadió a la biblioteca local:\n{project}", parent=parent or self.root)
        self.open_mod_project(project)

    def _install_mod_project(self, project, metadata):
        game = metadata.get("game", self.profile_name.get())
        game_folder = self.profiles.get(game, {}).get("game_dir", "").strip()
        if not game_folder or not Path(game_folder).expanduser().is_dir():
            messagebox.showwarning("Selecciona Game Data", f"Configura primero la carpeta del juego {game}.", parent=self.root)
            return
        target_root = Path(game_folder).expanduser() / "mods"
        target_root.mkdir(parents=True, exist_ok=True)
        target = target_root / self._safe_slug(metadata.get("name", Path(project).name))
        if target.exists():
            messagebox.showwarning("El destino ya existe", f"No sobrescribí la carpeta:\n{target}", parent=self.root)
            return
        try:
            shutil.copytree(project, target, ignore=shutil.ignore_patterns("project.json", "package_manifest.json"))
        except OSError as exc:
            messagebox.showerror("No se pudo instalar el mod", str(exc), parent=self.root)
            return
        messagebox.showinfo("Mod instalado", f"Se copió a:\n{target}\n\nComprueba la compatibilidad del motor y activa el mod desde el juego.", parent=self.root)

    def open_code_editor(self, project):
        project = Path(project)
        win = tk.Toplevel(self.root)
        win.title(f"Editor de código · {project.name}")
        win.geometry("1000x700")
        win.configure(bg=BG)
        win.transient(self.root)
        current = {"path": None}
        top = tk.Frame(win, bg="#081626", padx=14, pady=10); top.pack(fill="x")
        self.label(top, "EDITOR DE CÓDIGO DE MOD", bg="#081626", fg=CYAN,
                   font=(self.font_family.get(), 10, "bold")).pack(side="left")
        status = tk.StringVar(value="Abre un script del proyecto o crea uno nuevo.")
        self.label(win, "", textvariable=status, fg=MUTED, font=(self.font_family.get(), 8), anchor="w").pack(fill="x", padx=14, pady=5)
        text = tk.Text(win, bg="#07111e", fg="#d9e8ff", insertbackground=WHITE, selectbackground="#174967",
                       font=("Consolas", 11), undo=True, wrap="none", relief="flat", padx=12, pady=10)
        text.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        xscroll = tk.Scrollbar(text, orient="horizontal", command=text.xview); xscroll.pack(side="bottom", fill="x")
        yscroll = tk.Scrollbar(text, orient="vertical", command=text.yview); yscroll.pack(side="right", fill="y")
        text.configure(xscrollcommand=xscroll.set, yscrollcommand=yscroll.set)
        def load_file(path):
            try:
                content = Path(path).read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                messagebox.showerror("No se pudo abrir el código", str(exc), parent=win); return
            text.delete("1.0", "end"); text.insert("1.0", content)
            current["path"] = Path(path); status.set(str(path))
        def save_file():
            path = current["path"]
            if path is None:
                path = filedialog.asksaveasfilename(parent=win, initialdir=str(project / "Scripts"),
                    initialfile="NewScript.txt", defaultextension=".txt",
                    filetypes=[("Scripts", "*.txt *.cpp *.h *.ini"), ("Todos", "*.*")])
                if not path: return
                path = Path(path)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text.get("1.0", "end-1c"), encoding="utf-8")
                current["path"] = path; status.set(f"Guardado: {path}")
            except OSError as exc:
                messagebox.showerror("No se pudo guardar", str(exc), parent=win)
        buttons = tk.Frame(win, bg=BG); buttons.pack(fill="x", padx=14, pady=(0, 14))
        self.button(buttons, "Abrir archivo de código…", lambda: self._choose_code_file(win, load_file)).pack(side="left")
        self.button(buttons, "Guardar", save_file, primary=True).pack(side="left", padx=7)
        self.button(buttons, "Abrir carpeta Scripts", lambda: os.startfile(str(project / "Scripts"))).pack(side="left")
        self.label(win, "El editor guarda los archivos; no compila ni ejecuta código. Usa código fuente/decompilado y herramientas compatibles con tu build de RSDK.",
                   fg=MUTED, wraplength=950, justify="left", font=(self.font_family.get(), 8)).pack(anchor="w", padx=14, pady=(0, 10))

    def _choose_code_file(self, parent, callback):
        path = filedialog.askopenfilename(parent=parent, title="Abrir código fuente o script",
            filetypes=[("Código y scripts", "*.txt *.cpp *.h *.hpp *.c *.ini *.xml *.json *.lua"), ("Todos los archivos", "*.*")])
        if path:
            callback(path)

    def open_visual_workspace(self, game_name=None):
        """Open the native sprite workspace for the selected game profile."""
        game_name = game_name or self.profile_name.get()
        profile = self.profiles.get(game_name, {})
        game_dir = Path(profile.get("game_dir", "")).expanduser()
        saved = profile.get("asset_data_dir", "")
        candidates = ([Path(saved).expanduser()] if saved else []) + [game_dir / "Data", game_dir]
        data_root = next((resolved for p in candidates if p.is_dir()
                          for resolved in [self._find_asset_root(p)] if resolved is not None), None)
        win = tk.Toplevel(self.root)
        win.title(f"Hedgehod Launcher — Editor de sprites · {game_name}")
        win.geometry("1180x760")
        win.minsize(900, 600)
        win.configure(bg=BG)
        win.transient(self.root)
        win.game_name = game_name
        win.data_root = data_root
        win.assets = []
        win.category = tk.StringVar(value="Players")
        win.selected_asset = None
        win.preview_photo = None
        win.preview_image = None
        win.preview_frames = []
        win.base_preview_frames = []
        win.frame_durations = []
        win.frame_index = 0
        win.animation_after = None
        win.animation_playing = False
        win.asset_path_var = tk.StringVar(value="")
        win.dimensions_var = tk.StringVar(value="Selecciona un asset para ver sus dimensiones y límites.")
        win.width_var = tk.StringVar(value="1")
        win.height_var = tk.StringVar(value="1")
        win.keep_ratio = tk.BooleanVar(value=True)
        win.action_var = tk.StringVar(value="Idle")
        win._updating_size = False

        header = tk.Frame(win, bg="#081626", padx=18, pady=12)
        header.pack(fill="x")
        self.label(header, f"WORKSPACE DE SPRITES  /  {game_name.upper()}", bg="#081626", fg=CYAN,
                   font=(self.font_family.get(), 11, "bold")).pack(side="left")
        self.button(header, "Mods y proyectos", self.open_mod_hub).pack(side="right", padx=(8, 0))
        self.button(header, "Elegir carpeta Data…", lambda: self._choose_workspace_data(win)).pack(side="right")

        tabs = tk.Frame(win, bg=BG, padx=16, pady=10)
        tabs.pack(fill="x")
        for category in ("Stages", "Players", "Misc"):
            button = self.button(tabs, category, lambda c=category: self._populate_sprite_assets(win, c),
                                 primary=(category == "Players"))
            button.pack(side="left", padx=(0, 8))
            win.category_buttons = getattr(win, "category_buttons", {})
            win.category_buttons[category] = button
        win.library_count_var = tk.StringVar(value="Biblioteca sin cargar")
        self.label(tabs, "", textvariable=win.library_count_var, fg=MUTED,
                   font=(self.font_family.get(), 8)).pack(side="right")

        # Frame options take one pixel distance; the tuple form is valid for
        # geometry managers (pack/grid), not for tk.Frame's own padx/pady.
        win.action_bar = tk.Frame(win, bg=BG, padx=16, pady=0)
        # Animation controls are part of the native sprite editor timeline.
        win.action_assignment_var = tk.StringVar(value="")

        body = tk.Frame(win, bg=BG, padx=16, pady=0)
        # Place the editor body below the packed header/tabs/action row. Explicit
        # bounds avoid Tk pack propagation collapsing its children on Windows.
        win.update_idletasks()
        body_y = tabs.winfo_y() + tabs.winfo_height() + 8
        body.place(x=0, y=body_y, relwidth=1, relheight=1, height=-body_y)
        win.sprite_body = body
        win.sprite_tabs = tabs
        library = tk.Frame(body, bg=PANEL, width=280, highlightbackground="#284565", highlightthickness=1)
        library.place(x=16, y=0, width=280, relheight=1, height=-16)
        library.pack_propagate(False)
        self.label(library, "BIBLIOTECA DEL JUEGO", bg=PANEL, fg=CYAN,
                   font=(self.font_family.get(), 9, "bold")).pack(anchor="w", padx=12, pady=(12, 5))
        list_frame = tk.Frame(library, bg=PANEL)
        list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        scroll = tk.Scrollbar(list_frame)
        scroll.pack(side="right", fill="y")
        style = ttk.Style(win)
        style.configure("Sprite.Treeview", background="#09172a", foreground=WHITE, fieldbackground="#09172a",
                        borderwidth=0, rowheight=25, font=("Segoe UI", 9))
        style.map("Sprite.Treeview", background=[("selected", "#15516d")], foreground=[("selected", WHITE)])
        win.asset_list = ttk.Treeview(list_frame, show="tree", selectmode="browse", style="Sprite.Treeview",
                                      yscrollcommand=scroll.set)
        win.asset_list.pack(side="left", fill="both", expand=True)
        scroll.configure(command=win.asset_list.yview)
        win.asset_list.bind("<<TreeviewSelect>>", lambda _e: self._select_workspace_asset(win))

        editor = tk.Frame(body, bg=PANEL, highlightbackground="#284565", highlightthickness=1)
        editor.place(x=308, y=0, relwidth=1, relheight=1, width=-324, height=-16)
        editor.grid_columnconfigure(0, weight=1)
        editor.grid_columnconfigure(1, weight=0)
        editor.grid_rowconfigure(1, weight=1)
        self.label(editor, "PREVISUALIZACIÓN Y LÍMITES", bg=PANEL, fg=CYAN,
                   font=(self.font_family.get(), 9, "bold")).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 6))
        self.button(editor, "✎  Editar sprite", lambda: self.open_native_sprite_editor(win), primary=True).grid(
            row=0, column=1, sticky="e", padx=12, pady=(8, 4))
        win.preview_canvas = tk.Canvas(editor, bg="#09111e", highlightthickness=1,
                                      highlightbackground="#344b66", cursor="crosshair")
        win.preview_canvas.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=12, pady=(0, 8))
        win.preview_canvas.bind("<Configure>", lambda _e: self._draw_sprite_preview(win))
        controls = tk.Frame(editor, bg=PANEL)
        controls.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))
        controls.grid_columnconfigure(0, weight=1)
        self.label(controls, "", textvariable=win.dimensions_var, bg=PANEL, fg=WHITE,
                   font=(self.font_family.get(), 9)).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 5))
        self.label(controls, "", textvariable=win.asset_path_var, bg=PANEL, fg=MUTED,
                   font=(self.font_family.get(), 8), anchor="w").grid(row=1, column=0, columnspan=6, sticky="ew", pady=(0, 7))
        self.label(controls, "Ancho", bg=PANEL, fg=WHITE).grid(row=2, column=0, sticky="w")
        width_entry = tk.Entry(controls, textvariable=win.width_var, width=8, bg="#09172a", fg=WHITE, insertbackground=WHITE, relief="flat")
        width_entry.grid(row=2, column=1, padx=(5, 12), ipady=4)
        self.label(controls, "Alto", bg=PANEL, fg=WHITE).grid(row=2, column=2, sticky="w")
        height_entry = tk.Entry(controls, textvariable=win.height_var, width=8, bg="#09172a", fg=WHITE, insertbackground=WHITE, relief="flat")
        height_entry.grid(row=2, column=3, padx=(5, 12), ipady=4)
        tk.Checkbutton(controls, text="Mantener proporción", variable=win.keep_ratio, bg=PANEL, fg=WHITE,
                       selectcolor="#09172a", activebackground=PANEL, activeforeground=WHITE).grid(row=2, column=4, sticky="w")
        width_entry.bind("<KeyRelease>", lambda _e: self._size_changed(win, "width"))
        height_entry.bind("<KeyRelease>", lambda _e: self._size_changed(win, "height"))
        buttons = tk.Frame(controls, bg=PANEL)
        buttons.grid(row=3, column=0, columnspan=6, sticky="w", pady=(10, 0))
        win.animation_button = self.button(buttons, "Ⅱ Pausar", lambda: self._toggle_sprite_animation(win))
        win.animation_button.pack(side="left", padx=(0, 7))
        self.button(buttons, "Editar paleta…", lambda: self._edit_sprite_palette(win)).pack(side="left", padx=(0, 7))
        self.button(buttons, "Abrir en Aseprite / LibreSprite", lambda: self._open_selected_in_libresprite(win)).pack(side="left", padx=(0, 8))
        self.button(buttons, "Guardar copia reescalada…", lambda: self._save_resized_sprite(win), primary=True).pack(side="left")
        self.label(editor, "El contorno azul marca el límite completo del sprite; la cuadrícula ayuda a revisar píxeles.",
                   bg=PANEL, fg=MUTED, font=(self.font_family.get(), 8)).grid(row=3, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 10))
        win.protocol("WM_DELETE_WINDOW", lambda: self._close_sprite_workspace(win))

        if data_root is None:
            self._show_workspace_empty(win)
        else:
            self._scan_workspace_assets(win)
            first_category = next((category for category in ("Players", "Stages", "Misc")
                                   if any(item["category"] == category for item in win.assets)), "Players")
            self._populate_sprite_assets(win, first_category)

    @staticmethod
    def _has_asset_folders(folder):
        asset_names = {"sprites", "animations", "stages", "stage", "backgrounds", "players", "characters"}
        return folder.is_dir() and (folder.name.casefold() in asset_names or any(
            (folder / name).is_dir() for name in asset_names))

    def _find_asset_root(self, folder):
        folder = Path(folder)
        if self._has_asset_folders(folder):
            return folder
        names = {"sprites", "animations", "stages", "stage", "backgrounds", "players", "characters"}
        try:
            candidates = []
            excluded = {"mods", "mod projects", "sprite edits", "imported", "browser workspace"}
            for child in folder.rglob("*"):
                if not child.is_dir() or child.name.casefold() not in names:
                    continue
                if any(part.casefold() in excluded for part in child.relative_to(folder).parts):
                    continue
                data_root = child.parent
                depth = len(child.relative_to(folder).parts)
                preferred = 0 if data_root.name.casefold() == "data" else 1
                candidates.append((preferred, depth, data_root))
            if candidates:
                return min(candidates, key=lambda item: (item[0], item[1]))[2]
        except OSError:
            return None
        return None

    def _show_workspace_empty(self, win):
        self._clear_asset_tree(win)
        win.asset_list.insert("", "end", text="Aún no hay assets cargados.", open=True)
        win.asset_list.insert("", "end", text="Selecciona una carpeta Data exportada arriba.")
        win.dimensions_var.set("Exporta el Data.rsdk con RetroED y selecciona la carpeta Data.")
        win.empty_message = ("El editor trabaja sobre una copia local exportada.\n\n"
            "En RetroED: Tools → RSDK Unpacker → Export DataPack.\n"
            "Luego selecciona la carpeta exportada aquí. Si elegiste una carpeta contenedora, buscaré dentro.")
        self._draw_sprite_preview(win)

    def _choose_workspace_data(self, win):
        selected = filedialog.askdirectory(parent=win, title=f"Selecciona Data exportada de {win.game_name}")
        if not selected:
            return
        root = Path(selected).expanduser()
        resolved_root = self._find_asset_root(root)
        if resolved_root is not None:
            root = resolved_root
        win.data_root = root
        self.profiles.setdefault(win.game_name, {})["asset_data_dir"] = str(root.resolve())
        self.save_config()
        self._scan_workspace_assets(win)
        first_category = next((category for category in ("Players", "Stages", "Misc")
                               if any(item["category"] == category for item in win.assets)), "Players")
        self._populate_sprite_assets(win, first_category)

    def _scan_workspace_assets(self, win):
        root = win.data_root
        win.assets = []
        if not root or not root.is_dir():
            self._show_workspace_empty(win)
            return
        if hasattr(win, "empty_message"):
            del win.empty_message
        suffixes = {".gif", ".png", ".bmp", ".jpg", ".jpeg", ".webp", ".tga"}
        hints = {"sprites", "sprite", "animations", "animation", "stages", "stage", "backgrounds", "background", "players", "player", "characters", "character"}
        try:
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in suffixes:
                    continue
                relative = path.relative_to(root)
                parent_parts = {part.casefold() for part in relative.parts[:-1]}
                if root.name.casefold() in hints:
                    parent_parts.add(root.name.casefold())
                if not parent_parts.intersection(hints):
                    continue
                parts = parent_parts
                if parts.intersection({"stages", "stage", "backgrounds", "background"}):
                    category = "Stages"
                elif parts.intersection({"players", "player", "characters", "character"}) or any(
                    token in path.stem.casefold() for token in ("sonic", "tails", "knuck", "player")):
                    category = "Players"
                else:
                    category = "Misc"
                win.assets.append({"path": path, "relative": relative, "category": category})
        except OSError as exc:
            messagebox.showwarning("Biblioteca incompleta", f"No se pudo leer toda la carpeta:\n{exc}", parent=win)
        win.assets.sort(key=lambda item: item["relative"].as_posix().casefold())
        counts = {category: sum(item["category"] == category for item in win.assets)
                  for category in ("Stages", "Players", "Misc")}
        for category, button in getattr(win, "category_buttons", {}).items():
            button.configure(text=f"{category} ({counts[category]})")
        win.library_count_var.set(f"{len(win.assets)} assets encontrados · {root}")

    def _populate_sprite_assets(self, win, category):
        win.category.set(category)
        for button_category, button in getattr(win, "category_buttons", {}).items():
            active = button_category == category
            button.configure(bg=YELLOW if active else "#1a304b",
                             fg="#122139" if active else WHITE,
                             activebackground="#fff0a4" if active else "#284967",
                             activeforeground="#122139" if active else WHITE)
        visible = [asset for asset in win.assets if asset["category"] == category]
        win.visible_assets = visible
        self._layout_sprite_body(win)
        old_items = win.asset_list.get_children()
        if old_items:
            win.asset_list.delete(*old_items)
        win.asset_by_iid = {}
        if hasattr(win, "empty_message"):
            del win.empty_message
        folder_nodes = {}
        first_iid = None
        for asset in visible:
            parent_iid = ""
            folder_parts = asset["relative"].parent.parts
            accumulated = []
            for part in folder_parts:
                accumulated.append(part)
                key = "/".join(accumulated)
                if key not in folder_nodes:
                    folder_nodes[key] = win.asset_list.insert(parent_iid, "end", text=part, open=True)
                parent_iid = folder_nodes[key]
            iid = win.asset_list.insert(parent_iid, "end", text=asset["path"].name)
            win.asset_by_iid[iid] = asset
            if first_iid is None:
                first_iid = iid
        if not visible:
            win.asset_list.insert("", "end", text="No hay imágenes en esta sección.")
            win.selected_asset = None
            win.preview_image = None
            win.preview_frames = []
            win.animation_playing = False
            if win.animation_after is not None:
                win.after_cancel(win.animation_after); win.animation_after = None
            win.animation_button.configure(text="▶ Reproducir", state="disabled")
            win.base_preview_frames = []
            win.asset_path_var.set("")
            win.dimensions_var.set(f"No se encontraron assets de {category}.")
            win.empty_message = (f"No se encontraron imágenes en {category}.\n\n"
                f"Assets reconocidos en total: {len(win.assets)}. Prueba otra sección o selecciona la exportación Data correcta.")
            self._draw_sprite_preview(win)
        else:
            win.asset_list.selection_set(first_iid)
            win.asset_list.focus(first_iid)
            win.asset_list.see(first_iid)
            self._select_workspace_asset(win)

    def _clear_asset_tree(self, win):
        if hasattr(win, "asset_list"):
            children = win.asset_list.get_children()
            if children:
                win.asset_list.delete(*children)

    def _layout_sprite_body(self, win):
        win.update_idletasks()
        body_y = win.action_bar.winfo_y() + win.action_bar.winfo_height() + 8 if win.action_bar.winfo_manager() else win.sprite_tabs.winfo_y() + win.sprite_tabs.winfo_height() + 8
        win.sprite_body.place_configure(y=body_y, relheight=1, height=-body_y)

    @staticmethod
    def _close_sprite_workspace(win):
        if win.animation_after is not None:
            try:
                win.after_cancel(win.animation_after)
            except tk.TclError:
                pass
        win.destroy()

    def _select_workspace_asset(self, win):
        selection = win.asset_list.selection()
        if not selection:
            return
        asset = getattr(win, "asset_by_iid", {}).get(selection[0])
        if asset is None:
            return
        try:
            with Image.open(asset["path"]) as source:
                source.seek(0)
                win.source_format = source.format or asset["path"].suffix.lstrip(".").upper()
                win.source_mode = source.mode
                win.source_info = dict(source.info)
                loaded_frames = [frame.convert("RGBA").copy() for frame in ImageSequence.Iterator(source)]
                loaded_durations = [max(30, frame.info.get("duration", source.info.get("duration", 100)))
                                    for frame in ImageSequence.Iterator(source)]
            win.base_preview_frames = [frame.copy() for frame in loaded_frames]
            win.base_frame_durations = list(loaded_durations)
            win.preview_frames = [frame.copy() for frame in loaded_frames]
            win.frame_durations = list(loaded_durations)
            action = win.action_var.get()
            profile = self.profiles.get(win.game_name, {})
            assigned_path = profile.get("sprite_actions", {}).get(action)
            strip = profile.get("sprite_action_strips", {}).get(action)
            if assigned_path == asset["relative"].as_posix() and strip:
                sheet = loaded_frames[0]
                x, y = int(strip["x"]), int(strip["y"])
                fw, fh = int(strip["width"]), int(strip["height"])
                count, spacing = int(strip["count"]), int(strip.get("spacing", 0))
                axis = strip.get("axis", "horizontal")
                sliced = []
                for frame_number in range(count):
                    left = x + (frame_number * (fw + spacing) if axis == "horizontal" else 0)
                    top = y + (frame_number * (fh + spacing) if axis == "vertical" else 0)
                    if left + fw <= sheet.width and top + fh <= sheet.height:
                        sliced.append(sheet.crop((left, top, left+fw, top+fh)))
                if sliced:
                    win.preview_frames = sliced
                    win.frame_durations = [max(30, int(strip.get("duration", 100)))] * len(sliced)
            win.palette_edits = {}
            win.frame_index = 0
            win.preview_image = win.preview_frames[0] if win.preview_frames else Image.open(asset["path"]).convert("RGBA")
            if win.animation_after is not None:
                win.after_cancel(win.animation_after); win.animation_after = None
            win.animation_playing = len(win.preview_frames) > 1
            win.animation_button.configure(text="Ⅱ Pausar" if win.animation_playing else "▶ Reproducir",
                                           state="normal" if len(win.preview_frames) > 1 else "disabled")
            win.selected_asset = asset
            if hasattr(win, "empty_message"):
                del win.empty_message
            width, height = win.preview_image.size
            win.original_size = (width, height)
            win._updating_size = True
            win.width_var.set(str(width)); win.height_var.set(str(height))
            win._updating_size = False
            win.dimensions_var.set(f"Original: {width} × {height} px   ·   Límites: X 0–{width-1}, Y 0–{height-1}   ·   {win.source_format}")
            win.asset_path_var.set(asset["relative"].as_posix())
            self._update_action_assignment_status(win)
            self._draw_sprite_preview(win)
            if win.animation_playing:
                self._schedule_sprite_frame(win)
        except (OSError, ValueError) as exc:
            messagebox.showerror("No se pudo abrir el asset", str(exc), parent=win)

    def _update_action_assignment_status(self, win):
        mapping = self.profiles.get(win.game_name, {}).get("sprite_actions", {})
        assigned = mapping.get(win.action_var.get())
        if assigned:
            strip = self.profiles.get(win.game_name, {}).get("sprite_action_strips", {}).get(win.action_var.get())
            if strip:
                win.action_assignment_var.set(f"{win.action_var.get()}: {strip.get('count', 0)} frames · {Path(assigned).name}")
            else:
                win.action_assignment_var.set(f"{win.action_var.get()}: {Path(assigned).name} · GIF frames o configura tira")
        else:
            win.action_assignment_var.set(f"{win.action_var.get()}: sin asignar")

    def _select_assigned_action(self, win):
        if win.category.get() != "Players":
            return
        mapping = self.profiles.get(win.game_name, {}).get("sprite_actions", {})
        relative = mapping.get(win.action_var.get())
        if relative:
            for iid, asset in getattr(win, "asset_by_iid", {}).items():
                if asset["relative"].as_posix() == relative:
                    win.asset_list.selection_set(iid)
                    win.asset_list.focus(iid)
                    win.asset_list.see(iid)
                    self._select_workspace_asset(win)
                    return
        self._update_action_assignment_status(win)

    def _assign_sprite_action(self, win):
        asset = getattr(win, "selected_asset", None)
        if asset is None or win.category.get() != "Players":
            messagebox.showinfo("Selecciona un sprite", "Selecciona una imagen en Players antes de asignarla al movimiento.", parent=win)
            return
        profile = self.profiles.setdefault(win.game_name, {})
        mapping = profile.setdefault("sprite_actions", {})
        previous = mapping.get(win.action_var.get())
        mapping[win.action_var.get()] = asset["relative"].as_posix()
        if previous != asset["relative"].as_posix():
            profile.setdefault("sprite_action_strips", {}).pop(win.action_var.get(), None)
        self._update_action_assignment_status(win)
        self.save_config()

    def _configure_action_strip(self, win):
        asset = getattr(win, "selected_asset", None)
        if asset is None or win.category.get() != "Players":
            messagebox.showinfo("Selecciona un sprite", "Selecciona primero una hoja en Players.", parent=win)
            return
        try:
            with Image.open(asset["path"]) as source:
                sheet_width, sheet_height = source.size
        except OSError as exc:
            messagebox.showerror("No se pudo leer la hoja", str(exc), parent=win)
            return
        dialog = tk.Toplevel(win)
        dialog.title(f"Tira de animación · {win.action_var.get()}")
        dialog.geometry("440x510")
        dialog.configure(bg=BG)
        dialog.transient(win)
        self.label(dialog, f"ANIMACIÓN · {win.action_var.get().upper()}", fg=CYAN,
                   font=(self.font_family.get(), 10, "bold")).pack(anchor="w", padx=18, pady=(16, 6))
        self.label(dialog, f"Hoja: {asset['path'].name} · {sheet_width}×{sheet_height}px\nIndica el rectángulo del primer frame y cuántos frames contiguos tiene la tira.",
                   fg=MUTED, wraplength=400, justify="left").pack(anchor="w", padx=18, pady=(0, 12))
        form = tk.Frame(dialog, bg=PANEL, padx=16, pady=14)
        form.pack(fill="x", padx=16)
        variables = {
            "X inicial": tk.StringVar(value="0"), "Y inicial": tk.StringVar(value="0"),
            "Ancho del frame": tk.StringVar(value=str(max(1, sheet_width//8))),
            "Alto del frame": tk.StringVar(value=str(max(1, sheet_height//8))),
            "Cantidad de frames": tk.StringVar(value="8"), "Separación": tk.StringVar(value="0"),
            "Duración (ms)": tk.StringVar(value="100"),
        }
        for row, (label, variable) in enumerate(variables.items()):
            self.label(form, label, bg=PANEL, fg=WHITE).grid(row=row, column=0, sticky="w", pady=4)
            tk.Entry(form, textvariable=variable, width=12, bg="#09172a", fg=WHITE,
                     insertbackground=WHITE, relief="flat").grid(row=row, column=1, sticky="e", pady=4, ipady=3)
        self.label(form, "Dirección", bg=PANEL, fg=WHITE).grid(row=7, column=0, sticky="w", pady=4)
        axis = tk.StringVar(value="horizontal")
        tk.OptionMenu(form, axis, "horizontal", "vertical").grid(row=7, column=1, sticky="e")
        form.grid_columnconfigure(0, weight=1)
        self.label(dialog, "Cada acción guarda su propia tira. Al elegir la acción, el launcher reproduce sus frames en bucle.",
                   fg=MUTED, wraplength=400, justify="left").pack(anchor="w", padx=18, pady=12)
        footer = tk.Frame(dialog, bg=BG)
        footer.pack(fill="x", padx=16, pady=(0, 14))

        def save_strip():
            try:
                values = {key: int(variable.get()) for key, variable in variables.items()}
                x, y = values["X inicial"], values["Y inicial"]
                fw, fh = values["Ancho del frame"], values["Alto del frame"]
                count, spacing, duration = values["Cantidad de frames"], values["Separación"], values["Duración (ms)"]
                if min(x, y, spacing) < 0 or min(fw, fh, count, duration) < 1 or count > 256:
                    raise ValueError
                if x + fw > sheet_width or y + fh > sheet_height:
                    raise ValueError("El primer frame queda fuera de los límites de la hoja.")
                if axis.get() == "horizontal" and x + count*fw + (count-1)*spacing > sheet_width:
                    raise ValueError("La tira supera el ancho de la hoja.")
                if axis.get() == "vertical" and y + count*fh + (count-1)*spacing > sheet_height:
                    raise ValueError("La tira supera el alto de la hoja.")
            except ValueError as exc:
                messagebox.showerror("Valores no válidos", str(exc) or "Revisa coordenadas, dimensiones y cantidad de frames.", parent=dialog)
                return
            profile = self.profiles.setdefault(win.game_name, {})
            profile.setdefault("sprite_actions", {})[win.action_var.get()] = asset["relative"].as_posix()
            profile.setdefault("sprite_action_strips", {})[win.action_var.get()] = {
                "x": x, "y": y, "width": fw, "height": fh, "count": count,
                "spacing": spacing, "duration": duration, "axis": axis.get()
            }
            self.save_config()
            dialog.destroy()
            self._update_action_assignment_status(win)
            self._select_workspace_asset(win)

        self.button(footer, "Cancelar", dialog.destroy).pack(side="right", padx=(8, 0))
        self.button(footer, "Guardar y reproducir", save_strip, primary=True).pack(side="right")
        self._update_action_assignment_status(win)
        self.save_config()

    def _schedule_sprite_frame(self, win):
        if not win.animation_playing or len(win.preview_frames) < 2:
            return
        delay = win.frame_durations[win.frame_index] if win.frame_index < len(win.frame_durations) else 100
        win.animation_after = win.after(delay, lambda: self._advance_sprite_frame(win))

    def _advance_sprite_frame(self, win):
        win.animation_after = None
        if not win.animation_playing or not win.preview_frames:
            return
        win.frame_index = (win.frame_index + 1) % len(win.preview_frames)
        win.preview_image = win.preview_frames[win.frame_index]
        win.dimensions_var.set(f"{win.original_size[0]} × {win.original_size[1]} px   ·   Frame {win.frame_index+1}/{len(win.preview_frames)}   ·   {win.source_format}")
        self._draw_sprite_preview(win)
        self._schedule_sprite_frame(win)

    def _toggle_sprite_animation(self, win):
        if len(win.preview_frames) < 2:
            return
        win.animation_playing = not win.animation_playing
        win.animation_button.configure(text="Ⅱ Pausar" if win.animation_playing else "▶ Reproducir")
        if win.animation_playing:
            self._schedule_sprite_frame(win)
        elif win.animation_after is not None:
            win.after_cancel(win.animation_after); win.animation_after = None

    def _edit_sprite_palette(self, win):
        if not win.preview_frames:
            messagebox.showinfo("Selecciona un sprite", "Selecciona primero una imagen para editar su paleta.", parent=win)
            return
        colors = set()
        for frame in win.base_preview_frames:
            palette = frame.convert("RGB").getcolors(maxcolors=257)
            if palette is None:
                messagebox.showinfo("Paleta extensa", "Esta imagen tiene más de 256 colores. Usa LibreSprite para editar su paleta.", parent=win)
                return
            colors.update(color for _count, color in palette)
            if len(colors) > 256:
                messagebox.showinfo("Paleta extensa", "Esta animación supera 256 colores. Usa LibreSprite para editarla.", parent=win)
                return
        win.palette_edits = getattr(win, "palette_edits", {})
        dialog = tk.Toplevel(win); dialog.title("Editar paleta"); dialog.geometry("390x500"); dialog.configure(bg=BG); dialog.transient(win)
        self.label(dialog, "PALETA DEL SPRITE", fg=CYAN, font=(self.font_family.get(), 10, "bold")).pack(anchor="w", padx=16, pady=(16, 8))
        box = tk.Listbox(dialog, bg="#09172a", fg=WHITE, selectbackground="#15516d", relief="flat", font=("Consolas", 10))
        box.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        color_values = sorted(colors)
        for color in color_values:
            rgb_hex = "#%02X%02X%02X" % color
            replacement = win.palette_edits.get(color, color)
            box.insert("end", f"■  {rgb_hex}  →  #{replacement[0]:02X}{replacement[1]:02X}{replacement[2]:02X}")
            box.itemconfigure("end", foreground="#%02X%02X%02X" % replacement)
        def choose_color():
            selection = box.curselection()
            if not selection:
                return
            original = color_values[selection[0]]
            initial = win.palette_edits.get(original, original)
            chosen = colorchooser.askcolor(color="#%02X%02X%02X" % initial, parent=dialog, title="Nuevo color")
            if not chosen or not chosen[0]:
                return
            new_color = tuple(round(component) for component in chosen[0])
            win.palette_edits[original] = new_color
            box.delete(selection[0]); box.insert(selection[0], f"■  #{original[0]:02X}{original[1]:02X}{original[2]:02X}  →  #{new_color[0]:02X}{new_color[1]:02X}{new_color[2]:02X}")
            box.itemconfigure(selection[0], foreground="#%02X%02X%02X" % new_color)
            win.preview_frames = [self._recolor_frame(frame, win.palette_edits) for frame in win.base_preview_frames]
            win.preview_image = win.preview_frames[win.frame_index]
            self._draw_sprite_preview(win)
        self.button(dialog, "Cambiar color seleccionado…", choose_color, primary=True).pack(anchor="w", padx=16, pady=(0, 14))

    @staticmethod
    def _recolor_frame(frame, palette_edits):
        if not palette_edits:
            return frame.copy()
        updated = frame.copy()
        pixels = []
        for red, green, blue, alpha in updated.getdata():
            replacement = palette_edits.get((red, green, blue))
            pixels.append((*replacement, alpha) if replacement else (red, green, blue, alpha))
        updated.putdata(pixels)
        return updated

    def _draw_sprite_preview(self, win):
        canvas = win.preview_canvas
        canvas.delete("all")
        image = getattr(win, "preview_image", None)
        if image is None:
            if hasattr(win, "empty_message"):
                canvas.create_text(30, 30, anchor="nw", width=max(250, canvas.winfo_width()-60),
                    text=win.empty_message, fill=MUTED, font=(self.font_family.get(), 11))
            return
        cw, ch = max(1, canvas.winfo_width()-50), max(1, canvas.winfo_height()-50)
        iw, ih = image.size
        try:
            target_w = max(1, min(8192, int(win.width_var.get())))
            target_h = max(1, min(8192, int(win.height_var.get())))
        except (ValueError, tk.TclError):
            target_w, target_h = iw, ih
        scale = min(cw/target_w, ch/target_h, 8)
        scale = max(scale, min(1, 16/max(target_w, target_h)))
        dw, dh = max(1, round(target_w*scale)), max(1, round(target_h*scale))
        preview = image.resize((dw, dh), Image.Resampling.NEAREST)
        win.preview_photo = ImageTk.PhotoImage(preview)
        x, y = (canvas.winfo_width()-dw)//2, (canvas.winfo_height()-dh)//2
        tile = max(8, min(16, round(scale*2)))
        for row, yy in enumerate(range(y, y+dh, tile)):
            for col, xx in enumerate(range(x, x+dw, tile)):
                if (row+col) % 2 == 0:
                    canvas.create_rectangle(xx, yy, min(xx+tile, x+dw), min(yy+tile, y+dh),
                                            fill="#17263a", outline="")
        canvas.create_image(x, y, anchor="nw", image=win.preview_photo)
        canvas.create_rectangle(x-1, y-1, x+dw, y+dh, outline=CYAN, width=2)
        if scale >= 4 and target_w * target_h <= 16000:
            step = max(1, round(scale))
            for gx in range(x, x+dw+1, step):
                canvas.create_line(gx, y, gx, y+dh, fill="#34465c")
            for gy in range(y, y+dh+1, step):
                canvas.create_line(x, gy, x+dw, gy, fill="#34465c")

    def open_native_sprite_editor(self, workspace):
        """Open a small, native pixel editor for the selected exported sprite."""
        if not workspace.selected_asset or not workspace.preview_frames:
            messagebox.showinfo("Selecciona un sprite", "Elige una imagen de la biblioteca antes de editar.", parent=workspace)
            return
        win = tk.Toplevel(workspace)
        win.title(f"Editor de píxeles · {workspace.selected_asset['path'].name}")
        win.geometry("1100x760")
        win.minsize(820, 560)
        win.configure(bg=BG)
        win.transient(workspace)
        win.workspace = workspace
        source_frames = workspace.base_preview_frames or workspace.preview_frames
        win.frames = [frame.copy() for frame in source_frames]
        win.durations = list(getattr(workspace, "base_frame_durations", workspace.frame_durations))
        win.frame_index = min(max(0, workspace.frame_index), max(0, len(win.frames)-1))
        win.source_asset = workspace.selected_asset
        win.undo_stack = []
        win.tool = tk.StringVar(value="Pincel")
        win.color = "#ff245b"
        win.zoom = tk.IntVar(value=4)
        win.selection_box = None
        win.selection_mode = None
        win.selection_anchor = None
        win.selection_last_point = None
        win.action_var = tk.StringVar(value=workspace.action_var.get())
        win.keyframes_by_action = {win.action_var.get(): []}
        win.keyframes = win.keyframes_by_action[win.action_var.get()]
        win.current_action = win.action_var.get()
        win.preview_playing = False
        win.preview_after = None
        win.preview_index = 0
        win.selection_info = tk.StringVar(value="Arrastra sobre la hoja para seleccionar un sprite o una tira.")
        win.status = tk.StringVar(value="Pincel · clic o arrastre para editar píxeles. El original permanece intacto.")
        win.photo = None
        win.sprite_image_item = None
        win.sprite_bounds_item = None
        win.render_after = None
        win._stroke_start = None
        win._stroke_snapshot = None

        top = tk.Frame(win, bg="#081626", padx=12, pady=9)
        top.pack(fill="x")
        self.label(top, "EDITOR DE PÍXELES", bg="#081626", fg=CYAN,
                   font=(self.font_family.get(), 10, "bold")).pack(side="left", padx=(0, 15))
        for tool in ("Pincel", "Borrador", "Relleno", "Cuentagotas", "Selección ▭"):
            self.button(top, tool, lambda selected=tool: self._native_select_tool(win, selected),
                        primary=(tool == "Pincel")).pack(side="left", padx=3)
        self.button(top, "Color…", lambda: self._native_pick_color(win)).pack(side="left", padx=(8, 3))
        win.color_chip = tk.Label(top, text="   ", bg=win.color, relief="solid", bd=1)
        win.color_chip.pack(side="left", padx=(2, 12), ipady=4)
        self.button(top, "↶ Deshacer", lambda: self._native_undo(win)).pack(side="left", padx=3)
        self.button(top, "＋ Importar hoja personalizada…", lambda: self._native_import_custom_sprites(win)).pack(side="left", padx=3)
        self.button(top, "Guardar animación en mod…", lambda: self._native_save_to_mod(win), primary=True).pack(side="right", padx=(6, 0))
        self.button(top, "Guardar copia…", lambda: self._native_save_as(win)).pack(side="right")

        bar = tk.Frame(win, bg=PANEL, padx=12, pady=7)
        bar.pack(fill="x")
        self.label(bar, "Fotograma", bg=PANEL, fg=WHITE).pack(side="left")
        win.frame_var = tk.IntVar(value=win.frame_index + 1)
        win.frame_spin = tk.Spinbox(bar, from_=1, to=len(win.frames), width=5, textvariable=win.frame_var,
                                    command=lambda: self._native_change_frame(win), bg="#09172a", fg=WHITE,
                                    buttonbackground="#1a304b", relief="flat", wrap=True)
        win.frame_spin.pack(side="left", padx=(6, 16))
        win.frame_label = tk.StringVar(value=f"/ {len(win.frames)}")
        self.label(bar, "", textvariable=win.frame_label, bg=PANEL, fg=MUTED).pack(side="left")
        self.label(bar, "Zoom", bg=PANEL, fg=WHITE).pack(side="right", padx=(12, 5))
        tk.Scale(bar, from_=1, to=16, orient="horizontal", variable=win.zoom, showvalue=True, length=150,
                 bg=PANEL, fg=WHITE, troughcolor="#263b57", highlightthickness=0,
                 command=lambda _value: self._native_draw(win)).pack(side="right")

        win.palette_bar = tk.Frame(win, bg=BG, padx=12)
        win.palette_bar.pack(fill="x", pady=(3, 0))
        self.label(win.palette_bar, "Paleta", bg=BG, fg=MUTED, font=(self.font_family.get(), 8)).pack(side="left", padx=(0, 8))
        self._native_update_palette(win)

        stage = tk.Frame(win, bg=BG)
        stage.pack(fill="both", expand=True, padx=12, pady=(10, 6))
        canvas_frame = tk.Frame(stage, bg=BG)
        canvas_frame.pack(side="left", fill="both", expand=True)
        win.canvas = tk.Canvas(canvas_frame, bg="#09111e", highlightthickness=1, highlightbackground="#344b66",
                               cursor="crosshair", xscrollincrement=8, yscrollincrement=8)
        hscroll = tk.Scrollbar(canvas_frame, orient="horizontal",
                               command=lambda *args: self._native_scroll(win, "x", *args))
        vscroll = tk.Scrollbar(canvas_frame, orient="vertical",
                               command=lambda *args: self._native_scroll(win, "y", *args))
        win.canvas.configure(xscrollcommand=hscroll.set, yscrollcommand=vscroll.set)
        win.canvas.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")
        hscroll.grid(row=1, column=0, sticky="ew")
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)
        inspector = tk.Frame(stage, bg=PANEL, width=250, highlightbackground="#284565", highlightthickness=1)
        inspector.pack(side="right", fill="y", padx=(10, 0))
        inspector.pack_propagate(False)
        self.label(inspector, "PREVISUALIZACIÓN · HUD", bg=PANEL, fg=CYAN,
                   font=(self.font_family.get(), 9, "bold")).pack(anchor="w", padx=12, pady=(12, 8))
        win.hud_canvas = tk.Canvas(inspector, width=220, height=190, bg="#09111e",
                                   highlightthickness=1, highlightbackground="#344b66")
        win.hud_canvas.pack(fill="x", padx=12)
        self.label(inspector, "SELECCIÓN", bg=PANEL, fg=MUTED,
                   font=(self.font_family.get(), 8, "bold")).pack(anchor="w", padx=12, pady=(14, 3))
        self.label(inspector, "", textvariable=win.selection_info, bg=PANEL, fg=WHITE,
                   wraplength=210, justify="left", font=(self.font_family.get(), 8)).pack(anchor="w", padx=12)
        self.label(inspector, "ANIMACIÓN", bg=PANEL, fg=CYAN,
                   font=(self.font_family.get(), 9, "bold")).pack(anchor="w", padx=12, pady=(16, 4))
        tk.OptionMenu(inspector, win.action_var, "Idle", "Walk", "Running", "Spin", "Jump", "Roll", "Spin Dash", "Peel Out").pack(fill="x", padx=12)
        win.add_keyframe_button = self.button(inspector, "＋ Añadir fotograma clave",
                    lambda: self._native_add_keyframe(win), primary=True)
        win.add_keyframe_button.pack(fill="x", padx=12, pady=(8, 6))
        win.add_keyframe_button.configure(state="disabled")
        win.keyframe_list = tk.Listbox(inspector, height=7, bg="#09172a", fg=WHITE,
                    selectbackground="#18556d", relief="flat", highlightthickness=1,
                    highlightbackground="#344b66", activestyle="none")
        win.keyframe_list.pack(fill="x", padx=12, pady=(0, 6))
        win.keyframe_list.bind("<<ListboxSelect>>", lambda _e: self._native_select_keyframe(win))
        win.action_var.trace_add("write", lambda *_args: self._native_switch_action(win))
        controls = tk.Frame(inspector, bg=PANEL)
        controls.pack(fill="x", padx=12)
        self.button(controls, "▶ Reproducir", lambda: self._native_play_sequence(win)).pack(side="left", fill="x", expand=True)
        self.button(controls, "Ⅱ", lambda: self._native_stop_sequence(win)).pack(side="left", padx=(5, 0))
        self.button(inspector, "− Eliminar fotograma", lambda: self._native_remove_keyframe(win)).pack(fill="x", padx=12, pady=(6, 4))
        self.label(inspector, "Selecciona cada pose en la hoja y añádela a la secuencia.",
                   bg=PANEL, fg=MUTED, wraplength=210, justify="left",
                   font=(self.font_family.get(), 8)).pack(anchor="w", padx=12, pady=(4, 10))
        win.canvas.bind("<Configure>", lambda _event: self._native_draw(win))
        win.canvas.bind("<ButtonPress-1>", lambda event: self._native_pointer_down(win, event))
        win.canvas.bind("<B1-Motion>", lambda event: self._native_pointer_move(win, event))
        win.canvas.bind("<ButtonRelease-1>", lambda event: self._native_pointer_up(win, event))
        win.canvas.bind("<ButtonPress-2>", lambda event: win.canvas.scan_mark(event.x, event.y))
        win.canvas.bind("<B2-Motion>", lambda event: self._native_pan(win, event))
        self.label(win, "", textvariable=win.status, fg=MUTED, font=(self.font_family.get(), 8),
                   anchor="w").pack(fill="x", padx=14, pady=(0, 10))
        win.frame_spin.bind("<Return>", lambda _event: self._native_change_frame(win))
        win.frame_spin.bind("<FocusOut>", lambda _event: self._native_change_frame(win))
        self._native_draw(win)
        self._native_draw_hud(win)

    def _native_draw(self, win):
        if not win.winfo_exists():
            return
        canvas = win.canvas
        canvas.delete("selection")
        frame = win.frames[win.frame_index]
        width, height = frame.size
        scale = max(1, int(win.zoom.get()))
        draw_w, draw_h = width * scale, height * scale
        x0 = max(8, (canvas.winfo_width()-draw_w)//2)
        y0 = max(8, (canvas.winfo_height()-draw_h)//2)
        win.scale, win.origin = scale, (x0, y0)
        scroll_w = max(canvas.winfo_width(), x0+draw_w+16)
        scroll_h = max(canvas.winfo_height(), y0+draw_h+16)
        canvas.configure(scrollregion=(0, 0, scroll_w, scroll_h))

        # Render only the visible crop. Creating thousands of Tk rectangles for
        # the checkerboard (and regenerating the full 16x zoom) stalled every
        # brush movement. Pillow now composites one viewport-sized bitmap.
        view_left, view_top = canvas.canvasx(0), canvas.canvasy(0)
        view_right = view_left + max(1, canvas.winfo_width())
        view_bottom = view_top + max(1, canvas.winfo_height())
        left = max(x0, int(view_left))
        top = max(y0, int(view_top))
        right = min(x0+draw_w, int(view_right)+1)
        bottom = min(y0+draw_h, int(view_bottom)+1)
        canvas.delete("grid")
        if right <= left or bottom <= top:
            self._native_draw_hud(win)
            return
        px0, py0 = max(0, (left-x0)//scale), max(0, (top-y0)//scale)
        px1 = min(width, (right-x0+scale-1)//scale)
        py1 = min(height, (bottom-y0+scale-1)//scale)
        if px1 <= px0 or py1 <= py0:
            return
        crop = frame.crop((px0, py0, px1, py1))
        render_w, render_h = crop.width*scale, crop.height*scale
        # Checker texture is a single cached PIL tile, not thousands of Tk items.
        tile = getattr(win, "checker_tile", None)
        if tile is None:
            tile = Image.new("RGBA", (32, 32), "#101c2c")
            tile_draw = ImageDraw.Draw(tile)
            tile_draw.rectangle((0, 0, 15, 15), fill="#1a2a3e")
            tile_draw.rectangle((16, 16, 31, 31), fill="#1a2a3e")
            win.checker_tile = tile
        background = Image.new("RGBA", (render_w+32, render_h+32), "#101c2c")
        for yy in range(-32, render_h+32, 32):
            for xx in range(-32, render_w+32, 32):
                background.paste(tile, (xx, yy))
        phase_x = (x0 + px0*scale) % 32
        phase_y = (y0 + py0*scale) % 32
        background = background.crop((phase_x, phase_y, phase_x+render_w, phase_y+render_h))
        preview = crop.resize((render_w, render_h), Image.Resampling.NEAREST)
        background.alpha_composite(preview)
        win.photo = ImageTk.PhotoImage(background)
        image_x, image_y = x0+px0*scale, y0+py0*scale
        if win.sprite_image_item is None:
            win.sprite_image_item = canvas.create_image(image_x, image_y, image=win.photo, anchor="nw", tags="sprite-image")
        else:
            canvas.coords(win.sprite_image_item, image_x, image_y)
            canvas.itemconfigure(win.sprite_image_item, image=win.photo)
        if scale >= 8 and width*height <= 262144:
            for px in range(px0, px1+1):
                xx = x0 + px*scale
                canvas.create_line(xx, image_y, xx, image_y+render_h, fill="#314157", tags="grid")
            for py in range(py0, py1+1):
                yy = y0 + py*scale
                canvas.create_line(image_x, yy, image_x+render_w, yy, fill="#314157", tags="grid")
        if win.sprite_bounds_item is None:
            win.sprite_bounds_item = canvas.create_rectangle(x0, y0, x0+draw_w, y0+draw_h,
                                                            outline=CYAN, width=2, tags="sprite-bounds")
        else:
            canvas.coords(win.sprite_bounds_item, x0, y0, x0+draw_w, y0+draw_h)
        if win.selection_box:
            sx, sy, ex, ey = win.selection_box
            ax, ay = x0+sx*scale, y0+sy*scale
            bx, by = x0+ex*scale, y0+ey*scale
            canvas.create_rectangle(ax, ay, bx, by, outline=YELLOW, width=2, dash=(5, 3), tags="selection")
            handle = max(4, min(7, scale//2))
            for hx, hy in ((ax, ay), (bx, ay), (ax, by), (bx, by)):
                canvas.create_rectangle(hx-handle, hy-handle, hx+handle, hy+handle,
                                        fill=YELLOW, outline="#101827", tags="selection")
        self._native_draw_hud(win)

    @staticmethod
    def _native_preview_crop(image):
        """Use the classic hot-pink sheet key as transparency in preview/export crops."""
        rgba = image.convert("RGBA")
        pixels = rgba.load()
        for y in range(rgba.height):
            for x in range(rgba.width):
                red, green, blue, alpha = pixels[x, y]
                if red >= 245 and green <= 12 and blue >= 245:
                    pixels[x, y] = (red, green, blue, 0)
        return rgba

    def _native_draw_hud(self, win):
        canvas = getattr(win, "hud_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        canvas.delete("all")
        if getattr(win, "add_keyframe_button", None) and win.add_keyframe_button.winfo_exists():
            win.add_keyframe_button.configure(state=("normal" if win.selection_box else "disabled"))
        crop = None
        if win.preview_playing and win.keyframes:
            crop = self._native_preview_crop(win.keyframes[win.preview_index % len(win.keyframes)]["image"])
            win.selection_info.set(f"Reproduciendo {win.action_var.get()} · {len(win.keyframes)} fotogramas")
        elif win.selection_box:
            x, y, right, bottom = map(int, win.selection_box)
            crop = self._native_preview_crop(win.frames[win.frame_index].crop((x, y, right, bottom)))
            win.selection_info.set(f"X {x} · Y {y} · {right-x} × {bottom-y} px")
        else:
            canvas.create_text(canvas.winfo_width()//2, canvas.winfo_height()//2,
                text="Selecciona una región\nde la hoja", fill=MUTED, justify="center",
                font=(self.font_family.get(), 9))
            win.selection_info.set("Arrastra para dibujar el rectángulo.")
            return
        if crop and crop.width and crop.height:
            max_w, max_h = max(1, canvas.winfo_width()-24), max(1, canvas.winfo_height()-44)
            scale = min(max_w/crop.width, max_h/crop.height, 12)
            preview = crop.resize((max(1, round(crop.width*scale)), max(1, round(crop.height*scale))), Image.Resampling.NEAREST)
            win.hud_photo = ImageTk.PhotoImage(preview)
            canvas.create_image(canvas.winfo_width()//2, canvas.winfo_height()//2-8,
                                image=win.hud_photo, anchor="center")
            canvas.create_text(canvas.winfo_width()//2, canvas.winfo_height()-12,
                text=f"{crop.width} × {crop.height} px", fill=WHITE,
                font=(self.font_family.get(), 8))

    def _native_schedule_draw(self, win):
        if win.render_after is None:
            win.render_after = win.after(16, lambda: self._native_draw_pending(win))

    def _native_draw_pending(self, win):
        win.render_after = None
        if win.winfo_exists():
            self._native_draw(win)

    def _native_scroll(self, win, axis, *args):
        (win.canvas.xview if axis == "x" else win.canvas.yview)(*args)
        self._native_schedule_draw(win)

    def _native_pan(self, win, event):
        win.canvas.scan_dragto(event.x, event.y, gain=1)
        self._native_schedule_draw(win)

    def _native_pixel_at(self, win, event):
        x0, y0 = win.origin
        x = int((win.canvas.canvasx(event.x)-x0)//win.scale)
        y = int((win.canvas.canvasy(event.y)-y0)//win.scale)
        frame = win.frames[win.frame_index]
        return (x, y) if 0 <= x < frame.width and 0 <= y < frame.height else None

    def _native_pointer_down(self, win, event):
        point = self._native_pixel_at(win, event)
        if win.tool.get() == "Selección ▭":
            if point is None:
                if not win.selection_box or not self._native_selection_handle_near(win, event):
                    return
                frame = win.frames[win.frame_index]
                raw_x = int((win.canvas.canvasx(event.x)-win.origin[0])//win.scale)
                raw_y = int((win.canvas.canvasy(event.y)-win.origin[1])//win.scale)
                point = (max(0, min(frame.width-1, raw_x)), max(0, min(frame.height-1, raw_y)))
            self._native_begin_selection(win, event, point)
            self._native_draw(win)
            return
        if point is None:
            return
        frame = win.frames[win.frame_index]
        if win.tool.get() == "Cuentagotas":
            color = frame.getpixel(point)
            win.color = "#%02x%02x%02x" % color[:3]
            win.color_chip.configure(bg=win.color)
            win.status.set(f"Color seleccionado: {win.color}")
            return
        win.undo_stack.append(frame.copy())
        if len(win.undo_stack) > 30:
            del win.undo_stack[0]
        win._stroke_snapshot = frame.copy()
        x, y = point
        tool = win.tool.get()
        if tool == "Relleno":
            rgba = tuple(bytes.fromhex(win.color.lstrip("#"))) + (255,)
            ImageDraw.floodfill(frame, (x, y), rgba, thresh=0)
            win._stroke_start = None
            self._native_draw(win)
            return
        self._native_paint(win, x, y, x, y)
        win._stroke_start = point
        self._native_draw(win)

    def _native_pointer_move(self, win, event):
        if win.selection_mode:
            self._native_update_selection(win, event)
            self._native_schedule_draw(win)
            return
        point = self._native_pixel_at(win, event)
        if point is None or win._stroke_start is None:
            return
        self._native_paint(win, *win._stroke_start, *point)
        win._stroke_start = point
        self._native_schedule_draw(win)

    def _native_pointer_up(self, win, _event):
        if win.selection_mode:
            win.selection_mode = None
            win.selection_anchor = None
            win.selection_last_point = None
            self._native_draw(win)
            return
        if win._stroke_snapshot is not None:
            win._stroke_snapshot = None
            frame = win.frames[win.frame_index]
            win.status.set(f"{win.tool.get()} · Fotograma {win.frame_index+1}/{len(win.frames)} · {frame.width}×{frame.height}px")
        win._stroke_start = None

    def _native_begin_selection(self, win, event, point):
        frame = win.frames[win.frame_index]
        px, py = point
        box = win.selection_box
        if box:
            x0, y0, x1, y1 = box
            screen_x, screen_y = win.canvas.canvasx(event.x), win.canvas.canvasy(event.y)
            origin_x, origin_y = win.origin
            corners = {
                "nw": (origin_x+x0*win.scale, origin_y+y0*win.scale, (x1, y1)),
                "ne": (origin_x+x1*win.scale, origin_y+y0*win.scale, (x0, y1)),
                "sw": (origin_x+x0*win.scale, origin_y+y1*win.scale, (x1, y0)),
                "se": (origin_x+x1*win.scale, origin_y+y1*win.scale, (x0, y0)),
            }
            for name, (hx, hy, anchor) in corners.items():
                if abs(screen_x-hx) <= 10 and abs(screen_y-hy) <= 10:
                    win.selection_mode = "resize"
                    win.selection_anchor = anchor
                    win.selection_corner = name
                    win.selection_last_point = point
                    return
            if x0 <= px < x1 and y0 <= py < y1:
                win.selection_mode = "move"
                win.selection_last_point = point
                return
        win.selection_mode = "new"
        win.selection_start = point
        win.selection_box = (px, py, px+1, py+1)

    @staticmethod
    def _native_selection_handle_near(win, event):
        if not win.selection_box:
            return False
        x0, y0, x1, y1 = win.selection_box
        ox, oy = win.origin
        px, py = win.canvas.canvasx(event.x), win.canvas.canvasy(event.y)
        return any(abs(px-(ox+x*win.scale)) <= 10 and abs(py-(oy+y*win.scale)) <= 10
                   for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)))

    def _native_update_selection(self, win, event):
        frame = win.frames[win.frame_index]
        raw_x = int((win.canvas.canvasx(event.x)-win.origin[0])//win.scale)
        raw_y = int((win.canvas.canvasy(event.y)-win.origin[1])//win.scale)
        px = max(0, min(frame.width-1, raw_x))
        py = max(0, min(frame.height-1, raw_y))
        if win.selection_mode == "new":
            sx, sy = win.selection_start
            win.selection_box = (min(sx, px), min(sy, py), max(sx, px)+1, max(sy, py)+1)
        elif win.selection_mode == "move":
            x0, y0, x1, y1 = win.selection_box
            last_x, last_y = win.selection_last_point
            dx, dy = raw_x-last_x, raw_y-last_y
            dx = max(-x0, min(frame.width-x1, dx))
            dy = max(-y0, min(frame.height-y1, dy))
            win.selection_box = (x0+dx, y0+dy, x1+dx, y1+dy)
            win.selection_last_point = (raw_x, raw_y)
        elif win.selection_mode == "resize":
            ax, ay = win.selection_anchor
            corner = win.selection_corner
            left, right = (px, ax) if corner in ("nw", "sw") else (ax, px+1)
            top, bottom = (py, ay) if corner in ("nw", "ne") else (ay, py+1)
            left, right = sorted((left, right))
            top, bottom = sorted((top, bottom))
            left = max(0, min(frame.width-1, left)); right = max(left+1, min(frame.width, right))
            top = max(0, min(frame.height-1, top)); bottom = max(top+1, min(frame.height, bottom))
            win.selection_box = (left, top, right, bottom)

    def _native_switch_action(self, win):
        action = win.action_var.get()
        previous = getattr(win, "current_action", action)
        win.keyframes_by_action[previous] = win.keyframes
        self._native_stop_sequence(win)
        win.current_action = action
        win.keyframes = win.keyframes_by_action.setdefault(action, [])
        win.keyframe_list.delete(0, "end")
        for index, entry in enumerate(win.keyframes, 1):
            x, y, width, height = entry["rect"]
            win.keyframe_list.insert("end", f"{index:02d}  {x},{y} · {width}×{height}")
        win.preview_index = 0
        win.status.set(f"Animación {action}: {len(win.keyframes)} fotogramas clave.")
        self._native_draw_hud(win)

    def _native_add_keyframe(self, win):
        if not win.selection_box:
            return
        x, y, right, bottom = map(int, win.selection_box)
        crop = self._native_preview_crop(win.frames[win.frame_index].crop((x, y, right, bottom)))
        if crop.width < 1 or crop.height < 1:
            return
        win.keyframes.append({"image": crop, "rect": [x, y, crop.width, crop.height],
                              "source_frame": win.frame_index, "duration": 100})
        index = len(win.keyframes)
        win.keyframe_list.insert("end", f"{index:02d}  {x},{y} · {crop.width}×{crop.height}")
        win.keyframe_list.selection_clear(0, "end")
        win.keyframe_list.selection_set(index-1)
        win.keyframe_list.activate(index-1)
        win.status.set(f"Fotograma clave {index} añadido a {win.action_var.get()}.")
        self._native_draw_hud(win)

    def _native_select_keyframe(self, win):
        selection = win.keyframe_list.curselection()
        if selection:
            self._native_stop_sequence(win)
            win.preview_index = selection[0]
            self._native_draw_hud(win)

    def _native_play_sequence(self, win):
        if not win.keyframes:
            win.status.set("Selecciona una región y pulsa ＋ para añadir el primer fotograma.")
            return
        self._native_stop_sequence(win)
        win.preview_playing = True
        win.preview_index = 0
        self._native_preview_tick(win)

    def _native_preview_tick(self, win):
        if not win.winfo_exists() or not win.preview_playing or not win.keyframes:
            return
        self._native_draw_hud(win)
        delay = max(20, int(win.keyframes[win.preview_index].get("duration", 100)))
        win.preview_index = (win.preview_index + 1) % len(win.keyframes)
        win.preview_after = win.after(delay, lambda: self._native_preview_tick(win))

    def _native_stop_sequence(self, win):
        win.preview_playing = False
        if win.preview_after:
            try:
                win.after_cancel(win.preview_after)
            except tk.TclError:
                pass
            win.preview_after = None

    def _native_remove_keyframe(self, win):
        selected = win.keyframe_list.curselection()
        if not selected:
            return
        index = selected[0]
        win.keyframes.pop(index)
        win.keyframe_list.delete(index)
        win.keyframe_list.delete(0, "end")
        for i, entry in enumerate(win.keyframes, 1):
            x, y, width, height = entry["rect"]
            win.keyframe_list.insert("end", f"{i:02d}  {x},{y} · {width}×{height}")
        self._native_draw_hud(win)

    def _native_assign_selection(self, win):
        if not win.selection_box:
            messagebox.showinfo("Selecciona un sprite", "Activa Selección ▭ y dibuja un rectángulo alrededor del sprite o la tira.", parent=win)
            return
        x, y, right, bottom = win.selection_box
        try:
            count = max(1, int(win.action_frame_count.get()))
        except (ValueError, tk.TclError):
            messagebox.showerror("Cantidad no válida", "La cantidad de frames debe ser un número entre 1 y 256.", parent=win)
            return
        width, height = right-x, bottom-y
        if width < 1 or height < 1 or width % count:
            messagebox.showerror("Tira no válida", "El ancho seleccionado debe dividirse exactamente entre la cantidad de frames.", parent=win)
            return
        action = win.action_var.get()
        profile = self.profiles.setdefault(win.workspace.game_name, {})
        profile.setdefault("sprite_actions", {})[action] = win.source_asset["relative"].as_posix()
        profile.setdefault("sprite_action_strips", {})[action] = {
            "x": x, "y": y, "width": width//count, "height": height,
            "count": count, "spacing": 0, "duration": 100, "axis": "horizontal"
        }
        self.save_config()
        workspace = win.workspace
        if workspace.category.get() != "Players":
            self._populate_sprite_assets(workspace, "Players")
        if workspace.action_var.get() == action:
            self._select_assigned_action(workspace)
        else:
            workspace.action_var.set(action)
        win.status.set(f"Selección asignada a {action} · {count} frame(s)")
        messagebox.showinfo("Movimiento asignado", f"La selección se asignó a {action} con {count} frame(s).", parent=win)

    @staticmethod
    def _native_select_tool(win, tool):
        win.tool.set(tool)
        hints = {
            "Pincel": "Pincel · clic o arrastre para pintar.",
            "Borrador": "Borrador · arrastra para borrar píxeles.",
            "Relleno": "Relleno · clic en un área de color contigua.",
            "Cuentagotas": "Cuentagotas · clic sobre un color para tomarlo.",
            "Selección ▭": "Selección rectangular · arrastra para crearla; mueve el interior o arrastra una esquina para ajustarla."
        }
        win.status.set(hints.get(tool, tool))
        win.canvas.configure(cursor="crosshair" if tool == "Selección ▭" else "arrow")

    @staticmethod
    def _native_paint(win, x0, y0, x1, y1):
        frame = win.frames[win.frame_index]
        draw = ImageDraw.Draw(frame, "RGBA")
        color = (0, 0, 0, 0) if win.tool.get() == "Borrador" else tuple(bytes.fromhex(win.color.lstrip("#"))) + (255,)
        draw.line((x0, y0, x1, y1), fill=color, width=1)
        draw.point((x1, y1), fill=color)

    def _native_undo(self, win):
        if not win.undo_stack:
            win.status.set("No hay cambios para deshacer.")
            return
        win.frames[win.frame_index] = win.undo_stack.pop()
        win.status.set("Último cambio deshecho.")
        self._native_draw(win)

    def _native_pick_color(self, win):
        chosen = colorchooser.askcolor(color=win.color, parent=win, title="Color del pincel")
        if chosen and chosen[1]:
            win.color = chosen[1]
            win.color_chip.configure(bg=win.color)

    def _native_update_palette(self, win):
        for child in win.palette_bar.winfo_children()[1:]:
            child.destroy()
        reduced = win.frames[win.frame_index].convert("RGB").quantize(colors=24, dither=Image.Dither.NONE).convert("RGB")
        colors = reduced.getcolors(maxcolors=32) or []
        colors.sort(key=lambda item: item[0], reverse=True)
        for _count, rgb in colors[:24]:
            color = "#%02x%02x%02x" % rgb
            chip = tk.Button(win.palette_bar, bg=color, activebackground=color, width=2, relief="flat",
                             command=lambda value=color: self._native_set_color(win, value))
            chip.pack(side="left", padx=2, pady=2)

    @staticmethod
    def _native_set_color(win, color):
        win.color = color
        win.color_chip.configure(bg=color)

    def _native_import_custom_sprites(self, win):
        source = filedialog.askopenfilename(parent=win, title="Importar hoja de sprites personalizada",
            filetypes=[("Hojas de sprites", "*.png *.gif *.bmp *.tif *.tiff *.webp"), ("Todos los archivos", "*.*")])
        if not source:
            return
        if win.keyframes and not messagebox.askyesno("Reemplazar hoja", "La secuencia actual contiene fotogramas clave. ¿Importar la nueva hoja y borrar esas secuencias para evitar mezclar sprites?", parent=win):
            return
        try:
            imported = []
            durations = []
            with Image.open(source) as image:
                for frame in ImageSequence.Iterator(image):
                    rgba = frame.convert("RGBA")
                    # Many community sprite sheets use hot pink as the transparent key.
                    pixels = rgba.load()
                    for y in range(rgba.height):
                        for x in range(rgba.width):
                            red, green, blue, alpha = pixels[x, y]
                            if red >= 245 and green <= 12 and blue >= 245:
                                pixels[x, y] = (red, green, blue, 0)
                    alpha = rgba.getchannel("A")
                    indexed = rgba.convert("RGB").quantize(colors=255, method=Image.Quantize.MEDIANCUT,
                                                              dither=Image.Dither.NONE)
                    prepared = indexed.convert("RGBA")
                    prepared.putalpha(alpha)
                    imported.append(prepared)
                    durations.append(max(20, int(frame.info.get("duration", image.info.get("duration", 100)) or 100)))
            if not imported:
                raise ValueError("El archivo no contiene imágenes que pueda abrir el editor.")
            win.frames = imported
            win.durations = durations
            win.frame_index = 0
            win.frame_var.set(1)
            win.frame_spin.configure(to=len(imported))
            win.frame_label.set(f"/ {len(imported)}")
            win.keyframes_by_action = {win.action_var.get(): []}
            win.keyframes = win.keyframes_by_action[win.action_var.get()]
            win.keyframe_list.delete(0, "end")
            win.preview_index = 0
            win.imported_sprite_path = Path(source)
            win.source_asset = {"path": Path(source), "relative": Path("Custom") / (Path(source).stem + ".gif")}
            win.title(f"Editor de píxeles · {Path(source).name} · paleta optimizada")
            win.status.set(f"Hoja importada: {len(imported)} fotograma(s), máximo 255 colores indexados + transparencia.")
            self._native_update_palette(win)
            self._native_draw(win)
            self._native_draw_hud(win)
        except (OSError, ValueError) as exc:
            messagebox.showerror("No se pudo importar la hoja", str(exc), parent=win)

    def _native_change_frame(self, win):
        try:
            index = max(1, min(len(win.frames), int(win.frame_var.get()))) - 1
        except (ValueError, tk.TclError):
            return
        win.frame_index = index
        win.status.set(f"Fotograma {index+1}/{len(win.frames)} · {win.frames[index].width}×{win.frames[index].height}px")
        self._native_update_palette(win)
        self._native_draw(win)

    def _native_save_to_mod(self, win):
        if not win.keyframes:
            messagebox.showinfo("Animación vacía", "Selecciona y añade al menos un fotograma clave antes de guardar.", parent=win)
            return
        base = GAME_DATA_DIR / win.workspace.game_name / "Mod Projects"
        base.mkdir(parents=True, exist_ok=True)
        project_dir = filedialog.askdirectory(parent=win, title="Selecciona un proyecto de mod (carpeta con project.json)",
                                              initialdir=str(base))
        if not project_dir:
            return
        project = Path(project_dir)
        if not (project / "project.json").is_file() or not (project / "Data").is_dir():
            messagebox.showwarning("Elige un proyecto", "La carpeta debe ser un proyecto del launcher con project.json y Data/.", parent=win)
            return
        try:
            metadata = json.loads((project / "project.json").read_text(encoding="utf-8"))
            if metadata.get("game") != win.workspace.game_name:
                raise ValueError("El proyecto es de otro juego.")
            frames = [entry["image"].convert("RGBA") for entry in win.keyframes]
            frame_w = max(frame.width for frame in frames)
            frame_h = max(frame.height for frame in frames)
            if frame_w > 256 or frame_h > 256:
                raise ValueError("RSDKv4 limita a 256×256 px los spritesheets usados por animaciones. Reduce el tamaño de los recortes.")
            cols = min(len(frames), max(1, 256 // frame_w))
            rows = (len(frames) + cols - 1) // cols
            if rows * frame_h > 256:
                raise ValueError("Esta secuencia supera el límite RSDKv4 de 256×256 px. Guarda menos fotogramas por secuencia.")
            sheet = Image.new("RGBA", (cols*frame_w, rows*frame_h), (0, 0, 0, 0))
            frame_coords = []
            for i, frame in enumerate(frames):
                x, y = (i % cols)*frame_w, (i // cols)*frame_h
                sheet.alpha_composite(frame, (x, y))
                frame_coords.append({"x": x, "y": y, "width": frame.width, "height": frame.height,
                                    "duration_ms": int(win.keyframes[i].get("duration", 100)),
                                    "source_rect": win.keyframes[i]["rect"]})
            action_slug = re.sub(r"[^a-z0-9_-]+", "_", win.action_var.get().lower()).strip("_") or "animation"
            sprite_rel = Path("Generated") / f"{action_slug}.gif"
            sprite_path = project / "Data" / "Sprites" / sprite_rel
            sprite_path.parent.mkdir(parents=True, exist_ok=True)
            rgba = sheet
            paletted = rgba.convert("P", palette=Image.Palette.ADAPTIVE, colors=255, dither=Image.Dither.NONE)
            alpha = rgba.getchannel("A")
            paletted.paste(255, mask=alpha.point(lambda value: 255 if value < 128 else 0))
            palette = paletted.getpalette() or []
            palette.extend([0] * (768-len(palette)))
            palette[255*3:255*3+3] = [0, 0, 0]
            paletted.putpalette(palette[:768])
            paletted.info["transparency"] = 255
            paletted.save(sprite_path, transparency=255, optimize=False)

            script_rel = Path("Generated") / f"{action_slug}.txt"
            script_path = project / "Data" / "Scripts" / script_rel
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_lines = [f"// Generated by Hedgehod Launcher for {win.workspace.game_name}",
                "// RetroScript v4 frame declarations. Include these in the matching object script.",
                f'LoadSpriteSheet("{sprite_rel.as_posix()}")']
            for frame in frame_coords:
                script_lines.append(f'SpriteFrame(0, 0, {frame["width"]}, {frame["height"]}, {frame["x"]}, {frame["y"]})')
            script_path.write_text("\n".join(script_lines) + "\n", encoding="utf-8")
            descriptor = {"format": "hedgehog-animation-project", "version": 1,
                "game": win.workspace.game_name, "action": win.action_var.get(),
                "sprite_sheet": f"Data/Sprites/{sprite_rel.as_posix()}",
                "retroscript_source": f"Data/Scripts/{script_rel.as_posix()}",
                "frames": frame_coords,
                "note": "RetroScript SpriteFrame declarations are generated. To play a timed RSDKv4 animation in-game, connect these frames to the game's .ani animation resource and object logic."}
            manifest_path = project / f"{action_slug}.animation.json"
            manifest_path.write_text(json.dumps(descriptor, ensure_ascii=False, indent=2), encoding="utf-8")
            win.status.set(f"Animación {win.action_var.get()} guardada en {project.name}.")
            messagebox.showinfo("Animación exportada", f"Se guardaron el spritesheet GIF, las declaraciones RetroScript y el manifiesto:\n\n{sprite_path}\n{script_path}\n{manifest_path}\n\nEl código SpriteFrame lo entiende RetroScript v4; para reproducir tiempos en el juego, el motor también requiere vincular los frames a su recurso .ani.", parent=win)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            messagebox.showerror("No se pudo guardar la animación", str(exc), parent=win)

    def _native_save_as(self, win):
        asset = win.source_asset
        initial = GAME_DATA_DIR / win.workspace.game_name / "Sprite Edits" / asset["relative"]
        initial.parent.mkdir(parents=True, exist_ok=True)
        is_animated = len(win.frames) > 1
        extension = ".gif" if is_animated else ".png"
        output = filedialog.asksaveasfilename(parent=win, title="Guardar sprite editado como copia",
            initialdir=str(initial.parent), initialfile=initial.name if extension == asset["path"].suffix.lower() else asset["path"].stem + extension,
            defaultextension=extension, filetypes=[("GIF animado", "*.gif"), ("PNG", "*.png"), ("WebP", "*.webp"), ("Todos", "*.*")])
        if not output:
            return
        try:
            self._native_write_image(win, Path(output))
            win.status.set(f"Copia editada guardada: {output}")
            messagebox.showinfo("Edición guardada", f"Se guardó la copia editada:\n{output}\n\nEl archivo original no se modificó.", parent=win)
        except (OSError, ValueError) as exc:
            messagebox.showerror("No se pudo guardar la edición", str(exc), parent=win)

    @staticmethod
    def _native_write_image(win, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        suffix = path.suffix.lower()
        if suffix == ".gif" and len(win.frames) > 1:
            encoded = []
            for frame in win.frames:
                rgba = frame.convert("RGBA")
                paletted = rgba.convert("P", palette=Image.Palette.ADAPTIVE, colors=255, dither=Image.Dither.NONE)
                alpha = rgba.getchannel("A")
                paletted.paste(255, mask=alpha.point(lambda value: 255 if value < 128 else 0))
                palette = paletted.getpalette() or []
                palette.extend([0] * (768-len(palette)))
                palette[255*3:255*3+3] = [0, 0, 0]
                paletted.putpalette(palette[:768])
                paletted.info["transparency"] = 255
                encoded.append(paletted)
            durations = win.durations if len(win.durations) == len(encoded) else [100]*len(encoded)
            encoded[0].save(path, save_all=True, append_images=encoded[1:],
                duration=durations, loop=win.workspace.source_info.get("loop", 0),
                disposal=2, transparency=255, optimize=False)
        else:
            frame = win.frames[win.frame_index]
            if suffix in (".jpg", ".jpeg"):
                frame.convert("RGB").save(path)
            else:
                frame.save(path, format={".png":"PNG", ".webp":"WEBP", ".bmp":"BMP", ".tga":"TGA"}.get(suffix, "PNG"))

    def _size_changed(self, win, source):
        if win._updating_size or not win.preview_image:
            return
        try:
            value = max(1, min(8192, int(win.width_var.get() if source == "width" else win.height_var.get())))
            ow, oh = win.original_size
            win._updating_size = True
            if win.keep_ratio.get():
                if source == "width":
                    win.height_var.set(str(max(1, round(value*oh/ow))))
                else:
                    win.width_var.set(str(max(1, round(value*ow/oh))))
            win._updating_size = False
            self._draw_sprite_preview(win)
        except ValueError:
            win._updating_size = False

    def _open_selected_in_libresprite(self, win):
        if not win.selected_asset:
            messagebox.showinfo("Selecciona un sprite", "Elige primero un asset de la biblioteca.", parent=win)
            return
        editor = Path(self.libresprite_exe.get().strip()).expanduser()
        if not editor.is_file():
            selected = filedialog.askopenfilename(parent=win, title="Selecciona LibreSprite.exe",
                filetypes=[("LibreSprite", "LibreSprite.exe"), ("Aplicación", "*.exe")])
            if not selected:
                return
            editor = Path(selected)
            self.libresprite_exe.set(str(editor)); self.save_config()
        try:
            subprocess.Popen([str(editor), str(win.selected_asset["path"])], cwd=str(editor.parent))
        except OSError as exc:
            messagebox.showerror("No se pudo abrir LibreSprite", str(exc), parent=win)

    def _save_resized_sprite(self, win):
        if not win.selected_asset:
            messagebox.showinfo("Selecciona un sprite", "Elige primero un asset de la biblioteca.", parent=win)
            return
        try:
            width, height = int(win.width_var.get()), int(win.height_var.get())
            if not (1 <= width <= 8192 and 1 <= height <= 8192):
                raise ValueError
        except ValueError:
            messagebox.showerror("Dimensiones no válidas", "Usa valores entre 1 y 8192 píxeles.", parent=win)
            return
        source_path = win.selected_asset["path"]
        relative = win.selected_asset["relative"]
        output_dir = GAME_DATA_DIR / win.game_name / "Sprite Edits" / relative.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = filedialog.asksaveasfilename(parent=win, title="Guardar sprite reescalado",
            initialdir=str(output_dir), initialfile=source_path.name,
            defaultextension=source_path.suffix,
            filetypes=[(f"Imagen {source_path.suffix.upper()}", f"*{source_path.suffix}"), ("PNG", "*.png"), ("Todos los archivos", "*.*")])
        if not output_path:
            return
        try:
            frames = [frame.resize((width, height), Image.Resampling.NEAREST)
                      for frame in win.preview_frames] or [win.preview_image.resize((width, height), Image.Resampling.NEAREST)]
            if Path(output_path).suffix.lower() == ".gif" and len(frames) > 1:
                durations = win.frame_durations or [100] * len(frames)
                frames[0].save(output_path, save_all=True, append_images=frames[1:], duration=durations,
                               loop=win.source_info.get("loop", 0), disposal=2, optimize=False)
            else:
                resized = frames[0]
                if resized.mode == "RGBA" and Path(output_path).suffix.lower() in (".jpg", ".jpeg"):
                    resized = resized.convert("RGB")
                resized.save(output_path)
            messagebox.showinfo("Copia guardada", f"Se guardó {width} × {height} px sin tocar el asset original:\n{output_path}", parent=win)
        except (OSError, ValueError) as exc:
            messagebox.showerror("No se pudo guardar la imagen", str(exc), parent=win)

    def install_engine(self):
        """Fetch the official Windows release and place it beside the selected datapack."""
        if self.profile_name.get() not in ("Sonic 1", "Sonic 2"):
            messagebox.showinfo("Motor diferente requerido",
                "Este instalador solo configura RSDKv4 para Sonic 1 o Sonic 2. Selecciona el ejecutable compatible "
                "con este juego mediante Examinar….", parent=self.root)
            return
        folder = Path(self.game_dir.get().strip()).expanduser()
        if not folder.is_dir():
            messagebox.showwarning("Primero elige la carpeta del juego",
                "Selecciona la carpeta del juego antes de instalar el motor. El RSDK se instalará junto a Data.rsdk.",
                parent=self.root)
            return

        datapack = next((folder / name for name in ("Data.rsdk", "Data.rsdk.xmf", "Data.rsdk.uncompressed")
                         if (folder / name).is_file()), None)
        if datapack is None:
            messagebox.showwarning("No se encontró Data.rsdk",
                "La carpeta seleccionada no contiene Data.rsdk. Elige la carpeta correcta para evitar mezclar archivos.",
                parent=self.root)
            return

        accepted = messagebox.askyesno("Descargar RSDKv4 oficial",
            "Se consultará el último lanzamiento de RSDKModding/RSDKv4-Decompilation y se instalará el paquete Windows "
            "en la carpeta del juego. No se sobrescribirán archivos existentes.\n\n"
            "Este es un proyecto de decompilación independiente: uso no comercial, créditos a sus autores y licencia "
            "incluida. El paquete no contiene los datos del juego.\n\n¿Continuar?",
            parent=self.root)
        if not accepted:
            return

        try:
            request = urllib.request.Request(RSDK_RELEASES_API,
                headers={"User-Agent": "HedgehodLauncher/0.1", "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(request, timeout=30) as response:
                release = json.loads(response.read().decode("utf-8"))
            assets = [asset for asset in release.get("assets", [])
                      if asset.get("name", "").lower().endswith(".zip")]
            windows_assets = [asset for asset in assets
                              if any(word in asset.get("name", "").lower() for word in ("windows", "win64", "win32", "win-x64"))]
            if not windows_assets:
                messagebox.showinfo("Lanzamiento oficial disponible",
                    "No pude identificar automáticamente el paquete Windows. Se abrirá la página oficial para que "
                    "revises y descargues el asset correcto.", parent=self.root)
                import webbrowser
                webbrowser.open(release.get("html_url", RSDK_REPO + "/releases"))
                return
            asset = next((item for item in windows_assets
                          if any(word in item["name"].lower() for word in ("x64", "64-bit", "64bit"))), windows_assets[0])
            download_url = asset.get("browser_download_url", "")
            parsed_url = urllib.parse.urlparse(download_url)
            if parsed_url.scheme != "https" or parsed_url.hostname != "github.com":
                raise ValueError("La dirección del paquete no pertenece al lanzamiento oficial de GitHub.")

            version = release.get("tag_name", "versión sin etiqueta")
            confirm_asset = messagebox.askyesno("Confirmar paquete oficial",
                f"Paquete: {asset['name']}\nVersión: {version}\nOrigen: {RSDK_REPO}/releases\n\n"
                "El archivo se descargará y extraerá junto a Data.rsdk. ¿Instalarlo?",
                parent=self.root)
            if not confirm_asset:
                return

            request = urllib.request.Request(download_url, headers={"User-Agent": "HedgehodLauncher/0.1"})
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read(500 * 1024 * 1024 + 1)
            if len(payload) > 500 * 1024 * 1024:
                raise ValueError("El paquete supera el límite de tamaño de 500 MiB.")

            with tempfile.TemporaryDirectory(prefix="hedgehod-rsdk-") as temp_dir:
                archive_path = Path(temp_dir) / Path(asset["name"]).name
                archive_path.write_bytes(payload)
                if not zipfile.is_zipfile(archive_path):
                    raise ValueError("El archivo descargado no es un ZIP válido.")
                with zipfile.ZipFile(archive_path) as archive:
                    members = archive.infolist()
                    if len(members) > 2000 or sum(info.file_size for info in members) > 1024 * 1024 * 1024:
                        raise ValueError("El contenido del paquete supera los límites seguros de extracción.")
                    safe_members = []
                    member_names = set()
                    for info in members:
                        if info.filename in member_names:
                            raise ValueError("El ZIP contiene nombres de archivo duplicados.")
                        member_names.add(info.filename)
                        member_path = Path(info.filename)
                        if member_path.is_absolute() or ".." in member_path.parts:
                            raise ValueError("El ZIP contiene una ruta de archivo no permitida.")
                        destination = (folder / member_path).resolve()
                        if folder.resolve() not in destination.parents and destination != folder.resolve():
                            raise ValueError("El ZIP intenta extraer archivos fuera de la carpeta del juego.")
                        if destination.exists():
                            raise FileExistsError(f"No se sobrescribió el archivo existente: {destination.name}")
                        safe_members.append((info, destination))
                    for info, destination in safe_members:
                        if info.is_dir():
                            destination.mkdir(parents=True, exist_ok=True)
                            continue
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(info) as source, destination.open("wb") as output:
                            shutil.copyfileobj(source, output)

            executables = [path for path in folder.rglob("*.exe") if "rsdkv4" in path.stem.lower()]
            if not executables:
                messagebox.showwarning("Motor descargado; ejecutable no detectado",
                    "El paquete se extrajo, pero no encontré un ejecutable con RSDKv4 en el nombre. "
                    "Selecciona manualmente el EXE con Examinar….", parent=self.root)
                return
            engine = next((path for path in executables if path.parent == folder), executables[0])
            self.engine_exe.set(str(engine))
            license_path = engine.parent / "RSDKv4-LICENSE.md"
            if not license_path.exists():
                try:
                    license_request = urllib.request.Request(RSDK_LICENSE_URL, headers={"User-Agent": "HedgehodLauncher/0.1"})
                    with urllib.request.urlopen(license_request, timeout=20) as response:
                        license_path.write_bytes(response.read(200_000))
                except Exception:
                    license_path.write_text(
                        "RSDKv4 Decompilation source and license: " + RSDK_REPO + "\n"
                        "License: " + RSDK_REPO + "/blob/main/LICENSE.md\n",
                        encoding="utf-8")
            self.save_config()
            messagebox.showinfo("RSDKv4 instalado", f"Se instaló {version}.\n\nEjecutable: {engine}", parent=self.root)
        except Exception as exc:
            messagebox.showerror("No se pudo instalar RSDKv4", str(exc), parent=self.root)

    def launch_game(self):
        folder = Path(self.game_dir.get().strip()).expanduser()
        executable = Path(self.engine_exe.get().strip()).expanduser()
        if not folder.is_dir():
            messagebox.showwarning("Falta la carpeta del juego", f"Selecciona Data Games/{self.profile_name.get()} o la carpeta que contiene los archivos del juego.", parent=self.root)
            return
        if not executable.is_file():
            messagebox.showwarning("Falta el ejecutable del motor", f"Selecciona un ejecutable compatible con {self.profile_name.get()}.", parent=self.root)
            return
        if not self.save_config():
            return
        data_candidates = (folder / "Data.rsdk", folder / "Data.rsdk.xmf", folder / "Data.rsdk.uncompressed")
        if not any(path.is_file() for path in data_candidates):
            proceed = messagebox.askyesno("No se detectó Data.rsdk",
                "No encontré Data.rsdk en esa carpeta. ¿Quieres intentar iniciar el motor de todos modos?", parent=self.root)
            if not proceed:
                return
        if self.profile_name.get() == "Sonic Mania" and not (folder / "Game.dll").is_file():
            proceed = messagebox.askyesno("Falta Game.dll",
                "La configuración RSDKv5 de Sonic Mania normalmente necesita Game.dll compatible junto a Data.rsdk. "
                "No se encontró en esta carpeta. ¿Quieres intentar iniciar de todos modos?",
                parent=self.root)
            if not proceed:
                return
        try:
            subprocess.Popen([str(executable)], cwd=str(folder), shell=False)
        except OSError as exc:
            messagebox.showerror("No se pudo iniciar RSDKv4", str(exc), parent=self.root)

    def close(self):
        self.save_config()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    HedgehodLauncher(root)
    root.mainloop()



