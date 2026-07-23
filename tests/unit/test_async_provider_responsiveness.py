#!/usr/bin/env python3
"""Regression tests for synchronous provider work in async entry points."""

import asyncio
import configparser
import threading
from typing import Any, Awaitable, Callable, TypeVar
from unittest.mock import Mock

import pytest

from modules.commands.airplanes_command import AirplanesCommand
from modules.service_plugins import weather_service as weather_module
from modules.service_plugins.weather_service import WeatherService

_T = TypeVar("_T")


class _HeartbeatGate:
    """A synchronous provider waits until an asyncio heartbeat can run."""

    def __init__(self) -> None:
        self.provider_started = threading.Event()
        self.heartbeat_ran = threading.Event()
        self.provider_saw_heartbeat = False

    def block_until_heartbeat(self) -> None:
        self.provider_started.set()
        self.provider_saw_heartbeat = self.heartbeat_ran.wait(timeout=1)


async def _run_with_heartbeat(
    operation: Callable[[], Awaitable[_T]], gate: _HeartbeatGate
) -> _T:
    async def heartbeat() -> None:
        while not gate.provider_started.is_set():
            await asyncio.sleep(0)
        gate.heartbeat_ran.set()

    heartbeat_task = asyncio.create_task(heartbeat())
    await asyncio.sleep(0)
    result = await asyncio.wait_for(operation(), timeout=2)
    await heartbeat_task

    assert gate.provider_saw_heartbeat, "provider work blocked the asyncio event loop"
    return result


def _weather_service(mock_logger: Mock) -> WeatherService:
    config = configparser.ConfigParser()
    config.add_section("Weather")
    config.add_section("Weather_Service")
    config.set("Weather_Service", "my_position_lat", "47.6062")
    config.set("Weather_Service", "my_position_lon", "-122.3321")

    bot = Mock()
    bot.logger = mock_logger
    bot.config = config
    bot.db_manager = Mock()
    bot.command_manager = Mock()
    return WeatherService(bot)


@pytest.mark.asyncio
async def test_airplanes_provider_fetch_keeps_event_loop_responsive() -> None:
    command = object.__new__(AirplanesCommand)
    gate = _HeartbeatGate()
    expected = {"ac": []}

    def slow_fetch(_lat: float, _lon: float, _radius: float) -> dict[str, Any]:
        gate.block_until_heartbeat()
        return expected

    command._fetch_aircraft_data = slow_fetch  # type: ignore[method-assign]

    result = await _run_with_heartbeat(
        lambda: command._fetch_aircraft_data_async(47.6, -122.3, 25),
        gate,
    )

    assert result is expected


@pytest.mark.asyncio
async def test_airplanes_provider_fetch_await_is_cancellable() -> None:
    command = object.__new__(AirplanesCommand)
    provider_started = threading.Event()
    release_provider = threading.Event()

    def slow_fetch(_lat: float, _lon: float, _radius: float) -> dict[str, Any]:
        provider_started.set()
        release_provider.wait(timeout=1)
        return {"ac": []}

    command._fetch_aircraft_data = slow_fetch  # type: ignore[method-assign]
    task = asyncio.create_task(command._fetch_aircraft_data_async(47.6, -122.3, 25))

    try:
        assert await asyncio.to_thread(provider_started.wait, 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        release_provider.set()


@pytest.mark.asyncio
async def test_weather_forecast_fetch_keeps_event_loop_responsive(mock_logger: Mock) -> None:
    service = _weather_service(mock_logger)
    service._cached_location_name = "Seattle, WA"
    gate = _HeartbeatGate()
    response = Mock()
    response.ok = True
    response.json.return_value = {
        "current": {
            "temperature_2m": 70,
            "weather_code": 1,
            "wind_speed_10m": 5,
            "wind_direction_10m": 180,
        },
        "daily": {
            "time": ["2026-07-16", "2026-07-17"],
            "weather_code": [1, 2],
            "temperature_2m_max": [72, 73],
            "temperature_2m_min": [58, 59],
        },
    }

    def slow_get(*_args: Any, **_kwargs: Any) -> Mock:
        gate.block_until_heartbeat()
        return response

    service.api_session = Mock()
    service.api_session.get = slow_get

    result = await _run_with_heartbeat(service._get_weather_forecast, gate)

    assert result.startswith("Seattle, WA:")
    response.json.assert_called_once_with()


@pytest.mark.asyncio
async def test_weather_alert_fetch_keeps_event_loop_responsive(mock_logger: Mock) -> None:
    service = _weather_service(mock_logger)
    gate = _HeartbeatGate()
    response = Mock(ok=True, status_code=200, text="<feed />")

    def slow_get(*_args: Any, **_kwargs: Any) -> Mock:
        gate.block_until_heartbeat()
        return response

    service.api_session = Mock()
    service.api_session.get = slow_get

    await _run_with_heartbeat(service._check_weather_alerts, gate)

    assert service._nws_alerts_available is True


@pytest.mark.asyncio
async def test_weather_alert_xml_parse_keeps_event_loop_responsive(
    mock_logger: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _weather_service(mock_logger)
    response = Mock(ok=True, status_code=200, text="<feed />")
    service.api_session = Mock()
    service.api_session.get.return_value = response
    gate = _HeartbeatGate()
    real_parse = weather_module.xml.dom.minidom.parseString

    def slow_parse(value: str) -> Any:
        gate.block_until_heartbeat()
        return real_parse(value)

    monkeypatch.setattr(weather_module.xml.dom.minidom, "parseString", slow_parse)

    await _run_with_heartbeat(service._check_weather_alerts, gate)

    assert service._nws_alerts_available is True


@pytest.mark.asyncio
async def test_weather_reverse_geocode_keeps_event_loop_responsive(
    mock_logger: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _weather_service(mock_logger)
    gate = _HeartbeatGate()

    def slow_reverse(*_args: Any, **_kwargs: Any) -> dict[str, str]:
        gate.block_until_heartbeat()
        return {"city": "Seattle"}

    monkeypatch.setattr(
        "modules.utils.rate_limited_nominatim_reverse_sync",
        slow_reverse,
    )

    result = await _run_with_heartbeat(
        lambda: service._geocode_location(47.6, -122.3),
        gate,
    )

    assert result == "Seattle"
