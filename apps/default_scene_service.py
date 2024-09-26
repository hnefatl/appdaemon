# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

import datetime
import enum
import random
from typing import Any, Dict, Optional, TypeVar

import typed_hass
from typed_hass import EntityId, Scene, BinarySensor, InputBoolean

EVENT_NAME = "default_scene_turn_on"
T = TypeVar("T")


def between_hours(now: int, start: int, end: int) -> bool:
    """Handle wraparound when comparing hours."""
    if start < end:  # between_hours(12, 5, 18) = True
        return start <= now and now < end
    else:  # between_hours(19, 18, 5) = True
        return start <= now or now < end


class Room(enum.Enum):
    BEDROOM = enum.auto()
    LIVING_ROOM = enum.auto()
    OFFICE = enum.auto()
    CORRIDOR = enum.auto()
    ENTRANCE = enum.auto()
    BATHROOM = enum.auto()
    KITCHEN = enum.auto()


ROOM_NAME_MAPPING = {room.name.lower(): room for room in list(Room)}


def get_day_stable_random(seed: int, values: dict[T, int]) -> T:
    """Get a random value which is stable throughout a given day for the same given seed."""
    # Get the timestamp for the start of "today"
    today_seed = int(
        (
            datetime.datetime.combine(
                datetime.date.today(), datetime.datetime.min.time()
            )
        ).timestamp()
    )
    rand = random.Random(today_seed + seed)

    # The order of keys and values within the dict are the same
    sequence = list(values.keys())
    weights = list(values.values())
    choices = rand.choices(sequence, weights)
    assert len(choices) == 1
    return choices[0]


def get_day_stable_random_uniform(seed: int, values: set[T]) -> T:
    return get_day_stable_random(seed, {x: 1 for x in values})


# This can't be a proper service because AppDaemon can't create HA services :( Instead, using the workaround from
# https://community.home-assistant.io/t/ad-and-register-service-but-getting-service-not-found/185258/8 to listen for an
# event and treat it as a service call.
class DefaultSceneService(typed_hass.Hass):

    def initialize(self):
        self.listen_event(event=EVENT_NAME, callback=self._turn_on_default_scene)

    def _get_boolean_state(self, entity_id: EntityId) -> bool:
        return self.get_state(entity_id=entity_id) == "on"

    def _get_default_scene_for_room(self, room: Room) -> Optional[EntityId]:
        hour = datetime.datetime.now().hour
        keith_awake = self._get_boolean_state(InputBoolean("keith_awake"))
        nighttime_lights_enabled = self._get_boolean_state(
            InputBoolean("nighttime_lights_enabled")
        )

        is_workday = datetime.datetime.now().weekday() < 5 and self._get_boolean_state(
            InputBoolean("workday")
        )

        # Special-case lighting for the corridor when the 3d-printer is active,
        # so I can check up on it more easily.
        if room is Room.CORRIDOR and self._get_boolean_state(
            BinarySensor("octoprint_printing")
        ):
            return Scene(f"{room.name.lower()}_bright")

        # In the late evening and early morning, default to dim lights in all rooms.
        if nighttime_lights_enabled and between_hours(hour, 0, 6):
            return Scene(f"{room.name.lower()}_dim")

        # In the bedroom, if still in "asleep mode" then always do dim.
        if room is Room.BEDROOM and not keith_awake:
            return Scene("bedroom_dim")

        if room is Room.LIVING_ROOM:
            return get_day_stable_random_uniform(
                room.value,
                {
                    Scene("living_room_arctic_aurora"),
                    Scene("living_room_ibiza"),
                    Scene("living_room_savanna_sunset"),
                    Scene("living_room_soho"),
                    Scene("living_room_spring_blossom"),
                    Scene("living_room_tropical_twilight"),
                },
            )
        elif room is Room.OFFICE:
            keith_ooo = self._get_boolean_state(BinarySensor("keith_ooo"))
            # If it's mon-fri before 3pm, default to work lighting. This isn't a perfect match for e.g. OOO, or
            # wakeup/relax calendar events, but due to race conditions and complexity it's an approximation.
            if is_workday and hour < 15 and not keith_ooo:
                return Scene("office_concentrate")
            return get_day_stable_random_uniform(
                room.value,
                {
                    Scene("office_arctic_aurora"),
                    Scene("office_savanna_sunset"),
                    Scene("office_soho"),
                    Scene("office_spring_blossom"),
                    Scene("office_tropical_twilight"),
                },
            )
        else:
            return Scene(f"{room.name.lower()}_bright")

    def _turn_on_default_scene(self, _event_name: str, data: Dict[str, Any], *_: Any):
        room_names = data.get("rooms", None)
        assert isinstance(
            room_names, list
        ), f"room names passed to {EVENT_NAME} must be a list, got: {room_names}"
        transition = data.get("transition", None)
        assert transition is None or isinstance(
            transition, int
        ), f"transition passed to {EVENT_NAME} must be an int, got: {transition}"

        for room_name in room_names:
            assert isinstance(
                room_name, str
            ), f"room name passed to {EVENT_NAME} must be a str, got: {room_name}"
            room = ROOM_NAME_MAPPING.get(room_name)
            if room is None:
                continue
            scene = self._get_default_scene_for_room(room)
            self.info_log(f"Loading default scene for {room}: {scene}")
            if scene is None:
                continue
            # Passing a None transition fails, and I suspect a transition of 0
            # might be different to "no transition"...
            optional_transition = (
                {} if transition is None else {"transition": transition}
            )
            self.turn_on(entity_id=scene, **optional_transition)
