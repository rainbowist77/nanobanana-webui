"""NanoBanana 本地网页程序，仅使用 Python 标准库。"""

import argparse
import base64
import binascii
import json
from pathlib import Path
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import uuid
import webbrowser


ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"
CONFIG_PATH = ROOT / "config.json"
SIZES = {"1024x1024", "1024x1536", "1536x1024"}
MAX_BYTES = 32 * 1024 * 1024
GENERATING = threading.Lock()


class GenerationError(Exception):
    pass


def load_config():
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise GenerationError("缺少 config.json，请参考 config.example.json 创建。") from None
    except (ValueError, OSError):
        raise GenerationError("无法读取 config.json，请检查文件权限和 JSON 格式。") from None
    if not isinstance(config, dict):
        raise GenerationError("config.json 必须为 JSON 对象。")
    values = {}
    for field in ("endpoint", "api_key", "model"):
        value = config.get(field)
        if not isinstance(value, str) or not value.strip():
            raise GenerationError(f"请在 config.json 中填写非空字符串 {field}。")
        values[field] = value.strip()
    try:
        endpoint = urlsplit(values["endpoint"])
        if (endpoint.scheme not in ("http", "https") or not endpoint.hostname
                or endpoint.username is not None or endpoint.password is not None
                or endpoint.fragment or any(char.isspace() for char in values["endpoint"])):
            raise ValueError()
        endpoint.port
    except ValueError:
        raise GenerationError("config.json 中 endpoint 必须为有效的 HTTP 或 HTTPS 接口完整地址。") from None
    try:
        values["api_key"].encode("ascii")
        if any(ord(char) < 32 or ord(char) == 127 for char in values["api_key"]):
            raise ValueError()
    except (UnicodeError, ValueError):
        raise GenerationError("config.json 中 api_key 必须为不含控制字符的 ASCII 字符串。") from None
    return values


def read_limited(response):
    data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise GenerationError("服务返回的数据过大（超过 32 MB）。")
    return data


def image_extension(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    raise GenerationError("服务未返回支持的图片格式（PNG、JPEG、WebP、GIF）。")


def generate_image(prompt, size):
    config = load_config()
    payload = json.dumps({"model": config["model"], "size": size, "prompt": prompt}).encode("utf-8")
    request = Request(config["endpoint"], data=payload, headers={
        "Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json",
    }, method="POST")
    try:
        with urlopen(request, timeout=180) as response:
            result = json.loads(read_limited(response))
        items = result.get("data") if isinstance(result, dict) else None
        if not isinstance(items, list) or not items or not isinstance(items[0], dict):
            raise GenerationError("API 返回格式异常：缺少 data[0] 图片信息。")
        item = items[0]
        if item.get("b64_json"):
            data = base64.b64decode(item["b64_json"], validate=True)
        elif item.get("url"):
            url = item["url"]
            if not isinstance(url, str) or urlsplit(url).scheme != "https":
                raise GenerationError("图片下载地址必须使用 HTTPS。")
            # 图片下载请求独立发起，不携带 API Key。
            with urlopen(Request(url), timeout=120) as response:
                if urlsplit(response.geturl()).scheme != "https":
                    raise GenerationError("图片下载被重定向到不安全的地址。")
                data = read_limited(response)
        else:
            raise GenerationError("API 未返回图片地址或 Base64 图片。")
        extension = image_extension(data)
        OUTPUTS.mkdir(exist_ok=True)
        filename = uuid.uuid4().hex + extension
        (OUTPUTS / filename).write_bytes(data)
        return filename
    except HTTPError as exc:
        messages = {401: "API Key 无效或已过期。", 403: "API 拒绝访问，请检查账户权限。",
                    429: "请求过于频繁或额度不足，请稍后重试。"}
        raise GenerationError(messages.get(exc.code, f"远程服务请求失败（HTTP {exc.code}）。")) from None
    except (URLError, TimeoutError, OSError):
        raise GenerationError("网络连接、图片保存失败或请求超时，请检查网络和目录权限后重试。") from None
    except (ValueError, TypeError, binascii.Error):
        raise GenerationError("API 返回的数据无法解析，请稍后重试。") from None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # 不记录请求正文、提示词或凭据。
        pass

    def send_content(self, status, data, content_type, download=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="{download}"')
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_json(self, status, value):
        self.send_content(status, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def valid_host(self):
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def do_GET(self):
        if not self.valid_host():
            self.send_json(403, {"error": "请通过启动时显示的本地地址访问。"})
            return
        path = urlsplit(self.path).path
        static = {"/": ("index.html", "text/html; charset=utf-8"),
                  "/app.js": ("app.js", "text/javascript; charset=utf-8")}
        if path in static:
            name, mime = static[path]
            self.send_content(200, (ROOT / "static" / name).read_bytes(), mime)
        elif path == "/api/status":
            try:
                load_config()
                self.send_json(200, {"configured": True})
            except GenerationError as exc:
                self.send_json(200, {"configured": False, "error": str(exc)})
        elif re.fullmatch(r"/(images|download)/[a-f0-9]{32}\.(png|jpg|webp|gif)", path):
            name = path.rsplit("/", 1)[1]
            file = OUTPUTS / name
            if not file.is_file():
                self.send_json(404, {"error": "图片不存在。"})
                return
            mime = {".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}[file.suffix]
            self.send_content(200, file.read_bytes(), mime, name if path.startswith("/download/") else None)
        else:
            self.send_json(404, {"error": "页面不存在。"})

    def do_POST(self):
        origin = f"http://127.0.0.1:{self.server.server_port}"
        if not self.valid_host() or self.headers.get("Origin") != origin:
            self.send_json(403, {"error": "仅允许本地页面发起请求。"})
            return
        if self.path != "/api/generate":
            self.send_json(404, {"error": "接口不存在。"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                raise ValueError()
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError()
            prompt, size = body.get("prompt"), body.get("size", "1024x1024")
            if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 4000:
                raise ValueError()
            if not isinstance(size, str) or size not in SIZES:
                raise ValueError()
        except (ValueError, TypeError):
            self.send_json(400, {"error": "请输入 1–4000 字提示词，并选择有效尺寸。"})
            return
        if not GENERATING.acquire(blocking=False):
            self.send_json(429, {"error": "已有生成任务进行中，请等待完成。"})
            return
        try:
            filename = generate_image(prompt.strip(), size)
            self.send_json(200, {"image_url": f"/images/{filename}", "download_url": f"/download/{filename}"})
        except GenerationError as exc:
            self.send_json(502, {"error": str(exc)})
        finally:
            GENERATING.release()


def main():
    parser = argparse.ArgumentParser(description="NanoBanana 本地图片生成工具")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as exc:
        parser.exit(1, f"启动失败：{exc}，可使用 --port 8001 更换端口。\n")
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"NanoBanana 已启动：{url}\n按 Ctrl+C 停止。", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
