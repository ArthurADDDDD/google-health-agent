"""Public, secret-safe application errors."""


class HealthAgentError(Exception):
    """Base error safe to translate at API boundaries."""


class ProviderUnavailable(HealthAgentError):
    pass


class AuthenticationRequired(HealthAgentError):
    pass


class PermissionDenied(HealthAgentError):
    pass


class RateLimited(HealthAgentError):
    pass


class InvalidDateRange(HealthAgentError):
    pass


class DataUnavailable(HealthAgentError):
    pass


class InsufficientData(HealthAgentError):
    pass


class DatabaseUnavailable(HealthAgentError):
    pass


class ConfigurationError(HealthAgentError):
    pass
