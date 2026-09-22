import asyncio
import flet as ft
from fitness.domain.free_training import parse_measurements, validate_next_set
from fitness.ui.training import TrainingController
from fitness.ui.forms import refresh, call, card


class FreeTrainingController(TrainingController):
    def start_free(self):
        self.snapshot=self.service.start_free()
        return self.snapshot

    def restore(self):
        self.snapshot=self.service.restore_free()
        self.input_error=self.snapshot.input_error if self.snapshot else None
        return self.snapshot

    def _text(self):
        s=self.snapshot
        return (s.input_name if s.input_name is not None else s.action_name,
                s.input_reps if s.input_reps is not None else ('' if s.draft.reps is None else str(s.draft.reps)),
                s.input_weight if s.input_weight is not None else ('' if s.draft.weight is None else str(s.draft.weight)))

    def rename_current(self,name):
        if self.pending: raise ValueError('请先重试上次操作')
        _,reps,weight=self._text()
        self.snapshot=self.service.save_input_text(self.snapshot.id,name,reps,weight)
        self.input_error=self.snapshot.input_error
        return self.snapshot

    def update_inputs(self,weight,reps,duration=''):
        if self.pending: raise ValueError('请先重试上次操作')
        name,_,_=self._text()
        self.snapshot=self.service.save_input_text(self.snapshot.id,name,reps,weight)
        self.input_error=self.snapshot.input_error
        if self.input_error: raise ValueError(self.input_error)

    @property
    def can_complete(self):
        s=self.snapshot
        if not s or self.busy or self.input_error or s.status!='running' or not self._text()[0].strip():
            return False
        try: validate_next_set(s.draft)
        except ValueError: return False
        return True

    def advance(self,action):
        if self.input_error: raise ValueError(self.input_error)
        try:
            return self._command(action,lambda revision,identity:self.service.advance(self.snapshot.id,action,revision,identity))
        except ValueError:
            self.pending=None
            raise

    def begin_confirmation(self,action):
        if self.input_error: raise ValueError(self.input_error)
        if self.pending: raise ValueError('请先重试上次操作')
        self.snapshot=self.service.begin_confirmation(self.snapshot.id,action)
        return self.snapshot

    def cancel_confirmation(self):
        if self.pending:
            saved=self.service.command_result(self.snapshot.id,self.pending[2])
            self.pending=None
            if saved:
                self.snapshot=saved
                return saved
        self.snapshot=self.service.cancel_confirmation(self.snapshot.id)
        return self.snapshot


def duration(ms):
    seconds=ms//1000
    return f'{seconds//3600:02}:{seconds//60%60:02}:{seconds%60:02}'


class FreeTrainingView(ft.Column):
    def __init__(self,controller):
        super().__init__(spacing=16,horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.controller=controller
        self.refresh_task=None
        self.choice_dialog=None
        self.render()

    def did_mount(self):
        if self.refresh_task is None: self.refresh_task=self.page.run_task(self.tick)

    def will_unmount(self):
        if self.refresh_task: self.refresh_task.cancel();self.refresh_task=None

    async def tick(self):
        try:
            while True:
                s=self.controller.refresh()
                if s.notice and not self.controller.input_error:
                    self.error.value=s.notice
                    refresh(self.error)
                self.action_timer.value='动作时长  '+duration(s.action_elapsed_ms)
                self.set_timer.value='本组时长  '+duration(s.set_elapsed_ms)
                self.daily_timer.value='本日累计训练  '+duration(s.daily_elapsed_ms)
                refresh(self.action_timer);refresh(self.set_timer);refresh(self.daily_timer)
                await asyncio.sleep(1)
        except asyncio.CancelledError: pass
        except Exception as exc:
            self.error.value=str(exc);refresh(self.error)

    def sync_buttons(self):
        c=self.controller;s=c.snapshot
        self.next_set.disabled=not c.can_complete and not (c.pending and c.pending[0]=='next_set')
        self.inherit_button.disabled=not s.can_inherit or c.busy or bool(c.pending)
        self.pause_button.disabled=bool(c.pending)
        self.next_action.disabled=c.busy or bool(c.input_error) or bool(c.pending and c.pending[0]!='next_action')
        self.end_button.disabled=c.busy or bool(c.input_error) or bool(c.pending and c.pending[0]!='end')

    async def invoke(self,action):
        try:
            action()
            self.render();refresh(self)
            if self.controller.snapshot.status=='ended':
                await call(self.controller.on_changed,'records')
        except Exception as exc:
            self.error.value=str(exc);self.sync_buttons();refresh(self)

    async def ask(self,action):
        c=self.controller
        if c.pending:
            await self.invoke(lambda:c.advance(action));return
        try:
            c.begin_confirmation(action)
        except Exception as exc:
            self.error.value=str(exc);refresh(self.error);return
        accepted=False
        async def dismissed(event):
            if not accepted:
                c.cancel_confirmation()
            self.choice_dialog=None
            self.render();refresh(self)
        async def cancel(event):
            self.page.pop_dialog()
            await dismissed(event)
        async def accept(event):
            nonlocal accepted
            try:
                c.advance(action)
                accepted=True
                self.page.pop_dialog()
                self.choice_dialog=None
                self.render();refresh(self)
                if c.snapshot.status=='ended': await call(c.on_changed,'records')
            except Exception as exc:
                message.value=str(exc);refresh(message)
        message=ft.Text('已填写的本组数据会保存；两项都空则不记录。')
        dialog=ft.AlertDialog(modal=True,title=ft.Text('是否结束训练？' if action=='end' else '是否切换动作？'),
                              content=message,actions=[ft.TextButton('取消',on_click=cancel),ft.Button('确认',on_click=accept)],on_dismiss=dismissed)
        self.choice_dialog=dialog
        self.page.show_dialog(dialog)

    def render(self):
        c=self.controller;s=c.snapshot
        self.error=ft.Text(c.input_error or s.notice or '',color=ft.Colors.ERROR)
        self.name=ft.TextField(label='动作名称',value=c._text()[0])
        self.reps=ft.TextField(label='次数',value=c._text()[1],keyboard_type=ft.KeyboardType.NUMBER,expand=True)
        self.weight=ft.TextField(label='重量（kg）',value=c._text()[2],keyboard_type=ft.KeyboardType.NUMBER,expand=True)
        async def inputs(event):
            try:
                c.update_inputs(self.weight.value or '',self.reps.value or '')
                self.error.value=''
            except Exception as exc: self.error.value=str(exc)
            self.sync_buttons();refresh(self.error);refresh(self.next_set);refresh(self.next_action);refresh(self.end_button)
        async def rename(event):
            try:
                c.rename_current(self.name.value or '')
                self.error.value=''
            except Exception as exc: self.error.value=str(exc)
            self.sync_buttons();refresh(self.error);refresh(self.next_set)
        self.name.on_change=rename
        self.reps.on_change=self.weight.on_change=inputs
        async def inherit(event):await self.invoke(c.inherit)
        async def next_set(event):await self.invoke(lambda:c.advance('next_set'))
        async def next_action(event):await self.ask('next_action')
        async def end(event):await self.ask('end')
        async def pause(event):await self.invoke(c.pause if c.snapshot.status=='running' else c.resume)
        self.inherit_button=ft.OutlinedButton('继承数据',on_click=inherit,expand=True)
        self.next_set=ft.Button('下一组数',on_click=next_set,expand=True)
        self.next_action=ft.OutlinedButton('下一动作',on_click=next_action,expand=True)
        self.end_button=ft.OutlinedButton('结束训练',on_click=end,expand=True)
        self.pause_button=ft.TextButton('暂停' if s.status=='running' else '继续',on_click=pause)
        self.action_timer=ft.Text('动作时长  '+duration(s.action_elapsed_ms))
        self.set_timer=ft.Text('本组时长  '+duration(s.set_elapsed_ms))
        self.daily_timer=ft.Text('本日累计训练  '+duration(s.daily_elapsed_ms))
        self.controls=[ft.Row([ft.Text('自由训练',size=26,weight=ft.FontWeight.BOLD),self.pause_button],alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                       self.name,ft.Row([self.action_timer,self.set_timer],wrap=True,alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                       card(f'第 {s.set_index+1} 组',ft.Row([self.reps,self.weight])),self.error,
                       ft.Row([self.inherit_button,self.next_set]),ft.Row([self.next_action,self.end_button]),self.daily_timer]
        self.sync_buttons()
