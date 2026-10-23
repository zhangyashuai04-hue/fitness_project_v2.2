from datetime import timedelta
from fitness.services.records import RecordsService
from fitness.domain.models import Measurements

def test_training_days_unique_sorted_and_empty(free_service, clock):
    records=RecordsService(free_service.db,clock)
    assert records.training_days()==[]
    first=clock.today()
    for offset in (0,0,2):
        if offset: clock.advance_ms(offset*86400000)
        s=free_service.start_free()
        free_service.rename_current(s.id,"Squat")
        s=free_service.save_draft(s.id,Measurements(reps=8))
        free_service.advance(s.id,'end',s.revision,s.id)
    assert records.training_days()==[first+timedelta(days=2),first]

def test_legacy_dates_exclude_weight_hidden(free_service,clock):
    from fitness.services.weight import day_bounds
    today=clock.today()
    for name,hidden,offset in [('Weight',0,0),('Squat',1,1),('Bench',0,2)]:
        free_service.db.execute('INSERT INTO gym_sets(name,reps,weight,unit,created,hidden) VALUES (?,8,20,"kg",?,?)',(name,day_bounds(today-timedelta(days=offset))[0],hidden))
    r=RecordsService(free_service.db,clock)
    assert r.training_days()==[today-timedelta(days=2)]


def test_ios_date_navigation_preserves_weight(free_service,clock):
    import asyncio
    import flet as ft
    from fitness.ui.app import AppServices
    from fitness.ui.records import build_records
    s=free_service.start_free()
    free_service.rename_current(s.id,'Squat')
    s=free_service.save_draft(s.id,Measurements(reps=8))
    free_service.advance(s.id,'end',s.revision,s.id)
    root=build_records(AppServices.create(free_service.db,clock),platform=ft.PagePlatform.IOS)
    weight=root.controls[2]
    dates=root.controls[1].content.controls[1]
    assert len(dates.controls)==1
    assert dates.controls[0].content==clock.today().isoformat()
    asyncio.run(dates.controls[0].on_click(None))
    assert root.controls[1].value.endswith(clock.today().isoformat())
    assert any('Squat' in (getattr(c,'value','') or '') for c in root.controls[2].controls)
    asyncio.run(root.controls[0].on_click(None))
    assert root.controls[2] is weight

