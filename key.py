from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import sqlite3
import os

DATABASE_NAME = 'digital_signature.db'
PRIVATE_KEYS_DIR = 'private_keys' # Direktori untuk menyimpan file kunci privat

# Pastikan direktori penyimpanan kunci privat ada
if not os.path.exists(PRIVATE_KEYS_DIR):
    os.makedirs(PRIVATE_KEYS_DIR)

def generate_key_pair(user_id):
    """
    Menghasilkan pasangan kunci RSA (privat dan publik) dan menyimpan kunci privat ke file.
    Mengembalikan path file kunci privat dan konten kunci publik.
    """
    try:
        # Menghasilkan kunci privat RSA
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048, # Ukuran kunci yang umum dan aman
            backend=default_backend()
        )

        # Menserialisasi kunci privat ke format PEM dan menyimpannya ke file
        private_key_filename = f"{user_id}_private_key.pem"
        private_key_path = os.path.join(PRIVATE_KEYS_DIR, private_key_filename)

        with open(private_key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption() # TIDAK ADA ENKRIPSI UNTUK DEMO!
                                                                  # Dalam produksi, gunakan kunci sandi kuat
            ))
        print(f"Kunci privat untuk '{user_id}' disimpan di: {private_key_path}")

        # Menghasilkan kunci publik dari kunci privat dan menserialisasinya ke format PEM
        public_key = private_key.public_key()
        pem_public_key = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')

        return private_key_path, pem_public_key
    except Exception as e:
        print(f"Error saat menghasilkan pasangan kunci: {e}")
        return None, None

def save_key_pair(user_id, private_key_path, public_key_pem):
    """
    Menyimpan path kunci privat dan kunci publik ke database.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO keys (user_id, private_key_path, public_key)
            VALUES (?, ?, ?)
        ''', (user_id, private_key_path, public_key_pem))
        conn.commit()
        print(f"Informasi kunci untuk '{user_id}' berhasil disimpan di database.")
        return True
    except sqlite3.Error as e:
        print(f"Error saat menyimpan informasi kunci: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_private_key_path(user_id):
    """
    Mengambil path kunci privat dari database.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT private_key_path FROM keys WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            return result[0]
        return None
    except sqlite3.Error as e:
        print(f"Error saat mengambil path kunci privat: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_private_key_content(user_id):
    """
    Mengambil konten kunci privat dari file berdasarkan user_id.
    """
    private_key_path = get_private_key_path(user_id)
    if not private_key_path or not os.path.exists(private_key_path):
        print(f"Error: File kunci privat untuk '{user_id}' tidak ditemukan di '{private_key_path}'.")
        return None
    try:
        with open(private_key_path, "rb") as f:
            return f.read().decode('utf-8')
    except Exception as e:
        print(f"Error saat membaca file kunci privat: {e}")
        return None

def get_public_key(user_id):
    """
    Mengambil kunci publik dari database.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT public_key FROM keys WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            return result[0]
        return None
    except sqlite3.Error as e:
        print(f"Error saat mengambil kunci publik: {e}")
        return None
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Pastikan database sudah diinisialisasi
    from database import initialize_database
    initialize_database()

    test_user_id = "test_user_key" # Contoh ID pengguna
    print(f"\nMenghasilkan dan menyimpan kunci untuk {test_user_id}...")
    priv_key_path, pub_key_pem = generate_key_pair(test_user_id)
    if priv_key_path and pub_key_pem:
        save_key_pair(test_user_id, priv_key_path, pub_key_pem)

        # Coba ambil kunci privat dan publik
        retrieved_priv_key_content = get_private_key_content(test_user_id)
        retrieved_pub_key = get_public_key(test_user_id)

        print("\nKunci berhasil diambil (seharusnya sama dengan yang dihasilkan):")
        # Untuk keamanan, jangan cetak kunci privat secara langsung di produksi
        # print("Private Key Content (sebagian):", retrieved_priv_key_content[:50] + "...")
        # print("Public Key (sebagian):", retrieved_pub_key[:50] + "...")
        
        # Verifikasi bahwa file kunci privat benar-benar ada
        if os.path.exists(priv_key_path):
            print(f"File kunci privat ditemukan di: {priv_key_path}")
        else:
            print(f"ERROR: File kunci privat TIDAK ditemukan di: {priv_key_path}")

    # Membersihkan file kunci privat yang dibuat untuk pengujian (opsional)
    # if priv_key_path and os.path.exists(priv_key_path):
    #     os.remove(priv_key_path)
    #     print(f"File kunci privat '{priv_key_path}' dihapus.")
