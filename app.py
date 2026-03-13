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
    power = []

    for line in r2.text.strip().split(";"):

        parts = line.split(",")

        if len(parts) < 5:
            continue

        times.append(parts[1])
        power.append(float(parts[4]))

    times.reverse()
    power.reverse()

    current = power[-1] if power else 0

    return {
        "times": times,
        "power": power,
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

<title>Solar Dashboard</title>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<style>

body{
    background:#2D3036;
    color:white;
    font-family:Arial;
    text-align:center;
    margin:20px;
}

h1{margin-bottom:30px;}

.grid{
    display:grid;
    grid-template-columns:repeat(2, 1fr); /* 2 cards per row */
    gap:20px;
    margin-bottom:30px;
}

.card{
    background:#42454B;
    padding:20px;
    border-radius:10px;
    box-shadow:0 0 10px rgba(0,0,0,0.5);
}

.value{
    font-size:28px;
    font-weight:bold;
}

/* Chart container spans both cards */
.chart-container{
    grid-column: 1 / -1; /* full width of grid */
    margin: 0 auto 30px auto;
    max-width: 700px;     /* roughly 2 card widths */
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

<h1>☀ Solar Produktion</h1>

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
                    scales:{x:{ticks:{color:"white"}}, y:{ticks:{color:"white"}}}
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
