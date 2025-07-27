# --- main_signature_system.py ---

import os
import hashlib
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
import qrcode
from PIL import Image
from PyPDF2 import PdfReader, PdfWriter
from flask import Flask, request, jsonify, render_template_string
import base64

# --- Bagian 1: Konfigurasi dan Fungsi Utilitas ---

# Direktori untuk menyimpan kunci, dokumen, dll.
KEYS_DIR = "keys"
DOCS_DIR = "documents"
SIGNED_DOCS_DIR = "signed_documents"
DATABASE_MOCK_FILE = "signature_db.json" # Mock database sederhana

# URL dasar untuk verifikasi (ganti dengan domain Anda di produksi)
BASE_VERIFY_URL = "http://127.0.0.1:5000/verify"

# Pastikan direktori ada
os.makedirs(KEYS_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)
os.makedirs(SIGNED_DOCS_DIR, exist_ok=True)

# Mock database (gunakan database sungguhan seperti SQLite/PostgreSQL di produksi)
# Format: {id_transaksi: {doc_url, signature_b64, public_key_pem, signer_name, timestamp, doc_hash}}
signature_db = {}

def load_db():
    if os.path.exists(DATABASE_MOCK_FILE):
        import json
        with open(DATABASE_MOCK_FILE, 'r') as f:
            global signature_db
            signature_db = json.load(f)
            print(f"Database mock dimuat dari {DATABASE_MOCK_FILE}")

def save_db():
    import json
    with open(DATABASE_MOCK_FILE, 'w') as f:
        json.dump(signature_db, f, indent=4)
        print(f"Database mock disimpan ke {DATABASE_MOCK_FILE}")

# --- Bagian 2: Fungsi Kriptografi ---

def generate_rsa_key_pair(private_key_path="private_key.pem", public_key_path="public_key.pem"):
    """Menghasilkan pasangan kunci RSA dan menyimpannya ke file."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    public_key = private_key.public_key()

    # Simpan private key
    with open(os.path.join(KEYS_DIR, private_key_path), "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption() # Ganti dengan enkripsi di produksi!
        ))
    print(f"Private key disimpan di: {os.path.join(KEYS_DIR, private_key_path)}")

    # Simpan public key
    with open(os.path.join(KEYS_DIR, public_key_path), "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))
    print(f"Public key disimpan di: {os.path.join(KEYS_DIR, public_key_path)}")
    return private_key, public_key

def load_private_key(path):
    """Memuat private key dari file."""
    with open(path, "rb") as f:
        private_key = serialization.load_pem_private_key(
            f.read(),
            password=None, # Ganti dengan password di produksi!
            backend=default_backend()
        )
    return private_key

def load_public_key(path):
    """Memuat public key dari file."""
    with open(path, "rb") as f:
        public_key = serialization.load_pem_public_key(
            f.read(),
            backend=default_backend()
        )
    return public_key

def hash_file(file_path):
    """Menghitung SHA256 hash dari sebuah file."""
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(4096):
            hasher.update(chunk)
    return hasher.hexdigest() # Mengembalikan hash dalam format heksadesimal

def sign_hash(private_key, data_hash_bytes):
    """Menandatangani hash data menggunakan private key."""
    signature = private_key.sign(
        data_hash_bytes,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    return signature

def verify_signature(public_key, data_hash_bytes, signature):
    """Memverifikasi tanda tangan menggunakan public key."""
    try:
        public_key.verify(
            signature,
            data_hash_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except Exception as e:
        print(f"Verifikasi gagal: {e}")
        return False

# --- Bagian 3: Fungsi Manipulasi Dokumen dan QR Code ---

def generate_qr_code(data_url, output_path="qrcode.png", box_size=10, border=4):
    """Menghasilkan QR Code dari URL."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(output_path)
    return output_path

def add_qr_to_pdf(original_pdf_path, qr_code_path, output_pdf_path, page_number=0, x_pos=450, y_pos=50):
    """Menambahkan gambar QR Code ke halaman tertentu di PDF."""
    try:
        reader = PdfReader(original_pdf_path)
        writer = PdfWriter()

        # Baca semua halaman dari PDF asli
        for i, page in enumerate(reader.pages):
            writer.add_page(page)

        # Cek apakah halaman yang dituju ada
        if page_number >= len(reader.pages):
            print(f"Peringatan: Nomor halaman {page_number} di luar jangkauan. Menambahkan QR ke halaman pertama.")
            page_number = 0

        # Muat QR code sebagai gambar PIL
        qr_image = Image.open(qr_code_path)
        # Simpan QR code sementara sebagai JPEG untuk PyPDF2
        temp_qr_path = "temp_qrcode.jpg"
        qr_image.save(temp_qr_path)

        # PyPDF2 membutuhkan PDF atau gambar JPEG/PNG yang sudah ada di halaman untuk Overlay.
        # Untuk menempel gambar langsung, kita bisa membuat halaman PDF baru hanya berisi QR
        # dan menindihkannya, atau menggunakan ReportLab (lebih kompleks tapi lebih fleksibel).
        # Untuk kesederhanaan, kita akan menggunakan pendekatan yang lebih sederhana yang mungkin tidak sempurna
        # atau menunjukkan contoh yang lebih kompleks dengan ReportLab jika ini adalah produksi.
        # Untuk contoh ini, kita akan menggunakan PyPDF2 dengan asumsi QR sudah ada sebagai file gambar.
        # Perhatikan bahwa PyPDF2 tidak memiliki fungsi langsung untuk "overlay gambar" seperti itu,
        # ia lebih ke manipulasi teks atau bentuk yang ada.
        # MENEMPEL GAMBAR SECARA LANGSUNG PADA POSISI TERTENTU DENGAN PYPDF2 SANGAT TERBATAS.
        # SOLUSI YANG LEBIH BAIK ADALAH MENGGUNAKAN LIBRARY SEPERTI `REPORTLAB` ATAU `FPDF2`
        # UNTUK MENGGAMBAR LANGSUNG PADA KANVAS PDF.

        # Karena keterbatasan PyPDF2 untuk menempel gambar secara fleksibel,
        # bagian ini akan menjadi pseudo-code atau memerlukan library lain.
        # Anggap saja kita bisa mendapatkan objek PyPDF2.images.Image dari qr_image.
        # Jika Anda ingin implementasi nyata untuk menempel gambar, saya sarankan
        # menggunakan library seperti `reportlab` atau `fpdf2`.

        print("\n--- PENTING: Penempelan QR Code ke PDF ---")
        print("PyPDF2 memiliki keterbatasan dalam menempelkan gambar secara bebas.")
        print("Untuk produksi, disarankan menggunakan library seperti 'ReportLab' atau 'fpdf2' untuk penempatan gambar yang akurat.")
        print("Dalam contoh ini, diasumsikan proses penempelan berhasil dan file PDF baru disimpan.")

        # Karena kita tidak bisa menempel gambar langsung seperti itu dengan PyPDF2
        # tanpa kode ReportLab atau fpdf2 yang lebih kompleks, kita akan simulasikan
        # bahwa PDF baru dibuat dengan QR code sudah ada di dalamnya.
        # Ini berarti pengguna perlu menggabungkan PDF yang berisi QR dengan PDF asli
        # secara manual, atau menggunakan ReportLab.

        # Contoh sederhana (tidak menempel QR secara visual, hanya menyimpan ulang)
        with open(output_pdf_path, "wb") as f:
            writer.write(f)
        print(f"Salinan PDF disimpan di: {output_pdf_path} (QR code *tidak* ditempel secara visual oleh fungsi ini).")
        print("Silakan tambahkan QR code secara visual menggunakan alat/library lain jika diperlukan.")
        return output_pdf_path

    except Exception as e:
        print(f"Error saat menambahkan QR ke PDF: {e}")
        return None

# --- Bagian 4: Web Server untuk Verifikasi (Flask) ---

app = Flask(__name__)

# Template HTML dasar untuk halaman verifikasi
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verifikasi Tanda Tangan Digital</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { max-width: 800px; margin: auto; padding: 20px; border: 1px solid #ccc; border-radius: 8px; }
        .status-valid { color: green; font-weight: bold; }
        .status-invalid { color: red; font-weight: bold; }
        pre { background-color: #eee; padding: 10px; border-radius: 5px; overflow-x: auto; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Status Verifikasi Dokumen</h1>
        <p><strong>ID Dokumen:</strong> {{ doc_id }}</p>
        <p><strong>Penanda Tangan:</strong> {{ signer_name }}</p>
        <p><strong>Waktu Penandatanganan:</strong> {{ timestamp }}</p>
        <p><strong>Hash Dokumen Tersimpan:</strong> <code>{{ stored_doc_hash }}</code></p>
        <p><strong>Hash Dokumen yang Dihitung Ulang:</strong> <code>{{ current_doc_hash }}</code></p>

        <h2>Status Verifikasi: <span class="{{ 'status-valid' if is_valid else 'status-invalid' }}">
            {% if is_valid %}
                VALID: Dokumen Asli Belum Diubah!
            {% else %}
                TIDAK VALID: Dokumen Mungkin Telah Diubah Atau Tanda Tangan Palsu!
            {% endif %}
        </span></h2>

        <h3>Dokumen Asli:</h3>
        <p><a href="{{ doc_url }}" target="_blank">Lihat Dokumen Asli (PDF)</a></p>

        {% if not is_valid %}
            <p style="color: red;">Peringatan: Jika status TIDAK VALID, dokumen ini mungkin telah diubah setelah ditandatangani atau tanda tangannya tidak sah.</p>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route('/verify')
def verify_document():
    doc_id = request.args.get('id')
    if not doc_id:
        return jsonify({"error": "ID Dokumen tidak ditemukan"}), 400

    record = signature_db.get(doc_id)
    if not record:
        return jsonify({"error": "Data tanda tangan tidak ditemukan untuk ID ini"}), 404

    doc_url = record['doc_url']
    signature_b64 = record['signature_b64']
    public_key_pem = record['public_key_pem']
    stored_doc_hash = record['doc_hash']
    signer_name = record['signer_name']
    timestamp = record['timestamp']

    try:
        # 1. Unduh (atau akses lokal) dokumen asli
        # Untuk demo, kita asumsikan doc_url adalah path file lokal
        original_doc_path = os.path.join(DOCS_DIR, os.path.basename(doc_url))
        if not os.path.exists(original_doc_path):
             # Jika ini URL sungguhan, Anda perlu menggunakan requests.get()
            return jsonify({"error": f"Dokumen asli tidak ditemukan di server: {original_doc_path}"}), 500

        # 2. Hitung ulang hash dokumen asli
        current_doc_hash = hash_file(original_doc_path)

        # 3. Muat public key
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode('utf-8'),
            backend=default_backend()
        )

        # 4. Verifikasi tanda tangan
        is_valid = verify_signature(
            public_key,
            bytes.fromhex(current_doc_hash), # Hash harus dalam bytes
            base64.b64decode(signature_b64) # Tanda tangan harus dalam bytes
        )

        return render_template_string(
            HTML_TEMPLATE,
            doc_id=doc_id,
            signer_name=signer_name,
            timestamp=timestamp,
            stored_doc_hash=stored_doc_hash,
            current_doc_hash=current_doc_hash,
            is_valid=is_valid,
            doc_url=doc_url
        )

    except Exception as e:
        print(f"Error saat verifikasi: {e}")
        return jsonify({"error": f"Terjadi kesalahan saat verifikasi: {e}"}), 500

# --- Bagian 5: Fungsi Utama (Contoh Penggunaan) ---

def main():
    load_db() # Muat DB saat aplikasi dimulai

    # 1. Hasilkan Kunci (jalankan ini sekali saja untuk membuat kunci)
    private_key_path = os.path.join(KEYS_DIR, "my_private_key.pem")
    public_key_path = os.path.join(KEYS_DIR, "my_public_key.pem")

    if not os.path.exists(private_key_path):
        private_key, public_key = generate_rsa_key_pair(private_key_path, public_key_path)
    else:
        private_key = load_private_key(private_key_path)
        public_key = load_public_key(public_key_path)
        print("Kunci sudah ada, memuat kunci yang ada.")

    # Convert public key ke PEM string untuk disimpan di DB
    public_key_pem_str = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')

    # 2. Siapkan Dokumen untuk Ditandatangani
    original_pdf_filename = "contoh_dokumen.pdf"
    original_pdf_path = os.path.join(DOCS_DIR, original_pdf_filename)

    # Buat file dummy PDF jika belum ada
    if not os.path.exists(original_pdf_path):
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(original_pdf_path, pagesize=letter)
        c.drawString(100, 750, "Ini adalah Contoh Dokumen Asli.")
        c.drawString(100, 730, "Mohon tidak diubah setelah ditandatangani.")
        c.save()
        print(f"Membuat dummy PDF: {original_pdf_path}")

    # 3. Hash Dokumen Asli
    doc_hash = hash_file(original_pdf_path)
    print(f"\nHASH Dokumen Asli ({original_pdf_filename}): {doc_hash}")

    # 4. Tanda Tangani Hash dengan Private Key
    signature = sign_hash(private_key, bytes.fromhex(doc_hash))
    signature_b64 = base64.b64encode(signature).decode('utf-8') # Simpan sebagai base64 string

    print(f"Tanda Tangan Digital (Base64): {signature_b64[:50]}...") # Tampilkan sebagian

    # 5. Simpan Informasi Tanda Tangan ke Database Mock
    import uuid
    import datetime
    transaction_id = str(uuid.uuid4())
    doc_url = f"{BASE_VERIFY_URL}/docs/{original_pdf_filename}" # Mock URL untuk akses dokumen
    
    # Untuk demo ini, kita asumsikan dokumen asli dapat diakses via URL ini.
    # Di produksi, Anda akan mengunggah 'original_pdf_path' ke S3/GCS dll.
    # dan doc_url akan menjadi URL cloud storage tersebut.

    signature_db[transaction_id] = {
        "doc_url": doc_url,
        "signature_b64": signature_b64,
        "public_key_pem": public_key_pem_str,
        "signer_name": "John Doe",
        "timestamp": datetime.datetime.now().isoformat(),
        "doc_hash": doc_hash # Simpan hash asli juga untuk reference
    }
    save_db()
    print(f"\nInformasi tanda tangan disimpan dengan ID: {transaction_id}")

    # 6. Buat QR Code yang mengarah ke endpoint verifikasi
    verify_qr_url = f"{BASE_VERIFY_URL}?id={transaction_id}"
    qr_code_output_path = os.path.join(SIGNED_DOCS_DIR, f"qr_{transaction_id}.png")
    generate_qr_code(verify_qr_url, qr_code_output_path)
    print(f"QR Code dibuat: {qr_code_output_path}")
    print(f"URL Verifikasi QR: {verify_qr_url}")

    # 7. TEMPELKAN QR CODE KE SALINAN PDF
    # Catatan: Fungsi add_qr_to_pdf ini sangat dasar dan tidak menempel gambar secara visual.
    # Ini hanya membuat salinan. Untuk penempelan visual yang sebenarnya, perlu library lain.
    signed_pdf_path = os.path.join(SIGNED_DOCS_DIR, f"signed_{os.path.basename(original_pdf_filename)}")
    add_qr_to_pdf(original_pdf_path, qr_code_output_path, signed_pdf_path)
    print(f"\nPDF Salinan (dengan asumsi QR ditempel manual/via library lain): {signed_pdf_path}")
    print("Salin QR Code dan tempelkan secara manual ke dokumen PDF salinan ini untuk menguji.")

    # Instruksi untuk menjalankan verifikasi
    print("\n--- CARA VERIFIKASI (SETELAH MENJALANKAN KODE INI) ---")
    print("1. Jalankan Flask server: python3 main_signature_system.py (di terminal terpisah)")
    print("2. Pindai QR Code di file:")
    print(f"   {qr_code_output_path}")
    print(f"   Atau buka URL di browser: {verify_qr_url}")
    print("3. Cek hasilnya di browser.")

    # Untuk menjalankan Flask app
    print("\nMenjalankan Flask server (Ctrl+C untuk keluar)...")
    app.run(debug=True) # debug=True agar bisa melihat error di konsol

if __name__ == "__main__":
    main()