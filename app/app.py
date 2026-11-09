import time
from flask import Flask, jsonify

START_TIME = time.time()

app = Flask(__name__)


@app.get("/health/live")
def health_live():
    return jsonify(status="ok", uptime=round(time.time() - START_TIME))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)