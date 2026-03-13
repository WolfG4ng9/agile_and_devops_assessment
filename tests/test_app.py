"""
TaskFlow API - Test Suite
Run: python -m pytest tests/ -v
"""

import json
import unittest
from src.app import app
import src.app as module


def make_task(client, title="Buy milk", priority="medium", description=""):
    return client.post(
        "/tasks",
        data=json.dumps({"title": title, "priority": priority,
                         "description": description}),
        content_type="application/json",
    )


class BaseTest(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        module._tasks.clear()
        module._next_id = 1

    def tearDown(self):
        module._tasks.clear()
        module._next_id = 1


class TestHealth(BaseTest):
    def test_health_returns_200(self):
        rv = self.client.get("/health")
        self.assertEqual(rv.status_code, 200)

    def test_health_payload_fields(self):
        data = self.client.get("/health").get_json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("uptime_seconds", data)
        self.assertIn("task_count", data)
        self.assertIn("timestamp", data)

    def test_health_reflects_task_count(self):
        make_task(self.client)
        make_task(self.client, title="Another task")
        data = self.client.get("/health").get_json()
        self.assertEqual(data["task_count"], 2)


class TestListTasks(BaseTest):
    def test_empty_list(self):
        rv = self.client.get("/tasks")
        self.assertEqual(rv.status_code, 200)
        data = rv.get_json()
        self.assertEqual(data["tasks"], [])
        self.assertEqual(data["count"], 0)

    def test_list_returns_all_tasks(self):
        make_task(self.client, "Task A")
        make_task(self.client, "Task B")
        data = self.client.get("/tasks").get_json()
        self.assertEqual(data["count"], 2)

    def test_filter_by_valid_status(self):
        make_task(self.client, "Todo task")
        resp = make_task(self.client, "In-progress task")
        task_id = resp.get_json()["id"]
        self.client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "in_progress"}),
            content_type="application/json",
        )
        data = self.client.get("/tasks?status=in_progress").get_json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["tasks"][0]["status"], "in_progress")

    def test_filter_invalid_status_returns_400(self):
        rv = self.client.get("/tasks?status=flying")
        self.assertEqual(rv.status_code, 400)


class TestGetTask(BaseTest):
    def test_get_existing_task(self):
        make_task(self.client, "Find me")
        rv = self.client.get("/tasks/1")
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.get_json()["title"], "Find me")

    def test_get_missing_task_returns_404(self):
        rv = self.client.get("/tasks/999")
        self.assertEqual(rv.status_code, 404)

    def test_get_task_has_all_fields(self):
        make_task(self.client)
        data = self.client.get("/tasks/1").get_json()
        for field in ("id", "title", "description", "status",
                      "priority", "created_at", "updated_at"):
            self.assertIn(field, data)


class TestCreateTask(BaseTest):
    def test_create_task_returns_201(self):
        rv = make_task(self.client)
        self.assertEqual(rv.status_code, 201)

    def test_create_task_sets_defaults(self):
        data = make_task(self.client).get_json()
        self.assertEqual(data["status"], "todo")
        self.assertEqual(data["id"], 1)

    def test_create_task_without_title_returns_422(self):
        rv = self.client.post(
            "/tasks",
            data=json.dumps({"priority": "high"}),
            content_type="application/json",
        )
        self.assertEqual(rv.status_code, 422)

    def test_create_task_invalid_priority_returns_422(self):
        rv = self.client.post(
            "/tasks",
            data=json.dumps({"title": "T", "priority": "critical"}),
            content_type="application/json",
        )
        self.assertEqual(rv.status_code, 422)

    def test_create_task_no_body_returns_400(self):
        rv = self.client.post("/tasks")
        self.assertEqual(rv.status_code, 400)

    def test_create_task_ids_are_sequential(self):
        id1 = make_task(self.client, "First").get_json()["id"]
        id2 = make_task(self.client, "Second").get_json()["id"]
        self.assertEqual(id2, id1 + 1)

    def test_all_valid_priorities_accepted(self):
        for priority in ["low", "medium", "high"]:
            module._tasks.clear()
            module._next_id = 1
            rv = make_task(self.client, priority=priority)
            self.assertEqual(rv.status_code, 201)
            self.assertEqual(rv.get_json()["priority"], priority)


class TestUpdateTask(BaseTest):
    def test_update_status(self):
        make_task(self.client)
        rv = self.client.put(
            "/tasks/1",
            data=json.dumps({"status": "in_progress"}),
            content_type="application/json",
        )
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.get_json()["status"], "in_progress")

    def test_update_title(self):
        make_task(self.client, "Old Title")
        rv = self.client.put(
            "/tasks/1",
            data=json.dumps({"title": "New Title"}),
            content_type="application/json",
        )
        self.assertEqual(rv.get_json()["title"], "New Title")

    def test_update_invalid_status_returns_422(self):
        make_task(self.client)
        rv = self.client.put(
            "/tasks/1",
            data=json.dumps({"status": "deleted"}),
            content_type="application/json",
        )
        self.assertEqual(rv.status_code, 422)

    def test_update_missing_task_returns_404(self):
        rv = self.client.put(
            "/tasks/999",
            data=json.dumps({"status": "done"}),
            content_type="application/json",
        )
        self.assertEqual(rv.status_code, 404)

    def test_all_valid_statuses_accepted(self):
        for status in ["todo", "in_progress", "done"]:
            make_task(self.client, f"Task for {status}")
            tid = module._next_id - 1
            rv = self.client.put(
                f"/tasks/{tid}",
                data=json.dumps({"status": status}),
                content_type="application/json",
            )
            self.assertEqual(rv.status_code, 200)


class TestDeleteTask(BaseTest):
    def test_delete_existing_task(self):
        make_task(self.client)
        rv = self.client.delete("/tasks/1")
        self.assertEqual(rv.status_code, 200)

    def test_deleted_task_not_found(self):
        make_task(self.client)
        self.client.delete("/tasks/1")
        rv = self.client.get("/tasks/1")
        self.assertEqual(rv.status_code, 404)

    def test_delete_missing_task_returns_404(self):
        rv = self.client.delete("/tasks/999")
        self.assertEqual(rv.status_code, 404)

    def test_delete_reduces_count(self):
        make_task(self.client, "A")
        make_task(self.client, "B")
        self.client.delete("/tasks/1")
        data = self.client.get("/tasks").get_json()
        self.assertEqual(data["count"], 1)


class TestTaskSummary(BaseTest):
    def test_summary_empty(self):
        data = self.client.get("/tasks/summary").get_json()
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["summary"]["todo"], 0)

    def test_summary_counts_correctly(self):
        make_task(self.client, "A")
        make_task(self.client, "B")
        r = make_task(self.client, "C")
        tid = r.get_json()["id"]
        self.client.put(
            f"/tasks/{tid}",
            data=json.dumps({"status": "done"}),
            content_type="application/json",
        )
        data = self.client.get("/tasks/summary").get_json()
        self.assertEqual(data["summary"]["todo"], 2)
        self.assertEqual(data["summary"]["done"], 1)
        self.assertEqual(data["total"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
