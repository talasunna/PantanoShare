# Community Errand Sharing — MVP

A tiny Flask web app that lets a small community:
- Post trips to villages/stores
- Request items from specific stores
- Claim & fulfill requests when doing a trip
- Record deliveries
- Automatically track balances (who owes whom) based on delivered items
- Record payments to settle balances

## Quickstart

### 1) Create & activate a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate       # on Windows: .venv\Scripts\activate
```

### 2) Install dependencies
```bash
pip install -r requirements.txt
```

### 3) Initialize the database and seed sample data (4 houses + some villages/stores)
```bash
python app.py --initdb
```
This prints join codes for the 4 houses and writes them to `house_codes.txt`. Share each house's code with the people living there.

### 4) Run the dev server
```bash
flask --app app.py run --debug
```
Open http://127.0.0.1:5000 in your browser.

### 5) Sign up
Click “Sign up / Sign in”, pick your house, enter the join code, and choose a display name.

### 6) Use the app
- **Requests** → “New request” to ask for an item from a store
- **Trips** → “New trip” if you’re going to a village/store soon
- On a trip’s page you can **claim** matching open requests
- After the trip, go to “Deliver” on your trip to record actual prices & deliveries
- **Balances** → see who owes whom; record payments to settle up

## Notes & Limits
- This is an MVP for ~4 houses. It uses SQLite (`app.db`) and a very simple session-based sign-in (house join codes).
- No emails or passwords; **do not put this on the public internet** without adding real authentication.
- Extend later with: push notifications, real user accounts, item photos, fees, receipts, etc.


## Admin (manage houses, join codes, villages, stores)

1) Set an admin PIN (optional but recommended):
```bash
export ADMIN_PIN=your-secret-6-digits   # macOS/Linux
# PowerShell on Windows:
# $Env:ADMIN_PIN = "your-secret-6-digits"
```

2) Start the app and open **/admin** (e.g., http://127.0.0.1:5000/admin).  
Log in with the PIN. From there you can:
- Add/rename/delete **Houses** (delete blocked if in use)
- **Regenerate join codes** per house or **all at once**
- Add/rename/delete **Villages** (delete blocked if in use)
- Add/rename/move/delete **Stores** (delete blocked if in use)

> If you forget to set `ADMIN_PIN`, the default is `1234` (MVP convenience).

---

## Hosting it online (simple options)

### Option A: Render (free starter)

1) Push this folder to a new Git repo (GitHub).
2) On render.com → "New Web Service"
3) Connect repo, set:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn -w 2 -b 0.0.0.0:10000 app:app`
   - **Environment**:
     - `PORT=10000`
     - `ADMIN_PIN=your-secret`
   - **Instance Type**: Free
4) Add a **Persistent Disk** if you want SQLite to persist across deploys
   (mount to `/data` and change `DB_PATH` in `app.py` accordingly, e.g., `/data/app.db`).

### Option B: Railway

1) Create a new Railway project → Deploy GitHub repo.
2) Add variables: `ADMIN_PIN=your-secret`.
3) Set Start Command: `gunicorn -w 2 -b 0.0.0.0:$PORT app:app`.

### Option C: Docker + any VPS

Create `Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn
COPY . .
ENV ADMIN_PIN=change-me
ENV PORT=8000
EXPOSE 8000
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "app:app"]
```

Build & run:
```bash
docker build -t errandshare .
docker run -d -p 8000:8000 -e ADMIN_PIN=your-secret -v $PWD/data:/data errandshare
```

> For SQLite persistence in Docker, change `DB_PATH` to `/data/app.db` in `app.py` and mount a volume.

### Option D: Quick-and-dirty local sharing

On your Mac:
```bash
export ADMIN_PIN=your-secret
python -m flask --app app.py run --host 0.0.0.0 --port 5000
```
Neighbors on the same Wi‑Fi visit `http://YOUR-MAC-IP:5000`.

---

### Security note
This MVP uses join codes and an admin PIN only. Before exposing publicly, add proper user accounts (email/password or magic links), HTTPS, rate limiting, and CSRF protection.
