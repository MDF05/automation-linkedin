# LinkedIn Automation Bot

Bot otomatis untuk mengelola posting, interaksi, dan pencarian lowongan di LinkedIn, dikendalikan via web dashboard dan memanfaatkan HP Android melalui koneksi USB (ADB).

---

## Goals

- Otomatisasi pembuatan konten LinkedIn yang menarik dan relevan
- Otomatisasi interaksi dengan audience (komentar, reaksi)
- Otomatisasi pencarian dan apply lowongan kerja
- Dashboard web yang lengkap untuk mengelola semua aktivitas
- Pencatatan log dan history yang solid dan terstruktur
- Memanfaatkan AI free tier (DeepSeek, ChatGPT, Claude, Perplexity) via HP

---

## Full Stack Architecture

```
┌─────────────────────────────────────────────────────┐
│                  WEB DASHBOARD                       │
│              (React / Next.js)                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │Dashboard │ │ Posting  │ │ History  │ │  Jobs  │ │
│  │(metrics) │ │ Studio   │ │  & Logs  │ │ Hunter │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘ │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP / WebSocket
┌─────────────────────▼───────────────────────────────┐
│              BACKEND API (FastAPI / Python)          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ Content  │ │   Bot    │ │   AI     │ │  Log   │ │
│  │Generator │ │ Executor │ │ Service  │ │Service │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘ │
└──────────────────┬──────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
┌───────▼──────┐    ┌─────────▼──────┐
│  PostgreSQL  │    │   HP Android   │
│  (Database)  │    │  via ADB/USB   │
└──────────────┘    └────────────────┘
```

---

## Tech Stack

| Layer               | Technology                              |
| ------------------- | --------------------------------------- |
| Frontend            | Next.js (React) + TailwindCSS           |
| Backend             | Python + FastAPI                        |
| Database            | PostgreSQL + SQLAlchemy                 |
| Task Queue          | APScheduler                             |
| HP Control          | uiautomator2 / ADB                      |
| Screen Reading      | adb screencap + EasyOCR                 |
| AI (API)            | DeepSeek API, Groq (Llama3 free)        |
| AI (Browser via HP) | ChatGPT web, Claude web, Perplexity web |
| Image Generation    | Ideogram.ai, Playground.ai (free tier)  |
| Search Referensi    | googlesearch-python, Perplexity web     |
| Containerization    | Docker Compose                          |

---

## Project Structure

Menggunakan prinsip **Atomic Design** di frontend dan **modular service layer** di backend — setiap file kecil, satu tanggung jawab, mudah dibaca dan di-debug.

```
linkedin-bot/
│
├── backend/
│   ├── main.py                         # FastAPI app entry point
│   ├── config.py                       # Env vars & app config
│   ├── database.py                     # PostgreSQL session & engine
│   │
│   ├── api/                            # Route handlers (thin layer, no logic)
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── posts.py                # POST /posts, GET /posts, dll
│   │   │   ├── bot.py                  # POST /bot/run, GET /bot/status
│   │   │   ├── logs.py                 # GET /logs, GET /logs/{id}
│   │   │   ├── interactions.py         # GET /interactions
│   │   │   ├── jobs.py                 # GET /jobs, POST /jobs/search
│   │   │   ├── schedules.py            # CRUD /schedules
│   │   │   ├── settings.py             # GET/PUT /settings
│   │   │   └── ai_usage.py             # GET /ai-usage
│   │
│   ├── models/                         # SQLAlchemy ORM models (1 file per tabel)
│   │   ├── __init__.py
│   │   ├── post.py                     # Model: posts
│   │   ├── bot_log.py                  # Model: bot_logs
│   │   ├── interaction.py              # Model: interactions
│   │   ├── job_application.py          # Model: job_applications
│   │   ├── ai_usage.py                 # Model: ai_usage
│   │   └── schedule.py                 # Model: schedules
│   │
│   ├── schemas/                        # Pydantic schemas (request/response)
│   │   ├── __init__.py
│   │   ├── post.py                     # PostCreate, PostRead, PostUpdate
│   │   ├── bot_log.py                  # BotLogRead
│   │   ├── interaction.py              # InteractionRead
│   │   ├── job_application.py          # JobCreate, JobRead
│   │   ├── ai_usage.py                 # AIUsageRead
│   │   └── schedule.py                 # ScheduleCreate, ScheduleRead
│   │
│   ├── services/                       # Business logic (1 service per domain)
│   │   ├── __init__.py
│   │   │
│   │   ├── ai/                         # AI provider integrations
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # Abstract AIProvider class
│   │   │   ├── deepseek.py             # DeepSeek API client
│   │   │   ├── groq.py                 # Groq API client
│   │   │   ├── chatgpt_web.py          # ChatGPT via HP browser (ADB)
│   │   │   ├── claude_web.py           # Claude via HP browser (ADB)
│   │   │   ├── perplexity_web.py       # Perplexity via HP browser (ADB)
│   │   │   └── provider_chain.py       # Fallback chain manager
│   │   │
│   │   ├── adb/                        # Android device control
│   │   │   ├── __init__.py
│   │   │   ├── client.py               # ADB connection & device detection
│   │   │   ├── gestures.py             # Tap, swipe, scroll, type
│   │   │   ├── screenshot.py           # Capture & save screenshots
│   │   │   ├── clipboard.py            # Copy/paste via ADB
│   │   │   └── app_navigator.py        # Open apps, navigate screens
│   │   │
│   │   ├── ocr/                        # Screen reading
│   │   │   ├── __init__.py
│   │   │   ├── engine.py               # EasyOCR / pytesseract wrapper
│   │   │   ├── extractor.py            # Extract structured data from screenshots
│   │   │   └── filters.py              # Filter & clean extracted text
│   │   │
│   │   ├── bot/                        # Bot execution modules
│   │   │   ├── __init__.py
│   │   │   ├── base_bot.py             # Abstract bot dengan logging & error handling
│   │   │   ├── poster_bot.py           # Module A: posting konten
│   │   │   ├── engage_bot.py           # Module C: komentar & interaksi
│   │   │   └── job_bot.py              # Module D: cari & apply lowongan
│   │   │
│   │   ├── content/                    # Content generation
│   │   │   ├── __init__.py
│   │   │   ├── generator.py            # Orchestrate: search → AI → format
│   │   │   ├── search.py               # Google / Perplexity reference search
│   │   │   ├── formatter.py            # Format output per content type
│   │   │   └── thread_splitter.py      # Pecah konten panjang jadi thread
│   │   │
│   │   ├── image/                      # Image generation
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # Abstract ImageProvider
│   │   │   ├── ideogram.py             # Ideogram.ai client
│   │   │   └── playground.py           # Playground.ai client
│   │   │
│   │   ├── anti_ban/                   # Human behavior simulation
│   │   │   ├── __init__.py
│   │   │   ├── delay.py                # Random delay generator
│   │   │   ├── limiter.py              # Daily action limit checker
│   │   │   └── scroll_simulator.py     # Variable speed scroll patterns
│   │   │
│   │   ├── scheduler/                  # Task scheduling
│   │   │   ├── __init__.py
│   │   │   ├── runner.py               # APScheduler setup & lifecycle
│   │   │   └── task_registry.py        # Register & resolve task types
│   │   │
│   │   ├── log_service.py              # Write to bot_logs & ai_usage
│   │   ├── export_service.py           # CSV export logic
│   │   └── settings_service.py         # Read/write system config
│   │
│   ├── websocket/                      # Real-time communication
│   │   ├── __init__.py
│   │   ├── manager.py                  # WebSocket connection manager
│   │   └── events.py                   # Event types & broadcast helpers
│   │
│   ├── migrations/                     # Alembic DB migrations
│   │   └── versions/
│   │
│   └── requirements.txt
│
├── frontend/                           # Next.js + TailwindCSS
│   ├── src/
│   │   │
│   │   ├── components/                 # Atomic Design Structure
│   │   │   │
│   │   │   ├── atoms/                  # Elemen UI terkecil, tidak bisa dipecah lagi
│   │   │   │   ├── Button/
│   │   │   │   │   ├── Button.tsx
│   │   │   │   │   ├── Button.types.ts
│   │   │   │   │   └── index.ts
│   │   │   │   ├── Badge/
│   │   │   │   │   ├── Badge.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   ├── Input/
│   │   │   │   │   ├── Input.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   ├── Textarea/
│   │   │   │   │   ├── Textarea.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   ├── Select/
│   │   │   │   │   ├── Select.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   ├── Spinner/
│   │   │   │   │   ├── Spinner.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   ├── StatusDot/          # Online/offline indicator dot
│   │   │   │   │   ├── StatusDot.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   └── Icon/
│   │   │   │       ├── Icon.tsx
│   │   │   │       └── index.ts
│   │   │   │
│   │   │   ├── molecules/              # Gabungan atom, satu fungsi spesifik
│   │   │   │   ├── FormField/          # Label + Input + error message
│   │   │   │   │   ├── FormField.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   ├── SearchBar/
│   │   │   │   │   ├── SearchBar.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   ├── StatCard/           # Metric card (angka + label + trend)
│   │   │   │   │   ├── StatCard.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   ├── LogRow/             # Satu baris di tabel log
│   │   │   │   │   ├── LogRow.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   ├── PostCard/           # Card preview satu post
│   │   │   │   │   ├── PostCard.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   ├── JobCard/            # Card satu lowongan
│   │   │   │   │   ├── JobCard.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   ├── AIProviderBadge/    # Badge provider AI + usage bar
│   │   │   │   │   ├── AIProviderBadge.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   ├── ProgressStep/       # Satu langkah di bot execution progress
│   │   │   │   │   ├── ProgressStep.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   └── ToastNotif/         # Notifikasi toast
│   │   │   │       ├── ToastNotif.tsx
│   │   │   │       └── index.ts
│   │   │   │
│   │   │   ├── organisms/              # Gabungan molecules, section UI lengkap
│   │   │   │   ├── Sidebar/
│   │   │   │   │   ├── Sidebar.tsx
│   │   │   │   │   ├── SidebarItem.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   ├── TopBar/
│   │   │   │   │   ├── TopBar.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   ├── DeviceStatus/       # Panel status HP + koneksi ADB
│   │   │   │   │   ├── DeviceStatus.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   ├── StudioForm/         # Form buat konten (Module A & B)
│   │   │   │   │   ├── StudioForm.tsx
│   │   │   │   │   ├── ContentTypeSelector.tsx
│   │   │   │   │   ├── ToneSelector.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   ├── ContentPreview/     # Preview post sebelum publish
│   │   │   │   │   ├── ContentPreview.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   ├── LogTable/           # Tabel history + filter
│   │   │   │   │   ├── LogTable.tsx
│   │   │   │   │   ├── LogFilters.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   ├── LogDetail/          # Drawer/modal detail satu log
│   │   │   │   │   ├── LogDetail.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   ├── JobTable/           # Tabel lowongan + status
│   │   │   │   │   ├── JobTable.tsx
│   │   │   │   │   ├── JobFilters.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   ├── BotProgressPanel/   # Real-time eksekusi bot via WebSocket
│   │   │   │   │   ├── BotProgressPanel.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   ├── SchedulerCalendar/  # Kalender visual jadwal
│   │   │   │   │   ├── SchedulerCalendar.tsx
│   │   │   │   │   └── index.ts
│   │   │   │   └── AIUsagePanel/       # Panel monitoring AI usage
│   │   │   │       ├── AIUsagePanel.tsx
│   │   │   │       └── index.ts
│   │   │   │
│   │   │   └── templates/              # Layout per halaman (tanpa data)
│   │   │       ├── DashboardTemplate/
│   │   │       │   ├── DashboardTemplate.tsx
│   │   │       │   └── index.ts
│   │   │       ├── StudioTemplate/
│   │   │       │   ├── StudioTemplate.tsx
│   │   │       │   └── index.ts
│   │   │       ├── HistoryTemplate/
│   │   │       │   ├── HistoryTemplate.tsx
│   │   │       │   └── index.ts
│   │   │       ├── JobsTemplate/
│   │   │       │   ├── JobsTemplate.tsx
│   │   │       │   └── index.ts
│   │   │       └── SettingsTemplate/
│   │   │           ├── SettingsTemplate.tsx
│   │   │           └── index.ts
│   │   │
│   │   ├── pages/                      # Next.js pages (hanya compose template + data)
│   │   │   ├── index.tsx               # /  → Dashboard
│   │   │   ├── studio.tsx              # /studio
│   │   │   ├── history.tsx             # /history
│   │   │   ├── jobs.tsx                # /jobs
│   │   │   ├── scheduler.tsx           # /scheduler
│   │   │   └── settings.tsx            # /settings
│   │   │
│   │   ├── hooks/                      # Custom React hooks
│   │   │   ├── useWebSocket.ts         # WebSocket connection & events
│   │   │   ├── useDeviceStatus.ts      # HP connection status
│   │   │   ├── useBotExecution.ts      # Trigger & monitor bot run
│   │   │   ├── usePosts.ts             # CRUD posts
│   │   │   ├── useLogs.ts              # Fetch & filter logs
│   │   │   ├── useJobs.ts              # Job search & apply
│   │   │   └── useAIUsage.ts           # AI usage stats
│   │   │
│   │   ├── services/                   # API client (axios/fetch wrappers)
│   │   │   ├── api.ts                  # Base axios instance + interceptors
│   │   │   ├── posts.service.ts
│   │   │   ├── bot.service.ts
│   │   │   ├── logs.service.ts
│   │   │   ├── jobs.service.ts
│   │   │   ├── schedules.service.ts
│   │   │   └── settings.service.ts
│   │   │
│   │   ├── store/                      # State management (Zustand)
│   │   │   ├── botStore.ts             # Bot status, running state
│   │   │   ├── deviceStore.ts          # HP connection state
│   │   │   ├── notifStore.ts           # Toast notifications
│   │   │   └── settingsStore.ts        # App settings cache
│   │   │
│   │   ├── types/                      # TypeScript types & interfaces
│   │   │   ├── post.types.ts
│   │   │   ├── log.types.ts
│   │   │   ├── job.types.ts
│   │   │   ├── bot.types.ts
│   │   │   └── api.types.ts
│   │   │
│   │   └── lib/                        # Utilities & helpers
│   │       ├── constants.ts            # App-wide constants
│   │       ├── formatters.ts           # Date, number, text formatters
│   │       └── validators.ts           # Form validation helpers
│   │
│   ├── public/
│   └── package.json
│
└── docker-compose.yml                  # PostgreSQL + Backend + Frontend
```

### Prinsip Atomic Design yang Diterapkan

| Layer | Isi | Contoh |
|---|---|---|
| **Atoms** | Elemen UI terkecil, tidak bisa dipecah | Button, Badge, Input, Spinner |
| **Molecules** | Gabungan atoms dengan satu fungsi | FormField, StatCard, PostCard |
| **Organisms** | Section UI lengkap, bisa berdiri sendiri | StudioForm, LogTable, Sidebar |
| **Templates** | Layout halaman tanpa data nyata | DashboardTemplate, StudioTemplate |
| **Pages** | Compose template + inject data dari hooks | index.tsx, studio.tsx |

### Prinsip Backend Modular

- Setiap **service** punya folder sendiri dengan file yang fokus pada satu concern
- **API routes** hanya menerima request dan memanggil service — tidak ada logic di sini
- **Models** dan **Schemas** dipisah — ORM model tidak bercampur dengan Pydantic schema
- Setiap **AI provider** adalah class tersendiri yang mewarisi `base.py` — mudah tambah provider baru

---

## Modules & Options

### Module A — Content Posting (Studio)

Flow:

```
Input topik/ide dari user
    ↓
Search Google / Perplexity → kumpulkan referensi
    ↓
AI (DeepSeek / ChatGPT) → expand & tulis konten menarik
    ↓
Pilih tone & format konten
    ↓
Generate image jika diperlukan (Ideogram / Playground AI)
    ↓
Preview → user approve / edit
    ↓
Post via HP (LinkedIn App atau Mobile Browser)
    ↓
Catat ke database (post_id, konten, waktu, status)
```

Sub-type konten yang didukung:

- **Storytelling** — cerita personal / pengalaman
- **Tips & List** — konten edukatif berformat list
- **Pertanyaan / Polling** — konten interaktif untuk engagement
- **Kutipan Inspiratif** — quote + image
- **Video Script** — naskah untuk konten video
- **Thread** — rangkaian post bersambung

---

### Module B — Promosi (Promotion Generator)

Flow:

```
Input:
  - Deskripsi jasa/produk
  - Tipe promosi (penawaran spesial / portfolio / testimonial)
  - List item yang dipromosikan
    ↓
AI generate copywriting promosi
    ↓
Generate image promosi (Canva template / Ideogram)
    ↓
Susun caption + hashtag relevan
    ↓
Preview → Schedule atau langsung post
    ↓
Catat ke database
```

---

### Module C — Auto Interaksi (Engage)

Flow:

```
Scroll beranda LinkedIn di HP
    ↓
Screenshot + OCR → baca teks post menarik
    ↓
Buka browser HP → paste ke ChatGPT / DeepSeek web
    ↓
Copy jawaban / komentar yang dihasilkan AI
    ↓
Kembali ke LinkedIn → paste sebagai komentar
    ↓
Catat interaksi ke database (target post, author, konten komentar, waktu)
```

Catatan teknis:

- Gunakan `uiautomator2` untuk kontrol gestur & navigasi HP
- OCR via `EasyOCR` atau `pytesseract` untuk baca teks layar
- Clipboard otomatis via `adb shell input`
- Simulasi delay manusia untuk menghindari deteksi bot

---

### Module D — Job Hunter & Auto Apply

Flow:

```
Input kriteria:
  - Judul posisi, skill, lokasi, range gaji
    ↓
Buka LinkedIn Jobs di HP browser
    ↓
Search dengan filter kriteria
    ↓
Scrape & simpan daftar lowongan ke database
    ↓
Filter sesuai prioritas user
    ↓
Easy Apply otomatis (isi form, upload CV)
    ↓
Log hasil: status apply, perusahaan, tanggal, notes
    ↓
Export laporan ke CSV
```

---

## Database Schema (PostgreSQL)

```sql
-- Semua konten yang dibuat / diposting
posts (
  id, title, content, content_type,   -- story/tips/promo/question/thread
  status,                              -- draft/scheduled/posted/failed
  platform, image_url,
  scheduled_at, posted_at,
  likes, comments, shares,            -- engagement metrics
  ai_provider_used, prompt_used,
  created_at, updated_at
)

-- Log detail setiap eksekusi bot
bot_logs (
  id, post_id, action,                -- generate/post/comment/apply/search
  status,                             -- success/failed/running
  message, error_detail,
  screenshot_path,
  duration_ms, created_at
)

-- Interaksi dengan orang lain di LinkedIn
interactions (
  id, target_post_url, target_author,
  action_type,                        -- comment/react/share
  content_sent, status,
  created_at
)

-- Lowongan kerja & status apply
job_applications (
  id, job_title, company, location,
  salary_range, job_url,
  status,                             -- found/applied/rejected/interview/offer
  applied_at, notes,
  created_at, updated_at
)

-- Tracking penggunaan AI (untuk monitor free tier limit)
ai_usage (
  id, provider,                       -- deepseek/chatgpt/claude/perplexity/groq
  prompt_tokens, completion_tokens,
  cost_estimate, created_at
)

-- Jadwal otomatis
schedules (
  id, task_type, cron_expression,
  is_active, last_run, next_run,
  config_json, created_at
)
```

---

## Dashboard Pages

### 1. Dashboard (Home)

- Total posts, success rate, engagement metrics (likes/comments/shares)
- Status koneksi HP (connected / disconnected)
- Status bot (running / idle / error)
- Recent activity feed
- Quick action buttons

### 2. Studio (Buat Konten)

- Form input topik / ide
- Pilih module: Posting / Promosi / Interaktif
- Pilih tone & format
- Preview hasil generate AI
- Editor untuk revisi sebelum posting
- Tombol: Schedule / Post Sekarang / Simpan Draft

### 3. History & Logs

- Tabel semua konten dengan kolom lengkap
- Filter by: status, tipe, tanggal, platform
- Search konten
- Detail per post: konten lengkap, gambar, engagement, log eksekusi
- Screenshot log dari sesi bot
- Export ke CSV

### 4. Job Hunter

- Form input kriteria lowongan
- Tabel lowongan yang ditemukan
- Status per lowongan (found / applied / interview / rejected)
- Notes & catatan per lowongan
- Statistik: total apply, response rate

### 5. Scheduler

- Buat & kelola jadwal posting otomatis
- Kalender visual jadwal konten
- Toggle aktif/nonaktif per jadwal

---

## Environment Variables

Copy `.env.example` ke `.env` dan isi nilai yang sesuai:

```bash
cp .env.example .env
```

### PostgreSQL

| Variable | Deskripsi | Contoh | Wajib |
|---|---|---|---|
| `POSTGRES_DB` | Nama database PostgreSQL | `linkedin_bot` | ✅ Ya |
| `POSTGRES_USER` | Username database | `postgres` | ✅ Ya |
| `POSTGRES_PASSWORD` | Password database | `password` | ✅ Ya |
| `POSTGRES_HOST` | Hostname database (nama service Docker) | `postgres` | ✅ Ya |
| `POSTGRES_PORT` | Port database | `5432` | ✅ Ya |
| `DATABASE_URL` | Connection string lengkap untuk SQLAlchemy async | `postgresql+asyncpg://postgres:password@postgres:5432/linkedin_bot` | ✅ Ya |

### ADB (Android Debug Bridge)

| Variable | Deskripsi | Contoh | Wajib |
|---|---|---|---|
| `ADB_TIMEOUT` | Timeout (detik) untuk perintah ADB ke HP Android | `30` | ✅ Ya |

### AI Provider API Keys

Semua API key AI bersifat **opsional** — aplikasi mendukung free tier. Isi minimal satu provider agar fitur generate konten berfungsi.

| Variable | Deskripsi | Contoh | Wajib |
|---|---|---|---|
| `DEEPSEEK_API_KEY` | API key DeepSeek (free tier tersedia) | `sk-...` | ⬜ Opsional |
| `GROQ_API_KEY` | API key Groq untuk model Llama3 (free tier tersedia) | `gsk_...` | ⬜ Opsional |
| `IDEOGRAM_API_KEY` | API key Ideogram.ai untuk generate gambar (free tier tersedia) | `...` | ⬜ Opsional |

> **Catatan:** Jika tidak ada API key yang diisi, bot tetap bisa menggunakan AI berbasis browser (ChatGPT web, Claude web, Perplexity web) via HP Android.

### Backend

| Variable | Deskripsi | Contoh | Wajib |
|---|---|---|---|
| `ALLOWED_ORIGINS` | CORS origins yang diizinkan untuk akses API | `http://localhost:3000` | ✅ Ya |
| `SCREENSHOTS_DIR` | Path direktori penyimpanan screenshot bot | `/app/static/screenshots` | ✅ Ya |

### Frontend

| Variable | Deskripsi | Contoh | Wajib |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | URL base API backend | `http://localhost:8000` | ✅ Ya |
| `NEXT_PUBLIC_WS_URL` | URL WebSocket backend untuk update real-time | `ws://localhost:8000/ws` | ✅ Ya |

---

## Development Phases

```
Phase 1 — Setup & Infrastructure
  - Setup PostgreSQL + Docker Compose
  - Backend FastAPI skeleton + koneksi DB
  - Frontend Next.js skeleton + routing

Phase 2 — Module A: Auto Posting (text only)
  - ADB setup + kontrol HP basic
  - AI service (DeepSeek/Groq) untuk generate konten
  - Post via LinkedIn browser di HP
  - Log ke database

Phase 3 — Module B: Image & Promosi
  - Integrasi image generation (Ideogram)
  - Template promosi
  - Upload gambar + caption

Phase 4 — Module C: Auto Engage
  - OCR layar HP
  - Auto comment via AI
  - Tracking interaksi

Phase 5 — Module D: Job Hunter
  - Scrape lowongan LinkedIn
  - Auto Easy Apply
  - Tracking & reporting

Phase 6 — Polish
  - Dashboard analytics lengkap
  - Scheduler visual
  - Anti-ban: delay simulator, random behavior
  - Export & reporting
```

---

## Catatan Penting

- **Anti-ban strategy**: simulasi delay manusia, random interval antar aksi, batasi jumlah aksi per hari
- **HP**: wajib Android (untuk ADB), aktifkan USB Debugging
- **AI Free Tier**: monitor usage via tabel `ai_usage` agar tidak melebihi limit
- **CV Template**: siapkan template CV yang bisa diisi otomatis untuk module job apply
- **Screenshot logging**: setiap aksi bot disertai screenshot untuk audit trail
#   a u t o m a t i o n - l i n k e d i n  
 