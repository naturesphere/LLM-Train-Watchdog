import argparse
from core.engine import MonitorEngine
from core.context import MonitorContext
from handlers.resolvers import AliyunDSWResolver
from handlers.parsers import LossParser
from handlers.analyzers import RestartDetector, SpikeDetector, Archiver

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_dir", type=str, default=".")
    parser.add_argument("--pattern", type=str, default="*/worker_*/none_*/attempt_0/*/stdout.log")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--threshold", type=int, default=600)
    parser.add_argument("--keyword", type=str, default="lm loss")
    return parser.parse_args()

if __name__ == "__main__":
    args = get_args()
    ctx = MonitorContext(args)
    engine = MonitorEngine(ctx)

    # 组装中间件流水线
    engine.add_middleware(AliyunDSWResolver())
    engine.add_middleware(RestartDetector())
    engine.add_middleware(LossParser())
    engine.add_middleware(SpikeDetector(window_size=20, threshold=1.4))
    engine.add_middleware(Archiver())

    try:
        engine.start()
    except KeyboardInterrupt:
        print("\nMonitor stopped.")