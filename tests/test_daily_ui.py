import asyncio
from datetime import date
from unittest.mock import Mock
from fitness.ui.forms import build_weight_field
from fitness.ui.nutrition import build_food_form

def test_weight_three_events_save_once():
    service=Mock()
    service.read.return_value=None
    field=build_weight_field(service,date(2026,10,1))
    field.value='75.2'
    asyncio.run(field.on_tap_outside(None))
    asyncio.run(field.on_blur(None))
    asyncio.run(field.on_submit(None))
    service.save.assert_called_once_with(date(2026,10,1),75.2)

def test_weight_failure_keeps_editable_value():
    service=Mock()
    service.read.return_value=None
    service.save.side_effect=ValueError('保存失败')
    field=build_weight_field(service,date(2026,10,1))
    field.value='75.2'
    asyncio.run(field.on_submit(None))
    assert field.value=='75.2'
    assert field.error_text

def test_food_can_save_without_grams():
    service=Mock()
    form=build_food_form(service,date(2026,10,1))
    name,calories,grams=form.controls[:3]
    button=form.controls[-1]
    name.value='米饭';calories.value='230';grams.value=''
    asyncio.run(calories.on_change(None))
    assert button.disabled is False
    asyncio.run(button.on_click(None))
    service.save_food.assert_called_once_with(date(2026,10,1),'米饭',230.0,None,food_id=None)

def test_daily_plan_and_records_views_construct_with_migrated_data(db,clock):
    from fitness.ui.app import AppServices
    from fitness.ui.today import build_today
    from fitness.ui.plans import build_plans
    from fitness.ui.records import build_records
    from fitness.ui.settings import build_settings
    import flet as ft
    services=AppServices.create(db,clock)
    assert build_today(services,clock.today(),Mock()).controls
    assert build_plans(services,Mock()).controls
    assert build_records(services).controls
    assert build_settings(Mock(theme_mode=ft.ThemeMode.LIGHT)).controls

def test_today_offers_previous_day_active_session(db,clock):
    from fitness.ui.app import AppServices
    from fitness.ui.today import build_today
    import flet as ft
    callback=Mock()
    view=build_today(AppServices.create(db,clock),date(2026,10,1),callback)
    def walk(control):
        yield control
        for child in getattr(control,'controls',[]) or []:yield from walk(child)
        content=getattr(control,'content',None)
        if isinstance(content,ft.Control):yield from walk(content)
    buttons=[c for c in walk(view) if isinstance(c,ft.Button) and c.content=='继续未结束训练']
    assert len(buttons)==1
    asyncio.run(buttons[0].on_click(None))
    assert callback.call_args.args[0]=='resume'
