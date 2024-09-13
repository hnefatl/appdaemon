"""Slightly more typed overload for hass"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from typing import Any, Optional, NewType, Callable
import datetime

import appdaemon.plugins.hass.hassapi as hass  # pyright: ignore[reportMissingTypeStubs]

EntityId = NewType("EntityId", str)
# https://appdaemon.readthedocs.io/en/latest/APPGUIDE.html#state-callbacks
StateCallback = Callable[[EntityId, str, Optional[str], str, dict[str, Any]], None]
# https://appdaemon.readthedocs.io/en/latest/APPGUIDE.html#about-event-callbacks
# Args are event name, event arguments, user-provided arguments at the callsite.
EventCallback = Callable[[str, dict[str, Any], dict[str, Any]], None]


class Hass(hass.Hass):
    """Limited but usefully-typed overrides."""

    def __init__(self, *args: Any, **kwargs: Any):
        self.args: dict[str, str]
        return super().__init__(*args, **kwargs)

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
        **kwargs: Any
    ):
        if entity_id is not None:
            kwargs["entity_id"] = str(entity_id)
        if data is not None:
            kwargs["data"] = data
        super().call_service(service=service, **kwargs)

    def log(self, message: str, **kwargs: Any):
        super().log(message, **kwargs)
