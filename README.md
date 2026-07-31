# Google Health Claude Bridge

> 把 Google Health 中由手表、手机和 Fitbit 设备记录的健康数据，安全接入 Claude 对话。

[English](README.en.md)

Google Health Claude Bridge 是一个**本地优先、自托管、只读**的 Google Health 数据桥接服务。它从 Google Health API v4 读取数据，保存在你自己的设备或服务器中，再通过 MCP 提供给 Claude。Claude 可以在对话里查询和比较你的睡眠、活动、恢复状态与长期趋势，而不需要直接访问数据库。

这个项目明确面向 **Google Health / Fitbit / Pixel Watch 用户**。它不是 Apple Health 导入器，也不是医疗诊断系统。

## 可以做什么

目前可读取和分析：

- 睡眠时长与睡眠记录
- 步数、活动分钟、久坐时长与锻炼
- HRV、静息心率、血氧、呼吸频率
- 睡眠温度变化
- 体重
- 分时段比较、趋势、缺失数据、来源重叠和时区变化

MCP 端提供 8 个只读工具：

- `get_health_overview`
- `get_sleep`
- `get_recovery`
- `get_activity`
- `get_metric`
- `compare_periods`
- `get_data_quality`
- `get_daily_brief_context`

```text
Google Health API v4
        ↓
你自己的设备、服务器与数据库
        ↓
只读 MCP 服务
        ↓
Claude 网页版 / 手机端 / Claude Desktop / Claude Code
```

## 账号要求

### Claude

Claude 的远程自定义 MCP 连接器目前支持 Free、Pro、Max、Team 和 Enterprise。免费用户最多添加 1 个自定义连接器。

官方说明：<https://support.claude.com/zh-CN/articles/11175166>

### ChatGPT / Codex

本项目以 Claude 对话为主要入口，同时保留对其他 MCP 客户端的兼容。ChatGPT、Codex 的套餐要求和功能开放可能随账号、地区与产品模式变化，请以 OpenAI 当前官方说明和你的实际界面为准。

官方说明：<https://help.openai.com/en/articles/11487775-connectors-in>

---

# 先选择部署方式

项目本身**不强制要求 Linux、域名或 Cloudflare**。它是一个 Python 3.12+ 服务，也可以运行在 macOS、Windows、NAS 或支持容器的系统中。

下面的命令以 **Ubuntu / Debian Linux 服务器**为例，因为这是最常见、最适合长期运行的环境；其他系统只需要替换路径、权限和服务管理方式。

根据你准备使用的客户端和网络条件，选择一种部署方式：

| 模式 | 公网 IP | 域名 | Cloudflare | Claude 网页版/手机端 | Claude Code/Codex |
| --- | --- | --- | --- | --- | --- |
| 本地或 SSH 隧道 | 不需要 | 不需要 | 不需要 | 不支持远程连接 | 支持 |
| 公网直连 | 需要 | 正式使用需要 | 不需要 | 支持，但必须自行提供 HTTPS 与 OAuth 认证层 | 支持 |
| Cloudflare Tunnel | 不需要 | 正式使用需要 | 需要 | 支持，配置最省事 | 支持 |
| Quick Tunnel 测试 | 不需要 | 不需要 | 需要 | 仅临时测试 | 仅临时测试 |

## 重要结论

- **Linux 只是本文示例环境，不是项目硬性要求。**
- **Cloudflare 是可选方案，不是项目依赖。**有公网 IP 的服务器可以直接使用 Nginx、Caddy 或现有反向代理。
- **公网 IP 可以替代 Cloudflare Tunnel，但不能完全替代正式域名。**Google OAuth 的正式回调和 Claude 远程连接都更适合稳定的 HTTPS 主机名；直接使用裸 IP 不适合作为长期生产地址。
- **只使用 Claude Code、Codex 或本地 MCP 客户端时，可以通过 SSH 隧道工作，不需要域名、Cloudflare 或公网 Web 服务。**
- 真实健康数据不能通过无认证的公网 MCP 端点暴露。

推荐选择：

- 只在自己的电脑上用 Claude Code：选择 **本地或 SSH 隧道**。
- 已有公网服务器、域名、HTTPS 和统一认证：选择 **公网直连**。
- 想接入 Claude 网页版或手机端，又不想开放服务器端口：选择 **Cloudflare Tunnel + Access**。

---

# 通用安装步骤

以下步骤适用于三种部署模式。

## 1. 准备条件

基础条件：

- 能运行 Python 3.12+ 的电脑、NAS 或服务器
- Git
- Google Cloud 项目
- 已启用的 Google Health API
- Google OAuth Web Client

本文 Linux 示例还会使用：

- `systemd`：让服务常驻运行
- `curl`：健康检查
- `uv`：安装 Python 依赖

确认版本：

```bash
python3 --version
git --version
```

安装 `uv`：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.profile
uv --version
```

## 2. 下载项目

```bash
sudo mkdir -p /opt/google-health-claude-bridge
sudo chown "$USER":"$USER" /opt/google-health-claude-bridge

git clone https://github.com/ArthurADDDDD/google-health-claude-bridge.git \
  /opt/google-health-claude-bridge
cd /opt/google-health-claude-bridge

uv sync --locked
mkdir -p data credentials reports
chmod 700 data credentials reports
```

在 Windows、macOS 或 NAS 上，项目目录可以放在任意你有写入权限的位置，不必使用 `/opt`。

## 3. 先确定 Google OAuth 回调地址

回调地址取决于你的部署模式。

### 本地或 SSH 隧道

```text
http://localhost:8000/oauth/google-health/callback
```

### 公网直连或 Cloudflare Tunnel

```text
https://health.example.com/oauth/google-health/callback
```

把 `health.example.com` 替换为你自己的实际域名。

## 4. 创建 Google Cloud OAuth 凭据

在 Google Cloud Console 中：

1. 创建或选择一个项目。
2. 在 API Library 中启用 **Google Health API**。
3. 配置 OAuth consent screen。
4. 应用类型选择 **External**。
5. 测试阶段把你自己的 Google 账号加入 Test users。
6. 创建 OAuth Client ID，类型选择 **Web application**。
7. 将上一步选定的完整回调地址加入 **Authorized redirect URIs**。

项目只请求以下只读权限：

```text
https://www.googleapis.com/auth/googlehealth.sleep.readonly
https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly
https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly
```

Google 官方入门文档：<https://developers.google.com/health/get-started>

## 5. 生成 Token 加密密钥

Google OAuth Token 会加密保存在你自己的设备或服务器中：

```bash
cd /opt/google-health-claude-bridge
uv run python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

保存输出结果。不要把它提交到 GitHub，也不要和数据库备份放在同一个公开位置。

## 6. 创建 `.env`

```bash
cd /opt/google-health-claude-bridge
cp .env.example .env
chmod 600 .env
nano .env
```

基础配置：

```dotenv
APP_ENV=production
HEALTH_PROVIDER=google

DATABASE_URL=sqlite:////opt/google-health-claude-bridge/data/health.sqlite

MCP_HOST=127.0.0.1
MCP_PORT=8000

PREFERRED_STEP_SOURCE=

GOOGLE_CLIENT_ID=你的_Google_Client_ID
GOOGLE_CLIENT_SECRET=你的_Google_Client_Secret
GOOGLE_REDIRECT_URI=按部署模式填写完整回调地址
GOOGLE_TOKEN_ENCRYPTION_KEY=刚才生成的_Fernet_密钥

# 当前版本在 production + google 模式下要求 MAILER 不是 console。
# 不使用 Daily Brief 时也可以保留 smtp，SMTP 字段暂时留空。
MAILER=smtp
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
MAIL_FROM=
MAIL_TO=
DAILY_BRIEF_AGENT=claude
```

接下来按部署模式补充 MCP 认证配置。

### 模式 A：本地或 SSH 隧道

服务只监听服务器本机，不对公网开放：

```dotenv
MCP_AUTH_ENABLED=false
HEALTH_MCP_TOKEN=
HEALTH_MCP_TOKENS=
MCP_ALLOWED_HOSTS=
MCP_ALLOWED_ORIGINS=
```

### 模式 B/C：公网直连或 Cloudflare Tunnel

如果所有路由都由 Cloudflare Access、oauth2-proxy、Keycloak、Auth0、Authelia 或其他可靠认证层保护，可以保持：

```dotenv
MCP_AUTH_ENABLED=false
HEALTH_MCP_TOKEN=
HEALTH_MCP_TOKENS=
MCP_ALLOWED_HOSTS=
MCP_ALLOWED_ORIGINS=
```

这里的前提是：**外部认证层必须同时保护 `/mcp`、`/oauth/google-health/login` 和其他公开路由。**

只面向 Claude Code 或 Codex、准备使用项目内置 Bearer Token 时，可以改为：

```dotenv
MCP_AUTH_ENABLED=true
HEALTH_MCP_TOKEN=替换为足够长的随机字符串
HEALTH_MCP_TOKENS=
MCP_ALLOWED_HOSTS=
MCP_ALLOWED_ORIGINS=
```

内置 Bearer Token 只保护 MCP 路径，不能代替公网 OAuth 网关对 Google 授权入口的整体保护。因此真实数据的公网部署仍建议使用统一认证层。

## 7. 本机启动测试

```bash
cd /opt/google-health-claude-bridge
uv run healthctl doctor
uv run healthctl serve
```

在另一个终端或 SSH 窗口测试：

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
```

预期返回类似：

```json
{"status":"ok","service":"google-health-agent"}
```

确认正常后停止前台测试服务，继续配置常驻运行。

## 8. 配置 systemd 常驻运行（Linux 示例）

先确认运行用户：

```bash
whoami
```

创建服务文件：

```bash
sudo nano /etc/systemd/system/google-health-claude-bridge.service
```

写入以下内容，并把 `YOUR_USER` 替换为实际用户名：

```ini
[Unit]
Description=Google Health Claude Bridge
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/opt/google-health-claude-bridge
EnvironmentFile=/opt/google-health-claude-bridge/.env
ExecStart=/opt/google-health-claude-bridge/.venv/bin/healthctl serve
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

启用服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now google-health-claude-bridge
sudo systemctl status google-health-claude-bridge
```

查看日志：

```bash
journalctl -u google-health-claude-bridge -f
```

macOS、Windows、NAS 或容器环境请使用对应的服务管理方式，不需要安装 systemd。

---

# 模式 A：本地或 SSH 隧道

适合 Claude Code、Codex、MCP Inspector 或其他本地 MCP 客户端。

它不需要：

- 域名
- Cloudflare
- 公网 80/443 端口
- 把 MCP 服务暴露到互联网

如果客户端和服务在同一台机器上，直接使用：

```text
http://127.0.0.1:8000/mcp
```

如果服务运行在另一台服务器上，在客户端电脑建立 SSH 隧道：

```bash
ssh -N -L 8000:127.0.0.1:8000 YOUR_USER@YOUR_SERVER_IP
```

保持 SSH 窗口运行，然后在本地浏览器打开 Google 授权入口：

```text
http://localhost:8000/oauth/google-health/login
```

完成授权后，连接 Claude Code：

```bash
claude mcp add --transport http google-health \
  http://127.0.0.1:8000/mcp
```

或连接 Codex：

```bash
codex mcp add google_health_agent \
  --url http://127.0.0.1:8000/mcp
```

> Claude 网页版和手机端的请求来自 Anthropic 云端，无法通过你电脑上的 SSH 隧道访问，因此远程自定义连接器需要模式 B 或模式 C。

---

# 模式 B：公网 IP + 域名直连

适合已经拥有以下基础设施的用户：

- 服务器公网 IP
- 域名
- 80/443 端口
- Nginx、Caddy、Traefik 或现有反向代理
- HTTPS 证书
- OAuth 或统一身份认证网关

Cloudflare 在这个模式下**不是必需的**。

典型结构：

```text
Claude
  ↓ HTTPS + OAuth
你的域名
  ↓
Nginx / Caddy / Traefik + 认证网关
  ↓
127.0.0.1:8000
  ↓
Google Health Claude Bridge
```

## 1. 配置 DNS

将域名的 A/AAAA 记录指向服务器公网 IP，例如：

```text
health.example.com → 你的服务器公网 IP
```

## 2. 配置 HTTPS 反向代理

下面仅以 Caddy 为例：

```caddyfile
health.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

Caddy 可以自动申请 HTTPS 证书，但这个最小示例**只完成 TLS 和反向代理，不包含身份认证**。

在真实健康数据上线前，必须在域名前增加 OAuth 或统一认证层，并保护整个站点。可以使用你现有的：

- oauth2-proxy
- Keycloak
- Auth0
- Authelia
- Caddy Security
- Nginx `auth_request`
- 其他支持远程 MCP OAuth 的网关

如果只给 Claude Code/Codex 使用静态 Bearer Token，也要额外限制 Google OAuth 授权入口，不能让 `/oauth/google-health/login` 无认证暴露在公网。

## 3. 使用公网地址

Google OAuth 回调：

```text
https://health.example.com/oauth/google-health/callback
```

MCP 地址：

```text
https://health.example.com/mcp
```

健康检查：

```text
https://health.example.com/healthz
```

---

# 模式 C：Cloudflare Tunnel + Access

这是接入 Claude 网页版和手机端时最省事的方案，但仍然只是可选方案。

它的优势：

- 服务器不需要公网 IP
- 不需要开放入站 8000、80 或 443 端口
- 源站继续只监听 `127.0.0.1`
- Cloudflare Access 可以只允许你的邮箱
- Managed OAuth 可以为 Claude 远程连接器提供 OAuth 登录流程

典型结构：

```text
Claude
  ↓ OAuth
Cloudflare Access
  ↓
Cloudflare Tunnel
  ↓
127.0.0.1:8000
  ↓
Google Health Claude Bridge
```

## 1. 创建 Cloudflare Tunnel

在 Cloudflare Dashboard 中：

1. 打开 **Networking → Tunnels**。
2. 创建 Tunnel，例如 `google-health-claude`。
3. 选择对应的服务器系统，复制 Cloudflare 给出的安装和启动命令执行。
4. 新增 Public Hostname：

```text
Hostname: health.example.com
Service:  http://localhost:8000
```

Cloudflare 官方文档：<https://developers.cloudflare.com/tunnel/setup/>

## 2. 用 Cloudflare Access 保护整个域名

在 Cloudflare Zero Trust 中：

1. 打开 **Access controls → Applications**。
2. 新建一个 **Self-hosted application**。
3. 域名填写 `health.example.com`。
4. 创建 Allow Policy，只允许你自己的邮箱或指定账号。
5. 在 Advanced settings 中启用 **Managed OAuth**。
6. 确认 Access Policy 覆盖整个主机，而不只是 `/mcp`。

官方文档：<https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/managed-oauth/>

完成后访问：

```text
https://health.example.com/healthz
```

浏览器应先要求登录 Cloudflare Access，然后才显示健康检查结果。

---

# 授权 Google Health

完成所选网络模式后，在浏览器打开：

### 本地或 SSH 隧道

```text
http://localhost:8000/oauth/google-health/login
```

### 公网直连或 Cloudflare Tunnel

```text
https://health.example.com/oauth/google-health/login
```

按顺序完成：

1. 如果配置了外部认证，先完成认证网关登录。
2. 登录你的 Google 账号。
3. 同意项目请求的 Google Health 只读权限。
4. 页面显示：

```json
{
  "status": "authorized",
  "message": "Google Health authorization stored securely."
}
```

首次同步建议从较小范围开始：

```bash
cd /opt/google-health-claude-bridge
uv run healthctl sync --days 3
uv run healthctl status
uv run healthctl analytics --metric hrv --days 3
```

确认数据来源、时区和数量无误后，再增加到 7、30、90 或 365 天：

```bash
uv run healthctl sync --days 7
uv run healthctl sync --days 30
uv run healthctl sync --days 90
```

---

# 添加到 Claude 对话

远程模式 B/C 完成后，在 Claude 网页版、桌面端或手机端：

1. 打开 **Customize → Connectors**。
2. 点击 `+`。
3. 选择 **Add custom connector**。
4. 名称填写 `Google Health`。
5. URL 填写：

```text
https://health.example.com/mcp
```

6. 保存并完成认证网关的 OAuth 登录。
7. 在新对话的 Connectors 中启用 Google Health。

测试提问：

```text
先检查最近 30 天的数据质量，再总结我的睡眠、活动和恢复趋势。
请把观察到的事实、统计比较和推测分开写，不要进行疾病诊断。
```

## Claude Code 使用远程地址

OAuth 保护的远程端点：

```bash
claude mcp add --transport http google-health \
  https://health.example.com/mcp
```

进入 Claude Code 后执行：

```text
/mcp
```

按提示在浏览器完成 OAuth 登录。

Bearer Token 保护的远程端点：

```bash
claude mcp add --transport http google-health \
  https://health.example.com/mcp \
  --header "Authorization: Bearer YOUR_TOKEN"
```

静态 Bearer 方式适合 Claude Code 和 Codex，不是 Claude 网页版自定义连接器的首选方式。

---

# 没有域名怎么办

## 方案 1：使用本地或 SSH 隧道

这是处理真实数据时最安全的无域名方案。它只支持本地 MCP 客户端，不支持 Claude 网页版或手机端。

## 方案 2：Cloudflare Quick Tunnel 临时测试

```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

Cloudflare 会返回类似：

```text
https://random-words.trycloudflare.com
```

MCP 地址：

```text
https://random-words.trycloudflare.com/mcp
```

Quick Tunnel 只适合合成数据或临时联调：

- URL 每次重启可能改变
- 没有稳定性承诺
- 不适合作为固定 Google OAuth 回调地址
- 不应在无认证状态下暴露真实健康数据

官方说明：<https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/>

---

# PostgreSQL 可选配置

SQLite 对单用户通常够用。如果需要 PostgreSQL：

```bash
uv sync --locked --extra postgres
```

将 `.env` 中的数据库地址改为：

```dotenv
DATABASE_URL=postgresql+psycopg://health_user:强密码@127.0.0.1:5432/google_health
```

数据库用户应只拥有这个数据库，不要使用 PostgreSQL 超级管理员账号运行应用。

执行迁移：

```bash
cd /opt/google-health-claude-bridge
uv run alembic upgrade head
sudo systemctl restart google-health-claude-bridge
```

---

# 数据同步与自动更新

手动同步：

```bash
cd /opt/google-health-claude-bridge
uv run healthctl sync --days 7
```

每天自动同步可以使用 cron：

```bash
crontab -e
```

示例：每天早上 06:15 同步最近 7 天。重复数据会按 ID 更新，而不是无限追加。

```cron
15 6 * * * cd /opt/google-health-claude-bridge && /opt/google-health-claude-bridge/.venv/bin/healthctl sync --days 7 >> /var/log/google-health-sync.log 2>&1
```

Daily Brief 邮件属于可选功能，不影响 Claude 在对话中通过 MCP 查询健康数据。

---

# 更新项目

```bash
cd /opt/google-health-claude-bridge
git pull
uv sync --locked
sudo systemctl restart google-health-claude-bridge
sudo systemctl status google-health-claude-bridge
```

使用 PostgreSQL 时，更新后再执行：

```bash
uv run alembic upgrade head
```

---

# 备份

至少备份：

```text
/opt/google-health-claude-bridge/data/health.sqlite
/opt/google-health-claude-bridge/credentials/google-health-token.enc
```

另外单独保存：

```text
GOOGLE_TOKEN_ENCRYPTION_KEY
```

不要把加密 Token、数据库和解密密钥全部放在同一个公开备份里。

---

# 常见问题

详见 [常见问题](docs/faq.md)。

---

# 安全原则

- MCP 工具全部只读
- Google OAuth 只申请只读健康权限
- 源站默认只监听 `127.0.0.1`
- 真实数据的公网入口必须由 OAuth、统一认证网关或其他可靠认证保护
- 外部认证应保护整个主机，而不只是 `/mcp`
- 不要公开 `.env`、OAuth Client Secret、数据库或 Token 文件
- 不要把健康数据、日志、截图和备份提交到 GitHub
- 仅连接你自己部署并信任的 MCP 服务
- Claude 的解释不能替代医生诊断

## 致谢

本项目受 [Google Health Worker MCP V1](https://github.com/Ring8688/google-health-worker-mcp-V1) 启发，在此表示感谢。

## License

MIT License，详见 [LICENSE](LICENSE)。
