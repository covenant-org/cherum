from flask import Flask, render_template, request

app = Flask(__name__)


@app.route("/health")
def health():
    return "OK"


@app.route("/", ["GET", "POST"])
def index():
    if request.method == "POST":
        return "Hello, World!"
    return render_template("template/index.html", last_connection="Never")
