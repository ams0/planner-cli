"""
Usage:
    python3 count_incomplete_tasks.py <PLAN_ID> [--no-missing-description] [--no-oldest-tasks]

Arguments:
    <PLAN_ID>   The Microsoft Planner Plan ID to fetch tasks for. Required.
    --no-missing-description   (Optional) If set, disables the display of tasks with no description.
    --no-oldest-tasks         (Optional) If set, disables the display of the 10 oldest not completed tasks.

Alternatively, you can set the PLAN_ID environment variable:
    export PLAN_ID=your_plan_id
    python3 count_incomplete_tasks.py

The script will use the TOKEN environment variable for authentication.

By default, the script displays a list of tasks with no description and the 10 oldest not completed tasks. Use --no-missing-description and/or --no-oldest-tasks to disable these outputs.
"""

import json
from collections import defaultdict
from datetime import datetime, timezone
import os
import requests
import sys
from dateutil import parser as date_parser

# Get token from environment only
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("TOKEN environment variable is required.")
    exit(1)

# Parse command line options
show_missing_description = True
show_oldest_tasks = True
args = sys.argv[1:]
if "--no-missing-description" in args:
    show_missing_description = False
    args.remove("--no-missing-description")
if "--no-oldest-tasks" in args:
    show_oldest_tasks = False
    args.remove("--no-oldest-tasks")
if len(args) > 0:
    PLAN_ID = args[0]
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
no_description_tasks = []
oldest_not_completed = []
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
    if not task.get("hasDescription", False) and percent < 100:
        # Get assignees
        assignees = []
        if "assignments" in task and task["assignments"]:
            for user_id in task["assignments"].keys():
                assignees.append(get_username(user_id))
        if not assignees:
            assignees = ["Unassigned"]
        no_description_tasks.append((task.get("title", "<no title>"), assignees))
    if percent < 100:
        created = task.get("createdDateTime")
        if created:
            assignees = []
            if "assignments" in task and task["assignments"]:
                for user_id in task["assignments"].keys():
                    assignees.append(get_username(user_id))
            if not assignees:
                assignees = ["Unassigned"]
            oldest_not_completed.append((created, task.get("title", "<no title>"), assignees))

for user_id, stats in user_stats.items():
    print(f"User {get_username(user_id)}: Completed: {stats['completed']}, In Progress: {stats['in_progress']}, Not Started: {stats['not_started']}, Late: {stats['late']}")

print("\nTotal tasks:")
print(f"Completed: {total_completed}")
print(f"In Progress: {total_in_progress}")
print(f"Not Started: {total_not_started}")
print(f"Late: {total_late}")

if show_missing_description:
    print(f"\nTasks with no description: {len(no_description_tasks)}")
    for title, assignees in no_description_tasks:
        print(f"- {title} (Assignee(s): {', '.join(assignees)})")

# Print 10 oldest not completed tasks
if show_oldest_tasks and oldest_not_completed:
    print("\n10 oldest not completed tasks:")
    # Sort by createdDateTime ascending
    oldest_not_completed.sort(key=lambda x: date_parser.parse(x[0]))
    for created, title, assignees in oldest_not_completed[:10]:
        try:
            dt = date_parser.parse(created)
            created_str = dt.strftime('%Y-%m-%d %H:%M')
        except Exception:
            created_str = created
        print(f"- {title} (Created: {created_str}, Assignee(s): {', '.join(assignees)})")
