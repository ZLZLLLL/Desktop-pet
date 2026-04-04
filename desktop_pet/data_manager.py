import json
from pathlib import Path


class DataManager:
    SAVE_PATH = Path(__file__).parent / "save_data.json"

    DEFAULT_DATA = {
        "intimacy": 0,
        "total_clicks": 0,
        "last_seen": "",
        "unlocked_animations": ["idle", "click"],
    }

    def __init__(self):
        self.data = self._load()

    def _load(self) -> dict:
        try:
            if self.SAVE_PATH.exists():
                with open(self.SAVE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for key, default in self.DEFAULT_DATA.items():
                    data.setdefault(key, default)
                return data
        except (json.JSONDecodeError, IOError):
            pass
        return dict(self.DEFAULT_DATA)

    def save(self) -> None:
        try:
            with open(self.SAVE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except IOError:
            pass

    def get_intimacy(self) -> int:
        return self.data.get("intimacy", 0)

    def add_intimacy(self, amount: int) -> tuple[int, bool]:
        old_level = self._get_level(self.data["intimacy"])
        self.data["intimacy"] = min(100, self.data["intimacy"] + amount)
        new_level = self._get_level(self.data["intimacy"])
        self.save()
        return self.data["intimacy"], new_level > old_level

    def increment_clicks(self, delta: int = 1) -> None:
        self.data["total_clicks"] = self.data.get("total_clicks", 0) + delta
        self.save()

    def get_total_clicks(self) -> int:
        return self.data.get("total_clicks", 0)

    def get_last_seen(self) -> str:
        return self.data.get("last_seen", "")

    def set_last_seen(self, date_str: str) -> None:
        self.data["last_seen"] = date_str
        self.save()

    def get_unlocked_animations(self) -> list[str]:
        return self.data.get("unlocked_animations", ["idle", "click"])

    def set_unlocked_animations(self, animations: list[str]) -> None:
        self.data["unlocked_animations"] = animations
        self.save()

    def reset(self) -> None:
        self.data = dict(self.DEFAULT_DATA)
        self.save()

    @staticmethod
    def _get_level(intimacy: int) -> int:
        if intimacy <= 20:
            return 1
        elif intimacy <= 40:
            return 2
        elif intimacy <= 60:
            return 3
        elif intimacy <= 80:
            return 4
        else:
            return 5
