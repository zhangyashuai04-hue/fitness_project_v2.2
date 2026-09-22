import os
from pathlib import Path
import flet as ft
from fitness.domain.clock import Clock
from fitness.storage.paths import resolve_database
from fitness.storage.migrations import initialize
from fitness.storage.database import open_database
from fitness.ui.app import AppServices
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
        await navigate('records')
    body=ft.Column(expand=True,horizontal_alignment=ft.CrossAxisAlignment.STRETCH,scroll=ft.ScrollMode.AUTO,spacing=16)
    async def navigate(destination,identity=None):
        try:
            if destination=='training':
                from fitness.ui.free_training import FreeTrainingController,FreeTrainingView
                controller=FreeTrainingController(services.training,navigate)
                active=controller.restore()
                async def start(event):
                    controller.start_free()
                    body.controls=[FreeTrainingView(controller)]
                    page.update()
                async def resume(event):
                    body.controls=[FreeTrainingView(controller)]
                    page.update()
                control=ft.Container(content=ft.Column([
                    ft.Text('按自己的节奏训练',size=24,weight=ft.FontWeight.BOLD),
                    ft.Text('输入动作，逐组记录次数与重量。'),
                    ft.Button('继续训练' if active else '开始训练',on_click=resume if active else start)
                ],horizontal_alignment=ft.CrossAxisAlignment.CENTER,spacing=24),padding=ft.Padding.symmetric(vertical=80),alignment=ft.Alignment.CENTER)
            elif destination=='records':
                from fitness.ui.records import build_records
                control=build_records(services)
            else:
                control=build_settings(page,build_backup(backup_service,restore))
            page.navigation_bar.selected_index=['records','training','settings'].index(destination)
            body.controls=[control]
            page.update()
        except Exception as exc:
            page.show_dialog(ft.AlertDialog(title=ft.Text('暂时无法完成操作'),content=ft.Text(str(exc))))
    async def changed(event):
        await navigate(['records','training','settings'][event.control.selected_index])
    page.navigation_bar=ft.NavigationBar(selected_index=0,on_change=changed,destinations=[
        ft.NavigationBarDestination(icon=ft.Icons.HISTORY,label='记录'),
        ft.NavigationBarDestination(icon=ft.Icons.FITNESS_CENTER,label='训练'),
        ft.NavigationBarDestination(icon=ft.Icons.PERSON,label='我的')])
    page.add(ft.SafeArea(content=body,expand=True))
    await navigate('records')


if __name__=='__main__':
    ft.run(main)
