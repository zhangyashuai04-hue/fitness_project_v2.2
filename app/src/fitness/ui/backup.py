from pathlib import Path
from uuid import uuid4
import flet as ft
from fitness.ui.forms import refresh,confirm


def build_backup(service,on_restore):
    status=ft.Text()
    root=ft.Column()
    async def export(event):
        try:
            service.backup_dir.mkdir(parents=True,exist_ok=True)
            temporary=service.backup_dir/f'export-{uuid4().hex}.sqlite'
            service.export(temporary)
            data=temporary.read_bytes()
            picker=ft.FilePicker()
            result=await picker.save_file(file_name='fitness-backup.sqlite',src_bytes=data)
            if result and root.page.platform not in (ft.PagePlatform.ANDROID,ft.PagePlatform.IOS):
                Path(result).write_bytes(data)
            status.value='备份导出完成' if result else '已取消导出'
        except Exception as exc:
            status.value=str(exc)
        refresh(status)
    async def choose(event):
        try:
            files=await ft.FilePicker().pick_files(allow_multiple=False,with_data=True)
            if not files:return
            selected=files[0]
            if selected.path:
                source=Path(selected.path)
            elif selected.bytes:
                service.backup_dir.mkdir(parents=True,exist_ok=True)
                source=service.backup_dir/f'import-{uuid4().hex}.sqlite'
                source.write_bytes(selected.bytes)
            else:raise ValueError('无法读取所选文件')
            async def restore():
                await on_restore(source)
            await confirm(root.page,'恢复本地备份','当前记录会先另存备份，再替换为所选文件中的记录。',restore)
        except Exception as exc:
            status.value=str(exc);refresh(status)
    root.controls=[ft.Text('备份包含本地训练、体重及旧版本保留数据，请妥善保存。'),ft.Row([ft.Button('导出备份',on_click=export),ft.Button('恢复备份',on_click=choose)],wrap=True),status]
    return root
