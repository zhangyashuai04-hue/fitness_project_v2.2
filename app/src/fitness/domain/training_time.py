from datetime import datetime, time, timedelta


def daily_duration(intervals, day):
    start=int(datetime.combine(day,time.min).timestamp()*1000)
    end=int(datetime.combine(day+timedelta(days=1),time.min).timestamp()*1000)
    return sum(max(0,min(b,end)-max(a,start)) for a,b in intervals)


class GuardedClock:
    """Keep observed elapsed time stable when the wall clock is corrected backward."""
    def __init__(self,clock):
        self.source=clock
        self.high=clock.now_ms()
        self.backward=False

    def observe(self,value):
        self.high=max(self.high,value)

    def now_ms(self):
        value=self.source.now_ms()
        if value<self.high:self.backward=True
        self.high=max(self.high,value)
        return self.high

    def today(self):return self.source.today()
