# VidNotes AI 🎥 📝
> **Multimodal Lecture Ingestion, RAG Indexing & AI-Assisted Study Intelligence Platform**

VidNotes AI is a full-stack, distributed system engineered to transform raw educational videos, technical webinars, and YouTube lectures into structured study guides, timestamped slide keyframes, active-recall flashcard decks, interactive quizzes, concept mind maps, and a low-latency semantic RAG study copilot.

![VidNotes Dashboard Banner](vidnotes_app_banner.png)

---

## 📑 Table of Contents
- [1. High-Level Architecture](#1-high-level-architecture)
- [2. Technology Stack & Design Decisions ("Why Used")](#2-technology-stack--design-decisions-why-used)
- [3. End-to-End Multimodal Data Pipeline](#3-end-to-end-multimodal-data-pipeline)
  - [Stage 1: Ingestion & Subtitle Normalization](#stage-1-ingestion--subtitle-normalization)
  - [Stage 2: Keyframe Extraction & Visual Deduplication](#stage-2-keyframe-extraction--visual-deduplication)
  - [Stage 3: Knowledge Consolidation & Notes Generation](#stage-3-knowledge-consolidation--notes-generation)
  - [Stage 4: Semantic Chunking & Vector RAG Indexing](#stage-4-semantic-chunking--vector-rag-indexing)
- [4. Database Architecture & Vector Search Schema](#4-database-architecture--vector-search-schema)
- [5. API Design & Key Endpoints](#5-api-design--key-endpoints)
- [6. Resilience, Idempotency & Edge-Case Engineering](#6-resilience-idempotency--edge-case-engineering)
- [7. Step-by-Step Setup & How to Run](#7-step-by-step-setup--how-to-run)
  - [Option A: Docker Compose (Production-Ready)](#option-a-docker-compose-production-ready)
  - [Option B: Manual Local Development](#option-b-manual-local-development)
- [8. Environment Variables Reference](#8-environment-variables-reference)
- [9. Automated Verification & Testing](#9-automated-verification--testing)

---

## 1. High-Level Architecture

VidNotes AI is designed as a decoupled, microservices-oriented platform optimized for compute-heavy video processing, optical character recognition (OCR), vector indexing, and asynchronous AI tasks:

```mermaid
flowchart TB
    subgraph Client_Layer ["Client & Gateway Layer"]
        Browser["🖥️ Web Client (Next.js 16 App Router)"]
        NginxProxy["🌐 Nginx Reverse Proxy / Load Balancer (Port 80)"]
    end

    subgraph App_Layer ["Application & Compute Layer"]
        FastAPIApp["⚡ FastAPI Async Backend Service (Port 8000)"]
        WorkerService["⚙️ Background Pipeline Worker (Idempotent 4-Stage Engine)"]
    end

    subgraph Data_Layer ["Storage & Vector Database Layer"]
        PostgresDB[("🐘 PostgreSQL + pgvector (Relational Data & 1536d Embeddings)")]
        RedisBroker[("⚡ Redis Message Broker & State Cache")]
        MinIOObject[("📦 MinIO / S3 Storage (Video Files & Keyframe Slides)")]
    end

    subgraph AI_Layer ["AI & Multimodal Services"]
        LLMProvider["🤖 LLM Cascade (Mistral AI / OpenAI / Google Gemini)"]
        OCRLocal["👁️ EasyOCR + PyTorch (Local Slide Text Extraction)"]
        FFmpegEng["🎞️ ffmpeg / ffprobe (Scene Analysis & Audio Slicing)"]
        WhisperASR["🎙️ Faster-Whisper ASR Engine (Fallback Transcription)"]
    end

    Browser <-->|HTTP / WebSocket / RAG Streaming| NginxProxy
    NginxProxy -->|/api/v1/*| FastAPIApp
    NginxProxy -->|/vidnotes-storage/*| MinIOObject
    NginxProxy -->|/*| Browser

    FastAPIApp <-->|Async SQLAlchemy| PostgresDB
    FastAPIApp <-->|Task Dispatch & Status| RedisBroker
    FastAPIApp <-->|Direct RAG Retrieval| PostgresDB
    FastAPIApp <-->|On-Demand Study Gen| LLMProvider

    WorkerService <-->|Task Queue| RedisBroker
    WorkerService <-->|Read / Write Metadata| PostgresDB
    WorkerService <-->|Keyframe Slide Uploads| MinIOObject
    WorkerService -->|Local Vision & Audio| OCRLocal
    WorkerService -->|Local Video Extraction| FFmpegEng
    WorkerService -->|Fallback Audio ASR| WhisperASR
    WorkerService -->|Structured Notes Synthesis| LLMProvider
```

---

## 2. Technology Stack & Design Decisions ("Why Used")

| Layer / Tool | Technology Selected | Rationale & Trade-offs |
| :--- | :--- | :--- |
| **Frontend Framework** | **Next.js 16 (App Router, Turbopack)** | Server-side rendering (SSR), optimized production bundles via Turbopack, and modular route layouts. Enables 3-column independently scrollable workspace layouts (media player, notes, and AI copilot). |
| **Styling & Aesthetics** | **TailwindCSS v4 + Vanilla CSS Variables** | Ultra-responsive UI with custom glassmorphism (`backdrop-filter: blur(24px)`), ambient neon radial gradients, dark/light theme switching, and hardware-accelerated 3D flip cards. |
| **Client-Side Visualizations** | **Mermaid.js** | Dynamically renders responsive SVG concept maps directly from clean LLM markdown strings on the client without raster image generation overhead. |
| **Backend Framework** | **Python FastAPI (Async)** | Native asynchronous request handling (`async`/`await`), auto-generated OpenAPI documentation, fast Pydantic v2 data validation, and seamless integration with Python's scientific ecosystem (`numpy`, `torch`, `easyocr`). |
| **Relational & Vector DB** | **PostgreSQL + pgvector** | Unifies structured relational business data (users, folders, transcripts, notes, keyframes) and 1536-dimensional semantic chunk embeddings in a single ACID database. Eliminates the need to maintain and synchronize a separate dedicated vector database. |
| **Object Storage** | **MinIO (S3-Compatible)** | Decouples large binary blobs (extracted keyframe images, uploaded video/audio files) from the database layer, allowing scalable, high-throughput media serving. |
| **Task Queue & Caching** | **Redis** | High-throughput in-memory message broker and state manager for decoupled background video processing. |
| **Document Export Engine** | **ReportLab & python-docx** | Generates professionally formatted, downloadable `.pdf` and `.docx` study guides with embedded slide keyframe images and structured checklists on the server. |

---

## 3. End-to-End Multimodal Data Pipeline

The pipeline transforms unformatted video/audio streams into clean, structured lecture knowledge and interactive study assets across 4 stages:

```mermaid
flowchart LR
    A["Raw Video / YouTube URL"] --> B["Stage 1: Transcript & ASR Cleaning"]
    B --> C["Stage 2: Keyframe Extraction & OCR Deduplication"]
    C --> D["Stage 3: Multimodal Knowledge & Notes Synthesis"]
    D --> E["Stage 4: Vector Indexing & Semantic RAG"]

    subgraph S1 ["Stage 1"]
        B1["Fetch YouTube Captions / Whisper ASR"]
        B2["Resolve Timestamp Overlaps"]
        B3["Remove Disfluencies & Filler Words"]
        B4["Filter Gibberish & Loops"]
        B1 --> B2 --> B3 --> B4
    end

    subgraph S2 ["Stage 2"]
        C1["ffmpeg Scene Keyframe Extraction"]
        C2["MAE Image Deduplication"]
        C3["EasyOCR Text Extraction"]
        C4["Jaccard Slide Duplicate Suppression"]
        C1 --> C2 --> C3 --> C4
    end

    subgraph S3 ["Stage 3"]
        D1["Normalize Spoken vs Slide Knowledge"]
        D2["Two-Phase LLM Notes Synthesis"]
        D3["Enforce Zero Transcript Dumps"]
        D4["Validate Duplicate Ratio (<20%)"]
        D1 --> D2 --> D3 --> D4
    end

    subgraph S4 ["Stage 4"]
        E1["1000-Char Overlapping Chunks"]
        E2["1536d Vector Embeddings"]
        E3["pgvector HNSW Cosine Indexing"]
        E4["Timestamped RAG Copilot Queries"]
        E1 --> E2 --> E3 --> E4
    end
```

---

### Stage 1: Ingestion & Subtitle Normalization
Raw video subtitles and Whisper transcriptions often suffer from overlapping timestamp segments, stutter disfluencies, and repeated phrase loops caused by audio segment boundaries.

* **Sequential Overlap Trimming (`resolve_overlap_between_segments`):**
  Calculates word n-gram intersection between adjacent transcript cue boundaries ($[t_{start1}, t_{end1}]$ and $[t_{start2}, t_{end2}]$) to eliminate sliding-window repetition.
* **Filler & Disfluency Stripping (`clean_text_fragment`):**
  Removes spoken fillers (`uh`, `um`, `you know`, `like`, `so basically`), audio sound tags (`[Music]`, `[Applause]`), and ASR stutter loops (`the the the` $\rightarrow$ `the`).
* **Gibberish & Noise Filtering (`is_gibberish_or_broken`):**
  Rejects corrupted audio artifacts, consecutive character loops (`aaaa`), unprintable character noise, and empty punctuation fragments.

---

### Stage 2: Keyframe Extraction & Visual Deduplication
Technical lectures frequently stay on the same presentation slide for minutes while the speaker talks, generating dozens of redundant video frames.

* **Scene-Aware Keyframe Slicing:**
  `ffmpeg` samples candidate slide keyframes every 30–120 seconds based on total lecture duration.
* **Mean Absolute Error (MAE) Image Deduplication (`deduplicate_keyframes`):**
  Compares downscaled grayscale matrices ($64 \times 64$) between consecutive candidate frames:
  $$\text{MAE}(I_1, I_2) = \frac{1}{N} \sum_{x,y} |I_1(x, y) - I_2(x, y)|$$
  Frames with $\text{MAE} \le 8.0$ are flagged as identical static slides and discarded.
* **OCR Cleaning & Jaccard Duplicate Suppression (`clean_ocr_text`, `is_duplicate_ocr`):**
  EasyOCR extracts on-screen text, code blocks, and slide bullet points. Extracted text is normalized by stripping IDE line numbers and correcting common OCR character confusions. Duplicate slides are identified using Jaccard token similarity ($\ge 0.82$).

---

### Stage 3: Knowledge Consolidation & Notes Generation
* **Normalized Lecture Schema (`build_normalized_lecture_knowledge`):**
  Combines cleaned spoken transcript segments with on-screen slide text in chronological order without mixing internal debug labels or raw transcript dumps.
* **Two-Phase Prompting Architecture:**
  Splits LLM synthesis into two focused passes to avoid output token limits:
  1. *Pass 1:* Executive Overview, Core Conceptual Notes, and Slide Code Breakdowns.
  2. *Pass 2:* Key Takeaways, Revision Checklist, and Technical Glossary.
* **Quality & Duplicate Validation (`validate_pipeline_metrics`):**
  Enforces a maximum duplicate sentence ratio threshold ($\le 0.20$). If repetitive sentences exceed this threshold, the pipeline automatically applies deduplication before saving to PostgreSQL.

---

### Stage 4: Semantic Chunking & Vector RAG Indexing
* **Text Chunking:**
  Splits the combined lecture transcript and OCR metadata into 1000-character chunks with a 150-character sliding overlap.
* **Vector Embeddings (1536 Dimensions):**
  Embeddings are generated via `mistral-embed`, `text-embedding-3-small`, or Google embeddings.
* **Cosine Similarity Retrieval:**
  Finds the top-$K$ most relevant lecture moments using pgvector:
  $$\text{similarity} = 1 - (\vec{u} \cdot \vec{v}) / (\|\vec{u}\| \|\vec{v}\|)$$
  Returns cited timestamps ($[t_{\text{start}}]$) rendered as clickable badges in the workspace UI that seek the video player to the exact second.

---

## 4. Database Architecture & Vector Search Schema

```mermaid
erDiagram
    USERS ||--o{ FOLDERS : owns
    USERS ||--o{ VIDEOS : creates
    FOLDERS ||--o{ VIDEOS : organizes
    VIDEOS ||--o{ TRANSCRIPT_SEGMENTS : contains
    VIDEOS ||--o{ KEYFRAMES : captures
    VIDEOS ||--o{ VIDEO_CHUNKS : embeds
    VIDEOS ||--|| NOTES : produces

    USERS {
        int id PK
        string email UK
        string hashed_password
        datetime created_at
    }
    FOLDERS {
        int id PK
        int user_id FK
        string name
        int parent_id FK
    }
    VIDEOS {
        string id PK
        int user_id FK
        int folder_id FK
        string title
        string url
        string file_path
        string status
        int duration
        datetime created_at
    }
    TRANSCRIPT_SEGMENTS {
        int id PK
        string video_id FK
        float start_time
        float end_time
        string text
    }
    KEYFRAMES {
        int id PK
        string video_id FK
        float timestamp
        string s3_url
        string ocr_text
        string vision_description
    }
    VIDEO_CHUNKS {
        int id PK
        string video_id FK
        string content
        float start_time
        float end_time
        vector_1536 embedding
    }
    NOTES {
        int id PK
        string video_id FK
        string summary_exec
        string summary_detailed
        string takeaways
        string revision_notes
        string glossary
        json flashcards
        json mcqs
        string mindmap
    }
```

---

## 5. API Design & Key Endpoints

### 🔐 Authentication (`/api/v1/auth`)
* `POST /auth/signup` – Register new user with email and password.
* `POST /auth/login` – Authenticate user and issue JWT bearer token.
* `GET /auth/me` – Retrieve current authenticated user profile.

### 🎥 Video Ingestion & Management (`/api/v1/videos`)
* `POST /videos/youtube` – Ingest YouTube URL, trigger background pipeline worker.
* `POST /videos/upload` – Upload raw video/audio file (`.mp4`, `.mp3`, `.wav`), upload to MinIO, trigger pipeline.
* `GET /videos/` – List user workspaces with processing status indicators (`pending`, `processing`, `completed`, `failed`).
* `GET /videos/{video_id}` – Fetch video metadata, duration, source URL, and thumbnail.
* `DELETE /videos/{video_id}` – Cascade delete video, transcript segments, keyframe objects, notes, and vector embeddings.

### 📚 Study Assets & Interactive Intelligence (`/api/v1/videos/{video_id}`)
* `GET /videos/{video_id}/notes` – Retrieve structured Markdown study guide, takeaways, revision checklist, and glossary.
* `GET /videos/{video_id}/transcript` – Fetch timestamped transcript segments for interactive playback sync.
* `GET /videos/{video_id}/keyframes` – Fetch slide keyframes with MinIO URLs, OCR text, and vision context.
* `GET /videos/{video_id}/flashcards` – Retrieve active recall flashcards (on-demand generation with caching).
* `GET /videos/{video_id}/quiz` – Retrieve interactive MCQ assessment quiz with explanations.
* `GET /videos/{video_id}/mindmap` – Retrieve client-rendered Mermaid.js concept diagram (supports `?regenerate=true`).
* `GET /videos/{video_id}/export/{format}` – Download `.pdf`, `.docx`, or `.md` study packages with embedded slide images.
* `POST /videos/{video_id}/chat` – RAG query endpoint returning synthesized answers with timestamped video citations.

---

## 6. Resilience, Idempotency & Edge-Case Engineering

1. **Retry Idempotency (`clear_existing_stages`):**
   If a background worker job fails or is retried, the worker cleans up previous partial records (`transcript_segments`, `keyframes`, `video_chunks`, `notes`) before starting, preventing duplicate data.
2. **YouTube 429 & IP Rate Limiting Fallbacks:**
   - Primary: `youtube-transcript-api`
   - Secondary: `yt-dlp` subtitle extraction
   - Tertiary: Audio stream extraction with local Faster-Whisper ASR
3. **On-Demand Study Material Generation:**
   Flashcards, quizzes, and mind maps are generated only when the user selects their respective workspace tabs, reducing upfront LLM API costs and execution latency.
4. **Heuristic Fallback Engine:**
   If external LLM rate limits are reached, the system falls back to an internal heuristic parser to generate structured executive summaries, key learnings, and code blocks from cleaned OCR and transcript data.

---

## 7. Step-by-Step Setup & How to Run

### Option A: Docker Compose (Production-Ready)

#### 1. Clone the repository
```bash
git clone https://github.com/shashwat0010/VidNotesAI.git
cd VidNotesAI
```

#### 2. Configure Environment Variables
Create a `.env` file in the root directory:
```env
# Database Settings
DATABASE_URL=postgresql://vidnotes_user:vidnotes_password@postgres:5432/vidnotes_db

# Security
SECRET_KEY=generate_a_random_32_byte_secret_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# LLM Providers (Provide at least one)
MISTRAL_API_KEY=your_mistral_api_key
OPENAI_API_KEY=your_openai_api_key
GEMINI_API_KEY=your_gemini_api_key

# Storage (MinIO / S3)
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET_NAME=vidnotes-bucket

# Redis Broker
REDIS_URL=redis://redis:6379/0
```

#### 3. Build & Launch Containers
```bash
docker compose up --build -d
```

#### 4. Access Services
* **Frontend Web App:** [http://localhost](http://localhost) (Port 80 via Nginx)
* **Backend API Docs (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
* **MinIO Object Console:** [http://localhost:9001](http://localhost:9001)

---

### Option B: Manual Local Development

#### 1. Backend Setup
```bash
cd backend
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

Start the FastAPI application:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Frontend Setup
```bash
cd ../frontend
npm install
npm run dev
```

The frontend will run at [http://localhost:3000](http://localhost:3000) and automatically proxy API calls to [http://localhost:8000](http://localhost:8000).

---

## 8. Environment Variables Reference

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL connection string with pgvector support | `postgresql://user:pass@localhost:5432/vidnotes_db` |
| `SECRET_KEY` | JWT signing secret | `your-secure-secret-key-32-chars` |
| `MISTRAL_API_KEY` | Mistral API key for notes synthesis & embeddings | `mistral_api_key` |
| `OPENAI_API_KEY` | OpenAI API key (optional fallback) | `sk-...` |
| `GEMINI_API_KEY` | Google Gemini API key (optional fallback) | `AIzaSy...` |
| `S3_ENDPOINT` | MinIO / AWS S3 endpoint URL | `http://localhost:9000` |
| `S3_ACCESS_KEY` | Object storage access key | `minioadmin` |
| `S3_SECRET_KEY` | Object storage secret key | `minioadmin` |
| `S3_BUCKET_NAME` | Storage bucket name for keyframes & media | `vidnotes-bucket` |
| `REDIS_URL` | Redis broker connection URI | `redis://localhost:6379/0` |

---

## 9. Automated Verification & Testing

The pipeline cleaning and deduplication engine includes an automated test suite verifying edge-case handling across text overlaps, OCR cleanup, gibberish filtering, and retry idempotency:

```bash
# Run the pipeline cleaning unit tests
cd backend
python tests/test_pipeline_cleaning.py
```

### Test Suite Output:
```text
==================================================
Running Pipeline Cleaning & Deduplication Tests
==================================================
[PASS] Transcript overlap & stutter removal test passed.
[PASS] Gibberish and broken fragment filtering test passed.
[PASS] OCR normalization & duplicate detection test passed.
[PASS] Multimodal structured knowledge test passed.
[PASS] Pipeline validation & duplicate ratio test passed.
[PASS] Retry idempotency clear stages test passed.
==================================================
All 6 Pipeline Cleaning Unit Tests Passed!
==================================================
```

---

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).
