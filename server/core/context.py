import time

class MonitorContext:
    def __init__(self, args):
        self.args = args
        self.current_log_path = None
        self.last_log_path = None
        self.last_mtime = 0  # 新增：记录上次处理的文件修改时间
        self.last_iter_mtime = 0
        self.should_exit = False
        self.force_archive = False  # 新增：强制存证信号
        # 核心数据字典，最终映射为 JSON
        self.data = {
            "updated": "",
            "status": "UNKNOWN",
            "log_file": None,
            "idle_seconds": 0,
            "current_loss": None,
            "message": "Initializing...",
            "restarted": False,
            "is_spike": False,
            "current_step": -1,
            "total_steps": -1,
            "progress_pct": 0.0
        }

    def update_time(self):
        self.data["updated"] = time.strftime('%Y-%m-%d %H:%M:%S')