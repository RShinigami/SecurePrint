"""
Module 2 : Extraction des Minutiae
Fichier : modules/minutiae.py

Rôle : Parcourir le squelette de l'empreinte et détecter les points
       caractéristiques (terminaisons et bifurcations) via le Crossing Number.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import cv2
import numpy as np
from modules.preprocessor import preprocess


def crossing_number(neighbors):
    """
    Calcule le Crossing Number d'un pixel à partir de ses 8 voisins.
    Les voisins sont listés dans le sens horaire autour du pixel central.

    CN = 1  → point isolé (ignoré)
    CN = 2  → point de continuation (crête normale, ignoré)
    CN = 1  → terminaison de crête  ← ce qu'on veut !
    CN = 3+ → bifurcation            ← ce qu'on veut !

    Args:
        neighbors (list): 8 valeurs binaires (0 ou 1) dans le sens horaire

    Returns:
        int: Valeur du Crossing Number
    """
    # Force convert to plain Python ints to avoid numpy uint8 overflow
    n = [int(x) for x in neighbors]
    n = n + [n[0]]  # boucle circulaire
    return sum(abs(n[i] - n[i+1]) for i in range(8)) // 2


def _compute_angle(skel, x, y, neighbors):
    """
    Estime l'angle de la minutie en degrees [0, 360)
    en calculant la direction vers le(s) voisin(s) actif(s).
    """
    # Offsets (dx, dy) pour chaque voisin dans l'ordre horaire
    offsets = [(-1,-1),(0,-1),(1,-1),(1,0),(1,1),(0,1),(-1,1),(-1,0)]
    angles = []
    for i, (dx, dy) in enumerate(offsets):
        if neighbors[i] == 1:
            angles.append(np.degrees(np.arctan2(-dy, dx)) % 360)
    if not angles:
        return 0.0
    # Mean angle via circular mean
    rad = [np.radians(a) for a in angles]
    return float(np.degrees(np.arctan2(np.mean(np.sin(rad)), np.mean(np.cos(rad)))) % 360)


def extract_minutiae(skeleton, border_margin=15):
    """
    Détecte toutes les minutiae dans une image squelettisée.

    Args:
        skeleton (numpy.ndarray): Image squelettisée (valeurs 0 ou 255)
        border_margin (int): Marge en pixels à ignorer sur les bords

    Returns:
        list: Liste de tuples (x, y, type, angle)
              type = 'ending' ou 'bifurcation'
              angle = direction en degrés [0, 360)
    """
    # Normalize: handle both bool (True/False) and uint8 (0/255) skeletons
    if skeleton.dtype == bool:
        skel = skeleton.astype(np.uint8)
    else:
        skel = (skeleton > 0).astype(np.uint8)
    


    minutiae = []
    rows, cols = skel.shape

    print("[INFO] Analyse du squelette en cours...")

    for y in range(border_margin, rows - border_margin):
        for x in range(border_margin, cols - border_margin):

            # On ne traite que les pixels de crête (valeur = 1)
            if skel[y, x] != 1:
                continue

            # Récupérer les 8 voisins dans le sens horaire
            # Ordre : haut-gauche, haut, haut-droite, droite,
            #         bas-droite, bas, bas-gauche, gauche
            neighbors = [
                skel[y-1, x-1], skel[y-1, x], skel[y-1, x+1],
                skel[y,   x+1],
                skel[y+1, x+1], skel[y+1, x], skel[y+1, x-1],
                skel[y,   x-1]
            ]

            cn = crossing_number(neighbors)

            if cn == 1:
                angle = _compute_angle(skel, x, y, neighbors)
                minutiae.append((x, y, 'ending', angle))
            elif cn >= 3:
                angle = _compute_angle(skel, x, y, neighbors)
                minutiae.append((x, y, 'bifurcation', angle))

    endings      = sum(1 for m in minutiae if m[2] == 'ending')
    bifurcations = sum(1 for m in minutiae if m[2] == 'bifurcation')

    print(f"[OK] Minutiae détectées : {len(minutiae)} total")
    print(f"     → Terminaisons  : {endings}")
    print(f"     → Bifurcations  : {bifurcations}")

    return minutiae


def filter_minutiae(minutiae, min_distance=8):
    """
    Supprime les minutiae trop proches les unes des autres.
    Les clusters de points proches sont souvent des artefacts du squelette.

    Args:
        minutiae (list): Liste brute de minutiae (x, y, type)
        min_distance (int): Distance minimale en pixels entre deux minutiae

    Returns:
        list: Liste filtrée
    """
    if not minutiae:
        return []

    filtered = []
    for m in minutiae:
        too_close = False
        for f in filtered:
            dist = np.sqrt((m[0] - f[0])**2 + (m[1] - f[1])**2)
            if dist < min_distance:
                too_close = True
                break
        if not too_close:
            filtered.append(m)

    print(f"[OK] Après filtrage : {len(filtered)} minutiae (supprimé {len(minutiae)-len(filtered)} doublons)")
    return filtered


def visualize_minutiae(original, minutiae, window_title="Minutiae"):
    """
    Affiche les minutiae détectées sur l'image originale.
    - Points VERTS  = terminaisons de crête
    - Points ROUGES = bifurcations

    Args:
        original (numpy.ndarray): Image originale en niveaux de gris
        minutiae (list): Liste de minutiae (x, y, type)
        window_title (str): Titre de la fenêtre
    """
    # Convertir en couleur pour afficher des points colorés
    display = cv2.cvtColor(original, cv2.COLOR_GRAY2BGR)

    for (x, y, mtype, angle) in minutiae:
        if mtype == 'ending':
            color = (0, 255, 0)
            radius = 3
        else:
            color = (0, 0, 255)
            radius = 3
        cv2.circle(display, (x, y), radius, color, -1)
        # Draw angle direction line
        dx = int(6 * np.cos(np.radians(angle)))
        dy = int(-6 * np.sin(np.radians(angle)))
        cv2.line(display, (x, y), (x + dx, y + dy), color, 1)

    # Légende
    cv2.putText(display, "Vert = Terminaison", (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    cv2.putText(display, "Rouge = Bifurcation", (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    cv2.putText(display, f"Total: {len(minutiae)}", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # Resize pour un meilleur affichage
    display_resized = cv2.resize(display, (500, 600), interpolation=cv2.INTER_LINEAR)
    cv2.imshow(window_title, display_resized)

    return display


# ─────────────────────────────────────────────
#  TEST RAPIDE
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import os

    # Trouver une image dans data/
    if len(sys.argv) > 1:
        test_image = sys.argv[1]
    else:
        # Always look for data/ relative to the project root, not current folder
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        data_dir = os.path.join(root_dir, "data", "real")
        images = [f for f in os.listdir(data_dir)
                  if f.lower().endswith(('.png', '.jpg', '.bmp', '.tif'))]
        if not images:
            print("[ERREUR] Aucune image trouvée dans data/")
            sys.exit(1)
        test_image = os.path.join(data_dir, images[0])
        print(f"[INFO] Image utilisée : {test_image}")

    # Étape 1 : Prétraitement
    original, normalized, binary, skeleton = preprocess(test_image)

    if skeleton is None:
        sys.exit(1)

    # Étape 2 : Extraction brute
    minutiae_raw = extract_minutiae(skeleton)

    # Étape 3 : Filtrage des doublons
    minutiae_clean = filter_minutiae(minutiae_raw, min_distance=8)

    # Étape 4 : Visualisation
    print("\n[INFO] Affichage des résultats...")
    print("       Vert  = Terminaisons de crête")
    print("       Rouge = Bifurcations")

    original_display = cv2.resize(original, (500, 600))
    cv2.imshow("Original", original_display)
    cv2.moveWindow("Original", 0, 50)

    visualize_minutiae(original, minutiae_clean, "Minutiae Detectees")
    cv2.moveWindow("Minutiae Detectees", 520, 50)

    print("\n[INFO] Appuyez sur Q ou Echap pour fermer...")
    while True:
        key = cv2.waitKey(100) & 0xFF
        if key in [ord('q'), ord('Q'), 27]:
            break
        if cv2.getWindowProperty("Minutiae Detectees", cv2.WND_PROP_VISIBLE) < 1:
            break

    cv2.destroyAllWindows()