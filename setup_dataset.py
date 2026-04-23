"""
Utilitaire : Setup complet du dataset SOCOFing
Fichier : setup_dataset.py

Structure finale de data/ :
    data/
    ├── real/          ← images originales (1 par doigt)
    ├── altered/       ← versions altérées des mêmes doigts
    └── pairs.json     ← liste des paires pour les tests

Lancer depuis secureprint/ :
    python setup_dataset.py "E:\\chemin\\vers\\SOCOFing"
"""

import os
import shutil
import random
import json
import sys

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
SOCOFING_ROOT  = r"C:\Users\alhab\Downloads\archive\SOCOFing"   # ← change si besoin
OUTPUT_DIR     = "data"
PERSONS_COUNT  = 25
RANDOM_SEED    = 42
# ─────────────────────────────────────────────


def parse_filename(filename):
    """
    Parse un nom de fichier SOCOFing.
    Formats supportés :
      Real    : 9__M_Left_index_finger.BMP
      Altered : 9__M_Left_index_finger_Obl.BMP
    """
    name = os.path.splitext(filename)[0]
    parts = name.split("__")
    if len(parts) != 2:
        return None
    try:
        person_id = int(parts[0])
        details   = parts[1].split("_")
        if len(details) < 4:
            return None
        return {
            "person_id"  : person_id,
            "gender"     : details[0],
            "hand"       : details[1],
            "finger"     : details[2],
            "alteration" : details[4] if len(details) > 4 else "Real",
            "finger_key" : f"{person_id}__{details[1]}_{details[2]}",
        }
    except Exception:
        return None


def find_folder(root, name):
    """Cherche un sous-dossier par nom dans root."""
    for dirpath, dirnames, _ in os.walk(root):
        for d in dirnames:
            if d.lower() == name.lower():
                return os.path.join(dirpath, d)
    return None


def load_folder(folder_path):
    """Charge tous les fichiers BMP d'un dossier avec leurs métadonnées."""
    files = {}
    if not os.path.exists(folder_path):
        return files
    for f in os.listdir(folder_path):
        if not f.lower().endswith('.bmp'):
            continue
        info = parse_filename(f)
        if info:
            key = info["finger_key"]
            if key not in files:
                files[key] = []
            files[key].append({
                "filename" : f,
                "path"     : os.path.join(folder_path, f),
                "info"     : info,
            })
    return files


def setup(socofing_root=None):
    root = socofing_root or SOCOFING_ROOT
    random.seed(RANDOM_SEED)

    print(f"\n{'='*55}")
    print("  SETUP DATASET COMPLET")
    print(f"{'='*55}\n")

    # ── Trouver les dossiers SOCOFing ──────────────────────
    real_dir         = find_folder(root, "Real")
    altered_easy_dir = find_folder(root, "Altered-Easy")
    altered_med_dir  = find_folder(root, "Altered-Medium")
    altered_hard_dir = find_folder(root, "Altered-Hard")

    if not real_dir:
        print(f"[ERREUR] Dossier Real introuvable dans : {root}")
        print("         Modifiez SOCOFING_ROOT dans ce script")
        return False

    print(f"[OK] Real         : {real_dir}")
    print(f"[OK] Altered-Easy : {altered_easy_dir or 'non trouvé'}")
    print(f"[OK] Altered-Med  : {altered_med_dir  or 'non trouvé'}")
    print(f"[OK] Altered-Hard : {altered_hard_dir or 'non trouvé'}")

    # ── Charger les fichiers ───────────────────────────────
    real_files         = load_folder(real_dir)
    altered_easy_files = load_folder(altered_easy_dir) if altered_easy_dir else {}
    altered_med_files  = load_folder(altered_med_dir)  if altered_med_dir  else {}
    altered_hard_files = load_folder(altered_hard_dir) if altered_hard_dir else {}

    print(f"\n[INFO] Doigts dans Real         : {len(real_files)}")
    print(f"[INFO] Doigts dans Altered-Easy : {len(altered_easy_files)}")
    print(f"[INFO] Doigts dans Altered-Med  : {len(altered_med_files)}")
    print(f"[INFO] Doigts dans Altered-Hard : {len(altered_hard_files)}")

    # ── Sélectionner des doigts présents dans Real ET Altered-Easy ─
    valid_keys = [k for k in real_files if k in altered_easy_files]
    random.shuffle(valid_keys)

    # Max PERSONS_COUNT personnes différentes
    selected_keys = []
    seen_persons  = set()
    for key in valid_keys:
        pid = int(key.split("__")[0])
        if pid not in seen_persons:
            selected_keys.append(key)
            seen_persons.add(pid)
        if len(seen_persons) >= PERSONS_COUNT:
            break

    print(f"\n[INFO] {len(selected_keys)} doigts sélectionnés ({len(seen_persons)} personnes)")

    # ── Préparer les dossiers de sortie ───────────────────
    real_out    = os.path.join(OUTPUT_DIR, "real")
    altered_out = os.path.join(OUTPUT_DIR, "altered")

    for d in [real_out, altered_out]:
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d)

    # ── Copier les fichiers ────────────────────────────────
    same_pairs  = []
    copied_real = 0
    copied_alt  = 0

    for key in selected_keys:
        # Image réelle
        real_entry = real_files[key][0]
        shutil.copy2(real_entry["path"], os.path.join(real_out, real_entry["filename"]))
        copied_real += 1

        # Image altérée (Easy prioritaire, sinon Medium, sinon Hard)
        altered_entry = None
        for alt_dict in [altered_easy_files, altered_med_files, altered_hard_files]:
            if key in alt_dict and alt_dict[key]:
                altered_entry = alt_dict[key][0]
                break

        if altered_entry:
            shutil.copy2(altered_entry["path"], os.path.join(altered_out, altered_entry["filename"]))
            copied_alt += 1
            same_pairs.append({
                "type"    : "same_finger",
                "real"    : os.path.join("real",    real_entry["filename"]),
                "altered" : os.path.join("altered", altered_entry["filename"]),
                "person"  : real_entry["info"]["person_id"],
                "finger"  : f"{real_entry['info']['hand']}_{real_entry['info']['finger']}",
            })

    # ── Générer des paires DIFFÉRENTS doigts ──────────────
    diff_pairs = []
    for i in range(len(selected_keys)):
        j = (i + 1) % len(selected_keys)
        k1 = selected_keys[i]
        k2 = selected_keys[j]
        pid1 = int(k1.split("__")[0])
        pid2 = int(k2.split("__")[0])
        if pid1 != pid2:
            diff_pairs.append({
                "type"  : "different_finger",
                "file1" : os.path.join("real", real_files[k1][0]["filename"]),
                "file2" : os.path.join("real", real_files[k2][0]["filename"]),
            })

    # ── Sauvegarder pairs.json ─────────────────────────────
    pairs_data = {
        "same_finger_pairs"      : same_pairs,
        "different_finger_pairs" : diff_pairs,
        "total_real"             : copied_real,
        "total_altered"          : copied_alt,
        "persons"                : len(seen_persons),
    }
    with open(os.path.join(OUTPUT_DIR, "pairs.json"), "w") as f:
        json.dump(pairs_data, f, indent=2)

    # ── Résumé ─────────────────────────────────────────────
    print(f"\n{'='*55}")
    print(f"  DATASET PRÊT ✓")
    print(f"{'='*55}")
    print(f"  data/real/              → {copied_real} images originales")
    print(f"  data/altered/           → {copied_alt} images altérées")
    print(f"  Paires same finger      : {len(same_pairs)}")
    print(f"  Paires different finger : {len(diff_pairs)}")
    print(f"  Personnes               : {len(seen_persons)}")
    print(f"  Fichier paires          : data/pairs.json")
    print(f"{'='*55}")
    print(f"\n  Utilisation dans le projet :")
    print(f"    data/real/    → enrôlement des utilisateurs")
    print(f"    data/altered/ → simulation d'authentification réelle")
    print(f"    data/pairs.json → évaluation FAR/FRR\n")
    return True


if __name__ == "__main__":
    path_arg = sys.argv[1] if len(sys.argv) > 1 else None
    success  = setup(path_arg)
    if not success:
        sys.exit(1)