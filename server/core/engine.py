import time
import json
import threading
from core.web_server import start_server
import sys

class MonitorEngine:
    def __init__(self, context):
        self.context = context
        self.middlewares = []

    def add_middleware(self, middleware):
        self.middlewares.append(middleware)

    def run_once(self):
        self.context.update_time()
        for mw in self.middlewares:
            try:
                mw.process(self.context)
            except Exception as e:
                # 即使一个中间件挂了，也要保证后续和下一轮能跑
                print(f"Error in {mw.__class__.__name__}: {e}")

    def start(self):
        # 1. 启动 HTTP 服务线程
        if self.context.args.start_server:
            threading.Thread(
                target=start_server, 
                args=(self.context.args.port, self.context.args.base_dir), 
                daemon=True
            ).start()
            print(f"Web server started on port {self.context.args.port}...")

        # 2. 主监控循环
        print(f"Monitoring started on {self.context.args.base_dir}...")
        while True:
            self.run_once()
            
            # 持久化当前状态
            output_path = f"{self.context.args.base_dir}/training_status.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self.context.data, f, indent=4, ensure_ascii=False)

            if self.context.should_exit:
                print(f"[Engine] 收到退出信号，正在保存状态并关闭监控...")
                # 给予客户端最后一次读取 JSON 的时间（可选）
                time.sleep(self.context.args.interval) 
                print("[Engine] Goodbye.")
                sys.exit(0)  # 彻底退出程序
            
            time.sleep(self.context.args.interval)