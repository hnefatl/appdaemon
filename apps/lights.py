from __future__ import annotations

import dataclasses
import datetime

from typing import Optional, Callable, Any

import appdaemon.plugins.hass.hassapi as hass  # type: ignore


# Whether to print "verbose" log lines, intended to be debug logs for logic that doesn't cause state to change.
_VERBOSE_LOG = False


def callback(
    f: Callable[[Room, str, str, str, str, Any], None]
) -> Callable[[Room, str, str, str, str, Any], None]:
    """Provides type checking and early bail-out if manual control is enabled"""

    def wrapper(
        room: Room,
        entity: str,
        attribute: str,
        old: str,
        new: str,
        kwargs: Any,
    ) -> None:
        if room.manual_control_enabled():
            room.hass.log(f"Manual control enabled in {room.name}, no action")
            return
        f(room, entity, attribute, old, new, kwargs)

    return wrapper


def to_seconds(**kwargs) -> int:
    return datetime.timedelta(**kwargs).seconds


def get_state(hass: hass.Hass, entity_id: str) -> str:
    state = hass.get_state(entity_id=entity_id)
    # hass.log(f"entity {entity_id}, state {state}")
    if state is None:
        raise ValueError(f"Unknown entity {entity_id}")
    return state


@dataclasses.dataclass
class ActivitySensor:
    entity: str
    active_predicate: Callable[[str], bool]
    descriptor: str

    def is_active(self, hass: hass.Hass) -> bool:
        return self.active_predicate(get_state(hass, self.entity))

    def __str__(self) -> str:
        return f"{self.entity} {self.descriptor}"

    def __repr__(self) -> str:
        return str(self)

    @staticmethod
    def is_on(entity: str) -> ActivitySensor:
        return ActivitySensor(entity, lambda s: s == "on", descriptor="is on")

    @staticmethod
    def is_off(entity: str) -> ActivitySensor:
        return ActivitySensor(entity, lambda s: s == "off", descriptor="is off")

    @staticmethod
    def isnt_off(entity: str) -> ActivitySensor:
        return ActivitySensor(entity, lambda s: s != "off", descriptor="isn't off")


@dataclasses.dataclass
class Room:
    hass: hass.Hass

    # Room name for the default scene service and area for lights out.
    name: str
    # Entity indicating motion within the room.
    motion_sensor: str
    # How long to wait after no motion before turning off the lights.
    no_motion_timeout: int
    # Don't turn out the lights if any of these entities are on.
    activity_sensors: list[ActivitySensor]
    # Don't turn on the lights if any of these entities are on.
    lights_only_if: list[ActivitySensor]
    # input_boolean for toggling automatic/manual control.
    manual_control_input_boolean: Optional[str]

    @staticmethod
    def make_room(
        hass: hass.Hass,
        name: str,
        no_motion_timeout: int,
        activity_sensors: Optional[list[ActivitySensor]] = None,
        lights_only_if: Optional[list[ActivitySensor]] = None,
        has_manual_control_toggle: bool = False,
    ) -> Room:
        return Room(
            hass=hass,
            name=name,
            motion_sensor=f"binary_sensor.{name}_motion_occupancy",
            no_motion_timeout=no_motion_timeout,
            activity_sensors=activity_sensors or [],
            lights_only_if=lights_only_if or [],
            manual_control_input_boolean=(
                f"input_boolean.{name}_manual_control"
                if has_manual_control_toggle
                else None
            ),
        )

    def initialise(self, hass: hass.Hass):
        hass.listen_state(
            callback=self.on_room_motion, entity_id=self.motion_sensor, new="on"
        )
        hass.listen_state(
            callback=self.on_room_no_motion,
            entity_id=self.motion_sensor,
            new="off",
            duration=self.no_motion_timeout,
        )
        # In addition to listening to just motion, also listen for when the
        # devices indicating activity in the room change, otherwise we might
        # leave lights on when a device changes state once we've left the room.
        for activity_sensor in self.activity_sensors:
            hass.listen_state(
                callback=self.on_activity_sensor_change,
                entity_id=activity_sensor.entity,
            )

    def _turn_off_lights(self):
        self.hass.call_service(
            service="light/turn_off", transition=5, area_id=self.name
        )

    def _get_active_sensors(self):
        return [
            activity_sensor
            for activity_sensor in self.activity_sensors
            if activity_sensor.is_active(self.hass)
        ]

    def manual_control_enabled(self) -> bool:
        if self.manual_control_input_boolean is None:
            return False
        return get_state(self.hass, self.manual_control_input_boolean) == "on"

    def _log(self, msg: str):
        self.hass.log(msg)

    def _verbose_log(self, msg: str):
        if _VERBOSE_LOG:
            self.hass.log(msg)

    @callback
    def on_room_motion(self, *_):
        area_lights_off = get_state(self.hass, f"group.{self.name}_lights") == "off"
        # Only load the scene if the lights are off: if the lights are already
        # on, leave them as they are.
        if area_lights_off:
            self._log(f"motion in {self.name}, loading default scene")
            self.hass.fire_event(event="default_scene_turn_on", rooms=[self.name])
        else:
            self._verbose_log(f"motion in {self.name} but lights already on")

    @callback
    def on_room_no_motion(self, *_):
        active_devices = self._get_active_sensors()
        if not active_devices:
            self._log(f"no motion in {self.name}, no devices are active, lights off")
            self._turn_off_lights()
        else:
            self._verbose_log(
                f"no motion in {self.name}, but devices are active: {active_devices}"
            )

    @callback
    def on_activity_sensor_change(self, entity: str, *_):
        active_devices = self._get_active_sensors()
        if not active_devices:
            room_occupied = get_state(self.hass, self.motion_sensor) == "on"
            if not room_occupied:
                self._log(f"no active devices, last was {entity}, lights off")
                self._turn_off_lights()
            else:
                self._verbose_log(
                    f"no active devices, last was {entity}, but room occupied"
                )
        else:
            self._log(f"active devices remaining: {active_devices}")


class Lights(hass.Hass):
    def initialize(self):
        ROOMS = [
            Room.make_room(
                hass=self,
                name="office",
                no_motion_timeout=to_seconds(hours=1),
                activity_sensors=[ActivitySensor.is_on("switch.pc")],
            ),
            Room.make_room(
                hass=self,
                name="living_room",
                no_motion_timeout=to_seconds(minutes=15),
                activity_sensors=[ActivitySensor.isnt_off("media_player.shield")],
            ),
            Room.make_room(
                hass=self,
                name="bathroom",
                no_motion_timeout=to_seconds(minutes=2),
                activity_sensors=[ActivitySensor.is_on("input_boolean.shower_active")],
            ),
            Room.make_room(
                hass=self,
                name="bedroom",
                no_motion_timeout=to_seconds(minutes=1),
                lights_only_if=[ActivitySensor.is_on("input_boolean.keith_awake")],
                has_manual_control_toggle=True,
            ),
            Room.make_room(
                hass=self,
                name="corridor",
                no_motion_timeout=to_seconds(minutes=2, seconds=30),
            ),
            Room.make_room(
                hass=self,
                name="entrance",
                no_motion_timeout=to_seconds(minutes=5),
            ),
            Room.make_room(
                hass=self,
                name="kitchen",
                no_motion_timeout=to_seconds(minutes=5),
            ),
        ]

        for room in ROOMS:
            room.initialise(self)
