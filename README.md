# 健身记录 v2.2

在Python v2.1的Flet/SQLite代码上迭代。应用业务和界面代码位于app/src，Android运行壳由Flet构建工具生成。

## 功能

- 记录：按日期查看训练动作、组数和次数×重量；今日体重直接输入，仅保留体重趋势。
- 训练：直接开始、输入动作；继承当前动作上一组、下一组、下一动作、结束训练；暂停及退出恢复。
- 我的：本地备份/恢复、显示和许可证。

下一组须完整填写次数和重量；下一动作/结束须确认，只填一项也保存，两项都空不记录。历史只读。没有饮食、模板或计划入口。

## 环境和运行

本目录已建立独立.venv。PowerShell进入此目录后：

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\flet.exe run app/src/main.py
powershell -NoProfile -ExecutionPolicy Bypass -File .\scriptsuild-app.ps1
```

全新环境先执行 `python -m venv .venv`，再用虚拟环境pip安装requirements-build.lock.txt。Android脚本复用本机已有SDK/Flutter/JDK及兼容签名；更换电脑时需修改scripts/toolchain.ps1与tool-shims路径。不要提交签名密钥或用户数据库。

## 代码入口

- app/src/main.py：启动和三页导航。
- app/src/fitness/ui/free_training.py：训练界面和控制器。
- app/src/fitness/services/free_training.py：自由训练、计时、恢复。
- app/src/fitness/ui/records.py：按日记录和体重。
- app/src/fitness/storage/migrations.py：v58/v59到v60迁移。

保留旧服务和旧界面文件以复用兼容逻辑及回归测试；main.py只连接v2.2新入口。数据库兼容不等于跨设备同步。

设计和实施计划在docs/superpowers；审查及实测结果见docs/v2.2-review.md和docs/v2.2-validation.md。APK生成后位于deliverables。
