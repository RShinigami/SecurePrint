import sys, os, io, json
sys.path.insert(0, '.')
from contextlib import redirect_stdout
import numpy as np

from modules.storage import SecurePrintDB
from modules.matcher import enroll_all, combined_score

# Wipe and re-enroll
db = SecurePrintDB()
db.conn.execute('DELETE FROM templates')
db.conn.execute('DELETE FROM users')
db.conn.commit()
print("DB cleared. Re-enrolling...")
with redirect_stdout(io.StringIO()):
    enroll_all(db)
print("Done.\n")

all_t = db.get_all_templates()

with open('data/pairs.json') as f:
    pairs = json.load(f)

same_scores, diff_scores = [], []

for pair in pairs['same_finger_pairs']:
    altered_path = os.path.join('data', pair['altered'])
    name = f"User_{pair['person']}"
    db_entry = next((t for _, n, t, _ in all_t if n == name), None)
    with redirect_stdout(io.StringIO()):
        from modules.template import generate_template
        q = generate_template(altered_path)
    if db_entry is not None and q is not None:
        s = combined_score(q, db_entry)
        same_scores.append((s, name))

for pair in pairs['different_finger_pairs']:
    name1 = f"User_{os.path.basename(pair['file1']).split('__')[0]}"
    name2 = f"User_{os.path.basename(pair['file2']).split('__')[0]}"
    t1 = next((t for _, n, t, _ in all_t if n == name1), None)
    t2 = next((t for _, n, t, _ in all_t if n == name2), None)
    if t1 is not None and t2 is not None:
        diff_scores.append(combined_score(t1, t2))

ss = [s for s, _ in same_scores]
ds = diff_scores

print("=== SAME FINGER ===")
for s, n in sorted(same_scores):
    print(f"  {s:.4f}  {n}")

print(f"\nSame  mean={np.mean(ss):.4f}  min={min(ss):.4f}  max={max(ss):.4f}")
print(f"Diff  mean={np.mean(ds):.4f}  min={min(ds):.4f}  max={max(ds):.4f}")
print(f"Suggested threshold: {(np.mean(ss) + np.mean(ds)) / 2:.4f}")

# Count correct at suggested threshold
t = (np.mean(ss) + np.mean(ds)) / 2
frr = sum(1 for s in ss if s >= t) / len(ss)
far = sum(1 for s in ds if s <  t) / len(ds)
print(f"At threshold {t:.4f}:  FAR={far*100:.1f}%  FRR={frr*100:.1f}%  Accuracy={100-(far+frr)*50:.1f}%")

db.close()
