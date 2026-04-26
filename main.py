"""
main.py — Point d'entrée SecurePrint

Usage:
    python main.py              → Lance l'interface graphique
    python main.py enroll       → Enrôle toutes les images de data/real/
    python main.py evaluate     → Évalue FAR/FRR sur data/pairs.json
    python main.py gui          → Lance l'interface graphique (explicite)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Fix Tcl/Tk paths BEFORE any tkinter import
# Works from venv by walking up to find the base Python tcl/ folder
_base = os.path.dirname(sys.executable)
for _ in range(4):  # walk up max 4 levels
    _tcl_dir = os.path.join(_base, 'tcl')
    if os.path.isdir(_tcl_dir):
        for _name in os.listdir(_tcl_dir):
            _full = os.path.join(_tcl_dir, _name)
            if _name.startswith('tcl8') and os.path.isdir(_full):
                os.environ['TCL_LIBRARY'] = _full
            elif _name.startswith('tk8') and os.path.isdir(_full):
                os.environ['TK_LIBRARY'] = _full
        break
    _base = os.path.dirname(_base)


def run_gui():
    from ui.main_window import SecurePrintApp
    app = SecurePrintApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


def run_enroll():
    from modules.storage import SecurePrintDB
    from modules.matcher import enroll_all
    db = SecurePrintDB()
    enroll_all(db)
    db.close()


def run_evaluate():
    from modules.storage import SecurePrintDB
    from modules.matcher import enroll_all, evaluate, DEFAULT_THRESHOLD
    pairs_path = os.path.join(os.path.dirname(__file__), "data", "pairs.json")
    if not os.path.exists(pairs_path):
        print("[ERREUR] data/pairs.json introuvable — lancez setup_dataset.py d'abord")
        sys.exit(1)
    db = SecurePrintDB()
    enroll_all(db)
    evaluate(pairs_path, db, DEFAULT_THRESHOLD)
    db.close()


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "gui"

    if command == "enroll":
        run_enroll()
    elif command == "evaluate":
        run_evaluate()
    elif command in ("gui", ):
        run_gui()
    else:
        print(f"[ERREUR] Commande inconnue : '{command}'")
        print("Usage: python main.py [gui|enroll|evaluate]")
        sys.exit(1)
