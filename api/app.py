from flask import Flask, Response, jsonify, request, render_template, abort, redirect, send_file
import psutil
import platform
import time
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
import logging
import string
from zoneinfo import ZoneInfo
import uuid
import psycopg2
import urllib.parse as up
import math
import pyfiglet
from g4f.client import Client
import asyncio
import calendar
from dateutil import parser
import pytz
import markdown
import discord
import aiohttp
import mimetypes
from youtubesearchpython import VideosSearch

gptc = Client()
start_time = time.time()
TEXT_FILE_EXTENSIONS = ['.txt', '.js', '.bat', '.md', '.csv', '.log', '.json', '.yaml', '.yml', '.xml', '.html']

def run_async(coro):
    return asyncio.run(coro)

async def fetch_message_attachments(bot_token, channel_id, message_id):
    intents = discord.Intents.default()
    bot = discord.Client(intents=intents)

    result = {}

    @bot.event
    async def on_ready():
        try:
            print(f"Logged in as {bot.user}")
            channel = bot.get_channel(channel_id)
            if channel is None:
                print("Channel not in cache, fetching from API...")
                channel = await bot.fetch_channel(channel_id)

            message = await channel.fetch_message(message_id)
            print(f"Fetched message with ID {message.id}")

            attachments_info = []

            for attachment in message.attachments:
                print(f"Found attachment: {attachment.filename}")
                info = {
                    "filename": attachment.filename,
                    "url": attachment.url
                }

                # Guess file type from mimetypes
                file_type, _ = mimetypes.guess_type(attachment.filename)
                info["fileType"] = file_type if file_type else "unknown"

                # Check file extension manually to determine if we should fetch text content
                if any(attachment.filename.lower().endswith(ext) for ext in TEXT_FILE_EXTENSIONS):
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(attachment.url) as resp:
                                if resp.status == 200:
                                    text = await resp.text()
                                    info["content"] = text
                                else:
                                    info["content"] = f"Failed to fetch content: HTTP {resp.status}"
                    except Exception as e:
                        info["content"] = f"Error: {str(e)}"

                attachments_info.append(info)

            result["attachments"] = attachments_info
            result["success"] = True

        except Exception as e:
            result["error"] = str(e)
            result["success"] = False
        finally:
            await bot.close()

    await bot.start(bot_token)
    return result

def is_admin():
    key = request.headers.get("X-API-KEY")
    allowed_keys = os.environ.get("ADMIN_API_KEYS", "").split(",")
    if key not in allowed_keys:
        abort(403, description="Forbidden: Invalid API key")

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
        try:
            from flask import request
            path = request.path
            return path not in ["/sysinfo", "/health"]
        except RuntimeError:
            return True

for handler in app.logger.handlers:
    handler.addFilter(IgnoreSysinfoFilter())

DATABASE = 'api_keys.db'

def get_db():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise Exception("DATABASE_URL not set")

    up.uses_netloc.append("postgres")
    url = up.urlparse(db_url)

    conn = psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            user_id TEXT PRIMARY KEY,
            api_key TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS site_news (
            id SERIAL PRIMARY KEY,
            content TEXT
        )
    ''')
    conn.commit()
    conn.close()
with app.app_context():
    init_db()
    
def checkapikey(key):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM api_keys WHERE api_key = %s", (key,))
    result = c.fetchone()
    conn.close()
    return result is not None

@app.route('/admin/update-news', methods=['GET', 'POST'])
def manage_news():
    if request.method == 'GET':
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT content FROM site_news WHERE id = 1")
        row = c.fetchone()
        conn.close()
        return jsonify({"content": row[0] if row else ""})

    # POST (create/update or delete if empty)
    is_admin()  # Validate using admin API key
    data = request.get_json()
    content = data.get('content', '').strip()

    conn = get_db()
    c = conn.cursor()

    if content:
        c.execute("INSERT INTO site_news (id, content) VALUES (1, %s) ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content", (content,))
    else:
        c.execute("DELETE FROM site_news WHERE id = 1")

    conn.commit()
    conn.close()
    return jsonify({"success": True})
    

@app.route("/admin/get-user-id", methods=["GET"])
def get_user_id_from_key():
    key = request.headers.get("X-API-KEY")
    if key not in os.environ.get("ADMIN_API_KEYS", "").split(","):
        abort(403)

    api_key = request.args.get("api_key")
    if not api_key:
        return jsonify({"error": "Missing api_key", "success": False}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM api_keys WHERE api_key = %s", (api_key,))
    result = c.fetchone()
    conn.close()

    if not result:
        return jsonify({"error": "API key not found", "success": False}), 404

    return jsonify({"api_key": api_key, "user_id": result[0], "success": True})

@app.route("/admin/generate-key", methods=["POST"])
def generate_key():
    key = request.headers.get("X-API-KEY")
    if key not in os.environ.get("ADMIN_API_KEYS", "").split(","):
        abort(403)

    data = request.get_json()
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"error": "Missing user_id", "success": False}), 400

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT api_key FROM api_keys WHERE user_id = %s", (user_id,))
    existing = c.fetchone()

    if existing:
        conn.close()
        return jsonify({"user_id": user_id, "api_key": existing[0], "success": False, "error": "API Key for this user already exists"})

    api_key = str(uuid.uuid4())
    c.execute("INSERT INTO api_keys (user_id, api_key) VALUES (%s, %s)", (user_id, api_key))
    conn.commit()
    conn.close()

    return jsonify({"user_id": user_id, "api_key": api_key, "success": True})

@app.route("/admin/get-key", methods=["GET"])
def get_key():
    key = request.headers.get("X-API-KEY")
    if key not in os.environ.get("ADMIN_API_KEYS", "").split(","):
        abort(403)

    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "Missing user_id", "success": False}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT api_key FROM api_keys WHERE user_id = %s", (user_id,))
    result = c.fetchone()
    conn.close()

    if not result:
        return jsonify({"error": "No API key found", "success": False}), 404

    return jsonify({"user_id": user_id, "api_key": result[0], "success": True})

@app.route("/admin/delete-key", methods=["DELETE"])
def delete_key():
    key = request.headers.get("X-API-KEY")
    if key not in os.environ.get("ADMIN_API_KEYS", "").split(","):
        abort(403)
    user_id = request.args.get("user_id")

    if not user_id:
        return jsonify({"error": "Missing user_id", "success": False}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM api_keys WHERE user_id = %s", (user_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": f"API key for user {user_id} deleted", "success": True})

@app.route("/admin/keys")
def keyeditor():
    return render_template("keymaker.html")

@app.route("/")
def index():
    user_agent = request.headers.get('User-Agent', '').lower()
    discord_invite = os.environ.get("DISCORD_INVITE", "#")
    if "mozilla" in user_agent or "chrome" in user_agent or "safari" in user_agent:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT content FROM site_news WHERE id = 1")
        news_row = c.fetchone()
        conn.close()

        raw_news = news_row[0] if news_row else None
        news_html = markdown.markdown(raw_news) if raw_news else None
        return render_template("index.html", discord_invite=discord_invite, news=news_html)
    else:
        return jsonify({"status": True, "discord": f"{discord_invite}"})


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
    apikey = request.args.get("key")
    if not apikey:
        return jsonify({"error": "Missing api key! Get it from our server at api.loopy5418.dev/support. Example: ?key=apikeyhere", "success": False})
    if not checkapikey(apikey):
        return jsonify({"message": "Invalid API key", "success": False}), 403
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
            return jsonify({"error": f"Currency conversion failed: {data.get('error', 'Unknown error')}", "success": False})
        return jsonify({
            "base": data["base"],
            "target": target.upper(),
            "amount": amount,
            "converted": data["rates"][target.upper()],
            "date": data["date"],
            "success": True,
            "note": "This information is from Frankfurter API. Full credits to them."
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
    apikey = data.get("api_key")
    if not apikey:
        return jsonify({"error": "Missing api key! Get it from our server at api.loopy5418.dev/support. Add 'api_key' parameter to your request body.", "success": False})
    if not checkapikey(apikey):
        return jsonify({"error": "Invalid API key", "success": False}), 403
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
    apikey = request.args.get("key")
    if not apikey:
        return jsonify({"error": "Missing api key! Get it from our server at api.loopy5418.dev/support. Example: ?key=api_key_here", "success": False})
    if not checkapikey(apikey):
        return jsonify({"error": "Invalid API key", "success": False}), 403
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
    apikey = request.args.get("key")
    if not apikey:
        return jsonify({"error": "Missing api key! Get it from our server at api.loopy5418.dev/support. Example: ?key=apikeyhere", "success": False})
    if not checkapikey(apikey):
        return jsonify({"error": "Invalid API key", "success": False}), 403
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

import subprocess

@app.route("/admin/evaluate", methods=["POST"])
def admin_evaluate():
    key = request.headers.get("X-API-KEY")
    allowed_keys = os.environ.get("ADMIN_API_KEYS", "").split(",")
    if key not in allowed_keys:
        abort(403, description="Forbidden: Invalid API key")

    cmd = request.json.get("cmd")
    if not cmd:
        return jsonify({"error": "Missing 'cmd' in request body.", "success": False}), 400

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        return jsonify({
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "success": result.returncode == 0
        })
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500

@app.route("/try/webhook")
def try_webhook():
    return render_template("try/webhook.html")


@app.route("/try/qr")
def try_qr():
    return render_template("try/qr.html")

@app.route("/try/encrypt")
def try_encrypt():
    return render_template("try/encrypt.html")


@app.route("/try/image")
def try_image():
    return render_template("try/image.html")

@app.route("/reverse")
def reverse():
    text = request.args.get("text")
    if not text:
        return jsonify({"error": "Missing 'text' query parameter.", "success": False}), 400
    return jsonify({"result": text[::-1], "success": True})

@app.route('/generate-password', methods=['GET'])
def generate_password():
    try:
        length = int(request.args.get('length', 12))
        if length < 4 or length > 128:
            return jsonify({"error": "Length must be between 4 and 128", "success": False}), 400
    except ValueError:
        return jsonify({"error": "Invalid length parameter", "success": Falsr}), 400

    charset = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.choices(charset, k=length))
    
    return jsonify({
        "length": length,
        "password": password,
        "success": True
    })
    
@app.route('/convert-timezone', methods=['GET'])
def convert_timezone():
    from_tz = request.args.get('from')
    to_tz = request.args.get('to')
    time_str = request.args.get('time')
    if not from_tz:
        return jsonify({"error": "Missing 'from' parameter. Example: ?from=UTC", "success": False}), 400
    if not time_str:
        return jsonify({"error": "Missing 'time' parameter. Example: ?time=16:00", "success": False}), 400
    if not to_tz:
        return jsonify({"error": "Missing 'to' parameter. Example: ?to=Asia/Tokyo", "success": False}), 400

    try:
        naive_time = datetime.strptime(time_str, "%H:%M")
        now = datetime.now()
        aware_time = datetime(
            now.year, now.month, now.day,
            naive_time.hour, naive_time.minute,
            tzinfo=ZoneInfo(from_tz)
        )
        converted_time = aware_time.astimezone(ZoneInfo(to_tz))

        return jsonify({
            "from": from_tz,
            "to": to_tz,
            "original_time": aware_time.strftime("%Y-%m-%d %H:%M %Z"),
            "converted_time": converted_time.strftime("%Y-%m-%d %H:%M %Z"),
            "success": True
        })

    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 400
        
@app.route('/sqrt')
def sqrt():
    try:
        num_str = request.args.get('number', '')
        if num_str == '':
            return jsonify({'success': False, 'error': 'Missing number parameter'}), 400

        num = float(num_str)
        if num < 0:
            return jsonify({'success': False, 'error': 'Cannot take square root of a negative number'}), 400

        result = math.sqrt(num)
        return jsonify({'success': True, 'number': num, 'sqrt': result})

    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid number provided'}), 400
        
@app.route('/cbrt')
def cube_root():
    try:
        num_str = request.args.get('number', '')
        if num_str == '':
            return jsonify({'success': False, 'error': 'Missing number parameter'}), 400

        num = float(num_str)
        result = num ** (1.0 / 3.0)

        # Handle cube root of negative numbers correctly
        if num < 0:
            result = -(-num) ** (1.0 / 3.0)

        return jsonify({'success': True, 'number': num, 'cbrt': result})

    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid number provided'}), 400
        
@app.route('/ascii-art', methods=['GET'])
def ascii_art():
    text = request.args.get('text', '')
    if not text:
        return jsonify({'success': False, 'error': 'Missing text parameter'}), 400

    try:
        ascii_output = pyfiglet.figlet_format(text)
        return jsonify({'success': True, 'ascii_art': ascii_output})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
        
@app.route('/ai/gpt-4o', methods=['GET'])
def gpt4o():
    text = request.args.get("prompt")
    websearch = request.args.get("web_search", False)
    apikey = request.args.get("key")
    if not apikey:
        return jsonify({"error": "Missing api key! Get it from our server at api.loopy5418.dev/support. Example: ?key=apikeyhere", "success": False})
    if not checkapikey(apikey):
        return jsonify({"error": "Invalid API key", "success": False}), 403
    if not text:
        return jsonify({"error": "Missing 'prompt' parameter", "success": False})
    try:
        r = gptc.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": text}],
            web_search=websearch
        )
        return jsonify({"response": r.choices[0].message.content, "success": True, "prompt": text})
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500

@app.route('/ai', methods=['GET'])
def ai():
    text = request.args.get("prompt")
    websearch = request.args.get("web_search", "false")
    apikey = request.args.get("key")
    modelreq = request.args.get("model")
    if not apikey:
        return jsonify({"error": "Missing api key! Get it from our server at api.loopy5418.dev/support. Example: ?key=apikeyhere", "success": False})
    if not checkapikey(apikey):
        return jsonify({"error": "Invalid API key", "success": False}), 403
    if not text:
        return jsonify({"error": "Missing 'prompt' parameter", "success": False})
    if not modelreq:
        return jsonify({"error": "Missing 'model' parameter", "success": False})
    if websearch.lower() == "true":
        websearch = True
    elif websearch.lower() == "false":
        websearch = False
    else:
        return jsonify({"error": "Invalid 'web_search' value. Must be 'true' or 'false'", "success": False}), 400
    try:
        r = gptc.chat.completions.create(
            model=modelreq,
            messages=[
                {"role": "system", "content": "You are an AI service in an API called 'api.loopy5418.dev'. The API owner is Loopy5418. Refrain from providing data that is guessed. Refrain from any political, nsfw, or innapropiate question. Do what the user says, thank you." },
                {"role": "user", "content": text}
            ],
            web_search=websearch
        )
        return jsonify({"response": r.choices[0].message.content, "success": True, "prompt": text, "model": modelreq})
    except Exception as e:
        error_msg = str(e)
        not_found_msg = f"Model {modelreq} not found in any provider."
        if error_msg == not_found_msg:
            return jsonify({
                "error": "That model doesn't exist, or is unavailable at the moment. See the supported models in the docs.",
                "success": False
            }), 400
        else:
            return jsonify({
                "error": error_msg,
                "success": False
            }), 500

@app.route('/roblox-user-search', methods=['GET'])
def roblox_user_search():
    username = request.args.get('username')
    apikey = request.args.get("key")
    if not apikey:
        return jsonify({"error": "Missing api key! Get it from our server at api.loopy5418.dev/support. Example: ?key=apikeyhere", "success": False})
    if not checkapikey(apikey):
        return jsonify({"error": "Invalid API key", "success": False}), 403
    if not username:
        return jsonify({"error": "Missing 'username' parameter", "success": False}), 400

    roproxy_url = f"https://users.roproxy.com/v1/users/search?keyword={username}&limit=25"

    try:
        response = requests.get(roproxy_url)
        response.raise_for_status()
        data = response.json()

        results = data.get("data", [])
        return jsonify({
            "results": results,
            "total": len(results),
            "success": True
        })

    except requests.RequestException as e:
        return jsonify({"error": "Failed to fetch data from Roblox servers: str(e)", "success": False}), 500
        

@app.route('/roblox-user-info', methods=['GET'])
def roblox_user_info():
    apikey = request.args.get("key")
    if not apikey: # 1000th line!!!
        return jsonify({
            "error": "Missing API key! Get it from our server at api.loopy5418.dev/support. Example: ?key=apikeyhere",
            "success": False
        }), 400

    if not checkapikey(apikey):
        return jsonify({
            "error": "Invalid API key",
            "success": False
        }), 403

    username = request.args.get('username')
    user_id = request.args.get('user_id')

    if (username and user_id) or (not username and not user_id):
        return jsonify({
            "error": "Provide either 'username' or 'user_id', but not both",
            "success": False
        }), 400

    # Step 1: Get user_id from username if needed
    if username:
        try:
            search_url = f"https://users.roproxy.com/v1/users/search?keyword={username}&limit=25"
            search_response = requests.get(search_url)
            search_response.raise_for_status()
            search_data = search_response.json().get("data", [])
            if not search_data:
                return jsonify({"error": "User not found", "success": False}), 404
            user_id = search_data[0]["id"]
        except requests.RequestException as e:
            return jsonify({
                "error": "Failed to search user",
                "success": False
            }), 500

    # Step 2: Fetch user info
    headers = {
        "x-api-key": os.environ.get("ROBLOX_API_KEY", "")
    }

    if not headers["x-api-key"]:
        return jsonify({
            "error": "ROBLOX_API_KEY not set in environment",
            "success": False
        }), 500

    try:
        user_info_url = f"https://users.roproxy.com/v1/users/{user_id}"
        user_info_response = requests.get(user_info_url, headers=headers)
        user_info_response.raise_for_status()
        user_data = user_info_response.json()

        # Format "created" timestamp
        created_raw = user_data.get("created")
        if created_raw:
            try:
                dt = datetime.strptime(created_raw, "%Y-%m-%dT%H:%M:%S.%fZ")
                user_data["created"] = {
                    "day": dt.day,
                    "year": dt.year,
                    "month": dt.strftime("%B"),
                    "date": dt.strftime("%B %d, %Y"),
                    "time": dt.strftime("%H:%M")
                }
            except ValueError:
                user_data["created"] = {
                    "raw": created_raw,
                    "error": "Invalid date format"
                }

        # Step 3: Fetch profile picture
        thumb_url = f"https://apis.roproxy.com/cloud/v2/users/{user_id}:generateThumbnail?size=100&format=PNG&shape=ROUND"
        thumb_response = requests.get(thumb_url, headers=headers)
        if thumb_response.ok:
            thumb_data = thumb_response.json()
            user_data["profile_picture_url"] = thumb_data.get("response", {}).get("imageUri")

        user_data["success"] = True
        return jsonify(user_data)

    except requests.RequestException as e:
        return jsonify({
            "error": "Failed to fetch user info",
            "success": False
        }), 500
        
@app.route('/try/roblox-user-search')
def robloxsearchtry():
    return render_template('try/r-user-search.html')
    
@app.route('/try/roblox-search-info')
def robloxsearchinfotry():
    return render_template('try/user-info.html')

@app.route('/parse-iso8601', methods=['GET'])
def parse_timestamp():
    iso_timestamp = request.args.get('timestamp')

    if not iso_timestamp:
        return jsonify({"success": False, "error": "Missing 'timestamp' query parameter"}), 400

    try:
        dt = parser.isoparse(iso_timestamp)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)

        dt = dt.astimezone(pytz.UTC)

        formatted = {
            "success": True,
            "year": dt.year,
            "leap_year": calendar.isleap(dt.year),
            "month": {
                "number": dt.month,
                "name": dt.strftime("%B")
            },
            "day": dt.day,
            "weekday": dt.strftime("%A"),
            "time": {
                "hour": dt.hour,
                "minute": dt.minute,
                "second": dt.second
            },
            "timezone": dt.tzname(),
            "utc_offset": dt.strftime("%z")
        }

        return jsonify(formatted)

    except ValueError:
        return jsonify({"success": False, "error": "Invalid ISO 8601 timestamp format"}), 400
        
@app.route('/attachment-get', methods=['GET'])
def attachment_get():
    bot_token = request.args.get('bot_token')
    message_id = request.args.get('message_id')
    channel_id = request.args.get('channel_id')
    apikey = request.args.get("key")
    if not apikey:
        return jsonify({
            "error": "Missing API key! Get it from our server at api.loopy5418.dev/support. Example: ?key=apikeyhere",
            "success": False
        }), 400
    if not checkapikey(apikey):
        return jsonify({
            "error": "Invalid API key",
            "success": False
        }), 403

    if not all([bot_token, message_id, channel_id]):
        return jsonify({'success': False, 'error': 'Missing query parameters'}), 400

    try:
        message_id = int(message_id)
        channel_id = int(channel_id)
    except ValueError:
        return jsonify({'success': False, 'error': 'message_id and channel_id must be integers'}), 400

    try:
        data = run_async(fetch_message_attachments(bot_token, channel_id, message_id))
        return jsonify(data)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
        

@app.route('/yt-search', methods=['GET'])
def search_youtube():
    query = request.args.get('query')
    limit = int(request.args.get('limit', 5))
    if not isinstance(limit, (int, float)):
        return jsonify({"error": "Limit parameter needs to be a number"}), 400
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400

    try:
        videos_search = VideosSearch(query, limit=limit)
        results = videos_search.result()

        videos = [
            {
                'title': v['title'],
                'url': v['link'],
                'duration': v['duration'],
                'views': v['viewCount']['short'],
                'channel': v['channel']['name'],
                'thumbnails': v['thumbnails']
            }
            for v in results['result']
        ]
        return jsonify(videos)

    except Exception as e:
        return jsonify({"error": str(e)}), 500