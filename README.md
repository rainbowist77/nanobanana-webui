# NanoBanana 图片生成小程序

Python 本地网页应用：输入提示词、选择尺寸、预览和下载图片。端点、密钥和模型均从项目根目录 `config.json` 读取，不再读取环境变量。支持 API 返回 `data[0].url` 或 `data[0].b64_json`。

## 配置

编辑项目内的 `config.json`，填写自己的密钥：

```json
{
  "endpoint": "https://example.com/v1/images/generations",
  "api_key": "你的 API Key",
  "model": "nanobanana"
}
```

三个字段均为必填非空字符串。示例中的 `example.com` 是占位域名，请替换为你自己的服务接口地址。`endpoint` 是完整接口地址，程序不会自动追加路径。配置文件使用 UTF-8 编码；文件缺失时可复制 `config.example.json` 为 `config.json` 后填写。真实端点和密钥仅保存在被 Git 忽略的 `config.json` 中，请勿写入公开文件。

每次检查配置和生成图片时都会重新读取文件，保存后刷新页面即可生效，无需重启程序。密钥不会通过页面或状态接口返回；`config.json` 已加入 `.gitignore`，提交代码时保留不含密钥的示例文件即可。

## 启动（Windows PowerShell）

需要 Python 3.10 或更高版本。本项目仅使用标准库，无需安装第三方依赖。

```powershell
# 首次使用创建项目内的虚拟环境（已有 .venv 则跳过）
python -m venv .venv

# 无需激活环境，直接使用虚拟环境解释器
.\.venv\Scripts\python.exe app.py
```

程序自动打开 `http://127.0.0.1:8000`。保持终端运行，按 `Ctrl+C` 停止。也可双击 `start.bat`；它会在缺少虚拟环境时自动创建。

端口被占用或不希望自动打开浏览器时：

```powershell
.\.venv\Scripts\python.exe app.py --port 8001 --no-browser
```

## 启动（Linux、macOS 或 Windows Git Bash）

```bash
bash start.sh
# 传递启动参数
bash start.sh --port 8001 --no-browser
```

脚本从自身所在目录启动，自动在项目内创建并使用 `.venv`，无需手动激活。需要系统已安装 Python 3.10 或更高版本和 venv 支持。虚拟环境不可跨操作系统复制，迁移项目时请在目标系统重新创建 `.venv`。

## Git 本地管理

项目使用本地 Git 仓库管理代码。`config.json`、`.venv/`、`outputs/` 和 Python 缓存均被忽略，示例配置 `config.example.json` 纳入版本管理。

```bash
git status
git diff
git add app.py static tests README.md start.sh start.bat .gitignore .gitattributes config.example.json
git commit -m "Describe your changes"
git log --oneline
```

## 使用与文件

- 端点、密钥和模型仅从项目内 `config.json` 读取，缺失或无效时页面显示配置错误。
- 默认尺寸为示例中的 `1024x1024`；额外提供的竖图和横图尺寸是否可用，以服务商支持为准。
- 点击“生成图片”会产生真实 API 请求，费用及额度由服务商决定。程序不会自动重试，避免重复计费。
- 图片保存在项目内 `outputs/`，下载按钮从本地服务下载已保存图片。刷新页面不会删除图片，但页面不提供历史记录列表。
- `.venv/`、`outputs/` 和 Python 缓存均位于项目内；项目不安装全局包，不写入用户配置目录。浏览器自身缓存、用户主动下载的文件由浏览器管理。
- 服务仅监听 `127.0.0.1`，请使用启动时显示的地址访问。
- 常见错误：401 表示 Key 无效；429 表示频率或额度限制；超时请检查网络。请求超时仍可能已在服务商侧产生费用。

## 验证

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试使用项目内临时配置和模拟响应，不读取真实密钥、不调用真实 API、不产生生成费用。

## 许可证

本项目采用 [MIT License](LICENSE)，Copyright (c) 2026 rainbowist77。
