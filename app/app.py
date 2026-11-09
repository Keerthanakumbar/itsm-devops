import os
import time
from datetime import datetime, timezone

from flask import Flask, jsonify, request
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

# --- Helpers ---
def error(message, status):
    return jsonify(error=message), status


def parse_id(raw_id):
    """Return the id as int, or None if it is not a valid number."""
    return int(raw_id) if raw_id.isdigit() else None


def read_name_from_body():
    """Return (clean_name, error_response)."""
    body = request.get_json(silent=True) or {}
    name = body.get("name")
    if not isinstance(name, str) or name.strip() == "":
        return None, error("name is required", 400)
    name = name.strip()
    if len(name) > 100:
        return None, error("name must be 100 characters or fewer", 400)
    return name, None


# --- CRUD: /api/names ---
@app.get("/api/names")
def list_names():
    names = Name.query.order_by(Name.created_at.desc(), Name.id.desc()).all()
    return jsonify([n.to_dict() for n in names])


@app.post("/api/names")
def create_name():
    name, err = read_name_from_body()
    if err:
        return err
    new = Name(name=name)
    db.session.add(new)
    db.session.commit()
    return jsonify(new.to_dict()), 201


@app.put("/api/names/<raw_id>")
def update_name(raw_id):
    name_id = parse_id(raw_id)
    if name_id is None:
        return error("id is not a valid identifier", 400)
    name, err = read_name_from_body()
    if err:
        return err
    row = db.session.get(Name, name_id)
    if row is None:
        return error("name not found", 404)
    row.name = name
    db.session.commit()
    return jsonify(row.to_dict())


@app.delete("/api/names/<raw_id>")
def delete_name(raw_id):
    name_id = parse_id(raw_id)
    if name_id is None:
        return error("id is not a valid identifier", 400)
    row = db.session.get(Name, name_id)
    if row is None:
        return error("name not found", 404)
    db.session.delete(row)
    db.session.commit()
    return "", 204


# --- Errors: same JSON shape as the old Node.js app ---
@app.errorhandler(404)
@app.errorhandler(405)
def not_found(_err):
    return error("route not found", 404)


@app.errorhandler(500)
def server_error(_err):
    return error("internal server error", 500)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
