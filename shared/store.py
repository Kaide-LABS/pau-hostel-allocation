"""JSON file store under data/. FROZEN: change only via the owner. See CONTRACT.md section 3."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from shared.models import AllocationResult, Hostel, Rules, Student

DATA_DIR = Path(os.getenv("HOSTEL_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))

STUDENTS_FILE = "students.json"
HOSTEL_FILE = "hostel.json"
RULES_FILE = "default_rules.json"
RESULT_FILE = "result.json"


def _path(name: str) -> Path:
    return DATA_DIR / name


def _read_json(name: str):
    with open(_path(name), encoding="utf-8") as f:
        return json.load(f)


def _write_json(name: str, payload) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.replace(tmp, _path(name))
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def load_students() -> list[Student]:
    return [Student.model_validate(s) for s in _read_json(STUDENTS_FILE)]


def save_students(students: list[Student]) -> None:
    _write_json(STUDENTS_FILE, [s.model_dump(mode="json") for s in students])


def load_hostel() -> Hostel:
    return Hostel.model_validate(_read_json(HOSTEL_FILE))


def load_default_rules() -> Rules:
    """Falls back to model defaults if the fixture is missing, so the compiler fallback never breaks."""
    try:
        return Rules.model_validate(_read_json(RULES_FILE))
    except FileNotFoundError:
        return Rules()


def save_result(result: AllocationResult) -> None:
    _write_json(RESULT_FILE, result.model_dump(mode="json"))


def load_result() -> AllocationResult | None:
    try:
        return AllocationResult.model_validate(_read_json(RESULT_FILE))
    except FileNotFoundError:
        return None
