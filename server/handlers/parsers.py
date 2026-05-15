import os
import re
from handlers.base import Middleware

class LossParser(Middleware):
    def process(self, context):
        if not context.current_log_path: return
        if not context.data.get("is_new_step", True): return
        # 获取当前文件的修改时间
        try:
            current_mtime = os.path.getmtime(context.current_log_path)
        except OSError:
            return

        # 核心判断：如果修改时间没变，说明没有新日志产生
        # print(current_mtime, context.last_mtime)
        if current_mtime <= context.last_mtime:
            # 如果此时 StalledDetector 已经把状态改成了 STALLED，我们这里保持原样
            # 不要执行后续逻辑将状态改回 RUNNING
            return
        
        # 提取最后一段日志
        with open(context.current_log_path, 'r', errors='ignore') as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 8192))
            lines = f.readlines()

        # 使用正则提取数值
        pattern = rf"{re.escape(context.args.keyword)}[:\s]+(\d+\.\d+)"
        found_new_loss = False
        for line in reversed(lines):
            match = re.search(pattern, line.lower())
            if match:
                context.data["current_loss"] = float(match.group(1))
                context.data["message"] = line.strip()
                found_new_loss = True
                break

        # 处理完后更新 context 里的时间戳，供下一轮对比
        if found_new_loss:
            context.last_mtime = current_mtime


class IterationParser(Middleware):
    """
    专门解析训练迭代步数的解析器
    匹配格式: iteration       49/ 2152274
    """
    def process(self, context):
        if not context.current_log_path:
            return

        # 获取当前文件的修改时间（用于防重复解析）
        try:
            current_mtime = os.path.getmtime(context.current_log_path)
        except OSError:
            return

        # 如果文件没有更新，直接跳过
        if current_mtime <= getattr(context, 'last_iter_mtime', 0):
            return

        # 读取日志末尾内容
        with open(context.current_log_path, 'r', errors='ignore') as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 8192))
            lines = f.readlines()

        # 正则表达式说明：
        # iteration\s+ : 匹配单词 iteration 后跟至少一个空格
        # (\d+)        : 第一组捕获，当前步数
        # /            : 匹配分隔符斜杠
        # \s* : 匹配斜杠后可能存在的空格
        # (\d+)        : 第二组捕获，总步数
        pattern = r"iteration\s+(\d+)/\s*(\d+)"

        for line in reversed(lines):
            match = re.search(pattern, line.lower())
            if match:
                current_step = int(match.group(1))
                total_steps = int(match.group(2))

                prev_step = context.data.get("current_step", -1)
                if current_step != prev_step:
                    context.data["is_new_step"] = True
                    if current_step < prev_step:
                        context.data["needs_reset"] = True  # 发出全局重置信号
                        context.data["message"] = f"Detected training restart: {prev_step} -> {current_step}"
                        print(f"⚠️ {context.data['message']}")
                    else:
                        context.data["needs_reset"] = False
                    context.data["status"] = "RUNNING"
                    context.data["message"] = f"Training is active at step {current_step}"
                    # 将结果存入 context
                    context.data["current_step"] = current_step
                    context.data["total_steps"] = total_steps
                    
                    # 计算百分比进度（可选）
                    if total_steps > 0:
                        context.data["progress_pct"] = round((current_step / total_steps) * 100, 2)
                    
                    # 更新此处理器的专用时间戳
                    context.last_iter_mtime = current_mtime
                else:
                    context.data["is_new_step"] = False
                    if total_steps > 0 and current_step >= total_steps:
                        context.data["status"] = "FINISHED"
                        context.data["message"] = f"训练圆满完成：已达目标步数 {total_steps}"
                        print(context.data["message"])
                        # 信号联动：强制要求 Archiver 立即存档，并通知 Engine 准备退出
                        context.force_archive = True
                        context.should_exit = True
                # print(f'current_step: {current_step}, total_steps: {total_steps}, prev_step: {prev_step}, {context.data["is_new_step"]}, {context.data["needs_reset"]}')
                break
            
