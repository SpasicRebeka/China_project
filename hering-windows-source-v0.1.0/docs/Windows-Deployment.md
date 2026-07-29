# 医语桥 Windows 部署说明

适用版本：`0.1.0`  
适用平台：64 位 Windows 10/11、Windows x64 版 Python 3.12、3.13 或 3.14。

发布包已经包含医生端、患者端、FastAPI 本地服务、知识图谱数据库和 Windows x64 离线 Python 依赖。目标电脑不需要安装 Node.js、pnpm、数据库服务器或 Web 服务器。

## 一、部署前准备

1. 建议预先安装 64 位 Python 3.12、3.13 或 3.14，并勾选 `Add python.exe to PATH`。
2. 安装器会自动选择最高可用版本；如果都没有，`install.cmd` 会检测 winget，并在得到确认后为当前用户安装 Python 3.12。
3. 将 ZIP 解压到普通本地目录，例如：

   ```text
   D:\Hering\hering-windows-x64-v0.1.0
   ```

请勿直接在 ZIP 压缩包内运行，也不建议放在 OneDrive 等实时同步目录。

## 二、首次安装

双击发布目录中的：

```text
install.cmd
```

脚本会在当前目录创建独立的 `.venv`，并优先从包内 `wheelhouse` 离线安装依赖。整个过程不需要 Node.js，也不会修改其他 Python 项目。

看到“安装完成”后关闭窗口即可。若发布包未包含 `wheelhouse`，可联网运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Online
```

## 三、启动和访问

双击：

```text
start.cmd
```

服务会在后台启动，并自动打开医生端：

- 医生端：<http://127.0.0.1:8000/doctor/>
- 健康检查：<http://127.0.0.1:8000/api/health>
- 知识图谱接口：<http://127.0.0.1:8000/api/v1/knowledge-graph>
- API 文档：<http://127.0.0.1:8000/docs>

医生端创建会话后，点击“患者屏幕”复制患者端专用链接，在同一台电脑的第二块触摸屏浏览器中打开即可。

系统默认只监听 `127.0.0.1`，因此局域网内其他电脑无法直接访问，避免无意间暴露问诊会话。

## 四、双屏与触摸屏建议

1. 在 Windows“显示设置”中选择“扩展这些显示器”。
2. 将医生端浏览器窗口放在医生屏，将患者链接放在患者屏。
3. 两块设备均设置为 `1024×600`、横屏、缩放比例 `100%`。
4. 浏览器按 `F11` 进入全屏。
5. 在 Windows“平板电脑设置”中分别校准两块触摸屏与显示器的对应关系。

## 五、停止与状态检查

- 双击 `status.cmd`：显示服务状态、系统版本、知识库版本和主诉数量。
- 双击 `stop.cmd`：停止后台服务。

日志位于：

```text
logs\server.out.log
logs\server.err.log
```

会话数据库位于：

```text
data\hering.db
```

## 六、知识图谱数据库更新

当前医疗内容来源文件为：

```text
现病史追问知识库\knowledge_base.json
```

更新步骤：

1. 先备份原 JSON。
2. 用经过审核、结构兼容的新版本覆盖该文件。
3. 确认 JSON 使用 UTF-8 编码。
4. 刷新医生端页面；服务会根据文件修改时间重新读取知识库。
5. 运行 `status.cmd` 核对知识库版本。

如果文件缺失、JSON 无效、没有 `kb_version` 或没有主诉数据，接口将返回 `503`，医生端不会生成备用医疗节点。

## 七、修改端口

默认端口是 `8000`。如被占用，可在 PowerShell 中运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1 -Port 8080
```

然后访问：

```text
http://127.0.0.1:8080/doctor/
```

状态检查：

```powershell
powershell -ExecutionPolicy Bypass -File .\status.ps1 -Port 8080
```

## 八、故障排查

### 浏览器提示“无法访问此站点”

1. 运行 `status.cmd`。
2. 若显示未运行，重新运行 `start.cmd`。
3. 查看 `logs\server.err.log`。
4. 检查端口 8000 是否被占用。

### 提示没有兼容的 Python

新版安装脚本不会在 Python 探测失败后继续访问不存在的虚拟环境。如果机器有 winget，可在提示时输入 `Y` 自动安装；也可以手动安装 64 位 Python 3.12、3.13 或 3.14，并重新运行 `install.cmd`。例如：

```powershell
py -3.12 --version
```

### 提示知识图谱不可用

确认以下文件存在且是有效 UTF-8 JSON：

```text
现病史追问知识库\knowledge_base.json
```

### 需要完整重装

1. 先运行 `stop.cmd`。
2. 删除发布目录内的 `.venv` 文件夹。
3. 重新运行 `install.cmd`。

不要删除 `data`，除非明确需要清除本机已有会话数据。

## 九、校验发布包

发布包旁边提供 `.sha256` 文件。在 PowerShell 中运行：

```powershell
Get-FileHash .\hering-windows-x64-v0.1.0.zip -Algorithm SHA256
```

输出哈希应与 `.sha256` 文件中的值一致。
