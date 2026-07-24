from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
import respx

from google_health_agent.config import Settings
from google_health_agent.errors import (
    AuthenticationRequired,
    DataUnavailable,
    PermissionDenied,
    ProviderUnavailable,
    RateLimited,
)
from google_health_agent.providers.google_health import (
    GoogleHealthProvider,
    GoogleOAuthClient,
    TokenSet,
    TokenStore,
)

DATA_URL = "https://health.googleapis.com/v4/users/me/dataTypes/steps/dataPoints"
SLEEP_URL = "https://health.googleapis.com/v4/users/me/dataTypes/sleep/dataPoints"
ACTIVE_MINUTES_URL = "https://health.googleapis.com/v4/users/me/dataTypes/active-minutes/dataPoints"
TOKEN_URL = "https://oauth2.googleapis.com/token"


class MemoryTokenStore(TokenStore):
    def __init__(self, token: TokenSet | None) -> None:
        self.token = token

    def load(self) -> TokenSet | None:
        return self.token

    def save(self, tokens: TokenSet) -> None:
        self.token = tokens

    def delete(self) -> None:
        self.token = None


def _token() -> TokenSet:
    return TokenSet(
        access_token="mock-access",
        refresh_token="mock-refresh",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def _oauth(client: httpx.AsyncClient) -> GoogleOAuthClient:
    return GoogleOAuthClient(
        Settings(
            google_client_id="mock-client",
            google_client_secret="mock-secret",
            google_redirect_uri="https://health.example.com/oauth/google-health/callback",
        ),
        client,
    )


def _step(day: int, count: str) -> dict:
    return {
        "dataSource": {
            "recordingMethod": "PASSIVELY_MEASURED",
            "platform": "FITBIT",
            "device": {"displayName": "Mock Watch"},
        },
        "steps": {
            "interval": {
                "startTime": f"2026-01-{day:02d}T00:00:00Z",
                "startUtcOffset": "28800s",
                "endTime": f"2026-01-{day:02d}T23:59:00Z",
                "endUtcOffset": "28800s",
                "civilStartTime": {"date": {"year": 2026, "month": 1, "day": day}},
            },
            "count": count,
        },
    }


@pytest.mark.asyncio
@respx.mock
async def test_pagination_and_normalization() -> None:
    route = respx.get(DATA_URL).mock(
        side_effect=[
            httpx.Response(200, json={"dataPoints": [_step(1, "100")], "nextPageToken": "next"}),
            httpx.Response(200, json={"dataPoints": [_step(2, "200")]}),
        ]
    )
    async with httpx.AsyncClient() as client:
        provider = GoogleHealthProvider(
            MemoryTokenStore(_token()), _oauth(client), client, data_types=("steps",)
        )
        points = await provider.fetch(date(2026, 1, 1), date(2026, 1, 2))
    assert route.call_count == 2
    assert [point.value for point in points] == [100, 200]
    assert points[0].civil_date == date(2026, 1, 1)
    assert points[0].utc_offset_minutes == 480
    assert points[0].synthetic is False


@pytest.mark.asyncio
@respx.mock
async def test_current_page_sizes_filters_and_query_window_limits() -> None:
    sleep_route = respx.get(SLEEP_URL).mock(
        return_value=httpx.Response(200, json={"dataPoints": []})
    )
    active_route = respx.get(ACTIVE_MINUTES_URL).mock(
        return_value=httpx.Response(200, json={"dataPoints": []})
    )
    async with httpx.AsyncClient() as client:
        sleep_provider = GoogleHealthProvider(
            MemoryTokenStore(_token()),
            _oauth(client),
            client,
            data_types=("sleep",),
        )
        await sleep_provider.fetch(date(2026, 1, 1), date(2026, 1, 1))
        active_provider = GoogleHealthProvider(
            MemoryTokenStore(_token()),
            _oauth(client),
            client,
            data_types=("active-minutes",),
        )
        await active_provider.fetch(date(2026, 1, 1), date(2026, 1, 30))

    assert sleep_route.call_count == 1
    assert sleep_route.calls[0].request.url.params["pageSize"] == "25"
    assert (
        sleep_route.calls[0].request.url.params["filter"]
        == 'sleep.interval.civil_end_time >= "2026-01-01" '
        'AND sleep.interval.civil_end_time < "2026-01-02"'
    )
    assert active_route.call_count == 3
    filters = [call.request.url.params["filter"] for call in active_route.calls]
    assert all(item.startswith("active_minutes.interval.civil_start_time") for item in filters)
    assert '"2026-01-01"' in filters[0] and '"2026-01-15"' in filters[0]
    assert '"2026-01-15"' in filters[1] and '"2026-01-29"' in filters[1]
    assert '"2026-01-29"' in filters[2] and '"2026-01-31"' in filters[2]


@pytest.mark.asyncio
@respx.mock
async def test_401_refreshes_once_without_exposing_tokens() -> None:
    data_route = respx.get(DATA_URL).mock(
        side_effect=[
            httpx.Response(401),
            httpx.Response(200, json={"dataPoints": [_step(1, "123")]}),
        ]
    )
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "new-mock-access", "expires_in": 3600},
        )
    )
    store = MemoryTokenStore(_token())
    async with httpx.AsyncClient() as client:
        provider = GoogleHealthProvider(store, _oauth(client), client, data_types=("steps",))
        points = await provider.fetch(date(2026, 1, 1), date(2026, 1, 1))
    assert data_route.call_count == 2
    assert points[0].value == 123
    assert store.token
    assert store.token.access_token.get_secret_value() == "new-mock-access"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "error"),
    [
        (403, PermissionDenied),
        (404, DataUnavailable),
        (429, RateLimited),
        (500, ProviderUnavailable),
    ],
)
async def test_http_errors_are_structured(status, error) -> None:
    async with respx.mock:
        respx.get(DATA_URL).mock(return_value=httpx.Response(status))
        async with httpx.AsyncClient() as client:
            provider = GoogleHealthProvider(
                MemoryTokenStore(_token()),
                _oauth(client),
                client,
                data_types=("steps",),
                sleep=_no_sleep,
            )
            with pytest.raises(error):
                await provider.fetch(date(2026, 1, 1), date(2026, 1, 1))


async def _no_sleep(_: float) -> None:
    return None


@pytest.mark.asyncio
@respx.mock
async def test_timeout_malformed_and_missing_auth() -> None:
    async with httpx.AsyncClient() as client:
        provider = GoogleHealthProvider(
            MemoryTokenStore(None), _oauth(client), client, data_types=("steps",)
        )
        with pytest.raises(AuthenticationRequired):
            await provider.fetch(date(2026, 1, 1), date(2026, 1, 1))

        respx.get(DATA_URL).mock(
            side_effect=httpx.ReadTimeout("mock timeout"),
        )
        provider = GoogleHealthProvider(
            MemoryTokenStore(_token()),
            _oauth(client),
            client,
            data_types=("steps",),
            sleep=_no_sleep,
        )
        with pytest.raises(ProviderUnavailable):
            await provider.fetch(date(2026, 1, 1), date(2026, 1, 1))

        respx.get(DATA_URL).mock(return_value=httpx.Response(200, json={"dataPoints": "bad"}))
        with pytest.raises(DataUnavailable):
            await provider.fetch(date(2026, 1, 1), date(2026, 1, 1))
