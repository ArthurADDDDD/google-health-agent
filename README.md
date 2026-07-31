# Google Health Claude Bridge

> 把 Google Health 中由手表、手机和 Fitbit 设备记录的健康数据，安全接入 Claude 对话。

[English](README.en.md)

Google Health Claude Bridge 是一个**本地优先、自托管、只读**的 Google Health 数据桥接服务。它从 Google Health API v4 读取数据，保存在你自己的服务器中，再通过 MCP 提供给 Claude。Claude 可以在对话里查询和比较你的睡眠、活动、恢复状态与长期趋势，而不需要直接访问数据库。

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
你自己的服务器与数据库
        ↓
只读 MCP 服务
        ↓
Claude 网页版 / 手机端 / Claude Desktop / Claude Code
```

## 账号要求

### Claude

Claude 的远程自定义 MCP 连接器目前支持 Free、Pro、Max、Team 和 Enterprise。免费用户最多添加 1 个自定义连接器。

官方说明：<https://support.claude.com/zh-CN/articles/11175166>

### ChatGPT

本项目主入口是 Claude，但 MCP 本身也可供其他兼容客户端使用。OpenAI 当前的方案表已把 Custom MCP 列入 Plus 及以上方案；不同地区、账号与功能模式的开放情况仍可能不同。这个项目是只读 MCP，不依赖写入动作。

官方说明：<https://help.openai.com/en/articles/11487775-connectors-in>

## 推荐部署方式

对于 Claude 网页版和手机端，MCP 请求来自 Anthropic 的云端，不是从你的电脑直接发出，因此服务器必须有一个可从公网访问的 HTTPS 地址。

推荐结构：

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

这种方式有几个好处：

- 服务器不需要开放 8000 端口
- 不需要把源站 IP 暴露给公网
- Cloudflare Access 负责 OAuth 登录
- MCP 服务本身只监听 `127.0.0.1`
- 可以只允许你自己的邮箱访问

> 不要把装有真实健康数据的 MCP 端点以无认证方式暴露到公网。

---

# 部署教程：Linux 服务器 + 自有域名 + Cloudflare

以下步骤适合单用户自托管。SQLite 已足够个人使用；需要多用户、高并发或更完整的数据库运维时再换 PostgreSQL。

## 1. 准备条件

你需要：

- 一台 Linux 服务器
- 一个已接入 Cloudflare 的域名
- Python 3.12 或更高版本
- Git
- Google Cloud 项目
- 已启用的 Google Health API
- Google OAuth Web Client

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

## 3. 创建 Google Cloud OAuth 凭据

在 Google Cloud Console 中：

1. 创建或选择一个项目。
2. 在 API Library 中启用 **Google Health API**。
3. 配置 OAuth consent screen。
4. 应用类型选择 **External**。
5. 测试阶段把你自己的 Google 账号加入 Test users。
6. 创建 OAuth Client ID，类型选择 **Web application**。
7. 添加回调地址：

```text
https://health.example.com/oauth/google-health/callback
```

把 `health.example.com` 换成你准备使用的实际域名。

项目只请求以下只读权限：

```text
https://www.googleapis.com/auth/googlehealth.sleep.readonly
https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly
https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly
```

Google 官方入门文档：<https://developers.google.com/health/get-started>

## 4. 生成加密密钥

Google OAuth Token 会加密保存在服务器中。生成 Fernet 密钥：

```bash
cd /opt/google-health-claude-bridge
uv run python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

保存输出结果。不要把它提交到 GitHub，也不要和数据库备份放在同一个公开位置。

## 5. 创建 `.env`

```bash
cd /opt/google-health-claude-bridge
cp .env.example .env
chmod 600 .env
nano .env
```

推荐配置：

```dotenv
APP_ENV=production
HEALTH_PROVIDER=google

DATABASE_URL=sqlite:////opt/google-health-claude-bridge/data/health.sqlite

MCP_HOST=127.0.0.1
MCP_PORT=8000
MCP_AUTH_ENABLED=false
HEALTH_MCP_TOKEN=
HEALTH_MCP_TOKENS=
MCP_ALLOWED_HOSTS=
MCP_ALLOWED_ORIGINS=

PREFERRED_STEP_SOURCE=

GOOGLE_CLIENT_ID=你的_Google_Client_ID
GOOGLE_CLIENT_SECRET=你的_Google_Client_Secret
GOOGLE_REDIRECT_URI=https://health.example.com/oauth/google-health/callback
GOOGLE_TOKEN_ENCRYPTION_KEY=刚才生成的_Fernet_密钥

# 当前版本在 production + google 模式下要求 MAILER 不是 console。
# 只使用 Claude 对话、不运行 Daily Brief 时，保留 smtp 即可，其他 SMTP 项可暂时留空。
MAILER=smtp
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
MAIL_FROM=
MAIL_TO=
DAILY_BRIEF_AGENT=claude
```

这里故意关闭应用内置 Bearer Token，因为 MCP 只监听本机回环地址，公网认证交给 Cloudflare Access。不要在没有 Cloudflare Access 或其他 OAuth 保护的情况下照搬此配置。

## 6. 本机启动测试

```bash
cd /opt/google-health-claude-bridge
uv run healthctl doctor
uv run healthctl serve
```

在另一个 SSH 窗口测试：

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
```

预期返回：

```json
{"status":"ok","service":"google-health-agent"}
```

停止测试服务后继续配置 systemd。

## 7. 配置 systemd 常驻运行

先确认运行用户：

```bash
whoami
```

创建服务文件：

```bash
sudo nano /etc/systemd/system/google-health-claude-bridge.service
```

写入以下内容，并把 `YOUR_USER` 换成实际用户名：

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

## 8. 创建 Cloudflare Tunnel

在 Cloudflare Dashboard 中：

1. 打开 **Networking → Tunnels**。
2. 创建一个 Tunnel，例如 `google-health-claude`。
3. 选择 Linux，并复制 Cloudflare 给出的安装和启动命令到服务器执行。
4. 新增 Public Hostname：

```text
Hostname: health.example.com
Service:  http://localhost:8000
```

Cloudflare Tunnel 使用服务器主动向外建立连接，因此不需要在防火墙开放 8000 端口。

官方文档：<https://developers.cloudflare.com/tunnel/setup/>

## 9. 用 Cloudflare Access 保护 MCP

仅创建 Tunnel 不等于完成认证。真实健康数据必须再加 Cloudflare Access。

在 Cloudflare Zero Trust 中：

1. 打开 **Access controls → Applications**。
2. 新建一个 **Self-hosted application**。
3. 域名填写 `health.example.com`。
4. 创建 Allow Policy，只允许你自己的邮箱或指定账号。
5. 在应用的 Advanced settings 中启用 **Managed OAuth**。

Managed OAuth 会让 Claude 以标准 OAuth 流程登录 Cloudflare Access，而不是直接访问公开 MCP。

官方文档：<https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/managed-oauth/>

完成后测试：

```text
https://health.example.com/healthz
```

浏览器应先要求登录 Cloudflare Access，然后才显示健康检查结果。

## 10. 授权 Google Health

在浏览器打开：

```text
https://health.example.com/oauth/google-health/login
```

按顺序完成：

1. 登录 Cloudflare Access。
2. 登录你的 Google 账号。
3. 同意项目请求的 Google Health 只读权限。
4. 页面显示：

```json
{
  "status": "authorized",
  "message": "Google Health authorization stored securely."
}
```

随后在服务器同步最近 30 天数据：

```bash
cd /opt/google-health-claude-bridge
uv run healthctl sync --days 30
uv run healthctl status
uv run healthctl analytics --metric hrv --days 30
```

首次使用建议先同步 3 天或 7 天确认无误，再增加到 30、90 或 365 天：

```bash
uv run healthctl sync --days 7
uv run healthctl sync --days 90
```

## 11. 添加到 Claude 对话

在 Claude 网页版、桌面端或手机端：

1. 打开 **Customize → Connectors**。
2. 点击 `+`。
3. 选择 **Add custom connector**。
4. 名称填写：

```text
Google Health
```

5. URL 填写：

```text
https://health.example.com/mcp
```

6. 保存并完成 Cloudflare Access 登录。
7. 在新对话左下角 `+ → Connectors` 中启用 Google Health。

测试提问：

```text
先检查最近 30 天的数据质量，再总结我的睡眠、活动和恢复趋势。
请把观察到的事实、统计比较和推测分开写，不要进行疾病诊断。
```

## 12. 可选：连接 Claude Code

使用 Cloudflare Managed OAuth：

```bash
claude mcp add --transport http google-health \
  https://health.example.com/mcp
```

进入 Claude Code 后执行：

```text
/mcp
```

按提示在浏览器完成 OAuth 登录。

如果你不使用 Cloudflare Access，而是启用项目自带 Bearer Token，也可以：

```bash
claude mcp add --transport http google-health \
  https://health.example.com/mcp \
  --header "Authorization: Bearer YOUR_TOKEN"
```

静态 Bearer 方式适合 Claude Code 和 Codex，不适合作为 Claude 网页版自定义连接器的主部署方式。

---

# 没有域名怎么办

## 临时测试：Cloudflare Quick Tunnel

没有域名也可以生成临时公网地址：

```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

Cloudflare 会返回类似地址：

```text
https://random-words.trycloudflare.com
```

MCP URL 就是：

```text
https://random-words.trycloudflare.com/mcp
```

但 Quick Tunnel 只适合测试：

- URL 每次重启都会改变
- 没有稳定性承诺
- 不适合长期连接 Claude
- 不应在无认证状态下暴露真实健康数据

因此，没有域名时建议只使用合成数据测试，或者仅通过 Claude Code + Bearer Token 使用临时地址。要长期接入 Claude 网页版或手机端，建议准备一个稳定域名并启用 OAuth 保护。

Cloudflare 官方说明：<https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/>

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
uv run healthctl sync --days 7
```

每天自动同步可以使用 cron：

```bash
crontab -e
```

示例：每天早上 06:15 同步最近 7 天，重复数据会按 ID 更新而不是无限追加。

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

## Claude 提示无法连接 MCP

检查：

- URL 是否以 `/mcp` 结尾
- `health.example.com/healthz` 是否能访问
- Cloudflare Access 是否启用了 Managed OAuth
- Access Policy 是否允许当前登录邮箱
- Anthropic 云端是否能访问该公网地址

## Google 显示 `redirect_uri_mismatch`

Google Cloud 中登记的 URI 必须和 `.env` 完全一致，包括：

- `https`
- 域名
- 路径
- 是否有结尾斜杠

正确示例：

```text
https://health.example.com/oauth/google-health/callback
```

## Google Health 返回 403

常见原因：

- Google Health API 未启用
- OAuth 测试用户未添加
- 当前 Google 账号没有所需权限
- 账号或项目尚未获得对应 API 能力
- 授权时没有同意全部必要的只读范围

## 同一天出现多个步数来源

手机、手表和 Fitbit 可能同时产生步数。可在 `.env` 设置：

```dotenv
PREFERRED_STEP_SOURCE=你的首选来源名称
```

服务会保留来源信息并在统计时避免简单叠加重叠步数。

## 这是医疗诊断工具吗

不是。本项目只提供数据、统计、趋势和数据质量信息。Claude 的解释不能替代医生诊断；单日异常也不应被当成长期趋势。

---

# 安全原则

- MCP 工具全部只读
- Google OAuth 只申请只读健康权限
- 服务默认应只监听 `127.0.0.1`
- 真实数据必须置于 OAuth、VPN 或其他可靠认证之后
- 不要公开 `.env`、OAuth Client Secret、数据库或 Token 文件
- 不要把健康数据、日志、截图和备份提交到 GitHub
- 仅连接你自己部署并信任的 MCP 服务

## License

MIT License，详见 [LICENSE](LICENSE)。
