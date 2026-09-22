import asyncio
import pytest
from fitness.ui.free_training import FreeTrainingController,FreeTrainingView
from fitness.domain.models import Measurements

def controller(service):
    c=FreeTrainingController(service);c.start_free();return c

def test_validation_failure_does_not_lock_commands(free_service):
    c=controller(free_service);c.update_inputs('0','8','')
    c.begin_confirmation('end')
    with pytest.raises(ValueError):c.advance('end')
    c.cancel_confirmation()
    c.rename_current('深蹲')
    c.begin_confirmation('end');c.advance('end')
    assert c.snapshot.status=='ended'

def test_invalid_and_blank_name_survive_pause_and_restore(free_service):
    c=controller(free_service);c.rename_current('深蹲');c.update_inputs('20','8','');c.advance('next_set')
    c.rename_current('')
    c.update_inputs('20','8','')
    assert not c.can_complete
    with pytest.raises(ValueError):c.advance('next_set')
    c.rename_current('深蹲')
    with pytest.raises(ValueError):c.update_inputs('20','0','')
    c.pause()
    restored=FreeTrainingController(free_service);restored.restore()
    view=FreeTrainingView(restored)
    assert view.reps.value=='0' and not restored.can_complete

def test_unedited_weight_blur_does_not_rewrite_units(free_service,clock):
    from fitness.ui.app import AppServices
    from fitness.ui.records import build_records
    free_service.db.execute("INSERT INTO gym_sets(name,reps,weight,unit,created) VALUES ('Weight',0,100,'lb',?)",(clock.now_ms()//1000,))
    services=AppServices.create(free_service.db,clock)
    view=build_records(services)
    field=view.controls[-1].content.controls[1]
    before=free_service.db.total_changes
    asyncio.run(field.on_blur(None))
    assert free_service.db.total_changes==before
    assert free_service.db.execute("SELECT weight,unit FROM gym_sets WHERE name='Weight'").fetchone()[:]==(100,'lb')

def test_clock_rollback_after_observed_progress_freezes(free_service,clock):
    s=free_service.start_free();clock.advance_ms(10000)
    assert free_service.get(s.id).set_elapsed_ms==10000
    clock.advance_ms(-5000)
    s=free_service.get(s.id)
    assert s.set_elapsed_ms==10000 and s.notice


def test_cancel_after_lost_end_response_reconciles(free_service):
    c=controller(free_service);c.rename_current('深蹲');c.update_inputs('20','8','')
    c.begin_confirmation('end')
    original=free_service.advance
    def lost(*args):
        original(*args)
        raise OSError('lost response')
    free_service.advance=lost
    with pytest.raises(OSError):c.advance('end')
    c.cancel_confirmation()
    assert c.snapshot.status=='ended' and c.pending is None
    assert free_service.db.execute('SELECT COUNT(*) FROM training_set_results').fetchone()[0]==1


def test_clock_warning_reaches_visible_timer_view(free_service,clock,monkeypatch):
    import fitness.ui.free_training as ui
    c=controller(free_service);view=FreeTrainingView(c)
    clock.advance_ms(10000);free_service.get(c.snapshot.id);clock.advance_ms(-5000)
    monkeypatch.setattr(ui,'refresh',lambda control:None)
    async def stop_after_refresh(seconds):raise asyncio.CancelledError()
    monkeypatch.setattr(ui.asyncio,'sleep',stop_after_refresh)
    asyncio.run(view.tick())
    assert '系统时间' in view.error.value
