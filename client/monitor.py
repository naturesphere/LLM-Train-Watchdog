import argparse
from utils.data_sources import DSWSource, LocalSource
from utils.notifier import DingTalkNotifier
import time
from datetime import datetime
import os


def get_args(): 
    parser = argparse.ArgumentParser()
    parser.add_argument("--robot", default="default_alpha", help="选择使用的钉钉机器人")
    parser.add_argument("--cluster", choices=["dsw", "x10000"], default="x10000")
    parser.add_argument("--url", help="自定义 URL")
    parser.add_argument("--interval", type=int, default=30, help="检查间隔秒数")
    parser.add_argument("--stall_threshold", type=int, default=600, help="停更报警阈值秒数")
    parser.add_argument("--at_user_ids", nargs='*', default=['000808'], help="需要 @ 的用户 ID 列表")
    return parser.parse_args()


def monitor(args):
    last_step = -1
    last_update_time = time.time()
    last_status = "UNKNOWN"
    already_alerted_network_error = False
    already_alerted_watchdog_down = False
    already_alerted_stalled = False
    last_watchdog_update_time = 0

    # 根据参数选择数据源
    if args.cluster == "dsw":
        url = args.url or "https://.../training_status.json"
        source = DSWSource(url)
    else:
        url = args.url or "http://127.0.0.1:8003/training_status.json"
        source = LocalSource(url)
    print(f"监控启动，当前数据源: {type(source).__name__}")
    
    config_path = os.path.join(os.path.dirname(__file__), "config", "robots.yaml")
    notifier = DingTalkNotifier(config_path)
    while True:
        data = source.get_data() # 多态调用
        now = time.time()
        if not data:
            print(f"[{time.strftime('%H:%M:%S')}] 无法获取数据，正在重试...")
            if not already_alerted_network_error:
                idle_sec = now - last_update_time
                print(f"[{time.strftime('%H:%M:%S')}] 无法获取数据，已超过 {int(idle_sec)}s 未更新...")
                if idle_sec >= args.stall_threshold:
                    print(f"[{time.strftime('%H:%M:%S')}] 无法获取数据，已超过 {args.stall_threshold}s 未更新！")
                    alert_reason = f"❌ **无法获取数据：请检查 VPN 或 Cookie 是否失效**"
                    notifier.send_message(args.robot, alert_reason, at_user_ids=args.at_user_ids)
                    already_alerted_network_error = True
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] 无法获取数据，但还未达到报警阈值。")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] 无法获取数据，已超过报警阈值，等待下一次检查...")
        else:
            print(f"[{time.strftime('%H:%M:%S')}] 成功获取数据: 状态 {data.get('status', 'N/A')} | 步数 {data.get('current_step', 'N/A')}/{data.get('total_steps', 'N/A')} | Loss {data.get('current_loss', 'N/A')}")
            already_alerted_network_error = False
            time_str = data.get("updated", '1970-01-01 00:00:00')
            watchdog_update_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").timestamp()
            if watchdog_update_time <= last_watchdog_update_time:
                if status == "FINISHED":
                    print(f"[{time.strftime('%H:%M:%S')}] 任务已完成，监控结束。")
                    break
                elif not already_alerted_watchdog_down:
                    idle_sec = now - last_update_time
                    if idle_sec >= args.stall_threshold:
                        alert_reason = f"❌ **服务端进程出错：超过 {args.stall_threshold}s 未见数据更新**"
                        notifier.send_message(args.robot, alert_reason, at_user_ids=args.at_user_ids)
                        already_alerted_watchdog_down = True
                    else:
                        print(f"[{time.strftime('%H:%M:%S')}] 数据未更新，已超过 {int(idle_sec)}s，但还未达到报警阈值。")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] 数据未更新，已超过报警阈值，等待下一次检查...")
                    
            else:
                print(f"[{time.strftime('%H:%M:%S')}] 数据更新，重置停更报警计时器。")
                already_alerted_watchdog_down = False
                last_watchdog_update_time = watchdog_update_time
                last_update_time = now
                status = data.get("status", "UNKNOWN")
                curr_step = data.get("current_step", 0)
                total_step = data.get("total_steps", 0)
                loss = data.get("current_loss", "N/A")
                msg = data.get("message", "")
                is_spike = data.get("is_spike", False)
                restarted = data.get("restarted", False)    
            
                if status == "FINISHED":
                    alert_reason = f"✅ **任务完成：模型已达到目标步数**"
                    content = (
                        f"- **当前状态**: {status}\n"
                        f"- **训练进度**: `{curr_step} / {total_step}`\n"
                        f"- **当前 Loss**: `{loss}`\n\n"
                        f"{alert_reason}"
                    )
                    notifier.send_message(args.robot, content, at_user_ids=args.at_user_ids)
                    break
                else:
                    # 1. 检查进度是否有变化 (用 step 判断比用 text 判断更准)
                    if curr_step == last_step:
                        print(f"[{time.strftime('%H:%M:%S')}] 进度未变: {curr_step}/{total_step} | Loss: {loss}")
                        if status == "STALLED" and not already_alerted_stalled:
                            alert_reason = f"⚠️ **训练卡死**\n> {msg}"
                            content = (
                                f"- **当前状态**: {status}\n"
                                f"- **训练进度**: `{curr_step} / {total_step}`\n"
                                f"- **当前 Loss**: `{loss}`\n\n"
                                f"{alert_reason}"
                            )
                            notifier.send_message(args.robot, content, at_user_ids=args.at_user_ids)
                            already_alerted_stalled = True
                    else:
                        already_alerted_stalled = False
                        last_step = curr_step
                        print(f"[{time.strftime('%H:%M:%S')}] 进度更新: {curr_step}/{total_step} | Loss: {loss} | is_spike: {is_spike} | restarted: {restarted}")
                        alert_reason = ""
                        if status == "CRITICAL" and last_status != "CRITICAL":
                            alert_reason = f"🚨 **训练异常：Loss 持续过高**\n> {msg}"
                        # elif is_spike:
                        #     alert_reason = f"📉 **瞬时尖峰：检测到 Loss 突变**\n> {msg}"
                        elif restarted:
                            alert_reason = f"🔄 **训练重启：检测到训练进程重启**\n> {msg}"
                        # 发送报警
                        if alert_reason:
                            content = (
                                f"- **当前状态**: {status}\n"
                                f"- **训练进度**: `{curr_step} / {total_step}`\n"
                                f"- **当前 Loss**: `{loss}`\n\n"
                                f"{alert_reason}"
                            )
                            notifier.send_message(args.robot, content, at_user_ids=args.at_user_ids)
                        last_status = status
  
        time.sleep(args.interval)


def main():
    args = get_args()
    monitor(args)


if __name__ == "__main__":
    main()