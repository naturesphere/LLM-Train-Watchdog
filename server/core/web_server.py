import os
from http.server import HTTPServer, SimpleHTTPRequestHandler

class NoCacheHandler(SimpleHTTPRequestHandler):
    """
    自定义处理器：禁用所有浏览器缓存。
    确保客户端（本地 Mac）每次请求 JSON 时都能拿到服务器磁盘上的最新数据。
    """
    def end_headers(self):
        # 发送禁用缓存的 HTTP 响应头
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def log_message(self, format, *args):
        # 默认会打印每个请求的日志，如果不想要这些干扰信息，可以 pass 掉
        # print(f"[HTTP] {self.address_string()} - {format % args}")
        pass

def start_server(port, directory):
    """
    启动 HTTP 服务
    :param port: 监听端口
    :param directory: 服务根目录（即 training_status.json 所在的目录）
    """
    # 切换到指定目录，这样 SimpleHTTPRequestHandler 就能正确找到文件
    os.chdir(directory)
    
    # 强制监听 127.0.0.1 (Loopback)
    # 这在 SSH 隧道环境下是最稳健的选择，且阿里云 DSW Proxy 也支持
    server_address = ('127.0.0.1', port)
    
    try:
        httpd = HTTPServer(server_address, NoCacheHandler)
        # 这里的打印是为了触发 VS Code 等 IDE 的自动端口转发检测
        print(f"[HTTP Server] Serving HTTP on 127.0.0.1 port {port} (http://127.0.0.1:{port}/) ...")
        httpd.serve_forever()
    except Exception as e:
        print(f"[HTTP Server] Failed to start server: {e}")