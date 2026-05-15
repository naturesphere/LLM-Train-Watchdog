import os
import glob
import re
from handlers.base import Middleware

class X10000Resolver(Middleware):    
    # 自然排序逻辑
    def natural_keys(self, text):
        return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]

    def process(self, context):
        pattern = os.path.join(context.args.base_dir, context.args.pattern)
        log_dirs = glob.glob(pattern)
        if not log_dirs: return

        log_dirs.sort(key=self.natural_keys, reverse=True)
        latest_dir = log_dirs[0]
        
        files = [f for f in os.listdir(latest_dir) if f.endswith('.log')]
        if files:
            files.sort(key=self.natural_keys, reverse=True)
            context.current_log_path = os.path.join(latest_dir, files[0])
            relative_path = context.current_log_path.replace(context.args.base_dir, '').lstrip('/')
            context.data["log_file"] = relative_path



class AliYunDSWResolver(X10000Resolver): 
    def process(self, context):
        """根据通配符模式寻找最新的日志文件"""
        pattern = os.path.join(context.args.base_dir, '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9]') #20260511-2209
        log_dirs = glob.glob(pattern)
        if not log_dirs: return
        
        log_dirs.sort(key=self.natural_keys, reverse=True)
        latest_dir = log_dirs[0]

        pattern2 = os.path.join(latest_dir, 'worker_*')
        worker_folders = glob.glob(pattern2)
        worker_folders.sort(key=self.natural_keys, reverse=True)
        latest_worker = worker_folders[0]

        pattern3 = os.path.join(latest_worker, 'none_*/attempt_0/7/stdout.log')
        log_files = glob.glob(pattern3)
        # 按最后修改时间排序，取最新的一个
        log_files.sort(key=os.path.getmtime, reverse=True)
        log_file = log_files[0]
        context.current_log_path = log_file
        relative_path = context.current_log_path.replace(context.args.base_dir, '').lstrip('/')
        context.data["log_file"] = relative_path
