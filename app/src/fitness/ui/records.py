from datetime import date,timedelta
from uuid import uuid4
import flet as ft
from fitness.domain.models import Exercise,Measurements
from fitness.ui.charts import build_chart
from fitness.ui.forms import card,refresh
from fitness.ui.nutrition import build_nutrition


def build_records(services):
    root=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.STRETCH,spacing=16)
    today=services.history.clock.today()
    start=ft.TextField(label='开始日期',value=(today-timedelta(days=30)).isoformat(),expand=True)
    end=ft.TextField(label='结束日期',value=today.isoformat(),expand=True)
    metric=ft.Dropdown(label='趋势指标',value='default',options=[ft.DropdownOption(k,v) for k,v in [('default','各动作默认指标'),('weight_max','最高重量'),('reps_total','总次数'),('volume_total','训练量'),('elapsed_total','本组持续时间'),('duration_total','计时动作时长')]])
    error=ft.Text(color=ft.Colors.ERROR)
    cards=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.STRETCH,spacing=16)
    async def edit_set(event,item=None):
        item=item or {}
        values=item.get('measurements',{})
        day=ft.TextField(label='日期',value=item.get('local_date',today.isoformat()),disabled=bool(item))
        name=ft.TextField(label='动作名称',value=item.get('exercise_name',''),disabled=bool(item))
        kind=ft.Dropdown(value=item.get('exercise_kind','weighted'),disabled=bool(item),options=[ft.DropdownOption('weighted','负重'),ft.DropdownOption('bodyweight','自重'),ft.DropdownOption('timed','计时')])
        weight=ft.TextField(label='重量 kg（负重动作）',value='' if values.get('weight') is None else str(values['weight']))
        reps=ft.TextField(label='次数（负重/自重）',value='' if values.get('reps') is None else str(values['reps']))
        duration=ft.TextField(label='计时动作时长（秒）',value='' if values.get('durationSeconds') is None else str(values['durationSeconds']))
        elapsed=ft.TextField(label='本组持续秒数（选填）',value='' if item.get('elapsed_ms') is None else str(item['elapsed_ms']/1000))
        message=ft.Text(color=ft.Colors.ERROR)
        async def save(event):
            try:
                value=Measurements(float(weight.value) if weight.value else None,int(reps.value) if reps.value else None,float(duration.value) if duration.value else None)
                ms=int(float(elapsed.value)*1000) if elapsed.value else None
                if item:
                    services.history.amend_set(item['id'],value,ms,clear_elapsed=not bool(elapsed.value))
                else:
                    services.history.add_historical_set(date.fromisoformat(day.value),Exercise(str(uuid4()),name.value,kind.value),value,ms)
                root.page.pop_dialog()
                await reload()
            except Exception as exc:
                message.value=str(exc);refresh(message)
        async def cancel(event):root.page.pop_dialog()
        root.page.show_dialog(ft.AlertDialog(title=ft.Text('修改训练组' if item else '补录训练组'),content=ft.Column([day,name,kind,weight,reps,duration,elapsed,message],scroll=ft.ScrollMode.AUTO,width=420,height=440),actions=[ft.TextButton('取消',on_click=cancel),ft.Button('保存',on_click=save)]))
    async def details(point):
        rows=[]
        identities=set(point['set_ids'])
        for session in services.history.sessions(date.fromisoformat(point['day'])):
            for item in services.history.sets(session['id']):
                if item['id'] in identities:
                    async def edit(event,value=item):
                        root.page.pop_dialog()
                        await edit_set(event,value)
                    values=item['measurements']
                    details=(f"{values.get('durationSeconds')} 秒" if item['exercise_kind']=='timed' else f"{values.get('reps')} 次")
                    if item['exercise_kind']=='weighted':details=f"{values.get('weight')} kg × "+details
                    rows.append(ft.Column([ft.Text(item['exercise_name']),ft.Text(details),ft.TextButton('修改此组',on_click=edit)]))
        if not rows:rows=[ft.Text(f"{point['day']}：{point['value']}。体重可在下方按日期修改。")]
        async def close(event):root.page.pop_dialog()
        root.page.show_dialog(ft.AlertDialog(title=ft.Text(point['day']),content=ft.Column(rows,scroll=ft.ScrollMode.AUTO,width=420,height=350),actions=[ft.TextButton('关闭',on_click=close)]))
    async def reload(event=None):
        try:
            data=services.trends.series(date.fromisoformat(start.value),date.fromisoformat(end.value),None if metric.value=='default' else metric.value)
            cards.controls=[card(series['name'],build_chart(series,details)) for series in data] or [ft.Text('所选日期暂无记录')]
            error.value=''
            refresh(root)
        except Exception as exc:
            error.value=str(exc);refresh(error)
    async def daily(event):
        from fitness.ui.forms import build_weight_field
        try:
            day=date.fromisoformat(end.value)
            async def close(event):
                root.page.pop_dialog()
                await reload()
            root.page.show_dialog(ft.AlertDialog(title=ft.Text(f'{day} 日常记录'),content=ft.Column([build_weight_field(services.weight,day),build_nutrition(services.nutrition,day)],scroll=ft.ScrollMode.AUTO,width=420,height=480),actions=[ft.TextButton('完成',on_click=close)]))
        except Exception as exc:
            error.value=str(exc);refresh(error)
    metric.on_select=reload
    root.controls=[ft.Text('记录与趋势',size=28),ft.Row([start,end]),metric,ft.Row([ft.Button('查询',on_click=reload),ft.TextButton('补录训练',on_click=edit_set),ft.TextButton('结束日期的体重/饮食',on_click=daily)],wrap=True),error,cards]
    initial=services.trends.series(today-timedelta(days=30),today)
    cards.controls=[card(series['name'],build_chart(series,details)) for series in initial] or [ft.Text('暂无记录')]
    return root
