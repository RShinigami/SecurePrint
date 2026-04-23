"""
Module 7 : Interface Utilisateur
Fichier : ui/main_window.py

Rôle : Interface graphique Tkinter pour :
    - Enrôler un nouvel utilisateur (onglet 1)
    - Authentifier un utilisateur (onglet 2)

Lancer depuis secureprint/ :
    python ui/main_window.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ['TCL_LIBRARY'] = r'C:\Users\alhab\AppData\Local\Programs\Python\Python313\tcl\tcl8.6'
os.environ['TK_LIBRARY']  = r'C:\Users\alhab\AppData\Local\Programs\Python\Python313\tcl\tk8.6'


import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import threading

from modules.template import generate_template
from modules.storage  import SecurePrintDB
from modules.matcher  import identify, DEFAULT_THRESHOLD

# ─────────────────────────────────────────────
#  COULEURS & STYLE
# ─────────────────────────────────────────────
BG          = "#1a1a2e"   # fond principal (bleu nuit)
BG2         = "#16213e"   # fond secondaire
ACCENT      = "#0f3460"   # bleu foncé
GREEN       = "#4ecca3"   # vert menthe (succès)
RED         = "#e94560"   # rouge vif (échec)
YELLOW      = "#f5a623"   # orange (avertissement)
TEXT        = "#eaeaea"   # texte principal
TEXT_DIM    = "#7a7a9a"   # texte secondaire
FONT_TITLE  = ("Courier New", 18, "bold")
FONT_LABEL  = ("Courier New", 10)
FONT_SMALL  = ("Courier New", 9)
FONT_RESULT = ("Courier New", 13, "bold")


class SecurePrintApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("SecurePrint — Authentification Biométrique")
        self.geometry("700x580")
        self.resizable(False, False)
        self.configure(bg=BG)

        # Base de données
        self.db = SecurePrintDB()

        # Variables partagées
        self.enroll_image_path   = tk.StringVar()
        self.auth_image_path     = tk.StringVar()
        self.enroll_name         = tk.StringVar()

        self._build_header()
        self._build_tabs()
        self._build_status_bar()

    # ─────────────────────────────────────────
    #  HEADER
    # ─────────────────────────────────────────
    def _build_header(self):
        header = tk.Frame(self, bg=ACCENT, pady=12)
        header.pack(fill="x")

        tk.Label(
            header, text="🔒 SECUREPRINT",
            font=FONT_TITLE, bg=ACCENT, fg=GREEN
        ).pack()

        tk.Label(
            header, text="Système d'authentification biométrique par empreinte digitale",
            font=FONT_SMALL, bg=ACCENT, fg=TEXT_DIM
        ).pack()

    # ─────────────────────────────────────────
    #  TABS
    # ─────────────────────────────────────────
    def _build_tabs(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook",
                         background=BG, borderwidth=0)
        style.configure("TNotebook.Tab",
                         background=BG2, foreground=TEXT_DIM,
                         font=("Courier New", 10, "bold"),
                         padding=[20, 8])
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", GREEN)])

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # ── Tab 1 : Enrôlement ──
        self.tab_enroll = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(self.tab_enroll, text="  📋 ENRÔLEMENT  ")
        self._build_enroll_tab()

        # ── Tab 2 : Authentification ──
        self.tab_auth = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(self.tab_auth, text="  🔍 AUTHENTIFICATION  ")
        self._build_auth_tab()

    # ─────────────────────────────────────────
    #  ONGLET ENRÔLEMENT
    # ─────────────────────────────────────────
    def _build_enroll_tab(self):
        pad = {"padx": 30, "pady": 6}

        # Titre
        tk.Label(self.tab_enroll,
                 text="Enregistrer un nouvel utilisateur",
                 font=("Courier New", 12, "bold"),
                 bg=BG, fg=GREEN).pack(pady=(20, 5))

        tk.Label(self.tab_enroll,
                 text="Le template biométrique sera chiffré (AES-256) avant stockage.\nAucune image n'est conservée.",
                 font=FONT_SMALL, bg=BG, fg=TEXT_DIM,
                 justify="center").pack(pady=(0, 15))

        # Séparateur
        tk.Frame(self.tab_enroll, bg=ACCENT, height=1).pack(fill="x", **pad)

        # Nom utilisateur
        row1 = tk.Frame(self.tab_enroll, bg=BG)
        row1.pack(fill="x", **pad)
        tk.Label(row1, text="Nom :", font=FONT_LABEL,
                 bg=BG, fg=TEXT, width=14, anchor="w").pack(side="left")
        tk.Entry(row1, textvariable=self.enroll_name,
                 font=FONT_LABEL, bg=BG2, fg=TEXT,
                 insertbackground=GREEN, relief="flat",
                 bd=5, width=30).pack(side="left", padx=5)

        # Sélection image
        row2 = tk.Frame(self.tab_enroll, bg=BG)
        row2.pack(fill="x", **pad)
        tk.Label(row2, text="Image :", font=FONT_LABEL,
                 bg=BG, fg=TEXT, width=14, anchor="w").pack(side="left")
        tk.Entry(row2, textvariable=self.enroll_image_path,
                 font=FONT_SMALL, bg=BG2, fg=TEXT_DIM,
                 relief="flat", bd=5, width=30,
                 state="readonly").pack(side="left", padx=5)
        tk.Button(row2, text="Parcourir",
                  font=FONT_SMALL, bg=ACCENT, fg=GREEN,
                  relief="flat", cursor="hand2",
                  command=self._browse_enroll).pack(side="left", padx=5)

        # Prévisualisation
        self.enroll_preview = tk.Label(self.tab_enroll,
                                       bg=BG2, width=20, height=10,
                                       text="Aperçu", fg=TEXT_DIM,
                                       font=FONT_SMALL, relief="flat")
        self.enroll_preview.pack(pady=10)

        # Bouton enrôler
        tk.Button(self.tab_enroll,
                  text="  ✅  ENRÔLER CET UTILISATEUR  ",
                  font=("Courier New", 11, "bold"),
                  bg=GREEN, fg=BG,
                  relief="flat", cursor="hand2",
                  padx=10, pady=8,
                  command=self._do_enroll).pack(pady=10)

        # Zone résultat
        self.enroll_result = tk.Label(self.tab_enroll,
                                      text="", font=FONT_RESULT,
                                      bg=BG, fg=TEXT)
        self.enroll_result.pack(pady=5)

    # ─────────────────────────────────────────
    #  ONGLET AUTHENTIFICATION
    # ─────────────────────────────────────────
    def _build_auth_tab(self):
        pad = {"padx": 30, "pady": 6}

        tk.Label(self.tab_auth,
                 text="Vérifier l'identité par empreinte",
                 font=("Courier New", 12, "bold"),
                 bg=BG, fg=GREEN).pack(pady=(20, 5))

        tk.Label(self.tab_auth,
                 text="Chargez une image d'empreinte — le système identifie\nautomatiquement l'utilisateur dans la base.",
                 font=FONT_SMALL, bg=BG, fg=TEXT_DIM,
                 justify="center").pack(pady=(0, 15))

        tk.Frame(self.tab_auth, bg=ACCENT, height=1).pack(fill="x", **pad)

        # Sélection image
        row = tk.Frame(self.tab_auth, bg=BG)
        row.pack(fill="x", **pad)
        tk.Label(row, text="Image :", font=FONT_LABEL,
                 bg=BG, fg=TEXT, width=14, anchor="w").pack(side="left")
        tk.Entry(row, textvariable=self.auth_image_path,
                 font=FONT_SMALL, bg=BG2, fg=TEXT_DIM,
                 relief="flat", bd=5, width=30,
                 state="readonly").pack(side="left", padx=5)
        tk.Button(row, text="Parcourir",
                  font=FONT_SMALL, bg=ACCENT, fg=GREEN,
                  relief="flat", cursor="hand2",
                  command=self._browse_auth).pack(side="left", padx=5)

        # Prévisualisation
        self.auth_preview = tk.Label(self.tab_auth,
                                     bg=BG2, width=20, height=10,
                                     text="Aperçu", fg=TEXT_DIM,
                                     font=FONT_SMALL, relief="flat")
        self.auth_preview.pack(pady=10)

        # Bouton authentifier
        tk.Button(self.tab_auth,
                  text="  🔍  AUTHENTIFIER  ",
                  font=("Courier New", 11, "bold"),
                  bg=GREEN, fg=BG,
                  relief="flat", cursor="hand2",
                  padx=10, pady=8,
                  command=self._do_auth).pack(pady=10)

        # Zone résultat — grande carte
        self.auth_result_frame = tk.Frame(self.tab_auth, bg=BG2,
                                          relief="flat", bd=0)
        self.auth_result_frame.pack(fill="x", padx=30, pady=5)

        self.auth_status  = tk.Label(self.auth_result_frame,
                                     text="", font=("Courier New", 16, "bold"),
                                     bg=BG2, fg=TEXT)
        self.auth_status.pack(pady=(10, 2))

        self.auth_detail  = tk.Label(self.auth_result_frame,
                                     text="", font=FONT_LABEL,
                                     bg=BG2, fg=TEXT_DIM,
                                     justify="center")
        self.auth_detail.pack(pady=(0, 10))

    # ─────────────────────────────────────────
    #  STATUS BAR
    # ─────────────────────────────────────────
    def _build_status_bar(self):
        bar = tk.Frame(self, bg=ACCENT, pady=4)
        bar.pack(fill="x", side="bottom")

        users = self.db.list_users()
        self.status_var = tk.StringVar(
            value=f"Base de données : {len(users)} utilisateur(s) enrôlé(s)  |  Seuil : {DEFAULT_THRESHOLD}  |  Chiffrement : AES-256 ✓"
        )
        tk.Label(bar, textvariable=self.status_var,
                 font=FONT_SMALL, bg=ACCENT, fg=TEXT_DIM).pack()

    def _update_status(self):
        users = self.db.list_users()
        self.status_var.set(
            f"Base de données : {len(users)} utilisateur(s) enrôlé(s)  |  Seuil : {DEFAULT_THRESHOLD}  |  Chiffrement : AES-256 ✓"
        )

    # ─────────────────────────────────────────
    #  ACTIONS — ENRÔLEMENT
    # ─────────────────────────────────────────
    def _browse_enroll(self):
        path = filedialog.askopenfilename(
            title="Sélectionner une image d'empreinte",
            filetypes=[("Images", "*.bmp *.png *.jpg *.tif"), ("Tous", "*.*")]
        )
        if path:
            self.enroll_image_path.set(path)
            self._show_preview(path, self.enroll_preview)

    def _do_enroll(self):
        name  = self.enroll_name.get().strip()
        path  = self.enroll_image_path.get().strip()

        if not name:
            self.enroll_result.config(text="⚠  Entrez un nom d'utilisateur", fg=YELLOW)
            return
        if not path or not os.path.exists(path):
            self.enroll_result.config(text="⚠  Sélectionnez une image valide", fg=YELLOW)
            return

        self.enroll_result.config(text="⏳  Traitement en cours...", fg=TEXT_DIM)
        self.update()

        def run():
            template = generate_template(path)
            if template is None:
                self.enroll_result.config(
                    text="✗  Impossible d'extraire les minutiae\n   (image trop petite ou mauvaise qualité)",
                    fg=RED)
                return

            fname  = os.path.basename(path)
            parts  = fname.replace(".BMP","").replace(".bmp","").split("__")
            finger = "unknown"
            if len(parts) > 1:
                d = parts[1].split("_")
                if len(d) >= 3:
                    finger = f"{d[1]}_{d[2]}"

            success = self.db.enroll_user(name, template, finger)
            if success:
                self.enroll_result.config(
                    text=f"✓  '{name}' enrôlé avec succès !\n   Template chiffré AES-256 — aucune image conservée.",
                    fg=GREEN)
                self._update_status()
                self.enroll_name.set("")
                self.enroll_image_path.set("")
                self.enroll_preview.config(image="", text="Aperçu")
            else:
                self.enroll_result.config(
                    text=f"✗  Échec de l'enrôlement pour '{name}'", fg=RED)

        threading.Thread(target=run, daemon=True).start()

    # ─────────────────────────────────────────
    #  ACTIONS — AUTHENTIFICATION
    # ─────────────────────────────────────────
    def _browse_auth(self):
        path = filedialog.askopenfilename(
            title="Sélectionner une image d'empreinte",
            filetypes=[("Images", "*.bmp *.png *.jpg *.tif"), ("Tous", "*.*")]
        )
        if path:
            self.auth_image_path.set(path)
            self._show_preview(path, self.auth_preview)
            # Reset résultats
            self.auth_status.config(text="")
            self.auth_detail.config(text="")

    def _do_auth(self):
        path = self.auth_image_path.get().strip()
        if not path or not os.path.exists(path):
            self.auth_status.config(text="⚠  Sélectionnez une image", fg=YELLOW)
            self.auth_detail.config(text="")
            return

        self.auth_status.config(text="⏳  Analyse en cours...", fg=TEXT_DIM)
        self.auth_detail.config(text="")
        self.update()

        def run():
            template = generate_template(path)
            if template is None:
                self.auth_status.config(text="✗  Extraction échouée", fg=RED)
                self.auth_detail.config(
                    text="Image de mauvaise qualité ou trop petite.", fg=TEXT_DIM)
                return

            result = identify(template, self.db, DEFAULT_THRESHOLD)

            if result["accepted"]:
                self.auth_status.config(text="✓  ACCÈS AUTORISÉ", fg=GREEN)
                self.auth_detail.config(
                    text=(
                        f"Utilisateur identifié : {result['name']}\n"
                        f"Score de similarité  : {result['score']:.4f}  (seuil : {result['threshold']})\n"
                        f"Distance euclidienne : {result['euclidean']:.4f}  |  Cosinus : {result['cosine']:.4f}"
                    ),
                    fg=TEXT_DIM)
            else:
                self.auth_status.config(text="✗  ACCÈS REFUSÉ", fg=RED)
                self.auth_detail.config(
                    text=(
                        f"Aucune correspondance trouvée dans la base.\n"
                        f"Meilleur score : {result['score']:.4f}  (seuil : {result['threshold']})\n"
                        f"L'empreinte ne correspond à aucun utilisateur enrôlé."
                    ),
                    fg=TEXT_DIM)

        threading.Thread(target=run, daemon=True).start()

    # ─────────────────────────────────────────
    #  UTILITAIRE : PRÉVISUALISATION IMAGE
    # ─────────────────────────────────────────
    def _show_preview(self, path, label_widget):
        try:
            img = Image.open(path).convert("L")
            img = img.resize((180, 200), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            label_widget.config(image=photo, text="")
            label_widget.image = photo
        except Exception:
            label_widget.config(image="", text="Aperçu\nindisponible")

    def on_close(self):
        self.db.close()
        self.destroy()


# ─────────────────────────────────────────────
#  POINT D'ENTRÉE
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = SecurePrintApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()