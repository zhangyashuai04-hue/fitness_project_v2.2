import math


def finite_number(value, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('请输入数字')
    try:
        valid = math.isfinite(value) and (value > 0 if positive else value >= 0)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError('请输入有效的正数' if positive else '请输入有效的非负数')


def validate_measurements(kind, measurements):
    if kind not in ('weighted', 'bodyweight', 'timed'):
        raise ValueError('未知动作类型')
    if kind in ('weighted', 'bodyweight'):
        if type(measurements.reps) is not int or measurements.reps <= 0:
            raise ValueError('次数必须是正整数')
    if kind == 'weighted':
        finite_number(measurements.weight)
    if kind == 'timed':
        finite_number(measurements.duration_seconds, positive=True)
