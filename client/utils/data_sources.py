import requests
import browser_cookie3
import time

class DataSource:
    def get_data(self):
        raise NotImplementedError

class DSWSource(DataSource):
    """DSW 集群：需要浏览器 Cookie 和 域名代理"""
    def __init__(self, url):
        self.url = url

    def get_data(self):
        timestamp_url = f"{self.url}?t={int(time.time())}"
        try:
            cj = browser_cookie3.chrome(domain_name='aliyun.com')
            headers = {"Cache-Control": "no-cache"}
            resp = requests.get(timestamp_url, cookies=cj, headers=headers, timeout=10)
            return resp.json() if resp.status_code == 200 else None
        except Exception as e:
            print(f"DSW 获取失败: {e}")
            return None

class LocalSource(DataSource):
    """X10000 等集群：本地直连 (HTTP 127.0.0.1)"""
    def __init__(self, url="http://127.0.0.1:8003/training_status.json"):
        self.url = url

    def get_data(self):
        try:
            # 本地通常不需要 Cookie
            resp = requests.get(self.url, timeout=5)
            return resp.json() if resp.status_code == 200 else None
        except Exception as e:
            print(f"本地获取失败: {e}")
            return None