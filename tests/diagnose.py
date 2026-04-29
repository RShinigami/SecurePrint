"""
tests/diagnose.py — Diagnostic complet par utilisateur
Usage: python tests/diagnose.py
"""
import sys, os, io, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from contextlib import redirect_stdout
from modules.storage import SecurePrintDB
from modules.template import generate_template
from modules.matcher import combined_score, DEFAULT_THRESHOLD, MIN_GAP

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

db = SecurePrintDB()
all_t = {name: t for (_, name, t, _) in db.get_all_templates()}

with open(os.path.join(root, 'data', 'pairs.json')) as f:
    pairs = json.load(f)

print(f"\nThreshold={DEFAULT_THRESHOLD}  MIN_GAP={MIN_GAP}")
print(f"Users in DB: {list(all_t.keys())}\n")

# ── Same finger: all altered per user ──────────────────────────────
print("=== SAME FINGER (enrolled vs altered) ===")
same_scores = []
for p in pairs['same_finger_pairs']:
    name = f"User_{p['person']}"
    tr = all_t.get(name)
    alt_path = os.path.join(root, 'data', p['altered'])
    with redirect_stdout(io.StringIO()):
        ta = generate_template(alt_path)
    if tr is None or ta is None:
        continue
    s = combined_score(tr, ta)
    same_scores.append(s)
    status = 'GRANT' if s < DEFAULT_THRESHOLD else 'REJECT'
    print(f"  {name} | {os.path.basename(alt_path):12} | score={s:.4f} | {status}")

# ── Different fingers ───────────────────────────────────────────────
print("\n=== DIFFERENT FINGERS (cross-user) ===")
diff_scores = []
for p in pairs['different_finger_pairs']:
    n1 = 'User_' + os.path.splitext(os.path.basename(p['file1']))[0].split('_')[0]
    n2 = 'User_' + os.path.splitext(os.path.basename(p['file2']))[0].split('_')[0]
    t1, t2 = all_t.get(n1), all_t.get(n2)
    if t1 is None or t2 is None:
        continue
    s = combined_score(t1, t2)
    diff_scores.append(s)
    status = 'FALSE_ACCEPT' if s < DEFAULT_THRESHOLD else 'ok'
    if status == 'FALSE_ACCEPT':
        print(f"  {n1} vs {n2} | score={s:.4f} | {status}")

import numpy as np
print(f"\n=== SUMMARY ===")
print(f"Same  : n={len(same_scores)} mean={np.mean(same_scores):.4f} min={min(same_scores):.4f} max={max(same_scores):.4f}")
print(f"Diff  : n={len(diff_scores)} mean={np.mean(diff_scores):.4f} min={min(diff_scores):.4f} max={max(diff_scores):.4f}")
frr = sum(1 for s in same_scores if s >= DEFAULT_THRESHOLD) / len(same_scores)
far = sum(1 for s in diff_scores if s <  DEFAULT_THRESHOLD) / len(diff_scores)
print(f"FAR={far*100:.1f}%  FRR={frr*100:.1f}%  Accuracy={((1-far+1-frr)/2)*100:.1f}%")

db.close()
