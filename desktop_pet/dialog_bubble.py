import json
import random
from datetime import datetime
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

    def _get_intimacy_pool(self, intimacy: int) -> list[str]:
        pools = self._dialogs.get("intimacy_pools", {})
        if not isinstance(pools, dict):
            return []

        unlocked: list[str] = []
        for k, lines in pools.items():
            try:
                threshold = int(k)
            except (TypeError, ValueError):
                continue
            if intimacy >= threshold and isinstance(lines, list):
                unlocked.extend([str(line) for line in lines if isinstance(line, str) and line.strip()])
        return unlocked

    def get_dialog(self, level: int) -> str:
        name = self.LEVEL_NAMES.get(level, "stranger")
        return self._pick(name)

    def get_dialog_by_intimacy(self, intimacy: int) -> str:
        pool = self._get_intimacy_pool(intimacy)
        if pool:
            return random.choice(pool)

        # 兼容旧配置：若未配置好感度池，回退到等级对话。
        if intimacy <= 20:
            return self.get_dialog(1)
        if intimacy <= 40:
            return self.get_dialog(2)
        if intimacy <= 60:
            return self.get_dialog(3)
        if intimacy <= 80:
            return self.get_dialog(4)
        return self.get_dialog(5)

    def get_feeding_dialog(self, intimacy: int) -> str:
        feeding_lines = self._dialogs.get("feeding", [])
        if isinstance(feeding_lines, list) and feeding_lines:
            picked = random.choice([str(line) for line in feeding_lines if isinstance(line, str) and line.strip()])
            if picked:
                return picked
        return self.get_dialog_by_intimacy(intimacy)

    def get_levelup_dialog(self) -> str:
        return self._pick("levelup")

    def get_drag_dialog(self) -> str:
        return self._pick("drag")

    def get_daily_first_dialog(self) -> str:
        hour = datetime.now().hour
        if 5 <= hour < 11:
            key = "daily_morning"
        elif 11 <= hour < 13:
            key = "daily_noon"
        elif 13 <= hour < 19:
            key = "daily_afternoon"
        else:
            key = "daily_evening"

        text = self._pick(key)
        if text:
            return text
        return self._pick("daily_first")
