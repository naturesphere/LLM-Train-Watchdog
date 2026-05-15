import time
import hmac
import hashlib
import base64
import urllib.parse
import requests
import yaml
import os

class DingTalkNotifier:
    def __init__(self, config_path="config/robots.yaml"):
        self.config_path = config_path
        self.robots = self._load_config()

    def _load_config(self):
        """加载本地 YAML 配置"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"配置文件未找到: {self.config_path}，请确保本地已创建该文件。")
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _get_signature(self, secret):
        """根据钉钉安全设置生成时间戳和签名"""
        timestamp = str(round(time.time() * 1000))
        secret_enc = secret.encode('utf-8')
        string_to_sign = f'{timestamp}\n{secret}'
        string_to_sign_enc = string_to_sign.encode('utf-8')
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return timestamp, sign

    def send_message(self, robot_name, content, title="训练预警", at_user_ids=[]):
        """
        向指定的机器人发送 Markdown 消息
        :param robot_name: 对应 YAML 中的 key (如 'default_alpha')
        :param content: 消息内容 (支持 Markdown)
        :param title: 消息标题
        """
        conf = self.robots.get(robot_name)
        if not conf:
            print(f"❌ 错误: 未找到机器人配置 '{robot_name}'")
            return

        webhook = conf.get("webhook")
        secret = conf.get("secret")
        timestamp, sign = self._get_signature(secret)
        
        # 组装带签名的 URL
        final_url = f"{webhook}&timestamp={timestamp}&sign={sign}"
        at_text = ""
        if at_user_ids:
            # 钉钉 Markdown 需要在正文里包含 @用户ID 才能触发高亮和推送
            at_text = "\n\n" + " ".join([f" @{uid} " for uid in at_user_ids])
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"### {title}\n---\n{content}{at_text}\n\n> 监控时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            },
           "at": {
                "atUserIds": at_user_ids,
                "isAtAll": False,
                "atMobiles": []
            }
        }

        try:
            resp = requests.post(final_url, json=payload, timeout=10)
            result = resp.json()
            if result.get("errcode") == 0:
                print(f"✅ [{robot_name}] 消息发送成功")
            else:
                print(f"❌ [{robot_name}] 发送失败: {result.get('errmsg')}")
        except Exception as e:
            print(f"⚠️ 网络异常: {e}")

# 快速测试脚本
if __name__ == "__main__":
    # 假设在 client 目录下运行
    notifier = DingTalkNotifier("../config/robots.yaml")
    notifier.send_message("default_alpha", "测试消息：这是 Alpha 机器人。", 'test', at_user_ids=['000808', '001081', '002234'])
    notifier.send_message("021_beta", "测试消息：这是 Beta 机器人。", 'test', at_user_ids=['000808', '001081', '002234']) 