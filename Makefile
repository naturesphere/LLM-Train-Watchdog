# ==========================================
# 2. 客户端配置 (运行在本地)
# ==========================================
CLUSTER_TYPE ?= x10000  # 可选: x10000, dsw
TARGET_URL ?= http://127.0.0.1:8003/training_status.json

# 启动本地报警客户端 (需要外网权限发钉钉)
client-monitor:
	@echo "🔔 Launching Local Monitor Client..."
	cd client && python3 monitor.py --cluster $(CLUSTER_TYPE) --url $(TARGET_URL)