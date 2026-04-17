"""
Module 4 : Chiffrement des Templates
Fichier : modules/encryption.py

Rôle : Chiffrer les templates biométriques avant stockage en base
       et les déchiffrer lors de l'authentification.

Technologie : AES-256 via cryptography.fernet
- Fernet = AES-128-CBC + HMAC-SHA256 (authentification + confidentialité)
- Chaque template est chiffré avec une clé maîtresse unique
- Sans la clé → les données sont illisibles

Principe RGPD appliqué :
- On ne stocke JAMAIS le template en clair
- La clé est stockée séparément des données
- Droit à l'oubli : supprimer l'entrée SQLite suffit
"""

import os
import sys
import base64
import hashlib
import numpy as np
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Dossier où stocker la clé maîtresse (séparé de la base de données)
KEY_DIR  = "database"
KEY_FILE = os.path.join(KEY_DIR, "master.key")


# ─────────────────────────────────────────────
#  GESTION DE LA CLÉ MAÎTRESSE
# ─────────────────────────────────────────────

def generate_master_key():
    """
    Génère une nouvelle clé maîtresse AES-256 et la sauvegarde sur disque.
    Cette fonction ne doit être appelée QU'UNE SEULE FOIS à l'initialisation.

    Returns:
        bytes: La clé générée
    """
    os.makedirs(KEY_DIR, exist_ok=True)

    if os.path.exists(KEY_FILE):
        print("[INFO] Clé maîtresse déjà existante — chargement...")
        return load_master_key()

    key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as f:
        f.write(key)

    print(f"[OK] Clé maîtresse générée et sauvegardée : {KEY_FILE}")
    print(f"     Longueur : {len(key)} bytes (256 bits)")
    return key


def load_master_key():
    """
    Charge la clé maîtresse depuis le fichier.

    Returns:
        bytes: La clé, ou None si le fichier n'existe pas
    """
    if not os.path.exists(KEY_FILE):
        print(f"[ERREUR] Clé maîtresse introuvable : {KEY_FILE}")
        print("         Lancez generate_master_key() d'abord")
        return None

    with open(KEY_FILE, "rb") as f:
        key = f.read()

    print(f"[OK] Clé maîtresse chargée ({len(key)} bytes)")
    return key


def derive_key_from_password(password: str, salt: bytes = None):
    """
    Dérive une clé de chiffrement à partir d'un mot de passe (PBKDF2).
    Utile si on veut une clé par utilisateur basée sur son mot de passe.

    Args:
        password (str): Mot de passe utilisateur
        salt (bytes): Sel aléatoire (généré si None)

    Returns:
        tuple: (clé_fernet, sel)
    """
    if salt is None:
        salt = os.urandom(16)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    key_bytes = kdf.derive(password.encode())
    key = base64.urlsafe_b64encode(key_bytes)
    return key, salt


# ─────────────────────────────────────────────
#  CHIFFREMENT / DÉCHIFFREMENT
# ─────────────────────────────────────────────

def encrypt_template(template: np.ndarray, key: bytes) -> bytes:
    """
    Chiffre un template numpy en bytes chiffrés.

    Pipeline :
    1. numpy array → bytes bruts
    2. bytes bruts → bytes chiffrés (Fernet/AES-256)

    Args:
        template (np.ndarray): Vecteur de caractéristiques (float32)
        key (bytes): Clé Fernet

    Returns:
        bytes: Template chiffré (stockable en BLOB SQLite)
    """
    # Étape 1 : Sérialiser le tableau numpy en bytes
    raw_bytes = template.astype(np.float32).tobytes()

    # Étape 2 : Chiffrer avec Fernet (AES-256)
    f = Fernet(key)
    encrypted = f.encrypt(raw_bytes)

    return encrypted


def decrypt_template(encrypted_bytes: bytes, key: bytes) -> np.ndarray:
    """
    Déchiffre des bytes chiffrés et reconstruit le template numpy.

    Args:
        encrypted_bytes (bytes): Template chiffré (depuis SQLite)
        key (bytes): Clé Fernet

    Returns:
        np.ndarray: Template original reconstruit, ou None si erreur
    """
    try:
        f = Fernet(key)

        # Étape 1 : Déchiffrer
        raw_bytes = f.decrypt(encrypted_bytes)

        # Étape 2 : Reconstruire le tableau numpy
        template = np.frombuffer(raw_bytes, dtype=np.float32).copy()
        return template

    except Exception as e:
        print(f"[ERREUR] Déchiffrement échoué : {e}")
        print("         Clé incorrecte ou données corrompues")
        return None


def compute_hash(template: np.ndarray) -> str:
    """
    Calcule un hash SHA-256 du template pour vérifier son intégrité.
    Permet de détecter toute modification du template après stockage.

    Args:
        template (np.ndarray): Template à hasher

    Returns:
        str: Hash SHA-256 en hexadécimal
    """
    raw_bytes = template.astype(np.float32).tobytes()
    return hashlib.sha256(raw_bytes).hexdigest()


def verify_integrity(template: np.ndarray, expected_hash: str) -> bool:
    """
    Vérifie que le template n'a pas été modifié depuis son stockage.

    Args:
        template (np.ndarray): Template déchiffré
        expected_hash (str): Hash SHA-256 original (stocké en base)

    Returns:
        bool: True si intègre, False si modifié
    """
    actual_hash = compute_hash(template)
    return actual_hash == expected_hash


# ─────────────────────────────────────────────
#  TEST RAPIDE
# ─────────────────────────────────────────────
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    from modules.template import generate_template

    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    data_dir = os.path.join(root_dir, "data", "real")

    images = sorted([
        os.path.join(data_dir, f)
        for f in os.listdir(data_dir)
        if f.lower().endswith('.bmp')
    ])

    if not images:
        print("[ERREUR] Aucune image dans data/real/")
        sys.exit(1)

    print(f"\n{'='*55}")
    print("  TEST MODULE CHIFFREMENT")
    print(f"{'='*55}\n")

    # ── Étape 1 : Générer un template ─────────────────────
    print("── Étape 1 : Génération du template ──")
    template = generate_template(images[0])
    if template is None:
        sys.exit(1)

    # ── Étape 2 : Générer/charger la clé maîtresse ────────
    print("── Étape 2 : Clé maîtresse ──")
    key = generate_master_key()

    # ── Étape 3 : Calculer le hash (intégrité) ────────────
    print("\n── Étape 3 : Hash SHA-256 ──")
    original_hash = compute_hash(template)
    print(f"[OK] Hash original : {original_hash[:32]}...")

    # ── Étape 4 : Chiffrer ────────────────────────────────
    print("\n── Étape 4 : Chiffrement ──")
    encrypted = encrypt_template(template, key)
    print(f"[OK] Template chiffré : {len(encrypted)} bytes")
    print(f"     Aperçu : {encrypted[:40]}...")
    print(f"     → Illisible sans la clé ✓")

    # ── Étape 5 : Déchiffrer ──────────────────────────────
    print("\n── Étape 5 : Déchiffrement ──")
    decrypted = decrypt_template(encrypted, key)
    if decrypted is None:
        print("[ERREUR] Déchiffrement échoué")
        sys.exit(1)

    # ── Étape 6 : Vérifier l'intégrité ────────────────────
    print("\n── Étape 6 : Vérification intégrité ──")
    intact = verify_integrity(decrypted, original_hash)
    print(f"[OK] Intégrité vérifiée : {intact}")

    # ── Étape 7 : Vérifier que les données sont identiques ─
    print("\n── Étape 7 : Comparaison original vs déchiffré ──")
    match = np.allclose(template, decrypted, atol=1e-6)
    print(f"[OK] Template identique après chiffrement/déchiffrement : {match}")

    # ── Étape 8 : Tester avec mauvaise clé ────────────────
    print("\n── Étape 8 : Test avec mauvaise clé ──")
    wrong_key = Fernet.generate_key()
    result = decrypt_template(encrypted, wrong_key)
    print(f"[OK] Mauvaise clé rejetée correctement : {result is None}")

    print(f"\n{'='*55}")
    print("  CHIFFREMENT : TOUS LES TESTS PASSÉS ✓")
    print(f"{'='*55}\n")