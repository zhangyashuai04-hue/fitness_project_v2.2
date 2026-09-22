import os
from pathlib import Path
import flet as ft
from fitness.domain.clock import Clock
from fitness.storage.paths import resolve_database
from fitness.storage.migrations import initialize
from fitness.storage.database import open_database
from fitness.ui.app import AppServices
from fitness.ui.today import build_today
from fitness.ui.plans import build_plans
from fitness.ui.nutrition import build_nutrition
from fitness.ui.settings import build_settings


async def main(page):
    page.title='健身记录'
    page.theme=ft.Theme(color_scheme_seed=ft.Colors.TEAL)
    page.theme_mode=ft.ThemeMode.LIGHT
    page.padding=16
    clock=Clock()
    android=page.platform==ft.PagePlatform.ANDROID
    storage=Path(os.environ.get('FLET_APP_STORAGE_DATA',str(Path(__file__).resolve().parents[2]/'.data')))
    try:
        path=resolve_database(storage,android=android)
        initialize(path,storage/'backups')
        db=open_database(path)
    except Exception as exc:
        page.add(ft.Text('本地数据暂时无法打开',size=24),ft.Text(str(exc)),ft.Text('请保留应用数据，排查后重新打开。'))
        return
    services=AppServices.create(db,clock)
    from fitness.services.backup import BackupService
    from fitness.ui.backup import build_backup
    backup_service=BackupService(path,storage/'backups')
    async def restore(source):
        nonlocal db,services
        active=services.training.restore_active()
        if active:
            raise ValueError('请先结束当前训练再恢复备份')
        db.close()
        try:
            backup_service.restore(source)
        finally:
            db=open_database(path)
            services=AppServices.create(db,clock)
        await navigate('today')
    body=ft.Column(expand=True,horizontal_alignment=ft.CrossAxisAlignment.STRETCH,scroll=ft.ScrollMode.AUTO,spacing=16)
    async def navigate(destination,identity=None):
        try:
            if destination=='today':
                control=build_today(services,clock.today(),navigate)
            elif destination=='plans':
                async def start(plan_id):
                    await navigate('start',plan_id)
                control=build_plans(services,start)
            elif destination=='nutrition':
                control=build_nutrition(services.nutrition,clock.today())
            elif destination in ('start','resume'):
                from fitness.ui.training import build_training, TrainingController
                controller=TrainingController(services.training,navigate)
                if destination=='resume':controller.refresh(identity)
                else:controller.start(identity)
                control=build_training(controller)
            elif destination=='records':
                from fitness.ui.records import build_records
                control=build_records(services)
            else:
                control=build_settings(page,build_backup(backup_service,restore))
            body.controls=[control]
            page.update()
        except Exception as exc:
            page.show_dialog(ft.AlertDialog(title=ft.Text('暂时无法完成操作'),content=ft.Text(str(exc))))
    async def changed(event):
        await navigate(['today','plans','records','settings'][event.control.selected_index])
    page.navigation_bar=ft.NavigationBar(selected_index=0,on_change=changed,destinations=[
        ft.NavigationBarDestination(icon=ft.Icons.TODAY,label='今日'),
        ft.NavigationBarDestination(icon=ft.Icons.FITNESS_CENTER,label='训练'),
        ft.NavigationBarDestination(icon=ft.Icons.SHOW_CHART,label='记录'),
        ft.NavigationBarDestination(icon=ft.Icons.PERSON,label='我的')])
    page.add(ft.SafeArea(content=body,expand=True))
    await navigate('today')


if __name__=='__main__':
    ft.run(main)
