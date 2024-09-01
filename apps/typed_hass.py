"""Slightly more typed overload for hass"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from typing import Any, Optional, NewType, Callable
import datetime

import appdaemon.plugins.hass.hassapi as hass  # pyright: ignore[reportMissingTypeStubs]

EntityId = NewType("EntityId", str)
StateCallback = Callable[[EntityId, str, Optional[str], str, dict[str, Any]], None]


class Hass(hass.Hass):
    """Limited but usefully-typed overrides."""

    def __init__(self, *args, **kwargs):  # type: ignore
        return super().__init__(*args, **kwargs)  # type: ignore

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
