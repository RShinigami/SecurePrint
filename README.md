# 🔒 SecurePrint — Encrypted Biometric Authentication

A fingerprint-based authentication system that identifies users through biometric analysis while keeping their data **private by design**. No fingerprint images are ever stored — only encrypted mathematical representations.

---

## What It Does

SecurePrint lets you **enroll** users with a fingerprint image and later **authenticate** them using a different scan of the same finger. The system processes the image, extracts unique ridge patterns, converts them into a numerical vector, encrypts it with AES-256, and stores only the encrypted result in a local SQLite database.

When authenticating, the same pipeline runs on the new image and the resulting vector is compared against all stored templates. If the similarity score is below the threshold, access is granted.

---

## How It Works

```
Fingerprint Image (.bmp / .tif)
        │
        ▼
┌───────────────────┐
│  1. Preprocessing  │  CLAHE → Binarization → Morphological cleaning → Skeletonization
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  2. Minutiae       │  Crossing Number algorithm → Ridge endings + Bifurcations
│     Extraction     │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  3. Template       │  1350-value feature vector (3 parts):
│     Generation     │  • 1128 pairwise distances (48 minutiae)
│                    │  • 190 bifurcation distances (20 bifurcations)
│                    │  • 32 spatial density map (4×4 grid by type)
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  4. Encryption     │  AES-256 (Fernet) + SHA-256 integrity hash
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  5. Storage        │  SQLite database — encrypted blob only, no image
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  6. Matching       │  Normalized Euclidean + cosine distance → Accept / Reject
└───────────────────┘
```

---

## Project Structure

```
secureprint/
├── modules/
│   ├── preprocessor.py     # Image preprocessing pipeline
│   ├── minutiae.py         # Minutiae detection (Crossing Number)
│   ├── template.py         # 1350-value feature vector generation
│   ├── encryption.py       # AES-256 encryption + SHA-256 hashing
│   ├── storage.py          # SQLite database management
│   ├── matcher.py          # Authentication logic + FAR/FRR evaluation
│   └── fuzzy_vault.py      # Fuzzy Vault Scheme (demonstration module)
├── ui/
│   └── main_window.py      # CustomTkinter GUI (enroll + authenticate)
├── tests/
│   └── diagnose.py         # Per-user score analysis tool
├── data/
│   ├── real/               # Enrollment images (not committed)
│   ├── altered/            # Authentication test images (not committed)
│   └── pairs.json          # Test pairs for FAR/FRR evaluation
├── database/
│   ├── secureprint.db      # SQLite database (not committed)
│   └── master.key          # AES master key (not committed)
├── main.py                 # Entry point (gui / enroll / evaluate)
├── setup_dataset.py        # FVC2000 dataset preparation script
├── requirements.txt
└── README.md
```

---

## Datasets

The system was developed on **SOCOFing** and validated on **FVC2000 DB1\_B** as required.

| Dataset | Resolution | Users | Impressions | Use |
|---------|-----------|-------|-------------|-----|
| [SOCOFing](https://www.kaggle.com/datasets/ruizgara/socofing) | 96×103 px | 25 | 3 alterations | Development |
| [FVC2000 DB1\_B](http://bias.csr.unibo.it/fvc2000/) | 300×300 px | 10 | 8 impressions | Validation |

---

## Getting Started

### Requirements

- Python 3.9+
- FVC2000 DB1\_B dataset (or any dataset with the `NNN_M.tif` naming convention)

### Installation

```bash
git clone https://github.com/RShinigami/SecurePrint.git
cd secureprint

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux / macOS

pip install -r requirements.txt
```

### Prepare the Dataset

```bash
python setup_dataset.py "C:/path/to/DB1_B"
```

This copies impression `_1` of each finger into `data/real/` (enrollment) and impressions `_2` through `_8` into `data/altered/` (testing), and generates `data/pairs.json`.

### Enroll Users and Run Evaluation

```bash
# Windows
set PYTHONIOENCODING=utf-8 && python modules/matcher.py

# Linux / macOS
python modules/matcher.py
```

This enrolls all users from `data/real/`, then runs a full FAR/FRR evaluation.

### Launch the GUI

```bash
# Windows
set PYTHONIOENCODING=utf-8 && python main.py

# Linux / macOS
python main.py
```

---

## Using the GUI

### Enroll Tab

1. Enter a username
2. Browse for a fingerprint image (`.bmp` or `.tif`)
3. Click **Enroll**

The system extracts minutiae, generates the feature vector, encrypts it, and stores only the encrypted result. The original image is never saved.

### Authenticate Tab

1. Browse for a fingerprint image
2. Click **Authenticate**

The system runs the full pipeline and either shows **✓ ACCESS GRANTED** with the matched username and score, or **✗ ACCESS DENIED** if no match is found.

### Testing with Multiple Databases

If you have FVC2000 DB2\_B, DB3\_B, or DB4\_B, you can enroll new users directly from the GUI:
- **Enroll** with `DBX_B/101_1.tif` under a name like `DB2_101`
- **Authenticate** with `DBX_B/101_2.tif` — should grant access
- **Authenticate** with `DBX_B/102_2.tif` — should deny (different finger)

---

## Performance

### Development — SOCOFing (96×103px, 25 users)

| Metric | Value |
|--------|-------|
| Optimal threshold (EER) | 0.35 |
| False Accept Rate (FAR) | 0% |
| False Reject Rate (FRR) | 16% |
| Accuracy | 84% |
| Wrong-user matches | 0% |
| Avg score — same finger | 0.15 |
| Avg score — different finger | 0.48 |

### Validation — FVC2000 DB1\_B (300×300px, 10 users)

| Metric | Value |
|--------|-------|
| Optimal threshold (EER) | 0.031 |
| False Accept Rate (FAR) | 17.8% |
| False Reject Rate (FRR) | 18.6% |
| Accuracy | 81.8% |
| Wrong-user matches | 0% |
| Avg score — same finger | 0.026 |
| Avg score — different finger | 0.072 |
| Score ratio (diff/same) | 2.8× |

The 0% wrong-user match rate means the system never identified the wrong person — every false accept was caught by the confidence gap check and converted to a clean rejection.

---

## Migration: SOCOFing → FVC2000

The system was originally built for SOCOFing (96×103px). Migrating to FVC2000 (300×300px) required the following changes:

| Change | Reason |
|--------|--------|
| Removed 2× upscale | FVC2000 is natively 300×300px — upscaling caused 1500–4000 noisy minutiae per image, collapsing discrimination |
| Template: 85 → 1350 values | More minutiae (48 vs 16) + bifurcation-only distances + spatial density map needed to discriminate FVC2000 fingers |
| Score normalization: 6.0 → 26.0 | Euclidean range scales with template size: √(1350×0.5) ≈ 26.0 |
| Threshold: 0.35 → 0.031 | FVC2000 scores are in a completely different range than SOCOFing scores |

---

## Privacy & Security

| Principle | Implementation |
|-----------|---------------|
| **Data minimization** | Only mathematical vectors stored, never images |
| **Non-reversibility** | Cannot reconstruct a fingerprint from pairwise distances |
| **Encryption at rest** | AES-256 via Fernet before any SQLite write |
| **Integrity check** | SHA-256 hash verified on every read |
| **Right to erasure** | `delete_user()` removes all user data (GDPR Art. 17) |
| **Local processing** | No data leaves the machine |
| **Key separation** | Encryption key stored separately from the database |

### Fuzzy Vault

The `fuzzy_vault.py` module demonstrates the **Fuzzy Vault Scheme** (Juels & Sudan, 2002). Real minutiae points are hidden among randomly generated chaff points, making the stored data useless without both the correct fingerprint and the secret key.

---

## Dependencies

```
opencv-python
numpy
scikit-learn
scikit-image
cryptography
Pillow
customtkinter
```

---

## References

- Juels, A. & Sudan, M. (2002). _A Fuzzy Vault Scheme_
- Maurya et al. (2025). _Enhancing fingerprint template security using elliptic curve cryptography_
- Maio, D. et al. (2002). _FVC2000: Fingerprint Verification Competition_. IEEE TPAMI 24(3)
- [SOCOFing Dataset](https://www.kaggle.com/datasets/ruizgara/socofing)
- [GDPR — Regulation (EU) 2016/679](https://gdpr-info.eu/)
- [ISO/IEC 27001:2022](https://www.iso.org/isoiec-27001-information-security.html)
