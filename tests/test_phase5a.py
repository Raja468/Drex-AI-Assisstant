"""
Phase 5A verification: Task models, store, manager, events, and runtime integration.

Required tests:
  1. test_create_task              — Task created with correct defaults
  2. test_task_serialization       — to_dict() / from_dict() round-trip
  3. test_save_and_load_task       — TaskStore persists and retrieves
  4. test_update_status            — Status update persists correctly
  5. test_event_published          — EventBus receives task.created event
  6. test_list_tasks               — list_tasks() returns correct results
  7. test_list_tasks_by_status     — Filter by status works
  8. test_delete_task              — Task deletion works
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tempfile
from loguru import logger

logger.remove()

passed = 0
failed = 0
tests = []


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        mark = "PASS"
    else:
        failed += 1
        mark = "FAIL"
    msg = f"  {mark} {name}"
    if detail:
        msg += f" -- {detail}"
    tests.append(msg)


def header(title):
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


# Setup
from runtime.event_bus import EventBus
from runtime.tasks import (
    Task, TaskCancelled, TaskCompleted, TaskCreated,
    TaskFailed, TaskManager, TaskPaused, TaskPriority,
    TaskResumed, TaskStarted, TaskStatus, TaskStep,
    TaskStore, TaskUpdated,
)

# Use a temporary database for tests
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
TEST_DB_PATH = _tmp.name


def cleanup():
    try:
        os.unlink(TEST_DB_PATH)
    except OSError:
        pass


# ── Test 1: Task creation with defaults ────────────────────
header("TEST 1: Task creation defaults")
task = Task(
    id="test-1",
    title="Test Task",
    description="A test",
)
check("id is set", task.id == "test-1")
check("title is set", task.title == "Test Task")
check("status is PENDING", task.status == TaskStatus.PENDING)
check("priority is NORMAL", task.priority == TaskPriority.NORMAL)
check("steps is empty list", task.steps == [])
check("metadata is empty dict", task.metadata == {})

# Test creating with steps
step = TaskStep(id="step-1", title="Step 1", status=TaskStatus.PENDING,
                created_at=task.created_at, updated_at=task.updated_at)
task_with_steps = Task(
    id="test-2",
    title="Task with Steps",
    steps=[step],
)
check("steps contain 1 item", len(task_with_steps.steps) == 1)
check("step title correct", task_with_steps.steps[0].title == "Step 1")


# ── Test 2: Serialization round-trip ───────────────────────
header("TEST 2: Serialization round-trip")
import datetime
_now = datetime.datetime.now()
original = Task(
    id="serial-1",
    title="Serialization Test",
    description="Round-trip check",
    status=TaskStatus.RUNNING,
    priority=TaskPriority.HIGH,
    steps=[TaskStep(id="s1", title="Do thing", status=TaskStatus.PENDING,
                    created_at=_now, updated_at=_now)],
    metadata={"source": "test"},
)
data = original.to_dict()
restored = Task.from_dict(data)
check("id matches", restored.id == original.id)
check("title matches", restored.title == original.title)
check("description matches", restored.description == original.description)
check("status matches", restored.status == original.status)
check("priority matches", restored.priority == original.priority)
check("steps count matches", len(restored.steps) == len(original.steps))
check("step title matches", restored.steps[0].title == original.steps[0].title)
check("metadata matches", restored.metadata["source"] == "test")


# ── Test 3: TaskStore save and load ────────────────────────
header("TEST 3: TaskStore save and load")
store = TaskStore(db_path=TEST_DB_PATH)

task_a = Task(id="store-1", title="Store Test")
store.create_task(task_a)
check("create_task returns task", task_a.id == "store-1")

loaded = store.get_task("store-1")
check("get_task retrieves task", loaded is not None)
check("loaded title matches", loaded.title == "Store Test")
check("loaded status matches", loaded.status == TaskStatus.PENDING)

not_found = store.get_task("nonexistent")
check("get_task returns None for missing", not_found is None)


# ── Test 4: Status update persists ─────────────────────────
header("TEST 4: Status update persists")
task_b = Task(id="update-1", title="Update Test")
store.create_task(task_b)

task_b.status = TaskStatus.RUNNING
task_b.updated_at = task_b.created_at  # keep same for test simplicity
store.update_task(task_b)

loaded_b = store.get_task("update-1")
check("status updated to RUNNING", loaded_b.status == TaskStatus.RUNNING)
check("title unchanged", loaded_b.title == "Update Test")


# ── Test 5: EventBus receives events ───────────────────────
header("TEST 5: EventBus receives task events")
bus = EventBus()
manager = TaskManager(event_bus=bus, store=store)

received_events = []

def on_task_created(event):
    received_events.append(event)

bus.subscribe("task.created", on_task_created)

task_c = manager.create_task("Event Test", "Testing events")
check("event was received", len(received_events) == 1)
check("event carries task id", received_events[0].payload["task"]["id"] == task_c.id)

# Test task started event
received_events.clear()
def on_task_started(event):
    received_events.append(event)
bus.subscribe("task.started", on_task_started)

task_started = manager.start_task(task_c.id)
check("start_task returned task", task_started is not None)
check("task started event received", len(received_events) == 1)
check("task status is RUNNING", task_started.status == TaskStatus.RUNNING)

# Test complete event
received_events.clear()
def on_task_completed(event):
    received_events.append(event)
bus.subscribe("task.completed", on_task_completed)

task_done = manager.complete_task(task_c.id)
check("complete_task returned task", task_done is not None)
check("task completed event received", len(received_events) == 1)
check("task status is COMPLETED", task_done.status == TaskStatus.COMPLETED)


# ── Test 6: list_tasks ─────────────────────────────────────
header("TEST 6: list_tasks")
store = TaskStore(db_path=TEST_DB_PATH)
task_x = Task(id="list-1", title="Alpha")
task_y = Task(id="list-2", title="Beta")
task_z = Task(id="list-3", title="Gamma", status=TaskStatus.RUNNING)
store.create_task(task_x)
store.create_task(task_y)
store.create_task(task_z)

all_tasks = store.list_tasks()
check("all tasks returned", len(all_tasks) >= 3)

ids = {t.id for t in all_tasks}
check("list-1 present", "list-1" in ids)
check("list-2 present", "list-2" in ids)
check("list-3 present", "list-3" in ids)


# ── Test 7: list_tasks by status ───────────────────────────
header("TEST 7: list_tasks by status")
pending_tasks = store.list_tasks(status=TaskStatus.PENDING)
check("pending tasks returned", len(pending_tasks) >= 2)
for t in pending_tasks:
    check(f"  {t.id} is PENDING", t.status == TaskStatus.PENDING, f"got {t.status}")

running_tasks = store.list_tasks(status=TaskStatus.RUNNING)
check("running tasks returned", len(running_tasks) >= 1)
for t in running_tasks:
    check(f"  {t.id} is RUNNING", t.status == TaskStatus.RUNNING, f"got {t.status}")

# Status with no tasks
completed_tasks = store.list_tasks(status=TaskStatus.FAILED)
check("no FAILED tasks", len(completed_tasks) == 0)


# ── Test 8: delete_task ────────────────────────────────────
header("TEST 8: delete_task")
store = TaskStore(db_path=TEST_DB_PATH)
task_del = Task(id="delete-1", title="Delete Me")
store.create_task(task_del)
check("task exists before delete", store.get_task("delete-1") is not None)

deleted = store.delete_task("delete-1")
check("delete returns True", deleted is True)
check("task gone after delete", store.get_task("delete-1") is None)

deleted_false = store.delete_task("nonexistent")
check("delete missing returns False", deleted_false is False)


# ── Cleanup ────────────────────────────────────────────────
cleanup()


# Summary
print()
print("=" * 60)
print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
print("=" * 60)
for t in tests:
    print(t)
print()

if failed > 0:
    print("SOME TESTS FAILED")
    sys.exit(1)
else:
    print("ALL PHASE 5A TESTS PASSED")
    print()