from flask import Flask, Response, jsonify, request, render_template, abort
import psutil
import platform
import time
from flask import jsonify
from .errors import errors
import os
import requests
from datetime import datetime, timezone
import random
import base64
import uuid
import hashlib


start_time = time.time()

def format_duration(seconds):
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"

app = Flask(__name__, static_folder="templates/static")
app.register_blueprint(errors)

def restart_heroku_dyno():
    app_name = os.environ.get("HEROKU_APP_NAME")
    api_key = os.environ.get("HEROKU_API_KEY")

    if not app_name or not api_key:
        raise Exception("Missing HEROKU_APP_NAME or HEROKU_API_KEY")

    url = f"https://api.heroku.com/apps/{app_name}/dynos"
    headers = {
        "Accept": "application/vnd.heroku+json; version=3",
        "Authorization": f"Bearer {api_key}"
    }

    response = requests.delete(url, headers=headers)
    return response.status_code, response.json() if response.content else {}

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
            "/sysinfo": "System info (CPU, RAM, Disk, etc.)",
            "/utc-time": "Returns a wealthy amount of information about the current UTC time.",
            "/random-number?minimum=&maximum=": "Generates a random number between the minimum and maximum values (requires query params)",
            "/base64-encrypt": "Encrypts a text with base64",
            "/base64-decrypt": "Decrypts a text with base64",
            "/hash-generator": "Generates a hash for the provided data using the specified algorithm (default: sha256)",
            "/uuid-generator": "Generates a random UUID",
            "/currency-converter": "Converts an amount from one currency to another (requires query params)",
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

@app.route("/random-number")
def random_number():
    try:
        minimum = request.args.get("minimum")
        maximum = request.args.get("maximum")

        if minimum is None or maximum is None:
            return jsonify({"error": "Both 'minimum' and 'maximum' parameters are required."}), 400

        if not minimum.isdigit() or not maximum.isdigit():
            return jsonify({"error": "Both 'minimum' and 'maximum' must be valid integers."}), 400

        minimum = int(minimum)
        maximum = int(maximum)

        if minimum > maximum:
            return jsonify({"error": "Minimum value cannot be greater than maximum value."}), 400

        random_num = random.randint(minimum, maximum)
        return jsonify({"random_number": random_num})
    except ValueError:
        return jsonify({"error": "An unexpected error occurred. Please check your input."}), 400

@app.route("/utc-time")
def utc_time():
    utc_now = datetime.now(timezone.utc)
    return jsonify({
        "utc_time": utc_now.strftime("%Y-%m-%d %H:%M:%S"),
        "day": utc_now.day,
        "month_name": utc_now.strftime("%B"),
        "month_number": utc_now.month,
        "day_of_week": utc_now.strftime("%A"),
        "hour": utc_now.hour,
        "minute": utc_now.minute,
        "second": utc_now.second,
        "iso_format": utc_now.isoformat(),
        "week_of_year": utc_now.strftime("%U"),
        "day_of_year": utc_now.strftime("%j"),
        "quarter": (utc_now.month - 1) // 3 + 1,
        "is_leap_year": (utc_now.year % 4 == 0 and utc_now.year % 100 != 0) or (utc_now.year % 400 == 0),
        "timezone": "UTC",
        "epoch_time": int(utc_now.timestamp()),
        "year": utc_now.year,
        "year_short": int(str(utc_now.year)[-2:])
    })

@app.route("/admin")
def adminpage():
    return render_template("admindocs.html")

@app.route("/admin/signin")
def adminsignin():
    return render_template("signin.html")

@app.route("/admin/restart", methods=["POST"])
def restart_dyno():
    key = request.headers.get("X-API-KEY")
    allowed_keys = os.environ.get("ADMIN_API_KEYS", "").split(",")

    if key not in allowed_keys:
        abort(403, description="Forbidden: Invalid API key")

    code, data = restart_heroku_dyno()

    if code == 202:
        return jsonify({"message": "Heroku dyno restart triggered!", "success": True}), 202
    else:
        return jsonify({"success": False, "error": "Failed to restart dyno", "response": data}), 500

@app.route("/base64-encrypt", methods=["POST"])
def base64_encrypt():
    try:
        data = request.json.get("data")
        if not data:
            return jsonify({"error": "The 'data' field is required in the request body.", "success": False}), 400

        encoded_data = base64.b64encode(data.encode()).decode()
        return jsonify({"encrypted_data": encoded_data, "success": True})
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}", "success": False}), 500

@app.route("/base64-decrypt", methods=["POST"])
def base64_decrypt():
    try:
        data = request.json.get("data")
        if not data:
            return jsonify({"error": "The 'data' field is required in the request body.", "success": False}), 400

        decoded_data = base64.b64decode(data.encode()).decode()
        return jsonify({"decrypted_data": decoded_data, "success": True})
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}", "success": False}), 500

@app.route("/hash-generator", methods=["POST"])
def hash_generator():
    data = request.json.get("data")
    algorithm = request.json.get("algorithm", "sha256")
    if not data:
        return jsonify({"error": "The 'data' field is required in the request body.", "success": False}), 400
    try:
        hash_func = getattr(hashlib, algorithm)
    except AttributeError:
        return jsonify({"error": f"Unsupported algorithm", "success": False}), 400
    hashed = hash_func(data.encode()).hexdigest()
    return jsonify({"algorithm": algorithm, "hash": hashed, "success": True})

@app.route("/uuid-generator", methods=["GET"])
def uuid_generator():
    return jsonify({"uuid": str(uuid.uuid4())})

@app.route("/currency-converter")
def currency_converter():
    from requests import get
    base = request.args.get("base")
    target = request.args.get("target")
    amount = request.args.get("amount")
    if not base or not target or not amount:
        return jsonify({"error": "Parameters 'base', 'target', and 'amount' are required."}), 400
    try:
        amount = float(amount)
    except ValueError:
        return jsonify({"error": "'amount' must be a valid number."}), 400
    try:
        # Using Frankfurter API (no API key required)
        url = f"https://api.frankfurter.app/latest?amount={amount}&from={base.upper()}&to={target.upper()}"
        resp = get(url)
        if resp.status_code != 200:
            return jsonify({"error": "Failed to fetch exchange rate."}), 500
        data = resp.json()
        if target.upper() not in data.get("rates", {}):
            return jsonify({"error": f"Currency conversion failed: {data.get('error', 'Unknown error')}", "success": False}), 400
        return jsonify({
            "base": data["base"],
            "target": target.upper(),
            "amount": amount,
            "converted": data["rates"][target.upper()],
            "date": data["date"],
            "success": True
        })
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}", "success": False}), 500