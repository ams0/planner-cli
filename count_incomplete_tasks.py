"""
Usage:
    python3 count_incomplete_tasks.py <PLAN_ID>

Arguments:
    <PLAN_ID>   The Microsoft Planner Plan ID to fetch tasks for. Required.

Alternatively, you can set the PLAN_ID environment variable:
    export PLAN_ID=your_plan_id
    python3 count_incomplete_tasks.py

The script will use the TOKEN environment variable for authentication.
"""

import json
from collections import defaultdict
from datetime import datetime, timezone
import os
import requests
import sys

# Get token from environment only
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("TOKEN environment variable is required.")
    exit(1)

# Get PLAN_ID from command line or environment, no default
if len(sys.argv) > 1:
    PLAN_ID = sys.argv[1]
else:
    PLAN_ID = os.getenv("PLAN_ID")
if not PLAN_ID:
    print("PLAN_ID must be provided as a command line argument or PLAN_ID environment variable.")
    exit(1)
GRAPH_URL = f"https://graph.microsoft.com/v1.0/planner/plans/{PLAN_ID}/tasks"

headers = {"Authorization": f"Bearer {TOKEN}"}
resp = requests.get(GRAPH_URL, headers=headers)
resp.raise_for_status()
data = resp.json()

# Per-user stats
user_stats = defaultdict(lambda: {"completed": 0, "in_progress": 0, "not_started": 0, "late": 0})

# Global totals
total_completed = 0
total_in_progress = 0
total_not_started = 0
total_late = 0

USER_LOOKUP_FILE = "user_lookup_table.json"
try:
    with open(USER_LOOKUP_FILE, "r") as f:
        USER_LOOKUP = json.load(f)
except Exception as e:
    print(f"Warning: Could not load user lookup table from {USER_LOOKUP_FILE}: {e}")
    USER_LOOKUP = {}

def get_username(user_id):
    return USER_LOOKUP.get(user_id, user_id)

# Change the source of tasks to match new JSON structure
for task in data.get("value", []):
    percent = task.get("percentComplete", 0)
    due = task.get("dueDateTime")
    is_late = False
    if percent < 100 and due:
        try:
            due_dt = datetime.fromisoformat(due.replace("Z", "+00:00"))
            if due_dt < datetime.now(timezone.utc):
                is_late = True
        except Exception:
            pass
    # Gather all assigned user IDs from both assignments and _assignments
    user_ids = set()
    if "assignments" in task:
        user_ids.update(task["assignments"].keys())
    if "_assignments" in task:
        user_ids.update(a.get("userId") for a in task["_assignments"] if a.get("userId"))
    # Classify task status
    if percent == 100:
        status = "completed"
        total_completed += 1
    elif percent == 0:
        status = "not_started"
        total_not_started += 1
    else:
        status = "in_progress"
        total_in_progress += 1
    # Update per-user stats
    for user_id in user_ids:
        user_stats[user_id][status] += 1
        if is_late:
            user_stats[user_id]["late"] += 1
    if is_late:
        total_late += 1

for user_id, stats in user_stats.items():
    print(f"User {get_username(user_id)}: Completed: {stats['completed']}, In Progress: {stats['in_progress']}, Not Started: {stats['not_started']}, Late: {stats['late']}")

print("\nTotal tasks:")
print(f"Completed: {total_completed}")
print(f"In Progress: {total_in_progress}")
print(f"Not Started: {total_not_started}")
print(f"Late: {total_late}")
