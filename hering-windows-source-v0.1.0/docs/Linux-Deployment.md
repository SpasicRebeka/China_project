# 医语桥 Linux 部署说明

适用版本：`0.1.0`  
默认目标：Ubuntu 24.04 Desktop / 64 位 Python 3.12、3.13 或 3.14 / Xorg。  
屏幕：两块 `1024×600` 横向触摸屏。

发布包已经包含医生端、患者端、FastAPI 服务、知识图谱数据库、双屏 kiosk 启动器，以及 Python 3.12–3.14 对应的 Linux 离线 wheels。安装器会自动选择系统上最高可用的兼容版本。目标机不需要 Node.js 或 pnpm。

先在目标机执行 `uname -m` 选择发布包：

- 返回 `aarch64`：使用 `hering-linux-arm64-v0.1.0.tar.gz`。
- 返回 `x86_64`：使用 `hering-linux-x86_64-v0.1.0.tar.gz`。

如果目标设备明确只使用 ARM64 Python 3.14，也可以选择体积更小的专用包：

```text
hering-linux-arm64-py314-v0.1.0.tar.gz
```

该专用包只接受 64 位 Python 3.14，不包含 Python 3.12/3.13 wheels。

## 1. 安装系统依赖

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip chromium-browser curl x11-xserver-utils xinput
```

Ubuntu 24.04 某些镜像中的 Chromium 包名是 `chromium`；如果 `chromium-browser` 不存在，可改为：

```bash
sudo apt install -y chromium
```

建议在登录界面选择 **Ubuntu on Xorg**。Wayland 下浏览器窗口位置可能不会按参数固定到指定屏幕。

## 2. 解压和离线安装

把与设备架构匹配的发布包复制到设备，例如 `~/Downloads`。下面以 ARM64 为例：

```bash
mkdir -p ~/hering
tar -xzf ~/Downloads/hering-linux-arm64-v0.1.0.tar.gz -C ~/hering --strip-components=1
cd ~/hering
bash install.sh
```

安装脚本依次查找 `python3.14`、`python3.13`、`python3.12` 和 `python3`，选择最高可用的 64 位兼容版本，创建项目专用 `.venv`，并从 `wheelhouse` 离线安装对应依赖。

## 3. 单窗口启动

```bash
cd ~/hering
./start.sh
```

访问：

- 医生端：<http://127.0.0.1:8000/doctor/>
- 健康检查：<http://127.0.0.1:8000/api/health>
- 知识图谱：<http://127.0.0.1:8000/api/v1/knowledge-graph>

管理命令：

```bash
./status.sh
./stop.sh
```

日志位于 `logs/`，SQLite 会话数据库位于 `data/hering.db`。

## 4. 配置双屏触摸 kiosk

查看显示器：

```bash
xrandr --listmonitors
```

查看触摸设备：

```bash
xinput list --name-only
```

复制配置：

```bash
cp ops/kiosk/kiosk.env.example ops/kiosk/kiosk.env
nano ops/kiosk/kiosk.env
```

默认配置按照两块并排的 `1024×600` 屏幕：

```text
DOCTOR_WINDOW_POSITION=0,0
PATIENT_WINDOW_POSITION=1024,0
DOCTOR_WINDOW_SIZE=1024,600
PATIENT_WINDOW_SIZE=1024,600
```

请根据 `xrandr` 修改 `DOCTOR_OUTPUT`、`PATIENT_OUTPUT`，根据 `xinput` 填写两个触摸设备名称。

启动双屏：

```bash
bash ops/kiosk/start-kiosk.sh
```

启动器会创建一次性问诊会话，将医生端和患者端分别以 Chromium kiosk 模式放到两块屏幕，并把触摸设备映射到对应输出。

## 5. 用户级 systemd 开机启动

发布包中的服务模板默认安装目录为 `~/hering`：

```bash
mkdir -p ~/.config/systemd/user
cp ops/systemd/hering-kiosk.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable hering-kiosk.service
systemctl --user start hering-kiosk.service
```

查看状态和日志：

```bash
systemctl --user status hering-kiosk.service
journalctl --user -u hering-kiosk.service -f
```

该服务需要图形桌面会话。它不会自动配置用户登录；如需要真正的开机无人值守 kiosk，应另行评估自动登录的安全风险。

## 6. 更新知识图谱

医疗内容来源：

```text
现病史追问知识库/knowledge_base.json
```

覆盖该 UTF-8 JSON 后刷新医生端即可。服务会根据文件修改时间重新加载。若文件缺失或格式无效，接口返回 `503`，医生端不会生成备用医疗节点。

## 7. 修改端口

```bash
HERING_PORT=8080 HERING_OPEN_BROWSER=0 ./start.sh
HERING_PORT=8080 ./status.sh
```

同时修改 `ops/kiosk/kiosk.env`：

```text
HERING_BASE_URL=http://127.0.0.1:8080
HERING_PORT=8080
```

## 8. 常见问题

### 无法访问页面

```bash
./status.sh
cat logs/server.err.log
ss -ltnp | grep 8000
```

### Chromium 没有进入指定屏幕

确认使用 Xorg，并核对 `xrandr --listmonitors` 返回的坐标。Wayland 可能忽略 `--window-position`。

### 触摸发生在错误的屏幕

重新核对 `xinput list --name-only` 的设备名和 `DOCTOR_OUTPUT`、`PATIENT_OUTPUT`。

### wheel 无法安装

确认设备架构与发布包一致，且 Python 为 3.12、3.13 或 3.14：

```bash
uname -m
python3 --version
```

如果返回 `x86_64`，应使用 x86_64 发布包，而不是 ARM64 包。
