#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convertisseur Média — interface Tkinter pour FFmpeg
Prérequis : Python 3.10+ et FFmpeg/FFprobe installés et accessibles dans PATH.
Lancer : python convertisseur_media.py
"""

import os
import shutil
import subprocess
import threading
import queue
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "Convertisseur Média — FFmpeg"

# Formats pris en charge en sortie. Certains codecs dépendent de la compilation FFmpeg.
FORMATS = {
    "MP4": ".mp4",
    "WebM": ".webm",
    "WebP animé": ".webp",
    "GIF animé": ".gif",
    "MOV": ".mov",
    "MKV": ".mkv",
    "AVI": ".avi",
    "MP3 (audio)": ".mp3",
    "WAV (audio)": ".wav",
    "FLAC (audio)": ".flac",
}
SOURCE_FILTERS = {
    "Tous les formats pris en charge": ["*"],
    "MP4": [".mp4", ".m4v"],
    "WebM": [".webm"],
    "WebP animé": [".webp"],
    "GIF animé": [".gif"],
    "MOV": [".mov"],
    "MKV": [".mkv"],
    "AVI": [".avi"],
    "Audio": [".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".opus"],
}

VIDEO_EXTS = {".mp4", ".m4v", ".webm", ".mov", ".mkv", ".avi", ".wmv", ".flv", ".mpeg", ".mpg", ".ogv", ".gif", ".webp"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".opus", ".wma"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

class MediaConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.quality_label = None
        self.title(APP_TITLE)
        self.geometry("1080x720")
        self.minsize(900, 620)
        self.files = []
        self.events = queue.Queue()
        self.is_running = False
        self.output_dir = tk.StringVar(value=str(Path.home() / "Videos" / "Convertis"))
        self.source_format = tk.StringVar(value="Tous les formats pris en charge")
        self.target_format = tk.StringVar(value="WebP animé")
        self.quality = tk.IntVar(value=90)
        self.fps = tk.IntVar(value=24)
        self.max_width = tk.StringVar(value="Conserver l'original")
        self.webp_duration = tk.StringVar(value="Toute la durée")
        self.overwrite = tk.BooleanVar(value=False)
        self.keep_audio = tk.BooleanVar(value=True)
        self._setup_style()
        self._build_menu()
        self._build_ui()
        self.after(100, self._poll_events)
        self._check_ffmpeg()

    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Header.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Section.TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=27)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Ouvrir des fichiers…", accelerator="Ctrl+O", command=self.add_files)
        file_menu.add_command(label="Ouvrir un dossier…", accelerator="Ctrl+Maj+O", command=self.add_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Choisir le dossier de sortie…", command=self.choose_output)
        file_menu.add_separator()
        file_menu.add_command(label="Quitter", command=self.destroy)
        menubar.add_cascade(label="Fichier", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=False)
        edit_menu.add_command(label="Retirer les fichiers sélectionnés", command=self.remove_selected)
        edit_menu.add_command(label="Vider la liste", command=self.clear_files)
        menubar.add_cascade(label="Édition", menu=edit_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="Vérifier FFmpeg", command=self._check_ffmpeg)
        help_menu.add_command(label="À propos", command=lambda: messagebox.showinfo(
            "À propos", "Convertisseur Média — FFmpeg\nInterface Python/Tkinter.\nFFmpeg doit être installé séparément."))
        menubar.add_cascade(label="Aide", menu=help_menu)
        self.config(menu=menubar)
        self.bind_all("<Control-o>", lambda _e: self.add_files())
        self.bind_all("<Control-Shift-O>", lambda _e: self.add_folder())

    def _build_ui(self):
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="🎞  Convertisseur Média", style="Header.TLabel").pack(anchor="w")
        ttk.Label(header, text="Conversion par lots de vidéos, animations et fichiers audio avec FFmpeg.").pack(anchor="w", pady=(3, 0))

        top = ttk.Frame(root)
        top.pack(fill="both", expand=True)
        left = ttk.LabelFrame(top, text=" Fichiers à convertir ", style="Section.TLabelframe", padding=8)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        right = ttk.LabelFrame(top, text=" Paramètres de conversion ", style="Section.TLabelframe", padding=12)
        right.pack(side="right", fill="y", padx=(8, 0))
        right.configure(width=340)
        right.pack_propagate(False)

        toolbar = ttk.Frame(left)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="＋ Ajouter des fichiers", command=self.add_files).pack(side="left")
        ttk.Button(toolbar, text="Ajouter un dossier", command=self.add_folder).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Retirer", command=self.remove_selected).pack(side="right")
        cols = ("name", "size", "format", "status")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("name", text="Nom du fichier")
        self.tree.heading("size", text="Taille")
        self.tree.heading("format", text="Format")
        self.tree.heading("status", text="État")
        self.tree.column("name", width=280, minwidth=150)
        self.tree.column("size", width=85, anchor="e")
        self.tree.column("format", width=85)
        self.tree.column("status", width=110)
        yscroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")

        ttk.Label(right, text="Format source").pack(anchor="w")
        self.source_combo = ttk.Combobox(right, textvariable=self.source_format, state="readonly",
                                         values=list(SOURCE_FILTERS), width=32)
        self.source_combo.pack(fill="x", pady=(3, 10))
        self.source_combo.bind("<<ComboboxSelected>>", self._source_changed)
        ttk.Label(right, text="Convertir vers").pack(anchor="w")
        ttk.Combobox(right, textvariable=self.target_format, state="readonly",
                     values=list(FORMATS), width=32).pack(fill="x", pady=(3, 12))

        ttk.Separator(right).pack(fill="x", pady=5)
        ttk.Label(right, text="Options vidéo").pack(anchor="w", pady=(3, 5))
        ttk.Label(right, text="Qualité (0–100 ; plus haut = meilleure qualité)").pack(anchor="w")
        qrow = ttk.Frame(right)
        qrow.pack(fill="x", pady=(2, 8))
        self.quality_label
        self.quality_scale = ttk.Scale(qrow, from_=40, to=100, orient="horizontal",
                                       command=self._quality_changed)
        self.quality_scale.set(90)
        self.quality_scale.pack(side="left", fill="x", expand=True)
        self.quality_label = ttk.Label(qrow, text="90", width=4, anchor="e")
        self.quality_label.pack(side="right", padx=(6, 0))

        ttk.Label(right, text="Fréquence d'images (FPS)").pack(anchor="w")
        ttk.Spinbox(right, from_=5, to=60, increment=1, textvariable=self.fps, width=8).pack(anchor="w", pady=(2, 8))
        ttk.Label(right, text="Largeur maximale").pack(anchor="w")
        ttk.Combobox(right, textvariable=self.max_width, state="readonly",
                     values=["Conserver l'original", "1920 px", "1280 px", "960 px", "800 px", "640 px"],
                     width=28).pack(fill="x", pady=(2, 8))
        ttk.Label(right, text="Durée pour WebP/GIF").pack(anchor="w")
        ttk.Combobox(right, textvariable=self.webp_duration, state="readonly",
                     values=["Toute la durée", "5 secondes", "8 secondes", "9 secondes", "10 secondes"],
                     width=28).pack(fill="x", pady=(2, 8))
        ttk.Checkbutton(right, text="Conserver l'audio (si applicable)", variable=self.keep_audio).pack(anchor="w", pady=(3, 8))
        ttk.Checkbutton(right, text="Écraser les fichiers existants", variable=self.overwrite).pack(anchor="w", pady=(0, 8))

        ttk.Separator(right).pack(fill="x", pady=5)
        ttk.Button(right, text="▶  Lancer la conversion", style="Accent.TButton",
                   command=self.start_conversion).pack(fill="x", pady=(7, 4))
        ttk.Button(right, text="Ouvrir le dossier de sortie", command=self.open_output).pack(fill="x", pady=3)

        out = ttk.LabelFrame(root, text=" Dossier de sortie ", style="Section.TLabelframe", padding=8)
        out.pack(fill="x", pady=(12, 8))
        ttk.Entry(out, textvariable=self.output_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(out, text="Parcourir…", command=self.choose_output).pack(side="left", padx=(8, 0))

        log_frame = ttk.LabelFrame(root, text=" Journal ", style="Section.TLabelframe", padding=8)
        log_frame.pack(fill="both", expand=False)
        self.log_text = tk.Text(log_frame, height=6, wrap="word", state="disabled", font=("Consolas", 9))
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")
        self.progress = ttk.Progressbar(root, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(8, 0))
        self.status_label = ttk.Label(root, text="Prêt.")
        self.status_label.pack(anchor="w", pady=(3, 0))

    def _check_ffmpeg(self):
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        if ffmpeg and ffprobe:
            self._log(f"[OK] FFmpeg trouvé : {ffmpeg}")
            self.status_label.config(text="FFmpeg est disponible.")
        else:
            missing = []
            if not ffmpeg: missing.append("ffmpeg")
            if not ffprobe: missing.append("ffprobe")
            msg = "Composant(s) introuvable(s) : " + ", ".join(missing) + ". Installe FFmpeg et ajoute son dossier bin au PATH."
            self._log("[ATTENTION] " + msg)
            messagebox.showwarning("FFmpeg introuvable", msg + "\n\nTéléchargement : https://ffmpeg.org/download.html")

    def _source_changed(self, _event=None):
        # La liste choisie dans le menu source sert de filtre lors de l'ouverture.
        return

    def add_files(self):
        src = self.source_format.get()
        extensions = SOURCE_FILTERS.get(src, ["*"])
        patterns = " ".join("*" + e for e in extensions if e != "*")
        filetypes = [("Formats pris en charge", patterns or "*.*")]
        filetypes.append(("Tous les fichiers", "*.*"))
        chosen = filedialog.askopenfilenames(title="Choisir un ou plusieurs fichiers", filetypes=filetypes)
        self._add_paths(chosen)

    def add_folder(self):
        folder = filedialog.askdirectory(title="Choisir un dossier contenant les médias")
        if not folder:
            return
        paths = []
        allowed = set()
        selected = self.source_format.get()
        exts = SOURCE_FILTERS.get(selected, ["*"])
        if "*" not in exts:
            allowed = set(exts)
        for p in Path(folder).iterdir():
            if p.is_file() and (not allowed or p.suffix.lower() in allowed):
                if p.suffix.lower() in VIDEO_EXTS | AUDIO_EXTS | IMAGE_EXTS:
                    paths.append(str(p))
        self._add_paths(paths)

    def _add_paths(self, paths):
        existing = {str(Path(p).resolve()) for p in self.files}
        added = 0
        for raw in paths:
            p = Path(raw)
            if not p.is_file():
                continue
            resolved = str(p.resolve())
            if resolved in existing:
                continue
            self.files.append(resolved)
            self.tree.insert("", "end", iid=resolved, values=(p.name, self._human_size(p.stat().st_size),
                                                              p.suffix.upper().lstrip("."), "En attente"))
            existing.add(resolved)
            added += 1
        if added:
            self._log(f"[INFO] {added} fichier(s) ajouté(s).")
            self.status_label.config(text=f"{len(self.files)} fichier(s) dans la liste.")

    @staticmethod
    def _human_size(n):
        value = float(n)
        for unit in ("o", "Ko", "Mo", "Go", "To"):
            if value < 1024 or unit == "To":
                return f"{value:.1f} {unit}"
            value /= 1024
        return f"{value:.1f} To"

    def remove_selected(self):
        selected = self.tree.selection()
        for iid in selected:
            if iid in self.files:
                self.files.remove(iid)
            self.tree.delete(iid)
        self.status_label.config(text=f"{len(self.files)} fichier(s) dans la liste.")

    def clear_files(self):
        self.files.clear()
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.status_label.config(text="Liste vidée.")

    def choose_output(self):
        chosen = filedialog.askdirectory(title="Choisir le dossier de sortie",
                                         initialdir=self.output_dir.get() or str(Path.home()))
        if chosen:
            self.output_dir.set(chosen)

    def open_output(self):
        path = Path(self.output_dir.get()).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(path))
            elif os.uname().sysname == "Darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror("Ouverture impossible", str(exc))

    def _quality_changed(self, value):
        quality = round(float(value))
        self.quality.set(quality)

        label = getattr(self, "quality_label", None)
        if label is not None and label.winfo_exists():
            label.config(text=str(quality))

    def _log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_row_status(self, path, status):
        if self.tree.exists(path):
            vals = list(self.tree.item(path, "values"))
            vals[3] = status
            self.tree.item(path, values=vals)

    def start_conversion(self):
        if self.is_running:
            messagebox.showinfo("Conversion en cours", "Une conversion est déjà en cours.")
            return
        if not self.files:
            messagebox.showwarning("Aucun fichier", "Ajoute d'abord un ou plusieurs fichiers.")
            return
        if not shutil.which("ffmpeg"):
            messagebox.showerror("FFmpeg introuvable", "FFmpeg n'est pas accessible. Installe-le puis relance le programme.")
            return
        output = Path(self.output_dir.get()).expanduser()
        try:
            output.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            messagebox.showerror("Dossier invalide", str(exc))
            return
        target = self.target_format.get()
        snapshot = list(self.files)
        # Lire les paramètres Tkinter dans le thread principal, puis transmettre un instantané
        # au thread de conversion (les variables Tk ne doivent pas être consultées en arrière-plan).
        settings = {
            "quality": int(self.quality.get()),
            "fps": int(self.fps.get()),
            "max_width": self.max_width.get(),
            "duration": self.webp_duration.get(),
            "overwrite": bool(self.overwrite.get()),
            "keep_audio": bool(self.keep_audio.get()),
        }
        self.is_running = True
        self.progress.configure(value=0, maximum=len(snapshot))
        self.status_label.config(text="Conversion en cours…")
        self._log(f"[INFO] Conversion de {len(snapshot)} fichier(s) vers {target}.")
        threading.Thread(target=self._conversion_worker, args=(snapshot, output, target, settings), daemon=True).start()

    def _build_command(self, src, dest, target, settings):
        ext = src.suffix.lower()
        q = settings["quality"]
        fps = max(1, min(60, settings["fps"]))
        width_choice = settings["max_width"]
        max_width = None if width_choice == "Conserver l'original" else int(width_choice.split()[0])
        duration_choice = settings["duration"]
        duration = None if duration_choice == "Toute la durée" else float(duration_choice.split()[0])
        cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-y" if settings["overwrite"] else "-n", "-i", str(src)]
        if duration is not None and target in ("WebP animé", "GIF animé"):
            cmd += ["-t", str(duration)]

        is_audio_target = target.startswith(("MP3", "WAV", "FLAC"))
        is_audio_source = ext in AUDIO_EXTS
        is_video_source = ext in VIDEO_EXTS
        is_image_source = ext in IMAGE_EXTS
        if not (is_audio_source or is_video_source or is_image_source):
            raise ValueError(f"Format source non pris en charge : {ext or '(sans extension)'}")

        if target == "WebP animé":
            if is_audio_source:
                raise ValueError("Impossible de convertir un fichier audio seul en WebP animé.")
            filters = []
            if max_width:
                filters.append(f"scale='min({max_width},iw)':-2:flags=lanczos")
            else:
                filters.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")
            filters.insert(0, f"fps={fps}")
            cmd += ["-vf", ",".join(filters), "-an", "-c:v", "libwebp", "-lossless", "0",
                    "-quality", str(q), "-compression_level", "6", "-loop", "0"]
        elif target == "GIF animé":
            if is_audio_source:
                raise ValueError("Impossible de convertir un fichier audio seul en GIF.")
            width = max_width or 1280
            vf = f"fps={fps},scale='min({width},iw)':-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse"
            cmd += ["-filter_complex", vf, "-an"]
        elif target == "WebM":
            if is_audio_source:
                cmd += ["-vn", "-c:a", "libopus", "-b:a", "192k"]
            else:
                vf = []
                if max_width: vf.append(f"scale='min({max_width},iw)':-2:flags=lanczos")
                if vf: cmd += ["-vf", ",".join(vf)]
                cmd += ["-c:v", "libvpx-vp9", "-crf", str(max(10, min(50, 50 - q // 2))), "-b:v", "0", "-deadline", "good", "-cpu-used", "2"]
                if settings["keep_audio"]: cmd += ["-c:a", "libopus", "-b:a", "128k"]
                else: cmd += ["-an"]
        elif target == "MP4":
            if is_audio_source:
                raise ValueError("Pour un fichier audio, choisis MP3, WAV ou FLAC.")
            vf = []
            if max_width: vf.append(f"scale='min({max_width},iw)':-2:flags=lanczos")
            if vf: cmd += ["-vf", ",".join(vf)]
            cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", str(max(14, min(35, 38 - q // 4))), "-pix_fmt", "yuv420p"]
            if settings["keep_audio"]: cmd += ["-c:a", "aac", "-b:a", "192k"]
            else: cmd += ["-an"]
        elif target in ("MOV", "MKV", "AVI"):
            if is_audio_source:
                raise ValueError("Choisis un format de sortie audio pour une source audio.")
            vf = []
            if max_width: vf.append(f"scale='min({max_width},iw)':-2:flags=lanczos")
            if vf: cmd += ["-vf", ",".join(vf)]
            if target == "AVI":
                cmd += ["-c:v", "mpeg4", "-q:v", str(max(2, min(10, 11 - q // 10)))]
            else:
                cmd += ["-c:v", "libx264", "-crf", str(max(14, min(35, 38 - q // 4))), "-preset", "medium"]
            if settings["keep_audio"]: cmd += ["-c:a", "aac"]
            else: cmd += ["-an"]
        elif target.startswith("MP3"):
            cmd += ["-vn", "-c:a", "libmp3lame", "-q:a", str(max(0, min(9, (100 - q) // 10)))]
        elif target.startswith("WAV"):
            cmd += ["-vn", "-c:a", "pcm_s16le"]
        elif target.startswith("FLAC"):
            cmd += ["-vn", "-c:a", "flac"]
        else:
            raise ValueError(f"Format de sortie inconnu : {target}")

        cmd += [str(dest)]
        return cmd

    def _conversion_worker(self, files, output, target, settings):
        done = 0
        for src_str in files:
            src = Path(src_str)
            dest = output / (src.stem + FORMATS[target])
            if dest.resolve() == src.resolve():
                dest = output / (src.stem + "_converti" + FORMATS[target])
            if dest.exists() and not settings["overwrite"]:
                self.events.put(("log", f"[IGNORÉ] {dest.name} existe déjà (activer l'écrasement pour le remplacer)."))
                self.events.put(("row", (src_str, "Déjà présent")))
                done += 1
                self.events.put(("progress", done, len(files)))
                continue
            try:
                cmd = self._build_command(src, dest, target, settings)
                self.events.put(("row", (src_str, "Conversion…")))
                self.events.put(("log", f"[INFO] {src.name} → {dest.name}"))
                result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
                if result.returncode == 0 and dest.exists():
                    self.events.put(("row", (src_str, "Terminé")))
                    self.events.put(("log", f"[OK] {dest.name} ({self._human_size(dest.stat().st_size)})"))
                else:
                    error = (result.stderr or result.stdout or "Erreur FFmpeg inconnue").strip().splitlines()
                    self.events.put(("row", (src_str, "Échec")))
                    self.events.put(("log", f"[ERREUR] {src.name} : " + (error[-1] if error else "échec")))
                    if dest.exists() and dest.stat().st_size == 0:
                        dest.unlink(missing_ok=True)
            except Exception as exc:
                self.events.put(("row", (src_str, "Échec")))
                self.events.put(("log", f"[ERREUR] {src.name} : {exc}"))
            done += 1
            self.events.put(("progress", done, len(files)))
        self.events.put(("finished",))

    def _poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "log":
                    self._log(event[1])
                elif kind == "row":
                    self._set_row_status(*event[1])
                elif kind == "progress":
                    _, done, total = event
                    self.progress.configure(value=done, maximum=max(1, total))
                    self.status_label.config(text=f"Progression : {done}/{total}")
                elif kind == "finished":
                    self.is_running = False
                    self.status_label.config(text="Conversion terminée.")
                    self._log("[INFO] Toutes les conversions sont terminées.")
        except queue.Empty:
            pass
        self.after(100, self._poll_events)


if __name__ == "__main__":
    app = MediaConverterApp()
    app.mainloop()
