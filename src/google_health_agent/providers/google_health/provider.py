import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import httpx

from google_health_agent.domain import DataSource, HealthDataPoint
from google_health_agent.domain.models import RecordingMethod
from google_health_agent.errors import (
    AuthenticationRequired,
    DataUnavailable,
    PermissionDenied,
    ProviderUnavailable,
    RateLimited,
)
from google_health_agent.providers.base import HealthProvider
from google_health_agent.providers.google_health.oauth import (
    GoogleOAuthClient,
    TokenSet,
    TokenStore,
)

GOOGLE_HEALTH_BASE_URL = "https://health.googleapis.com/v4"

DATA_TYPES: dict[str, tuple[str, str, str, str]] = {
    "steps": ("steps", "steps", "count", "count"),
    "sleep": ("sleep", "sleep", "summary.minutesAsleep", "min"),
    "active-zone-minutes": (
        "activeZoneMinutes",
        "active_zone_minutes",
        "activeZoneMinutes",
        "min",
    ),
    "active-minutes": (
        "activeMinutes",
        "active_minutes",
        "activeMinutesByActivityLevel",
        "min",
    ),
    "sedentary-period": (
        "sedentaryPeriod",
        "sedentary_period",
        "intervalDurationMinutes",
        "min",
    ),
    "exercise": ("exercise", "exercise", "intervalDurationMinutes", "min"),
    "daily-heart-rate-variability": (
        "dailyHeartRateVariability",
        "daily_heart_rate_variability",
        "averageHeartRateVariabilityMilliseconds",
        "ms",
    ),
    "daily-resting-heart-rate": (
        "dailyRestingHeartRate",
        "daily_resting_heart_rate",
        "beatsPerMinute",
        "bpm",
    ),
    "daily-oxygen-saturation": (
        "dailyOxygenSaturation",
        "daily_oxygen_saturation",
        "averagePercentage",
        "percent",
    ),
    "respiratory-rate-sleep-summary": (
        "respiratoryRateSleepSummary",
        "respiratory_rate_sleep_summary",
        "fullSleepStats.breathsPerMinute",
        "breaths/min",
    ),
    "daily-sleep-temperature-derivations": (
        "dailySleepTemperatureDerivations",
        "daily_sleep_temperature_derivations",
        "nightlyTemperatureCelsius",
        "celsius",
    ),
    "weight": ("weight", "weight", "weightGrams", "kg"),
}
DOMAIN_METRICS = {
    "steps": "steps",
    "sleep": "sleep_minutes",
    "active-zone-minutes": "active_zone_minutes",
    "active-minutes": "active_minutes",
    "sedentary-period": "sedentary_minutes",
    "exercise": "exercise_minutes",
    "daily-heart-rate-variability": "hrv",
    "daily-resting-heart-rate": "resting_heart_rate",
    "daily-oxygen-saturation": "oxygen_saturation",
    "respiratory-rate-sleep-summary": "respiratory_rate",
    "daily-sleep-temperature-derivations": "temperature_deviation",
    "weight": "weight",
}


class GoogleHealthProvider(HealthProvider):
    name = "google"

    def __init__(
        self,
        token_store: TokenStore,
        oauth: GoogleOAuthClient,
        client: httpx.AsyncClient | None = None,
        data_types: tuple[str, ...] = tuple(DATA_TYPES),
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.token_store = token_store
        self.oauth = oauth
        self.client = client or httpx.AsyncClient(timeout=30)
        self.data_types = data_types
        self.sleep = sleep

    async def fetch(self, start_date: date, end_date: date) -> list[HealthDataPoint]:
        token = await self._valid_token()
        points: list[HealthDataPoint] = []
        for data_type in self.data_types:
            for window_start, window_end in self._windows(data_type, start_date, end_date):
                points.extend(await self._fetch_type(data_type, window_start, window_end, token))
        return points

    async def _valid_token(self) -> TokenSet:
        token = self.token_store.load()
        if token is None:
            raise AuthenticationRequired(
                "Google Health authorization is required; open the configured OAuth login route."
            )
        if token.expired():
            if token.refresh_token is None:
                raise AuthenticationRequired("Google OAuth refresh token is unavailable.")
            token = await self.oauth.refresh(token.refresh_token)
            self.token_store.save(token)
        return token

    async def _fetch_type(
        self, data_type: str, start_date: date, end_date: date, token: TokenSet
    ) -> list[HealthDataPoint]:
        if data_type not in DATA_TYPES:
            raise DataUnavailable(f"Unsupported Google Health data type: {data_type}")
        page_token: str | None = None
        points: list[HealthDataPoint] = []
        refreshed = False
        while True:
            params = {
                "pageSize": "25" if data_type in {"exercise", "sleep"} else "10000",
                "filter": self._filter(data_type, start_date, end_date),
            }
            if page_token:
                params["pageToken"] = page_token
            response = await self._request(data_type, params, token)
            if response.status_code == 401 and not refreshed and token.refresh_token:
                token = await self.oauth.refresh(token.refresh_token)
                self.token_store.save(token)
                refreshed = True
                continue
            self._raise_status(response)
            try:
                payload = response.json()
                raw_points = payload.get("dataPoints", [])
                if not isinstance(raw_points, list):
                    raise TypeError
                points.extend(self._normalize(data_type, raw) for raw in raw_points)
                page_token = payload.get("nextPageToken")
                if page_token is not None and not isinstance(page_token, str):
                    raise TypeError
            except (TypeError, ValueError, KeyError) as exc:
                raise DataUnavailable("Google Health returned a malformed data response.") from exc
            if not page_token:
                break
        return points

    async def _request(
        self, data_type: str, params: dict[str, str], token: TokenSet
    ) -> httpx.Response:
        url = f"{GOOGLE_HEALTH_BASE_URL}/users/me/dataTypes/{data_type}/dataPoints"
        for attempt in range(3):
            try:
                response = await self.client.get(
                    url,
                    params=params,
                    headers={
                        "Authorization": f"Bearer {token.access_token.get_secret_value()}",
                        "Accept": "application/json",
                    },
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt == 2:
                    raise ProviderUnavailable(
                        "Google Health request failed after retries."
                    ) from exc
                await self.sleep(0.1 * 2**attempt)
                continue
            if response.status_code not in {429, 500, 502, 503, 504} or attempt == 2:
                return response
            await self.sleep(0.1 * 2**attempt)
        raise ProviderUnavailable("Google Health request failed after retries.")

    @staticmethod
    def _raise_status(response: httpx.Response) -> None:
        if response.status_code == 401:
            raise AuthenticationRequired("Google Health access token was rejected.")
        if response.status_code == 403:
            raise PermissionDenied("Google Health readonly permission was denied.")
        if response.status_code == 404:
            raise DataUnavailable("Google Health data type or resource was not found.")
        if response.status_code == 429:
            raise RateLimited("Google Health rate limit persisted after retries.")
        if response.status_code >= 500:
            raise ProviderUnavailable("Google Health service failed after retries.")
        if response.status_code >= 400:
            raise ProviderUnavailable(f"Google Health request failed ({response.status_code}).")

    @staticmethod
    def _filter(data_type: str, start_date: date, end_date: date) -> str:
        exclusive_end = end_date + timedelta(days=1)
        filter_name = DATA_TYPES[data_type][1]
        field = f"{filter_name}.date"
        if data_type in {
            "steps",
            "active-zone-minutes",
            "active-minutes",
            "sedentary-period",
            "exercise",
        }:
            field = f"{filter_name}.interval.civil_start_time"
        elif data_type == "sleep":
            field = "sleep.interval.civil_end_time"
        elif data_type in {"weight", "respiratory-rate-sleep-summary"}:
            field = f"{filter_name}.sample_time.civil_time"
        return f'{field} >= "{start_date.isoformat()}" AND {field} < "{exclusive_end.isoformat()}"'

    @staticmethod
    def _windows(data_type: str, start_date: date, end_date: date) -> list[tuple[date, date]]:
        maximum_days = 14 if data_type == "active-minutes" else 90
        windows: list[tuple[date, date]] = []
        current = start_date
        while current <= end_date:
            window_end = min(end_date, current + timedelta(days=maximum_days - 1))
            windows.append((current, window_end))
            current = window_end + timedelta(days=1)
        return windows

    @staticmethod
    def _normalize(data_type: str, raw: dict[str, Any]) -> HealthDataPoint:
        field, _, value_field, unit = DATA_TYPES[data_type]
        body = raw[field]
        start_time, end_time, civil_date, offset = _observation_time(body)
        value = _metric_value(data_type, body, value_field, start_time, end_time)
        source_raw = raw.get("dataSource", {})
        device = source_raw.get("device") or {}
        application = source_raw.get("application") or {}
        source_name = (
            device.get("displayName")
            or application.get("displayName")
            or source_raw.get("platform")
            or "google-health"
        )
        recording = str(source_raw.get("recordingMethod", "PASSIVELY_MEASURED")).lower()
        method = {
            "actively_measured": RecordingMethod.ACTIVE,
            "manual_entry": RecordingMethod.MANUAL,
            "derived": RecordingMethod.DERIVED,
        }.get(recording, RecordingMethod.PASSIVE)
        external_id = (
            raw.get("name")
            or hashlib.sha256(
                f"{data_type}:{start_time.isoformat()}:{source_name}:{value}".encode()
            ).hexdigest()
        )
        return HealthDataPoint(
            external_id=external_id,
            metric=DOMAIN_METRICS[data_type],
            value=value,
            unit=unit,
            start_time=start_time,
            end_time=end_time,
            utc_offset_minutes=offset,
            civil_date=civil_date,
            source=DataSource(
                platform=str(source_raw.get("platform", "GOOGLE_HEALTH")),
                source=str(source_name),
                recording_method=method,
                device=device.get("displayName"),
            ),
            ingested_at=datetime.now(UTC),
            synthetic=False,
            tags={"provider_data_type": data_type},
        )


def _observation_time(body: dict[str, Any]) -> tuple[datetime, datetime, date, int]:
    interval = body.get("interval")
    sample = body.get("sampleTime")
    if isinstance(interval, dict):
        start = _parse_datetime(interval["startTime"])
        end = _parse_datetime(interval["endTime"])
        civil = _civil_date(interval.get("civilStartTime", {}).get("date")) or start.date()
        offset = _duration_minutes(interval.get("startUtcOffset", "0s"))
        return start, end, civil, offset
    if isinstance(sample, dict):
        physical = sample.get("physicalTime")
        if not isinstance(physical, str):
            raise ValueError("sample observation has no physical time")
        start = _parse_datetime(physical)
        civil_value = _civil_date(sample.get("civilTime", {}).get("date")) or start.date()
        offset = _duration_minutes(sample.get("utcOffset", "0s"))
        return start, start, civil_value, offset
    daily_civil = _civil_date(body.get("date"))
    if daily_civil is None:
        raise ValueError("observation has no supported time")
    start = datetime.combine(daily_civil, time(), tzinfo=UTC)
    return start, start + timedelta(days=1), daily_civil, 0


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _civil_date(value: dict[str, Any] | None) -> date | None:
    if not value:
        return None
    return date(int(value["year"]), int(value["month"]), int(value["day"]))


def _duration_minutes(value: str) -> int:
    return round(float(value.removesuffix("s")) / 60)


def _metric_value(
    data_type: str,
    body: dict[str, Any],
    value_field: str,
    start_time: datetime,
    end_time: datetime,
) -> float:
    if value_field == "intervalDurationMinutes":
        return (end_time - start_time).total_seconds() / 60
    if data_type == "active-minutes":
        rows = body.get("activeMinutesByActivityLevel")
        if not isinstance(rows, list):
            raise ValueError("active minutes payload is malformed")
        return sum(float(row["activeMinutes"]) for row in rows)
    value: Any = body
    for segment in value_field.split("."):
        value = value[segment]
    numeric = float(value)
    if data_type == "weight":
        return numeric / 1000
    if data_type == "daily-sleep-temperature-derivations":
        baseline = body.get("baselineTemperatureCelsius")
        return numeric - float(baseline) if baseline is not None else numeric
    return numeric
