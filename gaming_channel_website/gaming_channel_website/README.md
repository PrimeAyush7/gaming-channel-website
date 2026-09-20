# NEXUS GAMING — Official Content & Downloads Portal

A high-performance, full-stack gaming website designed specifically for gaming YouTube channels. Built with an immersive Dark Purple + Void Black + Neon Purple cyberpunk aesthetic, dynamic navigation and section management, full post publishing with external verified download links, real-time database search, YouTube embeds, first-class Google AdSense architecture, persistent PostgreSQL database storage, first-party privacy-friendly analytics, and a non-technical Admin Panel.

---

## Key Features

### 1. Visual Identity & Performance
- **Cyberpunk Gaming Aesthetic:** Deep space void backgrounds (`#06030b`), subtle grid lines, glowing neon purple (`#a855f7`, `#c084fc`) highlights, glassmorphism, and 3D card tilt effects.
- **Interactive Cursor Light (Desktop):** Smooth radial glow tracking cursor movements using hardware-accelerated interpolation (`requestAnimationFrame`), interacting dynamically with surrounding cards.
- **Mobile-First & Touch Optimized:** Cursor lights are automatically disabled on touch devices (`@media (pointer: coarse)`). Fully responsive layout tested from 360px up to 1920px displays with an animated mobile drawer.
- **Accessibility:** Fully respects `prefers-reduced-motion` accessibility settings.

### 2. Persistent PostgreSQL Database
- **Persistent Database Storage:** All database records created in the Admin Panel (posts, sections, tags, YouTube embeds, media records, settings, and analytics) are stored in PostgreSQL and survive Render restarts, redeploys, and sleep cycles.
- **Auto-Initialization:** The application automatically provisions all PostgreSQL tables, indexes, and default seed configurations on startup if they do not exist.
- **Fail-Fast Production Design:** In production, a valid `DATABASE_URL` is required. The application does not silently fall back to local or temporary databases.
- **Important Note on File Storage:** The PostgreSQL database persists all media records and external URLs. Uploaded binary files stored in `app/static/uploads/` reside on the server's local filesystem (which is ephemeral on Render Free tier unless external persistent object storage such as AWS S3 or Cloudinary is configured, or external image URLs are used).

### 3. Dynamic Sections & Navigation
- **100% Non-Technical Operation:** When a new update or patch arrives (e.g., `OB53 UPDATE`), the admin creates it directly from the Admin Panel (`Admin → Dynamic Sections → Add Section`).
- **Instant Live Navigation:** Navigation bars and homepage category rails dynamically update without touching any source code.
- **Full Control:** Customize section names, slugs, emojis/icons, descriptions, display order, and header navigation visibility.

### 4. Post Publishing & Verified Download System
- **Rich Content Management:** Create and edit guides with markdown formatting, headers, lists, quotes, and code blocks.
- **Safe External Download Links:** The site does not host large files directly. Admins link to verified external mirrors (Google Drive, MediaFire, Mega). Download URLs are strictly validated to allow only `http://` and `https://` schemes.
- **Visually Distinct Download Button:** Styled as an unmistakable glowing cyber button with clear labels, safe `rel="noopener noreferrer"`, opening in a new tab.
- **No Deceptive Ads:** Advertisements are strictly separated from download buttons with clear `SPONSORED` labels to ensure AdSense policy compliance.

### 5. YouTube & Social Media Integration
- Seamless embedding for YouTube videos (watch URLs, shorts, youtu.be, embed URLs, or raw 11-character video IDs).
- Featured video highlight on the homepage hero section.
- Persistent admin controls for all official social channels: YouTube, Instagram, WhatsApp, Telegram, Discord, and Facebook.

### 6. Google AdSense & Monetization Architecture
- **Built-in First-Class Architecture:** Toggle ads on/off globally or per-slot via the Admin Panel.
- **Safe Containers:** Dedicated ad slots for Homepage Top/Bottom, Post Top/Bottom, and Sidebar.
- **Live `/ads.txt` Endpoint:** Configurable directly through the Admin Panel and served live at `/ads.txt`.
- **Zero Fake IDs:** No hardcoded mock publisher IDs; ready for your real `ca-pub-` credentials upon approval.

### 7. Search, Tags & SEO
- **Real Database Full-Text Search:** Instant server-side search querying post titles, content, summaries, section names, and tags using PostgreSQL ILIKE matching.
- **Multi-Tag System:** Assign multiple tags per post for granular browsing at `/tag/<slug>`.
- **Comprehensive SEO:** Semantic HTML5, canonical URLs, Open Graph metadata, Twitter Cards, auto-generated `/sitemap.xml`, and configurable `/robots.txt`.

### 8. Security & Administration
- **Cryptographic Security:** Salted password hashing using `PBKDF2-HMAC-SHA256` with 100,000 iterations and constant-time digest verification.
- **Session & CSRF Protection:** Cryptographically secure session tokens, HTTP-only cookies, and CSRF validation on all mutating POST requests.
- **Brute-Force Rate Limiting:** Automatic temporary lockout of IP addresses after 5 consecutive failed login attempts within 15 minutes.
- **Safe Media Uploads:** Multi-layer validation ensuring file size limits (5MB), allowed extensions (`png`, `jpg`, `jpeg`, `webp`, `gif`, `svg`), MIME types, and binary image inspection.

---

## Tech Stack & Version Pinning

- **Runtime:** Python 3.11.10 (configured via `.python-version` and `runtime.txt`)
- **Backend Framework:** FastAPI `0.115.0` with Starlette `0.38.6`
- **ASGI Server:** Uvicorn `0.30.6`
- **Templating:** Jinja2 `3.1.6` with native modern `Jinja2Templates` signature (`request=request, name=..., context=...`)
- **Database Driver:** `psycopg2-binary==2.9.9` with PostgreSQL connection pooling (`ThreadedConnectionPool`)
- **Security:** Standard Python `hashlib` (PBKDF2-HMAC-SHA256), `secrets`, `cryptography`
- **Frontend:** Vanilla CSS3 (Custom 3D Cyberpunk Design System) & Vanilla JavaScript

---

## Project Structure

```
gaming_channel_website/
├── app/
│   ├── config.py                 # Application configuration & PostgreSQL URL parsing
│   ├── database.py               # PostgreSQL connection pool & table schemas
│   ├── templating.py             # Native modern Starlette Jinja2Templates instance
│   ├── models/                   # Data models
│   ├── routers/
│   │   ├── admin.py              # Admin authentication and dashboard routes
│   │   └── public.py             # Public routes (Home, Posts, Sections, Tags, Search, Feeds)
│   ├── services/
│   │   ├── ads.py                # AdSense configuration and ads.txt service
│   │   ├── analytics.py          # First-party analytics and dashboard metrics
│   │   ├── auth.py               # Password hashing, sessions, CSRF, rate-limiting & env bootstrap
│   │   ├── formatter.py          # Safe content formatting & XSS sanitization
│   │   ├── media.py              # Upload verification and file storage
│   │   ├── posts.py              # Post CRUD, downloads, and search logic
│   │   ├── sections.py           # Dynamic category/section management
│   │   ├── settings.py           # Site configuration and social media settings
│   │   ├── tags.py               # Tag management and relationship mapping
│   │   └── youtube.py            # YouTube video ID parser and embedding
│   ├── static/
│   │   ├── css/
│   │   │   ├── admin.css         # Admin dashboard styles
│   │   │   └── style.css         # Master cyberpunk public styles
│   │   ├── js/
│   │   │   ├── admin.js          # Admin clipboard, slug, and editor helpers
│   │   │   └── main.js           # Cursor glow, mobile drawer, analytics tracking
│   │   ├── images/             # Default logo and favicon SVGs
│   │   └── uploads/            # Uploaded media assets (.gitkeep)
│   └── templates/
│       ├── admin/                # Admin dashboard, forms, and manager views
│       ├── errors/               # Custom 404 and 500 cyberpunk error pages
│       └── public/               # Public base layout, home, post, section, tag, search
├── data/                         # Local data directory (.gitkeep)
├── scripts/
│   └── create_admin.py           # Secure admin user bootstrap CLI for local development
├── tests/
│   └── test_all.py               # Comprehensive automated test suite
├── .env.example                  # Example environment variables template
├── .gitignore                    # Git safety rules (prevents .env and db leakage)
├── .python-version               # Render Python version declaration (3.11.10)
├── Procfile                      # Render process declaration
├── README.md                     # Complete documentation
├── requirements.txt              # Pinned Python dependencies
└── runtime.txt                   # Python runtime declaration (python-3.11.10)
```

---

## Render Deployment with PostgreSQL (Step-by-Step)

### 1. Create a Free PostgreSQL Database on Render
1. Log into your Render Dashboard.
2. Click **New + → PostgreSQL**.
3. Name it (e.g. `gaming-channel-db`).
4. Select the **Free** instance type.
5. Click **Create Database**.
6. Once provisioned, copy the **Internal Database URL** (or External Database URL if connecting from outside Render).

### 2. Create the Web Service on Render
1. Click **New + → Web Service**.
2. Connect your GitHub repository.
3. Configure:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`

### 3. Set Environment Variables
In the **Environment** tab of your Web Service, configure:

| Variable | Required | Value / Example |
| :--- | :--- | :--- |
| `DATABASE_URL` | **Yes** | Paste the PostgreSQL connection string from step 1 |
| `PYTHON_VERSION` | **Yes** | `3.11.10` (enforces Python 3.11 on Render) |
| `SECRET_KEY` | **Yes** | A random cryptographic key (e.g. generated via `openssl rand -hex 32`) |
| `APP_URL` | **Yes** | Your deployed service URL (e.g. `https://your-app.onrender.com`) |
| `ENVIRONMENT` | **Yes** | `production` |
| `ADMIN_USERNAME` | **Initial boot** | Desired admin username (e.g. `admin`) |
| `ADMIN_PASSWORD` | **Initial boot** | Strong admin password |

### 4. Deploy and Automatic Initialization
- Click **Deploy Web Service**.
- Render will install dependencies (including `psycopg2-binary`).
- On initial startup, the application connects to PostgreSQL, automatically creates all tables and default configurations, and provisions your admin account.
- All posts, videos, dynamic sections, and settings created in the Admin Panel are stored in PostgreSQL and persist permanently across redeploys, restarts, and sleep cycles.

---

## Google AdSense & ads.txt Setup

1. **Initial State:**
   - AdSense is **disabled** by default for development safety.
   - `/ads.txt` is served live at `https://your-domain.com/ads.txt` with clear placeholder instructions. No fake publisher IDs are hardcoded.

2. **After Google AdSense Approval:**
   - Once approved by Google:
     1. Go to `Admin Panel → AdSense & Ads`.
     2. Check **Enable Google AdSense Globally**.
     3. Enter your Publisher ID (`ca-pub-XXXXXXXXXXXXXXXX`).
     4. Paste your authorized digital seller entry into `/ads.txt`:
        ```
        google.com, pub-XXXXXXXXXXXXXXXX, DIRECT, f08c47fec0942fa0
        ```
     5. Save settings.

---

## Running Automated Tests

```bash
python -m unittest tests/test_all.py -v
```
