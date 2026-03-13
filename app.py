import datetime
import os

from flask import Flask, jsonify, render_template_string
import requests
import time
import threading
import logging
from dotenv import load_dotenv

load_dotenv()  # load .env locally

API_KEY = os.environ.get("PVOUTPUT_API_KEY")
SYSTEM_ID = os.environ.get("PVOUTPUT_SYSTEM_ID")

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

    logger.info("Fetching PVOutput data...")

    headers = {
        "X-Pvoutput-Apikey": API_KEY,
        "X-Pvoutput-SystemId": SYSTEM_ID
    }

    # ----- DAILY SUMMARY -----
    r1 = requests.get(
        f"https://pvoutput.org/service/r2/getoutput.jsp?d={today}",
        headers=headers
    )

    summary = r1.text.strip().split(",")

    energy_wh = float(summary[1])
    peak_w = float(summary[5])
    peak_time = summary[6]

    total_kwh = round(energy_wh / 1000, 2)

    # ----- INTERVAL DATA FOR GRAPH -----
    r2 = requests.get(
        f"https://pvoutput.org/service/r2/getstatus.jsp?d={today}&h=1&limit=288",
        headers=headers
    )

    times = []
    powers = []

    for line in r2.text.strip().split(";"):

        parts = line.split(",")

        if len(parts) < 5:
            continue

        times.append(parts[1])
        powers.append(float(parts[4]))

    times.reverse()
    powers.reverse()

    current = powers[-1] if powers else 0

    times, powers = trim_zero_edges(times, powers)

    return {
        "times": times,
        "power": powers,
        "total_kwh": total_kwh,
        "peak": float(peak_w/1000),
        "peak_time": peak_time,
        "current": float(current/1000)
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
    return jsonify(get_data())


@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>

<title>PV Dashboard</title>

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
    max-width: 850px;                       /* max total width of both cards + gap */
    margin: 0 auto 50px;                    /* center horizontally, 50px margin-bottom */
}

.card{
    background:#42454B;
    padding:20px;
    border-radius:10px;
    box-shadow:0 0 10px rgba(0,0,0,0.5);
    max-width: 400px
}

.value{
    font-size:28px;
    font-weight:bold;
}

/* Chart container spans both cards */
.chart-container{
    grid-column: 1 / -1;
    margin: 0 auto 30px auto;
    max-width: 800px;
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

<h1>☀ PV Produktion</h1>

<div class="grid">

<div class="card">
<div>Aktuelle Leistung</div>
<div id="current" class="value">-</div>
</div>

<div class="card">
<div>Tagesproduktion</div>
<div id="total" class="value">-</div>
</div>

<div class="card">
<div>Spitzenleistung</div>
<div id="peak" class="value">-</div>
</div>

<div class="card">
<div>Spitzenzeit</div>
<div id="peaktime" class="value">-</div>
</div>

</div>

<div class="chart-container">
<canvas id="chart"></canvas>
</div>

<script>

let chart;

function loadData(){

    fetch('data')
    .then(r=>r.json())
    .then(data=>{

        document.getElementById("current").innerHTML = data.current + " kW";
        document.getElementById("total").innerHTML = data.total_kwh + " kWh";
        document.getElementById("peak").innerHTML = data.peak + " kW";
        document.getElementById("peaktime").innerHTML = data.peak_time;

        if(!chart){
            chart = new Chart(document.getElementById('chart'),{
                type:'line',
                data:{
                    labels:data.times,
                    datasets:[{
                        label:"Power (kW)",
                        data:data.power,
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
                            ticks: { color: "white" },           // x-axis labels
                            grid: {
                                color: "#42454B"                 // x-axis grid lines
                            }
                        },
                        y: {
                            ticks: { color: "white" },           // y-axis labels
                            grid: {
                                color: "#42454B"                 // y-axis grid lines
                            }
                        }
                    }
                }
            });
        } else {
            chart.data.labels = data.times;
            chart.data.datasets[0].data = data.power;
            chart.update();
        }

    });

}

loadData();
setInterval(loadData,300000); // refresh every 5 minutes

</script>

</body>
</html>
""")



app.run(host="0.0.0.0", port=5000, threaded=True)
