"""
Module 3 : Génération de Template
Fichier : modules/template.py

Rôle : Convertir les minutiae brutes en un vecteur de caractéristiques
       fixe, normalisé et stable — prêt pour stockage et comparaison.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
from modules.preprocessor import preprocess
from modules.minutiae import extract_minutiae, filter_minutiae

# Taille fixe du vecteur final (indépendant du nombre de minutiae détectées)
TEMPLATE_SIZE = 64  # must be multiple of 4 now: (x, y, type, angle) x 16


def normalize_minutiae(minutiae, image_shape):
    """
    Normalise les coordonnées et l'angle des minutiae.

    Returns:
        list: Liste de (x_norm, y_norm, type_val, angle_norm)
              angle_norm : angle / 360 → [0, 1]
    """
    h, w = image_shape
    normalized = []
    for m in minutiae:
        x, y, mtype = m[0], m[1], m[2]
        angle = m[3] if len(m) > 3 else 0.0
        x_norm     = x / w
        y_norm     = y / h
        type_val   = 0.0 if mtype == 'ending' else 1.0
        angle_norm = angle / 360.0
        normalized.append((x_norm, y_norm, type_val, angle_norm))
    return normalized


def build_feature_vector(minutiae_normalized, template_size=TEMPLATE_SIZE):
    # 4 values per minutia: (x, y, type, angle) → template_size // 4 minutiae
    max_minutiae = template_size // 4
    sorted_m = sorted(minutiae_normalized, key=lambda m: (m[0], m[1]))
    sorted_m = sorted_m[:max_minutiae]
    flat = []
    for m in sorted_m:
        flat.extend([m[0], m[1], m[2], m[3]])
    while len(flat) < template_size:
        flat.append(0.0)
    return np.array(flat, dtype=np.float32)


def compute_pairwise_distances(minutiae_normalized, max_pairs=21):
    """
    Calcule les distances entre toutes les paires de minutiae.
    Ces distances sont invariantes à la translation et rotation légère.

    Args:
        minutiae_normalized (list): Minutiae normalisées
        max_pairs (int): Nombre max de paires à garder

    Returns:
        numpy.ndarray: Vecteur de distances
    """
    distances = []
    points = [(m[0], m[1]) for m in minutiae_normalized]

    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            d = np.sqrt((points[i][0] - points[j][0])**2 +
                        (points[i][1] - points[j][1])**2)
            distances.append(d)

    # Trier et garder les max_pairs premières distances
    distances.sort()
    distances = distances[:max_pairs]

    # Padding si pas assez de paires
    while len(distances) < max_pairs:
        distances.append(0.0)

    return np.array(distances, dtype=np.float32)


def generate_template(image_path):
    """
    Pipeline complet : image → template final.

    Le template final combine :
    - Le vecteur de positions normalisées (64 valeurs)
    - Le vecteur de distances entre paires (21 valeurs)
    Total : 85 valeurs — vecteur stable et discriminant

    Args:
        image_path (str): Chemin vers l'image d'empreinte

    Returns:
        numpy.ndarray: Template de taille fixe (85,), ou None si erreur
    """
    print(f"\n{'='*50}")
    print(f"  GÉNÉRATION DU TEMPLATE")
    print(f"  Image : {os.path.basename(image_path)}")
    print(f"{'='*50}")

    # Étape 1 : Prétraitement
    original, normalized, binary, skeleton = preprocess(image_path)
    if skeleton is None:
        return None

    # Étape 2 : Extraction des minutiae
    minutiae_raw = extract_minutiae(skeleton)
    minutiae_clean = filter_minutiae(minutiae_raw, min_distance=8)

    if len(minutiae_clean) < 5:
        print(f"[ATTENTION] Seulement {len(minutiae_clean)} minutiae — qualité insuffisante")
        return None

    # Étape 3 : Normalisation
    minutiae_norm = normalize_minutiae(minutiae_clean, skeleton.shape)

    # Étape 4 : Vecteur de positions
    position_vector = build_feature_vector(minutiae_norm, TEMPLATE_SIZE)

    # Étape 5 : Vecteur de distances (plus robuste aux petites variations)
    distance_vector = compute_pairwise_distances(minutiae_norm)

    # Étape 6 : Concaténation → template final
    template = np.concatenate([position_vector, distance_vector])

    print(f"[OK] Template généré — taille : {template.shape[0]} valeurs")
    print(f"     → Positions+Angles : {len(position_vector)} valeurs")
    print(f"     → Distances        : {len(distance_vector)} valeurs")
    print(f"     → Min: {template.min():.4f} | Max: {template.max():.4f} | Moy: {template.mean():.4f}")
    print(f"{'='*50}\n")

    return template


# ─────────────────────────────────────────────
#  TEST RAPIDE — compare 2 images
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import os

    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    data_dir = os.path.join(root_dir, "data", "real")

    images = sorted([
        os.path.join(data_dir, f)
        for f in os.listdir(data_dir)
        if f.lower().endswith(('.bmp', '.png', '.jpg', '.tif'))
    ])

    if len(images) < 2:
        print("[ERREUR] Il faut au moins 2 images dans data/ pour tester")
        sys.exit(1)

    print("=== TEST : Génération de 2 templates ===\n")

    # Générer les templates pour les 2 premières images
    t1 = generate_template(images[0])
    t2 = generate_template(images[1])

    if t1 is not None and t2 is not None:
        # Calculer la similarité entre les deux templates
        distance = np.linalg.norm(t1 - t2)
        dot = np.dot(t1, t2) / (np.linalg.norm(t1) * np.linalg.norm(t2))
        cosine_dist = 1 - dot

        print("=== RÉSULTAT DE COMPARAISON ===")
        print(f"  Image 1 : {os.path.basename(images[0])}")
        print(f"  Image 2 : {os.path.basename(images[1])}")
        print(f"  Distance Euclidienne : {distance:.4f}")
        print(f"  Distance Cosinus     : {cosine_dist:.4f}")
        print(f"  (Plus la distance est faible, plus les empreintes sont similaires)")