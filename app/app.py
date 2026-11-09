import os
import time
from datetime import datetime, timezone

from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

START_TIME = time.time()

# --- Database settings (read from environment variables, with local defaults) ---
DB_USER = os.getenv("DB_USER", "appuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "apppass")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "namelist")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
# Check the connection is still alive before using it
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}

db = SQLAlchemy(app)


def utcnow():
    return datetime.now(timezone.utc)


# --- The "names" table ---
class Name(db.Model):
    __tablename__ = "names"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }


# --- Create the table at startup, retrying while the database boots ---
def init_db(attempts=10, wait_seconds=3):
    for attempt in range(1, attempts + 1):
        try:
            with app.app_context():
                db.create_all()
            print("[db] connected, table ready")
            return
        except Exception as err:
            if attempt == attempts:
                raise
            print(f"[db] attempt {attempt}/{attempts} failed: {err} - retrying in {wait_seconds}s")
            time.sleep(wait_seconds)


init_db()


# --- Health checks ---
@app.get("/health/live")
def health_live():
    return jsonify(status="ok", uptime=round(time.time() - START_TIME))


@app.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db.session.rollback()
        db_ok = False

    body = {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "uptime": round(time.time() - START_TIME),
    }
    return jsonify(body), (200 if db_ok else 503)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
