# iOS 云端模拟器验证

这是独立测试包，不会改动安卓业务或朋友的 Mac 系统。不需要 Apple Developer Program、Apple ID 或签名密钥。

## 启动

工作流文件需要先合并到仓库默认分支 `codex/v22-free-training`，GitHub 才会显示手动入口。
在仓库 Actions → iOS Simulator Check → Run workflow 中选择待测试分支并运行。
只有 workflow_dispatch，不会因 push 或 PR 自动运行。标准 macos-26 运行器，60分钟超时，产物保留7天。

## 输出与判读

运行页 Artifacts 下载 `ios-simulator-运行编号-尝试次数`：
- toolchain.txt：实际 macOS/Xcode/Python 版本。
- tests.log/tests.xml：Python 回归测试。
- build.log：Flet 编译日志。
- fitness-ios-simulator.tar.gz：保留执行权限的模拟器 .app 包。
- launch.png：启动20秒后的截图，需要看到“记录 / 训练 / 我的”和记录页内容。
- launch.txt/processes.txt/simulator.log/result.json：启动信息与进程存活证据。

只有进程存在不能证明 Python 界面成功，必须检查截图与日志。不存在可用 iPhone 模拟器时流程失败并明确注明未验证启动；先前生成的包仍保留。
截图正常也不证明训练、文件选择、数据恢复或真机全部可用，后续需交互验证。
模拟器包不能直接安装到 iPhone，也不保证能在朋友 macOS 14.1.1 的旧模拟器运行。

## 实现

从 app/pyproject.toml、requirements-build.lock.txt 安装固定依赖，使用 Flet 0.86.5 CLI 构建；不依赖 scripts/toolchain.ps1 的 Windows 路径。
测试包名 com.example.fitness.iosprobe。不要把个人数据库和签名材料加到仓库或产物中。
云端日志、产物与仓库可见性一致。实体机签名/TestFlight为下一阶段，尚未配置。

## 本地验证

Windows：`.venv\Scripts\python.exe -m pytest -q`。
真正编译与 simctl 检查必须在 macOS 执行。Windows 通过测试仅证明 Python 逻辑和配置静态检查，不表示 iOS 构建通过。

## 交互验证扩展

新增苹果 XCTest 测试工具，只用于云端自动点击，应用业务仍为 Python。覆盖训练完整组/部分组、继承、切换确认及取消、暂停杀进程恢复、记录与今日体重；另外检查原生备份导入/导出选择器打开和取消。
备份选择器通过不等于文件导出与恢复内容通过，完整备份往返仍需后续核查。
结果见 interactions-summary.json、interactions.xcresult 和 interaction-attachments 中的截图/控件树。

可选 reuse_build_run 输入之前成功的本仓库构建编号；脚本严格比较 app 与锁定依赖未变，并校验产物哈希。源代码变更时拒绝复用，应留空重新构建。旧产物过期时也需要重建。

首次交互运行发现 iOS 数字键盘不提供小数点及完成键，遮挡底部导航。已将 iOS 的体重、训练重量和次数输入改为标准键盘（可输入小数并提交关闭）；Android 保持数字键盘。此修复必须重新构建，不能复用之前安装包。
