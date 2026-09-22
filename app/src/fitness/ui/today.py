import flet as ft
from fitness.ui.forms import build_weight_field, card, call, confirm, refresh


def build_today(services, day, on_navigate):
    root = ft.Column(horizontal_alignment=ft.CrossAxisAlignment.STRETCH,spacing=16)
    async def rebuild():
        render()
        refresh(root)
    def render():
        summary = services.today.summary(day)
        previous = summary['previous_weight']
        difference = ''
        if previous and summary['weight'] is not None:
            difference = f"较上次 {summary['weight']-previous[1]:+.2f} kg（{previous[0]}）"
        async def food(event):
            await call(on_navigate, 'nutrition')
        plans = []
        active = services.training.restore_active()
        if active:
            async def resume(event):
                await call(on_navigate, 'resume', active.id)
            plans.append(ft.Button('继续未结束训练', on_click=resume))
        for plan in summary['plans']:
            async def start(event, identity=plan['id']):
                await call(on_navigate, 'start', identity)
            async def remove(event, identity=plan['id']):
                async def action():
                    services.plans.hide_plan(identity)
                    await rebuild()
                await confirm(root.page, '删除当天安排', '删除安排会保留已完成的训练记录；正在训练的计划需要先结束。', action)
            row = [ft.Text(plan['name'], size=17), ft.Text({'pending':'待训练','active':'训练中','completed':'已完成','skipped':'已跳过'}.get(plan['status'],plan['status']))]
            if plan['status'] in ('pending','active'):
                row.append(ft.Button('继续训练' if plan['status']=='active' else '开始今日训练计划', on_click=start))
            row.append(ft.TextButton('删除安排', on_click=remove))
            plans.append(ft.Column(row))
        nutrition = summary['nutrition']
        root.controls = [card('今日', ft.Text(day.isoformat()), ft.Text(f"本周已训练 {summary['week_training_days']} 天")),
                         card('体重', build_weight_field(services.weight,day,rebuild), ft.Text(difference or '直接输入体重，离开输入框自动保存')),
                         card('今日计划', *(plans or [ft.Text('今天还没有训练安排，请到训练页选择。')])),
                         card('饮食', ft.Text(f"摄入 {nutrition['intake']:g} kcal"),
                              ft.Text('消耗未记录' if nutrition['expenditure'] is None else f"消耗 {nutrition['expenditure']:g} kcal · 净摄入 {nutrition['balance']:g} kcal"),
                              ft.Button('记录饮食', on_click=food)),
                         card('今日成果', ft.Text(f"完成 {summary['completed_sets']} 组 · {summary['completed_exercises']} 个动作"),
                              ft.Text(f"训练累计 {summary['training_elapsed_ms']//60000} 分钟"))]
    render()
    return root
