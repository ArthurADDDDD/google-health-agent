from abc import ABC, abstractmethod
from datetime import date

from google_health_agent.domain import HealthDataPoint


class HealthProvider(ABC):
    name: str

    @abstractmethod
    async def fetch(self, start_date: date, end_date: date) -> list[HealthDataPoint]:
        """Normalize provider data into domain data points."""
