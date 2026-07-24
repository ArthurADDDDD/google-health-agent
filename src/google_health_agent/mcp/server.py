from collections.abc import Callable
from datetime import date, timedelta
from secrets import compare_digest
from typing import Any

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from sqlalchemy.engine import make_url
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from google_health_agent.config import Settings
from google_health_agent.errors import HealthAgentError
from google_health_agent.observability import SafeRequestLoggingMiddleware, configure_safe_logging
from google_health_agent.service import (
    ACTIVITY_METRICS,
    RECOVERY_METRICS,
    SLEEP_METRICS,
    HealthService,
)
from google_health_agent.storage import HealthRepository

SERVER_INSTRUCTIONS = """Google Health Agent exposes personal health and fitness data
for AI agent analysis.

Important reasoning rules:
1. Prioritize the user's own historical baseline.
2. Do not diagnose diseases.
3. A single unusual day is not a trend.
4. Check data quality before drawing conclusions.
5. Treat sleep, HRV, resting heart rate, respiratory rate, oxygen saturation,
   temperature and activity as related but distinct signals.
6. Clearly distinguish observed facts, statistical comparisons, hypotheses,
   and recommendations.
7. Reduce confidence when data is incomplete.
8. Prefer aggregated data unless detailed history is necessary.
9. Never infer that missing data means zero.
10. Request deeper metric history when the overview is insufficient.
"""

READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


def create_mcp(service: HealthService, settings: Settings) -> FastMCP[None]:
    transport_security = None
    if settings.allowed_host_patterns or settings.allowed_origin_patterns:
        transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=settings.allowed_host_patterns,
            allowed_origins=settings.allowed_origin_patterns,
        )
    mcp = FastMCP(
        "google-health-agent",
        instructions=SERVER_INSTRUCTIONS,
        host=settings.mcp_host,
        port=settings.mcp_port,
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        transport_security=transport_security,
    )

    def tool(
        *,
        name: str,
        description: str,
    ) -> Callable[[Callable[..., dict[str, Any]]], Callable[..., dict[str, Any]]]:
        return mcp.tool(
            name=name,
            description=description,
            annotations=READ_ONLY,
            structured_output=True,
        )

    @tool(
        name="get_health_overview",
        description="Aggregated sleep, recovery, activity, trend, source, and quality facts.",
    )
    def get_health_overview(days: int = 30, end_date: date | None = None) -> dict[str, Any]:
        return service.overview(days, end_date)

    @tool(name="get_sleep", description="Sleep timing, stages, daily history, and summaries.")
    def get_sleep(
        days: int = 30,
        end_date: date | None = None,
        include_stages: bool = True,
    ) -> dict[str, Any]:
        metrics = SLEEP_METRICS if include_stages else SLEEP_METRICS[:3]
        return service.category(metrics, days, end_date)

    @tool(name="get_recovery", description="Recovery metric facts, statistics, and trends.")
    def get_recovery(days: int = 30, end_date: date | None = None) -> dict[str, Any]:
        return service.category(RECOVERY_METRICS, days, end_date)

    @tool(name="get_activity", description="Activity facts with deduplicated step sources.")
    def get_activity(days: int = 30, end_date: date | None = None) -> dict[str, Any]:
        return service.category(ACTIVITY_METRICS, days, end_date)

    @tool(name="get_metric", description="Bounded daily history or summary for one metric.")
    def get_metric(
        metric: str,
        start_date: date,
        end_date: date,
        granularity: str = "daily",
    ) -> dict[str, Any]:
        return service.metric(metric, start_date, end_date, granularity)

    @tool(name="compare_periods", description="Mathematical comparison of two explicit periods.")
    def compare_periods_tool(
        metric: str,
        period_a_start: date,
        period_a_end: date,
        period_b_start: date,
        period_b_end: date,
    ) -> dict[str, Any]:
        return service.compare(
            metric,
            period_a_start,
            period_a_end,
            period_b_start,
            period_b_end,
        )

    @tool(name="get_data_quality", description="Completeness, source, timezone, and overlap facts.")
    def get_data_quality(days: int = 30, end_date: date | None = None) -> dict[str, Any]:
        return service.quality(days, end_date)

    @tool(
        name="get_daily_brief_context",
        description="Compact facts for an agent-generated daily brief; contains no conclusion.",
    )
    def get_daily_brief_context(date: date, lookback_days: int = 30) -> dict[str, Any]:
        overview = service.overview(lookback_days, date)
        overview["brief_date"] = date.isoformat()
        overview["last_night_sleep"] = service.category(SLEEP_METRICS, 1, date)
        overview["yesterday_activity"] = service.category(
            ACTIVITY_METRICS, 1, date - timedelta(days=1)
        )
        return overview

    return mcp


class BearerAuthMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.enabled = settings.mcp_auth_enabled
        self.tokens = tuple(f"Bearer {token}".encode() for token in settings.mcp_token_map.values())

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.enabled and scope["type"] == "http" and scope["path"].startswith("/mcp"):
            headers = dict(scope.get("headers", []))
            supplied = headers.get(b"authorization", b"")
            if not any(compare_digest(supplied, expected) for expected in self.tokens):
                response = JSONResponse({"error": "Unauthorized"}, status_code=401)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def create_app(settings: Settings, repository: HealthRepository | None = None) -> Starlette:
    repository = repository or HealthRepository(settings.database_url)
    repository.initialize()
    service = HealthService(
        repository,
        data_label=(
            "SYNTHETIC DATA" if settings.health_provider == "synthetic" else "PRIVATE DATA"
        ),
        preferred_step_source=settings.preferred_step_source,
    )
    mcp = create_mcp(service, settings)
    mcp_app = mcp.streamable_http_app()

    async def healthz(_: Request) -> Response:
        return JSONResponse({"status": "ok", "service": "google-health-agent"})

    async def readyz(_: Request) -> Response:
        if not repository.ready():
            return JSONResponse({"status": "not ready", "database": "unavailable"}, status_code=503)
        return JSONResponse({"status": "ready", "database": "ok"})

    async def safe_error(_: Request, exc: Exception) -> Response:
        return JSONResponse({"error": str(exc)}, status_code=400)

    oauth_routes: list[Route] = []
    if settings.health_provider == "google":
        from pathlib import Path

        from google_health_agent.providers.google_health import (
            EncryptedFileTokenStore,
            GoogleOAuthClient,
            OAuthStateStore,
        )

        if settings.google_token_encryption_key is None:
            raise HealthAgentError(
                "GOOGLE_TOKEN_ENCRYPTION_KEY is required for the Google provider."
            )
        oauth = GoogleOAuthClient(settings)
        token_store = EncryptedFileTokenStore(
            Path("credentials/google-health-token.enc"),
            settings.google_token_encryption_key,
        )
        states = OAuthStateStore()

        async def oauth_login(_: Request) -> Response:
            return RedirectResponse(oauth.authorization_url(states.issue()))

        async def oauth_callback(request: Request) -> Response:
            code = request.query_params.get("code")
            state = request.query_params.get("state")
            if not code or not state:
                return JSONResponse({"error": "Missing OAuth code or state."}, status_code=400)
            states.consume(state)
            tokens = await oauth.exchange_code(code)
            token_store.save(tokens)
            return JSONResponse(
                {
                    "status": "authorized",
                    "message": "Google Health authorization stored securely.",
                }
            )

        oauth_routes = [
            Route("/oauth/google-health/login", oauth_login),
            Route("/oauth/google-health/callback", oauth_callback),
        ]

    app = Starlette(
        routes=[
            Route("/healthz", healthz),
            Route("/readyz", readyz),
            *oauth_routes,
            Mount("/", app=mcp_app),
        ],
        lifespan=mcp_app.router.lifespan_context,
        exception_handlers={HealthAgentError: safe_error},
    )
    app.add_middleware(BearerAuthMiddleware, settings=settings)
    app.add_middleware(SafeRequestLoggingMiddleware)
    return app


def run_server(settings: Settings) -> None:
    secret_values = list(settings.mcp_token_map.values())
    for value in (
        settings.google_client_id,
        settings.google_client_secret,
        settings.google_token_encryption_key,
        settings.smtp_password,
    ):
        if value:
            secret_values.append(value.get_secret_value())
    database_password = make_url(settings.database_url).password
    if database_password:
        secret_values.append(database_password)
    configure_safe_logging(secret_values)
    uvicorn.run(
        create_app(settings),
        host=settings.mcp_host,
        port=settings.mcp_port,
        log_config=None,
    )
