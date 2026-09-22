from datetime import timedelta
import flet as ft
from fitness.domain.models import Measurements
from fitness.services.records import format_set
from fitness.ui.charts import build_chart
from fitness.ui.forms import card, refresh


class RecordsController:
    def __init__(self,records,weight,clock):
        self.records,self.weight,self.clock=records,weight,clock
        self.selected_day=clock.today()

    def select_day(self,day): self.selected_day=day

    def save_today_weight(self,value):
        day=self.clock.today()
        if self.weight.read(day)!=value: self.weight.save(day,value)


def build_records(services):
    c=RecordsController(services.records,services.weight,services.records.clock)
    root=ft.Column(spacing=16,horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    history=ft.Column(spacing=12,horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    heading=ft.Text(size=19,weight=ft.FontWeight.BOLD)
    graph=ft.Column()
    error=ft.Text(color=ft.Colors.ERROR)
    today=c.clock.today()
    current=c.weight.read(today)
    weight=ft.TextField(label='输入今日体重（kg）',value='' if current is None else f'{current:g}',keyboard_type=ft.KeyboardType.NUMBER)
    async def detail(point):
        async def close(event):root.page.pop_dialog()
        root.page.show_dialog(ft.AlertDialog(title=ft.Text(point['day']),content=ft.Text(f"体重 {point['value']:g} kg"),actions=[ft.TextButton('关闭',on_click=close)]))
    def update_chart():
        series=next((s for s in services.trends.series(c.clock.today()-timedelta(days=365),c.clock.today()) if s['key']=='body_weight'),None)
        graph.controls=[build_chart(series,detail)] if series else [ft.Text('记录体重后，这里会显示变化趋势。')]
    async def save_weight(event):
        try:
            if (weight.value or '').strip():c.save_today_weight(float(weight.value))
            error.value='';update_chart();refresh(graph)
        except Exception as exc:error.value=str(exc)
        refresh(error)
    weight.on_submit=weight.on_blur=weight.on_tap_outside=save_weight
    def show_day():
        heading.value=f'训练记录  {c.selected_day.isoformat()}'
        rows=[]
        for index,session in enumerate(c.records.day_sessions(c.selected_day),1):
            rows.append(ft.Text(f"训练 {index}"+(' · 进行中' if session['status']!='ended' else ''),weight=ft.FontWeight.BOLD))
            for action in session['actions']:
                rows.append(ft.Text(f"{action['name']} · {len(action['sets'])}组",size=17))
                for i,item in enumerate(action['sets'],1):
                    value=Measurements(weight=item['weight'],reps=item['reps'],duration_seconds=item['duration_seconds'])
                    text='时长缺失' if item['kind']=='timed' and value.duration_seconds is None else format_set(value)
                    rows.append(ft.Text(f'第{i}组  {text}'))
        history.controls=rows or [ft.Text('这一天还没有训练记录。')]
    async def move(days):
        c.select_day(c.selected_day+timedelta(days=days));show_day();refresh(heading);refresh(history)
    async def previous(event):await move(-1)
    async def following(event):await move(1)
    async def swipe(event):
        velocity=event.primary_velocity or 0
        if abs(velocity)>150:await move(-1 if velocity<0 else 1)
    show_day();update_chart()
    root.controls=[ft.Row([ft.Text(today.isoformat(),size=20),ft.Text(f'本周训练次数：{c.records.week_count(today)}')],wrap=True,alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                   card('训练记录',heading,ft.GestureDetector(content=history,on_horizontal_drag_end=swipe),ft.Row([ft.TextButton('← 前一天',on_click=previous),ft.TextButton('后一天 →',on_click=following)],alignment=ft.MainAxisAlignment.SPACE_BETWEEN)),
                   card('体重',weight,error,graph)]
    return root
