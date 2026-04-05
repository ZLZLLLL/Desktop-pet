import random


class StateMachine:
    def on_click(self, unlocked: list[str]) -> str:
        choices = [s for s in unlocked if s not in ("idle", "sleep", "levelup")]
        return random.choice(choices) if choices else "click"

    def on_double_click(self, unlocked: list[str]) -> str:
        if "levelup" in unlocked:
            return "levelup"
        return self.on_click(unlocked)

    def on_animation_done(self) -> str:
        return "sleep"
