import datetime
import logging
import os
import threading
import time

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template_string

load_dotenv()  # load .env locally

API_KEY = os.environ.get("PVOUTPUT_API_KEY")
SYSTEM_ID = os.environ.get("PVOUTPUT_SYSTEM_ID")
USE_MOCK_DATA = os.environ.get("USE_MOCK_DATA", "").lower() == "true"

if not API_KEY or not SYSTEM_ID:
    raise ValueError("PVOutput API_KEY or SYSTEM_ID not set")

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

logger = logging.getLogger(__name__)

app = Flask(__name__)

cache = None
cache_time = 0
cache_lock = threading.Lock()


def fetch_pvoutput():
    today = datetime.date.today().strftime("%Y%m%d")
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")

    logger.info("Fetching PVOutput data...")

    headers = {
        "X-Pvoutput-Apikey": API_KEY,
        "X-Pvoutput-SystemId": SYSTEM_ID
    }

    # ----- TODAY SUMMARY -----
    r1 = requests.get(
        f"https://pvoutput.org/service/r2/getoutput.jsp?df={today}&dt={today}",
        headers=headers
    )
    r1.raise_for_status()

    summary = r1.text.strip().split(",")

    energy_wh = float(summary[1])
    peak_kw = float(summary[5]) / 1000
    peak_time = summary[6]

    total_kwh = round(energy_wh / 1000, 2)

    # ----- YESTERDAY SUMMARY -----
    r2 = requests.get(
        f"https://pvoutput.org/service/r2/getoutput.jsp?df={yesterday}&dt={yesterday}",
        headers=headers
    )
    r2.raise_for_status()

    summary = r2.text.strip().split(",")
    total_yesterday_kwh = round(float(summary[1]) / 1000, 2)

    # ----- INTERVAL DATA FOR GRAPH -----
    r3 = requests.get(
        f"https://pvoutput.org/service/r2/getstatus.jsp?d={today}&h=1&limit=288",
        headers=headers
    )
    r3.raise_for_status()

    times = []
    powers = []

    for line in r3.text.strip().split(";"):

        parts = line.split(",")

        if len(parts) < 5:
            continue

        times.append(parts[1])
        powers.append(float(parts[4]) / 1000)

    times.reverse()
    powers.reverse()

    current_kw = powers[-1] if powers else 0

    times, powers = trim_zero_edges(times, powers)

    return {
        "times": times,
        "powers_kwh": powers,
        "current_kw": current_kw,
        "total_kwh": total_kwh,
        "total_yesterday_kwh": total_yesterday_kwh,
        "peak_kw": peak_kw,
        "peak_time": peak_time
    }


def get_mock_pv_data():
    """
    Generate a hardcoded mock PV output data object
    for testing the dashboard.
    """
    times = [
        "07:00","07:30","08:00","08:30","09:00","09:30","10:00","10:30",
        "11:00","11:30","12:00","12:30","13:00","13:30","14:00","14:30",
        "15:00","15:30","16:00","16:30","17:00","17:30","18:00","18:30",
        "19:00","19:30","20:00"
    ]

    # Example power values (kW), roughly PV-shaped curve
    power = [
        0.0,0.5,1.0,2.0,3.0,2.2,5.5,6.8,
        7.5,8.5,9.0,9.5,9.0,8.5,7.5,6.0,
        4.5,3.2,2.0,1.8,1.0,0.8,0.6,0.5,
        0.3,0.3,0.1
    ]

    total_kwh = round(sum(power) * 0.5, 2)  # each slot = 0.5h
    peak_kw = max(power)
    peak_index = power.index(peak_kw)
    peak_time = times[peak_index]
    current_kw = power[-1]
    total_yesterday_kwh = round(total_kwh * 0.9, 2)

    return {
        "times": times,
        "powers_kwh": power,
        "current_kw": current_kw,
        "total_kwh": total_kwh,
        "total_yesterday_kwh": total_yesterday_kwh,
        "peak_kw": peak_kw,
        "peak_time": peak_time
    }


def get_data():
    global cache, cache_time
    with cache_lock:
        if cache and time.time() - cache_time < 300: # Cache 5mins (rate limiting, max. 12 calls per hour)
            return cache

        cache = fetch_pvoutput()
        cache_time = time.time()

        return cache


def trim_zero_edges(t_arr, p_arr):
    """
    Keep only the first and last zero at the edges, remove intermediate leading/trailing zeros.
    t_arr and p_arr must have the same length.
    """
    if not p_arr or not t_arr or len(t_arr) != len(p_arr):
        return t_arr, p_arr

    # Find first non-zero index
    first = 0
    while first < len(p_arr) and p_arr[first] == 0:
        first += 1
    first = max(first - 1, 0)  # keep one zero at the start

    # Find last non-zero index
    last = len(p_arr) - 1
    while last >= 0 and p_arr[last] == 0:
        last -= 1
    last = min(last + 1, len(p_arr)-1)  # keep one zero at the end

    # Slice arrays
    trimmed_t = t_arr[first:last+1]
    trimmed_p = p_arr[first:last+1]

    return trimmed_t, trimmed_p


@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/data")
def data():
    if USE_MOCK_DATA:
        return jsonify(get_mock_pv_data())
    return jsonify(get_data())


@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>

<title>PV-Dashboard</title>
<link rel="icon" type="image/x-icon" href="{{ url_for('static', filename='favicon.ico') }}">
<meta name="viewport" content="width=device-width, initial-scale=1">

<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>

<style>

body{
    background:#2D3036;
    color:white;
    font-family:Arial;
    text-align:center;
    margin: 20px 50px 20px 50px;
}

h1{
    margin-bottom:30px;
}

.grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr); /* two columns */
    gap: 30px;                             /* space between cards */
    max-width: 1000px;                       /* max total width of both cards + gap */
    margin: 0 auto 50px;                    /* center horizontally, 50px margin-bottom */
}

.card{
    background:#42454B;
    padding:20px;
    border-radius:10px;
    box-shadow:0 0 10px rgba(0,0,0,0.5);
    max-width: 500px
}

.title{
    font-size:18px;
    margin-bottom: 8px;
}

.value{
    font-size:28px;
    font-weight:bold;
}

/* Chart container spans both cards */
.chart-container{
    grid-column: 1 / -1;
    margin: 0 auto 30px auto;
    max-width: 1000px;
}

canvas{
    width:100% !important;
    height:400px !important;
}

@media (max-width: 600px){
    .grid{
        grid-template-columns: 1fr; /* stack cards on small screens */
    }
    .chart-container{
        max-width: 100%;
    }
}

</style>

</head>
<body>

<h1 style="display: flex; align-items: center; justify-content: center; gap: 20px;">
  <img src="{{ url_for('static', filename='pvlogo.png') }}" height="50" alt="PV Logo" />
  PV-Produktion
</h1>

<div class="grid">

<div class="card">
<div class="title">Aktuelle Leistung</div>
<div id="current" class="value">-</div>
</div>

<div class="card">
<div class="title">Heute erzeugte Energie</div>
<div id="total" class="value">-</div>
</div>

<div class="card">
<div class="title">Heutige Spitzenleistung</div>
<div id="peak" class="value">-</div>
</div>

<div class="card">
<div class="title">Gestern erzeugte Energie</div>
<div id="total_yesterday" class="value">-</div>
</div>

</div>

<div class="chart-container">
<canvas id="chart"></canvas>
</div>

<div id="updated" style="margin-top:10px;color:#aaa;font-size:14px"></div>

<script>

let chart;

function formatNumber(n){
    return Number(n).toLocaleString("de-DE", {maximumFractionDigits:2});
}

function loadData(){

    fetch('data')
    .then(r => {
        if(!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
    })
    .then(data=>{

        document.getElementById("current").innerHTML = formatNumber(data.current_kw) + " kW";
        document.getElementById("total").innerHTML = formatNumber(data.total_kwh) + " kWh";
        document.getElementById("peak").innerHTML = formatNumber(data.peak_kw) + " kW um " + data.peak_time;
        document.getElementById("total_yesterday").innerHTML = formatNumber(data.total_yesterday_kwh) + " kWh";
        document.getElementById("updated").innerHTML = "Letzte Aktualisierung: " + new Date().toLocaleTimeString("de-DE")
            + " / " + data.times[data.times.length - 1];;

        if(!chart){
            chart = new Chart(document.getElementById('chart'),{
                type:'line',
                data:{
                    labels:data.times,
                    datasets:[{
                        label:"Power (kW)",
                        data:data.powers_kwh,
                        tension:0.3,
                        fill:true,
                        backgroundColor:"rgba(0,150,255,0.2)",
                        borderColor:"rgba(0,150,255,1)",
                        pointRadius:0
                    }]
                },
                options:{
                    plugins:{legend:{display:false}},
                    scales: {
                        x: {
                            ticks: {                             // x-axis labels
                                color: "white",   
                                maxTicksLimit:12,
                                autoSkip: true
                            },
                            grid: {
                                color: "#42454B"                 // x-axis grid lines
                            }
                        },
                        y: {
                            beginAtZero:true,
                            ticks: {                             // y-axis labels
                                color: "white" 
                            },          
                            grid: {
                                color: "#42454B"                 // y-axis grid lines
                            },
                            title: {
                                display: true,
                                text: "Leistung (kW)",
                                color: "white"
                            }
                        }
                    }
                }
            });
        } else {
            chart.data.labels = data.times;
            chart.data.datasets[0].data = data.powers_kwh;
            chart.update('none');
        }

    })
    .catch(err => {
        console.error("Fehler beim Laden der Daten:", err);

        document.getElementById("updated").innerHTML =
            "⚠ Fehler beim Laden der Daten – " +
            new Date().toLocaleTimeString("de-DE");
    });

}

loadData();
setInterval(loadData,60000); // refresh every minute (caching in backend)

</script>

</body>
</html>
""")



app.run(host="0.0.0.0", port=5000, threaded=True)
