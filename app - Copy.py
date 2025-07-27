import os
import shutil
import uuid # Import modul uuid
from flask import Flask, request, jsonify, send_from_directory # Import Flask dan komponennya

# Import modul-modul yang sudah ada
from database import initialize_database, DATABASE_NAME, get_user_name_by_id # Import fungsi baru
from key import generate_key_pair, save_key_pair, get_private_key_content, get_public_key
from generate import sign_document, verify_signature, save_document_info, get_document_info, STORAGE_DIR, calculate_file_hash

app = Flask(__name__) # Inisialisasi aplikasi Flask

# --- Inisialisasi Awal Aplikasi ---
# Fungsi ini akan dipanggil sekali saat aplikasi dimulai
def setup_application():
    """
    Melakukan setup awal aplikasi: inisialisasi database dan generate kunci default.
    """
    print("Memulai setup aplikasi...")
    initialize_database()

    # Generate kunci untuk pengguna default jika belum ada
    default_user_id = "admin_signature"
    # Cek apakah kunci privat untuk user ini sudah ada di file
    # (get_private_key_content akan mengembalikan None jika path tidak ada atau file tidak ada)
    if not get_private_key_content(default_user_id):
        print(f"Kunci untuk user '{default_user_id}' tidak ditemukan. Menghasilkan dan menyimpan...")
        # generate_key_pair sekarang akan menyimpan kunci privat ke file
        private_key_path, public_key_pem = generate_key_pair(default_user_id)
        if private_key_path and public_key_pem:
            # save_key_pair sekarang menyimpan path kunci privat
            save_key_pair(default_user_id, private_key_path, public_key_pem)
            print(f"Kunci untuk '{default_user_id}' berhasil dibuat.")
        else:
            print(f"Gagal menghasilkan kunci untuk '{default_user_id}'.")
    else:
        print(f"Kunci untuk user '{default_user_id}' sudah ada.")
    print("Setup aplikasi selesai.")

# Panggil setup aplikasi saat startup
with app.app_context():
    setup_application()

# --- Routes API ---

@app.route('/', methods=['GET'])
def home():
    """
    Endpoint home sederhana.
    """
    return jsonify({"message": "Selamat datang di Digital Signature Service API!"}), 200

@app.route('/upload_and_sign', methods=['POST'])
def api_upload_document_and_sign():
    """
    API Endpoint: Menerima file untuk diunggah, ditandatangani, dan disimpan.
    Menerima file, user_id, dan publisher_name melalui form-data.
    """
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "Tidak ada bagian 'file' dalam permintaan."}), 400

    file = request.files['file']
    user_id = request.form.get('user_id') # Mengambil user_id dari form-data
    # Mengambil publisher_name dari form-data, dengan default 'PT. Signature Dokumen'
    publisher_name = request.form.get('publisher_name', 'PT. Signature Dokumen') 

    if file.filename == '':
        return jsonify({"status": "error", "message": "Tidak ada file yang dipilih."}), 400

    if not user_id: # Memastikan user_id disediakan
        return jsonify({"status": "error", "message": "Parameter 'user_id' harus disediakan dalam form-data."}), 400

    # --- Tambahkan kondisi untuk membuat kunci jika user_id belum memiliki kunci ---
    if not get_private_key_content(user_id):
        print(f"Kunci untuk user '{user_id}' tidak ditemukan. Mencoba membuat kunci baru...")
        private_key_path, public_key_pem = generate_key_pair(user_id)
        if private_key_path and public_key_pem:
            if save_key_pair(user_id, private_key_path, public_key_pem):
                print(f"Kunci baru untuk '{user_id}' berhasil dibuat dan disimpan.")
            else:
                return jsonify({"status": "error", "message": f"Gagal menyimpan kunci baru untuk user '{user_id}'."}), 500
        else:
            return jsonify({"status": "error", "message": f"Gagal menghasilkan kunci baru untuk user '{user_id}'."}), 500
    # --- Akhir dari kondisi penambahan kunci ---


    if file:
        original_filename = file.filename # Simpan nama file asli
        # Buat nama file unik untuk penyimpanan di server
        stored_filename = f"{uuid.uuid4()}_{original_filename}"
        file_data = file.read() # Baca konten file dalam bentuk bytes

        print(f"\n[API] Menerima dokumen '{original_filename}' untuk ditandatangani oleh '{user_id}'...")

        # 1. Simpan file asli ke storage dengan nama unik
        file_path = os.path.join(STORAGE_DIR, stored_filename)
        try:
            with open(file_path, 'wb') as f:
                f.write(file_data)
            print(f"File '{original_filename}' berhasil disimpan di '{file_path}'.")
        except Exception as e:
            return jsonify({"status": "error", "message": f"Gagal menyimpan file: {e}"}), 500

        # 2. Tandatangani dokumen (menggunakan path ke nama file unik)
        signature_hex, doc_hash = sign_document(file_path, user_id)
        if not signature_hex:
            os.remove(file_path) # Hapus file jika gagal tanda tangan
            return jsonify({"status": "error", "message": "Gagal menandatangani dokumen. Pastikan user_id valid dan kunci tersedia."}), 500

        # 3. Ambil kunci publik penanda tangan
        public_key_signer = get_public_key(user_id)
        if not public_key_signer:
            os.remove(file_path)
            return jsonify({"status": "error", "message": "Kunci publik penanda tangan tidak ditemukan."}), 500

        # 4. Simpan informasi tanda tangan ke database
        # Mengirimkan nama file unik, nama file asli, dan publisher_name
        doc_id = save_document_info(
            stored_filename, original_filename, file_path, doc_hash,
            public_key_signer, signature_hex, user_id, publisher_name # Menambahkan publisher_name
        )
        if not doc_id:
            os.remove(file_path)
            return jsonify({"status": "error", "message": "Gagal menyimpan informasi tanda tangan ke database."}), 500

        return jsonify({
            "status": "success",
            "message": "Dokumen berhasil diunggah dan ditandatangani.",
            "document_id": doc_id,
            "original_filename": original_filename, # Mengembalikan nama file asli
            "stored_filename": stored_filename,     # Mengembalikan nama file unik di storage
            "document_hash": doc_hash,
            "signature": signature_hex,
            "signer_user_id": user_id,
            "publisher_name": publisher_name # Mengembalikan publisher_name
        }), 201 # 201 Created
    
    return jsonify({"status": "error", "message": "Permintaan tidak valid."}), 400


@app.route('/download_original_file/<int:document_id>', methods=['GET'])
def api_download_original_file(document_id):
    """
    API Endpoint: Mengunduh file asli berdasarkan ID dokumen.
    """
    print(f"\n[API] Permintaan unduh file asli untuk dokumen ID: {document_id}...")
    doc_info = get_document_info(doc_id=document_id)
    if not doc_info:
        return jsonify({"status": "error", "message": f"Dokumen dengan ID {document_id} tidak ditemukan."}), 404

    # Menggunakan original_file_path yang berisi nama file unik di storage
    file_path_on_storage = doc_info['original_file_path']
    # Menggunakan original_filename untuk nama file saat diunduh
    download_filename = doc_info['original_filename']

    if not os.path.exists(file_path_on_storage):
        return jsonify({"status": "error", "message": f"File asli tidak ditemukan di path: {file_path_on_storage}"}), 404

    try:
        # send_from_directory digunakan untuk mengirim file dengan benar
        # Menggunakan download_filename sebagai nama file yang akan diterima oleh klien
        return send_from_directory(STORAGE_DIR, os.path.basename(file_path_on_storage), as_attachment=True, download_name=download_filename)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error saat mengunduh file: {e}"}), 500


@app.route('/get_signature_info', methods=['GET'])
def api_get_digital_signature_info():
    """
    API Endpoint: Mengambil informasi tanda tangan digital dan melakukan verifikasi.
    Menerima document_id atau filename (nama file unik di storage) sebagai query parameter.
    Contoh: /get_signature_info?document_id=123 atau /get_signature_info?filename=unique_uuid_my_doc.txt
    """
    document_id = request.args.get('document_id', type=int)
    # Sekarang, 'filename' di sini akan merujuk pada nama file unik di storage
    filename_on_storage = request.args.get('filename')

    if not document_id and not filename_on_storage:
        return jsonify({"status": "error", "message": "Harap berikan 'document_id' atau 'filename' (nama file unik di storage)."}), 400

    print(f"\n[API] Permintaan info tanda tangan digital untuk ID: {document_id} / Nama Unik: {filename_on_storage}...")
    doc_info = get_document_info(doc_id=document_id, filename=filename_on_storage)
    if not doc_info:
        return jsonify({"status": "error", "message": "Dokumen tidak ditemukan."}), 404

    # Lakukan verifikasi
    is_valid = verify_signature(
        doc_info['original_file_path'], # Ini akan merujuk ke path dengan nama unik
        doc_info['public_key'],
        doc_info['signature']
    )

    # --- Ambil nama lengkap penanda tangan dari tabel user_profiles ---
    signer_fullname = get_user_name_by_id(doc_info['signer_user_id'])
    # --- Akhir penambahan ---

    return jsonify({
        "status": "success",
        "document_id": doc_info['id'],
        "original_filename": doc_info['original_filename'], # Mengembalikan nama file asli
        "stored_filename": doc_info['filename'],             # Mengembalikan nama file unik di storage
        "original_file_path": doc_info['original_file_path'],
        "document_hash_stored": doc_info['document_hash'],
        "public_key_used": doc_info['public_key'],
        "signature_stored": doc_info['signature'],
        "signer_user_id": doc_info['signer_user_id'],
        "signer_fullname": signer_fullname, # Menambahkan nama lengkap penanda tangan
        "publisher_name": doc_info['publisher_name'], # Mengembalikan publisher_name
        "timestamp": doc_info['timestamp'],
        "verification_status": "VALID" if is_valid else "INVALID",
        "verification_message": "Tanda tangan digital valid, integritas dokumen terjaga." if is_valid else "Tanda tangan digital tidak valid atau dokumen telah diubah."
    }), 200


# --- Main Program ---
if __name__ == "__main__":
    # Flask akan berjalan di port 5000 secara default
    # debug=True akan memberikan pesan error yang lebih detail dan reload otomatis
    app.run(debug=True)
