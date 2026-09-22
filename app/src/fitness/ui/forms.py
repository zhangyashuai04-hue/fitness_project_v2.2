import inspect
import flet as ft


def refresh(control):
    try:
        control.page
    except RuntimeError:
        return
    control.update()


async def call(callback, *args):
    if callback:
        result = callback(*args)
        if inspect.isawaitable(result):
            await result


def card(title, *controls):
    return ft.Container(content=ft.Column([ft.Text(title, size=19, weight=ft.FontWeight.BOLD), *controls], spacing=12),
                        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW, border_radius=18, padding=18)


def build_weight_field(service, day, on_saved=None):
    current = service.read(day)
    field = ft.TextField(label='今日体重（kg）', value='' if current is None else str(round(current, 3)),
                         keyboard_type=ft.KeyboardType.NUMBER)
    saved = current
    async def save(event):
        nonlocal saved
        if not (field.value or '').strip():
            return
        try:
            value = float(field.value)
            if value != saved:
                service.save(day, value)
                saved = value
                await call(on_saved)
            field.error_text = None
        except Exception as exc:
            field.error_text = str(exc)
        refresh(field)
    field.on_submit = field.on_blur = field.on_tap_outside = save
    return field


async def confirm(page, title, body, action):
    async def cancel(event):
        page.pop_dialog()
    async def accept(event):
        try:
            await call(action)
            page.pop_dialog()
        except Exception as exc:
            dialog.content = ft.Text(str(exc))
            dialog.update()
    dialog = ft.AlertDialog(modal=True, title=ft.Text(title), content=ft.Text(body),
                            actions=[ft.TextButton('取消', on_click=cancel), ft.Button('确认', on_click=accept)])
    page.show_dialog(dialog)
