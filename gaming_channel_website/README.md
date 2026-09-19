# NEXUS GAMING — Official Content & Downloads Portal

A high-performance, full-stack gaming website designed specifically for gaming YouTube channels. Built from the ground up with an immersive Dark Purple + Void Black + Neon Purple cyberpunk aesthetic, dynamic navigation and section management, full post publishing with external verified download links, real-time database search, YouTube embeds, first-class Google AdSense architecture, first-party privacy-friendly analytics, and a non-technical Admin Panel.

---

## Key Features

### 1. Visual Identity & Performance
- **Cyberpunk Gaming Aesthetic:** Deep space void backgrounds (`#06030b`), subtle grid lines, glowing neon purple (`#a855f7`, `#c084fc`) highlights, glassmorphism, and 3D card tilt effects.
- **Interactive Cursor Light (Desktop):** Smooth radial glow tracking cursor movements using hardware-accelerated interpolation (`requestAnimationFrame`), interacting dynamically with surrounding cards.
- **Mobile-First & Touch Optimized:** Cursor lights are automatically disabled on touch devices (`@media (pointer: coarse)`). Fully responsive layout tested from 360px up to 1920px displays with an animated mobile drawer.
- **Accessibility:** Fully respects `prefers-reduced-motion` accessibility settings.

### 2. Dynamic Sections & Categories
- **100% Non-Technical Operation:** When a new update or patch arrives (e.g., `OB53 UPDATE`), the admin creates it directly from the Admin Panel (`Admin → Dynamic Sections → Add Section`).
- **Instant Live Navigation:** Navigation bars and homepage category rails dynamically update without touching any source code.
- **Full Control:** Customize section names, slugs, emojis/icons, descriptions, display order, and header navigation visibility.

### 3. Post Publishing & Verified Download System
- **Rich Content Management:** Create and edit guides with markdown formatting, headers, lists, quotes, and code blocks.
- **Safe External Download Links:** The site does not host large files directly. Admins link to verified external mirrors (Google Drive, MediaFire, Mega). Download URLs are strictly validated to allow only `http://` and `https://` schemes.
- **Visually Distinct Download Button:** Styled as an unmistakable glowing cyber button with clear labels, safe `rel="noopener noreferrer"`, opening in a new tab.
- **No Deceptive Ads:** Advertisements are strictly separated from download buttons with clear `SPONSORED` labels to ensure AdSense policy compliance.

### 4. YouTube Integration
- Seamless embedding for YouTube videos (watch URLs, shorts, youtu.be, embed URLs, or raw 11-character video IDs).
- Featured video highlight on the homepage hero section.
- Direct quick-link button to your official YouTube channel.

### 5. Google AdSense & Monetization Architecture
- **Built-in First-Class Architecture:** Toggle ads on/off globally or per-slot via the Admin Panel.
- **Safe Containers:** Dedicated ad slots for Homepage Top/Bottom, Post Top/Bottom, and Sidebar.
- **Live `/ads.txt` Endpoint:** Configurable directly through the Admin Panel and served live at `/ads.txt`.
- **Zero Fake IDs:** No hardcoded mock publisher IDs; ready for your real `ca-pub-` credentials upon approval.

### 6. Search, Tags & SEO
- **Real Database Full-Text Search:** Instant server-side search querying post titles, content, summaries, section names, and tags.
- **Multi-Tag System:** Assign multiple tags per post for granular browsing at `/tag/<slug>`.
- **Comprehensive SEO:** Semantic HTML5, canonical URLs, Open Graph metadata, Twitter Cards, auto-generated `/sitemap.xml`, and configurable `/robots.txt`.

### 7. Security & Administration
- **Cryptographic Security:** Salted password hashing using `PBKDF2-HMAC-SHA256` with 100,000 iterations and constant-time digest verification.
- **Session & CSRF Protection:** Cryptographically secure session tokens, HTTP-only cookies, and CSRF validation on all mutating POST requests.
- **Brute-Force Rate Limiting:** Automatic temporary lockout of IP addresses after 5 consecutive failed login attempts within 15 minutes.
- **Safe Media Uploads:** Multi-layer validation ensuring file size limits (5MB), allowed extensions (`png`, `jpg`, `jpeg`, `webp`, `gif`, `svg`), MIME types, and binary image inspection.

---

## Tech Stack

- **Backend Framework:** Python 3.11, FastAPI, Uvicorn, Starlette
- **Templating:** Jinja2 with semantic HTML5
- **Database:** Native SQLite (via Python standard library `sqlite3`). Fast, zero-configuration, robust, and self-contained in `data/site.db`.
- **Security:** Standard Python `hashlib` (PBKDF2-HMAC-SHA256), `secrets`, `cryptography`
- **Frontend:** Vanilla CSS3 (Custom 3D Cyberpunk Design System) & Vanilla JavaScript (No heavy third-party bloat)

---

## Project Structure

```
gaming_channel_website/
├── app/
│   ├── models/
│   ├── routers/
│   │   ├── admin.py            # Admin authentication and dashboard routes
│   │   └── public.py           # Public routes (Home, Posts, Sections, Tags, Search, Feeds)
│   ├── services/
│   │   ├── ads.py              # AdSense configuration and ads.txt service
│   │   ├── analytics.py        # First-party analytics and dashboard metrics
│   │   ├── auth.py             # Password hashing, sessions, CSRF, rate-limiting & env bootstrap
│   │   ├── formatter.py        # Safe content formatting & XSS sanitization
│   │   ├── media.py            # Upload verification and file storage
│   │   ├── posts.py            # Post CRUD, downloads, and search logic
│   │   ├── sections.py         # Dynamic category/section management
│   │   ├── settings.py         # Site configuration and SEO settings
│   │   ├── tags.py             # Tag management and relationship mapping
│   │   └── youtube.py          # YouTube video ID parser and embedding
│   ├── static/
│   │   ├── css/
│   │   │   ├── admin.css       # Admin dashboard styles
│   │   │   └── style.css       # Master cyberpunk public styles
│   │   ├── js/
│   │   │   ├── admin.js        # Admin clipboard, slug, and editor helpers
│   │   │   └── main.js         # Cursor glow, mobile drawer, analytics tracking
│   │   ├── images/             # Default logo and favicon SVGs
│   │   └── uploads/            # Uploaded media assets (.gitkeep)
│   ├── templates/
│   │   ├── admin/              # Admin dashboard, forms, and manager views
│   │   ├── errors/             # Custom 404 and 500 cyberpunk error pages
│   │   └── public/             # Public base layout, home, post, section, tag, search
│   ├── config.py               # Environment configuration and paths (SQLite)
│   └── database.py             # Database connection, schemas, and migrations
├── data/                       # Local SQLite database directory (.gitkeep)
├── scripts/
│   └── create_admin.py         # Secure admin user bootstrap CLI for local development
├── tests/
│   └── test_all.py             # Comprehensive automated test suite
├── .env.example                # Example environment variables template
├── .gitignore                  # Git safety rules (prevents .env and db leakage)
├── Procfile                    # Render process declaration
├── README.md                   # Complete documentation
├── requirements.txt            # Python dependencies
└── runtime.txt                 # Python runtime version
```

---

## Local Installation & Setup

### 1. Prerequisites
- Python 3.10+ (Python 3.11 recommended)
- `pip` package manager

### 2. Clone and Setup Environment
```bash
git clone <repository_url>
cd gaming_channel_website

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` to set your desired `SECRET_KEY` and `APP_URL`.

### 4. Create the First Admin User (Local CLI)
Run the secure CLI bootstrap tool:
```bash
python scripts/create_admin.py --username admin --password "YourStrongPasswordHere"
```
Or run interactively:
```bash
python scripts/create_admin.py
```

### 5. Start the Application
```bash
python main.py
```
Or using Uvicorn directly:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Visit:
- Public Website: `http://localhost:8000`
- Admin Panel: `http://localhost:8000/admin`

---

## Render Free Deployment (No Shell Required)

On Render's Free tier, interactive Shell access is often not available. To make initial deployment seamless and secure, the application includes automatic initial admin provisioning via environment variables on first boot.

### Step-by-Step Deployment on Render Free:

1. **Push your code to GitHub:**
   Ensure `.env` is NOT committed (it is excluded by `.gitignore`).

2. **Create New Web Service on Render:**
   - Connect your GitHub repository.
   - **Name:** e.g. `my-gaming-portal`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`

3. **Configure Environment Variables in Render Dashboard:**
   In your service settings under the **Environment** tab, add the following variables:
   - `SECRET_KEY`: A secure random string (e.g. generated via `openssl rand -hex 32`).
   - `APP_URL`: Your live Render URL (e.g. `https://my-gaming-portal.onrender.com`).
   - `ENVIRONMENT`: `production`
   - `ADMIN_USERNAME`: Your desired initial administrator username (e.g. `admin`).
   - `ADMIN_PASSWORD`: Your chosen strong password for the admin account.

4. **Automatic Initial Provisioning:**
   - When the web service boots for the first time, it detects if no administrator account exists in the database.
   - It hashes `ADMIN_PASSWORD` using PBKDF2-HMAC-SHA256 with a unique random cryptographic salt and creates the initial admin.
   - **Security Guarantees:**
     - The password is NEVER printed or logged to stdout/stderr.
     - Once an admin exists, this process will **NEVER overwrite** or reset existing administrator accounts.
   - After you log in to `/admin/login`, you can safely remove `ADMIN_USERNAME` and `ADMIN_PASSWORD` from your Render Environment Variables dashboard.

---

## Google AdSense & ads.txt Setup

1. **Initial State:**
   - The application ships with AdSense **disabled** by default so your website remains compliant with Google Webmaster policies during development.
   - `/ads.txt` is served live at `https://your-domain.com/ads.txt`. By default, it contains a clear setup placeholder instruction. No fake publisher IDs are hardcoded.

2. **After Google AdSense Approval:**
   - Once Google reviews and approves your website for AdSense:
     1. Log in to your Admin Panel (`/admin`).
     2. Navigate to **AdSense & Ads**.
     3. Check **Enable Google AdSense Globally**.
     4. Paste your official Publisher / Client ID (format: `ca-pub-XXXXXXXXXXXXXXXX`).
     5. Under `/ads.txt` Content, add your authorized digital seller entry:
        ```
        google.com, pub-XXXXXXXXXXXXXXXX, DIRECT, f08c47fec0942fa0
        ```
     6. Enter the corresponding Ad Slot IDs for the homepage, article top/bottom, and sidebar slots.
     7. Click **Save Monetization Settings**.
   - Your live `/ads.txt` will immediately reflect your verified publisher record, and ad units will render in safe, clearly marked containers.

---

## Running Automated Tests

Run the full automated test suite to verify security, CSRF, admin bootstrap, downloads, uploads, search, and endpoints:
```bash
python -m unittest tests/test_all.py -v
```
