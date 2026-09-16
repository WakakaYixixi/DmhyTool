# DMHY Tool

这是一个轻量的 FastAPI Web 服务，可实时搜索动漫花园资源、在浏览器本地保存搜索词、勾选结果并按需导出 magnet 链接，或直接将所选资源加入 Synology Download Station。项目不包含 RSS 搜索、自动追番、用户系统或数据库。

## Download Station 配置

复制示例文件并填写 DSM 连接信息：

```bash
cp .env.example .env
```

```dotenv
DSM_URL=https://nas.example.com
DSM_USERNAME=download-user
DSM_PASSWORD=
DSM_DOWNLOAD_DIR=
DSM_VERIFY_SSL=true
```

| 环境变量 | 必填 | 说明 |
| --- | --- | --- |
| `DSM_URL` | 是 | DSM 基础地址，包含 `http://` 或 `https://`，不要附加 `/webapi` |
| `DSM_USERNAME` | 是 | 具有 Download Station 权限的 DSM 账号 |
| `DSM_PASSWORD` | 是 | DSM 账号密码，仅保存在 NAS 的 `.env` 中 |
| `DSM_DOWNLOAD_DIR` | 否 | Download Station 目标目录；留空使用 DSM 默认目录 |
| `DSM_VERIFY_SSL` | 否 | 默认 `true`；仅在使用自签名证书且确认风险时设为 `false` |

`DSM_DOWNLOAD_DIR` 使用 DSM Download Station 接受的、以共享文件夹开头的路径，例如 `downloads/anime`。请确保配置账号对该目录具有写入权限。

`.env` 已被 Git 和 Docker 构建上下文忽略，不能提交真实密码或 SID。修改环境变量后需要重新创建容器。

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

- 首页：`http://NAS_IP:6199/`，应显示搜索界面和 `DMHY Tool OK` 状态标识
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
7. Download Station 使用的 DSM 账号只需授予 Download Station 和目标下载目录所需权限，不建议使用管理员账号。

## 接口

| 方法 | 路径 | 响应 |
| --- | --- | --- |
| GET | `/` | 搜索页面 |
| GET | `/health` | JSON `{"status":"ok","service":"dmhytool"}` |
| GET | `/api/search?q=关键词` | 整理后的实时搜索结果 JSON |
| POST | `/api/magnets` | 按需解析所选 DMHY 详情页的 magnet |
| GET | `/api/download/status` | 返回 DSM 是否已配置及目标目录，不返回凭据 |
| POST | `/api/download` | 解析所选详情页 magnet 并逐项创建 Download Station 任务 |

`POST /api/magnets` 请求示例：

```json
{
  "items": [
    {
      "resource": "https://share.dmhy.org/topics/view/724804_example.html",
      "title": "资源标题"
    }
  ]
}
```

后端只允许 DMHY 官方域名下符合 `/topics/view/<数字>_*.html` 格式的详情页，也可直接传数字资源 ID。批量导出并发数限制为 3，单项失败不会中断其他项目。

`POST /api/download` 使用与 `/api/magnets` 相同的请求结构，响应示例：

```json
{
  "success": [
    {
      "resource_id": "724804",
      "title": "资源标题",
      "detail_url": "https://share.dmhy.org/topics/view/724804_example.html"
    }
  ],
  "failed": []
}
```

服务会通过 `SYNO.API.Info` 查询 NAS 实际支持的 API 路径和版本，登录后在内存中保存 SID/SynoToken。DSM 返回会话超时、重复登录或无效 SID 时会自动重新登录一次。密码和 SID 不会返回前端，也不会由应用主动写入日志。
