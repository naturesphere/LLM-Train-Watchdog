import os
import re
from handlers.base import Middleware

class LossParser(Middleware):
    def process(self, context):
        if not context.current_log_path: return
        
        # 提取最后一段日志
        with open(context.current_log_path, 'r', errors='ignore') as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 8192))
            lines = f.readlines()

        # 使用正则提取数值
        pattern = rf"{re.escape(context.args.keyword)}[:\s]+(\d+\.\d+)"
        for line in reversed(lines):
            match = re.search(pattern, line.lower())
            if match:
                context.data["current_loss"] = float(match.group(1))
                context.data["message"] = line.strip()
                context.data["status"] = "RUNNING"
                break