pip install cryptography PyPDF2 qrcode Pillow Flask
pip install Flask
pip install cryptography
s



Begini cara kerjanya secara konseptual:

    File sebagai Urutan Byte: Setiap file di komputer, terlepas dari jenisnya (teks, gambar, video, program, dll.), pada dasarnya disimpan sebagai serangkaian angka biner (0 dan 1). Angka-angka biner ini dikelompokkan menjadi byte (satu byte = 8 bit). Jadi, sebuah file adalah urutan panjang dari byte-byte.

    Input ke Fungsi Hash: Fungsi hash (seperti SHA256 atau SHA512) mengambil seluruh urutan byte ini sebagai input.

    Proses Komputasi: Algoritma hash kemudian melakukan serangkaian operasi matematika yang kompleks (misalnya, rotasi bit, XOR, penjumlahan modular, kompresi) pada byte-byte tersebut. Setiap byte memengaruhi hasil perhitungan selanjutnya.

    Output Hash: Hasil akhirnya adalah string heksadesimal dengan panjang tetap, yang merupakan "sidik jari" unik dari urutan byte file asli tersebut.