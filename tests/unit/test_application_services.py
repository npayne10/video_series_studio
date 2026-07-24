"""Tests for the application service registry."""

import pytest

from vscs.infrastructure.services import (
    ApplicationServices,
    ServiceAlreadyRegisteredError,
    ServiceNotRegisteredError,
)


class ExampleService:
    """Small service used to verify typed registration."""


class OtherService:
    """Second service used to verify isolation and replacement."""


def test_register_and_require_service() -> None:
    """A registered instance can be resolved by its public type."""
    services = ApplicationServices()
    instance = ExampleService()

    returned = services.register(ExampleService, instance)

    assert returned is instance
    assert services.require(ExampleService) is instance
    assert services.get(ExampleService) is instance
    assert services.contains(ExampleService)
    assert len(services) == 1


def test_missing_optional_service_returns_none() -> None:
    """Optional lookup does not raise for an unavailable service."""
    services = ApplicationServices()

    assert services.get(ExampleService) is None
    assert not services.contains(ExampleService)


def test_missing_required_service_raises() -> None:
    """Required lookup reports the exact missing service type."""
    services = ApplicationServices()

    with pytest.raises(ServiceNotRegisteredError, match="ExampleService"):
        services.require(ExampleService)


def test_duplicate_registration_is_rejected() -> None:
    """Duplicate services require an explicit replacement decision."""
    services = ApplicationServices()
    services.register(ExampleService, ExampleService())

    with pytest.raises(ServiceAlreadyRegisteredError, match="ExampleService"):
        services.register(ExampleService, ExampleService())


def test_service_can_be_replaced_explicitly() -> None:
    """Tests and controlled reconfiguration can replace a service."""
    services = ApplicationServices()
    original = ExampleService()
    replacement = ExampleService()
    services.register(ExampleService, original)

    services.register(ExampleService, replacement, replace=True)

    assert services.require(ExampleService) is replacement


def test_registration_rejects_wrong_instance_type() -> None:
    """The runtime guard prevents a service being registered under the wrong key."""
    services = ApplicationServices()

    with pytest.raises(TypeError, match="ExampleService"):
        services.register(ExampleService, OtherService())  # type: ignore[arg-type]


def test_unregister_and_clear_services() -> None:
    """Services can be removed individually or cleared during shutdown."""
    services = ApplicationServices()
    example = services.register(ExampleService, ExampleService())
    services.register(OtherService, OtherService())

    assert services.unregister(ExampleService) is example
    assert services.unregister(ExampleService) is None
    assert len(services) == 1

    services.clear()

    assert len(services) == 0
