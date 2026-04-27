# SecurePrint

# 🔒 SecurePrint — Encrypted Biometric Authentication

A fingerprint-based authentication system that identifies users through biometric analysis while keeping their data **private by design**. No fingerprint images are ever stored — only encrypted mathematical representations.

---

## What It Does

SecurePrint lets you **enroll** users with a fingerprint image and later **authenticate** them using a different scan of the same finger. The system processes the image, extracts unique ridge patterns, converts them into a numerical vector, encrypts it with AES-256, and stores only the encrypted result in a local SQLite database.

When authenticating, the same pipeline runs on the new image and the resulting vector is compared against all stored templates. If the similarity score is below the threshold, access is granted.

---

## How It Works

```
Fingerprint Image (.bmp)
        │
        ▼
┌───────────────────┐
│  1. Preprocessing  │  2x Upscale → CLAHE → Binarization → Morphological cleaning → Skeletonization
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
│  3. Template       │  Normalized 85-value feature vector
│     Generation     │  (64 position+angle values + 21 pairwise distances)
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
│  6. Matching       │  Combined cosine + euclidean distance → Accept / Reject
└───────────────────┘
```

---

## Project Structure

```
secureprint/
├── modules/
│   ├── preprocessor.py     # Image preprocessing pipeline
│   ├── minutiae.py         # Minutiae detection (Crossing Number)
│   ├── template.py         # Feature vector generation
│   ├── encryption.py       # AES-256 encryption + SHA-256 hashing
│   ├── storage.py          # SQLite database management
│   ├── matcher.py          # Authentication logic + FAR/FRR evaluation
│   └── fuzzy_vault.py      # Fuzzy Vault Scheme (demonstration module)
├── ui/
│   └── main_window.py      # Tkinter GUI (enroll + authenticate)
├── data/
│   ├── real/               # Original fingerprint images (not committed)
│   ├── altered/            # Altered versions for testing (not committed)
│   └── pairs.json          # Test pairs for FAR/FRR evaluation
├── database/
│   ├── secureprint.db      # SQLite database with 2 tables:
│   │                       #   templates       — AES-256 encrypted blobs (production)
│   │                       #   templates_plain — raw blobs for Phase 4 demo only
│   └── master.key          # AES master key (not committed)
├── setup_dataset.py        # SOCOFing dataset preparation script
├── requirements.txt
└── README.md
```

---

## Getting Started

### Requirements

- Python 3.9+
- A fingerprint dataset — we used [SOCOFing](https://www.kaggle.com/datasets/ruizgara/socofing) (free on Kaggle)

### Installation

```bash
git clone https://github.com/your-username/secureprint.git
cd secureprint

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux / macOS

pip install -r requirements.txt
```

### Prepare the Dataset

Download SOCOFing from Kaggle, extract it, then run:

```bash
python setup_dataset.py "path/to/SOCOFing"
```

This selects 25 diverse fingerprints from the Real folder and their altered counterparts, and saves them into `data/real/` and `data/altered/`.

### Enroll Users and Run Evaluation

```bash
# Windows — set UTF-8 encoding to avoid console errors
set PYTHONIOENCODING=utf-8 && python modules/matcher.py

# Linux / macOS
python modules/matcher.py
```

This enrolls all 25 users from `data/real/` into both the encrypted table (`templates`) and the plaintext demo table (`templates_plain`), then runs a full FAR/FRR evaluation using the altered images.

### Launch the GUI

```bash
# Windows
set PYTHONIOENCODING=utf-8 && python ui/main_window.py

# Linux / macOS
python ui/main_window.py
```

---

## Using the GUI

### Enroll Tab

1. Enter a username
2. Browse for a fingerprint image (`.bmp`)
3. Click **Enroll**

The system extracts minutiae, generates the feature vector, encrypts it, and stores only the encrypted result. The original image is never saved.

### Authenticate Tab

1. Browse for a fingerprint image
2. Click **Authenticate**

The system runs the full pipeline and either shows **✓ ACCESS GRANTED** with the matched username and similarity score, or **✗ ACCESS DENIED** if no match is found.

---

## Performance

Evaluated on SOCOFing (96×103px images, 25 users):

| Metric                       | Value |
| ---------------------------- | ----- |
| Optimal threshold (EER)      | 0.35  |
| False Accept Rate (FAR)      | 0%    |
| False Reject Rate (FRR)      | 16%   |
| Accuracy                     | 84%   |
| Wrong-user matches           | 0%    |
| Avg score — same finger      | 0.15  |
| Avg score — different finger | 0.48  |

The gap between same-finger scores (0.15) and different-finger scores (0.48) confirms strong identity discrimination. Accuracy improved from 72% to 84% after adding 2× upscaling and morphological cleaning to the preprocessing pipeline. The system **prefers rejection over misidentification** — when confidence is low (gap < 0.05 between top two candidates), access is denied rather than risking a wrong match. The remaining 16% FRR is a direct consequence of the low image resolution — commercial AFIS systems use 500dpi sensors producing images 10× larger.

---

## Privacy & Security

| Principle              | Implementation                                           |
| ---------------------- | -------------------------------------------------------- |
| **Data minimization**  | Only mathematical vectors stored, never images           |
| **Non-reversibility**  | Cannot reconstruct a fingerprint from its feature vector |
| **Encryption at rest** | AES-256 via Fernet before any SQLite write               |
| **Integrity check**    | SHA-256 hash verified on every read                      |
| **Right to erasure**   | `delete_user()` removes all user data (GDPR Art. 17)     |
| **Local processing**   | No data leaves the machine                               |
| **Key separation**     | Encryption key stored separately from the database       |

### Fuzzy Vault

The `fuzzy_vault.py` module demonstrates the **Fuzzy Vault Scheme** (Juels & Sudan, 2002). Real minutiae points are hidden among randomly generated fake points (_chaff points_), making the stored data useless without both the correct fingerprint and the secret key. On high-resolution images, this mechanism would act as a strong cryptographic lock on top of AES encryption.

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
- [SOCOFing Dataset](https://www.kaggle.com/datasets/ruizgara/socofing)
- [GDPR — Regulation (EU) 2016/679](https://gdpr-info.eu/)
- [ISO/IEC 27001:2022](https://www.iso.org/isoiec-27001-information-security.html)
