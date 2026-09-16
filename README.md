# DMHY Tool 链路验证服务

这是一个最小可运行的 FastAPI Web 服务，仅用于验证 Synology NAS Container Manager、宿主机 `6199` 端口和 `dmhy.maskpic.com` 的访问链路。项目不包含搜索、RSS、Download Station、认证或数据库功能。

## 启动

在项目目录执行：

```bash
docker compose up -d --build
```

查看容器状态和日志：

```bash
docker compose ps
docker compose logs -f dmhytool
```

停止服务：

```bash
docker compose down
```

## 验证

将 `NAS_IP` 替换为 NAS 的局域网 IP：

- 首页：`http://NAS_IP:6199/`，应显示 `DMHY Tool OK`
- 健康检查：`http://NAS_IP:6199/health`，应返回 `{"status":"ok","service":"dmhytool"}`

也可在 NAS 上执行：

```bash
curl http://127.0.0.1:6199/
curl http://127.0.0.1:6199/health
```

## Synology Container Manager 部署注意事项

1. 将整个项目目录上传到 NAS，在 Container Manager 的“项目”中从该目录创建 Compose 项目，或通过 SSH 在目录中执行启动命令。
2. 确认 NAS 的 `6199` 端口未被占用，并在 DSM 防火墙中允许所需来源访问 TCP `6199`。
3. Compose 已将宿主机端口 `6199` 映射到容器端口 `8000`；应用在容器内监听 `0.0.0.0:8000`。
4. 若通过 `dmhy.maskpic.com` 访问，在 Synology 反向代理或现有网关中，将该域名的 HTTP/HTTPS 请求转发到 `http://127.0.0.1:6199`（也可使用 NAS 局域网 IP）。HTTPS 证书和 DNS 由 NAS/网关配置，本项目不保存任何凭据。
5. 外网访问时，还需确认域名 DNS、路由器端口转发或隧道、DSM 反向代理及防火墙规则均正确。通常只应对外开放反向代理的 80/443，而无需直接暴露 `6199` 到互联网。
6. 部署后在 Container Manager 中确认容器状态最终变为 `healthy`。

## 接口

| 方法 | 路径 | 响应 |
| --- | --- | --- |
| GET | `/` | 纯文本 `DMHY Tool OK` |
| GET | `/health` | JSON `{"status":"ok","service":"dmhytool"}` |
