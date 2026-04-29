"""
Utilitaire : Setup dataset FVC2000
Fichier : setup_dataset.py

Structure FVC2000 DB1_B :
    DB1_B/
        101_1.tif  ← finger 101, impression 1 (enrollment)
        101_2.tif  ← finger 101, impression 2 (testing)
        ...
        101_8.tif
        102_1.tif
        ...

Structure finale de data/ :
    data/
    ├── real/          ← impression _1 de chaque doigt (enrollment)
    ├── altered/       ← impressions _2 à _8 (testing)
    └── pairs.json     ← paires pour évaluation FAR/FRR

Lancer depuis secureprint/ :
    python setup_dataset.py "C:\\Users\\alhab\\Downloads\\DB1_B"
"""

import os
import shutil
import json
import sys

FVC2000_ROOT = r"C:\Users\alhab\Downloads\DB1_B"
OUTPUT_DIR   = "data"


def setup(fvc_root=None):
    root = fvc_root or FVC2000_ROOT

    if not os.path.exists(root):
        print(f"[ERREUR] Dossier introuvable : {root}")
        return False

    all_tifs = sorted([f for f in os.listdir(root) if f.lower().endswith('.tif')])
    if not all_tifs:
        print(f"[ERREUR] Aucun fichier .tif trouvé dans : {root}")
        return False

    print(f"\n{'='*55}")
    print("  SETUP DATASET FVC2000")
    print(f"{'='*55}\n")
    print(f"[OK] Dossier FVC2000 : {root}")
    print(f"[OK] {len(all_tifs)} images trouvées\n")

    # Group by finger_id
    fingers = {}
    for f in all_tifs:
        name = os.path.splitext(f)[0]       # e.g. "101_1"
        parts = name.split("_")
        if len(parts) != 2:
            continue
        finger_id, impression = parts[0], int(parts[1])
        if finger_id not in fingers:
            fingers[finger_id] = {}
        fingers[finger_id][impression] = f

    print(f"[INFO] {len(fingers)} doigts détectés : {sorted(fingers.keys())}\n")

    # Prepare output dirs
    real_out    = os.path.join(OUTPUT_DIR, "real")
    altered_out = os.path.join(OUTPUT_DIR, "altered")
    for d in [real_out, altered_out]:
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d)

    same_pairs  = []
    diff_pairs  = []
    copied_real = 0
    copied_alt  = 0

    finger_ids = sorted(fingers.keys())

    for finger_id in finger_ids:
        impressions = fingers[finger_id]

        if 1 not in impressions:
            print(f"[WARN] Impression 1 manquante pour doigt {finger_id}, ignoré")
            continue

        # Enrollment: impression 1 → data/real/
        src = os.path.join(root, impressions[1])
        dst = os.path.join(real_out, impressions[1])
        shutil.copy2(src, dst)
        copied_real += 1

        # Testing: impressions 2–8 → data/altered/
        for imp in range(2, 9):
            if imp not in impressions:
                continue
            src = os.path.join(root, impressions[imp])
            dst = os.path.join(altered_out, impressions[imp])
            shutil.copy2(src, dst)
            copied_alt += 1

            same_pairs.append({
                "type"    : "same_finger",
                "real"    : os.path.join("real",    impressions[1]),
                "altered" : os.path.join("altered", impressions[imp]),
                "person"  : finger_id,
                "finger"  : finger_id,
            })

    # Different-finger pairs: cross every finger's _1 with every other finger's _1
    for i, fid1 in enumerate(finger_ids):
        for fid2 in finger_ids[i+1:]:
            if 1 not in fingers[fid1] or 1 not in fingers[fid2]:
                continue
            diff_pairs.append({
                "type"  : "different_finger",
                "file1" : os.path.join("real", fingers[fid1][1]),
                "file2" : os.path.join("real", fingers[fid2][1]),
            })

    pairs_data = {
        "same_finger_pairs"      : same_pairs,
        "different_finger_pairs" : diff_pairs,
        "total_real"             : copied_real,
        "total_altered"          : copied_alt,
        "persons"                : len(finger_ids),
    }
    with open(os.path.join(OUTPUT_DIR, "pairs.json"), "w") as f:
        json.dump(pairs_data, f, indent=2)

    print(f"{'='*55}")
    print(f"  DATASET PRÊT ✓")
    print(f"{'='*55}")
    print(f"  data/real/              → {copied_real} images (enrollment)")
    print(f"  data/altered/           → {copied_alt} images (testing)")
    print(f"  Paires same finger      : {len(same_pairs)}")
    print(f"  Paires different finger : {len(diff_pairs)}")
    print(f"  Doigts                  : {len(finger_ids)}")
    print(f"  Fichier paires          : data/pairs.json")
    print(f"{'='*55}\n")
    return True


if __name__ == "__main__":
    path_arg = sys.argv[1] if len(sys.argv) > 1 else None
    if not setup(path_arg):
        sys.exit(1)
