from __future__ import annotations

import dataclasses
import datetime

from typing import Optional, Callable, Any

import appdaemon.plugins.hass.hassapi as hass  # type: ignore


# Whether to print "verbose" log lines, intended to be debug logs for logic that doesn't cause state to change.
_VERBOSE_LOG = True


def callback(f: Callable[[Room, str, str, str, str, Any], None]) -> Callable[[Room, str, str, str, str, Any], None]:
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

    @staticmethod
    def is_below(entity: str, threshold: float) -> ActivitySensor:
        return ActivitySensor(entity, lambda s: float(s) < threshold, descriptor=f"< {threshold}")


@dataclasses.dataclass
class Room:
    hass: hass.Hass

    # Room name for the default scene service and area for lights out.
    name: str
    # Entity indicating motion within the room.
    motion_sensor: str
    # How long to wait after no motion before turning off the lights.
    no_motion_timeout: datetime.timedelta
    # Don't turn out the lights if any of these entities are on.
    activity_sensors: list[ActivitySensor]
    # Don't turn on the lights if any of these entities are on.
    lights_only_if: list[ActivitySensor]
    # input_boolean for toggling automatic/manual control.
    manual_control_input_boolean: Optional[str]
    # The last time there was motion in the room. Homeassistant "are lights on"
    # queries can have a bit of lag due to e.g. light transitions.
    last_motion: datetime.datetime
    # Whether this model thinks the lights are on: if we tell HA to turn off
    # the lights, it'll take maybe 5s before getting the light's state will
    # return "off", because of transition + lag.
    # This causes an edge case where movement while the light is turning off
    # off prevents the lights from coming back on, until movement stops being
    # detected and is subsequently detected again.
    lights_on: bool

    @staticmethod
    def make_room(
        hass: hass.Hass,
        name: str,
        no_motion_timeout: datetime.timedelta,
        activity_sensors: Optional[list[ActivitySensor]] = None,
        lights_only_if: Optional[list[ActivitySensor]] = None,
        has_manual_control_toggle: bool = False,
    ) -> Room:
        room = Room(
            hass=hass,
            name=name,
            motion_sensor=f"binary_sensor.{name}_motion_occupancy",
            no_motion_timeout=no_motion_timeout,
            activity_sensors=activity_sensors or [],
            lights_only_if=lights_only_if or [],
            manual_control_input_boolean=(
                f"input_boolean.{name}_manual_control" if has_manual_control_toggle else None
            ),
            last_motion=datetime.datetime.min,
            lights_on=False
        )
        # Initial seed for when developing.
        room.lights_on = room._is_light_group_on()
        return room

    def initialise(self, hass: hass.Hass):
        hass.listen_state(callback=self.on_room_motion, entity_id=self.motion_sensor, new="on")
        hass.listen_state(
            callback=self.on_room_no_motion,
            entity_id=self.motion_sensor,
            new="off",
            duration=self.no_motion_timeout.seconds,
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
        self.lights_on = False
        self.hass.call_service(service="light/turn_off", transition=5, area_id=self.name)

    def _is_light_group_on(self):
        return get_state(self.hass, f"group.{self.name}_lights") == "off"

    def _get_active_sensors(self) -> list[ActivitySensor]:
        return [activity_sensor for activity_sensor in self.activity_sensors if activity_sensor.is_active(self.hass)]

    def _get_inactive_required_sensors(self) -> list[ActivitySensor]:
        return [sensor for sensor in self.lights_only_if if not sensor.is_active(self.hass)]

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
        self.last_motion = datetime.datetime.now()

        inactive_required_sensors = self._get_inactive_required_sensors()
        if inactive_required_sensors:
            self._verbose_log(f"motion in {self.name} but required sensors aren't active: {inactive_required_sensors}")
            return
        area_lights_off = self._is_light_group_on()
        # Only load the scene if the lights are off: if the lights are already
        # on, leave them as they are.
        if area_lights_off or not self.lights_on:
            self._log(f"motion in {self.name}, loading default scene")
            if not self.lights_on:
                self._verbose_log("edge case: lights were on in HA but off in the model.")
            self.hass.fire_event(event="default_scene_turn_on", rooms=[self.name])
            self.lights_on = True
        else:
            self._verbose_log(f"motion in {self.name} but lights already on")

    @callback
    def on_room_no_motion(self, *_):
        active_devices = self._get_active_sensors()
        if active_devices:
            self._verbose_log(f"no motion in {self.name}, but devices are active: {active_devices}")
            return

        self._log(f"no motion in {self.name} for {self.no_motion_timeout}, no devices are active, lights off")
        self._turn_off_lights()

    @callback
    def on_activity_sensor_change(self, entity: str, *_):
        active_devices = self._get_active_sensors()
        if active_devices:
            self._log(f"active devices remaining: {active_devices}")
            return

        # Don't turn the lights off if a device is turned off and there hasn't
        # been motion recently: wait for the full timeout.
        time_since_last_motion = datetime.datetime.now() - self.last_motion
        if time_since_last_motion > self.no_motion_timeout:
            self._log(
                f"no active devices, last was {entity}, last motion was "
                f"{time_since_last_motion.seconds} ago vs timeout of "
                f"{self.no_motion_timeout.seconds}, lights off"
            )
            self._turn_off_lights()
        else:
            self._verbose_log(
                f"no active devices, last was {entity}, last motion was "
                f"{time_since_last_motion.seconds} ago vs timeout of "
                f"{self.no_motion_timeout.seconds}, so room occupied"
            )


class Lights(hass.Hass):
    def initialize(self):
        ROOMS = [
            Room.make_room(
                hass=self,
                name="office",
                no_motion_timeout=datetime.timedelta(hours=1),
                activity_sensors=[ActivitySensor.is_on("switch.pc")],
            ),
            Room.make_room(
                hass=self,
                name="living_room",
                no_motion_timeout=datetime.timedelta(minutes=15),
                activity_sensors=[
                    ActivitySensor.isnt_off("media_player.shield"),
                    ActivitySensor.isnt_off("media_player.living_room_speaker"),
                ],
            ),
            Room.make_room(
                hass=self,
                name="bathroom",
                no_motion_timeout=datetime.timedelta(minutes=2),
                activity_sensors=[ActivitySensor.is_on("input_boolean.shower_active")],
            ),
            Room.make_room(
                hass=self,
                name="bedroom",
                no_motion_timeout=datetime.timedelta(minutes=1),
                lights_only_if=[ActivitySensor.is_on("input_boolean.keith_awake")],
                has_manual_control_toggle=True,
            ),
            Room.make_room(
                hass=self,
                name="corridor",
                no_motion_timeout=datetime.timedelta(minutes=2, seconds=30),
                lights_only_if=[ActivitySensor.is_below("sensor.corridor_motion_illuminance", 35)],
                has_manual_control_toggle=True,
            ),
            Room.make_room(
                hass=self,
                name="entrance",
                no_motion_timeout=datetime.timedelta(minutes=5),
            ),
            Room.make_room(
                hass=self,
                name="kitchen",
                no_motion_timeout=datetime.timedelta(minutes=5),
            ),
        ]

        for room in ROOMS:
            room.initialise(self)
