# Ubuntu ARM64 双屏运行说明

首个验收环境为树莓派 5 4GB、Ubuntu 24.04 Desktop ARM64。建议在登录界面选择 **Ubuntu on Xorg**，以便 Chromium 窗口能稳定定位到指定屏幕。

## 依赖

- Python 3.12、`python3-venv`、`python3-pip`
- Node.js 22 或更高的 LTS 版本，并启用 Corepack
- Chromium/Chrome、`curl`、`xrandr`、`xinput`
- 两块显示器设置为“扩展”，不要使用镜像模式

安装项目依赖并生成前端静态资源：

```bash
bash ops/build-release.sh
```

普通单窗口运行：

```bash
make start
```

## 双屏 kiosk

1. 执行 `xrandr --listmonitors` 获取两块屏幕的输出名称与坐标。
2. 执行 `xinput list --name-only` 获取两个触摸设备的精确名称。
3. 将 `ops/kiosk/kiosk.env.example` 复制为 `ops/kiosk/kiosk.env` 并填写上述信息。
4. 执行 `make kiosk`。

启动器会创建一次性本机会话，分别启动两个独立 Chromium 配置目录，并把角色令牌只放在各自的本机 URL 中。退出两个浏览器后，由启动器创建的 API 进程也会停止。

## 可选开机启动

`ops/systemd/hering-kiosk.service` 是用户级服务模板。先将项目放到 `~/hering` 并完成构建，再执行：

```bash
mkdir -p ~/.config/systemd/user
cp ops/systemd/hering-kiosk.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable hering-kiosk.service
```

模板不会自动启用、不会配置桌面自动登录，也不会修改 Ubuntu 的安全设置。

