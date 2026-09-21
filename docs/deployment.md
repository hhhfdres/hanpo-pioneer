# 部署

## 本地演示

```powershell
$env:PYTHONPATH = "src"
python -m hanpo --host 0.0.0.0 --port 8080
```

控制台与 API 在同一端口提供。默认演示设备位于东海测试区域，`POST /api/v1/simulate/tick` 推进模拟状态。

## Docker

```bash
docker build -t hanpo-pioneer:0.1.0 .
docker run --rm -p 8080:8080 hanpo-pioneer:0.1.0
```

或：

```bash
docker compose up --build
```

## 生产边界

参考服务使用内存存储，适合演示、算法验证和接口联调。生产环境应替换以下部分：

- 设备鉴权：mTLS 或设备证书，上传报文带单调序号。
- 消息入口：MQTT broker 或 HTTPS 网关，进入持久化队列。
- 状态存储：时序数据库保存遥测，关系数据库保存告警和确认。
- 模型服务：独立 ONNX Runtime 服务，设置超时和审计日志。
- 地图服务：使用合规底图和坐标转换，不在日志中泄露精确位置。
- 可观测性：指标包括消息延迟、告警确认时延、模型漂移和链路成功率。

## 配置

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `HANPO_DASHBOARD_DIR` | 自动探测 | 控制台静态资源目录 |

生产密钥不得写入仓库。建议使用部署平台的 secret 注入机制。

