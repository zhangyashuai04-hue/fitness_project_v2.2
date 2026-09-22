from datetime import date
import flet as ft
import flet_charts as charts
from fitness.ui.forms import call


def build_chart(series,on_select_day):
    points=series['points']
    valid=[p for p in points if p['value'] is not None]
    controls=[]
    if valid:
        xs=[date.fromisoformat(p['day']).toordinal() for p in valid]
        ys=[p['value'] for p in valid]
        span=max(ys)-min(ys)
        padding=max(span*.15,1)
        labels=[charts.ChartAxisLabel(value=xs[i],label=ft.Text(valid[i]['day'][5:],size=10)) for i in sorted({0,len(valid)//2,len(valid)-1})]
        controls.append(charts.LineChart(data_series=[charts.LineChartData(points=[charts.LineChartDataPoint(x,y) for x,y in zip(xs,ys)],color=ft.Colors.TEAL,stroke_width=3,point=True)],
                                        bottom_axis=charts.ChartAxis(labels=labels,label_size=30),left_axis=charts.ChartAxis(label_size=42,show_min=False,show_max=False),
                                        min_x=min(xs)-.5,max_x=max(xs)+.5,min_y=max(0,min(ys)-padding),max_y=max(ys)+padding,height=210))
    else:
        controls.append(ft.Text('暂无可用数值'))
    if any(p['missing_elapsed'] for p in points):
        controls.append(ft.Text('部分旧记录没有本组持续时间，未补造时长。',size=12))
    buttons=[]
    for point in points:
        async def select(event,value=point):
            await call(on_select_day,value)
        label=f"{point['day']} · {'缺失' if point['value'] is None else format(point['value'],'.2f')} {series['unit']}"
        buttons.append(ft.TextButton(label,on_click=select))
    controls.append(ft.Row(buttons,wrap=True))
    return ft.Column(controls)
