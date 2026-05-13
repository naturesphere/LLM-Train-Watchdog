import os
import glob
import time
import argparse
import re
import json
import threading
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

# --- 1. 平台适配逻辑 (策略模式) ---

class LogResolver:
    """日志路径解析基类"""
    def get_latest_file(self, base_dir, pattern):
        raise NotImplementedError
    
    def natural_keys(self, text):
        return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]

class X10000Resolver(LogResolver):
    """适配x10000目录结构的平台"""
    def get_latest_file(self, base_dir, pattern):
        full_pattern = os.path.join(base_dir, pattern)
        log_dirs = glob.glob(full_pattern)
        if not log_dirs: return None
        
        # 先按目录名自然排序取最新的
        log_dirs.sort(key=self.natural_keys, reverse=True)
        latest_dir = log_dirs[0]
        
        # 再按文件名自然排序取最新的文件
        files = [f for f in os.listdir(latest_dir) if f.endswith('.log')]
        if not files: return None
        files.sort(key=self.natural_keys, reverse=True)
        return os.path.join(latest_dir, files[0])

class FlatResolver(LogResolver):
    """适配扁平化目录结构，直接按修改时间排序"""
    def get_latest_file(self, base_dir, pattern):
        files = glob.glob(os.path.join(base_dir, "*.log"))
        if not files: return None
        # 修改时间相同则按文件名自然排序降序
        files.sort(key=lambda x: (os.path.getmtime(x), self.natural_keys(x)), reverse=True)
        return files[0]

# --- 2. HTTP 服务部分 ---

class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

def start_server(port, directory):
    """固定使用 127.0.0.1，确保全平台兼容"""
    os.chdir(directory)
    host = '127.0.0.1'
    server = HTTPServer((host, port), NoCacheHandler)
    # 模拟标准输出以触发 VS Code 自动映射
    print(f"\n[HTTP Server] Serving HTTP on {host} port {port} (http://{host}:{port}/) ...")
    server.serve_forever()

# --- 3. 监控主逻辑 ---

def monitor_logs(args, resolver):
    output_path = os.path.join(args.base_dir, "training_status.json")

    # 启动后台服务线程
    threading.Thread(target=start_server, args=(args.port, args.base_dir), daemon=True).start()

    print(f"\n[Monitor] 启动成功！平台模式: {args.platform}")
    print(f"[Monitor] 正在监控: {args.base_dir}")
    print("-" * 50)

    last_check_status = ""
    last_log_path = None

    while True:
        current_log = resolver.get_latest_file(args.base_dir, args.pattern)
        current_time = time.time()
        time_str = time.strftime('%Y-%m-%d %H:%M:%S')
        
        data = {
            "updated": time_str,
            "status": "UNKNOWN",
            "log_file": os.path.basename(current_log) if current_log else None,
            "idle_seconds": 0,
            "message": "",
            "restarted": False,
            "is_spike": False # 预留尖峰报警位
        }

        if not current_log:
            data["status"] = "WAITING"
            data["message"] = "未找到日志文件..."
        else:
            # 重启检测
            if last_log_path and last_log_path != current_log:
                data["restarted"] = True
            last_log_path = current_log

            mtime = os.path.getmtime(current_log)
            data["idle_seconds"] = int(current_time - mtime)
            
            if data["idle_seconds"] > args.threshold:
                data["status"] = "STALLED"
                data["message"] = f"停更 {data['idle_seconds']}s"
            else:
                try:
                    with open(current_log, 'r', errors='ignore') as f:
                        f.seek(0, 2)
                        f.seek(max(0, f.tell() - 4096))
                        lines = f.readlines()
                        
                        log_msg = "Waiting for data..."
                        for line in reversed(lines):
                            if args.keyword.lower() in line.lower():
                                log_msg = line.strip()
                                # 这里可以扩展数值提取和 is_spike 判定逻辑
                                break
                        data["status"] = "RUNNING"
                        data["message"] = log_msg
                except Exception as e:
                    data["status"] = "ERROR"
                    data["message"] = str(e)

        with open(output_path, "w", encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        summary = f"{data['status']} | {data['message']}"
        if summary != last_check_status or data["restarted"]:
            print(f"[{time_str}] {summary} {'(RESTARTED!)' if data['restarted'] else ''}")
            last_check_status = summary
            
        time.sleep(args.interval)

# --- 4. 入口 ---

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_dir", type=str, default=".")
    parser.add_argument("--pattern", type=str, default="*/worker_*/none_*/attempt_0/*/stdout.log")
    parser.add_argument("--platform", choices=["x10000", "flat"], default="x10000")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--threshold", type=int, default=600)
    parser.add_argument("--keyword", type=str, default="lm loss")
    return parser.parse_args()

if __name__ == "__main__":
    args = get_args()
    resolvers = {"x10000": X10000Resolver(), "flat": FlatResolver()}
    try:
        monitor_logs(args, resolvers[args.platform])
    except KeyboardInterrupt:
        sys.exit(0)