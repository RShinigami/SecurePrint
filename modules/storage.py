"""
Module 5 : Base de Données SQLite
Fichier : modules/storage.py

Rôle : Stocker et récupérer les templates chiffrés associés
       aux identités des utilisateurs.

Principes RGPD appliqués :
    - Aucune image stockée, seulement des templates chiffrés AES-256
    - Droit à l'oubli : delete_user() supprime toutes les données
    - Séparation : clé dans database/master.key, données dans database/secureprint.db
"""

import os
import sys
import sqlite3
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.encryption import (
    generate_master_key,
    load_master_key,
    encrypt_template,
    decrypt_template,
    compute_hash,
    verify_integrity,
)

DB_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'database')
DB_FILE = os.path.join(DB_DIR, "secureprint.db")


class SecurePrintDB:

    def __init__(self):
        os.makedirs(DB_DIR, exist_ok=True)
        self.db_path = DB_FILE
        self.key     = self._init_key()
        self.conn    = self._init_db()

    def _init_key(self):
        key = load_master_key()
        if key is None:
            key = generate_master_key()
        return key

    def _init_db(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    UNIQUE NOT NULL,
                created_at TEXT    NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                encrypted_blob  BLOB    NOT NULL,
                integrity_hash  TEXT    NOT NULL,
                finger_label    TEXT    DEFAULT 'unknown',
                created_at      TEXT    NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        # Phase 4 : table de démonstration stockage EN CLAIR (avant chiffrement)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS templates_plain (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                raw_blob     BLOB    NOT NULL,
                finger_label TEXT    DEFAULT 'unknown',
                created_at   TEXT    NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.commit()
        print(f"[OK] Base de données initialisée : {self.db_path}")
        return conn

    def enroll_user(self, name: str, template, finger_label: str = "unknown") -> tuple:
        """
        Returns (success: bool, message: str)
        If user already exists, updates their template instead of duplicating.
        """
        try:
            cursor = self.conn.cursor()
            now    = datetime.now().isoformat()

            cursor.execute("SELECT id FROM users WHERE name = ?", (name,))
            existing = cursor.fetchone()

            encrypted = encrypt_template(template, self.key)
            integrity = compute_hash(template)

            if existing:
                user_id = existing[0]
                cursor.execute("""
                    UPDATE templates SET encrypted_blob=?, integrity_hash=?, finger_label=?, created_at=?
                    WHERE user_id=?
                """, (encrypted, integrity, finger_label, now, user_id))
                self.conn.commit()
                print(f"[OK] Template mis à jour pour '{name}'")
                return True, "updated"
            else:
                cursor.execute(
                    "INSERT INTO users (name, created_at) VALUES (?, ?)",
                    (name, now)
                )
                user_id = cursor.lastrowid
                cursor.execute("""
                    INSERT INTO templates (user_id, encrypted_blob, integrity_hash, finger_label, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, encrypted, integrity, finger_label, now))
                self.conn.commit()
                print(f"[OK] Utilisateur créé et enrôlé : '{name}'")
                return True, "created"

        except Exception as e:
            print(f"[ERREUR] Enrôlement échoué pour '{name}' : {e}")
            return False, str(e)

    def get_all_templates(self) -> list:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT u.id, u.name, t.encrypted_blob, t.integrity_hash, t.finger_label
            FROM templates t
            JOIN users u ON t.user_id = u.id
        """)
        rows = cursor.fetchall()
        results = []
        for (user_id, name, blob, hash_val, finger) in rows:
            template = decrypt_template(blob, self.key)
            if template is None:
                print(f"[ATTENTION] Déchiffrement échoué pour {name}")
                continue
            if not verify_integrity(template, hash_val):
                print(f"[ATTENTION] Intégrité compromise pour {name} !")
                continue
            results.append((user_id, name, template, finger))
        return results

    def get_user_template(self, name: str):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT t.encrypted_blob, t.integrity_hash
            FROM templates t
            JOIN users u ON t.user_id = u.id
            WHERE u.name = ?
            LIMIT 1
        """, (name,))
        row = cursor.fetchone()
        if not row:
            print(f"[INFO] Aucun template trouvé pour '{name}'")
            return None
        template = decrypt_template(row[0], self.key)
        if template is None:
            return None
        if not verify_integrity(template, row[1]):
            print(f"[ATTENTION] Intégrité compromise pour '{name}' !")
            return None
        return template

    def delete_user(self, name: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM users WHERE name = ?", (name,))
        row = cursor.fetchone()
        if not row:
            print(f"[INFO] Utilisateur '{name}' introuvable")
            return False
        user_id = row[0]
        cursor.execute("DELETE FROM templates WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.conn.commit()
        print(f"[OK] Utilisateur '{name}' supprimé (droit à l'oubli RGPD ✓)")
        return True

    def list_users(self) -> list:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT u.name, u.created_at, COUNT(t.id) as nb_templates
            FROM users u
            LEFT JOIN templates t ON u.id = t.user_id
            GROUP BY u.id
        """)
        return cursor.fetchall()

    def print_summary(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        nb_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM templates")
        nb_templates = cursor.fetchone()[0]
        print(f"\n{'='*45}")
        print(f"  BASE DE DONNÉES — RÉSUMÉ")
        print(f"{'='*45}")
        print(f"  Fichier       : {self.db_path}")
        print(f"  Utilisateurs  : {nb_users}")
        print(f"  Templates     : {nb_templates}")
        print(f"  Chiffrement   : AES-256 (Fernet) ✓")
        print(f"  Clé séparée   : {os.path.abspath('database/master.key')} ✓")
        print(f"{'='*45}\n")

    # ── Phase 4 : Stockage EN CLAIR (démonstration avant chiffrement) ──────

    def enroll_user_plaintext(self, name: str, template, finger_label: str = "unknown") -> tuple:
        """
        Phase 4 — Stocke le template EN CLAIR dans templates_plain.
        Permet de visualiser que les données sont lisibles sans chiffrement.
        NE PAS utiliser en production — démonstration pédagogique uniquement.
        """
        try:
            cursor = self.conn.cursor()
            now    = datetime.now().isoformat()

            cursor.execute("SELECT id FROM users WHERE name = ?", (name,))
            existing = cursor.fetchone()
            if existing:
                user_id = existing[0]
            else:
                cursor.execute("INSERT INTO users (name, created_at) VALUES (?, ?)", (name, now))
                user_id = cursor.lastrowid

            raw_bytes = template.astype("float32").tobytes()
            cursor.execute("""
                INSERT INTO templates_plain (user_id, raw_blob, finger_label, created_at)
                VALUES (?, ?, ?, ?)
            """, (user_id, raw_bytes, finger_label, now))
            self.conn.commit()
            print(f"[Phase 4] Template EN CLAIR stocké pour '{name}' ({len(raw_bytes)} bytes)")
            print(f"          ⚠ Lisible sans clé — voir Phase 5 pour le chiffrement")
            return True, "plaintext_created"
        except Exception as e:
            print(f"[ERREUR] Stockage en clair échoué pour '{name}' : {e}")
            return False, str(e)

    def get_user_template_plaintext(self, name: str):
        """
        Phase 4 — Récupère et reconstruit le template depuis le stockage en clair.
        """
        import numpy as np
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT t.raw_blob FROM templates_plain t
            JOIN users u ON t.user_id = u.id
            WHERE u.name = ? LIMIT 1
        """, (name,))
        row = cursor.fetchone()
        if not row:
            print(f"[INFO] Aucun template en clair pour '{name}'")
            return None
        return np.frombuffer(row[0], dtype="float32").copy()

    def compare_plain_vs_encrypted(self, name: str):
        """
        Démonstration visuelle Phase 4 → Phase 5 :
        Affiche le template en clair vs chiffré pour le même utilisateur.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT t.raw_blob FROM templates_plain t
            JOIN users u ON t.user_id = u.id WHERE u.name = ? LIMIT 1
        """, (name,))
        plain_row = cursor.fetchone()

        cursor.execute("""
            SELECT t.encrypted_blob FROM templates t
            JOIN users u ON t.user_id = u.id WHERE u.name = ? LIMIT 1
        """, (name,))
        enc_row = cursor.fetchone()

        print(f"\n{'='*55}")
        print(f"  COMPARAISON STOCKAGE : '{name}'")
        print(f"{'='*55}")
        if plain_row:
            raw = plain_row[0]
            print(f"  [Phase 4] EN CLAIR   : {len(raw)} bytes")
            print(f"            Aperçu     : {raw[:20]}...  ← lisible, exploitable")
        if enc_row:
            enc = enc_row[0]
            print(f"  [Phase 5] CHIFFRÉ    : {len(enc)} bytes")
            print(f"            Aperçu     : {enc[:20]}...  ← illisible sans clé ✓")
        print(f"{'='*55}\n")

    def close(self):
        self.conn.close()