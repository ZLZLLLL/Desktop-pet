import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal


_PRIVACY_CONFIG_PATH = Path(__file__).parent / "privacy_config.json"


def _load_privacy_config() -> dict:
    try:
        if _PRIVACY_CONFIG_PATH.exists():
            with open(_PRIVACY_CONFIG_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f)
                if isinstance(payload, dict):
                    return payload
    except Exception:
        pass
    return {}


def _get_lark_identity() -> str:
    cfg = _load_privacy_config()
    lark_cfg = cfg.get("lark") if isinstance(cfg, dict) else {}
    identity = ""
    if isinstance(lark_cfg, dict):
        identity = str(lark_cfg.get("identity") or "").strip()
    return identity or "user"


def _get_lark_assignee_open_id() -> str:
    cfg = _load_privacy_config()
    lark_cfg = cfg.get("lark") if isinstance(cfg, dict) else {}
    if isinstance(lark_cfg, dict):
        return str(lark_cfg.get("assignee_open_id") or "").strip()
    return ""


class LarkTaskFetcherThread(QThread):
    result_ready = pyqtSignal(str)
    tasks_ready = pyqtSignal(object)

    def _resolve_command(self, args: list[str]) -> list[str]:
        if not args:
            return args

        cmd = args[0]
        if os.path.sep in cmd or (os.path.altsep and os.path.altsep in cmd):
            return args

        resolved = shutil.which(cmd)
        if resolved:
            return [resolved, *args[1:]]

        if os.name == "nt":
            # Windows 下 `lark-cli` 常见为 `lark-cli.cmd`，裸命令会触发 WinError 2。
            for suffix_cmd in (f"{cmd}.cmd", f"{cmd}.bat", f"{cmd}.exe", f"{cmd}.ps1"):
                resolved = shutil.which(suffix_cmd)
                if resolved:
                    return [resolved, *args[1:]]

        return args

    def _run_cli(self, args: list[str]) -> str:
        command = self._resolve_command(args)
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.returncode != 0:
            err = (result.stderr or "").strip()
            out = (result.stdout or "").strip()
            raise RuntimeError(err or out or "命令执行失败")
        return result.stdout or ""

    def _extract_task_list(self, payload):
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("data", "items", "tasks", "list", "result"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value
                if isinstance(value, dict):
                    for sub_key in ("items", "tasks", "list"):
                        sub_value = value.get(sub_key)
                        if isinstance(sub_value, list):
                            return sub_value
        return []

    def _extract_guid(self, item: dict) -> str | None:
        if not isinstance(item, dict):
            return None
        for key in ("guid", "id", "task_guid", "task_id"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _extract_title(self, payload, fallback: str = "(未命名任务)") -> str:
        if isinstance(payload, dict):
            for key in ("title", "summary", "subject", "name"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            data = payload.get("data")
            if isinstance(data, dict):
                return self._extract_title(data, fallback)
        return fallback

    def _extract_due_time(self, payload) -> str | None:
        if isinstance(payload, dict):
            for key in (
                "due_at",
                "due_time",
                "deadline",
                "deadline_at",
                "end_at",
                "end_time",
                "expire_at",
            ):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            for nested_key in ("data", "task", "item", "result"):
                nested = payload.get(nested_key)
                due = self._extract_due_time(nested)
                if due:
                    return due
        return None

    def _format_due_time(self, raw_due_time: str | None) -> str | None:
        if not raw_due_time:
            return None

        value = raw_due_time.strip()
        if not value:
            return None

        dt: datetime | None = None

        if value.isdigit():
            try:
                timestamp = int(value)
                if len(value) >= 13:
                    dt = datetime.fromtimestamp(timestamp / 1000)
                else:
                    dt = datetime.fromtimestamp(timestamp)
            except Exception:
                dt = None
        else:
            try:
                # 业务要求：类似 2026-04-06T08:00:00+08:00 需要额外再加 8 小时显示。
                offset_match = re.search(r"([+-])(\d{2}):(\d{2})$", value)
                base = value[:-6] if offset_match else value
                dt = datetime.fromisoformat(base)
                if offset_match:
                    sign = 1 if offset_match.group(1) == "+" else -1
                    offset_hours = int(offset_match.group(2))
                    offset_minutes = int(offset_match.group(3))
                    from datetime import timedelta
                    dt = dt + timedelta(
                        hours=sign * offset_hours,
                        minutes=sign * offset_minutes,
                    )
            except Exception:
                dt = None

        if dt is None:
            return value

        return f"{dt.year}年{dt.month}月{dt.day}日 {dt.hour:02d}:{dt.minute:02d}"

    def _is_completed(self, payload) -> bool:
        if isinstance(payload, dict):
            completion_time_keys = {
                "completed_at",
                "complete_time",
                "completed_time",
                "done_at",
                "finish_time",
                "finished_at",
                "completion_time",
            }
            for key in completion_time_keys:
                if payload.get(key):
                    return True

            for key in ("is_completed", "completed", "done", "is_done", "finished", "is_finished"):
                value = payload.get(key)
                if value is True:
                    return True

            for key in ("status", "state", "task_status"):
                value = payload.get(key)
                if isinstance(value, str):
                    normalized = value.strip().lower()
                    if normalized in {"completed", "done", "finished", "closed", "success"}:
                        return True
                if isinstance(value, int) and value in {2, 3, 4}:
                    return True

            for nested_key in ("data", "task", "item", "result"):
                nested = payload.get(nested_key)
                if nested is not None and self._is_completed(nested):
                    return True

        if isinstance(payload, list):
            return any(self._is_completed(item) for item in payload)

        return False

    def run(self):
        try:
            raw = self._run_cli(
                [
                    "lark-cli",
                    "task",
                    "+get-my-tasks",
                    "--as",
                    _get_lark_identity(),
                    "--complete=false",
                    "--format",
                    "json",
                ]
            )
            task_list_payload = json.loads(raw)
            if isinstance(task_list_payload, dict) and task_list_payload.get("ok") is False:
                raise RuntimeError(task_list_payload.get("error", {}).get("message", "查询失败"))
            task_items = self._extract_task_list(task_list_payload)
        except Exception as exc:
            self.result_ready.emit(f"飞书待办查询失败：{exc}")
            self.tasks_ready.emit([])
            return

        todos: list[dict] = []
        detail_query_unavailable = False

        for item in task_items:
            guid = self._extract_guid(item)
            base_title = self._extract_title(item, fallback=f"任务 {guid}" if guid else "(未命名任务)")
            base_due = self._extract_due_time(item)

            if not guid:
                todos.append(
                    {
                        "guid": "",
                        "title": base_title,
                        "due_time": self._format_due_time(base_due),
                    }
                )
                continue

            if detail_query_unavailable:
                todos.append(
                    {
                        "guid": guid,
                        "title": base_title,
                        "due_time": self._format_due_time(base_due),
                    }
                )
                continue

            try:
                detail_raw = self._run_cli(
                    ["lark-cli", "task", "tasks", "get", guid, "--format", "json"]
                )
                detail_payload = json.loads(detail_raw)

                if isinstance(detail_payload, dict) and detail_payload.get("ok") is False:
                    raise RuntimeError(detail_payload.get("error", {}).get("message", "详情查询失败"))

                if self._is_completed(detail_payload):
                    continue

                title = self._extract_title(detail_payload, fallback=base_title)
                due_time = self._extract_due_time(detail_payload) or base_due
                todos.append(
                    {
                        "guid": guid,
                        "title": title,
                        "due_time": self._format_due_time(due_time),
                    }
                )
            except Exception as exc:
                err_msg = str(exc)
                if "missing required path parameter: task_guid" in err_msg:
                    # 当前 lark-cli 版本详情接口参数解析异常，降级到列表摘要展示
                    detail_query_unavailable = True
                    todos.append(
                        {
                            "guid": guid,
                            "title": base_title,
                            "due_time": self._format_due_time(base_due),
                        }
                    )
                continue

        if not todos:
            self.result_ready.emit("太棒啦，当前没有未完成的任务！")
            self.tasks_ready.emit([])
            return

        lines = ["【我的待办】"]
        for index, task in enumerate(todos, start=1):
            title = str(task.get("title") or "(未命名任务)")
            due_text = task.get("due_time")
            if due_text:
                lines.append(f"{index}. {title}  {due_text}")
            else:
                lines.append(f"{index}. {title}")

        self.tasks_ready.emit(todos)
        self.result_ready.emit("\n".join(lines))


class LarkTaskCompleterThread(QThread):
    completed = pyqtSignal(str, bool, str)

    def __init__(self, guid: str, parent=None):
        super().__init__(parent)
        self.guid = (guid or "").strip()

    def _resolve_command(self, args: list[str]) -> list[str]:
        if not args:
            return args

        cmd = args[0]
        if os.path.sep in cmd or (os.path.altsep and os.path.altsep in cmd):
            return args

        resolved = shutil.which(cmd)
        if resolved:
            return [resolved, *args[1:]]

        if os.name == "nt":
            for suffix_cmd in (f"{cmd}.cmd", f"{cmd}.bat", f"{cmd}.exe", f"{cmd}.ps1"):
                resolved = shutil.which(suffix_cmd)
                if resolved:
                    return [resolved, *args[1:]]

        return args

    def run(self):
        if not self.guid:
            self.completed.emit(self.guid, False, "任务缺少 guid，无法完成")
            return

        try:
            command = self._resolve_command(
                [
                    "lark-cli",
                    "task",
                    "+complete",
                    "--as",
                    _get_lark_identity(),
                    "--task-id",
                    self.guid,
                    "--format",
                    "json",
                ]
            )
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if result.returncode != 0:
                err = (result.stderr or "").strip()
                out = (result.stdout or "").strip()
                self.completed.emit(self.guid, False, err or out or "完成待办失败")
                return

            payload = json.loads(result.stdout or "{}")
            if isinstance(payload, dict) and payload.get("ok") is False:
                message = payload.get("error", {}).get("message", "完成待办失败")
                self.completed.emit(self.guid, False, message)
                return

            self.completed.emit(self.guid, True, "完成成功")
        except Exception as exc:
            self.completed.emit(self.guid, False, str(exc))


class LarkTaskCreatorThread(QThread):
    created = pyqtSignal(bool, str)

    def __init__(self, summary: str, due_date: str, parent=None):
        super().__init__(parent)
        self.summary = (summary or "").strip()
        self.due_date = (due_date or "+0d").strip()

    def _resolve_command(self, args: list[str]) -> list[str]:
        if not args:
            return args

        cmd = args[0]
        if os.path.sep in cmd or (os.path.altsep and os.path.altsep in cmd):
            return args

        resolved = shutil.which(cmd)
        if resolved:
            return [resolved, *args[1:]]

        if os.name == "nt":
            for suffix_cmd in (f"{cmd}.cmd", f"{cmd}.bat", f"{cmd}.exe", f"{cmd}.ps1"):
                resolved = shutil.which(suffix_cmd)
                if resolved:
                    return [resolved, *args[1:]]

        return args

    def run(self):
        if not self.summary:
            self.created.emit(False, "待办标题不能为空")
            return

        assignee_open_id = _get_lark_assignee_open_id()
        if not assignee_open_id:
            self.created.emit(False, "未配置 assignee_open_id，请先填写 privacy_config.json")
            return

        try:
            command = self._resolve_command(
                [
                    "lark-cli",
                    "task",
                    "+create",
                    "--as",
                    _get_lark_identity(),
                    "--summary",
                    self.summary,
                    "--assignee",
                    assignee_open_id,
                    "--due",
                    self.due_date,
                    "--format",
                    "json",
                ]
            )
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if result.returncode != 0:
                err = (result.stderr or "").strip()
                out = (result.stdout or "").strip()
                self.created.emit(False, err or out or "添加待办失败")
                return

            payload = json.loads(result.stdout or "{}")
            if isinstance(payload, dict) and payload.get("ok") is False:
                message = payload.get("error", {}).get("message", "添加待办失败")
                self.created.emit(False, message)
                return

            self.created.emit(True, "添加成功")
        except Exception as exc:
            self.created.emit(False, str(exc))