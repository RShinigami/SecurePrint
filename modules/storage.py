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

DB_DIR  = "database"
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
        conn.commit()
        print(f"[OK] Base de données initialisée : {self.db_path}")
        return conn

    def enroll_user(self, name: str, template, finger_label: str = "unknown") -> bool:
        try:
            cursor = self.conn.cursor()
            now    = datetime.now().isoformat()

            cursor.execute("SELECT id FROM users WHERE name = ?", (name,))
            existing = cursor.fetchone()

            if existing:
                user_id = existing[0]
                print(f"[INFO] Utilisateur '{name}' déjà existant (id={user_id})")
            else:
                cursor.execute(
                    "INSERT INTO users (name, created_at) VALUES (?, ?)",
                    (name, now)
                )
                user_id = cursor.lastrowid
                print(f"[OK] Utilisateur créé : '{name}' (id={user_id})")

            encrypted = encrypt_template(template, self.key)
            integrity = compute_hash(template)

            cursor.execute("""
                INSERT INTO templates (user_id, encrypted_blob, integrity_hash, finger_label, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, encrypted, integrity, finger_label, now))

            self.conn.commit()
            print(f"[OK] Template enrôlé pour '{name}' — doigt: {finger_label}")
            print(f"     Taille chiffrée : {len(encrypted)} bytes")
            return True

        except Exception as e:
            print(f"[ERREUR] Enrôlement échoué pour '{name}' : {e}")
            return False

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

    def close(self):
        self.conn.close()