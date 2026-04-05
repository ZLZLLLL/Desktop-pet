from datetime import date

from data_manager import DataManager


class Intimacy:
    LEVEL_THRESHOLDS = {1: (0, 20), 2: (21, 40), 3: (41, 60), 4: (61, 80), 5: (81, 100)}
    LEVEL_UNLOCKS = {
        1: ["sleep", "click"],
        2: ["sleep", "click", "run"],
        3: ["sleep", "click", "run", "jump"],
        4: ["sleep", "click", "run", "jump"],
        5: ["sleep", "click", "run", "jump", "levelup"],
    }
    LEVEL_NAMES = {
        1: "陌生人",
        2: "熟人",
        3: "朋友",
        4: "好朋友",
        5: "挚友",
    }

    def __init__(self, data_manager: DataManager):
        self._dm = data_manager

    def add_click_intimacy(self) -> tuple[int, bool]:
        self._dm.increment_clicks(delta=1)
        return self._dm.add_intimacy(1)

    def add_double_click_intimacy(self) -> tuple[int, bool]:
        self._dm.increment_clicks(delta=2)
        return self._dm.add_intimacy(2)

    def add_daily_bonus(self) -> tuple[int, bool]:
        today = date.today().isoformat()
        if self._dm.get_last_seen() == today:
            return self._dm.get_intimacy(), False
        self._dm.set_last_seen(today)
        return self._dm.add_intimacy(5)

    def get_current_level(self) -> int:
        val = self._dm.get_intimacy()
        for lvl, (lo, hi) in self.LEVEL_THRESHOLDS.items():
            if lo <= val <= hi:
                return lvl
        return 5

    def get_level_name(self) -> str:
        return self.LEVEL_NAMES.get(self.get_current_level(), "陌生人")

    def get_unlocked_animations(self) -> list[str]:
        lvl = self.get_current_level()
        return list(self.LEVEL_UNLOCKS.get(lvl, self.LEVEL_UNLOCKS[1]))

    def get_intimacy_status(self) -> str:
        val = self._dm.get_intimacy()
        lvl = self.get_current_level()
        name = self.get_level_name()
        clicks = self._dm.get_total_clicks()
        return f"亲密度: {val}/100\n等级: Lv.{lvl} {name}\n总点击: {clicks}"
