from test_training import training,new_plan,complete
from fitness.services.training import TrainingService

def test_pause_choice_and_restart_time(training,new_plan,clock,db):
    snap=training.start(new_plan)
    clock.advance_ms(5000)
    paused=training.pause(snap.id)
    assert paused.set_elapsed_ms==5000
    clock.advance_ms(9000)
    assert training.get(snap.id).set_elapsed_ms==5000
    training.resume(snap.id)
    clock.advance_ms(3000)
    recovered=TrainingService(db,clock).restore_active()
    assert recovered.set_elapsed_ms==8000
    saved=complete(training,recovered)
    clock.advance_ms(15000)
    assert training.get(snap.id).set_elapsed_ms==8000
    next_=training.choose(snap.id,'add_set',saved.revision,'next')
    assert next_.set_elapsed_ms==0
    clock.advance_ms(2000)
    assert training.get(snap.id).set_elapsed_ms==2000

def test_clock_backwards_never_negative(training,new_plan,clock):
    snap=training.start(new_plan)
    clock.advance_ms(-5000)
    result=training.get(snap.id)
    assert result.set_elapsed_ms==0
    assert result.notice
