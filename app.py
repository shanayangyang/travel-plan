from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flask import Flask, abort, g, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "travel_plan.sqlite"

app = Flask(__name__)


@dataclass
class DaySummary:
    day_number: int
    items: list[dict[str, Any]]
    total: float


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(exception: Exception | None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            days INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS day_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL,
            day_number INTEGER NOT NULL,
            title TEXT NOT NULL,
            map_link TEXT,
            expense_name TEXT,
            expense_amount REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE
        )
        """
    )
    conn.commit()
    conn.close()


def fetch_trip(trip_id: int) -> sqlite3.Row:
    trip = get_db().execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()
    if trip is None:
        abort(404)
    return trip


def build_day_summaries(trip_id: int, days: int) -> list[DaySummary]:
    rows = get_db().execute(
        """
        SELECT * FROM day_items
        WHERE trip_id = ?
        ORDER BY day_number ASC, id DESC
        """,
        (trip_id,),
    ).fetchall()
    items_by_day: dict[int, list[dict[str, Any]]] = {day: [] for day in range(1, days + 1)}
    for row in rows:
        items_by_day[row["day_number"]].append(dict(row))

    summaries: list[DaySummary] = []
    for day_number in range(1, days + 1):
        items = items_by_day.get(day_number, [])
        total = sum(item["expense_amount"] or 0 for item in items)
        summaries.append(DaySummary(day_number=day_number, items=items, total=total))
    return summaries


def calculate_trip_total(trip_id: int) -> float:
    row = get_db().execute(
        "SELECT COALESCE(SUM(expense_amount), 0) AS total FROM day_items WHERE trip_id = ?",
        (trip_id,),
    ).fetchone()
    return float(row["total"] or 0)


@app.route("/")
def landing() -> str:
    return render_template("landing.html")


@app.route("/v<int:version>")
def list_trips(version: int) -> str:
    if version not in (1, 2, 3):
        abort(404)
    trips = get_db().execute(
        "SELECT * FROM trips ORDER BY created_at DESC, id DESC"
    ).fetchall()
    return render_template(f"v{version}/index.html", trips=trips, version=version)


@app.route("/v<int:version>/trips", methods=["POST"])
def create_trip(version: int) -> str:
    if version not in (1, 2, 3):
        abort(404)
    name = request.form.get("name", "").strip()
    days = int(request.form.get("days", "0") or 0)
    if not name or days <= 0:
        abort(400)
    cursor = get_db().execute(
        "INSERT INTO trips (name, days) VALUES (?, ?)",
        (name, days),
    )
    get_db().commit()
    return redirect(url_for("view_trip", version=version, trip_id=cursor.lastrowid))


@app.route("/v<int:version>/trips/<int:trip_id>")
def view_trip(version: int, trip_id: int) -> str:
    if version not in (1, 2, 3):
        abort(404)
    trip = fetch_trip(trip_id)
    summaries = build_day_summaries(trip_id, trip["days"])
    trip_total = calculate_trip_total(trip_id)
    return render_template(
        f"v{version}/trip.html",
        version=version,
        trip=trip,
        summaries=summaries,
        trip_total=trip_total,
    )


@app.route("/v<int:version>/trips/<int:trip_id>/edit", methods=["POST"])
def edit_trip(version: int, trip_id: int) -> str:
    if version not in (1, 2, 3):
        abort(404)
    fetch_trip(trip_id)
    name = request.form.get("name", "").strip()
    days = int(request.form.get("days", "0") or 0)
    if not name or days <= 0:
        abort(400)
    get_db().execute(
        "UPDATE trips SET name = ?, days = ? WHERE id = ?",
        (name, days, trip_id),
    )
    get_db().commit()
    return redirect(url_for("view_trip", version=version, trip_id=trip_id))


@app.route("/v<int:version>/trips/<int:trip_id>/delete", methods=["POST"])
def delete_trip(version: int, trip_id: int) -> str:
    if version not in (1, 2, 3):
        abort(404)
    get_db().execute("DELETE FROM trips WHERE id = ?", (trip_id,))
    get_db().commit()
    return redirect(url_for("list_trips", version=version))


@app.route("/v<int:version>/trips/<int:trip_id>/items", methods=["POST"])
def add_item(version: int, trip_id: int) -> str:
    if version not in (1, 2, 3):
        abort(404)
    trip = fetch_trip(trip_id)
    day_number = int(request.form.get("day_number", "0") or 0)
    if day_number < 1 or day_number > trip["days"]:
        abort(400)
    title = request.form.get("title", "").strip()
    if not title:
        abort(400)
    map_link = request.form.get("map_link", "").strip() or None
    expense_name = request.form.get("expense_name", "").strip() or None
    expense_amount = float(request.form.get("expense_amount", "0") or 0)
    get_db().execute(
        """
        INSERT INTO day_items (trip_id, day_number, title, map_link, expense_name, expense_amount)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (trip_id, day_number, title, map_link, expense_name, expense_amount),
    )
    get_db().commit()
    return redirect(url_for("view_trip", version=version, trip_id=trip_id))


@app.route("/v<int:version>/trips/<int:trip_id>/items/<int:item_id>/delete", methods=["POST"])
def delete_item(version: int, trip_id: int, item_id: int) -> str:
    if version not in (1, 2, 3):
        abort(404)
    fetch_trip(trip_id)
    get_db().execute("DELETE FROM day_items WHERE id = ?", (item_id,))
    get_db().commit()
    return redirect(url_for("view_trip", version=version, trip_id=trip_id))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8000, debug=True)
