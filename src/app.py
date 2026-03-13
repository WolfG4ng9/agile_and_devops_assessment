"""
TaskFlow API - A lightweight task management REST API
"""

import logging
import os
import time
from datetime import datetime, timezone
from flask import Flask, jsonify, request, abort

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("taskflow")

app = Flask(__name__)
app.start_time = time.time()

_tasks: dict = {}
_next_id: int = 1

VALID_STATUSES = {"todo", "in_progress", "done"}
VALID_PRIORITIES = {"low", "medium", "high"}


def _get_task_or_404(task_id):
    task = _tasks.get(task_id)
    if not task:
        logger.warning("Task %d not found", task_id)
        abort(404, description=f"Task {task_id} not found")
    return task


def _utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@app.route("/health", methods=["GET"])
def health():
    uptime = round(time.time() - app.start_time, 2)
    payload = {
        "status": "healthy",
        "uptime_seconds": uptime,
        "task_count": len(_tasks),
        "timestamp": _utcnow(),
    }
    logger.info("Health check OK | uptime=%.2fs tasks=%d", uptime, len(_tasks))
    return jsonify(payload), 200


@app.route("/tasks", methods=["GET"])
def list_tasks():
    status_filter = request.args.get("status")
    if status_filter and status_filter not in VALID_STATUSES:
        return jsonify({"error": f"Invalid status '{status_filter}'"}), 400
    tasks = list(_tasks.values())
    if status_filter:
        tasks = [t for t in tasks if t["status"] == status_filter]
    logger.info("Listed %d tasks (filter=%s)", len(tasks), status_filter)
    return jsonify({"tasks": tasks, "count": len(tasks)}), 200


@app.route("/tasks/summary", methods=["GET"])
def tasks_summary():
    summary = {s: 0 for s in VALID_STATUSES}
    for t in _tasks.values():
        summary[t["status"]] += 1
    logger.info("Summary requested: %s", summary)
    return jsonify({"summary": summary, "total": len(_tasks)}), 200


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    task = _get_task_or_404(task_id)
    logger.info("Fetched task %d", task_id)
    return jsonify(task), 200


@app.route("/tasks", methods=["POST"])
def create_task():
    global _next_id
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Request body must be JSON"}), 400
    title = (body.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Field 'title' is required"}), 422
    priority = body.get("priority", "medium")
    if priority not in VALID_PRIORITIES:
        return jsonify({"error": f"Invalid priority '{priority}'"}), 422
    task = {
        "id": _next_id,
        "title": title,
        "description": body.get("description", ""),
        "status": "todo",
        "priority": priority,
        "created_at": _utcnow(),
        "updated_at": _utcnow(),
    }
    _tasks[_next_id] = task
    _next_id += 1
    logger.info("Created task %d: '%s'", task["id"], task["title"])
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    task = _get_task_or_404(task_id)
    body = request.get_json(silent=True) or {}
    if "title" in body:
        title = body["title"].strip()
        if not title:
            return jsonify({"error": "Field 'title' cannot be blank"}), 422
        task["title"] = title
    if "description" in body:
        task["description"] = body["description"]
    if "status" in body:
        if body["status"] not in VALID_STATUSES:
            return jsonify({"error": f"Invalid status '{body['status']}'"}), 422
        task["status"] = body["status"]
    if "priority" in body:
        if body["priority"] not in VALID_PRIORITIES:
            return jsonify({"error": f"Invalid priority '{body['priority']}'"}), 422
        task["priority"] = body["priority"]
    task["updated_at"] = _utcnow()
    logger.info("Updated task %d (status=%s)", task_id, task["status"])
    return jsonify(task), 200


@app.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    _get_task_or_404(task_id)
    del _tasks[task_id]
    logger.info("Deleted task %d", task_id)
    return jsonify({"message": f"Task {task_id} deleted"}), 200


@app.errorhandler(404)
def not_found(e):
    logger.error("404: %s", e.description)
    return jsonify({"error": str(e.description)}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed"}), 405


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info("TaskFlow API starting on port %d", port)
    app.run(host="0.0.0.0", port=port)
