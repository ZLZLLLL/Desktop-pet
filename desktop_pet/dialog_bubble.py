import json
import random
from pathlib import Path


class DialogBubble:
    CONFIG_PATH = Path(__file__).parent / "dialogs.json"

    LEVEL_NAMES = {
        1: "stranger",
        2: "acquaintance",
        3: "friend",
        4: "good_friend",
        5: "best_friend",
    }

    def __init__(self):
        self._dialogs = self._load()

    def _load(self) -> dict:
        try:
            if self.CONFIG_PATH.exists():
                with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return {}

    def _pick(self, key: str) -> str:
        lines = self._dialogs.get(key, [])
        return random.choice(lines) if lines else ""

    def get_dialog(self, level: int) -> str:
        name = self.LEVEL_NAMES.get(level, "stranger")
        return self._pick(name)

    def get_levelup_dialog(self) -> str:
        return self._pick("levelup")

    def get_drag_dialog(self) -> str:
        return self._pick("drag")

    def get_daily_first_dialog(self) -> str:
        return self._pick("daily_first")
