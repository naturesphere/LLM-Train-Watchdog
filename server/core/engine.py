import time
import json
import threading
from core.web_server import start_server

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
        threading.Thread(
            target=start_server, 
            args=(self.context.args.port, self.context.args.base_dir), 
            daemon=True
        ).start()

        # 2. 主监控循环
        print(f"Monitoring started on {self.context.args.base_dir}...")
        while True:
            self.run_once()
            
            # 持久化当前状态
            output_path = f"{self.context.args.base_dir}/training_status.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self.context.data, f, indent=4, ensure_ascii=False)
            
            time.sleep(self.context.args.interval)