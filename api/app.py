from flask import Flask, Response, jsonify, request, render_template

from .errors import errors

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
