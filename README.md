# ✈ Flight Price Tracker

Tracks the daily evolution of flight prices and exports a dashboard Excel file.

---

## Project Structure

```
flight-tracker/
├── config.json        ← your flights + SerpAPI key
├── tracker.py         ← fetches prices and saves to SQLite
├── export.py          ← generates Excel dashboard from SQLite data
├── db.py              ← database helpers (don't edit)
├── requirements.txt
├── flights.db         ← auto-created on first run
└── flight_prices.xlsx ← auto-generated dashboard
```

---

## Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Add your SerpAPI key

Open `config.json` and replace `YOUR_SERPAPI_KEY_HERE` with your key from https://serpapi.com/dashboard

### 3. Test the tracker manually

```bash
python tracker.py
python export.py
```

Open `flight_prices.xlsx` to see your dashboard.

---

## Adding New Flights

Edit `config.json` and add a new entry to the `"flights"` array:

```json
{
  "id": "TLS_BCN_JUL",
  "label": "Toulouse → Barcelona (15–20 Jul)",
  "origin": "TLS",
  "destination": "BCN",
  "outbound_date": "2026-07-15",
  "return_date": "2026-07-20",
  "trip_type": "round_trip"
}
```

That's it. The tracker and dashboard will pick it up automatically on the next run.

---

## Scheduling on Windows (Task Scheduler)

To run `tracker.py` automatically every day at 09:00:

### Step-by-step

1. Open **Task Scheduler** (search for it in the Start menu)
2. Click **Create Basic Task** in the right panel
3. **Name**: `Flight Price Tracker`
4. **Trigger**: Daily → set start time to **09:00**
5. **Action**: Start a program
   - Program/script: `python`  
     *(or the full path to python.exe, e.g. `C:\Python311\python.exe`)*
   - Add arguments: `tracker.py`
   - Start in: `C:\path\to\your\flight-tracker`  
     *(replace with the actual folder path where you put these files)*
6. Click **Finish**

### Test it

Right-click your new task → **Run** — check the console output or look at `flights.db` to confirm a row was inserted.

### Optional: also schedule export.py

Repeat the steps above with:
- **Name**: `Flight Price Dashboard Export`
- Trigger: Daily at **09:05** (5 min after tracker)
- **Add arguments**: `export.py`

This keeps your Excel dashboard refreshed every morning automatically.

---

## SerpAPI Free Tier

- 100 searches/month free
- 2 flights × 1 fetch/day = ~62 calls/month → safely within free tier
- Monitor usage at https://serpapi.com/dashboard
- Each new flight you add costs ~31 calls/month

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ERROR: Please set your SerpAPI key` | Edit `config.json` and paste your key |
| `No flights found in response` | Check origin/destination IATA codes are correct |
| Excel file not updating | Run `python export.py` manually |
| Task Scheduler not running | Check the "Start in" path is set correctly |
