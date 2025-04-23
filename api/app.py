from flask import Flask, Response, jsonify, request, render_template
import psutil
import platform
import time
from flask import jsonify
from .errors import errors

start_time = time.time()

app = Flask(__name__)
app.register_blueprint(errors)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/custom", methods=["POST"])
def custom():
    payload = request.get_json()

    if payload.get("say_hello") is True:
        output = jsonify({"message": "Hello!"})
    else:
        output = jsonify({"message": "..."})

    return output


@app.route("/health")
def health():
    return Response("OK", status=200)

@app.route("/error")
def error():
    return jsonify({"error": "This is an error response"}), 500

@app.route("/sysinfo")
def system_info():
    boot_time = psutil.boot_time()
    uptime = time.time() - boot_time

    cpu_percent = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    return jsonify({
        "cpu_usage_percent": cpu_percent,
        "cpu_cores": psutil.cpu_count(logical=False),
        "cpu_threads": psutil.cpu_count(logical=True),
        "ram_total_mb": round(ram.total / 1024**2),
        "ram_used_percent": ram.percent,
        "disk_total_gb": round(disk.total / 1024**3),
        "disk_used_percent": disk.percent,
        "uptime_seconds": int(uptime),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "python_version": platform.python_version()
    })