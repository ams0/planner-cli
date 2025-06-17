import os
import time
import threading
import requests
import json
from prometheus_client import Gauge, CollectorRegistry, generate_latest
from flask import Flask, Response

SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", 3600))  # seconds, default 1 hour
PORT = int(os.getenv("PROMETHEUS_PORT", 9100))
METRICS_PATH = "/metrics"
PLAN_ID = "".join(os.getenv("PLAN_ID", "").split())  # Remove any extra whitespace
GRAPH_URL = f"https://graph.microsoft.com/v1.0/planner/plans/{PLAN_ID}/tasks"
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("TOKEN environment variable is required.")
    exit(1)

app = Flask(__name__)
registry = CollectorRegistry()

g_completed = Gauge('planner_tasks_completed', 'Number of completed tasks', registry=registry)
g_in_progress = Gauge('planner_tasks_in_progress', 'Number of in-progress tasks', registry=registry)
g_not_started = Gauge('planner_tasks_not_started', 'Number of not started tasks', registry=registry)
g_late = Gauge('planner_tasks_late', 'Number of late tasks', registry=registry)

USER_LOOKUP_FILE = "user_lookup_table.json"
try:
    with open(USER_LOOKUP_FILE, "r") as f:
        USER_LOOKUP = json.load(f)
except Exception as e:
    print(f"Warning: Could not load user lookup table from {USER_LOOKUP_FILE}: {e}")
    USER_LOOKUP = {}

user_gauge = Gauge(
    'planner_user_tasks',
    'Number of tasks per user by status',
    ['user_id', 'username', 'status'],
    registry=registry
)

def fetch_and_update_metrics():
    while True:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        try:
            resp = requests.get(GRAPH_URL, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            completed = 0
            in_progress = 0
            not_started = 0
            late = 0
            now = time.time()
            # Per-user stats
            user_stats = {}
            for task in data.get("value", []):
                percent = task.get("percentComplete", 0)
                due = task.get("dueDateTime")
                is_late = False
                if percent < 100 and due:
                    try:
                        due_ts = time.mktime(time.strptime(due, "%Y-%m-%dT%H:%M:%SZ"))
                        if due_ts < now:
                            is_late = True
                    except Exception:
                        pass
                # Gather all assigned user IDs
                user_ids = set()
                if "assignments" in task:
                    user_ids.update(task["assignments"].keys())
                if "_assignments" in task:
                    user_ids.update(a.get("userId") for a in task["_assignments"] if a.get("userId"))
                if not user_ids:
                    user_ids.add("unassigned")
                for user_id in user_ids:
                    if user_id not in user_stats:
                        user_stats[user_id] = {"completed": 0, "in_progress": 0, "not_started": 0, "late": 0}
                    if percent == 100:
                        user_stats[user_id]["completed"] += 1
                    elif percent == 0:
                        user_stats[user_id]["not_started"] += 1
                    else:
                        user_stats[user_id]["in_progress"] += 1
                    if is_late:
                        user_stats[user_id]["late"] += 1
                # Global stats
                if percent == 100:
                    completed += 1
                elif percent == 0:
                    not_started += 1
                else:
                    in_progress += 1
                if is_late:
                    late += 1
            g_completed.set(completed)
            g_in_progress.set(in_progress)
            g_not_started.set(not_started)
            g_late.set(late)
            # Update per-user metrics
            user_gauge.clear()
            for user_id, stats in user_stats.items():
                username = USER_LOOKUP.get(user_id, user_id)
                for status in ["completed", "in_progress", "not_started", "late"]:
                    user_gauge.labels(user_id=user_id, username=username, status=status).set(stats[status])
        except Exception as e:
            print(f"Error fetching or updating metrics: {e}")
        time.sleep(SCAN_INTERVAL)

@app.route(METRICS_PATH)
def metrics():
    return Response(generate_latest(registry), mimetype="text/plain")

def main():
    if not TOKEN:
        print("TOKEN environment variable is required.")
        exit(1)
    threading.Thread(target=fetch_and_update_metrics, daemon=True).start()
    # Only use Flask to serve /metrics
    app.run(host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
