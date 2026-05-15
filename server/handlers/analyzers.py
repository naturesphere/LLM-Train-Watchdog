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

class StalledDetector(Middleware):
    """
    停更检查处理器：
    如果日志文件超过指定阈值（threshold）未更新，则将状态判定为 STALLED。
    """
    def process(self, context):
        if context.should_exit:
            return
        
        if not context.current_log_path:
            context.data["status"] = "UNKNOWN"
            context.data["message"] = "No log file detected."
            return

        # 获取当前时间和文件最后修改时间
        current_time = time.time()
        try:
            mtime = os.path.getmtime(context.current_log_path)
            idle_seconds = int(current_time - mtime)
            context.data["idle_seconds"] = idle_seconds

            # 逻辑判断：如果空闲时间超过阈值
            # print(idle_seconds,  context.args.threshold,  idle_seconds > context.args.threshold)
            if idle_seconds > context.args.threshold:
                curr = context.data.get("current_step", 0)
                total = context.data.get("total_steps", 0)

                if total > 0 and curr >= total:
                    context.data["status"] = "FINISHED"
                    context.data["message"] = f"训练圆满完成：已达目标步数 {total}"
                    
                    # 信号联动：强制要求 Archiver 立即存档，并通知 Engine 准备退出
                    context.force_archive = True
                    context.should_exit = True
                    
                    print(f"\n[Terminator] 监测到任务结束 ({curr}/{total})，正在执行最终存证...")
                else:
                    # 真正的卡死
                    context.data["status"] = "STALLED"
                    context.data["message"] = f"训练卡死：停止更新 {idle_seconds}s"
            
        except OSError:
            context.data["status"] = "ERROR"
            context.data["message"] = "无法读取日志文件时间戳"

class SpikeDetector(Middleware):
    def __init__(self, window_size=15, threshold=1.3):
        self.history = deque(maxlen=window_size)
        self.threshold = threshold
        self.last_processed_mtime = 0  # 记录上次判定时的文件修改时间

    def process(self, context):
        if not context.data.get("is_new_step", True):
            return
        if context.data.get("needs_reset", False):
            self.history.clear()

        val = context.data.get("current_loss")
        current_mtime = context.last_mtime # 从 context 获取 LossParser 更新后的时间戳
        # 核心防重复逻辑：
        # 1. 如果没有提取到 Loss，直接跳过
        # 2. 如果当前 Loss 的时间戳与上次判定的时间戳一致，说明是旧数据，直接跳过
        if val is None or current_mtime <= self.last_processed_mtime:
            # 必须重置 is_spike，防止旧的尖峰状态一直挂在 JSON 里
            context.data["is_spike"] = False 
            return

        if not self.history:
            self.history.append(val)
            self.last_processed_mtime = current_mtime
            return

        avg = sum(self.history) / len(self.history)
        context.data["avg_loss"] = avg # 存入 context 供后续解析器使用
        if val > avg * self.threshold:
            context.data["is_spike"] = True
        else:
            context.data["is_spike"] = False
            self.history.append(val)
        # 无论是否是尖峰，只要判定过了，就更新处理时间戳
        self.last_processed_mtime = current_mtime

class PersistentHighLossDetector(Middleware):
    """
    持续高 Loss 检测：
    如果 Loss 超过滑动平均值的一定比例，且持续步数超过阈值，
    则判定为训练可能失败。
    """
    def __init__(self, threshold=1.2, p_steps=5):
        self.threshold = threshold
        self.p_steps = p_steps  # 允许持续超标的最大步数
        self.count = 0          # 当前连续超标计数
        self.last_processed_mtime = 0
        self.is_currently_critical = False

    def process(self, context):
        
        if not context.data.get("is_new_step", True):
            return
        if context.data.get("needs_reset", False):
            self.count = 0

        val = context.data.get("current_loss")
        avg = context.data.get("avg_loss")
        current_mtime = context.last_mtime
        
        if val is None or current_mtime <= self.last_processed_mtime:
            return

        if not avg: return

        if val > avg * self.threshold:
            # 持续异常，累加计数，上限设为 p_steps 的 2 倍防止数值过大
            self.count = min(self.count + 1, self.p_steps * 2)
        else:
            if self.count > 0:
                self.count -= 1 

        if self.count >= self.p_steps:
            if not self.is_currently_critical:
                self.is_currently_critical = True
                context.force_archive = True # 初次进入异常，强制存证
            
            context.data["status"] = "CRITICAL"
            context.data["message"] = f"CRITICAL: Loss 持续异常 (当前权重: {self.count})"
            
        # 康复判定：计数器彻底归零
        elif self.count == 0 and self.is_currently_critical:
            self.is_currently_critical = False
            context.data["status"] = "RUNNING"
            context.data["message"] = "Loss 已彻底恢复正常。"
            # 康复时也可以选择强制存证一次，记录恢复点
            context.force_archive = True

        self.last_processed_mtime = current_mtime

class Archiver(Middleware):
    def __init__(self):
        self.last_archive_reason = None

    def process(self, context):
        # 判定存证原因
        current_reason = None
        if context.data["restarted"]: 
            current_reason = "RESTART"
        elif context.data["is_spike"]: 
            current_reason = "SPIKE"
        elif context.data["status"] == "STALLED": 
            current_reason = "STALLED"
        elif context.data["status"] == "FINISHED": 
            current_reason = "FINISHED"
        
        # 触发条件：原因发生变化 OR 收到强制存证信号 (context.force_archive)
        force = getattr(context, "force_archive", False)

        if (current_reason and current_reason != self.last_archive_reason) or force:
            archive_dir = os.path.join(context.args.base_dir, "archive")
            if not os.path.exists(archive_dir):
                os.makedirs(archive_dir)
            
            ts = time.strftime('%Y%m%d_%H%M%S')
            filename = f"{ts}_{current_reason}.json"
            path = os.path.join(archive_dir, filename)
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(context.data, f, indent=4, ensure_ascii=False)
            
            print(f"[{time.strftime('%H:%M:%S')}] 💾 版本存证已归档: {filename}")
            
            # 更新状态记录
            self.last_archive_reason = current_reason
            # 处理完强制存证后重置信号，防止重复执行（尽管 Engine 即将退出）
            context.force_archive = False