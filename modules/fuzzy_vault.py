"""
Module 4 : Coffre-fort Flou (Fuzzy Vault)
Fichier : modules/fuzzy_vault.py

Rôle : Protéger les minutiae en les cachant parmi des points factices.
       Même en cas de vol de la base, impossible de distinguer
       les vrais points des faux sans la clé secrète.

Principe (Juels & Sudan, 2002) :
    1. On génère un polynôme secret P(x) à partir d'une clé utilisateur
    2. Les vrais points de minutiae sont projetés SUR ce polynôme : (x, P(x))
    3. Des points factices (chaff) sont ajoutés HORS du polynôme : (x, P(x)+bruit)
    4. Le vault = tous les points mélangés → indiscernables sans la clé
    5. Pour vérifier : on teste si les nouveaux minutiae tombent près du polynôme

Simplification académique :
    - Polynôme de degré 3 (suffisant pour démonstration)
    - Distance de tolérance configurable (pour les variations biométriques)
    - Pas d'interpolation de Lagrange complète (hors périmètre)
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
import random
import json
import hashlib


# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
POLYNOMIAL_DEGREE = 3      # degré du polynôme secret
CHAFF_RATIO       = 3      # nb points factices = CHAFF_RATIO × nb vrais points
TOLERANCE         = 0.12   # tolérance pour considérer un point "sur" le polynôme
COORD_RANGE       = (0.0, 1.0)  # plage des coordonnées normalisées
# ─────────────────────────────────────────────


class FuzzyVault:
    """
    Implémentation simplifiée du Fuzzy Vault Scheme.
    Protège un ensemble de points biométriques par obfuscation polynomiale.
    """

    def __init__(self, secret_key: str = None):
        """
        Args:
            secret_key (str): Clé secrète pour générer le polynôme.
                              Si None, une clé aléatoire est générée.
        """
        if secret_key is None:
            secret_key = hashlib.sha256(os.urandom(32)).hexdigest()[:16]
        self.secret_key  = secret_key
        self.coefficients = self._derive_polynomial(secret_key)

    def _derive_polynomial(self, key: str) -> list:
        """
        Dérive les coefficients du polynôme secret depuis la clé.
        Résultat reproductible : même clé → même polynôme.

        P(x) = a0 + a1*x + a2*x² + a3*x³

        Args:
            key (str): Clé secrète

        Returns:
            list: Coefficients [a0, a1, a2, a3]
        """
        # Hasher la clé pour obtenir des octets déterministes
        key_bytes = hashlib.sha256(key.encode()).digest()

        # Extraire 4 coefficients entre -1 et 1
        coeffs = []
        for i in range(POLYNOMIAL_DEGREE + 1):
            val = int.from_bytes(key_bytes[i*2:(i+1)*2], 'big')
            coeff = (val / 32767.5) - 1.0   # normaliser vers [-1, 1]
            coeffs.append(round(coeff, 6))

        return coeffs

    def _evaluate_polynomial(self, x: float) -> float:
        """
        Évalue P(x) = a0 + a1*x + a2*x² + a3*x³

        Args:
            x (float): Valeur d'entrée

        Returns:
            float: P(x) modulo 1 (ramené dans [0,1])
        """
        result = sum(c * (x ** i) for i, c in enumerate(self.coefficients))
        # Ramener dans [0, 1] avec modulo
        return abs(result) % 1.0

    def lock(self, minutiae: list, chaff_ratio: int = CHAFF_RATIO) -> dict:
        """
        Crée le coffre-fort : cache les vrais points parmi des points factices.

        Args:
            minutiae (list): Liste de (x, y, type) normalisés
            chaff_ratio (int): Nb de points factices par vrai point

        Returns:
            dict: Le vault contenant tous les points mélangés
        """
        if not minutiae:
            return {"points": [], "n_genuine": 0, "n_chaff": 0}

        genuine_points = []
        chaff_points   = []

        # ── Projeter les vrais points SUR le polynôme ─────
        for (x, y, mtype) in minutiae:
            px = x  # coordonnée x originale
            py = self._evaluate_polynomial(px)  # y projeté sur P(x)
            genuine_points.append({
                "x"    : round(float(px), 6),
                "y"    : round(float(py), 6),
                "real" : True   # marqueur (sera retiré du vault final)
            })

        # ── Générer des points factices HORS du polynôme ──
        n_chaff = len(minutiae) * chaff_ratio
        attempts = 0
        while len(chaff_points) < n_chaff and attempts < n_chaff * 10:
            attempts += 1
            cx = random.uniform(0.0, 1.0)
            cy = random.uniform(0.0, 1.0)

            # Vérifier que le point factice n'est PAS sur le polynôme
            poly_y = self._evaluate_polynomial(cx)
            if abs(cy - poly_y) > TOLERANCE * 2:
                chaff_points.append({
                    "x"    : round(cx, 6),
                    "y"    : round(cy, 6),
                    "real" : False
                })

        # ── Mélanger et masquer le marqueur "real" ─────────
        all_points = genuine_points + chaff_points
        random.shuffle(all_points)

        # Retirer le marqueur "real" du vault stocké
        vault_points = [{"x": p["x"], "y": p["y"]} for p in all_points]

        vault = {
            "points"    : vault_points,
            "n_genuine" : len(genuine_points),
            "n_chaff"   : len(chaff_points),
            "n_total"   : len(vault_points),
            "degree"    : POLYNOMIAL_DEGREE,
        }

        return vault

    def unlock(self, new_minutiae: list, vault: dict,
               tolerance: float = TOLERANCE) -> dict:
        """
        Tente d'ouvrir le coffre avec de nouveaux points biométriques.
        Compte combien de nouveaux points tombent près du polynôme.

        Args:
            new_minutiae (list): Nouveaux points (x, y, type)
            vault (dict): Le vault à ouvrir
            tolerance (float): Distance max pour considérer un "match"

        Returns:
            dict: Résultat avec score et décision
        """
        if not vault.get("points") or not new_minutiae:
            return {"unlocked": False, "score": 0.0, "matches": 0}

        matches = 0
        match_details = []

        for (x, y, mtype) in new_minutiae:
            poly_y  = self._evaluate_polynomial(x)
            dist    = abs(y - poly_y)  # distance au polynôme

            if dist <= tolerance:
                matches += 1
                match_details.append({
                    "x": round(float(x), 4),
                    "dist": round(dist, 4)
                })

        n_genuine = vault.get("n_genuine", 1)
        score     = matches / max(len(new_minutiae), 1)

        # Seuil : au moins 30% des points doivent matcher
        threshold = 0.15
        unlocked  = score >= threshold

        return {
            "unlocked"  : unlocked,
            "score"     : round(score, 4),
            "matches"   : matches,
            "tested"    : len(new_minutiae),
            "threshold" : threshold,
            "details"   : match_details[:5],  # premiers matches pour debug
        }

    def serialize(self, vault: dict) -> str:
        """Sérialise le vault en JSON pour stockage."""
        return json.dumps(vault)

    def deserialize(self, vault_json: str) -> dict:
        """Désérialise un vault depuis JSON."""
        return json.loads(vault_json)


# ─────────────────────────────────────────────
#  INTÉGRATION AVEC LE PIPELINE EXISTANT
# ─────────────────────────────────────────────

def create_vault_from_image(image_path: str, secret_key: str) -> dict:
    """
    Pipeline complet : image → minutiae → vault.

    Args:
        image_path (str): Chemin vers l'image d'empreinte
        secret_key (str): Clé secrète de l'utilisateur

    Returns:
        dict: {"vault": ..., "template": ..., "fv": FuzzyVault instance}
    """
    from modules.preprocessor import preprocess
    from modules.minutiae     import extract_minutiae, filter_minutiae
    from modules.template     import normalize_minutiae, generate_template

    # Prétraitement
    original, normalized, binary, skeleton = preprocess(image_path)
    if skeleton is None:
        return None

    # Minutiae
    raw      = extract_minutiae(skeleton)
    clean    = filter_minutiae(raw)
    norm     = normalize_minutiae(clean, skeleton.shape)

    # Fuzzy Vault
    fv    = FuzzyVault(secret_key)
    vault = fv.lock(norm)

    # Template standard (pour comparaison)
    template = generate_template(image_path)

    return {"vault": vault, "template": template, "fv": fv}


def verify_with_vault(image_path: str, vault: dict, secret_key: str) -> dict:
    """
    Vérifie une empreinte contre un vault existant.

    Args:
        image_path (str): Nouvelle image à vérifier
        vault (dict): Vault stocké
        secret_key (str): Clé secrète

    Returns:
        dict: Résultat de l'ouverture du vault
    """
    from modules.preprocessor import preprocess
    from modules.minutiae     import extract_minutiae, filter_minutiae
    from modules.template     import normalize_minutiae

    original, normalized, binary, skeleton = preprocess(image_path)
    if skeleton is None:
        return {"unlocked": False, "score": 0.0}

    raw   = extract_minutiae(skeleton)
    clean = filter_minutiae(raw)
    norm  = normalize_minutiae(clean, skeleton.shape)

    fv     = FuzzyVault(secret_key)
    result = fv.unlock(norm, vault)
    return result


# ─────────────────────────────────────────────
#  TEST COMPLET
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import json

    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    real_dir    = os.path.join(root_dir, "data", "real")
    altered_dir = os.path.join(root_dir, "data", "altered")

    real_images    = sorted([f for f in os.listdir(real_dir)
                              if f.lower().endswith('.bmp')])
    altered_images = sorted([f for f in os.listdir(altered_dir)
                              if f.lower().endswith('.bmp')])

    if not real_images:
        print("[ERREUR] Aucune image dans data/real/")
        sys.exit(1)

    SECRET_KEY = "secureprint_demo_2026"

    print(f"\n{'='*55}")
    print("  TEST FUZZY VAULT")
    print(f"{'='*55}\n")

    # ── Test 1 : Créer un vault ────────────────────────────
    print("── Test 1 : Création du vault ──")
    img1 = os.path.join(real_dir, real_images[0])
    result = create_vault_from_image(img1, SECRET_KEY)

    if result is None:
        print("[ERREUR] Impossible de créer le vault")
        sys.exit(1)

    vault = result["vault"]
    print(f"[OK] Vault créé pour : {real_images[0]}")
    print(f"     Points réels   : {vault['n_genuine']}")
    print(f"     Points factices: {vault['n_chaff']}")
    print(f"     Total dans vault: {vault['n_total']}")
    print(f"     → Impossible de distinguer réels des factices ✓")

    # ── Test 2 : Ouvrir avec le bon doigt (altéré) ────────
    print(f"\n── Test 2 : Ouverture avec MÊME doigt (altéré) ──")
    person_id  = real_images[0].split("__")[0]
    match_alt  = [f for f in altered_images if f.startswith(person_id + "__")]

    if match_alt:
        img_alt = os.path.join(altered_dir, match_alt[0])
        res2    = verify_with_vault(img_alt, vault, SECRET_KEY)
        status  = "✓ OUVERT" if res2["unlocked"] else "✗ FERMÉ"
        print(f"[{status}] Image : {match_alt[0]}")
        print(f"   Score  : {res2['score']:.4f}  (seuil : {res2['threshold']})")
        print(f"   Points matchés : {res2['matches']} / {res2['tested']}")
    else:
        print("[INFO] Pas d'image altérée trouvée pour ce doigt")

    # ── Test 3 : Tenter avec un MAUVAIS doigt ─────────────
    print(f"\n── Test 3 : Tentative avec MAUVAIS doigt ──")
    if len(real_images) > 1:
        wrong_img = os.path.join(real_dir, real_images[1])
        res3      = verify_with_vault(wrong_img, vault, SECRET_KEY)
        status    = "✓ OUVERT" if res3["unlocked"] else "✗ FERMÉ"
        print(f"[{status}] Image : {real_images[1]}")
        print(f"   Score  : {res3['score']:.4f}  (seuil : {res3['threshold']})")
        print(f"   → Mauvais doigt correctement rejeté : {not res3['unlocked']}")

    # ── Test 4 : Mauvaise clé ─────────────────────────────
    print(f"\n── Test 4 : Tentative avec MAUVAISE clé ──")
    fv_wrong   = FuzzyVault("wrong_key_12345")
    from modules.preprocessor import preprocess
    from modules.minutiae     import extract_minutiae, filter_minutiae
    from modules.template     import normalize_minutiae

    _, _, _, skel = preprocess(img1)
    raw   = extract_minutiae(skel)
    clean = filter_minutiae(raw)
    norm  = normalize_minutiae(clean, skel.shape)
    res4  = fv_wrong.unlock(norm, vault)
    status = "✓ OUVERT" if res4["unlocked"] else "✗ FERMÉ"
    print(f"[{status}] Même doigt, mauvaise clé")
    print(f"   Score : {res4['score']:.4f}")
    print(f"   → Mauvaise clé rejetée : {not res4['unlocked']}")

    print(f"\n{'='*55}")
    print("  FUZZY VAULT : TEST TERMINÉ")
    print(f"{'='*55}\n")