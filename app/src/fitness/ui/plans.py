from datetime import date
from uuid import uuid4
import flet as ft
from fitness.domain.models import Exercise
from fitness.ui.forms import card, call, refresh, confirm


def build_exercise_editor(exercises=()):
    rows = ft.Column()
    def add(exercise=None):
        exercise = exercise or dict(id=str(uuid4()),name='',kind='weighted')
        name = ft.TextField(label='动作名称',value=exercise['name'],expand=True)
        kind = ft.Dropdown(label='类型',value=exercise['kind'],options=[ft.DropdownOption('weighted','负重'),ft.DropdownOption('bodyweight','自重'),ft.DropdownOption('timed','计时')],width=130)
        row = ft.Column([ft.Row([name,kind])],data=exercise['id'])
        async def remove(event):
            rows.controls.remove(row)
            refresh(rows)
        row.controls.append(ft.TextButton('移除此动作',on_click=remove))
        rows.controls.append(row)
    for exercise in exercises:
        add(exercise)
    async def add_click(event):
        add()
        refresh(rows)
    def values():
        return [Exercise(row.data,row.controls[0].controls[0].value or '',row.controls[0].controls[1].value) for row in rows.controls]
    return ft.Column([rows,ft.TextButton('添加动作',on_click=add_click)]), values


def build_plans(services,on_start):
    root = ft.Column(horizontal_alignment=ft.CrossAxisAlignment.STRETCH,spacing=14)
    selected = services.plans.clock.today()
    error = ft.Text(color=ft.Colors.ERROR)
    async def rebuild():
        render()
        refresh(root)
    async def editor(event,template=None,plan_mode=False):
        template = template or {}
        name = ft.TextField(label='计划名称' if plan_mode else '模板名称',value=template.get('name',''))
        exercises, values = build_exercise_editor(template.get('exercises',[]))
        message = ft.Text(color=ft.Colors.ERROR)
        async def save(event):
            try:
                if plan_mode:
                    services.plans.edit_plan(template['id'],name.value,values())
                else:
                    services.plans.save_template(name.value,values(),template.get('id'))
                root.page.pop_dialog()
                await rebuild()
            except Exception as exc:
                message.value=str(exc)
                refresh(message)
        async def cancel(event):
            root.page.pop_dialog()
        root.page.show_dialog(ft.AlertDialog(title=ft.Text('训练模板'),content=ft.Column([name,exercises,message],scroll=ft.ScrollMode.AUTO,width=460,height=430),actions=[ft.TextButton('取消',on_click=cancel),ft.Button('保存',on_click=save)]))
    def render():
        date_field = ft.TextField(label='计划日期（YYYY-MM-DD）',value=selected.isoformat())
        async def change_day(event):
            nonlocal selected
            try:
                selected=date.fromisoformat(date_field.value)
                await rebuild()
            except ValueError:
                date_field.error_text='请输入有效日期，例如 2026-10-01'
                refresh(date_field)
        date_field.on_submit=date_field.on_blur=change_day
        root.controls=[ft.Text('训练',size=28,weight=ft.FontWeight.BOLD),date_field,error]
        for plan in services.plans.list_plans(selected):
            async def start(event,identity=plan['id']):
                await call(on_start,identity)
            async def remove(event,identity=plan['id']):
                async def action():
                    services.plans.hide_plan(identity)
                    await rebuild()
                await confirm(root.page,'删除安排','已完成记录会保留。',action)
            async def skip(event,identity=plan['id']):
                try:
                    services.plans.skip_plan(identity)
                    await rebuild()
                except Exception as exc:
                    error.value=str(exc);refresh(error)
            controls=[ft.Text({'pending':'待训练','active':'训练中','completed':'已完成','skipped':'已跳过'}.get(plan['status'],plan['status'])),ft.Text(' → '.join(e['name'] for e in plan['exercises']))]
            if plan['status'] in ('pending','active'):
                controls.append(ft.Button('继续训练' if plan['status']=='active' else '开始训练',on_click=start))
            if plan['status']=='pending':
                async def edit_plan(event,item=plan):
                    await editor(event,item,True)
                controls.append(ft.TextButton('编辑本日计划',on_click=edit_plan))
                controls.append(ft.TextButton('标记跳过',on_click=skip))
            controls.append(ft.TextButton('删除安排',on_click=remove))
            root.controls.append(card(plan['name'],*controls))
        root.controls.append(ft.Button('新建模板',on_click=editor))
        for template in services.plans.list_templates():
            async def edit(event,item=template):
                await editor(event,item)
            async def schedule(event,identity=template['id']):
                try:
                    services.plans.schedule(identity,selected)
                    await rebuild()
                except Exception as exc:
                    error.value=str(exc);refresh(error)
            root.controls.append(card(template['name'],ft.Text(' → '.join(e['name'] for e in template['exercises'])),
                                      ft.Row([ft.Button('安排到所选日期',on_click=schedule),ft.TextButton('编辑模板',on_click=edit)])))
    render()
    return root
