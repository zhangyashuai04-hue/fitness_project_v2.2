import asyncio
from uuid import uuid4
import flet as ft
from fitness.domain.models import Measurements
from fitness.domain.validation import validate_measurements
from fitness.ui.forms import refresh as refresh_control, call, card, confirm


class TrainingController:
    def __init__(self, service, on_changed=None):
        self.service, self.on_changed = service, on_changed
        self.snapshot = None
        self.pending = None
        self.busy = False
        self.input_error = None

    def start(self, plan_id):
        self.snapshot = self.service.start(plan_id)
        return self.snapshot

    def refresh(self, identity=None):
        if not self.pending:
            self.snapshot = self.service.get(identity or self.snapshot.id)
        return self.snapshot

    @property
    def can_complete(self):
        s = self.snapshot
        if not s or self.busy or self.input_error or s.status != 'running' or s.phase != 'collecting' or not s.current_slot_id:
            return False
        try:
            kind = next(slot.exercise.kind for slot in s.slots if slot.id == s.current_slot_id)
            validate_measurements(kind, s.draft)
            return True
        except ValueError:
            return False

    def update_inputs(self, weight, reps, duration):
        if self.pending:
            raise ValueError('请先重试完成本组，确认上次保存结果')
        try:
            value = Measurements(float(weight) if weight.strip() else None, int(reps) if reps.strip() else None,
                                 float(duration) if duration.strip() else None)
            self.snapshot = self.service.save_draft(self.snapshot.id, value)
            self.input_error = None
        except Exception as exc:
            self.input_error = str(exc)
            raise

    def _command(self, action, callback):
        if self.busy:
            return self.snapshot
        self.busy = True
        try:
            if self.pending is None:
                self.pending = (action, self.snapshot.revision, str(uuid4()))
            if self.pending[0] != action:
                raise ValueError('请先重试上次操作')
            self.snapshot = callback(self.pending[1], self.pending[2])
            self.pending = None
            return self.snapshot
        finally:
            self.busy = False

    def complete(self):
        if not self.pending and not self.can_complete:
            return self.snapshot
        return self._command('complete', lambda revision, identity: self.service.complete(self.snapshot.id, revision, identity))

    def choose(self, action):
        return self._command(action, lambda revision, identity: self.service.choose(self.snapshot.id, action, revision, identity))

    def end(self):
        return self._command('end', lambda revision, identity: self.service.end(self.snapshot.id, revision, identity))

    def skip(self):
        return self._command('skip', lambda revision, identity: self.service.skip(self.snapshot.id, revision, identity))

    def inherit(self):
        self.snapshot = self.service.inherit(self.snapshot.id)
        self.input_error = None
        return self.snapshot

    def pause(self):
        self.snapshot = self.service.pause(self.snapshot.id)
        return self.snapshot

    def resume(self):
        self.snapshot = self.service.resume(self.snapshot.id)
        return self.snapshot

    def edit(self):
        self.snapshot = self.service.begin_edit(self.snapshot.id)
        return self.snapshot


class TrainingView(ft.Column):
    def __init__(self, controller):
        super().__init__(spacing=16)
        self.controller = controller
        self.refresh_task = None
        self.choice_dialog = None
        self.render()

    def did_mount(self):
        if self.refresh_task is None:
            self.refresh_task = self.page.run_task(self.tick)

    def will_unmount(self):
        if self.refresh_task:
            self.refresh_task.cancel()
            self.refresh_task = None

    async def tick(self):
        try:
            while True:
                s = self.controller.refresh()
                self.timer.value = f'本组持续 {s.set_elapsed_ms // 1000} 秒'
                refresh_control(self.timer)
                await self.show_choice()
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            self.error.value = str(exc)
            refresh_control(self.error)

    async def invoke(self, action):
        try:
            action()
            self.render()
            refresh_control(self)
            await self.show_choice()
            if self.controller.snapshot.status == 'ended':
                await call(self.controller.on_changed, 'today')
        except Exception as exc:
            self.error.value = str(exc)
            refresh_control(self.error)

    async def show_choice(self):
        s = self.controller.snapshot
        if s.phase not in ('awaiting_choice', 'awaiting_selection') or self.choice_dialog:
            return
        actions = []
        async def choose(action):
            try:
                self.controller.choose(action)
                self.page.pop_dialog()
                self.choice_dialog = None
                self.render()
                refresh_control(self)
                if self.controller.snapshot.status == 'ended':
                    await call(self.controller.on_changed, 'today')
            except Exception as exc:
                self.choice_dialog.content = ft.Text(str(exc))
                self.choice_dialog.update()
        if s.current_slot_id:
            async def add(event): await choose('add_set')
            actions.append(ft.Button('添加下一组', on_click=add))
        if s.order and (not s.current_slot_id or s.current_slot_id != s.order[-1]):
            async def next_(event): await choose('next_exercise')
            actions.append(ft.Button('下一个动作', on_click=next_))
        async def end(event): await choose('end')
        actions.append(ft.TextButton('结束训练', on_click=end))
        async def dismissed(event):
            self.choice_dialog = None
        self.choice_dialog = ft.AlertDialog(modal=True, on_dismiss=dismissed, title=ft.Text('接下来做什么？'), content=ft.Text('请选择下一步；此处等待不计入本组时长。'),actions=actions)
        self.page.show_dialog(self.choice_dialog)

    def render(self):
        s = self.controller.snapshot
        slot = next((x for x in s.slots if x.id == s.current_slot_id), None)
        self.timer = ft.Text(f'本组持续 {s.set_elapsed_ms // 1000} 秒',size=20)
        self.error = ft.Text(color=ft.Colors.ERROR)
        if not slot:
            self.controls = [ft.Text('训练已结束' if s.status=='ended' else '请选择下一个动作',size=24),self.timer,self.error]
            return
        kind = slot.exercise.kind
        weight = ft.TextField(label='本组重量（kg）',value='' if s.draft.weight is None else str(s.draft.weight),visible=kind=='weighted',keyboard_type=ft.KeyboardType.NUMBER)
        reps = ft.TextField(label='本组次数',value='' if s.draft.reps is None else str(s.draft.reps),visible=kind!='timed',keyboard_type=ft.KeyboardType.NUMBER)
        duration = ft.TextField(label='动作时长（秒，手动记录）',value='' if s.draft.duration_seconds is None else str(s.draft.duration_seconds),visible=kind=='timed',keyboard_type=ft.KeyboardType.NUMBER)
        complete = ft.Button('完成本组',disabled=not self.controller.can_complete)
        async def changed(event):
            try:
                self.controller.update_inputs(weight.value or '',reps.value or '',duration.value or '')
                self.error.value = ''
            except Exception as exc:
                self.error.value = str(exc)
            complete.disabled = not self.controller.can_complete
            refresh_control(complete);refresh_control(self.error)
        for field in (weight,reps,duration):
            field.disabled = s.status!='running' or s.phase!='collecting'
            field.on_change = changed
        async def finish(event): await self.invoke(self.controller.complete)
        async def inherit(event): await self.invoke(self.controller.inherit)
        async def pause(event): await self.invoke(self.controller.pause if self.controller.snapshot.status=='running' else self.controller.resume)
        async def edit(event):
            from fitness.ui.training_edit import show_training_editor
            await show_training_editor(self)
        async def skip(event):
            await confirm(self.page,'跳过当前动作','未完成输入会舍弃，已完成组保留。',lambda:self.invoke(self.controller.skip))
        async def end(event):
            await confirm(self.page,'结束训练','已完成的组会保留，未完成的输入不会记为一组。',lambda:self.invoke(self.controller.end))
        complete.on_click = finish
        self.controls = [ft.Text(slot.exercise.name,size=28,weight=ft.FontWeight.BOLD),ft.Text(f'第 {s.set_index+1} 组'),
                         self.timer,ft.Text(s.notice or ''),weight,reps,duration,self.error,
                         ft.Row([ft.Button('继承上组数据',on_click=inherit,disabled=s.set_index==0 or s.status!='running' or s.phase!='collecting'),complete],wrap=True),
                         ft.Row([ft.TextButton('暂停' if s.status=='running' else '继续',on_click=pause),ft.TextButton('修改本次计划',on_click=edit),ft.TextButton('跳过当前动作',on_click=skip),ft.TextButton('结束训练',on_click=end)],wrap=True)]


def build_training(controller):
    return TrainingView(controller)
