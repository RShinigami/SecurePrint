"""
Module 6 : Matching et Authentification
Fichier : modules/matcher.py

Rôle : Comparer un template de requête avec tous les templates
       en base et décider accepter / rejeter.

Métriques :
    - Distance Euclidienne : sensible à l'amplitude des vecteurs
    - Distance Cosinus     : mesure l'angle entre vecteurs (plus robuste)

Évaluation :
    - FAR (False Accept Rate) : imposteur accepté → dangereux
    - FRR (False Reject Rate) : utilisateur légitime rejeté → gênant
    - EER (Equal Error Rate)  : point où FAR = FRR → seuil optimal
"""

import os
import sys
import json
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.template  import generate_template
from modules.storage   import SecurePrintDB

# Seuil optimal calibré sur notre dataset
DEFAULT_THRESHOLD = 0.31
MIN_GAP = 0.0  # disabled — gap check hurts recall on low-res images


# ─────────────────────────────────────────────
#  FONCTIONS DE DISTANCE
# ─────────────────────────────────────────────

def euclidean_distance(t1: np.ndarray, t2: np.ndarray) -> float:
    return float(np.linalg.norm(t1 - t2))


def cosine_distance(t1: np.ndarray, t2: np.ndarray) -> float:
    n1, n2 = np.linalg.norm(t1), np.linalg.norm(t2)
    if n1 == 0 or n2 == 0:
        return 1.0
    return float(1.0 - np.dot(t1, t2) / (n1 * n2))


def combined_score(t1: np.ndarray, t2: np.ndarray) -> float:
    euc = euclidean_distance(t1, t2)
    cos = cosine_distance(t1, t2)
    euc_norm = euc / 6.0
    return float(0.5 * euc_norm + 0.5 * cos)


# ─────────────────────────────────────────────
#  AUTHENTIFICATION
# ─────────────────────────────────────────────

def identify(query_template: np.ndarray, db: SecurePrintDB,
             threshold: float = DEFAULT_THRESHOLD) -> dict:
    """
    Compare un template de requête contre tous les templates en base.
    Accepte uniquement si :
      1. best score < threshold
      2. gap between best and second best >= MIN_GAP (confident match)
    """
    all_templates = db.get_all_templates()

    if not all_templates:
        return {"accepted": False, "name": None,
                "score": 999.0, "threshold": threshold, "all_scores": []}

    scores = []
    for (user_id, name, stored_template, finger) in all_templates:
        euc  = euclidean_distance(query_template, stored_template)
        cos  = cosine_distance(query_template, stored_template)
        comb = combined_score(query_template, stored_template)
        scores.append({
            "name"      : name,
            "finger"    : finger,
            "euclidean" : round(euc,  4),
            "cosine"    : round(cos,  4),
            "combined"  : round(comb, 4),
        })

    scores.sort(key=lambda x: x["combined"])
    best   = scores[0]
    second = scores[1] if len(scores) > 1 else None

    gap = (second["combined"] - best["combined"]) if second else 1.0
    accepted = best["combined"] < threshold and (MIN_GAP == 0.0 or gap >= MIN_GAP)

    return {
        "accepted"  : accepted,
        "name"      : best["name"] if accepted else None,
        "score"     : best["combined"],
        "euclidean" : best["euclidean"],
        "cosine"    : best["cosine"],
        "gap"       : round(gap, 4),
        "threshold" : threshold,
        "all_scores": scores,
    }


# ─────────────────────────────────────────────
#  ÉVALUATION COMPLÈTE (FAR / FRR / EER)
# ─────────────────────────────────────────────

def evaluate(pairs_json_path: str, db: SecurePrintDB, threshold: float = DEFAULT_THRESHOLD):
    """
    Évalue les performances du système sur toutes les paires connues.
    Utilise les templates déjà en base pour éviter le double traitement.
    """
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    with open(pairs_json_path) as f:
        pairs = json.load(f)

    # Précharger TOUS les templates de la base en mémoire une seule fois
    print("[INFO] Chargement des templates depuis la base...")
    all_templates = db.get_all_templates()
    db_index = {name: template for (_, name, template, _) in all_templates}
    print(f"[OK] {len(db_index)} templates chargés\n")

    same_scores = []
    diff_scores = []

    print(f"── Test paires MÊME doigt ({len(pairs['same_finger_pairs'])}) ──")
    for pair in pairs["same_finger_pairs"]:
        # Récupérer le template réel depuis la base (déjà calculé)
        person_id = pair["person"]
        name      = f"User_{person_id}"
        t_real    = db_index.get(name)

        # Générer le template de l'image altérée (scan différent)
        altered_path = os.path.join(root_dir, "data", pair["altered"])
        t_altered    = generate_template(altered_path)

        if t_real is None or t_altered is None:
            continue

        score = combined_score(t_real, t_altered)
        same_scores.append(score)

    print(f"\n── Test paires DIFFÉRENTS doigts ({len(pairs['different_finger_pairs'])}) ──")
    for pair in pairs["different_finger_pairs"]:
        # Les deux templates sont déjà en base
        name1 = f"User_{os.path.basename(pair['file1']).split('__')[0]}"
        name2 = f"User_{os.path.basename(pair['file2']).split('__')[0]}"
        t1    = db_index.get(name1)
        t2    = db_index.get(name2)

        if t1 is None or t2 is None:
            continue

        score = combined_score(t1, t2)
        diff_scores.append(score)

    if not same_scores or not diff_scores:
        print("[ERREUR] Pas assez de données pour l'évaluation")
        return None

    # ── Calculer FAR et FRR ────────────────────────────────
    frr = sum(1 for s in same_scores if s >= threshold) / len(same_scores)
    far = sum(1 for s in diff_scores if s <  threshold) / len(diff_scores)
    accuracy = 1.0 - (far + frr) / 2.0

    # ── Trouver seuil optimal (EER) ────────────────────────
    best_threshold = threshold
    best_eer       = abs(far - frr)
    for t in np.arange(0.05, 1.0, 0.01):
        f = sum(1 for s in same_scores if s >= t) / len(same_scores)
        a = sum(1 for s in diff_scores if s <  t) / len(diff_scores)
        if abs(f - a) < best_eer:
            best_eer       = abs(f - a)
            best_threshold = round(float(t), 2)

    results = {
        "threshold"         : threshold,
        "FAR"               : round(far * 100, 1),
        "FRR"               : round(frr * 100, 1),
        "accuracy"          : round(accuracy * 100, 1),
        "optimal_threshold" : best_threshold,
        "same_scores_mean"  : round(float(np.mean(same_scores)), 4),
        "diff_scores_mean"  : round(float(np.mean(diff_scores)), 4),
        "n_same"            : len(same_scores),
        "n_diff"            : len(diff_scores),
    }

    print(f"\n{'='*50}")
    print(f"  RÉSULTATS D'ÉVALUATION")
    print(f"{'='*50}")
    print(f"  Seuil utilisé        : {threshold}")
    print(f"  Paires même doigt    : {len(same_scores)}")
    print(f"  Paires diff. doigt   : {len(diff_scores)}")
    print(f"  ─────────────────────────────────────────")
    print(f"  Score moyen (même)   : {results['same_scores_mean']}  ← doit être faible")
    print(f"  Score moyen (diff)   : {results['diff_scores_mean']}  ← doit être élevé")
    print(f"  ─────────────────────────────────────────")
    print(f"  FAR  (faux acceptés) : {results['FAR']}%")
    print(f"  FRR  (faux rejetés)  : {results['FRR']}%")
    print(f"  Accuracy             : {results['accuracy']}%")
    print(f"  ─────────────────────────────────────────")
    print(f"  Seuil optimal (EER)  : {best_threshold}")
    print(f"{'='*50}\n")

    return results


# ─────────────────────────────────────────────
#  ENRÔLEMENT EN MASSE
# ─────────────────────────────────────────────

def enroll_all(db: SecurePrintDB):
    """Enrôle toutes les images de data/real/ dans la base."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    data_dir = os.path.join(root_dir, "data", "real")

    images = sorted([
        os.path.join(data_dir, f)
        for f in os.listdir(data_dir)
        if f.lower().endswith('.bmp')
    ])

    print(f"\n[INFO] Enrôlement de {len(images)} images...\n")
    enrolled = 0

    for img_path in images:
        fname   = os.path.basename(img_path)
        parts   = fname.replace(".BMP", "").replace(".bmp", "").split("__")
        name    = f"User_{parts[0]}"
        details = parts[1].split("_") if len(parts) > 1 else []
        finger  = f"{details[1]}_{details[2]}" if len(details) >= 3 else "unknown"

        existing = db.get_user_template(name)
        if existing is not None:
            continue

        template = generate_template(img_path)
        if template is not None:
            ok, _ = db.enroll_user(name, template, finger)
            if ok:
                enrolled += 1

    print(f"\n[OK] {enrolled} nouveaux utilisateurs enrôlés")
    db.print_summary()


# ─────────────────────────────────────────────
#  TEST RAPIDE
# ─────────────────────────────────────────────
if __name__ == "__main__":
    root_dir   = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    pairs_path = os.path.join(root_dir, "data", "pairs.json")

    print(f"\n{'='*55}")
    print("  TEST MODULE MATCHER")
    print(f"{'='*55}")

    # ── Étape 1 : Ouvrir la base et enrôler tout le monde ─
    db = SecurePrintDB()
    enroll_all(db)

    # ── Étape 2 : Test d'authentification sur une paire ───
    if not os.path.exists(pairs_path):
        print("\n[INFO] pairs.json introuvable — lancement de setup_dataset.py")
        import subprocess
        subprocess.run(["python", "setup_dataset.py"], check=True)

    with open(pairs_path) as f:
        pairs = json.load(f)

    first_pair  = pairs["same_finger_pairs"][0]
    altered_img = os.path.join(root_dir, "data", first_pair["altered"])
    true_name   = f"User_{first_pair['person']}"

    print(f"\n── Test authentification ──")
    print(f"   Image test   : {os.path.basename(altered_img)}")
    print(f"   Attendu      : {true_name}")

    query = generate_template(altered_img)
    if query is not None:
        result = identify(query, db)
        status = "✓ ACCEPTÉ" if result["accepted"] else "✗ REJETÉ"
        print(f"\n   Résultat     : {status}")
        print(f"   Identifié    : {result['name'] or 'inconnu'}")
        print(f"   Score        : {result['score']:.4f}")
        print(f"   Seuil        : {result['threshold']}")
        correct = result["accepted"] and result["name"] == true_name
        print(f"   Correct      : {'✓ OUI' if correct else '✗ NON'}")

    # ── Étape 3 : Évaluation complète ─────────────────────
    print(f"\n── Évaluation complète FAR/FRR ──")
    evaluate(pairs_path, db, threshold=DEFAULT_THRESHOLD)

    db.close()