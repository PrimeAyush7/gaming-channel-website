# GOD4XE ESPORTS — Production Platform (Website, Admin Console & Android Backend)

Official competitive gaming and esports tournament infrastructure for Free Fire, featuring live dynamic player rankings, automated custom rooms, anti-cheat enforcement, verified diamond ledgers, and dynamic referral leaderboards.

---

## 1. System Architecture

The ecosystem relies on **ONE shared FastAPI backend** deployed on Render and **ONE persistent Supabase PostgreSQL database**:

```
           Android Native App (Kotlin / Compose)
                     ↓  HTTPS REST APIs
             FastAPI Backend (Render)
                     ↓  psycopg2 Connection Pool
             Supabase PostgreSQL (Database)
                     ↑  SSR Templates & Admin Console
              Existing GOD4XE Gaming Website
```

- **Persistent Database:** Supabase PostgreSQL (`DATABASE_URL`).
- **Business Logic & Ranking Engine:** FastAPI backend (`app/services/`).
- **Presentation Clients:**
  - Android App (Jetpack Compose, Retrofit, Kotlin Coroutines).
  - Website & Admin Console (Jinja2 SSR, Vanilla JS, CSS3 Cyberpunk Theme).

---

## 2. Business Rules & Diamond Ledger

### A. Zero Free Registration Diamonds
- **Zero Registration Diamonds:** All new user registrations (Email/Password, Phone OTP, and Google Sign-In) receive **0 free diamonds**.
- No automatic registration bonuses or starter rewards (`STARTER_BONUS` completely removed).
- Diamond accounts are initialized with balance `0` and locked balance `0`.
- The Diamond ledger continues to track deposits, tournament fees, and match winning payouts.

### B. Dynamic Referral & Ranking Engine
- Every registered user has a unique, deterministic referral code (`referral_code`) and shareable link.
- **Successful Referral Criteria:** A referral is counted as `SUCCESSFUL` only after the referred user completes registration.
- **Anti-Abuse Safeguards:**
  - Self-referrals are blocked (`referrer_id != referee_id`).
  - Duplicate referrals are blocked (database unique constraint on `referee_id`).
  - No client-side counts or ranks are accepted; all calculations are executed server-side.
- **Referral Diamonds:** Referrals award **0 diamonds**. Referrals advance the user's **Referral Rank** and **Leaderboard Position**.
- **Dynamic Rank Movement (Up & Down):**
  - Referral ranks are calculated dynamically on every request based on the user's *current valid successful referral count*.
  - When referral count crosses a higher tier &rarr; Rank automatically moves **UP**.
  - When an admin invalidates or reverses a referral &rarr; Count decreases and Rank automatically moves **DOWN** if below threshold.
- **Authoritative Rank Tiers (`referral_ranks` table):**
  1. **ROOKIE:** 0–9 Referrals (Badge: `#94a3b8`)
  2. **PRO:** 10–24 Referrals (Badge: `#38bdf8`)
  3. **ELITE:** 25–49 Referrals (Badge: `#a855f7`)
  4. **MASTER:** 50–99 Referrals (Badge: `#f59e0b`)
  5. **LEGEND:** 100+ Referrals (Badge: `#ef4444`, Max Tier)
- **Live Leaderboard:**
  - Sorted by `successful_referrals DESC, referrer_id ASC`.
  - Logged-in user's exact position (e.g. `#47`) is returned even if outside the top list.
  - Available in Android App (`ui/social/ReferralScreen.kt`) and Website (`/referrals`).

---

## 3. UPI Deposit & Payment Proof Workflow

### A. Admin Panel Configuration (`/admin/deposits` & `/admin/settings`)
- **UPI VPA / ID:** Configurable via Admin settings (`upi_id`).
- **Payee Merchant Name:** Configurable (`upi_payee_name`).
- **UPI QR Code Image:**
  - Admin can upload or replace a QR code image (PNG, JPG, WEBP).
  - Admin can preview the live QR image in the dashboard.
  - Admin can remove the QR code image at any time.

### B. User Android App Deposit Flow (`ui/wallet/DepositScreen.kt`)
1. User opens **Add Diamonds via UPI**.
2. Screen displays the official UPI ID with quick copy button and loads the official QR Code image.
3. User enters:
   - **Amount** (Minimum 50 Diamonds).
   - **UTR Reference Number** (12-digit transaction number).
   - **Payment Screenshot** (**REQUIRED** — user selects image from gallery with preview, replace, and remove controls).
4. On submit:
   - Screenshot is validated for format and size (max 5 MB) and uploaded to `/api/v1/wallet/upload-screenshot`.
   - Deposit request is submitted to `/api/v1/wallet/deposit-request` with `amount`, `utr_reference`, and `payment_proof_url`.
   - Status is set to `PENDING`.

### C. Admin Review & Idempotency
- Admin inspects pending requests on `/admin/deposits` with player details, amount, UTR, and a clickable screenshot thumbnail.
- Clicking **✓ Approve**:
  - Updates status to `APPROVED`.
  - Atomically credits diamonds to player's ledger (`diamond_transactions` entry of type `DEPOSIT`).
  - **Idempotency Guarantee:** Attempting to approve an already-approved request raises an error and never double-credits diamonds.
- Clicking **✕ Reject**:
  - Updates status to `REJECTED` with reason. Zero diamonds credited.

---

## 4. Google OAuth 2.0 Setup Guide

### Android Google Sign-In Setup
The app utilizes Android Credential Manager (`com.google.android.libraries.identity.googleid:googleid`):
1. Go to the [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
2. Create an **OAuth 2.0 Web Client ID** (used by backend for ID token audience validation):
   - Type: *Web application*.
   - Copy the Client ID (e.g., `1234567890-abcdef.apps.googleusercontent.com`).
3. Create an **OAuth 2.0 Android Client ID**:
   - Package name: `com.god4xe.esports`.
   - SHA-1 Fingerprint: Run `keytool -list -v -keystore ~/.android/debug.keystore` (or production keystore).
4. Configure the Web Client ID in the project:
   - **In Android:** In `god4xe_android/gradle.properties`:
     ```properties
     GOD4XE_GOOGLE_CLIENT_ID=1234567890-abcdef.apps.googleusercontent.com
     ```
     Or build with `-PGOD4XE_GOOGLE_CLIENT_ID="YOUR_ID"`.
   - **In Backend (Render):** Set environment variable `GOOGLE_CLIENT_ID="YOUR_ID"` or configure in Admin Settings.
5. If the client ID is not configured, the Android app gracefully notifies the user without crashing, and falls back to query `/api/v1/auth/config`.

---

## 5. Database Migrations

All migrations are located in `migrations/` and run sequentially and idempotently:

1. `001_baseline_website_schema.sql`: Articles, categories, tags, media, settings.
2. `002_extend_admin_roles_and_audit.sql`: Admin roles (Super, Tournament, Finance, Support) & `admin_audit_logs`.
3. `003_add_app_users_and_profiles.sql`: `app_users`, `user_profiles`, JWT sessions.
4. `004_add_tournaments_and_matches.sql`: `tournaments`, `tournament_participants`, `matches`.
5. `005_add_diamond_ledger.sql`: `diamond_accounts`, `diamond_transactions`, `deposit_requests`.
6. `006_add_social_redeem_support_notifications.sql`: `redeem_codes`, `referrals`, `notifications`, `support_tickets`.
7. `007_starter_diamonds_bonus.sql`: Transaction idempotency constraints.
8. `008_homepage_hero_headline_setting.sql`: Admin-configurable homepage hero headline.
9. `009_dynamic_referrals_and_payment_proof.sql`: `referral_ranks` table, referral audit columns, UPI QR settings.

---

## 6. Running Tests

Execute the automated backend test suite:
```bash
python3 -m unittest tests/test_all.py
```
All 45 tests validate zero registration diamonds, referral rank progression and demotion, live leaderboards, deposit screenshot enforcement, and admin audit trails.
