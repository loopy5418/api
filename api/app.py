from flask import Flask, Response, jsonify, request, render_template, abort
import psutil
import platform
import time
from flask import jsonify
from .errors import errors
import os

start_time = time.time()

def format_duration(seconds):
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"

app = Flask(__name__)
app.register_blueprint(errors)


@app.route("/")
def index():
    user_agent = request.headers.get('User-Agent', '').lower()
    if "mozilla" in user_agent or "chrome" in user_agent or "safari" in user_agent:
        return render_template("index.html")
    else:
        return jsonify({
        "base_url": "https://api.loopy5418.dev",
        "endpoints": {
            "/": "Index page",
            "/health": "Health check endpoint",
            "/seconds-to-time?seconds": "Converts seconds into hh:mm:ss (requires query params)",
            "/sysinfo": "System info (CPU, RAM, Disk, etc.)"
        },
        "support": {
            "discord": "work in progress"
        },
        "note": "This API supports both browser and direct HTTP requests"
    })


@app.route("/health")
def health():
    return Response("OK", status=200, mimetype="text/plain")

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
        "python_version": platform.python_version(),
        "ram_used_mb": round(ram.used / 1024**2),
        "disk_used_gb": round(disk.used / 1024**3),
    })

@app.route("/seconds-to-time")
def seconds_to_time():
    query = request.args.get("seconds")
    if query is None:
        return jsonify({"error": "Please provide a query with your seconds. Append ?seconds=(put your number here) to your URL."}), 400
    
    if not query.isdigit():
        return jsonify({"error": "Please provide a valid number."}), 400
    
    final = format_duration(int(query))
    return jsonify({"formatted_time": final})

@app.route("/admin/signin")
def adminsignin():
    return render_template("signin.html")

@app.route("/admin/restart", methods=["POST"])
def restart_dyno():
    key = request.headers.get("X-API-KEY")
    allowed_keys = os.environ.get("ADMIN_API_KEYS", "").split(",")

    if key not in allowed_keys:
        abort(403, description="Forbidden: Invalid API key")

    os._exit(0)
    return jsonify({"message": "Dyno restarting..."})