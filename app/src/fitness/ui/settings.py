from pathlib import Path
import flet as ft
from fitness.ui.forms import card


def build_settings(page, backup_control=None):
    async def theme(event):
        page.theme_mode=ft.ThemeMode.DARK if event.control.value else ft.ThemeMode.LIGHT
        page.update()
    async def licenses(event):
        text='\n\n'.join(path.name+'\n'+path.read_text(encoding='utf-8') for path in sorted((Path(__file__).parents[1]/'licenses').glob('*.txt')))
        async def close(event):page.pop_dialog()
        page.show_dialog(ft.AlertDialog(title=ft.Text('开源许可'),content=ft.Column([ft.Text(text,selectable=True)],scroll=ft.ScrollMode.AUTO,width=460,height=450),actions=[ft.TextButton('关闭',on_click=close)]))
    return ft.Column([card('我的',ft.Text('数据保存在这台设备本地，没有账号登录或云端同步。')),
                      card('备份与恢复',backup_control or ft.Text('备份不可用')),
                      card('显示',ft.Switch(label='深色模式',value=page.theme_mode==ft.ThemeMode.DARK,on_change=theme)),
                      card('开源信息',ft.Text('界面框架：Flet（Apache-2.0）\n数据兼容：基于旧版 Flexify 数据结构\n业务实现：Python + SQLite'),ft.TextButton('查看许可证',on_click=licenses))],spacing=16,horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
