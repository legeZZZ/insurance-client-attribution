#!/bin/bash
# 保险销售客户端经营归因 · 控制台一键启动
# 双击本文件即可启动本地控制台并自动打开演示页。
cd "$(dirname "$0")"
echo "正在启动控制台：http://127.0.0.1:8765/"
(sleep 2 && open "http://127.0.0.1:8765/") &
python3 run_server.py 8765
