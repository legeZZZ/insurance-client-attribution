# HTTP 可执行部署说明

这个项目不是纯静态页。`run_server.py` 会同时提供：

- `/`：演示控制台
- `/api/health`：健康检查
- `/api/track2/scenario-run?...`：真实 Python 归因场景
- `/api/track2/chat`：多轮 Agent 入口

## 本地 HTTP 运行

```bash
python3 run_server.py 8765 --host 127.0.0.1
```

打开：

```text
http://127.0.0.1:8765/
```

## Render 从 GitHub 部署

1. 将本目录作为仓库根目录推送到：

```text
https://github.com/legeZZZ/insurance-client-attribution
```

2. 在 Render 新建 Web Service，选择该 GitHub 仓库。
3. Render 会自动读取 `render.yaml`。
4. 部署完成后打开 Render 分配的 HTTPS 地址。

## Docker 运行

```bash
docker build -t insurance-client-attribution .
docker run --rm -p 8765:8765 insurance-client-attribution
```

打开：

```text
http://127.0.0.1:8765/
```

云平台会注入 `PORT`，服务会自动读取并监听 `0.0.0.0:$PORT`。
