import flet as ft
from fitness.domain.validation import finite_number
from fitness.ui.forms import call, refresh, card


def build_food_form(service, day, food=None, on_saved=None):
    food = food or {}
    name = ft.TextField(label='食物名称', value=food.get('name', ''))
    calories = ft.TextField(label='总热量（kcal）', value=str(food.get('calories', '')), keyboard_type=ft.KeyboardType.NUMBER)
    grams = ft.TextField(label='重量（g，选填）', value='' if food.get('grams') is None else str(food['grams']), keyboard_type=ft.KeyboardType.NUMBER)
    error = ft.Text(color=ft.Colors.ERROR)
    button = ft.Button('保存饮食', disabled=True)
    def values():
        if not (name.value or '').strip():
            raise ValueError('请输入食物名称')
        energy = float(calories.value)
        weight = float(grams.value) if (grams.value or '').strip() else None
        finite_number(energy)
        if weight is not None:
            finite_number(weight, positive=True)
        return name.value.strip(), energy, weight
    async def changed(event):
        try:
            values()
            button.disabled = False
        except (ValueError, TypeError):
            button.disabled = True
        refresh(button)
    async def save(event):
        try:
            text, energy, weight = values()
            service.save_food(day, text, energy, weight, food_id=food.get('id'))
            error.value = '已保存'
            await call(on_saved)
        except Exception as exc:
            error.value = str(exc)
        refresh(error)
    for field in (name, calories, grams):
        field.on_change = changed
    button.on_click = save
    try:
        values()
        button.disabled = False
    except (ValueError, TypeError):
        pass
    return ft.Column([name, calories, grams, error, button], tight=True)


def build_nutrition(service, day, on_changed=None):
    column = ft.Column(spacing=14)
    async def saved():
        rebuild()
        refresh(column)
        await call(on_changed)
    def rebuild():
        summary = service.summary(day)
        expenditure = ft.TextField(label='全天消耗（kcal，选填）', value='' if summary['expenditure'] is None else str(summary['expenditure']))
        status = ft.Text()
        async def save_expenditure(event):
            try:
                service.save_expenditure(day, float(expenditure.value))
                await saved()
            except Exception as exc:
                status.value = str(exc)
                refresh(status)
        column.controls = [ft.Text(str(day), size=20), card('添加饮食', build_food_form(service, day, on_saved=saved)),
                           card('全天消耗', expenditure, ft.Button('保存消耗', on_click=save_expenditure), status)]
        for food in service.foods(day):
            column.controls.append(card(food['name'], build_food_form(service, day, food, saved)))
    rebuild()
    return column
