import json
import sqlite3
from datetime import datetime
from db import init_db, get_combinations_for_flight, get_prices_for_combination

CONFIG_PATH  = "config.json"
OUTPUT_PATH  = "index.html"
DB_PATH      = "flights.db"


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def build_chart_data(config):
    """
    Returns a dict ready to be serialised into JS:
    {
      flights: [
        {
          id, label, outbound_date, return_date, outbound_after,
          combinations: [
            {
              id, outbound_time, outbound_airline, return_airline,
              dates: [...], prices: [...],
              current, min, max, avg, trend
            }
          ]
        }
      ],
      generated_at: "..."
    }
    """
    flights_out = []

    for fcfg in config["flights"]:
        fid   = fcfg["id"]
        combos = get_combinations_for_flight(fid)
        combos_out = []

        for combo_id in sorted(c for c in combos if c is not None):
            rows = get_prices_for_combination(fid, combo_id)
            if not rows:
                continue

            dates   = [r[0][:10] for r in rows]
            prices  = [r[1]      for r in rows if r[1] is not None]
            out_time    = rows[-1][3] or "?"
            out_airline = rows[-1][4] or "?"
            ret_airline = rows[-1][6] or "?"

            if not prices:
                continue

            trend = None
            if len(prices) >= 2:
                trend = round(prices[-1] - prices[-2], 2)

            combos_out.append({
                "id":              combo_id,
                "outbound_time":   out_time,
                "outbound_airline":out_airline,
                "return_airline":  ret_airline,
                "dates":           dates,
                "prices":          [round(p, 2) for p in prices],
                "current":         round(prices[-1], 2),
                "min":             round(min(prices), 2),
                "max":             round(max(prices), 2),
                "avg":             round(sum(prices) / len(prices), 2),
                "trend":           trend,
            })

        # Sort combinations by current price ascending
        combos_out.sort(key=lambda x: x["current"])

        flights_out.append({
            "id":             fid,
            "label":          fcfg["label"],
            "outbound_date":  fcfg["outbound_date"],
            "return_date":    fcfg["return_date"],
            "outbound_after": fcfg.get("outbound_after", "any"),
            "combinations":   combos_out,
        })

    return {
        "flights":      flights_out,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Flight Price Tracker</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg:       #f5f5f3;
    --surface:  #ffffff;
    --border:   #e0ddd8;
    --text:     #1a1a18;
    --muted:    #6b6b66;
    --blue:     #2E75B6;
    --blue-lt:  #d6e4f0;
    --green:    #2d8a4e;
    --green-lt: #e2f0e8;
    --red:      #c0392b;
    --red-lt:   #fdecea;
    --amber:    #b06c0a;
    --amber-lt: #fef3e0;
    --radius:   10px;
    --shadow:   0 1px 4px rgba(0,0,0,0.08);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg:      #1a1a18;
      --surface: #242422;
      --border:  #383836;
      --text:    #e8e6e0;
      --muted:   #9a9890;
      --blue:    #5b9fd4;
      --blue-lt: #1f3147;
      --green:   #4caf72;
      --green-lt:#1a2e22;
      --red:     #e57373;
      --red-lt:  #2e1a1a;
      --amber:   #f0a830;
      --amber-lt:#2e2010;
    }
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--text); font-size: 15px; line-height: 1.5; }
  header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 18px 28px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
  header h1 { font-size: 20px; font-weight: 600; color: var(--blue); letter-spacing: -0.3px; }
  header .meta { font-size: 12px; color: var(--muted); }
  .tabs { display: flex; gap: 2px; padding: 20px 28px 0; overflow-x: auto; }
  .tab { padding: 8px 18px; border-radius: var(--radius) var(--radius) 0 0; background: var(--surface); border: 1px solid var(--border); border-bottom: none; cursor: pointer; font-size: 13px; color: var(--muted); transition: all .15s; white-space: nowrap; }
  .tab:hover { color: var(--text); }
  .tab.active { background: var(--blue); color: #fff; border-color: var(--blue); }
  .panel { display: none; padding: 0 28px 40px; }
  .panel.active { display: block; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow); padding: 20px 24px; margin-top: 20px; }
  .card h2 { font-size: 16px; font-weight: 600; margin-bottom: 4px; }
  .card .subtitle { font-size: 12px; color: var(--muted); margin-bottom: 16px; }
  .summary-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }
  .stat { background: var(--bg); border-radius: var(--radius); padding: 14px 16px; }
  .stat .label { font-size: 11px; text-transform: uppercase; letter-spacing: .6px; color: var(--muted); margin-bottom: 4px; }
  .stat .value { font-size: 22px; font-weight: 700; }
  .stat.best .value { color: var(--green); }
  .stat.worst .value { color: var(--red); }
  .stat.avg .value { color: var(--blue); }
  .chart-wrap { position: relative; height: 260px; margin-bottom: 20px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  thead th { text-align: left; padding: 8px 10px; border-bottom: 2px solid var(--border); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: .4px; color: var(--muted); }
  tbody tr { border-bottom: 1px solid var(--border); transition: background .1s; }
  tbody tr:last-child { border-bottom: none; }
  tbody tr:hover { background: var(--bg); }
  tbody td { padding: 10px 10px; vertical-align: middle; }
  .combo-tag { display: inline-block; background: var(--blue-lt); color: var(--blue); padding: 2px 8px; border-radius: 20px; font-size: 11px; font-weight: 600; white-space: nowrap; }
  .pill { display: inline-block; padding: 2px 8px; border-radius: 20px; font-size: 12px; font-weight: 600; }
  .pill.up   { background: var(--red-lt);   color: var(--red);   }
  .pill.down { background: var(--green-lt); color: var(--green); }
  .pill.flat { background: var(--blue-lt);  color: var(--blue);  }
  .price-col { font-weight: 700; font-size: 15px; }
  .overview-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; margin-top: 20px; }
  .overview-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px 20px; box-shadow: var(--shadow); }
  .overview-card h3 { font-size: 14px; font-weight: 600; margin-bottom: 8px; line-height: 1.3; }
  .overview-card .route { font-size: 12px; color: var(--muted); margin-bottom: 12px; }
  .overview-card .best-price { font-size: 28px; font-weight: 800; color: var(--green); }
  .overview-card .best-label { font-size: 11px; color: var(--muted); margin-bottom: 8px; }
  .overview-card .combos-count { font-size: 12px; color: var(--muted); }
  .section-title { font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: .6px; color: var(--muted); margin: 24px 0 10px; }
  .combo-section { margin-top: 28px; border-top: 1px solid var(--border); padding-top: 20px; }
  .combo-section:first-of-type { border-top: none; margin-top: 0; }
  .combo-header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
  .combo-header .combo-tag { font-size: 13px; padding: 4px 12px; }
  .combo-meta { font-size: 12px; color: var(--muted); }
  @media (max-width: 600px) {
    header, .tabs, .panel { padding-left: 14px; padding-right: 14px; }
    .card { padding: 14px 14px; }
    .summary-grid { grid-template-columns: 1fr 1fr; }
  }
</style>
</head>
<body>
<header>
  <h1>&#9992;&#65039; Flight Price Tracker</h1>
  <span class="meta">Updated: __GENERATED_AT__</span>
</header>

<div class="tabs" id="tabs">
  <div class="tab active" onclick="showTab(0)">Overview</div>
  __FLIGHT_TABS__
</div>

__PANELS__

<script>
const DATA = __DATA_JSON__;

function showTab(i) {
  document.querySelectorAll('.tab').forEach((t,j) => t.classList.toggle('active', i===j));
  document.querySelectorAll('.panel').forEach((p,j) => p.classList.toggle('active', i===j));
}

function trendPill(trend) {
  if (trend === null || trend === undefined) return '<span class="pill flat">-</span>';
  const sign = trend > 0 ? '+' : '';
  const cls  = trend > 0 ? 'up' : trend < 0 ? 'down' : 'flat';
  return `<span class="pill ${cls}">${sign}&#8364;${Math.abs(trend).toFixed(2)}</span>`;
}

const COLORS = [
  '#2E75B6','#1D9E75','#D85A30','#7F77DD','#BA7517',
  '#993556','#639922','#D4537E','#378ADD','#0F6E56'
];

function buildOverviewPanel() {
  const cards = DATA.flights.map(f => {
    const allPrices = f.combinations.flatMap(c => c.prices);
    const cheapest  = allPrices.length ? Math.min(...allPrices) : null;
    const bestCombo = f.combinations.find(c => c.current === Math.min(...f.combinations.map(x => x.current)));
    return `
      <div class="overview-card">
        <h3>${f.label}</h3>
        <div class="route">${f.outbound_date} &rarr; ${f.return_date} &nbsp;|&nbsp; depart after ${f.outbound_after}</div>
        <div class="best-price">${cheapest !== null ? '&#8364;' + cheapest.toFixed(2) : 'N/A'}</div>
        <div class="best-label">cheapest seen${bestCombo ? ' &mdash; ' + bestCombo.outbound_time + ' ' + bestCombo.outbound_airline : ''}</div>
        <div class="combos-count">${f.combinations.length} combination(s) tracked</div>
      </div>`;
  }).join('');
  return `<div class="panel active" id="panel-0">
    <div class="overview-grid">${cards}</div>
    <div class="section-title">All combinations today</div>
    <div class="card" style="padding:0;overflow:hidden">
      <table>
        <thead><tr>
          <th>Flight</th><th>Combination</th><th>Out time</th>
          <th>Out airline</th><th>Ret airline</th>
          <th>Current</th><th>Min</th><th>Max</th><th>Avg</th><th>Trend</th>
        </tr></thead>
        <tbody id="overview-body"></tbody>
      </table>
    </div>
  </div>`;
}

function populateOverviewTable() {
  const body = document.getElementById('overview-body');
  if (!body) return;
  const rows = DATA.flights.flatMap(f =>
    f.combinations.map(c => ({ flight: f.label, ...c }))
  ).sort((a,b) => a.current - b.current);

  body.innerHTML = rows.map(r => `
    <tr>
      <td style="max-width:160px;font-size:12px">${r.flight}</td>
      <td><span class="combo-tag">${r.id}</span></td>
      <td>${r.outbound_time}</td>
      <td>${r.outbound_airline}</td>
      <td>${r.return_airline}</td>
      <td class="price-col">&#8364;${r.current.toFixed(2)}</td>
      <td style="color:var(--green)">&#8364;${r.min.toFixed(2)}</td>
      <td style="color:var(--red)">&#8364;${r.max.toFixed(2)}</td>
      <td style="color:var(--muted)">&#8364;${r.avg.toFixed(2)}</td>
      <td>${trendPill(r.trend)}</td>
    </tr>`).join('');
}

function buildFlightPanels() {
  return DATA.flights.map((f, fi) => {
    const comboSections = f.combinations.map((c, ci) => `
      <div class="combo-section">
        <div class="combo-header">
          <span class="combo-tag">${c.id}</span>
          <span class="combo-meta">${c.outbound_time} &nbsp;${c.outbound_airline} &rarr; return ${c.return_airline}</span>
        </div>
        <div class="summary-grid">
          <div class="stat best">
            <div class="label">Best price</div>
            <div class="value">&#8364;${c.min.toFixed(2)}</div>
          </div>
          <div class="stat">
            <div class="label">Current</div>
            <div class="value">&#8364;${c.current.toFixed(2)}</div>
          </div>
          <div class="stat worst">
            <div class="label">Highest seen</div>
            <div class="value">&#8364;${c.max.toFixed(2)}</div>
          </div>
          <div class="stat avg">
            <div class="label">Average</div>
            <div class="value">&#8364;${c.avg.toFixed(2)}</div>
          </div>
          <div class="stat">
            <div class="label">vs yesterday</div>
            <div class="value">${c.trend !== null ? (c.trend > 0 ? '+' : '') + '&#8364;' + Math.abs(c.trend).toFixed(2) : '-'}</div>
          </div>
          <div class="stat">
            <div class="label">Records</div>
            <div class="value">${c.dates.length}</div>
          </div>
        </div>
        <div class="chart-wrap"><canvas id="chart-${fi}-${ci}"></canvas></div>
      </div>`).join('');

    return `<div class="panel" id="panel-${fi+1}">
      <div class="card">
        <h2>${f.label}</h2>
        <div class="subtitle">${f.outbound_date} &rarr; ${f.return_date} &nbsp;&bull;&nbsp; Depart after ${f.outbound_after} &nbsp;&bull;&nbsp; ${f.combinations.length} combination(s)</div>
        ${comboSections}
      </div>
      <div class="card" style="padding:0;overflow:hidden;margin-top:16px">
        <table>
          <thead><tr>
            <th>Date</th><th>Combination</th><th>Out airline</th>
            <th>Ret airline</th><th>Price</th><th>vs prev</th>
          </tr></thead>
          <tbody id="table-${fi}"></tbody>
        </table>
      </div>
    </div>`;
  }).join('');
}

function populateFlightTables() {
  DATA.flights.forEach((f, fi) => {
    const body = document.getElementById(`table-${fi}`);
    if (!body) return;
    const allRows = [];
    f.combinations.forEach(c => {
      c.dates.forEach((d, i) => {
        allRows.push({
          date: d, combo: c.id,
          out_airline: c.outbound_airline, ret_airline: c.return_airline,
          price: c.prices[i],
          trend: i > 0 ? c.prices[i] - c.prices[i-1] : null
        });
      });
    });
    allRows.sort((a,b) => b.date.localeCompare(a.date) || a.combo.localeCompare(b.combo));
    body.innerHTML = allRows.map(r => `
      <tr>
        <td>${r.date}</td>
        <td><span class="combo-tag">${r.combo}</span></td>
        <td>${r.out_airline}</td>
        <td>${r.ret_airline}</td>
        <td class="price-col">&#8364;${r.price.toFixed(2)}</td>
        <td>${trendPill(r.trend)}</td>
      </tr>`).join('');
  });
}

function buildCharts() {
  const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const gridColor = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)';
  const textColor = isDark ? '#9a9890' : '#6b6b66';

  DATA.flights.forEach((f, fi) => {
    f.combinations.forEach((c, ci) => {
      const canvas = document.getElementById(`chart-${fi}-${ci}`);
      if (!canvas) return;
      new Chart(canvas, {
        type: 'line',
        data: {
          labels: c.dates,
          datasets: [{
            label: c.id,
            data: c.prices,
            borderColor: COLORS[ci % COLORS.length],
            backgroundColor: COLORS[ci % COLORS.length] + '18',
            borderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 6,
            tension: 0.3,
            fill: true,
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: ctx => ' EUR ' + ctx.parsed.y.toFixed(2)
              }
            }
          },
          scales: {
            x: {
              grid: { color: gridColor },
              ticks: { color: textColor, font: { size: 11 } }
            },
            y: {
              grid: { color: gridColor },
              ticks: {
                color: textColor, font: { size: 11 },
                callback: v => 'EUR' + v
              }
            }
          }
        }
      });
    });
  });
}

// Boot
document.getElementById('tabs').insertAdjacentHTML('beforeend',
  DATA.flights.map((f,i) =>
    `<div class="tab" onclick="showTab(${i+1})">${f.label.split('(')[0].trim()}</div>`
  ).join('')
);

document.getElementById('panels-root').innerHTML =
  buildOverviewPanel() + buildFlightPanels();

populateOverviewTable();
populateFlightTables();
buildCharts();
</script>
</body>
</html>
"""


def generate(data):
    tabs_html  = ""  # tabs are built dynamically in JS
    panels_html = ""  # panels too

    html = HTML_TEMPLATE
    html = html.replace("__GENERATED_AT__", data["generated_at"])
    html = html.replace("__FLIGHT_TABS__",  "")
    html = html.replace("__PANELS__",
        '<div id="panels-root"></div>')
    html = html.replace("__DATA_JSON__",
        json.dumps(data, ensure_ascii=False))
    return html


def run():
    init_db()
    config = load_config()
    data   = build_chart_data(config)

    html = generate(data)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    total_combos = sum(len(f["combinations"]) for f in data["flights"])
    print(f"Dashboard generated -> {OUTPUT_PATH}")
    print(f"  {len(data['flights'])} flight(s), {total_combos} combination(s)")


if __name__ == "__main__":
    run()
