"""Rules for new free-training inputs; absent values stay absent."""
import math
from .models import Measurements


def parse_measurements(reps: str, weight: str) -> Measurements:
    reps, weight = reps.strip(), weight.strip()
    if reps and (not reps.isascii() or not reps.isdecimal() or int(reps) <= 0):
        raise ValueError('次数须为正整数')
    try:
        kg = float(weight) if weight else None
    except ValueError:
        raise ValueError('重量须为非负数字') from None
    if kg is not None and (not math.isfinite(kg) or kg < 0):
        raise ValueError('重量须为有限非负数字')
    return Measurements(reps=int(reps) if reps else None, weight=kg)


def should_save(value: Measurements) -> bool:
    return value.reps is not None or value.weight is not None


def validate_partial(value: Measurements) -> None:
    if value.duration_seconds is not None:
        raise ValueError('新动作使用次数和重量记录')
    if value.reps is not None and (type(value.reps) is not int or value.reps <= 0):
        raise ValueError('次数须为正整数')
    if value.weight is not None and (isinstance(value.weight, bool) or not isinstance(value.weight,(int,float)) or not math.isfinite(value.weight) or value.weight < 0):
        raise ValueError('重量须为有限非负数字')


def validate_next_set(value: Measurements) -> None:
    validate_partial(value)
    if value.reps is None or value.weight is None:
        raise ValueError('请填写次数和重量后进入下一组')
