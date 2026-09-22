from datetime import timedelta
import pytest
from fitness.services.weight import WeightService

def controller(service):
    from fitness.ui.free_training import FreeTrainingController
    c=FreeTrainingController(service);c.start_free();return c

def test_weight_today_not_selected_history(free_service,clock):
    from fitness.ui.records import RecordsController
    from fitness.services.records import RecordsService
    weight=WeightService(free_service.db,clock)
    c=RecordsController(RecordsService(free_service.db,clock),weight,clock)
    c.select_day(clock.today()-timedelta(days=1));c.save_today_weight(75)
    assert weight.read(clock.today())==75
    assert weight.read(c.selected_day) is None

def test_buttons_partial_and_cancel(free_service,clock):
    c=controller(free_service)
    c.rename_current('深蹲')
    c.update_inputs('','8','')
    assert not c.can_complete
    c.begin_confirmation('end')
    c.cancel_confirmation()
    assert c.snapshot.draft.reps==8 and c.snapshot.status=='running'
    c.update_inputs('0','8','')
    assert c.can_complete
    c.advance('next_set')
    assert c.snapshot.set_index==1 and c.snapshot.can_inherit

def test_lost_response_retries_same_command(free_service):
    c=controller(free_service);c.rename_current('深蹲');c.update_inputs('0','8','')
    original=free_service.advance
    def lost(*args):
        result=original(*args)
        free_service.advance=original
        raise OSError('response lost')
    free_service.advance=lost
    with pytest.raises(OSError):c.advance('next_set')
    c.advance('next_set')
    assert free_service.db.execute('SELECT COUNT(*) FROM training_set_results').fetchone()[0]==1

def test_view_controls_construct(free_service):
    from fitness.ui.free_training import FreeTrainingView
    c=controller(free_service)
    view=FreeTrainingView(c)
    assert view.next_set.disabled and view.inherit_button.disabled
    c.rename_current('深蹲');c.update_inputs('20','8','')
    view.sync_buttons()
    assert not view.next_set.disabled


def test_records_page_and_main_navigation(free_service,clock):
    from fitness.ui.app import AppServices
    from fitness.ui.records import build_records
    view=build_records(AppServices.create(free_service.db,clock))
    assert view.controls
    import flet as ft
    assert ft.Alignment.CENTER is not None


def test_dialog_cancel_and_timer_task_cleanup(free_service,monkeypatch):
    import asyncio
    from fitness.ui.free_training import FreeTrainingView
    class Page:
        def show_dialog(self,dialog):self.dialog=dialog
        def pop_dialog(self):pass
        def update(self,*args):pass
    page=Page()
    monkeypatch.setattr(FreeTrainingView,'page',property(lambda self:page))
    monkeypatch.setattr(FreeTrainingView,'update',lambda self:None)
    c=controller(free_service);c.rename_current('深蹲');c.update_inputs('','8','')
    view=FreeTrainingView(c)
    asyncio.run(view.ask('end'))
    asyncio.run(page.dialog.on_dismiss(None))
    assert c.snapshot.status=='running' and c.snapshot.draft.reps==8
    assert free_service.db.execute('SELECT COUNT(*) FROM training_set_results').fetchone()[0]==0
    class Task:
        cancelled=False
        def cancel(self):self.cancelled=True
    task=Task();view.refresh_task=task;view.will_unmount()
    assert task.cancelled and view.refresh_task is None
