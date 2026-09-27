# iPhone 真机包与安装步骤

## 本次构建的用途

云端 macOS 生成真机 arm64 的 Release 归档，再将其中的应用整理为 `Payload/*.app` 结构的 `fitness-v2.2-ios-unsigned.ipa`，供安装工具重新签名。
这不是已经签名、直接点击就能安装的 IPA，也不是 App Store / TestFlight 发布。
无需改动朋友的 macOS；云端构建不使用 Apple ID、签名证书或开发者会员。
实体 iPhone 16 / iOS 26.5 的安装、签名与运行效果仍需要在手机上验证。

## 在 GitHub 生成

Actions → iOS Build and Test → Run workflow，选择包含本修改的分支。
若默认分支尚未合并修改，工作流可能仍显示旧名称 iOS Simulator Check，需通过 API 对修改分支发起运行。
设置 `target=device-unsigned`，`reuse_build_run` 留空。模拟器包不能复用为真机包。
构建完成后下载 `ios-device-运行编号-尝试次数`，其中包含：

- `fitness-v2.2-ios-unsigned.ipa`：待签名真机包。
- `fitness-v2.2-ios-unsigned.json`：包名、版本、arm64 架构、最低系统版本、SHA256。
- `fitness-ios-xcarchive.tar.gz`：原始 Xcode 归档，可在后续配置签名后使用。
- `toolchain.txt`、`build.log`、`tests.log`：实际环境与测试记录。

云端验证归档的 iPhoneOS 平台、主可执行文件的 arm64 / IOS 构建目标以及 IPA 的 ZIP 完整性。
构建成功只证明真机包生成成功，不代表已经在实体手机运行。

## 免费测试安装：Windows + AltStore Classic

以下为待用户选择的安装路线；没有自动安装 AltServer，也没有自动使用任何 Apple 账号。
普通账号安装的应用需要定期刷新签名，通常为 7 天。AltStore 自身也占用可安装应用名额。
依据官方指南操作，具体界面及 iOS 26.5 兼容结果以当前安装工具和手机实际结果为准。

1. 按 [AltStore Windows 官方指南](https://faq.altstore.io/altstore-classic/how-to-install-altstore-windows) 安装所需的 iTunes、iCloud 和 AltServer。官网对 Microsoft Store 版有特别要求，已有安装时先核对官方说明。
2. 用数据线连接 iPhone，解锁并信任电脑；按指南设置 iTunes 的 Wi-Fi 同步。
3. 在 Windows 托盘打开 AltServer，选择 Install AltStore → 自己的 iPhone。Apple ID、密码和验证码由你在工具或苹果界面内输入，不发送到聊天或 GitHub。
4. 在手机设置中按提示信任开发者，并启用“隐私与安全 → 开发者模式”；如提示重启，按手机提示完成。
5. 将 `fitness-v2.2-ios-unsigned.ipa` 放到 iPhone“文件”中，在 AltStore 的 My Apps 中导入该 IPA，等待工具签名和安装。此时电脑上的 AltServer 保持运行。
6. 安装后先创建测试体重和训练，确认键盘、暂停继续、退出恢复、备份导出与恢复都正常，再导入自己的正式数据。
7. 定期在 AltStore 刷新签名，使用同一个 Apple ID 和应用身份更新。更新前导出备份；不要通过卸载应用来处理签名过期，以免丢失本地数据。

签名周期与刷新方式见 [AltStore 官方说明](https://faq.altstore.io/altstore-classic/your-altstore)。

## 数据迁移

数据仍保存在各设备本地，安卓与 iPhone 不会自动同步。
需要在旧设备“我的 → 导出备份”，将备份文件传到 iPhone，再在新应用“我的 → 恢复备份”选择文件并确认。
恢复会替换当前数据，先保存好两边备份。已验证 iOS 模拟器中 v2.2 的完整备份往返；尚未逐一验证所有 Dart/v2.1 历史备份在实体 iPhone 上的导入，正式迁移前保留原文件与原设备。

## 付费开发者路线

若后来加入 Apple Developer Program，可配置证书与 provisioning profile，使用 Xcode 归档导出或重新执行已配置签名的 Flet 构建。TestFlight / App Store 发布是独立步骤，本工作流不包含发布动作。
官方构建与签名说明：[Flet iOS 打包](https://flet.dev/docs/publish/ios/)。

## 首次云端构建结果

云端运行：https://github.com/zhangyashuai04-hue/fitness_project_v2.2/actions/runs/36334899189
测试提交：7087744bc456f84691e286dc1042141c96ff14c0。

- macOS 26.6.2 / Xcode 26.6 / Python 3.12 云端编译成功。
- Python 回归测试 181 通过；打包脚本代码审查无阻断问题。
- 生成 v2.2.0、build 6 的 iPhoneOS / arm64 归档和待重新签名 IPA，大小 28,799,500 字节（约 28.8 MB）。
- 包标识 io.github.zhangyashuai04hue.fitness。归档的最低 iOS 字段为 13.0，此字段不代表已测试全部系统版本。
- 本机已校验整个 GitHub 产物 ZIP 和 IPA 的 SHA256，并检查 IPA ZIP 完整性、主程序 arm64 Mach-O 头、iPhoneOS 平台、可执行权限和 Payload 结构。
- IPA SHA256：50a352dcca4b3174f8a97ab3d32e286873e41ba09f1545cd82614d92ea42d34f。
- 应用源码与通过训练/体重/完整备份往返验证的模拟器提交 2453987 一致；这不能替代实体手机测试。

尚未完成：Apple 签名、实体 iPhone 安装运行。该 IPA 需要安装工具重新签名，不能在手机中直接点开安装；没有发布到 App Store 或 TestFlight。
操作步骤见 INSTALL.md。免费安装路径通常需要每 7 天刷新签名。
