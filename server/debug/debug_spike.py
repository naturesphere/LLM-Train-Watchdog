import matplotlib.pyplot as plt
from handlers.analyzers import SpikeDetector, PersistentHighLossDetector
from core.context import MonitorContext
import pandas as pd
import numpy as np


def debug_spike_threshold(loss_sequence, threshold=1.5, window_size=100):
    """
    仿真调试函数
    """
    # 1. 模拟环境初始化
    class DummyArgs:
        base_dir = "."
        threshold = 600 
    
    ctx = MonitorContext(DummyArgs())
    # 实例化两个检测器
    detector = SpikeDetector(window_size=window_size, threshold=threshold)
    # 针对 1.2T 模型，1.2倍均值且持续50步被判定为异常
    p_steps = 50
    detector_p = PersistentHighLossDetector(threshold=2, p_steps=p_steps)
    
    spikes_x = []
    spikes_y = []
    critical_indices = [] # 记录判定为 CRITICAL 的所有索引
    
    # 2. 模拟流式处理
    for i, val in enumerate(loss_sequence):
        # 模拟 Parser 更新上下文
        ctx.data["current_loss"] = val
        ctx.last_mtime = i  
        
        # 执行检测：注意顺序，detector 先计算 avg 并放入 ctx，detector_p 再使用
        detector.process(ctx)
        detector_p.process(ctx)
        
        # 记录瞬时尖峰
        if ctx.data.get("is_spike"):
            spikes_x.append(i)
            spikes_y.append(val)
            
        # 记录持续性异常状态
        if ctx.data.get("status") == "CRITICAL":
            critical_indices.append(i)

    # 3. 结果可视化
    plt.figure(figsize=(16, 8))
    
    # 绘制原始 Loss 曲线
    plt.plot(loss_sequence, label='LM Loss', color='#1f77b4', alpha=0.6, linewidth=1)
    
    # 绘制瞬时尖峰点
    if spikes_x:
        plt.scatter(spikes_x, spikes_y, color='red', label='Instant Spike', zorder=5, s=20)
    
    # 绘制持续异常区间 (CRITICAL Regions)
    # 将连续的索引合并为区间进行着色
    if critical_indices:
            corrected_intervals = self_get_intervals_corrected(critical_indices, p_steps)
            for i, (start, end) in enumerate(corrected_intervals):
                plt.axvspan(start, end, color='orange', alpha=0.3, 
                            label='Corrected Critical Region' if i == 0 else "")
    plt.title(f"LLM Watchdog Debug: Spike & Persistent High Loss\n(Spike Threshold: {threshold}, Critical: 1.2x/50steps)", fontsize=14)
    plt.xlabel("Steps (Training Progress)")
    plt.ylabel("Loss Value")
    
    # 优化图例，防止重复
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    plt.legend(by_label.values(), by_label.keys(), loc='upper right')
    
    plt.grid(True, linestyle='--', alpha=0.4)
    
    save_path = f'spike_debug_{threshold}_correctd.png'
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"--- 调试报告 ---")
    print(f"总样本数: {len(loss_sequence)}")
    print(f"检测到瞬时尖峰: {len(spikes_x)} 次")
    print(f"检测到持续异常步数: {len(critical_indices)} 步")
    print(f"结果已保存至: {save_path}")


def self_get_intervals_corrected(indices, p_steps=50):
    """
    辅助函数：将离散的索引转换为连续的区间 [(start, end), ...]
    """
    if not indices: return []
    intervals = []
    start = indices[0]
    for i in range(1, len(indices)):
        if indices[i] != indices[i-1] + 1:
            intervals.append((max(0, start - p_steps), max(0, indices[i-1] - p_steps)))
            start = indices[i]
    intervals.append((max(0, start - p_steps), max(0, indices[-1] - p_steps)))
    return intervals


def get_lmloss():
    # 保持你原有的读取逻辑
    fp = '/mnt/si001081jz1d/users/cjj/logs/draw_tf_logs/834B_8T_baseline/train_logs-x10000.xlsx'
    try:
        df = pd.read_excel(fp)
        loss_sequence = df['lm loss'].tolist()
        return loss_sequence
    except Exception as e:
        print(f"读取文件失败: {e}")
        return []


def main():
    test_loss_data = get_lmloss()
    if test_loss_data:
        # 你可以尝试 2.5, 3.0 等不同阈值观察效果
        debug_spike_threshold(test_loss_data, threshold=2.5)


if __name__ == "__main__":
    main()