"""Application-wide service registration and resolution."""

from __future__ import annotations

from typing import Any, TypeVar, cast


class ServiceError(RuntimeError):
    """Base exception for application service failures."""


class ServiceAlreadyRegisteredError(ServiceError):
    """Raised when a service type is registered more than once."""


class ServiceNotRegisteredError(ServiceError):
    """Raised when a required service has not been registered."""


ServiceType = TypeVar("ServiceType")


class ApplicationServices:
    """Typed registry for shared application service instances.

    Services are registered by their public type rather than by string keys.
    This keeps dependencies explicit, supports static type checking, and makes
    test doubles straightforward to install.
    """

    def __init__(self) -> None:
        self._services: dict[type[Any], Any] = {}

    def register(
        self,
        service_type: type[ServiceType],
        instance: ServiceType,
        *,
        replace: bool = False,
    ) -> ServiceType:
        """Register an instance for a service type and return the instance."""
        if service_type in self._services and not replace:
            raise ServiceAlreadyRegisteredError(
                f"Service already registered: {service_type.__qualname__}"
            )
        if not isinstance(instance, service_type):
            raise TypeError(f"Service instance must be an instance of {service_type.__qualname__}")
        self._services[service_type] = instance
        return instance

    def get(self, service_type: type[ServiceType]) -> ServiceType | None:
        """Return a registered service, or ``None`` when it is unavailable."""
        instance = self._services.get(service_type)
        if instance is None:
            return None
        return cast(ServiceType, instance)

    def require(self, service_type: type[ServiceType]) -> ServiceType:
        """Return a registered service or raise a descriptive exception."""
        instance = self.get(service_type)
        if instance is None:
            raise ServiceNotRegisteredError(
                f"Required service is not registered: {service_type.__qualname__}"
            )
        return instance

    def contains(self, service_type: type[Any]) -> bool:
        """Return whether a service type is currently registered."""
        return service_type in self._services

    def unregister(self, service_type: type[ServiceType]) -> ServiceType | None:
        """Remove and return a service, or ``None`` if it was not registered."""
        instance = self._services.pop(service_type, None)
        if instance is None:
            return None
        return cast(ServiceType, instance)

    def clear(self) -> None:
        """Remove all registered services."""
        self._services.clear()

    def __len__(self) -> int:
        """Return the number of registered services."""
        return len(self._services)
