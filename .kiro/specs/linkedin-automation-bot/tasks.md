v e

# Rencana Implementasi: LinkedIn Automation Bot

## Gambaran Umum

Implementasi sistem LinkedIn Automation Bot secara bertahap mulai dari infrastruktur, backend core, layanan ADB & AI, modul-modul bot, API layer, WebSocket, hingga frontend dashboard berbasis Next.js dengan Atomic Design.

Stack: Python 3.11 + FastAPI (backend), Next.js 14 + TypeScript (frontend), PostgreSQL 15 (database), Docker Compose (infra).

---

## Tasks

- [x] 1. Infrastruktur & Project Setup
  - [x] 1.1 Buat `docker-compose.yml` dengan service: `postgres`, `backend`, `frontend`
    - PostgreSQL 15 dengan volume persisten, port 5432
    - Backend FastAPI port 8000, Frontend Next.js port 3000
    - Environment variables via `.env` file
    - _Requirements: semua requirement (fondasi sistem)_
  - [x] 1.2 Scaffold struktur direktori backend Python
    - `backend/app/{models,schemas,services,routers,core,utils}/`
    - `backend/alembic/` untuk migrasi database
    - `backend/requirements.txt` dengan semua dependensi yang dipinned
    - _Requirements: semua requirement_
  - [x] 1.3 Scaffold struktur direktori frontend Next.js dengan Atomic Design
    - `frontend/src/components/{atoms,molecules,organisms,templates}/`
    - `frontend/src/{pages,hooks,stores,lib,types}/`
    - `tsconfig.json`, `tailwind.config.ts`, `package.json` dengan semua dependensi
    - _Requirements: semua requirement_
  - [x] 1.4 Buat konfigurasi Alembic dan file `env.py` untuk migrasi
    - Koneksi ke PostgreSQL via `DATABASE_URL` env var
    - _Requirements: semua requirement_

- [X] 2. Database Models & Migrasi

  - [X] 2.1 Buat SQLAlchemy models di `backend/app/models/`
    - `Post` (id, content, content_type, tone, status, provider_used, posted_at, post_id_linkedin, created_at)
    - `BotLog` (id, action_type, status, message, error_detail, duration_ms, screenshot_path, created_at)
    - `Interaction` (id, post_url, author_name, comment_text, status, created_at)
    - `JobApplication` (id, job_title, company, location, job_url, status, applied_at, skip_reason, created_at)
    - `Schedule` (id, task_type, cron_expression, is_active, last_run, next_run, config_json, created_at)
    - `AiUsage` (id, provider, prompt_tokens, completion_tokens, estimated_cost, created_at)
    - `SystemConfig` (id, key, value, updated_at)
    - _Requirements: 1.6, 2.8, 3.6, 4.6, 5.4, 5.6, 7.1, 8.1, 12.1_
  - [X] 2.2 Buat Alembic migration `001_initial_schema.py` dan jalankan `alembic upgrade head`
    - Semua tabel dengan index yang diperlukan (status, created_at, job_url)
    - _Requirements: semua requirement_
  - [X] 2.3 Tulis property test untuk invariant konsistensi status Post
    - **Property 1: Invariant — Konsistensi Status Post**
    - **Validates: Requirements 2.8, 10.6**
    - Test: setiap post status='posted' harus punya posted_at non-null; status='draft' harus posted_at null
  - [X] 2.4 Tulis property test untuk tracking penggunaan AI
    - **Property 8: Invariant — Tracking Penggunaan AI**
    - **Validates: Requirements 8.1**
    - Test: setiap panggilan AI (mock) menghasilkan tepat satu entri ai_usage
- [X] 3. Pydantic Schemas & Core Config

  - [X] 3.1 Buat Pydantic schemas di `backend/app/schemas/`
    - `post.py` — `PostCreate`, `PostRead`, `PostUpdate`
    - `bot_log.py` — `BotLogRead`
    - `interaction.py` — `InteractionRead`
    - `job_application.py` — `JobCriteria`, `JobApplicationRead`
    - `schedule.py` — `ScheduleCreate`, `ScheduleRead`, `ScheduleUpdate`
    - `ai_usage.py` — `AiUsageRead`, `AiUsageSummary`
    - `system_config.py` — `SystemConfigUpdate`, `SystemConfigRead`
    - _Requirements: 12.2, 12.3_
  - [X] 3.2 Buat `backend/app/core/config.py` dengan `Settings` class (Pydantic BaseSettings)
    - Load dari env: DATABASE_URL, ADB_TIMEOUT, AI_PROVIDERS config, batas harian per modul
    - _Requirements: 1.4, 9.2, 12.1_
  - [X] 3.3 Buat `backend/app/core/database.py` — async SQLAlchemy engine dan session factory
    - _Requirements: semua requirement_
- [X] 4. ADB & Device Service

  - [X] 4.1 Buat `backend/app/services/adb_service.py`
    - `get_connected_devices()` — list perangkat via `adb devices`
    - `is_linkedin_installed(device_id)` — cek package `com.linkedin.android`
    - `execute_tap(x, y)`, `execute_swipe(x1,y1,x2,y2)`, `execute_input_text(text)`
    - `take_screenshot()` — simpan ke `static/screenshots/` dan return path
    - `open_app(package)`, `press_back()`, `press_home()`
    - Semua method raise `ADBTimeoutError` jika >30 detik (Requirements 1.4)
    - _Requirements: 1.1, 1.3, 1.4, 1.6_
  - [X] 4.2 Buat `backend/app/services/device_monitor.py`
    - Background task yang poll `adb devices` setiap 5 detik
    - Emit WebSocket event saat status berubah (connected/disconnected/error)
    - Stop running tasks saat HP disconnect (Requirements 1.2)
    - _Requirements: 1.1, 1.2, 1.5_
  - [X] 4.3 Tulis property test untuk error condition disconnect HP
    - **Property 10: Error Condition — Disconnect HP saat Eksekusi**
    - **Validates: Requirements 1.2, 1.4**
    - Test: simulasi ADBTimeoutError → bot_log status='failed', sistem tetap stabil
- [x] 5. OCR Engine

  - [x] 5.1 Buat `backend/app/services/ocr_service.py`
    - `extract_text(image_path)` menggunakan EasyOCR sebagai primary, pytesseract sebagai fallback
    - Return dict dengan `text`, `confidence`, `words_count`
    - Raise `OCRInsufficientTextError` jika teks < 10 karakter
    - _Requirements: 4.2, 4.8, 5.3_
  - [x] 5.2 Tulis unit test untuk OCR dengan berbagai skenario screenshot
    - Test: screenshot kosong, teks < 10 karakter, teks normal, teks campuran bahasa
    - _Requirements: 4.2, 4.8_
- [x] 6. Anti-Ban Controller

  - [x] 6.1 Buat `backend/app/services/anti_ban.py`
    - `get_random_delay(min_s, max_s)` — return delay acak dalam range
    - `check_daily_limit(module, action_type)` — cek batas harian dari db + config
    - `simulate_human_scroll(device_id)` — scroll dengan kecepatan bervariasi + idle acak
    - `detect_captcha(screenshot_path)` — OCR untuk deteksi halaman CAPTCHA/security challenge
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_
  - [x] 6.2 Tulis property test untuk invariant batas anti-ban harian
    - **Property 7: Invariant — Batas Anti-Ban Harian**
    - **Validates: Requirements 9.2, 9.3**
    - Test: generate N aksi (N > batas), verifikasi count sukses <= batas harian config
- [x] 7. AI Provider Services

  - [x] 7.1 Buat `backend/app/services/ai_service.py` — base interface dan provider chain
    - Abstract `BaseAIProvider` dengan method `generate(prompt) -> str`
    - `ProviderChain` — iterasi providers berdasarkan prioritas, fallback otomatis (Requirements 8.5)
    - Catat setiap call ke `AiUsage` table (Requirements 8.1)
    - Raise `AllProvidersExhaustedError` jika semua provider gagal (Requirements 8.4)
    - _Requirements: 8.1, 8.4, 8.5_
  - [x] 7.2 Buat `backend/app/services/providers/deepseek_provider.py`
    - Implementasi `BaseAIProvider` via DeepSeek API (HTTP requests)
    - Hitung token usage dan estimasi biaya
    - _Requirements: 8.1, 8.3_
  - [x] 7.3 Buat `backend/app/services/providers/groq_provider.py`
    - Implementasi `BaseAIProvider` via Groq API
    - _Requirements: 8.1, 8.3_
  - [x] 7.4 Buat `backend/app/services/providers/web_provider.py`
    - Implementasi untuk ChatGPT web dan Claude web via ADB browser control
    - Buka URL di browser HP, input prompt via clipboard, salin respons (Requirements 8.6)
    - _Requirements: 8.6_
  - [x] 7.5 Tulis property test untuk provider chain fallback
    - Test: primary provider mock gagal → secondary provider digunakan, ai_usage tetap tercatat
    - _Requirements: 8.4, 8.5_
- [x] 8. Search & Image Services

  - [x] 8.1 Buat `backend/app/services/search_service.py`
    - `search_references(topic, source)` — source: 'google' atau 'perplexity'
    - Google: gunakan requests + HTML parsing (SerpAPI jika tersedia)
    - Perplexity: via web provider jika API tidak tersedia
    - Return list of `{title, snippet, url}`
    - _Requirements: 2.2_
  - [x] 8.2 Buat `backend/app/services/image_service.py`
    - `generate_image(prompt, provider)` — provider: 'ideogram' atau 'playground'
    - HTTP POST ke Ideogram.ai API dengan prompt
    - Simpan URL gambar dan return untuk preview
    - _Requirements: 2.5, 3.4, 3.5_
- [x] 9. Log Service

  - [x] 9.1 Buat `backend/app/services/log_service.py`
    - `create_log(action_type, status, message, error_detail, duration_ms, screenshot_path)` → `BotLog`
    - `update_log(log_id, status, message, duration_ms)`
    - _Requirements: 7.1, 7.2_
  - [x] 9.2 Buat `backend/app/services/csv_exporter.py`
    - `export_posts(filters)`, `export_bot_logs(filters)`, `export_interactions(filters)`, `export_job_applications(filters)`
    - Output: CSV bytes dengan UTF-8 BOM encoding
    - _Requirements: 7.5, 11.1, 11.2, 11.3, 11.4_
  - [x] 9.3 Tulis property test untuk round-trip CSV export
    - **Property 4: Round-Trip — Export CSV**
    - **Validates: Requirements 11.2, 11.5**
    - Test: export N records → parse CSV → bandingkan dengan original records
- [x] 10. Checkpoint — Backend Services

  - Pastikan semua service dapat diinstansiasi tanpa error, semua unit test service pass.
  - Pastikan semua test pass, tanya user jika ada pertanyaan.
- [x] 11. Module A — Content Posting Bot

  - [x] 11.1 Buat `backend/app/services/content_generator.py`
    - `generate_content(topic, description, content_type, tone, length)` → list of 3 variasi
    - Panggil `search_service.search_references()` terlebih dahulu (Requirements 2.2)
    - Panggil `ai_service` dengan prompt yang menyertakan referensi
    - Validasi thread: split konten jika > 3.000 karakter (Requirements 2.11)
    - _Requirements: 2.2, 2.3, 2.4, 2.9, 2.11_
  - [x] 11.2 Buat `backend/app/services/bots/posting_bot.py`
    - `post_content(post_id)` — ambil post dari db, eksekusi via ADB
    - Buka LinkedIn, navigasi ke form post baru, input teks via `adb_service`
    - Upload gambar jika ada, tekan Publish
    - Emit WebSocket progress event setiap langkah (Requirements 2.10)
    - Update `Post.status` dan `Post.posted_at` setelah berhasil
    - Catat ke `BotLog` (Requirements 2.8)
    - _Requirements: 2.7, 2.8, 2.10, 10.6_
  - [x] 11.3 Tulis property test untuk round-trip draft konten
    - **Property 2: Round-Trip — Serialisasi Draft Konten**
    - **Validates: Requirements 10.1, 10.2**
    - Test: save_draft(content) → load_draft() → verifikasi semua field identik
  - [x] 11.4 Tulis property test untuk invariant kelengkapan log
    - **Property 3: Invariant — Kelengkapan Log**
    - **Validates: Requirements 2.8, 7.1**
    - Test: setiap post status='posted' memiliki ≥1 bot_log action='post' status='success'
- [x] 12. Module B — Promosi Bot

  - [x] 12.1 Buat `backend/app/services/content_generator.py` — extend dengan promo mode
    - Method `generate_promo(description, promo_type, items, target_audience)` → copywriting
    - Pastikan struktur berbeda dari konten promosi sebelumnya (Requirements 3.3)
    - Generate prompt untuk image jika tipe 'portofolio' atau 'penawaran_spesial'
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  - [x] 12.2 Buat `backend/app/services/bots/promo_bot.py`
    - Reuse `posting_bot` logic dengan content_type='promo'
    - Fallback posting tanpa gambar jika image_service gagal (Requirements 3.7)
    - _Requirements: 3.6, 3.7_
- [x] 13. Module C — Engage Bot

  - [x] 13.1 Buat `backend/app/services/bots/engage_bot.py`
    - `run_engage_session(duration_minutes)` — main loop
    - Scroll beranda, screenshot setiap 3–5 detik interval acak (Requirements 4.1)
    - Panggil `ocr_service.extract_text()` untuk setiap screenshot
    - Skip post jika teks < 10 karakter atau URL sudah ada di interactions dalam 7 hari (Requirements 4.8, 4.9)
    - Panggil `ai_service` untuk generate komentar 20–200 karakter (Requirements 4.3, 4.4)
    - Ketik dan kirim komentar via ADB, catat ke `Interaction` (Requirements 4.5, 4.6)
    - Cek batas harian via `anti_ban` sebelum setiap komentar (Requirements 4.7)
    - Filter topik jika konfigurasi aktif (Requirements 4.10)
    - _Requirements: 4.1–4.10_
  - [x] 13.2 Tambahkan `detect_captcha` call di engage loop
    - Jika CAPTCHA terdeteksi: stop semua aksi, catat bot_log, emit WebSocket notifikasi (Requirements 9.6)
    - _Requirements: 9.6_
- [x] 14. Module D — Job Hunter Bot

  - [x] 14.1 Buat `backend/app/services/bots/job_hunter_bot.py`
    - `search_jobs(criteria)` — buka LinkedIn Jobs, input pencarian, ekstrak hasil via OCR
    - Simpan tiap lowongan ke `JobApplication` status='found', skip duplikat by job_url (Requirements 5.4)
    - `apply_job(job_application_id)` — buka halaman, klik Easy Apply, isi form, upload CV
    - Skip jika form butuh input yang tidak ada di config CV (Requirements 5.8)
    - Update status='applied' dan catat screenshot (Requirements 5.6)
    - Cek batas harian via `anti_ban` (Requirements 5.7)
    - _Requirements: 5.1–5.9_
  - [x] 14.2 Buat `backend/app/services/job_report_service.py`
    - `generate_session_report(session_id)` → dict dengan jumlah found/applied/skipped + alasan
    - _Requirements: 5.9_
  - [x] 14.3 Tulis property test untuk idempotency apply lowongan duplikat
    - **Property 9: Idempotency — Apply Lowongan Duplikat**
    - **Validates: Requirements 5.4**
    - Test: apply(job_url) dua kali → hanya ada satu entri di job_applications
  - [x] 14.4 Tulis property test untuk filter lowongan metamorphic
    - **Property 5: Metamorphic — Filter Lowongan**
    - **Validates: Requirements 5.1, 5.2**
    - Test: kriteria A ⊂ kriteria B → results(A) ⊆ results(B)
- [x] 15. Scheduler Service

  - [x] 15.1 Buat `backend/app/services/scheduler_service.py` menggunakan APScheduler
    - `add_schedule(schedule)`, `remove_schedule(schedule_id)`, `toggle_schedule(schedule_id)`
    - Update `last_run` dan `next_run` setelah setiap eksekusi (Requirements 6.2, 6.3)
    - Retry logic: max 3x dengan interval 5 menit jika HP tidak terhubung (Requirements 6.4)
    - `reactivate_schedule(schedule_id)` — hitung ulang next_run dari waktu saat ini (Requirements 6.7)
    - _Requirements: 6.1–6.7_
  - [x] 15.2 Tulis property test untuk idempotency toggle scheduler
    - **Property 6: Idempotency — Toggle Scheduler**
    - **Validates: Requirements 6.6, 6.7**
    - Test: toggle(toggle(schedule)) → schedule aktif dengan next_run dihitung dari waktu saat ini
- [x] 16. Checkpoint — Bot Modules & Scheduler

  - Pastikan semua modul bot dan scheduler dapat diinisialisasi, semua test pass.
  - Tanya user jika ada pertanyaan sebelum lanjut ke API Layer.
- [x] 17. API Layer — FastAPI Routers

  - [x] 17.1 Buat `backend/app/routers/device.py`
    - `GET /api/device/status` — return status koneksi HP dan info perangkat
    - `POST /api/device/screenshot` — ambil screenshot manual
    - _Requirements: 1.1, 1.5_
  - [x] 17.2 Buat `backend/app/routers/content.py`
    - `POST /api/content/generate` — generate konten, return 3 variasi
    - `POST /api/content/posts` — simpan post baru (draft/schedule)
    - `GET /api/content/posts` — list posts dengan filter status, tanggal
    - `GET /api/content/posts/{id}` — detail post
    - `PATCH /api/content/posts/{id}` — update draft
    - `POST /api/content/posts/{id}/publish` — trigger posting bot
    - `POST /api/content/image/generate` — generate gambar via image_service
    - _Requirements: 2.1–2.11, 3.1–3.7, 10.1–10.6_
  - [x] 17.3 Buat `backend/app/routers/engage.py`
    - `POST /api/engage/start` — mulai sesi engage
    - `POST /api/engage/stop` — hentikan sesi
    - `GET /api/engage/interactions` — list interaksi dengan filter
    - _Requirements: 4.1–4.10_
  - [x] 17.4 Buat `backend/app/routers/jobs.py`
    - `POST /api/jobs/search` — mulai job hunting session
    - `GET /api/jobs/applications` — list semua aplikasi dengan filter status
    - `GET /api/jobs/report/{session_id}` — laporan sesi job hunting
    - `GET /api/jobs/stats` — statistik total apply dan breakdown status (Requirements 5.10)
    - _Requirements: 5.1–5.10_
  - [x] 17.5 Buat `backend/app/routers/schedules.py`
    - `GET /api/schedules` — list semua jadwal
    - `POST /api/schedules` — buat jadwal baru
    - `PATCH /api/schedules/{id}` — update jadwal
    - `DELETE /api/schedules/{id}` — hapus jadwal
    - `POST /api/schedules/{id}/toggle` — aktifkan/nonaktifkan
    - _Requirements: 6.1–6.7_
  - [x] 17.6 Buat `backend/app/routers/logs.py`
    - `GET /api/logs` — list bot_logs dengan filter status, action_type, date range (Requirements 7.3)
    - `GET /api/logs/{id}` — detail log dengan screenshot path (Requirements 7.4)
    - `GET /api/logs/export` — download CSV bot_logs (Requirements 7.5, 11.1)
    - `GET /api/content/posts/export` — download CSV posts
    - `GET /api/engage/interactions/export` — download CSV interactions
    - `GET /api/jobs/applications/export` — download CSV job_applications
    - _Requirements: 7.1–7.7, 11.1–11.4_
  - [x] 17.7 Buat `backend/app/routers/ai.py`
    - `GET /api/ai/usage` — ringkasan penggunaan 30 hari per provider (Requirements 8.2)
    - _Requirements: 8.1, 8.2_
  - [x] 17.8 Buat `backend/app/routers/settings.py`
    - `GET /api/settings` — semua config dengan updated_at (Requirements 12.5)
    - `PUT /api/settings` — update config dengan validasi (Requirements 12.2, 12.3)
    - Validasi: batas harian > 0, delay min < max, return 422 jika invalid
    - _Requirements: 12.1–12.5_
  - [x] 17.9 Buat `backend/app/main.py` — wire semua router, CORS, lifespan events
    - Include semua router dengan prefix `/api`
    - Jalankan device_monitor dan scheduler sebagai background tasks
    - Mount `static/screenshots/` sebagai static files
    - _Requirements: semua requirement_
- [x] 18. WebSocket Layer

  - [x] 18.1 Buat `backend/app/core/websocket_manager.py`
    - `ConnectionManager` class — manage multiple WebSocket connections
    - `broadcast(event_type, data)` — kirim ke semua client
    - `send_personal(websocket, event_type, data)`
    - _Requirements: 1.5, 2.10_
  - [x] 18.2 Buat `backend/app/routers/ws.py`
    - `WS /ws` endpoint — terima dan maintain koneksi WebSocket
    - Event types: `device_status`, `bot_progress`, `bot_log`, `captcha_detected`
    - _Requirements: 1.5, 2.10, 9.6_
  - [x] 18.3 Integrasikan WebSocket broadcast ke semua bot services
    - `posting_bot`, `engage_bot`, `job_hunter_bot` emit progress events
    - `device_monitor` emit device status setiap update
    - _Requirements: 1.5, 2.10_
- [x] 19. Checkpoint — Backend Lengkap

  - Jalankan semua test backend, pastikan semua router dapat diakses (smoke test dengan curl/httpx).
  - Tanya user jika ada pertanyaan sebelum mulai frontend.
- [x] 20. Frontend — Atoms & Molecules

  - [x] 20.1 Buat atoms di `frontend/src/components/atoms/`
    - `Button.tsx` — variant: primary, secondary, danger, ghost; size: sm, md, lg
    - `Badge.tsx` — variant: success, error, warning, info, pending
    - `Input.tsx` — text input dengan label dan error state
    - `Textarea.tsx` — textarea dengan character count display
    - `Select.tsx` — dropdown dengan opsi
    - `Spinner.tsx` — loading indicator
    - `StatusDot.tsx` — indikator status berwarna (connected/disconnected)
    - _Requirements: semua UI_
  - [x] 20.2 Buat molecules di `frontend/src/components/molecules/`
    - `FormField.tsx` — wrapper Input/Select/Textarea dengan label dan error message
    - `LogRow.tsx` — satu baris di tabel log (waktu, aksi, status Badge, durasi)
    - `ContentVariantCard.tsx` — card untuk satu variasi konten dengan tombol pilih/edit
    - `JobCard.tsx` — card lowongan kerja dengan status dan tombol apply
    - `ScheduleItem.tsx` — item jadwal dengan toggle aktif/nonaktif
    - `StatCard.tsx` — card statistik dengan angka besar dan label
    - _Requirements: 2.6, 5.10, 7.3_
- [x] 21. Frontend — Organisms & Templates

  - [x] 21.1 Buat organisms di `frontend/src/components/organisms/`
    - `ContentForm.tsx` — form lengkap untuk generate konten (Requirements 2.1)
    - `PromoForm.tsx` — form untuk generate konten promosi (Requirements 3.1)
    - `JobCriteriaForm.tsx` — form kriteria job hunting (Requirements 5.1)
    - `ScheduleForm.tsx` — form buat/edit jadwal dengan cron picker (Requirements 6.1)
    - `LogTable.tsx` — tabel history lengkap dengan filter dan pagination (Requirements 7.3)
    - `ContentPreview.tsx` — preview konten ala LinkedIn dengan character count (Requirements 10.3)
    - `AIUsageChart.tsx` — chart penggunaan AI per provider (Requirements 8.2)
    - `DeviceStatusBar.tsx` — bar status HP dengan StatusDot dan tombol reconnect (Requirements 1.5)
    - _Requirements: 2.1, 3.1, 5.1, 6.1, 7.3, 8.2, 10.3_
  - [x] 21.2 Buat templates di `frontend/src/components/templates/`
    - `DashboardLayout.tsx` — sidebar navigasi + main content area + DeviceStatusBar
    - `StudioLayout.tsx` — dua kolom: form kiri + preview kanan
    - _Requirements: semua halaman_
- [x] 22. Frontend — Pages & Hooks

  - [x] 22.1 Buat `frontend/src/hooks/`

    - `useWebSocket.ts` — koneksi ke `/ws`, handle reconnect, expose event stream
    - `useDeviceStatus.ts` — subscribe device_status events dari WebSocket
    - `useBotProgress.ts` — subscribe bot_progress events, expose progress state
    - `useApiMutation.ts` — wrapper fetch untuk POST/PUT/DELETE dengan loading/error state
    - _Requirements: 1.5, 2.10_
  - [x] 22.2 Buat `frontend/src/pages/index.tsx` — halaman Dashboard Overview

    - StatCard untuk: total posts, total interaksi, total aplikasi kerja, status HP
    - Grafik aktivitas mingguan (Requirements 5.10, 7.3)
    - _Requirements: 5.10, 7.3_
  - [x] 22.3 Buat `frontend/src/pages/studio.tsx` — halaman Studio (Module A & B)

    - Tab: "Buat Konten" dan "Buat Promosi"
    - ContentForm / PromoForm → ContentVariantCard hasil → ContentPreview → tombol Post/Save Draft
    - Tampilkan progress bot_progress via `useBotProgress` (Requirements 2.10)
    - Warn + tawarkan split thread jika > 3.000 karakter (Requirements 10.4)
    - _Requirements: 2.1–2.11, 3.1–3.7, 10.1–10.6_
  - [x] 22.4 Buat `frontend/src/pages/engage.tsx` — halaman Engage (Module C)

    - Tombol Start/Stop sesi, konfigurasi filter topik
    - Live log stream via WebSocket
    - Tabel interaksi terakhir
    - _Requirements: 4.1–4.10_
  - [x] 22.5 Buat `frontend/src/pages/jobs.tsx` — halaman Job Hunter (Module D)

    - JobCriteriaForm + daftar JobCard hasil
    - Statistik breakdown status (Requirements 5.10)
    - Tabel job_applications dengan filter
    - _Requirements: 5.1–5.10_
  - [x] 22.6 Buat `frontend/src/pages/schedule.tsx` — halaman Penjadwalan

    - Kalender visual dengan jadwal aktif berwarna (Requirements 6.5)
    - Tabel jadwal + ScheduleForm modal untuk tambah/edit
    - _Requirements: 6.1–6.7_
  - [x] 22.7 Buat `frontend/src/pages/history.tsx` — halaman History & Logs

    - LogTable dengan filter status, action_type, date range
    - Modal detail log dengan screenshot preview dan stack trace
    - Tombol Export CSV per entitas (Requirements 7.5, 11.1–11.4)
    - _Requirements: 7.1–7.7, 11.1–11.4_
  - [X] 22.8 Buat `frontend/src/pages/settings.tsx` — halaman Settings

    - Form konfigurasi: provider AI, batas harian, delay range, path CV
    - Tampilkan updated_at timestamp (Requirements 12.5)
    - Validasi sisi client sebelum submit, tampilkan field error dari 422 response (Requirements 12.3)
    - _Requirements: 12.1–12.5_
  - [x] 22.9 Buat `frontend/src/lib/api.ts` — typed API client

    - Fungsi fetch untuk setiap endpoint backend dengan TypeScript types
    - Handle error dan 422 validation error response
    - _Requirements: semua API_
- [x] 23. Checkpoint — Frontend Selesai

  - Pastikan semua halaman dapat dirender tanpa error di browser, semua API call terkoneksi.
  - Tanya user jika ada pertanyaan.
- [X] 24. Testing — Unit & Property Tests Backend

  - [x] 24.1 Tulis unit test untuk `anti_ban.py` — semua metode
    - Test: `check_daily_limit` return False setelah batas tercapai
    - Test: `detect_captcha` mendeteksi screenshot dengan teks CAPTCHA
    - _Requirements: 9.1–9.7_
  - [x] 24.2 Tulis unit test untuk `csv_exporter.py`
    - Test: output UTF-8 BOM, baris header, data row count sesuai filter
    - _Requirements: 11.1–11.4_
  - [x] 24.3 Tulis unit test untuk `settings` router — validasi input
    - Test: kirim batas harian negatif → 422 dengan pesan spesifik
    - Test: delay min > max → 422 dengan pesan spesifik
    - _Requirements: 12.2, 12.3_
  - [x] 24.4 Tulis unit test untuk `scheduler_service.py`
    - Test: toggle aktif → nonaktif → aktif, next_run dihitung dari sekarang
    - Test: retry logic 3x saat HP disconnect
    - _Requirements: 6.4, 6.6, 6.7_
- [x] 25. Integrasi & Polish

  - [x] 25.1 Tambahkan environment variable documentation di `README.md`
    - Semua env vars yang diperlukan dengan contoh nilai
  - [x] 25.2 Buat `backend/app/core/exceptions.py` — custom exception handlers untuk FastAPI
    - Handler untuk `ADBTimeoutError`, `AllProvidersExhaustedError`, `OCRInsufficientTextError`
    - Return JSON error response yang konsisten dengan format `{detail, field}`
    - _Requirements: 1.4, 8.4, 12.3_
  - [x] 25.3 Tambahkan static file serving untuk screenshots di `main.py`
    - Mount `/static` directory untuk serve screenshot images ke frontend
    - _Requirements: 7.2, 7.4_
  - [x] 25.4 Verifikasi semua property test pass dan task selesai
    - Jalankan semua test: `pytest backend/tests/ -v`
    - Tanya user jika ada pertanyaan atau penyesuaian yang diperlukan.

---

## Catatan

- Task bertanda `*` bersifat opsional dan bisa dilewati untuk MVP yang lebih cepat
- Setiap task mereferensikan requirement spesifik untuk traceability
- Checkpoint memastikan validasi bertahap sebelum fase berikutnya
- Property test memvalidasi correctness properties dari requirements.md
- Unit test memvalidasi contoh spesifik dan edge cases
