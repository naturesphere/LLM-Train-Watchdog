import time

class MonitorContext:
    def __init__(self, args):
        self.args = args
        self.current_log_path = None
        self.last_log_path = None
        # 核心数据字典，最终映射为 JSON
        self.data = {
            "updated": "",
            "status": "UNKNOWN",
            "log_file": None,
            "idle_seconds": 0,
            "current_loss": None,
            "message": "Initializing...",
            "restarted": False,
            "is_spike": False
        }

    def update_time(self):
        self.data["updated"] = time.strftime('%Y-%m-%d %H:%M:%S')