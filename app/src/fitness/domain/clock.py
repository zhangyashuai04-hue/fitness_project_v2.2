from datetime import date
import time

class Clock:
    def now_ms(self) -> int:
        return time.time_ns() // 1_000_000

    def today(self) -> date:
        return date.today()
