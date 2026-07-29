# 医语桥｜听障医疗双屏问诊系统

面向听障患者与医生的本机双屏沟通终端工程骨架。当前版本只验证医生端、患者端、会话服务和离线部署链路，不包含真实问诊、诊断、病历生成或语音识别。

## 当前能力

- 两个独立 React/TypeScript 客户端：`/doctor/` 与 `/patient/`
- FastAPI 本机服务、短期角色令牌和 WebSocket 实时通道
- SQLite 通用会话与事件存储，医生凭据可清除整场会话
- 简体中文、繁体中文、英文三套基础界面文案
- 空的流式 ASR 适配接口，未来可接本地或远程实现
- Ubuntu ARM64 双 Chromium kiosk 和可选 systemd 用户服务模板

## 工程结构

```text
apps/
  doctor/             医生端独立应用
  patient/            患者端独立应用
packages/
  contracts/          由 Pydantic/OpenAPI 导出的前端协议
  frontend-core/      实时连接、国际化和终端空壳
services/api/
  app/                 FastAPI、SQLite、WebSocket、ASR 边界
  tests/               后端测试
ops/                   ARM64 构建、运行与 kiosk 配置
tests/e2e/             双浏览器端到端测试
```

原有设计文档、draw.io 文件和产品效果图均保留在仓库根目录。

## Linux 快速开始

要求 Python 3.12+、Node.js 22+、pnpm/Corepack。前后端分别由 `requirements.lock` 与 `pnpm-lock.yaml` 锁定；首次安装可以联网，构建完成后的正常运行不调用外部服务。

```bash
bash ops/build-release.sh
make start
```

打开：

- 医生端：<http://127.0.0.1:8000/doctor/>
- 患者端：由医生端生成带短期会话凭据的本机链接
- API 文档：<http://127.0.0.1:8000/docs>

双屏配置见 [ops/README.md](ops/README.md)。

## Linux 部署包

默认发布目标为 Ubuntu 24.04 Desktop / 双 1024×600 触摸屏，同时支持 ARM64 与 x86_64，以及 Python 3.12、3.13、3.14。目标机不需要 Node.js，发布包包含构建后的前端、后端、知识库和对应架构、Python 版本的离线 wheelhouse。

维护者在 Windows 构建机上运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\ops\linux\package-release.ps1 -Architecture arm64
```

将 `-Architecture` 改为 `x86_64` 可生成 Intel/AMD Linux 包。发布 `tar.gz` 与 SHA256 文件生成在 `dist` 目录。部署步骤见 [Linux 部署说明](docs/Linux-Deployment.md)。

## Windows 部署包

Windows x64 发布包不需要在目标机安装 Node.js。目标机准备 64 位 Python 3.12、3.13 或 3.14 后，解压发布包并依次运行 `install.cmd`、`start.cmd` 即可；包内含对应版本的离线 Python wheel 依赖。

完整步骤见 [Windows 部署说明](docs/Windows-Deployment.md)。维护者可在项目根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\ops\windows\package-release.ps1
```

发布 ZIP 与 SHA256 校验文件生成在 `dist` 目录。

## 开发

分别启动三个进程：

```bash
make dev-api
make dev-doctor
make dev-patient
```

开发地址为 `http://127.0.0.1:5173/doctor/` 与 `http://127.0.0.1:5174/patient/`。若希望医生端生成正确的开发患者链接，可将 `VITE_PATIENT_APP_URL` 设置为 `http://127.0.0.1:5174/patient/`。

常用检查：

```bash
make check
make test
make test-e2e
make contracts
```

`make contracts` 先从 FastAPI/Pydantic 导出 OpenAPI 和实时消息 JSON Schema，再生成 TypeScript 类型。后端模型是协议的唯一来源。

## 接口边界

- `GET /api/health`
- `POST /api/v1/sessions`
- `DELETE /api/v1/sessions/{session_id}?role=doctor&token=...`
- `WS /ws/v1/sessions/{session_id}?role=doctor|patient&token=...`

服务默认只监听 `127.0.0.1`。患者端不会获得清除会话的权限，业务功能也不得在患者界面显示疾病推断或诊断结论。
