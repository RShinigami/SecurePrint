"""
modules/fuzzy_vault.py — Fuzzy Vault Scheme (Juels & Sudan, 2002)

Principle:
    A secret key is encoded as coefficients of a polynomial p(x) over GF(PRIME).
    Genuine points  : (x_i, p(x_i))  — lie ON the polynomial, x_i from minutiae
    Chaff points    : (x_j, random_y) — do NOT lie on the polynomial
    Stored vault    : shuffled (x, y) pairs only — no template, no key, no labels

Lock:
    1. Derive polynomial coefficients from secret key
    2. Map minutiae (x, y, type) → integer x-values
    3. Compute genuine vault points (x, p(x))
    4. Generate chaff points (random x, random y ≠ p(x))
    5. Shuffle and store — vault reveals nothing without the biometric

Unlock:
    1. Map query minutiae → integer x-values
    2. Find vault points whose x is within TOLERANCE of a query x
    3. Try combinations of POLY_DEGREE+1 candidate points
    4. Lagrange-interpolate → check if recovered polynomial matches key hash
    5. Accept if hash matches

Security note:
    The vault stores ONLY (x, y) integer pairs.
    Without the correct minutiae, an attacker cannot distinguish genuine from chaff
    (there are C(n_genuine + n_chaff, POLY_DEGREE+1) combinations to try).
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import hashlib
import json
import random
import numpy as np
from itertools import combinations


# ─────────────────────────────────────────────
#  PARAMETERS
# ─────────────────────────────────────────────
PRIME        = 7919    # prime field — large enough for minutiae coords on 96×103 images
POLY_DEGREE  = 4       # need POLY_DEGREE+1 = 5 genuine matches to reconstruct
N_CHAFF      = 60      # fake points added to the vault
TOLERANCE    = 6       # pixel tolerance for matching minutiae across scans
MIN_MATCHES  = POLY_DEGREE + 1


# ─────────────────────────────────────────────
#  FINITE FIELD ARITHMETIC (mod PRIME)
# ─────────────────────────────────────────────

def _extended_gcd(a, b):
    if a == 0:
        return b, 0, 1
    g, x, y = _extended_gcd(b % a, a)
    return g, y - (b // a) * x, x


def _mod_inv(a, prime=PRIME):
    g, x, _ = _extended_gcd(a % prime, prime)
    return x % prime if g == 1 else None


def _poly_eval(coeffs, x, prime=PRIME):
    """Evaluate polynomial at x using Horner's method (mod prime)."""
    result = 0
    for c in reversed(coeffs):
        result = (result * x + c) % prime
    return result


def _lagrange_interpolate(points, prime=PRIME):
    """
    Reconstruct polynomial value at x=0 (the free term / secret anchor)
    from POLY_DEGREE+1 points using Lagrange interpolation mod prime.
    Returns the full coefficient list of the interpolated polynomial.
    """
    n = len(points)
    # We only need to verify the polynomial, so compute all coefficients
    # via Newton's divided differences (simpler in finite field)
    # Instead: evaluate at x=0,1,...,n-1 and check consistency
    # Simplest correct approach: compute p(0) via Lagrange and compare to stored hash

    result = 0
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    for i in range(n):
        num = ys[i]
        den = 1
        for j in range(n):
            if i == j:
                continue
            num = (num * (0 - xs[j])) % prime
            den = (den * (xs[i] - xs[j])) % prime
        inv = _mod_inv(den, prime)
        if inv is None:
            return None
        result = (result + num * inv) % prime

    return result  # p(0) — the secret anchor value


# ─────────────────────────────────────────────
#  KEY ↔ POLYNOMIAL
# ─────────────────────────────────────────────

def _key_to_coeffs(secret_key: bytes, degree: int = POLY_DEGREE, prime: int = PRIME) -> list:
    """Derive stable polynomial coefficients from a secret key."""
    coeffs = []
    h = hashlib.sha256(secret_key).digest()
    for i in range(degree + 1):
        block = hashlib.sha256(h + i.to_bytes(2, 'big')).digest()
        coeffs.append(int.from_bytes(block[:4], 'big') % prime)
    return coeffs


def _secret_anchor(coeffs: list, prime: int = PRIME) -> int:
    """p(0) = coeffs[0] — the value we verify after interpolation."""
    return coeffs[0] % prime


def _anchor_hash(anchor: int) -> str:
    """SHA-256 of the secret anchor — stored in vault for verification."""
    return hashlib.sha256(anchor.to_bytes(4, 'big')).hexdigest()


# ─────────────────────────────────────────────
#  MINUTIAE → INTEGER X-VALUES
# ─────────────────────────────────────────────

def _minutiae_to_xs(minutiae: list, prime: int = PRIME) -> list:
    """
    Map minutiae (x, y, type) to unique integer x-values for the polynomial.
    Uses pixel coordinates directly — small images keep values well below PRIME.
    Deduplicates to avoid two genuine points sharing the same x.
    """
    seen = set()
    xs = []
    for (px, py, _) in minutiae:
        val = (int(px) * 200 + int(py)) % prime
        if val not in seen:
            seen.add(val)
            xs.append(val)
    return xs


# ─────────────────────────────────────────────
#  FUZZY VAULT CLASS
# ─────────────────────────────────────────────

class FuzzyVault:

    def __init__(self, secret_key: bytes):
        """
        Args:
            secret_key: Raw bytes, e.g. os.urandom(32).
                        Use the same key for lock and unlock.
        """
        self.secret_key = secret_key
        self.coeffs     = _key_to_coeffs(secret_key)
        self.anchor     = _secret_anchor(self.coeffs)
        self.anchor_hash = _anchor_hash(self.anchor)

    def lock(self, minutiae: list) -> dict:
        """
        Build the vault from raw minutiae.

        Args:
            minutiae: list of (x, y, type) — output of filter_minutiae()

        Returns:
            dict: vault with (x,y) pairs only — no template data, no labels
        """
        xs = _minutiae_to_xs(minutiae)

        if len(xs) < MIN_MATCHES:
            print(f"[FuzzyVault] Not enough unique minutiae: {len(xs)} < {MIN_MATCHES}")
            return {"vault_points": [], "anchor_hash": self.anchor_hash,
                    "valid": False, "n_genuine": 0, "n_chaff": 0}

        # Genuine points: (x, p(x))
        genuine_xs  = set(xs)
        genuine_pts = [(x, _poly_eval(self.coeffs, x)) for x in xs]

        # Chaff points: random (x, y) guaranteed NOT on the polynomial
        chaff_pts = []
        attempts  = 0
        while len(chaff_pts) < N_CHAFF and attempts < N_CHAFF * 20:
            attempts += 1
            cx = random.randint(1, PRIME - 1)
            if cx in genuine_xs:
                continue
            cy = random.randint(0, PRIME - 1)
            if cy != _poly_eval(self.coeffs, cx):
                chaff_pts.append((cx, cy))
                genuine_xs.add(cx)  # prevent duplicate x in chaff

        all_points = genuine_pts + chaff_pts
        random.shuffle(all_points)

        print(f"[FuzzyVault] Vault locked — {len(genuine_pts)} genuine + {len(chaff_pts)} chaff = {len(all_points)} total")

        return {
            "vault_points" : all_points,        # list of [x, y] — no labels
            "anchor_hash"  : self.anchor_hash,  # SHA-256(p(0)) for verification
            "valid"        : True,
            "n_genuine"    : len(genuine_pts),
            "n_chaff"      : len(chaff_pts),
        }

    def unlock(self, query_minutiae: list, vault: dict) -> dict:
        """
        Attempt to open the vault using query minutiae.

        Steps:
            1. Map query minutiae → x-values
            2. Find vault points with x within TOLERANCE of a query x
            3. Try all C(candidates, MIN_MATCHES) combinations
            4. Lagrange-interpolate p(0) and compare to anchor_hash

        Args:
            query_minutiae: list of (x, y, type) from a new scan
            vault: dict returned by lock()

        Returns:
            dict: unlocked (bool), score, matches found
        """
        if not vault.get("valid") or not vault.get("vault_points"):
            return {"unlocked": False, "score": 0.0, "matches": 0, "candidates": 0}

        vault_points = [tuple(p) for p in vault["vault_points"]]
        stored_hash  = vault["anchor_hash"]
        query_xs     = _minutiae_to_xs(query_minutiae)

        # Step 1: collect candidate vault points near query x-values
        candidates = []
        for qx in query_xs:
            for (vx, vy) in vault_points:
                if abs(qx - vx) <= TOLERANCE:
                    candidates.append((vx, vy))
                    break  # one candidate per query minutia

        n_candidates = len(candidates)
        n_genuine    = vault.get("n_genuine", 1)

        if n_candidates < MIN_MATCHES:
            return {
                "unlocked"   : False,
                "score"      : n_candidates / max(n_genuine, 1),
                "matches"    : n_candidates,
                "candidates" : n_candidates,
            }

        # Step 2: try combinations until polynomial reconstructed
        # Limit combinations to avoid exponential blowup on low-res images
        max_combos = 2000
        tested     = 0

        for combo in combinations(candidates, MIN_MATCHES):
            # Check no duplicate x-values (Lagrange requires distinct x)
            xs_in_combo = [p[0] for p in combo]
            if len(set(xs_in_combo)) < MIN_MATCHES:
                continue

            tested += 1
            if tested > max_combos:
                break

            recovered_anchor = _lagrange_interpolate(list(combo))
            if recovered_anchor is None:
                continue

            if _anchor_hash(recovered_anchor) == stored_hash:
                return {
                    "unlocked"   : True,
                    "score"      : 1.0,
                    "matches"    : n_candidates,
                    "candidates" : n_candidates,
                    "combos_tried": tested,
                }

        return {
            "unlocked"    : False,
            "score"       : n_candidates / max(n_genuine, 1),
            "matches"     : n_candidates,
            "candidates"  : n_candidates,
            "combos_tried": tested,
        }

    def serialize(self, vault: dict) -> str:
        return json.dumps(vault)

    def deserialize(self, vault_json: str) -> dict:
        return json.loads(vault_json)


# ─────────────────────────────────────────────
#  PIPELINE HELPERS
# ─────────────────────────────────────────────

def _get_minutiae(image_path: str):
    """Run preprocessing + minutiae extraction on an image."""
    from modules.preprocessor import preprocess
    from modules.minutiae import extract_minutiae, filter_minutiae

    _, _, _, skeleton = preprocess(image_path)
    if skeleton is None:
        return None, None
    raw      = extract_minutiae(skeleton)
    filtered = filter_minutiae(raw, min_distance=8)
    return filtered, skeleton.shape


def lock_image(image_path: str, secret_key: bytes) -> dict:
    """Full pipeline: image → vault."""
    minutiae, _ = _get_minutiae(image_path)
    if not minutiae:
        return {"valid": False}
    fv = FuzzyVault(secret_key)
    return fv.lock(minutiae)


def unlock_image(image_path: str, vault: dict, secret_key: bytes) -> dict:
    """Full pipeline: image + vault → unlock result."""
    minutiae, _ = _get_minutiae(image_path)
    if not minutiae:
        return {"unlocked": False, "score": 0.0, "matches": 0, "candidates": 0}
    fv = FuzzyVault(secret_key)
    return fv.unlock(minutiae, vault)


# ─────────────────────────────────────────────
#  TEST — runs on actual pairs.json data
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import json

    root_dir   = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    real_dir   = os.path.join(root_dir, "data", "real")
    alt_dir    = os.path.join(root_dir, "data", "altered")
    pairs_path = os.path.join(root_dir, "data", "pairs.json")

    with open(pairs_path) as f:
        pairs = json.load(f)

    print(f"\n{'='*60}")
    print("  FUZZY VAULT — Correct Implementation Test")
    print(f"  PRIME={PRIME}  DEGREE={POLY_DEGREE}  TOLERANCE={TOLERANCE}  CHAFF={N_CHAFF}")
    print(f"{'='*60}\n")

    # ── Quick sanity check on first pair ──────────────────
    first      = pairs["same_finger_pairs"][0]
    real_path  = os.path.join(root_dir, "data", first["real"])
    alt_path   = os.path.join(root_dir, "data", first["altered"])
    secret_key = os.urandom(32)

    print(f"── Sanity check: person {first['person']} ({first['finger']}) ──")
    vault = lock_image(real_path, secret_key)
    if vault["valid"]:
        # Same finger (altered scan) — should unlock
        r_same = unlock_image(alt_path, vault, secret_key)
        print(f"  Same finger  : {'✓ UNLOCKED' if r_same['unlocked'] else '✗ LOCKED'}"
              f"  candidates={r_same['candidates']}  combos={r_same.get('combos_tried', 0)}")

        # Different finger — should stay locked
        diff_pair = pairs["different_finger_pairs"][0]
        diff_path = os.path.join(root_dir, "data", diff_pair["file2"])
        r_diff    = unlock_image(diff_path, vault, secret_key)
        print(f"  Diff finger  : {'✓ UNLOCKED' if r_diff['unlocked'] else '✗ LOCKED (correct)'}"
              f"  candidates={r_diff['candidates']}")

        # Wrong key — should stay locked
        r_key = unlock_image(alt_path, vault, os.urandom(32))
        print(f"  Wrong key    : {'✓ UNLOCKED' if r_key['unlocked'] else '✗ LOCKED (correct)'}"
              f"  candidates={r_key['candidates']}")
    else:
        print("  [SKIP] Not enough minutiae for sanity check")

    # ── Full FAR / FRR evaluation ──────────────────────────
    print(f"\n── Full evaluation on all {len(pairs['same_finger_pairs'])} pairs ──\n")

    same_results = []   # True = correctly unlocked
    diff_results = []   # True = correctly rejected (stayed locked)

    for pair in pairs["same_finger_pairs"]:
        rp  = os.path.join(root_dir, "data", pair["real"])
        ap  = os.path.join(root_dir, "data", pair["altered"])
        key = hashlib.sha256(str(pair["person"]).encode()).digest()  # deterministic per person

        vault = lock_image(rp, key)
        if not vault["valid"]:
            print(f"  [SKIP] person {pair['person']} — vault invalid")
            continue

        res = unlock_image(ap, vault, key)
        same_results.append(res["unlocked"])
        status = "✓" if res["unlocked"] else "✗"
        print(f"  [{status}] person {pair['person']:4d}  same finger  "
              f"candidates={res['candidates']:2d}  combos={res.get('combos_tried', 0):4d}")

    print()
    for pair in pairs["different_finger_pairs"]:
        fp1 = os.path.join(root_dir, "data", pair["file1"])
        fp2 = os.path.join(root_dir, "data", pair["file2"])
        pid = int(os.path.basename(pair["file1"]).split("__")[0])
        key = hashlib.sha256(str(pid).encode()).digest()

        vault = lock_image(fp1, key)
        if not vault["valid"]:
            continue

        res = unlock_image(fp2, vault, key)
        # Correct behaviour = stays locked (False)
        diff_results.append(not res["unlocked"])
        status = "✓" if not res["unlocked"] else "✗ FALSE ACCEPT"
        print(f"  [{status}] person {pid:4d}  diff finger  "
              f"candidates={res['candidates']:2d}")

    # ── Summary ───────────────────────────────────────────
    if same_results and diff_results:
        frr = 1.0 - (sum(same_results) / len(same_results))   # false reject rate
        far = 1.0 - (sum(diff_results) / len(diff_results))   # false accept rate

        print(f"\n{'='*60}")
        print(f"  RESULTS")
        print(f"{'='*60}")
        print(f"  Same-finger pairs tested  : {len(same_results)}")
        print(f"  Diff-finger pairs tested  : {len(diff_results)}")
        print(f"  Correctly unlocked (GAR)  : {sum(same_results)}/{len(same_results)}  ({(1-frr)*100:.1f}%)")
        print(f"  Correctly rejected        : {sum(diff_results)}/{len(diff_results)}  ({(1-far)*100:.1f}%)")
        print(f"  FRR (false reject rate)   : {frr*100:.1f}%")
        print(f"  FAR (false accept rate)   : {far*100:.1f}%")
        print(f"{'='*60}\n")
