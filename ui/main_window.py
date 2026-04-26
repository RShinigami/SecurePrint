"""
Module 7 : Interface Utilisateur
Fichier : ui/main_window.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import threading
import customtkinter as ctk
from tkinter import filedialog
from PIL import Image

from modules.template import generate_template
from modules.storage  import SecurePrintDB
from modules.matcher  import identify, DEFAULT_THRESHOLD

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

GREEN  = "#4ecca3"
RED    = "#e94560"
YELLOW = "#f5a623"
DIM    = "#7a7a9a"


class SecurePrintApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SecurePrint — Authentification Biométrique")
        self.geometry("780x680")
        self.resizable(False, False)

        self.db = SecurePrintDB()

        self.enroll_image_path = ctk.StringVar()
        self.auth_image_path   = ctk.StringVar()
        self.enroll_name       = ctk.StringVar()

        self._build_header()
        self._build_tabs()
        self._build_status_bar()

    # ── Header ────────────────────────────────────────────
    def _build_header(self):
        header = ctk.CTkFrame(self, corner_radius=0, fg_color="#0f3460")
        header.pack(fill="x")
        ctk.CTkLabel(header, text="🔒 SECUREPRINT",
                     font=("Courier New", 20, "bold"),
                     text_color=GREEN).pack(pady=(12, 2))
        ctk.CTkLabel(header,
                     text="Système d'authentification biométrique par empreinte digitale",
                     font=("Courier New", 10), text_color=DIM).pack(pady=(0, 10))

    # ── Tabs ──────────────────────────────────────────────
    def _build_tabs(self):
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=15, pady=10)
        self.tabs.add("  📋 ENRÔLEMENT  ")
        self.tabs.add("  🔍 AUTHENTIFICATION  ")
        self._build_enroll_tab(self.tabs.tab("  📋 ENRÔLEMENT  "))
        self._build_auth_tab(self.tabs.tab("  🔍 AUTHENTIFICATION  "))

    # ── Enroll Tab ────────────────────────────────────────
    def _build_enroll_tab(self, tab):
        ctk.CTkLabel(tab, text="Enregistrer un nouvel utilisateur",
                     font=("Courier New", 13, "bold"),
                     text_color=GREEN).pack(pady=(15, 3))
        ctk.CTkLabel(tab,
                     text="Le template biométrique sera chiffré (AES-256).\nAucune image n'est conservée.",
                     font=("Courier New", 10), text_color=DIM).pack(pady=(0, 12))

        row1 = ctk.CTkFrame(tab, fg_color="transparent")
        row1.pack(fill="x", padx=30, pady=4)
        ctk.CTkLabel(row1, text="Nom :", width=80,
                     font=("Courier New", 11)).pack(side="left")
        ctk.CTkEntry(row1, textvariable=self.enroll_name,
                     font=("Courier New", 11), width=280).pack(side="left", padx=8)

        row2 = ctk.CTkFrame(tab, fg_color="transparent")
        row2.pack(fill="x", padx=30, pady=4)
        ctk.CTkLabel(row2, text="Image :", width=80,
                     font=("Courier New", 11)).pack(side="left")
        ctk.CTkEntry(row2, textvariable=self.enroll_image_path,
                     font=("Courier New", 10), width=220,
                     state="readonly").pack(side="left", padx=8)
        ctk.CTkButton(row2, text="Parcourir", width=90,
                      command=self._browse_enroll).pack(side="left")

        self.enroll_preview = ctk.CTkLabel(tab, text="Aperçu",
                                           width=180, height=200,
                                           fg_color="#16213e", corner_radius=8)
        self.enroll_preview.pack(pady=8)

        ctk.CTkButton(tab, text="✅  ENRÔLER CET UTILISATEUR",
                      font=("Courier New", 12, "bold"),
                      fg_color=GREEN, text_color="#1a1a2e", hover_color="#3ab88a",
                      command=self._do_enroll).pack(pady=6)

        self.enroll_result = ctk.CTkLabel(tab, text="",
                                          font=("Courier New", 11, "bold"),
                                          wraplength=500)
        self.enroll_result.pack(pady=4)

    # ── Auth Tab ──────────────────────────────────────────
    def _build_auth_tab(self, tab):
        ctk.CTkLabel(tab, text="Vérifier l'identité par empreinte",
                     font=("Courier New", 13, "bold"),
                     text_color=GREEN).pack(pady=(15, 3))
        ctk.CTkLabel(tab,
                     text="Chargez une image — le système identifie automatiquement l'utilisateur.",
                     font=("Courier New", 10), text_color=DIM).pack(pady=(0, 12))

        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.pack(fill="x", padx=30, pady=4)
        ctk.CTkLabel(row, text="Image :", width=80,
                     font=("Courier New", 11)).pack(side="left")
        ctk.CTkEntry(row, textvariable=self.auth_image_path,
                     font=("Courier New", 10), width=220,
                     state="readonly").pack(side="left", padx=8)
        ctk.CTkButton(row, text="Parcourir", width=90,
                      command=self._browse_auth).pack(side="left")

        self.auth_preview = ctk.CTkLabel(tab, text="Aperçu",
                                         width=180, height=200,
                                         fg_color="#16213e", corner_radius=8)
        self.auth_preview.pack(pady=8)

        ctk.CTkButton(tab, text="🔍  AUTHENTIFIER",
                      font=("Courier New", 12, "bold"),
                      fg_color=GREEN, text_color="#1a1a2e", hover_color="#3ab88a",
                      command=self._do_auth).pack(pady=6)

        # Result card
        self.auth_card = ctk.CTkFrame(tab, fg_color="#16213e", corner_radius=10)
        self.auth_card.pack(fill="x", padx=30, pady=(6, 4))

        self.auth_status = ctk.CTkLabel(self.auth_card, text="",
                                        font=("Courier New", 18, "bold"))
        self.auth_status.pack(pady=(12, 4))

        self.auth_user = ctk.CTkLabel(self.auth_card, text="",
                                      font=("Courier New", 14, "bold"),
                                      text_color=GREEN)
        self.auth_user.pack(pady=(0, 4))

        self.auth_detail = ctk.CTkLabel(self.auth_card, text="",
                                        font=("Courier New", 10),
                                        text_color=DIM, wraplength=680,
                                        justify="center")
        self.auth_detail.pack(pady=(0, 12))

    # ── Status Bar ────────────────────────────────────────
    def _build_status_bar(self):
        bar = ctk.CTkFrame(self, corner_radius=0, fg_color="#0f3460", height=28)
        bar.pack(fill="x", side="bottom")
        self.status_var = ctk.StringVar()
        ctk.CTkLabel(bar, textvariable=self.status_var,
                     font=("Courier New", 9), text_color=DIM).pack(pady=4)
        self._update_status()

    def _update_status(self):
        n = len(self.db.list_users())
        self.status_var.set(
            f"Base : {n} utilisateur(s)  |  Seuil : {DEFAULT_THRESHOLD}  |  Chiffrement : AES-256 ✓"
        )

    # ── Browse ────────────────────────────────────────────
    def _browse_enroll(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.bmp *.png *.jpg *.tif"), ("Tous", "*.*")]
        )
        if path:
            self.enroll_image_path.set(path)
            self._show_preview(path, self.enroll_preview)

    def _browse_auth(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.bmp *.png *.jpg *.tif"), ("Tous", "*.*")]
        )
        if path:
            self.auth_image_path.set(path)
            self._show_preview(path, self.auth_preview)
            self.auth_status.configure(text="")
            self.auth_user.configure(text="")
            self.auth_detail.configure(text="")

    # ── Enroll Action ─────────────────────────────────────
    def _do_enroll(self):
        name = self.enroll_name.get().strip()
        path = self.enroll_image_path.get().strip()
        if not name:
            self.enroll_result.configure(text="⚠  Entrez un nom", text_color=YELLOW)
            return
        if not path or not os.path.exists(path):
            self.enroll_result.configure(text="⚠  Sélectionnez une image valide", text_color=YELLOW)
            return

        self.enroll_result.configure(text="⏳  Traitement...", text_color=DIM)

        def run():
            template = generate_template(path)
            if template is None:
                self.enroll_result.configure(text="✗  Extraction échouée", text_color=RED)
                return
            fname  = os.path.basename(path)
            parts  = fname.replace(".BMP", "").replace(".bmp", "").split("__")
            finger = "unknown"
            if len(parts) > 1:
                d = parts[1].split("_")
                if len(d) >= 3:
                    finger = f"{d[1]}_{d[2]}"
            ok, status = self.db.enroll_user(name, template, finger)
            if ok:
                msg = (f"✓  '{name}' enrôlé — AES-256 ✓" if status == "created"
                       else f"🔄  '{name}' mis à jour — nouveau template enregistré")
                self.enroll_result.configure(text=msg, text_color=GREEN)
                self._update_status()
                self.enroll_name.set("")
                self.enroll_image_path.set("")
                self.enroll_preview.configure(image=None, text="Aperçu")
            else:
                self.enroll_result.configure(text=f"✗  Échec pour '{name}'", text_color=RED)

        threading.Thread(target=run, daemon=True).start()

    # ── Auth Action ───────────────────────────────────────
    def _do_auth(self):
        path = self.auth_image_path.get().strip()
        if not path or not os.path.exists(path):
            self.auth_status.configure(text="⚠  Sélectionnez une image", text_color=YELLOW)
            return

        self.auth_status.configure(text="⏳  Analyse...", text_color=DIM)
        self.auth_detail.configure(text="")

        def run():
            template = generate_template(path)
            if template is None:
                self.auth_status.configure(text="✗  Extraction échouée", text_color=RED)
                return
            result = identify(template, self.db, DEFAULT_THRESHOLD)
            if result["accepted"]:
                self.auth_status.configure(text="✓  ACCÈS AUTORISÉ", text_color=GREEN)
                self.auth_user.configure(text=f"👤  {result['name']}")
                self.auth_detail.configure(
                    text=(f"Score : {result['score']:.4f}  |  Gap : {result['gap']:.4f}  |  Seuil : {result['threshold']}\n"
                          f"Euclidienne : {result['euclidean']:.4f}  |  Cosinus : {result['cosine']:.4f}"),
                    text_color=DIM)
            else:
                self.auth_status.configure(text="✗  ACCÈS REFUSÉ", text_color=RED)
                self.auth_user.configure(text="Utilisateur inconnu", text_color=RED)
                self.auth_detail.configure(
                    text=(f"Aucune correspondance confiante trouvée.\n"
                          f"Meilleur score : {result['score']:.4f}  |  Gap : {result['gap']:.4f}  |  Seuil : {result['threshold']}"),
                    text_color=DIM)

        threading.Thread(target=run, daemon=True).start()

    # ── Preview ───────────────────────────────────────────
    def _show_preview(self, path, widget):
        try:
            img = Image.open(path).convert("L").resize((180, 200))
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(180, 200))
            widget.configure(image=ctk_img, text="")
            widget.image = ctk_img
        except Exception:
            widget.configure(image=None, text="Aperçu\nindisponible")

    def on_close(self):
        self.db.close()
        self.destroy()


if __name__ == "__main__":
    app = SecurePrintApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
