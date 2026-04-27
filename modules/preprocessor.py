"""
Module 1 : Acquisition et Prétraitement des empreintes digitales
Fichier : modules/preprocessor.py

Rôle : Charger une image d'empreinte, la nettoyer, et produire un squelette
       prêt pour l'extraction des minutiae.
"""

import cv2
import numpy as np
from skimage.morphology import skeletonize


def load_image(image_path):
    """
    Charge une image depuis un fichier et la convertit en niveaux de gris.
    
    Args:
        image_path (str): Chemin vers l'image d'empreinte
    
    Returns:
        numpy.ndarray: Image en niveaux de gris, ou None si erreur
    """
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        print(f"[ERREUR] Impossible de charger l'image : {image_path}")
        return None
    print(f"[OK] Image chargée : {image_path} — Taille : {image.shape}")
    return image


def upscale_image(image, scale=2):
    h, w = image.shape
    upscaled = cv2.resize(image, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
    print(f"[OK] Image agrandie : {image.shape} -> {upscaled.shape}")
    return upscaled


def normalize_image(image):
    """
    Normalise le contraste de l'image pour améliorer la qualité.
    
    Args:
        image (numpy.ndarray): Image en niveaux de gris
    
    Returns:
        numpy.ndarray: Image normalisée
    """
    # CLAHE = amélioration locale du contraste (meilleur que simple normalisation)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    normalized = clahe.apply(image)
    print("[OK] Contraste normalisé (CLAHE)")
    return normalized


def binarize_image(image):
    """
    Binarise l'image (noir et blanc) en utilisant un seuillage adaptatif.
    Les crêtes deviennent blanches (255), les vallées noires (0).
    
    Args:
        image (numpy.ndarray): Image normalisée en niveaux de gris
    
    Returns:
        numpy.ndarray: Image binaire
    """
    # Seuillage adaptatif : meilleur que global car gère les variations de luminosité
    binary = cv2.adaptiveThreshold(
        image,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,  # INV : crêtes en blanc
        blockSize=11,
        C=2
    )
    print("[OK] Image binarisée (seuillage adaptatif)")
    return binary


def clean_binary(binary):
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN,  kernel)
    print("[OK] Nettoyage morphologique applique")
    return cleaned


def skeletonize_image(binary_image):
    """
    Réduit les crêtes à 1 pixel d'épaisseur (squelettisation).
    C'est indispensable pour détecter précisément les minutiae.
    
    Args:
        binary_image (numpy.ndarray): Image binaire
    
    Returns:
        numpy.ndarray: Image squelettisée (valeurs 0 ou 255)
    """
    # Convertir en bool pour skimage, puis reconvertir en uint8
    binary_bool = binary_image > 0
    skeleton_bool = skeletonize(binary_bool)
    skeleton = (skeleton_bool * 255).astype(np.uint8)
    print("[OK] Squelettisation terminée")
    return skeleton


def preprocess(image_path, save_steps=False, output_dir="data/debug"):
    """
    Pipeline complet de prétraitement d'une image d'empreinte.
    
    Args:
        image_path (str): Chemin vers l'image source
        save_steps (bool): Si True, sauvegarde les images intermédiaires
        output_dir (str): Dossier de sauvegarde des étapes (si save_steps=True)
    
    Returns:
        tuple: (image_originale, image_normalisee, image_binaire, squelette)
               ou (None, None, None, None) si erreur
    """
    print(f"\n{'='*50}")
    print(f"  PRÉTRAITEMENT : {image_path}")
    print(f"{'='*50}")

    # Étape 1 : Chargement
    original = load_image(image_path)
    if original is None:
        return None, None, None, None

    # Étape 2 : Agrandissement (2x) pour plus de détails
    upscaled = upscale_image(original)

    # Étape 3 : Normalisation
    normalized = normalize_image(upscaled)

    # Étape 4 : Binarisation
    binary = binarize_image(normalized)

    # Étape 5 : Nettoyage morphologique
    binary = clean_binary(binary)

    # Étape 6 : Squelettisation
    skeleton = skeletonize_image(binary)

    # Sauvegarde optionnelle des étapes pour debug visuel
    if save_steps:
        import os
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        cv2.imwrite(f"{output_dir}/{base_name}_1_original.png", original)
        cv2.imwrite(f"{output_dir}/{base_name}_2_normalized.png", normalized)
        cv2.imwrite(f"{output_dir}/{base_name}_3_binary.png", binary)
        cv2.imwrite(f"{output_dir}/{base_name}_4_skeleton.png", skeleton)
        print(f"[OK] Étapes sauvegardées dans : {output_dir}/")

    print(f"{'='*50}")
    print("  PRÉTRAITEMENT TERMINÉ AVEC SUCCÈS")
    print(f"{'='*50}\n")

    return original, normalized, binary, skeleton


# ─────────────────────────────────────────────
#  TEST RAPIDE (exécuter directement ce fichier)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import os

    # Utilise l'image passée en argument, ou la première image du dossier data/
    if len(sys.argv) > 1:
        test_image = sys.argv[1]
    else:
        # Cherche automatiquement une image dans data/
        data_dir = "data"
        images = [f for f in os.listdir(data_dir) if f.endswith(('.png', '.jpg', '.BMP', '.tif'))]
        if not images:
            print("[ERREUR] Aucune image trouvée dans le dossier data/")
            sys.exit(1)
        test_image = os.path.join(data_dir, images[0])
        print(f"[INFO] Aucun argument fourni, utilisation de : {test_image}")

    # Lancer le prétraitement avec sauvegarde des étapes
    original, normalized, binary, skeleton = preprocess(
        test_image,
        save_steps=True,
        output_dir="data/debug"
    )

    if skeleton is not None:
        # Resize images for better display (scale up small fingerprint images)
        display_size = (400, 500)
        original_display    = cv2.resize(original,    display_size, interpolation=cv2.INTER_LINEAR)
        normalized_display  = cv2.resize(normalized,  display_size, interpolation=cv2.INTER_LINEAR)
        binary_display      = cv2.resize(binary,      display_size, interpolation=cv2.INTER_LINEAR)
        skeleton_display    = cv2.resize(skeleton,    display_size, interpolation=cv2.INTER_NEAREST)

        # Show all 4 steps side by side
        cv2.imshow("1 - Original",    original_display)
        cv2.imshow("2 - Normalise",   normalized_display)
        cv2.imshow("3 - Binaire",     binary_display)
        cv2.imshow("4 - Squelette",   skeleton_display)

        # Position windows neatly across the screen
        cv2.moveWindow("1 - Original",   0,   50)
        cv2.moveWindow("2 - Normalise",  420, 50)
        cv2.moveWindow("3 - Binaire",    840, 50)
        cv2.moveWindow("4 - Squelette",  1260,50)

        print("\n[INFO] Appuyez sur 'Q' ou Echap pour fermer les fenetres...")
        while True:
            key = cv2.waitKey(100) & 0xFF
            if key in [ord('q'), ord('Q'), 27]:  # Q or Escape
                break
            # Also close if any window is manually closed
            if cv2.getWindowProperty("4 - Squelette", cv2.WND_PROP_VISIBLE) < 1:
                break
        cv2.destroyAllWindows()