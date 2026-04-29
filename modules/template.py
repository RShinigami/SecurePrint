"""
Module 3 : Generation de Template
Fichier : modules/template.py

Conforme au cahier des charges :
  - Normalisation par centre de masse (translation invariance)
  - Vecteur de distances entre paires de minutiae (non-inversible)
  - Taille fixe independante du nombre de minutiae detectees

Feature vector (3 parties) :
  1. Distances paires ALL minutiae (N*(N-1)/2 valeurs) — geometrie globale
  2. Distances paires BIFURCATIONS seulement (discriminant par type)
  3. Carte de densite 4x4 separee par type (32 valeurs) — topologie locale

Adapte pour FVC2000 DB1_B (300x300px).
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
from modules.preprocessor import preprocess
from modules.minutiae import extract_minutiae, filter_minutiae

N_MINUTIAE = 48   # minutiae retenues (centroid-closest)
N_ALL      = (N_MINUTIAE * (N_MINUTIAE - 1)) // 2  # 1128 distances all
N_BIF      = 20   # bifurcations retenues separement
N_BIF_DIST = (N_BIF * (N_BIF - 1)) // 2            # 190 distances bifurcations
N_DENSITY  = 32   # 4x4 grid x 2 types


def normalize_minutiae(minutiae, image_shape):
    h, w = image_shape
    result = []
    for m in minutiae:
        x, y, mtype = m[0], m[1], m[2]
        angle = m[3] if len(m) > 3 else 0.0
        result.append((x / w, y / h, 0.0 if mtype == 'ending' else 1.0, angle / 360.0))
    return result


def select_by_centroid(minutiae_norm, n):
    """Selectionne les n minutiae les plus proches du centre de masse."""
    if len(minutiae_norm) <= n:
        return minutiae_norm[:]
    cx = np.mean([m[0] for m in minutiae_norm])
    cy = np.mean([m[1] for m in minutiae_norm])
    return sorted(minutiae_norm, key=lambda m: (m[0]-cx)**2 + (m[1]-cy)**2)[:n]


def pairwise_distances(points_norm):
    """Vecteur trie de distances euclidiennes entre toutes les paires, normalise dans [0,1]."""
    pts = points_norm
    n = len(pts)
    dists = []
    for i in range(n):
        for j in range(i + 1, n):
            dx = pts[i][0] - pts[j][0]
            dy = pts[i][1] - pts[j][1]
            dists.append(float(np.sqrt(dx*dx + dy*dy)))
    dists.sort()
    return dists


def density_map(minutiae_norm, grid=4):
    """
    Carte de densite spatiale grid x grid separee par type.
    Endings dans les premieres grid^2 cellules, bifurcations dans les suivantes.
    Normalise par le total de chaque type.
    """
    endings = np.zeros((grid, grid), dtype=np.float32)
    bifurcs = np.zeros((grid, grid), dtype=np.float32)
    for m in minutiae_norm:
        col = min(int(m[0] * grid), grid - 1)
        row = min(int(m[1] * grid), grid - 1)
        if m[2] == 0.0:
            endings[row, col] += 1.0
        else:
            bifurcs[row, col] += 1.0
    e_total = endings.sum()
    b_total = bifurcs.sum()
    if e_total > 0: endings /= e_total
    if b_total > 0: bifurcs /= b_total
    return np.concatenate([endings.flatten(), bifurcs.flatten()])


def generate_template(image_path):
    """
    Pipeline complet : image -> template.

    Template = concatenation de :
      - 1128 distances paires (48 minutiae proches du centroide)
      - 190  distances paires bifurcations (20 bifurcations proches du centroide)
      - 32   valeurs de densite spatiale 4x4 par type
    Total : 1350 valeurs, taille fixe, non-inversible.
    """
    print(f"\n{'='*50}")
    print(f"  GENERATION DU TEMPLATE")
    print(f"  Image : {os.path.basename(image_path)}")
    print(f"{'='*50}")

    original, normalized, binary, skeleton = preprocess(image_path)
    if skeleton is None:
        return None

    minutiae_raw   = extract_minutiae(skeleton)
    minutiae_clean = filter_minutiae(minutiae_raw, min_distance=8)

    if len(minutiae_clean) < N_MINUTIAE:
        print(f"[ATTENTION] {len(minutiae_clean)} minutiae < {N_MINUTIAE} requis")
        return None

    minutiae_norm = normalize_minutiae(minutiae_clean, skeleton.shape)

    # ── Partie 1 : distances toutes minutiae ──────────────
    selected_all  = select_by_centroid(minutiae_norm, N_MINUTIAE)
    dists_all     = pairwise_distances(selected_all)
    while len(dists_all) < N_ALL: dists_all.append(0.0)
    v_all = np.array(dists_all[:N_ALL], dtype=np.float32) / np.sqrt(2)

    # ── Partie 2 : distances bifurcations (+ endings si pas assez) ──
    bifurcs_only = [m for m in minutiae_norm if m[2] == 1.0]
    endings_only = [m for m in minutiae_norm if m[2] == 0.0]
    # Pad with endings if not enough bifurcations
    type_pool = bifurcs_only[:]
    if len(type_pool) < N_BIF:
        needed = N_BIF - len(type_pool)
        type_pool += select_by_centroid(endings_only, needed)
    selected_bif = select_by_centroid(type_pool, N_BIF)
    dists_bif = pairwise_distances(selected_bif)
    while len(dists_bif) < N_BIF_DIST: dists_bif.append(0.0)
    v_bif = np.array(dists_bif[:N_BIF_DIST], dtype=np.float32) / np.sqrt(2)

    # ── Partie 3 : carte de densite spatiale ──────────────
    v_density = density_map(minutiae_norm, grid=4)

    template = np.concatenate([v_all, v_bif, v_density])

    print(f"[OK] Template genere : {template.shape[0]} valeurs")
    print(f"     Minutiae : {len(minutiae_clean)} detectees | {N_MINUTIAE} retenues")
    print(f"     Parties  : {N_ALL} dist-all + {N_BIF_DIST} dist-bif + {N_DENSITY} densite")
    print(f"     Min: {template.min():.4f} | Max: {template.max():.4f} | Moy: {template.mean():.4f}")
    print(f"{'='*50}\n")

    return template


# ─────────────────────────────────────────────
#  TEST RAPIDE
# ─────────────────────────────────────────────
if __name__ == "__main__":
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    data_dir = os.path.join(root_dir, "data", "real")
    images = sorted([
        os.path.join(data_dir, f)
        for f in os.listdir(data_dir)
        if f.lower().endswith(('.bmp', '.png', '.jpg', '.tif'))
    ])
    if len(images) < 2:
        print("[ERREUR] Il faut au moins 2 images dans data/real/")
        sys.exit(1)
    t1 = generate_template(images[0])
    t2 = generate_template(images[1])
    if t1 is not None and t2 is not None:
        from modules.matcher import combined_score
        score = combined_score(t1, t2)
        print(f"  {os.path.basename(images[0])} vs {os.path.basename(images[1])}")
        print(f"  Score : {score:.4f}  (doigts differents — doit etre eleve)")
