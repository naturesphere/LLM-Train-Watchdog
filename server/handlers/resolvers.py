import os
import glob
import re
from handlers.base import Middleware

class AliyunDSWResolver(Middleware):
    def process(self, context):
        pattern = os.path.join(context.args.base_dir, context.args.pattern)
        log_dirs = glob.glob(pattern)
        if not log_dirs: return

        # 自然排序逻辑
        def natural_keys(text):
            return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]

        log_dirs.sort(key=natural_keys, reverse=True)
        latest_dir = log_dirs[0]
        
        files = [f for f in os.listdir(latest_dir) if f.endswith('.log')]
        if files:
            files.sort(key=natural_keys, reverse=True)
            context.current_log_path = os.path.join(latest_dir, files[0])
            context.data["log_file"] = os.path.basename(context.current_log_path)