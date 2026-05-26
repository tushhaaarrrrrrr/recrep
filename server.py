import os
import sys
import time
import asyncio
import threading
import subprocess
import psutil
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, render_template
from flask_socketio import SocketIO, emit

from services.db_service import DBService
from database.connection import init_db_pool, close_db_pool
from utils.logger import get_logger

from dotenv import load_dotenv
load_dotenv()

BOT_SCRIPT    = "main.py"
PID_FILE      = "bot.pid"
READY_FILE    = "bot.ready"
LOG_FILE      = "bot.log"
VENV_PYTHON   = sys.executable

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

logger = get_logger(__name__)

# ── Threading lock ─────────────────────────
_start_lock = threading.Lock()

# ── Async event loop ──────────────────────────────────────────────────────────
_db_pool = None
_event_loop = None
_pool_ready = threading.Event()
_pool_init_error = None

async def _init_global_pool():
    global _db_pool, _pool_init_error
    try:
        _db_pool = await init_db_pool()
    except Exception as exc:
        _pool_init_error = exc
        _db_pool = None
        logger.exception("Database pool initialisation failed")
    finally:
        _pool_ready.set()

def _start_async_loop():
    global _event_loop
    _event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_event_loop)
    try:
        _event_loop.run_until_complete(_init_global_pool())
    finally:
        _event_loop.run_forever()

def run_async(coro):
    if _event_loop is None:
        raise RuntimeError("Async loop not started")
    return asyncio.run_coroutine_threadsafe(coro, _event_loop).result(timeout=30)

_loop_thread = threading.Thread(target=_start_async_loop, daemon=True)
_loop_thread.start()
# Wait properly for the pool to be ready
if not _pool_ready.wait(timeout=30):
    raise RuntimeError("Database pool did not initialise within 30 seconds")
if _pool_init_error is not None:
    raise RuntimeError(f"Database pool initialisation failed: {_pool_init_error}") from _pool_init_error

# ── Bot process management ────────────────────────────────────────────────────
def _get_bot_process():
    if not os.path.exists(PID_FILE):
        return None
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        proc = psutil.Process(pid)
        cmdline = proc.cmdline()
        if not cmdline:
            raise psutil.NoSuchProcess(pid)
        if len(cmdline) >= 2 and BOT_SCRIPT in cmdline[1]:
            return proc
        os.remove(PID_FILE)
        return None
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, FileNotFoundError, ProcessLookupError):
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        return None

def _find_bot_process():
    """Return psutil.Process if *any* running process looks like our bot."""
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and len(cmdline) >= 2 and BOT_SCRIPT in cmdline[1]:
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None

def _ensure_pid_file(proc):
    try:
        with open(PID_FILE, "w") as f:
            f.write(str(proc.pid))
    except Exception:
        pass

def get_bot_status():
    # First try the PID file
    proc = _get_bot_process() if os.path.exists(PID_FILE) else None
    if proc is None:
        # Fallback to process scan
        proc = _find_bot_process()
        if proc is not None:
            _ensure_pid_file(proc)

    if proc is None:
        if os.path.exists(READY_FILE):
            try:
                os.remove(READY_FILE)
            except OSError:
                pass
        return {"running": False, "pid": None, "uptime": None}

    # Also check whether the bot is actually connected to Discord
    connected = os.path.exists(READY_FILE)
    if not connected:
        return {"running": True, "pid": proc.pid, "uptime": "...", "connected": False}

    secs   = int(time.time() - proc.create_time())
    uptime = f"{secs//86400}d {(secs%86400)//3600}h {(secs%3600)//60}m {secs%60}s"
    return {"running": True, "pid": proc.pid, "uptime": uptime, "connected": True}

def start_bot():
    acquired = _start_lock.acquire(blocking=False)
    if not acquired:
        return False, "Bot is already starting or running."

    try:
        existing = _find_bot_process()
        if existing:
            _ensure_pid_file(existing)
            return False, "Bot is already running."

        log_file = open(LOG_FILE, "a")
        try:
            proc = subprocess.Popen(
                [VENV_PYTHON, BOT_SCRIPT],
                stdout=log_file, stderr=subprocess.STDOUT,
                start_new_session=True
            )
        finally:
            log_file.close()

        with open(PID_FILE, "w") as f:
            f.write(str(proc.pid))
        return True, f"Bot started (PID {proc.pid})"
    finally:
        _start_lock.release()

def stop_bot():
    proc = _get_bot_process() if os.path.exists(PID_FILE) else None
    if proc is None:
        proc = _find_bot_process()

    if proc is None:
        return False, "Bot is not running."

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except psutil.TimeoutExpired:
        proc.kill()

    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
    if os.path.exists(READY_FILE):
        os.remove(READY_FILE)
    return True, "Bot stopped."

def restart_bot():
    ok, msg = stop_bot()
    if not ok and "not running" not in msg:
        return False, f"Stop failed: {msg}"
    time.sleep(2)
    return start_bot()

def reset_bot():
    stop_bot()
    try:
        subprocess.run([VENV_PYTHON, "reset_db.py"], check=True)
        subprocess.run([VENV_PYTHON, "reset_s3.py"], check=True)
    except subprocess.CalledProcessError as e:
        return False, f"Reset failed: {e}"
    return start_bot()

# ── Watchdog thread ────────────────────────
def _watchdog_thread():
    """Check bot health every 300 seconds, restart if dead."""
    while True:
        time.sleep(300)
        if not _find_bot_process():
            logger.warning("Bot process missing - watchdog restarting.")
            start_bot()

_watchdog = threading.Thread(target=_watchdog_thread, daemon=True)
_watchdog.start()

# ── Data helpers ──────────────────────────────────────────────────────────────
FORM_TABLES = [
    "recruitment", "progress_report", "purchase_invoice", "mall_shop", "supplier",
    "demolition_report", "eviction_report", "scroll_completion",
]

# Discord IDs are 64-bit integers that exceed JS Number.MAX_SAFE_INTEGER.
# Always serialise them as strings so the browser never silently corrupts them.
_DISCORD_ID_FIELDS = {"submitted_by", "approved_by", "discord_id", "staff_id"}

def _serialize_row(row):
    d = {}
    for k in row.keys():
        v = row[k]
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
        elif v is None:
            d[k] = None
        elif k in _DISCORD_ID_FIELDS and isinstance(v, int):
            # Stringify so JS JSON.parse() doesn't lose precision
            d[k] = str(v)
        else:
            d[k] = v
    return d

async def async_get_overview():
    approved_counts, pending_counts = {}, {}
    total_approved = total_pending = 0
    for table in FORM_TABLES:
        r_a = await DBService.fetchrow(f"SELECT COUNT(*) FROM {table} WHERE status='approved'")
        r_p = await DBService.fetchrow(f"SELECT COUNT(*) FROM {table} WHERE status='pending'")
        a, p = (r_a[0] if r_a else 0), (r_p[0] if r_p else 0)
        approved_counts[table], pending_counts[table] = a, p
        total_approved += a
        total_pending  += p
    r_rep   = await DBService.fetchrow("SELECT COALESCE(SUM(reputation),0) FROM staff_member")
    r_staff = await DBService.fetchrow("SELECT COUNT(*) FROM staff_member")
    return {
        "totals": {
            "approved_total":   total_approved,
            "pending_total":    total_pending,
            "reputation_total": r_rep[0] if r_rep else 0,
            "staff_total":      r_staff[0] if r_staff else 0,
        },
        "approved_breakdown": approved_counts,
        "pending_breakdown":  pending_counts,
    }

async def async_get_activity(limit=30):
    activities = []
    for table in FORM_TABLES:
        rows = await DBService.fetch(
            f"SELECT id, submitted_by, submitted_at, status FROM {table} "
            f"ORDER BY submitted_at DESC LIMIT $1", limit
        )
        for row in rows:
            activities.append({
                "table":        table,
                "id":           row["id"],
                "submitted_by": str(row["submitted_by"]),   # always string
                "submitted_at": row["submitted_at"].isoformat(),
                "status":       row["status"],
            })
    activities.sort(key=lambda x: x["submitted_at"], reverse=True)
    return activities[:limit]

async def async_get_activity_timeseries(granularity: str):
    granularity = granularity.lower()
    if granularity not in {"daily", "weekly", "monthly"}:
        granularity = "weekly"

    if granularity == "daily":
        span, label_fn = 7, lambda i: "Today" if i == 0 else f"{i}d ago"
        bounds = lambda i: (f"CURRENT_DATE - INTERVAL '{i} day'", f"CURRENT_DATE - INTERVAL '{i-1} day'")
    elif granularity == "monthly":
        span, label_fn = 6, lambda i: "This month" if i == 0 else f"{i}mo ago"
        bounds = lambda i: (f"date_trunc('month',CURRENT_DATE) - INTERVAL '{i} month'", f"date_trunc('month',CURRENT_DATE) - INTERVAL '{i-1} month'")
    else:
        span, label_fn = 8, lambda i: "This week" if i == 0 else f"{i}w ago"
        bounds = lambda i: (f"date_trunc('week',CURRENT_DATE) - INTERVAL '{i} week'", f"date_trunc('week',CURRENT_DATE) - INTERVAL '{i-1} week'")

    labels = []
    periods = []
    for i in range(span - 1, -1, -1):
        labels.append(label_fn(i))
        periods.append(bounds(i))

    series = {k: [] for k in [
        "recruitment", "progress_report", "progress_help",
        "purchase_invoice", "mall_shop", "demolition_report", "eviction_report",
        "scroll_completion", "reputation"
    ]}

    # Build every query coroutine up-front, then fire them all concurrently.
    # Previously these were sequential awaits (64 round-trips for weekly),
    # which reliably exceeded the 30-second timeout.
    all_coros = []
    for start_expr, end_expr in periods:
        for t in FORM_TABLES:
            all_coros.append(DBService.fetchrow(
                f"SELECT COUNT(*) FROM {t} WHERE status='approved' "
                f"AND submitted_at >= {start_expr} AND submitted_at < {end_expr}"
            ))
        all_coros.append(DBService.fetchrow(
            f"SELECT COUNT(*) FROM reputation_log WHERE form_type='progress_help' "
            f"AND created_at >= {start_expr} AND created_at < {end_expr}"
        ))
        all_coros.append(DBService.fetchrow(
            f"SELECT COALESCE(SUM(points),0) FROM reputation_log "
            f"WHERE created_at >= {start_expr} AND created_at < {end_expr}"
        ))

    results = await asyncio.gather(*all_coros)

    # Unpack results in the same order the coroutines were appended.
    queries_per_period = len(FORM_TABLES) + 2  # 6 form tables + progress_help + reputation
    for period_idx in range(span):
        base = period_idx * queries_per_period
        for t_idx, t in enumerate(FORM_TABLES):
            r = results[base + t_idx]
            series[t].append(r[0] if r else 0)
        r_h = results[base + len(FORM_TABLES)]
        series["progress_help"].append(r_h[0] if r_h else 0)
        r_rep = results[base + len(FORM_TABLES) + 1]
        series["reputation"].append(r_rep[0] if r_rep else 0)

    return {"labels": labels, "series": series}

async def async_get_leaderboard(category, period):
    category, period = category.lower(), period.lower()
    rows = await (
        DBService.get_leaderboard(period)
        if category == "reputation"
        else DBService.get_category_leaderboard(category, period)
    )
    staff_rows = await DBService.fetch("SELECT discord_id, display_name FROM staff_member")
    names = {str(r["discord_id"]): (r["display_name"] or "") for r in staff_rows}
    return [dict(r) | {"display_name": names.get(str(r["discord_id"]), ""), "discord_id": str(r["discord_id"])} for r in rows]

async def async_get_staff_directory():
    rows = await DBService.fetch(
        "SELECT discord_id, display_name, reputation FROM staff_member ORDER BY reputation DESC"
    )

    staff_map = {}
    for row in rows:
        sid = str(row["discord_id"])
        raw = row.get("display_name") or ""
        label = raw if raw else (f"User {sid[:4]}…{sid[-4:]}" if len(sid) > 8 else f"User {sid}")
        staff_map[sid] = {
            "discord_id": sid, "label": label, "reputation": row["reputation"],
            "recruitment": 0, "progress_report": 0, "progress_help": 0,
            "purchase_invoice": 0, "mall_shop": 0, "supplier": 0, "demolition_report": 0, "eviction_report": 0,
            "scroll_completion": 0, "approvals": 0, "roles": [],
        }

    for table in FORM_TABLES:
        rows = await DBService.fetch(
            f"SELECT submitted_by, COUNT(*) as cnt FROM {table} WHERE status='approved' GROUP BY submitted_by"
        )
        for r in rows:
            sid = str(r["submitted_by"])
            staff_map.setdefault(sid, {
                "discord_id": sid, "label": f"User {sid}", "reputation": 0,
                "recruitment": 0, "progress_report": 0, "progress_help": 0,
                "purchase_invoice": 0, "mall_shop": 0, "supplier": 0, "demolition_report": 0, "eviction_report": 0,
                "scroll_completion": 0, "approvals": 0, "roles": [],
            })
            staff_map[sid][table] = r["cnt"]

    rows = await DBService.fetch(
        "SELECT staff_id, COUNT(*) as cnt FROM reputation_log WHERE form_type='progress_help' GROUP BY staff_id"
    )
    for r in rows:
        sid = str(r["staff_id"])
        if sid in staff_map:
            staff_map[sid]["progress_help"] = r["cnt"]

    for table in FORM_TABLES:
        rows = await DBService.fetch(
            f"SELECT approved_by, COUNT(*) as cnt FROM {table} "
            f"WHERE status='approved' AND approved_by IS NOT NULL GROUP BY approved_by"
        )
        for r in rows:
            sid = str(r["approved_by"])
            if sid in staff_map:
                staff_map[sid]["approvals"] += r["cnt"]

    sids = list(staff_map.keys())
    role_tasks = [DBService.get_user_roles(int(sid)) for sid in sids]
    role_results = await asyncio.gather(*role_tasks, return_exceptions=True)

    for sid, roles in zip(sids, role_results):
        staff_map[sid]["roles"] = roles if not isinstance(roles, Exception) else []

    return sorted(staff_map.values(), key=lambda x: x["reputation"], reverse=True)

async def async_get_user_history(discord_id_str: str):
    try:
        discord_id_int = int(discord_id_str)
    except (TypeError, ValueError):
        return {"history": [], "counts": {}, "error": "Invalid user ID"}
    history, counts = [], {}
    for table in FORM_TABLES:
        try:
            rows = await DBService.fetch(
                f"SELECT id, submitted_at, status FROM {table} "
                f"WHERE submitted_by = $1::bigint ORDER BY submitted_at DESC",
                discord_id_int
            )
        except Exception as e:
            logger.error(f"Error querying {table} for {discord_id_int}: {e}")
            rows = []
        for row in rows:
            history.append({
                "table":        table,
                "id":           row["id"],
                "submitted_at": row["submitted_at"].isoformat(),
                "status":       row["status"],
            })
        try:
            r = await DBService.fetchrow(
                f"SELECT COUNT(*) FROM {table} WHERE submitted_by = $1::bigint", discord_id_int
            )
            counts[table] = r[0] if r else 0
        except Exception as e:
            logger.error(f"Error counting {table} for {discord_id_int}: {e}")
            counts[table] = 0
    history.sort(key=lambda x: x["submitted_at"], reverse=True)
    return {"history": history, "counts": counts}

async def async_get_monthly_records(year_month: str):
    try:
        parts = year_month.split('-')
        year, month = int(parts[0]), int(parts[1])
    except Exception:
        now = datetime.now(timezone.utc)
        year, month = now.year, now.month
    result = {}
    for table in FORM_TABLES:
        try:
            rows = await DBService.fetch(
                f"SELECT * FROM {table} "
                f"WHERE EXTRACT(YEAR FROM submitted_at) = $1 "
                f"AND EXTRACT(MONTH FROM submitted_at) = $2 "
                f"ORDER BY submitted_at DESC",
                year, month
            )
            result[table] = [_serialize_row(row) for row in rows]
        except Exception as e:
            logger.error(f"Monthly records error for {table}: {e}")
            result[table] = []
    return result

# ── Flask routes ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template('index.html')

@app.route("/api/status")
def api_status():
    return jsonify(get_bot_status())

@app.route("/api/overview")
def api_overview():
    try:
        return jsonify(run_async(async_get_overview()))
    except Exception as e:
        logger.exception("Overview error")
        return jsonify({"error": str(e)}), 500

@app.route("/api/activity")
def api_activity():
    try:
        return jsonify(run_async(async_get_activity(30)))
    except Exception as e:
        logger.exception("Activity error")
        return jsonify({"error": str(e)}), 500

@app.route("/api/activity_timeseries")
def api_activity_timeseries():
    try:
        gran = request.args.get("granularity", "weekly")
        return jsonify(run_async(async_get_activity_timeseries(gran)))
    except Exception as e:
        logger.exception("Timeseries error")
        return jsonify({"error": str(e)}), 500

@app.route("/api/leaderboard/<category>/<period>")
def api_leaderboard(category, period):
    try:
        return jsonify(run_async(async_get_leaderboard(category, period)))
    except Exception as e:
        logger.exception("Leaderboard error")
        return jsonify({"error": str(e)}), 500

@app.route("/api/staff")
def api_staff():
    try:
        return jsonify({"staff": run_async(async_get_staff_directory())})
    except Exception as e:
        logger.exception("Staff error")
        return jsonify({"error": str(e)}), 500

@app.route("/api/form/<string:table>/<int:form_id>")
def api_form_detail(table, form_id):
    try:
        if table not in FORM_TABLES:
            return jsonify({"error": "Invalid table"}), 400
        row = run_async(DBService.fetchrow(f"SELECT * FROM {table} WHERE id = $1", form_id))
        return jsonify(_serialize_row(row) if row else None)
    except Exception as e:
        logger.exception("Form detail error")
        return jsonify({"error": str(e)}), 500

@app.route("/api/user/<discord_id>/history")
def api_user_history(discord_id):
    try:
        return jsonify(run_async(async_get_user_history(discord_id)))
    except Exception as e:
        logger.exception("User history error")
        return jsonify({"error": str(e)}), 500

@app.route("/api/monthly_records")
def api_monthly_records():
    try:
        month = request.args.get("month", datetime.now(timezone.utc).strftime("%Y-%m"))
        return jsonify(run_async(async_get_monthly_records(month)))
    except Exception as e:
        logger.exception("Monthly records error")
        return jsonify({"error": str(e)}), 500

@app.route("/start",   methods=["POST"])
def start():
    ok, msg = start_bot()
    return jsonify({"success": ok, "message": msg})

@app.route("/stop",    methods=["POST"])
def stop():
    ok, msg = stop_bot()
    return jsonify({"success": ok, "message": msg})

@app.route("/restart", methods=["POST"])
def restart():
    ok, msg = restart_bot()
    return jsonify({"success": ok, "message": msg})

@app.route("/reset",   methods=["POST"])
def reset():
    ok, msg = reset_bot()
    return jsonify({"success": ok, "message": msg})

# ── WebSocket live logs ───────────────────────────────────────────────────────
def _log_watcher():
    if not os.path.exists(LOG_FILE):
        open(LOG_FILE, "w").close()
    with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if line:
                socketio.emit("log", {"line": line.strip()})
            else:
                time.sleep(0.3)

@socketio.on("connect")
def handle_connect():
    emit("connected", {"data": "Connected"})
    if not hasattr(app, "_log_thread"):
        app._log_thread = threading.Thread(target=_log_watcher, daemon=True)
        app._log_thread.start()

# ── HTML Template ─────────────────────────────────────────────────────────────


if __name__ == "__main__":
    socketio.run(
        app,
        host  = "0.0.0.0",
        port  = int(os.environ.get("PORT", 5000)),
        debug = False,
    )