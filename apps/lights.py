# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
from __future__ import annotations

import abc
import datetime

from typing import Any, Optional, Callable, TypeVar, ParamSpec, Concatenate
from typing_extensions import override
from functools import wraps

import typed_hass
from typed_hass import EntityId

P = ParamSpec("P")
# Annoyingly necessary because decorators can't easily be defined inside classes,
# and we need `Self@Room` from outside the class. `Room` doesn't cut it for some
# reason, but an upper-bounded typevar does.
RoomVar = TypeVar("RoomVar", bound="Room")

# Whether to print "verbose" log lines, intended to be debug logs for logic that doesn't cause state to change.
_VERBOSE_LOG = True


class ActivitySensor:
    def __init__(
        self,
        entity: EntityId,
        predicate: Callable[[typed_hass.Hass, str], bool],
        descriptor: str,
    ):
        self.entity = entity
        self._predicate = predicate
        self.descriptor = descriptor
        # active_predicate:

    def is_active(self, hass: typed_hass.Hass) -> bool:
        return self._predicate(hass, hass.get_state(self.entity))

    def __str__(self) -> str:
        return f"{self.entity} {self.descriptor}"

    def __repr__(self) -> str:
        return str(self)

    @staticmethod
    def _single_entity_predicate(
        entity: EntityId, predicate: Callable[[str], bool], *args, **kwargs  # type: ignore
    ):
        return ActivitySensor(
            entity, lambda _, s: predicate(s), *args, **kwargs  # type: ignore
        )

    @staticmethod
    def is_on(entity: EntityId) -> ActivitySensor:
        return ActivitySensor._single_entity_predicate(
            entity, lambda s: s == "on", descriptor="is on"
        )

    @staticmethod
    def is_off(entity: EntityId) -> ActivitySensor:
        return ActivitySensor._single_entity_predicate(
            entity, lambda s: s == "off", descriptor="is off"
        )

    @staticmethod
    def isnt_off(entity: EntityId) -> ActivitySensor:
        return ActivitySensor._single_entity_predicate(
            entity, lambda s: s != "off", descriptor="isn't off"
        )

    @staticmethod
    def is_below(entity: EntityId, threshold: float) -> ActivitySensor:
        return ActivitySensor._single_entity_predicate(
            entity, lambda s: float(s) < threshold, descriptor=f"< {threshold}"
        )

    @staticmethod
    def is_above(entity: EntityId, threshold: float) -> ActivitySensor:
        return ActivitySensor._single_entity_predicate(
            entity, lambda s: float(s) > threshold, descriptor=f"> {threshold}"
        )

    @staticmethod
    def compared_to(
        entity: EntityId,
        other: EntityId,
        comparator: Callable[[str, str], bool],
        descriptor: str,
    ):
        return ActivitySensor(
            entity, lambda h, s: comparator(s, h.get_state(other)), descriptor
        )


class Room(abc.ABC):
    def __init__(
        self,
        hass: typed_hass.Hass,
        name: str,
        no_motion_timeout: datetime.timedelta,
        motion_sensors: Optional[set[EntityId]] = None,
        activity_sensors: Optional[list[ActivitySensor]] = None,
        lights_only_if: Optional[list[ActivitySensor]] = None,
        has_manual_control_toggle: bool = False,
    ):
        # hass instance
        self._hass = hass
        # Room name for the default scene service and area for lights out.
        self._name = name
        # How long to wait after no motion before turning off the lights.
        self._no_motion_timeout = no_motion_timeout
        # Don't turn out the lights if any of these entities are on.
        self._activity_sensors = activity_sensors or []
        # Don't turn on the lights if any of these entities are on.
        self._lights_only_if = lights_only_if or []
        # `input_boolean` for toggling automatic/manual control.
        self._manual_control_input_boolean = (
            EntityId(f"input_boolean.{name}_manual_control")
            if has_manual_control_toggle
            else None
        )

        if motion_sensors is None:
            motion_sensors = {EntityId(f"binary_sensor.{name}_motion_occupancy")}
        # Entities indicating motion within the room.
        self._motion_sensors = motion_sensors
        # The last time there was motion in the room. Homeassistant "are lights
        # on" queries can have a bit of lag due to e.g. light transitions.
        self._last_motions = {
            sensor: datetime.datetime.min for sensor in motion_sensors
        }

        # Whether this model thinks the lights are on: if we tell HA to turn off
        # the lights, it'll take maybe 5s before getting the light's state will
        # return "off", because of transition + lag.  This causes an edge case
        # where movement while the light is turning off off prevents the lights
        # from coming back on, until movement stops being detected and is
        # subsequently detected again.
        self._lights_on = self._are_lights_off()

    def initialise(self, hass: typed_hass.Hass):
        for motion_sensor in self._motion_sensors:
            hass.listen_state(
                callback=self.on_room_motion, entity_id=motion_sensor, new="on"
            )
            hass.listen_state(
                callback=self.on_room_no_motion,
                entity_id=motion_sensor,
                new="off",
                duration=self._no_motion_timeout,
            )
        # In addition to listening to just motion, also listen for when the
        # devices indicating activity in the room change, otherwise we might
        # leave lights on when a device changes state once we've left the room.
        for activity_sensor in self._activity_sensors:
            hass.listen_state(
                callback=self.on_activity_sensor_change,
                entity_id=activity_sensor.entity,
            )

    @abc.abstractmethod
    def _turn_on_lights(self) -> None:
        pass

    @abc.abstractmethod
    def _turn_off_lights(self) -> None:
        pass

    @abc.abstractmethod
    def _are_lights_off(self) -> bool:
        pass

    def _get_active_sensors(self) -> list[ActivitySensor]:
        return [
            activity_sensor
            for activity_sensor in self._activity_sensors
            if activity_sensor.is_active(self._hass)
        ]

    def _get_inactive_required_sensors(self) -> list[ActivitySensor]:
        return [
            sensor
            for sensor in self._lights_only_if
            if not sensor.is_active(self._hass)
        ]

    def manual_control_enabled(self) -> bool:
        if self._manual_control_input_boolean is None:
            return False
        return self._hass.get_state(self._manual_control_input_boolean) == "on"

    @staticmethod
    def skip_if_manual_control_enabled(
        f: Callable[Concatenate[RoomVar, P], None]
    ) -> Callable[Concatenate[RoomVar, P], None]:
        @wraps(f)
        def inner(self: RoomVar, *args: P.args, **kwargs: P.kwargs):
            if self.manual_control_enabled():
                self._log(f"Manual control enabled in {self._name}, no action")
                return
            f(self, *args, **kwargs)

        return inner

    def _log(self, msg: str):
        self._hass.log(msg)

    def _verbose_log(self, msg: str):
        if _VERBOSE_LOG:
            self._hass.log(msg)

    @skip_if_manual_control_enabled
    def on_room_motion(self, entity_id: str, *_: Any):
        self._last_motions[EntityId(entity_id)] = datetime.datetime.now()

        inactive_required_sensors = self._get_inactive_required_sensors()
        if inactive_required_sensors:
            self._verbose_log(
                f"motion in {self._name} from {entity_id} but required sensors aren't active: {inactive_required_sensors}"
            )
            return
        lights_off = self._are_lights_off()
        # Only load the scene if the lights are off: if the lights are already
        # on, leave them as they are.
        if lights_off or not self._lights_on:
            self._log(f"motion in {self._name} from {entity_id}, turning on lights")
            if not self._lights_on:
                self._verbose_log(
                    "edge case: lights were on in HA but off in the model."
                )
            self._turn_on_lights()
        else:
            self._verbose_log(
                f"motion in {self._name} from {entity_id} but lights already on"
            )

    @skip_if_manual_control_enabled
    def on_room_no_motion(self, *_: Any):
        active_devices = self._get_active_sensors()
        if active_devices:
            self._verbose_log(
                f"no motion in {self._name}, but devices are active: {active_devices}"
            )
            return

        self._log(
            f"no motion in {self._name} for {self._no_motion_timeout}, no devices are active, lights off"
        )
        self._turn_off_lights()

    @skip_if_manual_control_enabled
    def on_activity_sensor_change(self, entity: str, *_: Any):
        active_devices = self._get_active_sensors()
        if active_devices:
            self._log(f"active devices remaining: {active_devices}")
            return

        # Don't turn the lights off if a device is turned off and there hasn't
        # been motion recently: wait for the full timeout.
        now = datetime.datetime.now()
        time_since_last_motion = min(
            now - last_motion for last_motion in self._last_motions.values()
        )
        if time_since_last_motion > self._no_motion_timeout:
            self._log(
                f"no active devices, last was {entity}, last motion was "
                f"{time_since_last_motion.seconds} ago vs timeout of "
                f"{self._no_motion_timeout.seconds}, lights off"
            )
            self._turn_off_lights()
        else:
            self._verbose_log(
                f"no active devices, last was {entity}, last motion was "
                f"{time_since_last_motion.seconds} ago vs timeout of "
                f"{self._no_motion_timeout.seconds}, so room occupied"
            )


class LightGroupRoom(Room):
    def __init__(self, name: str, area_name: Optional[str] = None, **kwargs):  # type: ignore
        self._area_name = name if area_name is None else area_name
        super().__init__(name=name, **kwargs)  # type: ignore

    @override
    def _turn_on_lights(self) -> None:
        self._lights_on = True
        self._hass.fire_event(event="default_scene_turn_on", rooms=[self._name])

    @override
    def _turn_off_lights(self) -> None:
        self._lights_on = False
        self._hass.call_service(
            service="light/turn_off", transition=5, area_id=self._area_name
        )

    @override
    def _are_lights_off(self) -> bool:
        return (
            self._hass.get_state(EntityId(f"group.{self._area_name}_lights")) == "off"
        )


class SwitchLightRoom(Room):
    def __init__(self, switch_name: EntityId, **kwargs):  # type: ignore
        self._switch_name = switch_name
        super().__init__(**kwargs)  # type: ignore

    @override
    def _turn_on_lights(self) -> None:
        self._lights_on = True
        self._hass.call_service(service="switch/turn_on", entity_id=self._switch_name)

    @override
    def _turn_off_lights(self) -> None:
        self._lights_on = False
        self._hass.call_service(service="switch/turn_off", entity_id=self._switch_name)

    @override
    def _are_lights_off(self) -> bool:
        return self._hass.get_state(self._switch_name) == "off"


class Lights(typed_hass.Hass):
    def initialize(self):
        ROOMS = [
            LightGroupRoom(
                hass=self,
                name="office",
                no_motion_timeout=datetime.timedelta(minutes=15),
            ),
            LightGroupRoom(
                hass=self,
                name="living_room",
                no_motion_timeout=datetime.timedelta(minutes=15),
                motion_sensors={
                    EntityId("binary_sensor.living_room_motion_occupancy"),
                    EntityId("binary_sensor.reading_chair_motion_occupancy"),
                },
                activity_sensors=[
                    ActivitySensor.isnt_off(EntityId("media_player.shield")),
                    ActivitySensor.isnt_off(
                        EntityId("binary_sensor.ping_nintendo_switch")
                    ),
                    ActivitySensor.isnt_off(
                        EntityId("media_player.living_room_speaker")
                    ),
                    ActivitySensor.is_on(EntityId("switch.pc")),
                ],
            ),
            SwitchLightRoom(
                hass=self,
                name="bathroom",
                switch_name=EntityId("switch.bathroom_light_and_fan"),
                no_motion_timeout=datetime.timedelta(minutes=2),
                activity_sensors=[
                    ActivitySensor.is_on(EntityId("input_boolean.shower_active")),
                    # Can't turn off the lights because they're also the extractor fan :(
                    ActivitySensor.compared_to(
                        EntityId("sensor.bathroom_humidity"),
                        EntityId("sensor.office_humidity"),
                        # Wait until bathroom is close to the ambient humidity
                        # as measured in office. Hardcoded thresholds don't
                        # work well with the highly variable humidity here.
                        lambda b, o: float(b) > float(o) + 5,
                        descriptor="bathroom humidity > office humidity + 5",
                    ),
                ],
            ),
            LightGroupRoom(
                hass=self,
                name="bedroom",
                motion_sensors={
                    EntityId("binary_sensor.bedroom_motion_occupancy"),
                    EntityId("binary_sensor.bedroom_entrance_motion_occupancy"),
                },
                no_motion_timeout=datetime.timedelta(minutes=1),
                lights_only_if=[
                    ActivitySensor.is_on(EntityId("input_boolean.keith_awake"))
                ],
                has_manual_control_toggle=True,
            ),
            LightGroupRoom(
                hass=self,
                name="entrance",
                no_motion_timeout=datetime.timedelta(minutes=3),
            ),
            LightGroupRoom(
                hass=self,
                name="kitchen",
                no_motion_timeout=datetime.timedelta(minutes=2),
            ),
        ]

        for room in ROOMS:
            room.initialise(self)
