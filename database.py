import sqlite3
import os

DATABASE_NAME = 'digital_signature.db'

def initialize_database():
    """
    Menginisialisasi database SQLite, membuat tabel jika belum ada.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        # Tabel untuk menyimpan informasi dokumen dan tanda tangan
        # Menambahkan kolom 'signer_user_id' untuk merelasikan dokumen dengan pengguna yang menandatangani
        # Menambahkan kolom 'original_filename' untuk menyimpan nama file asli dari user
        # Menambahkan kolom 'publisher_name' untuk nama perusahaan/penerbit tanda tangan
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,            -- Ini akan menjadi nama file unik yang disimpan di storage
                original_filename TEXT NOT NULL,   -- Nama file asli yang diunggah oleh pengguna
                original_file_path TEXT NOT NULL,  -- Path ke file asli di storage (akan menggunakan 'filename' unik)
                document_hash TEXT NOT NULL,       -- Hash dari dokumen asli (misal: SHA256)
                public_key TEXT NOT NULL,          -- Kunci publik yang digunakan untuk verifikasi
                signature TEXT NOT NULL,           -- Tanda tangan digital
                signer_user_id TEXT NOT NULL,      -- ID pengguna yang menandatangani dokumen
                publisher_name TEXT,               -- Nama perusahaan/penerbit tanda tangan (opsional, bisa NULL)
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Tabel untuk menyimpan kunci privat (path ke file) dan publik
        # Kunci privat sekarang disimpan di file, dan path-nya disimpan di sini.
        # Dalam skenario nyata, penyimpanan kunci privat harus lebih aman (misalnya, dienkripsi atau di HSM).
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                private_key_path TEXT NOT NULL,    -- Path ke file kunci privat
                public_key TEXT NOT NULL
            )
        ''')

        # --- Tabel user_profiles untuk menyimpan nama pengguna ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY NOT NULL, -- Menggunakan user_id sebagai PK
                name TEXT NOT NULL                 -- Nama lengkap pengguna
            )
        ''')
        # --- Akhir tabel user_profiles ---

        conn.commit()
        print(f"Database '{DATABASE_NAME}' berhasil diinisialisasi.")

    except sqlite3.Error as e:
        print(f"Error saat inisialisasi database: {e}")
    finally:
        if conn:
            conn.close()

def add_sample_user_profiles(num_users=10):
    """
    Menambahkan contoh profil pengguna ke database.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        # Tambahkan user_id 'admin_signature' jika belum ada
        cursor.execute("SELECT COUNT(*) FROM user_profiles WHERE user_id = 'admin_signature'")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO user_profiles (user_id, name) VALUES (?, ?)", ('admin_signature', 'Administrator Signature'))
            print("Profil 'admin_signature' ditambahkan.")

        # Tambahkan user_id 1 sampai 10 jika belum ada
        for i in range(1, num_users + 1):
            user_id = str(i)
            user_name = f"User {i}"
            cursor.execute("SELECT COUNT(*) FROM user_profiles WHERE user_id = ?", (user_id,))
            if cursor.fetchone()[0] == 0:
                cursor.execute("INSERT INTO user_profiles (user_id, name) VALUES (?, ?)", (user_id, user_name))
                print(f"Profil '{user_name}' (ID: {user_id}) ditambahkan.")
        conn.commit()
        print(f"Total {num_users} profil pengguna sampel ditambahkan/diperbarui.")
    except sqlite3.Error as e:
        print(f"Error saat menambahkan profil pengguna sampel: {e}")
    finally:
        if conn:
            conn.close()

def get_user_name_by_id(user_id):
    """
    Mengambil nama lengkap pengguna berdasarkan user_id.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM user_profiles WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            return result[0]
        return None
    except sqlite3.Error as e:
        print(f"Error saat mengambil nama pengguna: {e}")
        return None
    finally:
        if conn:
            conn.close()

# Fungsi add_sample_keys tidak lagi relevan karena kunci akan dibuat saat dibutuhkan
# atau diinisialisasi untuk admin_signature di app.py
def add_sample_keys():
    """
    Fungsi ini tidak lagi digunakan secara langsung.
    Kunci akan dibuat saat dibutuhkan atau diinisialisasi untuk admin_signature di app.py.
    """
    pass


if __name__ == "__main__":
    initialize_database()
    add_sample_user_profiles(10) # Panggil fungsi untuk menambahkan profil pengguna sampel
    # Contoh penggunaan fungsi baru
    # print(f"Nama untuk user_id '1': {get_user_name_by_id('1')}")
    # print(f"Nama untuk user_id 'admin_signature': {get_user_name_by_id('admin_signature')}")
