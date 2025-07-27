import hashlib
import os
import sqlite3
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
# Mengimpor fungsi yang diperbarui dari key.py
from key import get_private_key_content, get_public_key

import qrcode # Import pustaka qrcode
import io     # Import io untuk menangani data biner di memori
import base64 # Import base64 untuk encoding gambar

DATABASE_NAME = 'digital_signature.db'
STORAGE_DIR = 'uploaded_files' # Direktori untuk menyimpan file asli

# Pastikan direktori penyimpanan ada
if not os.path.exists(STORAGE_DIR):
    os.makedirs(STORAGE_DIR)

def calculate_file_hash(filepath, hash_algorithm="sha256", chunk_size=4096):
    """
    Menghitung hash (checksum) dari sebuah file.
    Args:
        filepath (str): Path lengkap ke file.
        hash_algorithm (str): Algoritma hash yang akan digunakan (misal: "md5", "sha1", "sha256", "sha512").
        chunk_size (int): Ukuran chunk (dalam byte) untuk membaca file.
    Returns:
        str: Nilai hash heksadesimal dari file, atau None jika file tidak ditemukan.
    """
    if not os.path.exists(filepath):
        print(f"Error: File tidak ditemukan di '{filepath}'")
        return None

    try:
        hasher = hashlib.new(hash_algorithm)
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        print(f"Terjadi kesalahan saat menghitung hash file: {e}")
        return None

def sign_document(document_path, user_id):
    """
    Menandatangani dokumen menggunakan kunci privat pengguna.
    Args:
        document_path (str): Path ke dokumen yang akan ditandatangani.
        user_id (str): ID pengguna yang akan menandatangani dokumen.
    Returns:
        tuple: (signature_hex, doc_hash) jika berhasil, (None, None) jika gagal.
    """
    # Mengambil konten kunci privat dari file
    private_key_pem_content = get_private_key_content(user_id)
    if not private_key_pem_content:
        print(f"Error: Kunci privat untuk user '{user_id}' tidak ditemukan atau tidak dapat dibaca.")
        return None, None

    try:
        # Load kunci privat dari konten PEM
        private_key = serialization.load_pem_private_key(
            private_key_pem_content.encode('utf-8'),
            password=None, # Tidak ada password untuk demo ini
            backend=default_backend()
        )

        # Hitung hash dokumen
        doc_hash = calculate_file_hash(document_path, "sha256")
        if not doc_hash:
            return None, None

        # Konversi hash ke bytes untuk ditandatangani
        hashed_data = bytes.fromhex(doc_hash)

        # Lakukan tanda tangan digital
        signature = private_key.sign(
            hashed_data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return signature.hex(), doc_hash # Mengembalikan signature dalam format heksadesimal
    except Exception as e:
        print(f"Error saat menandatangani dokumen: {e}")
        return None, None

def verify_signature(document_path, public_key_pem, signature_hex):
    """
    Memverifikasi tanda tangan digital menggunakan kunci publik.
    Args:
        document_path (str): Path ke dokumen yang akan diverifikasi.
        public_key_pem (str): Konten kunci publik dalam format PEM.
        signature_hex (str): Tanda tangan digital dalam format heksadesimal.
    Returns:
        bool: True jika verifikasi berhasil, False jika gagal.
    """
    try:
        # Load kunci publik dari konten PEM
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode('utf-8'),
            backend=default_backend()
        )

        # Hitung hash dokumen
        doc_hash = calculate_file_hash(document_path, "sha256")
        if not doc_hash:
            return False

        # Konversi hash dan signature dari hex ke bytes
        hashed_data = bytes.fromhex(doc_hash)
        signature = bytes.fromhex(signature_hex)

        # Lakukan verifikasi
        public_key.verify(
            signature,
            hashed_data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True # Verifikasi berhasil
    except Exception as e:
        print(f"Verifikasi gagal: {e}")
        return False # Verifikasi gagal

def save_document_info(filename_on_storage, original_filename, original_file_path, document_hash, public_key_pem, signature_hex, signer_user_id, publisher_name):
    """
    Menyimpan informasi dokumen dan tanda tangan ke database.
    Args:
        filename_on_storage (str): Nama file unik yang disimpan di storage.
        original_filename (str): Nama file asli yang diunggah oleh pengguna.
        original_file_path (str): Path lengkap ke file di storage.
        document_hash (str): Hash dari dokumen asli.
        public_key_pem (str): Kunci publik yang digunakan untuk verifikasi.
        signature_hex (str): Tanda tangan digital.
        signer_user_id (str): ID pengguna yang menandatangani dokumen.
        publisher_name (str): Nama perusahaan/penerbit tanda tangan.
    Returns:
        int: ID dokumen yang baru disimpan, atau None jika gagal.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO documents (filename, original_filename, original_file_path, document_hash, public_key, signature, signer_user_id, publisher_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (filename_on_storage, original_filename, original_file_path, document_hash, public_key_pem, signature_hex, signer_user_id, publisher_name))
        conn.commit()
        print(f"Informasi dokumen '{original_filename}' (disimpan sebagai '{filename_on_storage}') oleh '{signer_user_id}' berhasil disimpan.")
        return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"Error saat menyimpan informasi dokumen: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_document_info(doc_id=None, filename=None):
    """
    Mengambil informasi dokumen dari database berdasarkan ID atau nama file unik di storage.
    Args:
        doc_id (int, optional): ID dokumen.
        filename (str, optional): Nama file unik di storage.
    Returns:
        dict: Informasi dokumen sebagai dictionary, atau None jika tidak ditemukan.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        if doc_id:
            cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        elif filename:
            # Mencari berdasarkan nama file unik di storage
            cursor.execute("SELECT * FROM documents WHERE filename = ?", (filename,))
        else:
            return None

        result = cursor.fetchone()
        if result:
            # Mengembalikan data sebagai dictionary untuk kemudahan akses
            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, result))
        return None
    except sqlite3.Error as e:
        print(f"Error saat mengambil informasi dokumen: {e}")
        return None
    finally:
        if conn:
            conn.close()

def generate_qr_code_for_doc_info(document_id, base_url):
    """
    Menghasilkan QR code yang mengarah ke endpoint get_signature_info untuk dokumen tertentu.
    Args:
        document_id (int): ID dokumen.
        base_url (str): URL dasar API (misal: "http://localhost:5000").
    Returns:
        str: Gambar QR code dalam format Base64 (PNG), atau None jika gagal.
    """
    try:
        # URL yang akan di-encode ke QR code
        info_url = f"{base_url}/get_signature_info?document_id={document_id}"
        
        # Membuat objek QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(info_url)
        qr.make(fit=True)

        # Membuat gambar QR code
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Menyimpan gambar ke buffer memori
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        
        # Mengencode gambar ke Base64
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return img_str
    except Exception as e:
        print(f"Error saat menghasilkan QR code: {e}")
        return None

if __name__ == "__main__":
    # Pastikan database sudah diinisialisasi
    from database import initialize_database
    initialize_database()

    # Pastikan ada kunci untuk user 'admin_signature'
    from key import generate_key_pair, save_key_pair
    test_user_id = "admin_signature"
    # Cek apakah kunci privat untuk user ini sudah ada di file
    if not get_private_key_content(test_user_id):
        print(f"Kunci untuk '{test_user_id}' belum ada. Menghasilkan dan menyimpan...")
        priv_key_path, pub_key = generate_key_pair(test_user_id)
        if priv_key_path and pub_key:
            save_key_pair(test_user_id, priv_key_path, pub_key)
        else:
            print("Gagal menghasilkan kunci. Keluar.")
            exit()

    # --- Contoh Penggunaan ---

    # 1. Buat file dummy
    original_dummy_file_name = "contoh_dokumen_generate_v2.txt"
    # Kita akan membuat nama file unik untuk penyimpanan
    import uuid
    stored_dummy_file_name = f"{uuid.uuid4()}_{original_dummy_file_name}"
    dummy_file_path = os.path.join(STORAGE_DIR, stored_dummy_file_name)

    with open(dummy_file_path, "w") as f:
        f.write("Ini adalah isi dokumen yang akan ditandatangani secara digital.\n")
        f.write("Baris kedua dari dokumen untuk pengujian generate.py.\n")
    print(f"\nFile dummy '{original_dummy_file_name}' dibuat (disimpan sebagai '{stored_dummy_file_name}').")

    # 2. Tandatangani dokumen
    print(f"\nMenandatangani dokumen '{original_dummy_file_name}' dengan user '{test_user_id}'...")
    signature_hex, doc_hash = sign_document(dummy_file_path, test_user_id)
    public_key_signer = get_public_key(test_user_id)

    if signature_hex and doc_hash and public_key_signer:
        print(f"Dokumen berhasil ditandatangani. Hash: {doc_hash[:10]}... Signature: {signature_hex[:10]}...")

        # 3. Simpan informasi tanda tangan ke database
        # Menambahkan original_filename dan menggunakan filename_on_storage
        doc_db_id = save_document_info(
            stored_dummy_file_name, original_dummy_file_name, dummy_file_path,
            doc_hash, public_key_signer, signature_hex, test_user_id, "Contoh Perusahaan" # Menambahkan publisher_name
        )
        if doc_db_id:
            print(f"Informasi tanda tangan disimpan dengan ID: {doc_db_id}")

            # 4. Ambil informasi dokumen dari database
            print(f"\nMengambil informasi dokumen dengan ID {doc_db_id}...")
            retrieved_doc_info = get_document_info(doc_id=doc_db_id)
            if retrieved_doc_info:
                print("Informasi dokumen yang diambil:")
                for key, value in retrieved_doc_info.items():
                    print(f"  {key}: {value[:50]}..." if isinstance(value, str) and len(value) > 50 else f"  {key}: {value}")

                # 5. Verifikasi tanda tangan (menggunakan stored_filename untuk path)
                print("\nMelakukan verifikasi tanda tangan...")
                is_valid = verify_signature(
                    retrieved_doc_info['original_file_path'], # Ini akan merujuk ke path dengan nama unik
                    retrieved_doc_info['public_key'],
                    retrieved_doc_info['signature']
                )
                print(f"Verifikasi tanda tangan: {'BERHASIL' if is_valid else 'GAGAL'}")

                # 6. Coba modifikasi file dan verifikasi lagi (akan gagal)
                print("\nMemodifikasi file dan mencoba verifikasi ulang (seharusnya GAGAL)...")
                with open(dummy_file_path, "a") as f: # Tambahkan sesuatu ke file
                    f.write("\nIni adalah baris yang dimodifikasi.")
                is_valid_after_mod = verify_signature(
                    retrieved_doc_info['original_file_path'],
                    retrieved_doc_info['public_key'],
                    retrieved_doc_info['signature']
                )
                print(f"Verifikasi tanda tangan setelah modifikasi: {'BERHASIL' if is_valid_after_mod else 'GAGAL'}")
            
            # 7. Contoh pembuatan QR Code
            base_url_example = "http://localhost:5000" # Ganti dengan URL API Anda
            qr_code_base64 = generate_qr_code_for_doc_info(doc_db_id, base_url_example)
            if qr_code_base64:
                print("\nQR Code Base64 (sebagian):", qr_code_base64[:50] + "...")
            else:
                print("\nGagal membuat QR Code.")

    # Menghapus file dummy setelah pengujian (opsional)
    # if os.path.exists(dummy_file_path):
    #     os.remove(dummy_file_path)
    #     print(f"File dummy '{stored_dummy_file_name}' dihapus.")
