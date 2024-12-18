"""Slightly more typed overload for hass"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from typing import Any, Optional, NewType, Callable
import datetime

import appdaemon.plugins.hass.hassapi as hass  # pyright: ignore[reportMissingTypeStubs]

EntityId = NewType("EntityId", str)


def make_typed_entity_id(prefix: str) -> Callable[[str], EntityId]:
    def inner(s: str):
        if "." in s:
            raise ValueError("Argument contains a prefix.")
        return EntityId(f"{prefix}.{s}")

    return inner


# Vaguely checked alternatives to `EntityId("input_boolean.foo")`.
InputBoolean = make_typed_entity_id("input_boolean")
Switch = make_typed_entity_id("switch")
Sensor = make_typed_entity_id("sensor")
Group = make_typed_entity_id("group")
BinarySensor = make_typed_entity_id("binary_sensor")
MediaPlayer = make_typed_entity_id("media_player")
TTS = make_typed_entity_id("tts")
Scene = make_typed_entity_id("Scene")


# https://appdaemon.readthedocs.io/en/latest/APPGUIDE.html#state-callbacks
StateCallback = Callable[[EntityId, str, Optional[str], str, dict[str, Any]], None]
# https://appdaemon.readthedocs.io/en/latest/APPGUIDE.html#about-event-callbacks
# Args are event name, event arguments, user-provided arguments at the callsite.
EventCallback = Callable[[str, dict[str, Any], dict[str, Any]], None]
# https://appdaemon.readthedocs.io/en/latest/APPGUIDE.html#about-schedule-callbacks
SchedulerCallback = Callable[[dict[str, Any]], None]


class Hass(hass.Hass):
    """Limited but usefully-typed overrides."""

    def __init__(self, *args: Any, **kwargs: Any):
        self.args: dict[str, str]
        super().__init__(*args, **kwargs)

    def get_state(
        self,
        entity_id: EntityId,
        attribute: Optional[str] = None,
        default: Optional[str] = None,
    ) -> str:
        return super().get_state(entity_id, attribute, default)

    def listen_state(
        self,
        callback: StateCallback,
        entity_id: EntityId,
        new: Optional[str] = None,
        duration: Optional[datetime.timedelta] = None,
    ):
        # The appdaemon API does things like "if duration in kwargs" without None-checking...
        kwargs = {}
        if new is not None:
            kwargs["new"] = new
        if duration is not None:
            kwargs["duration"] = duration.seconds

        super().listen_state(
            callback=callback,
            entity_id=str(entity_id),
            **kwargs,  # type: ignore
        )

    def listen_event(
        self,
        callback: EventCallback,
        event: str,
    ):
        super().listen_event(callback=callback, event=event)

    def call_service(
        self,
        service: str,
        entity_id: Optional[EntityId] = None,
        data: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ):
        if entity_id is not None:
            kwargs["entity_id"] = str(entity_id)
        if data is not None:
            kwargs["data"] = data
        super().call_service(service=service, **kwargs)

    def log(self, message: str, level: str):
        super().log(message, level=level)

    def info_log(self, message: str):
        super().log(message, level="INFO")

    def warning_log(self, message: str):
        super().log(message, level="WARNING")

    def error_log(self, message: str):
        super().log(message, level="ERROR")

    def tts_speak(self, message: str, media_player: EntityId):
        self.info_log(f"speaking: '{message}'")
        self.call_service(
            service="tts/speak",
            entity_id=TTS("piper"),
            cache=False,
            media_player_entity_id=str(media_player),
            message=message,
        )

    def turn_on(self, entity_id: EntityId, **kwargs: Any):
        self.call_service(
            service="homeassistant/turn_on", entity_id=entity_id, **kwargs
        )
    
    def run_in(self, callback: SchedulerCallback, after_seconds: float) -> str:
        return super().run_in(callback=callback, delay=after_seconds)
