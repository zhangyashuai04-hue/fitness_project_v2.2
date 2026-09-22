from datetime import datetime, time, timedelta


def daily_duration(intervals, day):
    start=int(datetime.combine(day,time.min).timestamp()*1000)
    end=int(datetime.combine(day+timedelta(days=1),time.min).timestamp()*1000)
    return sum(max(0,min(b,end)-max(a,start)) for a,b in intervals)
