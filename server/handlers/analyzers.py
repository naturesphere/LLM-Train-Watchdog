import os
import time
import json
from collections import deque
from handlers.base import Middleware

class RestartDetector(Middleware):
    def process(self, context):
        if context.last_log_path and context.last_log_path != context.current_log_path:
            context.data["restarted"] = True
        else:
            context.data["restarted"] = False
        context.last_log_path = context.current_log_path

class SpikeDetector(Middleware):
    def __init__(self, window_size=15, threshold=1.3):
        self.history = deque(maxlen=window_size)
        self.threshold = threshold

    def process(self, context):
        val = context.data.get("current_loss")
        if val is None: return

        if not self.history:
            self.history.append(val)
            return

        avg = sum(self.history) / len(self.history)
        if val > avg * self.threshold:
            context.data["is_spike"] = True
        else:
            context.data["is_spike"] = False
            self.history.append(val)

class Archiver(Middleware):
    def process(self, context):
        # 触发存证的条件：重启、尖峰或卡死
        if context.data["restarted"] or context.data["is_spike"]:
            archive_dir = os.path.join(context.args.base_dir, "archive")
            if not os.path.exists(archive_dir): os.makedirs(archive_dir)
            
            ts = time.strftime('%Y%m%d_%H%M%S')
            tag = "RESTART" if context.data["restarted"] else "SPIKE"
            path = os.path.join(archive_dir, f"{ts}_{tag}.json")
            
            with open(path, 'w') as f:
                json.dump(context.data, f, indent=4)