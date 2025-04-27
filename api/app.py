from flask import Flask, Response, jsonify, request, render_template, abort, redirect
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
import io
from PIL import Image, ImageDraw, ImageFont
from flask_cors import CORS
from googletrans import Translator
import logging

start_time = time.time()

def format_duration(seconds):
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"

app = Flask(__name__, static_folder="templates/static")
app.register_blueprint(errors)
CORS(app)
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

class IgnoreSysinfoFilter(logging.Filter):
    def filter(self, record):
        # Only log if the path is not /sysinfo or /health
        try:
            from flask import request
            path = request.path
            return path not in ["/sysinfo", "/health"]
        except RuntimeError:
            # Not in a request context
            return True

for handler in app.logger.handlers:
    handler.addFilter(IgnoreSysinfoFilter())

@app.route("/")
def index():
    user_agent = request.headers.get('User-Agent', '').lower()
    discord_invite = os.environ.get("DISCORD_INVITE", "#")
    if "mozilla" in user_agent or "chrome" in user_agent or "safari" in user_agent:
        return render_template("index.html", discord_invite=discord_invite)
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
            "/image-with-text": "Generates an image with text overlay (requires POST data)",
            "/currency-converter": "Converts an amount from one currency to another (requires query params)",
            "/qr": "Generates a QR code from the provided data (requires query params)",
            "/emojify": "Converts text to emoji representation (requires query params)",
            "/owoify": "Converts text to owo representation (requires query params)",
            "/choose": "Randomly chooses an option from a comma-separated list (requires query params)",
            "/wifi-qr": "Generates a WiFi QR code from ssid, password, security, and hidden query parameters.",
            "/translate": "Translates text",
            "/webhook-send": "Sends a message to a Discord webhook (requires POST data)"
        },
        "support": {
            "discord": f"{discord_invite}",
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
        return jsonify({"error": "Please provide a query with your seconds. Append ?seconds=(put your number here) to your URL.", "success": False}), 400
    
    if not query.isdigit():
        return jsonify({"error": "Please provide a valid number.", "success": False}), 400
    
    final = format_duration(int(query))
    return jsonify({"formatted_time": final, "success": True})

@app.route("/random-number")
def random_number():
    try:
        minimum = request.args.get("minimum")
        maximum = request.args.get("maximum")

        if minimum is None or maximum is None:
            return jsonify({"error": "Both 'minimum' and 'maximum' parameters are required.", "success": False}), 400

        if not minimum.isdigit() or not maximum.isdigit():
            return jsonify({"error": "Both 'minimum' and 'maximum' must be valid integers.", "success": False}), 400

        minimum = int(minimum)
        maximum = int(maximum)

        if minimum > maximum:
            return jsonify({"error": "Minimum value cannot be greater than maximum value.", "success": False}), 400

        random_num = random.randint(minimum, maximum)
        return jsonify({"random_number": random_num, "success": True})
    except ValueError:
        return jsonify({"error": "An unexpected error occurred. Please check your input.", "success": False}), 400

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
        "year_short": int(str(utc_now.year)[-2:]),
        "success": True
    })

@app.route("/admin")
def adminpage():
    discord_invite = os.environ.get("DISCORD_INVITE", "#")
    return render_template("admindocs.html", discord_invite=discord_invite)

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
    return jsonify({"uuid": str(uuid.uuid4()), "success": True})

@app.route("/currency-converter")
def currency_converter():
    from requests import get
    base = request.args.get("base")
    target = request.args.get("target")
    amount = request.args.get("amount")
    if not base or not target or not amount:
        return jsonify({"error": "Parameters 'base', 'target', and 'amount' are required.", "success": False}), 400
    try:
        amount = float(amount)
    except ValueError:
        return jsonify({"error": "'amount' must be a valid number.", "success": False}), 400
    try:
        # Using Frankfurter API (no API key required)
        url = f"https://api.frankfurter.app/latest?amount={amount}&from={base.upper()}&to={target.upper()}"
        resp = get(url)
        if resp.status_code != 200:
            return jsonify({"error": "Failed to fetch exchange rate.", "success": False}), 500
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

@app.route("/support")
def support_redirect():
    discord_invite = os.environ.get("DISCORD_INVITE", "#")
    return redirect(discord_invite)

@app.route("/image-with-text", methods=["POST"])
def image_with_text():
    data = request.json
    image_url = data.get("image_url")
    text = data.get("text")
    position = data.get("position", (10, 10))
    color = data.get("color", "#FFFFFF")
    font_size = data.get("font_size", 32)
    font_style = data.get("font_style", "normal").lower()

    if not image_url or not text:
        return jsonify({"error": "'image_url' and 'text' are required fields.", "success": False}), 400

    try:
        # Download the image with a user-agent header
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ImageBot/1.0)"}
        response = requests.get(image_url, headers=headers, timeout=10)
        if int(response.headers.get("Content-Length", 0)) > 8 * 1024 * 1024:
            return jsonify({"error": "File too big!", "success": False}), 400
        content_type = response.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            return jsonify({"error": f"URL did not return an image. Content-Type: {content_type}", "success": False}), 400
        if len(response.content) > 8 * 1024 * 1024:
            return jsonify({"error": "File too big!", "success": False}), 400
        image = Image.open(io.BytesIO(response.content)).convert("RGBA")
        draw = ImageDraw.Draw(image)
        try:
            # Try to use a font that supports different sizes
            font_path_base = os.path.join(os.path.dirname(__file__), "templates", "static")
            font_files = {
                "normal": "Roboto-Regular.ttf",
                "bold": "Roboto-Bold.ttf",
                "italic": "Roboto-Italic.ttf",
                "bold-italic": "Roboto-BoldItalic.ttf"
            }
            font_file = font_files.get(font_style, "Roboto-Regular.ttf")
            font_path = os.path.join(font_path_base, font_file)
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, font_size)
            else:
                font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()
        width, height = image.size
        # Calculate text size (compatibility for Pillow >=10)
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError:
            text_width, text_height = font.getsize(text)
        if isinstance(position, str):
            pos = position.lower().strip()
            if pos == "top":
                position = ((width - text_width) // 2, 10)
            elif pos == "center":
                position = ((width - text_width) // 2, (height - text_height) // 2)
            elif pos == "bottom":
                position = ((width - text_width) // 2, height - text_height - 10)
            else:
                try:
                    position = tuple(map(int, pos.strip("() ").split(",")))
                except Exception:
                    position = (10, 10)
        elif isinstance(position, (list, tuple)) and len(position) == 2:
            position = tuple(position)
        else:
            position = (10, 10)
        draw.text(position, text, fill=color, font=font)
        img_bytes = io.BytesIO()
        image.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        return Response(img_bytes, mimetype="image/png")
    except Exception as e:
        return jsonify({"error": f"Failed to process image: {str(e)}", "success": False}), 500

@app.route("/qr")
def qr_code():
    import qrcode
    import io
    data = request.args.get("data")
    if not data:
        return jsonify({"error": "Missing 'data' query parameter.", "success": False}), 400
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(buf, mimetype="image/png")

@app.route("/wifi-qr")
def wifi_qr():
    import qrcode
    import io
    ssid = request.args.get("ssid")
    password = request.args.get("password", "")
    security = request.args.get("security", "WPA")
    hidden = request.args.get("hidden", "false").lower() == "true"
    if not ssid:
        return jsonify({"error": "Missing 'ssid' query parameter.", "success": False}), 400
    qr_data = f"WIFI:T:{security};S:{ssid};P:{password};{'H:true;' if hidden else ''};"
    img = qrcode.make(qr_data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(buf, mimetype="image/png")

@app.route("/emojify")
def emojify():
    text = request.args.get("text")
    if not text:
        return jsonify({"error": "Missing 'text' query parameter.", "success": False}), 400
    def to_emoji(c):
        if c.isalpha():
            return f":regional_indicator_{c.lower()}:"
        elif c.isdigit():
            nums = ["zero","one","two","three","four","five","six","seven","eight","nine"]
            return f":{nums[int(c)]}:"
        elif c == ' ':
            return '   '
        else:
            return c
    result = ' '.join(to_emoji(c) for c in text)
    return jsonify({"result": result, "success": True})

@app.route("/owoify")
def owoify():
    text = request.args.get("text")
    if not text:
        return jsonify({"error": "Missing 'text' query parameter.", "success": False}), 400
    owo = text
    owo = owo.replace('r', 'w').replace('l', 'w')
    owo = owo.replace('R', 'W').replace('L', 'W')
    owo = owo.replace('no', 'nyo').replace('No', 'Nyo')
    owo = owo.replace('ove', 'uv')
    faces = [';;w;;', 'owo', 'UwU', '>w<', '^w^']
    import random
    owo += ' ' + random.choice(faces)
    return jsonify({"result": owo, "success": True})

@app.route("/choose")
def choose():
    options = request.args.get("options")
    if not options:
        return jsonify({"error": "Missing 'options' query parameter.", "success": False}), 400
    opts = [o.strip() for o in options.split(",") if o.strip()]
    if not opts:
        return jsonify({"error": "No valid options provided.", "success": False}), 400
    import random
    choice = random.choice(opts)
    return jsonify({"result": choice, "success": True})

@app.route("/translate")
def translate_text():
    return jsonify({"error": "This endpoint is temporarily disabled.", "success": False}), 500

@app.route("/webhook-send", methods=["POST"])
def webhook_send():
    import requests

    def validate_embed(embed):
        """Validate one embed dict and return a cleaned version or raise ValueError."""
        if not isinstance(embed, dict):
            raise ValueError("Each embed must be an object.")

        embed_obj = {}

        if "title" in embed:
            if not isinstance(embed["title"], str):
                raise ValueError("'title' must be a string.")
            embed_obj["title"] = embed["title"]

        if "description" in embed:
            if not isinstance(embed["description"], str):
                raise ValueError("'description' must be a string.")
            embed_obj["description"] = embed["description"]

        if "url" in embed:
            if not isinstance(embed["url"], str):
                raise ValueError("'url' must be a string.")
            embed_obj["url"] = embed["url"]

        if "color" in embed:
            if not isinstance(embed["color"], int):
                raise ValueError("'color' must be an integer.")
            embed_obj["color"] = embed["color"]

        if "author" in embed:
            if not isinstance(embed["author"], dict):
                raise ValueError("'author' must be an object.")
            author = {}
            if "name" in embed["author"]:
                if not isinstance(embed["author"]["name"], str):
                    raise ValueError("'author.name' must be a string.")
                author["name"] = embed["author"]["name"]
            if "url" in embed["author"]:
                if not isinstance(embed["author"]["url"], str):
                    raise ValueError("'author.url' must be a string.")
                author["url"] = embed["author"]["url"]
            if "icon_url" in embed["author"]:
                if not isinstance(embed["author"]["icon_url"], str):
                    raise ValueError("'author.icon_url' must be a string.")
                author["icon_url"] = embed["author"]["icon_url"]
            if author:
                embed_obj["author"] = author

        if "footer" in embed:
            if not isinstance(embed["footer"], dict):
                raise ValueError("'footer' must be an object.")
            footer = {}
            if "text" in embed["footer"]:
                if not isinstance(embed["footer"]["text"], str):
                    raise ValueError("'footer.text' must be a string.")
                footer["text"] = embed["footer"]["text"]
            if "icon_url" in embed["footer"]:
                if not isinstance(embed["footer"]["icon_url"], str):
                    raise ValueError("'footer.icon_url' must be a string.")
                footer["icon_url"] = embed["footer"]["icon_url"]
            if footer:
                embed_obj["footer"] = footer

        if "fields" in embed:
            if not isinstance(embed["fields"], list):
                raise ValueError("'fields' must be a list.")
            fields = []
            for field in embed["fields"]:
                if not isinstance(field, dict):
                    raise ValueError("Each field in 'fields' must be an object.")
                if "name" not in field or "value" not in field:
                    raise ValueError("Each field must have 'name' and 'value'.")
                if not isinstance(field["name"], str) or not isinstance(field["value"], str):
                    raise ValueError("'field.name' and 'field.value' must be strings.")
                field_obj = {
                    "name": field["name"],
                    "value": field["value"],
                    "inline": bool(field.get("inline", False))
                }
                fields.append(field_obj)
            embed_obj["fields"] = fields

        if "image" in embed:
            if not isinstance(embed["image"], dict) or "url" not in embed["image"] or not isinstance(embed["image"]["url"], str):
                raise ValueError("'image' must be an object with a string 'url'.")
            embed_obj["image"] = {"url": embed["image"]["url"]}

        if "thumbnail" in embed:
            if not isinstance(embed["thumbnail"], dict) or "url" not in embed["thumbnail"] or not isinstance(embed["thumbnail"]["url"], str):
                raise ValueError("'thumbnail' must be an object with a string 'url'.")
            embed_obj["thumbnail"] = {"url": embed["thumbnail"]["url"]}

        return embed_obj

    data = request.json
    url = data.get("url")
    content = data.get("content")
    username = data.get("username")
    avatar_url = data.get("avatar_url")
    embeds = data.get("embeds")

    if not url or (not content and not embeds):
        return jsonify({"error": "'url' and either 'content' or 'embeds' are required fields.", "success": False}), 400

    payload = {}

    if content:
        if not isinstance(content, str):
            return jsonify({"error": "'content' must be a string.", "success": False}), 400
        payload["content"] = content

    if username:
        if not isinstance(username, str):
            return jsonify({"error": "'username' must be a string.", "success": False}), 400
        payload["username"] = username

    if avatar_url:
        if not isinstance(avatar_url, str):
            return jsonify({"error": "'avatar_url' must be a string.", "success": False}), 400
        payload["avatar_url"] = avatar_url

    if embeds:
        if not isinstance(embeds, list):
            return jsonify({"error": "'embeds' must be a list.", "success": False}), 400

        try:
            payload["embeds"] = [validate_embed(embed) for embed in embeds]
        except ValueError as e:
            return jsonify({"error": str(e), "success": False}), 400

    try:
        resp = requests.post(url, json=payload)
        if resp.status_code in (200, 204):
            return jsonify({"success": True})
        else:
            return jsonify({"error": f"Webhook send failed: {resp.text}", "success": False}), 500
    except Exception as e:
        return jsonify({"error": f"Request failed: {str(e)}", "success": False}), 500

@app.route("/status")
def status():
    return render_template("status.html")