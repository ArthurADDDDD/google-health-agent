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
