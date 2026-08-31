# Dokumen Requirements

## Pendahuluan

LinkedIn Automation Bot adalah sistem otomasi lengkap berbasis web yang memungkinkan pengguna untuk:
- Membuat dan memposting konten LinkedIn secara otomatis dengan bantuan AI
- Mengelola interaksi dengan audiens (komentar, reaksi) secara otomatis
- Mencari dan melamar lowongan kerja secara otomatis
- Memantau semua aktivitas melalui web dashboard yang komprehensif

Sistem menggunakan HP Android yang terhubung via USB (ADB/uiautomator2) sebagai eksekutor aksi fisik di aplikasi LinkedIn, sementara backend Python/FastAPI bertindak sebagai otak koordinasi. Seluruh alur dikendalikan dari browser melalui dashboard Next.js.

---

## Glossary

- **Bot**: Komponen sistem yang mengeksekusi aksi otomatis di HP Android via ADB
- **ADB**: Android Debug Bridge — protokol komunikasi antara PC dan HP Android via USB
- **ADB_Service**: Layanan Python yang mengirim perintah ke HP Android via ADB
- **AI_Service**: Layanan Python yang mengintegrasikan berbagai provider AI (DeepSeek, Groq, ChatGPT web, Claude web)
- **Content_Generator**: Komponen yang menghasilkan teks konten LinkedIn menggunakan AI
- **Image_Service**: Layanan yang menghasilkan atau mengambil gambar menggunakan layanan eksternal (Ideogram, Playground.ai)
- **OCR_Engine**: Komponen yang membaca teks dari screenshot layar HP menggunakan EasyOCR/pytesseract
- **Scheduler**: Komponen APScheduler yang mengelola eksekusi tugas terjadwal
- **Log_Service**: Layanan yang mencatat setiap aksi bot ke database dengan detail lengkap
- **Dashboard**: Antarmuka web berbasis Next.js untuk mengendalikan semua fungsi sistem
- **Studio**: Halaman dashboard untuk membuat dan mengelola konten
- **Job_Hunter**: Komponen yang mencari dan melamar lowongan kerja di LinkedIn
- **Post**: Konten LinkedIn yang dibuat oleh sistem, dapat berupa teks, gambar, atau kombinasi
- **Interaction**: Aksi bot berupa komentar, reaksi, atau share terhadap post pengguna lain
- **Job_Application**: Lamaran pekerjaan yang diajukan secara otomatis oleh sistem
- **Anti_Ban_Controller**: Komponen yang mengatur delay dan batasan frekuensi aksi untuk menghindari deteksi bot
- **Provider**: Penyedia layanan AI (DeepSeek, Groq, ChatGPT web, Claude web, Perplexity web)
- **Easy_Apply**: Fitur LinkedIn yang memungkinkan lamaran pekerjaan instan tanpa meninggalkan platform
- **CSV_Exporter**: Komponen yang mengekspor data log dan history ke format CSV
- **Search_Service**: Layanan yang mencari referensi dari Google atau Perplexity untuk konten

---

## Requirements

---

### Requirement 1: Koneksi dan Manajemen HP Android

**User Story:** Sebagai pengguna, saya ingin sistem dapat mendeteksi dan mengelola koneksi HP Android saya, agar saya tahu kapan bot siap digunakan dan dapat merespons ketika HP terputus.

#### Acceptance Criteria

1. WHEN HP Android dihubungkan via USB dengan USB Debugging aktif, THE ADB_Service SHALL mendeteksi perangkat dalam waktu maksimal 10 detik dan memperbarui status koneksi di dashboard.
2. WHEN HP Android terputus dari USB saat bot sedang berjalan, THE ADB_Service SHALL menghentikan eksekusi tugas yang berjalan, mencatat error ke Log_Service, dan menampilkan notifikasi di Dashboard.
3. THE ADB_Service SHALL memverifikasi bahwa aplikasi LinkedIn terpasang dan dapat dibuka di HP sebelum mengizinkan eksekusi modul apapun.
4. IF perintah ADB gagal dieksekusi dalam 30 detik, THEN THE ADB_Service SHALL menandai eksekusi sebagai timeout, mencatat error detail ke Log_Service, dan mengembalikan status error ke Dashboard.
5. THE Dashboard SHALL menampilkan status koneksi HP (terhubung/terputus/error) secara real-time via WebSocket dengan interval pembaruan maksimal 5 detik.
6. WHERE fitur screenshot diaktifkan, THE ADB_Service SHALL mengambil screenshot layar HP setelah setiap aksi bot dan menyimpan path-nya ke bot_logs.

---

### Requirement 2: Pembuatan Konten LinkedIn (Module A — Content Posting)

**User Story:** Sebagai pengguna, saya ingin memberikan topik atau ide dan sistem secara otomatis menghasilkan konten LinkedIn yang menarik, agar saya bisa memposting konten berkualitas tanpa harus menulis sendiri dari nol.

#### Acceptance Criteria

1. THE Studio SHALL menyediakan form input yang menerima: judul/topik, deskripsi ide, tipe konten (storytelling/tips_list/pertanyaan/kutipan/video_script/thread), tone (profesional/kasual/inspiratif/edukasi), dan panjang konten (pendek/sedang/panjang).
2. WHEN pengguna men-submit form input konten, THE Content_Generator SHALL mencari referensi via Search_Service dari Google atau Perplexity menggunakan topik yang diberikan sebelum memanggil AI.
3. WHEN referensi berhasil dikumpulkan, THE AI_Service SHALL menghasilkan draft konten LinkedIn berdasarkan topik, referensi, tipe, dan tone yang dipilih menggunakan provider yang dikonfigurasi.
4. THE Content_Generator SHALL menghasilkan minimal 3 variasi konten yang berbeda untuk setiap request agar pengguna dapat memilih yang paling sesuai.
5. WHERE tipe konten adalah "kutipan" atau "tips_list", THE Image_Service SHALL menawarkan opsi generate gambar menggunakan Ideogram.ai atau Playground.ai dengan prompt yang diturunkan dari konten.
6. WHEN konten berhasil dihasilkan, THE Studio SHALL menampilkan preview lengkap dengan estimasi jumlah karakter, prediksi hashtag, dan pilihan untuk edit sebelum posting.
7. WHEN pengguna mengklik "Post Sekarang", THE Bot SHALL membuka aplikasi LinkedIn di HP, menavigasi ke form post baru, mengetik konten, menambahkan gambar jika ada, dan menekan tombol Publish.
8. WHEN posting berhasil dipublikasikan, THE Log_Service SHALL mencatat post ke tabel posts dengan status "posted", menyertakan: konten, tipe, provider AI yang digunakan, waktu posting, dan screenshot konfirmasi.
9. IF AI_Service gagal menghasilkan konten setelah 3 percobaan, THEN THE Content_Generator SHALL mengembalikan pesan error yang deskriptif ke Dashboard dan menyimpan request ke tabel bot_logs dengan status "failed".
10. WHILE Bot sedang memposting ke LinkedIn, THE Dashboard SHALL menampilkan progress real-time setiap langkah eksekusi via WebSocket.
11. THE Content_Generator SHALL mendukung format thread dengan memecah konten panjang menjadi maksimal 10 bagian, masing-masing tidak melebihi 3.000 karakter sesuai batas LinkedIn.

---

### Requirement 3: Generator Konten Promosi (Module B — Promosi)

**User Story:** Sebagai pengguna, saya ingin membuat konten promosi jasa atau produk saya di LinkedIn secara otomatis, agar saya bisa konsisten mempromosikan bisnis tanpa menghabiskan waktu untuk menulis copywriting.

#### Acceptance Criteria

1. THE Studio SHALL menyediakan form promosi yang menerima: deskripsi jasa/produk, tipe promosi (penawaran_spesial/portofolio/testimoni/pengumuman), daftar item yang dipromosikan, dan target audiens.
2. WHEN form promosi di-submit, THE AI_Service SHALL menghasilkan copywriting promosi yang mencakup minimal: headline yang menarik, body post yang menjelaskan value proposition, call-to-action yang jelas, dan 5–10 hashtag relevan.
3. THE Content_Generator SHALL memastikan setiap konten promosi yang dihasilkan memiliki struktur yang berbeda dari konten promosi sebelumnya untuk menghindari pola posting yang monoton.
4. WHERE tipe promosi adalah "portofolio" atau "penawaran_spesial", THE Image_Service SHALL menghasilkan gambar promosi menggunakan template Ideogram.ai yang sesuai dengan tipe promosi.
5. WHEN gambar promosi dihasilkan, THE Image_Service SHALL menyimpan URL gambar dan menampilkan preview di Studio sebelum pengguna menyetujui untuk posting.
6. WHEN pengguna menyetujui konten promosi, THE Bot SHALL memposting konten beserta gambar ke LinkedIn melalui HP dan mencatat hasilnya ke tabel posts dengan content_type = "promo".
7. IF gambar gagal dihasilkan oleh Image_Service, THEN THE Studio SHALL menawarkan opsi untuk posting tanpa gambar atau mencoba provider image generation alternatif.

---

### Requirement 4: Auto Interaksi dengan Audiens (Module C — Engage)

**User Story:** Sebagai pengguna, saya ingin sistem secara otomatis membaca post di beranda LinkedIn dan memberikan komentar yang relevan, agar engagement akun saya meningkat tanpa harus memantau feed secara manual.

#### Acceptance Criteria

1. WHEN modul Engage dijalankan, THE Bot SHALL membuka aplikasi LinkedIn di HP, scroll beranda, dan mengambil screenshot setiap 3–5 detik (interval acak dalam range tersebut) untuk membaca konten feed.
2. WHEN screenshot diambil, THE OCR_Engine SHALL mengekstrak teks dari post yang terlihat di layar dengan akurasi minimal 80% untuk teks berbahasa Latin.
3. WHEN teks post berhasil diekstrak, THE AI_Service SHALL menghasilkan komentar yang relevan dan kontekstual menggunakan provider AI yang dikonfigurasi (ChatGPT web atau DeepSeek API).
4. THE AI_Service SHALL menghasilkan komentar dengan panjang antara 20–200 karakter untuk terlihat natural dan tidak seperti bot.
5. WHEN komentar dihasilkan, THE Bot SHALL membuka post target di LinkedIn, mengetik komentar via ADB, dan menekan tombol kirim.
6. WHEN komentar berhasil terkirim, THE Log_Service SHALL mencatat interaksi ke tabel interactions dengan: URL post target, nama author, teks komentar yang dikirim, waktu, dan status.
7. THE Anti_Ban_Controller SHALL membatasi jumlah komentar maksimal 15 komentar per hari dan memastikan interval antar komentar antara 3–10 menit (nilai acak dalam range tersebut).
8. IF OCR_Engine gagal mengekstrak teks yang bermakna dari screenshot (teks < 10 karakter), THEN THE Bot SHALL melewati post tersebut, mencatat ke bot_logs, dan melanjutkan ke post berikutnya.
9. THE Bot SHALL melewati post yang URL-nya sudah ada di tabel interactions dalam 7 hari terakhir untuk menghindari komentar duplikat pada post yang sama.
10. WHERE fitur filter topik diaktifkan, THE OCR_Engine SHALL hanya memproses post yang mengandung kata kunci yang dikonfigurasi pengguna.

---

### Requirement 5: Job Hunter & Auto Apply (Module D)

**User Story:** Sebagai pengguna, saya ingin sistem secara otomatis mencari lowongan kerja di LinkedIn sesuai kriteria saya dan melamar menggunakan Easy Apply, agar saya bisa melamar lebih banyak posisi tanpa effort manual yang berulang.

#### Acceptance Criteria

1. THE Job_Hunter SHALL menyediakan form input kriteria yang menerima: judul posisi (satu atau lebih), skill yang diinginkan, lokasi (kota atau remote), range gaji minimum, dan tipe pekerjaan (full-time/part-time/kontrak/freelance).
2. WHEN kriteria disubmit, THE Bot SHALL membuka LinkedIn Jobs di browser HP, memasukkan kata kunci pencarian sesuai kriteria, dan menerapkan filter yang tersedia.
3. WHEN halaman hasil pencarian terbuka, THE OCR_Engine SHALL mengekstrak daftar lowongan yang terlihat, termasuk: judul posisi, nama perusahaan, lokasi, dan indikator Easy Apply.
4. THE Job_Hunter SHALL menyimpan setiap lowongan yang ditemukan ke tabel job_applications dengan status "found" dan menghindari duplikasi berdasarkan job_url.
5. WHEN lowongan dengan tombol Easy Apply ditemukan dan memenuhi semua kriteria, THE Bot SHALL membuka halaman lowongan, mengisi form Easy Apply, mengunggah CV yang dikonfigurasi, dan menekan tombol kirim.
6. WHEN lamaran berhasil terkirim, THE Log_Service SHALL memperbarui status job_applications menjadi "applied" dan mencatat waktu apply, screenshot konfirmasi, dan detail form yang diisi.
7. THE Anti_Ban_Controller SHALL membatasi jumlah lamaran maksimal 20 lamaran per hari untuk menghindari deteksi aktivitas tidak normal oleh LinkedIn.
8. IF form Easy Apply membutuhkan input yang tidak tersedia di profil CV yang dikonfigurasi, THEN THE Bot SHALL melewati lowongan tersebut, mencatat ke bot_logs sebagai "skipped_incomplete_form", dan melanjutkan ke lowongan berikutnya.
9. THE Job_Hunter SHALL menghasilkan laporan ringkasan setelah setiap sesi yang mencakup: jumlah lowongan ditemukan, jumlah berhasil dilamar, jumlah dilewati, dan alasan lewat.
10. THE Dashboard SHALL menampilkan statistik job hunting: total apply, breakdown status (found/applied/rejected/interview/offer), dan grafik tren aktivitas per minggu.

---

### Requirement 6: Penjadwalan Otomatis (Scheduler)

**User Story:** Sebagai pengguna, saya ingin menjadwalkan posting konten di waktu tertentu secara otomatis, agar konten saya dipublikasikan pada waktu optimal tanpa saya harus online saat itu.

#### Acceptance Criteria

1. THE Scheduler SHALL menyediakan antarmuka pembuatan jadwal yang menerima: tipe tugas (post_konten/engage/job_hunt), waktu eksekusi (one-time atau cron expression), dan konfigurasi tugas spesifik.
2. WHEN waktu yang dijadwalkan tiba, THE Scheduler SHALL mengeksekusi tugas yang sesuai, mencatat waktu eksekusi aktual ke tabel schedules di kolom last_run, dan menghitung next_run berikutnya.
3. THE Scheduler SHALL memperbarui kolom next_run pada setiap jadwal aktif setiap kali jadwal berhasil dieksekusi.
4. IF tugas terjadwal gagal dieksekusi karena HP terputus, THEN THE Scheduler SHALL mencatat kegagalan di bot_logs, mempertahankan jadwal sebagai aktif, dan mencoba eksekusi ulang maksimal 3 kali dengan interval 5 menit.
5. THE Dashboard SHALL menampilkan kalender visual yang menunjukkan semua jadwal aktif dan histori eksekusi dengan warna berbeda untuk status success/failed/pending.
6. WHEN pengguna menonaktifkan jadwal, THE Scheduler SHALL segera menghentikan eksekusi terjadwal berikutnya tanpa mempengaruhi eksekusi yang sedang berjalan.
7. WHERE jadwal diaktifkan kembali setelah sebelumnya dinonaktifkan, THE Scheduler SHALL menghitung ulang next_run berdasarkan cron expression dan waktu saat ini, bukan berdasarkan last_run.

---

### Requirement 7: Logging, History, dan Audit Trail

**User Story:** Sebagai pengguna, saya ingin setiap aksi bot tercatat secara lengkap dengan detail dan screenshot, agar saya dapat mengaudit semua aktivitas, mendiagnosis kegagalan, dan membuktikan hasil kerja bot.

#### Acceptance Criteria

1. THE Log_Service SHALL mencatat setiap eksekusi aksi bot ke tabel bot_logs dengan field wajib: action type, status (success/failed/running/skipped), pesan hasil, detail error jika ada, durasi eksekusi dalam milidetik, dan timestamp.
2. WHERE screenshot diaktifkan di konfigurasi, THE Log_Service SHALL menyimpan path screenshot ke kolom screenshot_path di setiap entri bot_logs yang berkaitan dengan aksi di layar HP.
3. THE Dashboard SHALL menampilkan tabel history lengkap dengan kolom: waktu, aksi, status, durasi, dan ringkasan konten, dengan kemampuan filter berdasarkan status, tipe aksi, dan rentang tanggal.
4. WHEN pengguna mengklik baris di tabel history, THE Dashboard SHALL menampilkan detail lengkap log termasuk screenshot jika tersedia, konten lengkap, dan stack trace error jika ada.
5. THE CSV_Exporter SHALL menghasilkan file CSV dari data yang difilter dalam tabel history dengan semua kolom yang tampil di tabel, dapat diunduh langsung dari Dashboard.
6. THE Log_Service SHALL mempertahankan semua log selama minimal 90 hari sebelum dapat dihapus secara permanen.
7. WHEN sebuah post berhasil dipublikasikan di LinkedIn, THE Log_Service SHALL mencatat post_id LinkedIn aktual (jika dapat diekstrak dari URL halaman konfirmasi) ke kolom post_id di tabel posts.

---

### Requirement 8: Manajemen dan Monitoring Penggunaan AI

**User Story:** Sebagai pengguna, saya ingin memantau penggunaan setiap layanan AI yang dipakai, agar saya dapat mengelola kuota free tier dan menghindari tagihan tak terduga.

#### Acceptance Criteria

1. THE AI_Service SHALL mencatat setiap panggilan ke provider AI ke tabel ai_usage dengan: nama provider, jumlah token prompt, jumlah token completion, estimasi biaya, dan timestamp.
2. THE Dashboard SHALL menampilkan ringkasan penggunaan AI per provider dalam 30 hari terakhir, termasuk total token, estimasi biaya kumulatif, dan persentase penggunaan relatif terhadap batas free tier.
3. WHEN penggunaan token suatu provider mencapai 80% dari batas yang dikonfigurasi, THE AI_Service SHALL menampilkan peringatan di Dashboard dan secara otomatis beralih ke provider fallback yang dikonfigurasi.
4. IF semua provider AI yang dikonfigurasi tidak dapat diakses atau telah mencapai batas, THEN THE AI_Service SHALL menolak request baru, mencatat error ke bot_logs, dan menampilkan notifikasi ke pengguna di Dashboard.
5. THE AI_Service SHALL mendukung konfigurasi urutan prioritas provider (provider chain) sehingga jika provider utama gagal, sistem secara otomatis mencoba provider berikutnya dalam urutan.
6. WHERE provider menggunakan akses web (ChatGPT web, Claude web), THE AI_Service SHALL mengontrol browser HP via ADB untuk membuka halaman web AI, menginput prompt via clipboard, dan menyalin hasil respons.

---

### Requirement 9: Anti-Ban dan Simulasi Perilaku Manusia

**User Story:** Sebagai pengguna, saya ingin bot berperilaku seperti manusia nyata saat menggunakan LinkedIn, agar akun saya tidak dideteksi sebagai bot dan tidak dibanned atau dibatasi oleh LinkedIn.

#### Acceptance Criteria

1. THE Anti_Ban_Controller SHALL menerapkan delay acak antara setiap aksi ADB dalam range yang dikonfigurasi (default: 1–3 detik antar ketukan, 2–5 detik antar navigasi).
2. THE Anti_Ban_Controller SHALL membatasi total aksi bot per hari sesuai batas yang dikonfigurasi per modul: posting maksimal 3 post per hari, komentar maksimal 15 per hari, lamaran kerja maksimal 20 per hari.
3. WHEN batas harian suatu modul tercapai, THE Anti_Ban_Controller SHALL menolak eksekusi lebih lanjut untuk modul tersebut pada hari yang sama dan mencatat alasan penolakan ke bot_logs.
4. THE Anti_Ban_Controller SHALL mensimulasikan pola scroll manusia dengan kecepatan scroll yang bervariasi (bukan scroll dengan kecepatan konstan) saat membaca feed LinkedIn.
5. THE Anti_Ban_Controller SHALL secara acak menyisipkan aksi "idle" (berhenti scroll selama 5–30 detik) selama sesi engagement untuk mensimulasikan perilaku membaca.
6. IF sistem mendeteksi halaman CAPTCHA atau tantangan keamanan LinkedIn di layar HP via OCR, THEN THE Anti_Ban_Controller SHALL segera menghentikan semua aksi bot, mencatat kejadian ke bot_logs, dan mengirim notifikasi ke pengguna di Dashboard.
7. THE Anti_Ban_Controller SHALL memastikan interval antar sesi bot (dari selesai satu sesi ke mulai sesi berikutnya) minimal 30 menit untuk sesi engage berturut-turut.

---

### Requirement 10: Manajemen Draft dan Preview Konten

**User Story:** Sebagai pengguna, saya ingin dapat menyimpan konten sebagai draft, mengeditnya, dan melihat preview sebelum memposting, agar saya tetap memiliki kontrol penuh atas konten sebelum dipublikasikan.

#### Acceptance Criteria

1. THE Studio SHALL memungkinkan pengguna menyimpan konten yang sedang dibuat sebagai draft ke tabel posts dengan status "draft" kapan saja sebelum posting.
2. WHEN pengguna membuka draft yang tersimpan, THE Studio SHALL memuat konten lengkap termasuk teks, gambar, tipe, dan tone ke dalam form editor yang sama dengan semua field terisi.
3. THE Studio SHALL menampilkan preview konten yang mensimulasikan tampilan post LinkedIn dengan menampilkan nama pengguna (placeholder), teks konten, gambar jika ada, dan jumlah karakter.
4. WHEN jumlah karakter konten melebihi 3.000 karakter, THE Studio SHALL menampilkan peringatan dan menawarkan opsi untuk otomatis memecah menjadi format thread.
5. THE Studio SHALL menyediakan editor teks inline untuk memodifikasi konten yang dihasilkan AI sebelum posting tanpa perlu regenerasi.
6. WHEN konten berhasil diposting, THE Studio SHALL memperbarui status post di tabel posts dari "draft" atau "scheduled" menjadi "posted" dan mencatat posted_at timestamp.

---

### Requirement 11: Export Data dan Pelaporan

**User Story:** Sebagai pengguna, saya ingin mengekspor data aktivitas bot ke CSV, agar saya dapat menganalisis performa dan membuat laporan eksternal.

#### Acceptance Criteria

1. THE CSV_Exporter SHALL mendukung export terpisah untuk setiap entitas utama: posts, bot_logs, interactions, dan job_applications.
2. WHEN pengguna memilih rentang tanggal dan filter status lalu mengklik Export, THE CSV_Exporter SHALL menghasilkan file CSV yang dapat diunduh dalam waktu maksimal 10 detik untuk dataset hingga 10.000 baris.
3. THE CSV_Exporter SHALL memastikan setiap file CSV menggunakan encoding UTF-8 dengan BOM untuk kompatibilitas dengan Microsoft Excel.
4. THE CSV_Exporter SHALL menyertakan baris header dengan nama kolom yang deskriptif pada setiap file CSV yang dihasilkan.
5. FOR ALL data yang diekspor ke CSV kemudian di-import ulang ke sistem, THE CSV_Exporter SHALL menghasilkan data yang setara dengan data asli untuk semua field non-computed (round-trip property).

---

### Requirement 12: Konfigurasi dan Pengaturan Sistem

**User Story:** Sebagai pengguna, saya ingin dapat mengonfigurasi semua aspek sistem dari dashboard tanpa harus mengedit file konfigurasi manual, agar setup dan penyesuaian lebih mudah.

#### Acceptance Criteria

1. THE Dashboard SHALL menyediakan halaman Settings yang memungkinkan konfigurasi: provider AI prioritas dan urutan fallback, batas harian per modul, range delay Anti_Ban_Controller, path CV untuk auto apply, dan preferensi bahasa konten.
2. WHEN konfigurasi disimpan, THE Backend SHALL memvalidasi semua nilai (misalnya: batas harian harus bilangan positif, range delay harus min < max) sebelum menyimpan ke database.
3. IF nilai konfigurasi tidak valid dikirim ke API, THEN THE Backend SHALL mengembalikan pesan error yang spesifik menyebutkan field mana yang tidak valid dan mengapa, dengan HTTP status 422.
4. THE Backend SHALL menerapkan konfigurasi baru yang disimpan pada eksekusi bot berikutnya tanpa memerlukan restart aplikasi.
5. THE Dashboard SHALL menampilkan nilai konfigurasi saat ini dan timestamp kapan terakhir diubah di halaman Settings.

---

## Correctness Properties

### Property 1: Invariant — Konsistensi Status Post

Untuk semua post di tabel posts:
- `count(posts) = count(status='draft') + count(status='scheduled') + count(status='posted') + count(status='failed')`
- Setiap post dengan `status='posted'` HARUS memiliki nilai `posted_at` yang tidak null
- Setiap post dengan `status='draft'` HARUS memiliki nilai `posted_at` yang null

### Property 2: Round-Trip — Serialisasi Draft Konten

Untuk semua draft konten:
- `load_draft(save_draft(content)) == content`
- Konten yang disimpan sebagai draft dan kemudian dimuat kembali harus identik untuk semua field: teks, tipe, tone, gambar URL, dan hashtag.

### Property 3: Invariant — Kelengkapan Log

Untuk setiap eksekusi bot yang tercatat:
- `count(bot_logs where action='post') >= count(posts where status='posted')`
- Setiap post yang berhasil dipublikasikan HARUS memiliki minimal satu entri di bot_logs dengan action='post' dan status='success'.

### Property 4: Round-Trip — Export CSV

Untuk semua data yang diekspor:
- `parse_csv(export_csv(records)) ≈ records`
- Data yang diekspor ke CSV dan di-parse kembali harus menghasilkan nilai yang setara untuk semua field non-computed (tanggal, teks, status, ID).

### Property 5: Metamorphic — Filter Lowongan

Untuk kriteria pencarian lowongan:
- Jika kriteria A lebih ketat dari kriteria B (A merupakan subset dari B), maka `results(A) ⊆ results(B)`
- Jumlah lowongan yang ditemukan dengan filter ketat selalu lebih kecil atau sama dengan filter yang lebih longgar.

### Property 6: Idempotency — Toggle Scheduler

Untuk setiap jadwal:
- `toggle(toggle(schedule)) == schedule`
- Menonaktifkan lalu mengaktifkan kembali jadwal harus menghasilkan jadwal dalam kondisi aktif dengan next_run yang dihitung ulang dari waktu saat ini.

### Property 7: Invariant — Batas Anti-Ban Harian

Untuk setiap hari kalender:
- `count(interactions where date=today AND status='success') <= max_comments_per_day`
- `count(job_applications where date=today AND status='applied') <= max_applies_per_day`
- `count(posts where date=today AND status='posted') <= max_posts_per_day`

### Property 8: Invariant — Tracking Penggunaan AI

Untuk setiap pemanggilan AI:
- `count(ai_usage) = total_ai_calls_since_start`
- Setiap panggilan ke provider AI, baik berhasil maupun gagal, HARUS menghasilkan tepat satu entri di tabel ai_usage.

### Property 9: Idempotency — Apply Lowongan Duplikat

Untuk setiap URL lowongan:
- `apply(apply(job_url)) == apply(job_url)` — dalam arti, mencoba melamar lowongan yang sudah ada di database dengan status 'applied' tidak menghasilkan entri duplikat di job_applications.
- Sistem HARUS mengecek keberadaan job_url sebelum memproses lamaran baru.

### Property 10: Error Condition — Disconnect HP saat Eksekusi

Untuk setiap skenario disconnect:
- Jika HP terputus di tengah eksekusi apapun, sistem TIDAK BOLEH crash; status eksekusi HARUS diperbarui menjadi 'failed' di bot_logs dengan pesan error yang deskriptif.
- `system_state_after_disconnect == stable` — backend tetap dapat menerima request baru setelah HP terputus.
