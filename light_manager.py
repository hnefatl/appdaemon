from __future__ import annotations
from typing import Any, Awaitable, Dict, List, NamedTuple, NewType, Optional, Set

import appdaemon.plugins.hass.hassapi as hass  # type: ignore
import asyncio
import bidict
import contextlib
import enum


@enum.unique
class Room(enum.Enum):
    BEDROOM = enum.auto()
    LIVING_ROOM = enum.auto()
    OFFICE = enum.auto()
    CORRIDOR = enum.auto()


ALL_ROOMS = list(Room)
LightId = NewType("LightId", "str")


ROOM_LIGHT_MAPPING = {
    Room.LIVING_ROOM: {
        LightId("light.living_room_1"),
        LightId("light.living_room_2"),
        LightId("light.living_room_spot_1"),
        LightId("light.living_room_spot_2"),
    },
}
LIGHT_ROOM_MAPPING = {light: room for room, lights in ROOM_LIGHT_MAPPING.items() for light in lights}


class RoomLocker:
    def __init__(self):
        self._room_locks = {room: asyncio.Lock() for room in ALL_ROOMS}

    @contextlib.asynccontextmanager
    async def lock_rooms(self, *args: Room):
        """Acquires the locks for all given rooms in a deterministic order to prevent deadlocks."""
        room_set = set(args)
        async with contextlib.AsyncExitStack() as exit_stack:
            for room in sorted(room_set, key=lambda r: r.value):
                room_lock = self._room_locks.get(room)
                assert room_lock is not None, f"Invalid room: {room}, from {args}"
                await exit_stack.enter_async_context(room_lock)
            yield


class LightSession(contextlib.AsyncExitStack):
    """An exclusive lock on a set of rooms, allowing for the lights to be controlled exclusively. NOT THREAD SAFE."""

    class LightState(NamedTuple):
        state: str
        attributes: Dict[str, Any]

    def __init__(
        self,
        hassio: hass.Hass,
        restore_lights: bool,
        rooms: Set[Room],
        room_lock_context: contextlib.AbstractAsyncContextManager,
    ):
        super().__init__()
        self._hass = hassio
        self._restore_lights = restore_lights
        self._rooms = rooms
        self._room_lock_context = room_lock_context
        self._light_states: Optional[Dict[LightId, LightSession.LightState]] = None

    async def __aenter__(self) -> LightSession:
        result = await super().__aenter__()
        await self.enter_async_context(self._room_lock_context)
        if self._restore_lights:
            self._save_light_state()
        return result

    async def __aexit__(self, *args) -> bool:
        if self._restore_lights:
            self._load_light_state()
        return await super().__aexit__(*args)

    def _save_light_state(self):
        self._light_states = {}
        for room in self._rooms:
            for light_id in ROOM_LIGHT_MAPPING.get(room):
                attributes = self._hass.get_state(entity_id=light_id, attribute="all")
                if attributes is None:
                    self.log(f"Failed to get state for light {light_id}")
                    continue
                self._light_states[light_id] = LightSession.LightState(
                    state=attributes.get("state"), attributes=attributes
                )
        self._hass.log(self._light_states)

    def _load_light_state(self):
        for light_id, light_state in self._light_states.items():
            self._hass.set_state(entity_id=light_id, state=light_state.state, attributes=light_state.attributes)
        self._light_states = None

    async def load_scene(self, scene_name: str, transition: Optional[int] = None):
        if self._light_states is None:
            raise ValueError("load_scene called outside of context manager.")
        kwargs = {} if transition is None else {transition: transition}
        self._hass.call_service("scene/load", entity_id=scene_name, **kwargs)


# TODO: Need to make this a singleton for use between different apps?
class LightManager:
    def __init__(self, hassio: hass.Hass):
        self._hass = hassio
        self._room_locker = RoomLocker()

    async def set_lights(self):
        async with self._room_locker.lock_rooms():
            raise NotImplementedError()

    def open_session(self, *args: Room, restore_lights=True) -> LightSession:
        # Create but do not yet enter (acquire) the locks for each room.
        room_lock_context = self._room_locker.lock_rooms(*args)
        return LightSession(
            hassio=self._hass,
            restore_lights=restore_lights,
            rooms=set(args),
            room_lock_context=room_lock_context,
        )
