import flet as ft
from fitness.ui.app import AppServices
from fitness.ui.free_training import FreeTrainingController, FreeTrainingView
from fitness.ui.records import build_records


def weight_field(view):
    return view.controls[-1].content.controls[1]


def test_ios_weight_keyboard_allows_decimal_and_submit(free_service, clock):
    services = AppServices.create(free_service.db, clock)
    field = weight_field(build_records(services, platform=ft.PagePlatform.IOS))
    assert field.keyboard_type == ft.KeyboardType.TEXT
    assert field.on_submit is not None


def test_ios_training_uses_dismissible_keyboard_after_render(free_service):
    c = FreeTrainingController(free_service); c.start_free()
    view = FreeTrainingView(c, platform=ft.PagePlatform.IOS)
    view.render()
    assert view.reps.keyboard_type == ft.KeyboardType.TEXT
    assert view.weight.keyboard_type == ft.KeyboardType.TEXT


def test_android_keeps_numeric_keyboard(free_service, clock):
    services = AppServices.create(free_service.db, clock)
    field = weight_field(build_records(services, platform=ft.PagePlatform.ANDROID))
    c = FreeTrainingController(free_service); c.start_free()
    view = FreeTrainingView(c, platform=ft.PagePlatform.ANDROID)
    assert field.keyboard_type == view.reps.keyboard_type == view.weight.keyboard_type == ft.KeyboardType.NUMBER
