from unittest.mock import Mock
import pytest
from test_training import training,new_plan
from fitness.ui.training import TrainingController
from fitness.domain.models import Measurements

def test_empty_then_valid_then_paused(training,new_plan):
    controller=TrainingController(training)
    controller.start(new_plan)
    assert controller.snapshot.draft==Measurements()
    assert not controller.can_complete
    controller.update_inputs('40','10','')
    assert controller.can_complete
    controller.pause()
    assert not controller.can_complete

def test_save_failure_retains_inputs_and_retry_command(training,new_plan):
    controller=TrainingController(training)
    controller.start(new_plan)
    controller.update_inputs('40','10','')
    original=training.complete
    calls=[]
    def uncertain(*args):
        calls.append(args)
        result=original(*args)
        if len(calls)==1:raise OSError('result lost')
        return result
    training.complete=uncertain
    with pytest.raises(OSError):controller.complete()
    assert controller.snapshot.draft.weight==40
    controller.complete()
    assert calls[0]==calls[1]
    assert controller.snapshot.phase=='awaiting_choice'
    controller.complete()
    assert len(calls)==2

def test_recover_pending_choice(training,new_plan):
    controller=TrainingController(training)
    controller.start(new_plan)
    controller.update_inputs('40','10','')
    controller.complete()
    recovered=TrainingController(training)
    recovered.refresh(controller.snapshot.id)
    assert recovered.snapshot.phase=='awaiting_choice'

def test_view_constructs_and_unmount_cancels_task(training,new_plan):
    from fitness.ui.training import build_training
    controller=TrainingController(training)
    controller.start(new_plan)
    view=build_training(controller)
    task=Mock()
    view.refresh_task=task
    view.will_unmount()
    task.cancel.assert_called_once()
    assert view.refresh_task is None

def test_dismissed_choice_is_presented_again(training,new_plan,monkeypatch):
    import asyncio
    from fitness.ui.training import TrainingView
    controller=TrainingController(training)
    controller.start(new_plan);controller.update_inputs('40','10','');controller.complete()
    page=Mock()
    monkeypatch.setattr(TrainingView,'page',property(lambda self:page))
    view=TrainingView(controller)
    asyncio.run(view.show_choice())
    dialog=view.choice_dialog
    assert callable(dialog.on_dismiss)
    asyncio.run(dialog.on_dismiss(None))
    asyncio.run(view.show_choice())
    assert page.show_dialog.call_count==2
