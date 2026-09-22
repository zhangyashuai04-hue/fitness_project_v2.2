from uuid import uuid4
import flet as ft
from fitness.domain.models import Slot, Exercise
from fitness.ui.forms import refresh


async def show_training_editor(view):
    controller = view.controller
    snap = controller.edit()
    view.render()
    refresh(view)
    name = ft.TextField(label='本次计划名称',value=controller.service.session_name(snap.id))
    rows = ft.Column()
    error = ft.Text(color=ft.Colors.ERROR)
    discard = ft.Checkbox(label='确认舍弃被移除动作的未完成输入',value=False)
    existing = {s.id:s for s in snap.slots}
    def add(slot=None):
        if slot is None:
            slot=Slot(str(uuid4()),Exercise(str(uuid4()),'','weighted'),-1)
        text=ft.TextField(label='动作名称',value=slot.exercise.name,expand=True)
        kind=ft.Dropdown(value=slot.exercise.kind,width=125,options=[ft.DropdownOption('weighted','负重'),ft.DropdownOption('bodyweight','自重'),ft.DropdownOption('timed','计时')])
        row=ft.Column([ft.Row([text,kind])],data=slot)
        async def up(event):
            index=rows.controls.index(row)
            if index>0:
                rows.controls[index-1],rows.controls[index]=rows.controls[index],rows.controls[index-1]
                refresh(rows)
        async def down(event):
            index=rows.controls.index(row)
            if index<len(rows.controls)-1:
                rows.controls[index+1],rows.controls[index]=rows.controls[index],rows.controls[index+1]
                refresh(rows)
        async def remove(event):
            rows.controls.remove(row)
            refresh(rows)
        row.controls.append(ft.Row([ft.TextButton('上移',on_click=up),ft.TextButton('下移',on_click=down),ft.TextButton('移除',on_click=remove)]))
        rows.controls.append(row)
    for identity in snap.order:
        add(existing[identity])
    async def add_click(event):
        add()
        refresh(rows)
    async def save(event):
        try:
            if snap.current_slot_id and snap.current_slot_id not in [r.data.id for r in rows.controls] and not discard.value:
                raise ValueError('移除当前动作前，请确认舍弃未完成输入。')
            slots=[]
            append_index=len(snap.slots)
            for row in rows.controls:
                slot=row.data
                fields=row.controls[0].controls
                index=slot.legacy_index if slot.id in existing else append_index
                if slot.id not in existing: append_index+=1
                slots.append(Slot(slot.id,Exercise(slot.exercise.id,fields[0].value or '',fields[1].value),index))
            controller.snapshot=controller.service.apply_edit(snap.id,name.value,tuple(slots),tuple(s.id for s in slots),snap.revision)
            view.page.pop_dialog()
            view.render()
            refresh(view)
            await view.show_choice()
        except Exception as exc:
            error.value=str(exc)
            refresh(error)
    async def cancel(event):
        view.page.pop_dialog()
    view.page.show_dialog(ft.AlertDialog(modal=True,title=ft.Text('修改本次训练'),
        content=ft.Column([ft.Text('编辑期间暂停计时，保存后点击继续。已完成组保留原记录。'),name,rows,ft.TextButton('添加动作',on_click=add_click),discard,error],scroll=ft.ScrollMode.AUTO,width=460,height=450),
        actions=[ft.TextButton('取消',on_click=cancel),ft.Button('保存修改',on_click=save)]))
