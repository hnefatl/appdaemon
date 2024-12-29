from typing import Any, NewType, Self
import abc
import dataclasses
import datetime
import typed_hass
import re
import json
import pathlib
import threading

ACTION_NAME = "WIFI_DEVICE_REMEMBER"
INTERNAL_IP_REGEX = re.compile(r"^(10|192\.168|172)\..*")
# This resolves to a path outside the docker container, on the host filesystem.
REGISTRY_PATH = pathlib.Path("/conf/wifi_device_registry.json")

Mac = NewType("Mac", str)
FriendlyName = NewType("FriendlyName", str)


@dataclasses.dataclass(frozen=True)
class Serialisable(abc.ABC):
    def serialise(self) -> str:
        return json.dumps(dataclasses.asdict(self), indent=2)

    @classmethod
    def deserialise(cls, s: str) -> Self:
        return cls(**json.loads(s))


@dataclasses.dataclass(frozen=True)
class DeviceTracker(Serialisable):
    entity_id: typed_hass.EntityId
    state: dict[str, Any]

    def is_wifi_device(self) -> bool:
        return (
            self._attributes().get("source_type") == "router"
            and INTERNAL_IP_REGEX.match(self.ip() or "") is not None
        )

    def is_connected(self) -> bool:
        return self.state.get("state") == "home"

    def _attributes(self) -> dict[str, Any]:
        return self.state.get("attributes", {})

    def ip(self) -> str | None:
        return self._attributes().get("ip")

    def mac(self) -> Mac | None:
        if (mac := self._attributes().get("mac")) is not None:
            return Mac(mac)
        return None

    def hostname(self) -> str | None:
        return self._attributes().get("hostname")


@dataclasses.dataclass(frozen=True)
class DeviceRegistry(Serialisable):
    macs: dict[Mac, FriendlyName]
    unknown_entities: dict[typed_hass.EntityId, FriendlyName]

    def contains(self, tracker: DeviceTracker) -> bool:
        return tracker.mac() in self.macs or tracker.entity_id in self.unknown_entities

    def add(self, tracker: DeviceTracker, friendly_name: FriendlyName):
        if (mac := tracker.mac()) is not None:
            self.macs[mac] = friendly_name
            # If a previously unknown device has gained a mac, remove the old record to
            # keep the registry clean.
            self.unknown_entities.pop(tracker.entity_id, None)
        else:
            self.unknown_entities[tracker.entity_id] = friendly_name

    @classmethod
    def load(cls) -> "DeviceRegistry | None":
        try:
            return DeviceRegistry.deserialise(REGISTRY_PATH.read_text())
        except:
            return None

    def save(self):
        REGISTRY_PATH.write_text(self.serialise())


class WifiDevices(typed_hass.Hass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._device_registry = DeviceRegistry(macs={}, unknown_entities={})
        self._device_registry_lock = threading.Lock()

        self._last_notified_time = dict[typed_hass.EntityId, datetime.datetime]()

    def initialize(self):
        with self._device_registry_lock:
            if (device_registry := DeviceRegistry.load()) is not None:
                self._device_registry = device_registry
                self.info_log(f"Loaded device registry from {REGISTRY_PATH}")
            else:
                self.warning_log(
                    f"Failed to load wifi device registry from {REGISTRY_PATH}"
                )

        self.listen_notify_phone_action(
            callback=self.on_remember_device, action_name=ACTION_NAME
        )
        self.run_every(callback=self.update, start="now", interval_s=60)

    def terminate(self):
        try:
            with self._device_registry_lock:
                self._device_registry.save()
        except Exception as e:
            # Don't fail the termination since that breaks the next automatic start.
            self.error_log(f"Failed to save on termination: {e}")

    def update(self, _):
        trackers = [DeviceTracker(e, s) for e, s in self.get_tracker_details().items()]
        # Filter to only relevant new devices
        with self._device_registry_lock:
            trackers = [
                t
                for t in trackers
                if t.is_wifi_device()
                and t.is_connected()
                and not self._device_registry.contains(t)
            ]

        for tracker in trackers:
            # Rate limit notifications per entity
            last_notified = self._last_notified_time.get(
                tracker.entity_id, datetime.datetime.min
            )
            if datetime.datetime.now() - last_notified <= datetime.timedelta(hours=1):
                continue

            message_lines = {
                "Hostname": tracker.hostname(),
                "IP": tracker.ip(),
                "MAC": tracker.mac(),
            }
            if tracker.mac() is None:
                # The ID is based on the MAC, so omit the full ID unless there's no better identifier
                message_lines["Entity ID"] = tracker.entity_id

            s = "\n".join(
                f"- {f}: {v}" for f, v in message_lines.items() if v is not None
            )

            self._last_notified_time[tracker.entity_id] = datetime.datetime.now()
            self.info_log(f"Sending notification for new device {tracker.entity_id}")
            self.notify_phone(
                title="Unknown device connected to wifi",
                message=s,
                data={"tracker_data": tracker.serialise()},
                actions=[
                    typed_hass.NotifyAction(
                        title="Name",
                        action=ACTION_NAME,
                        behavior="textInput",
                    ),
                ],
            )

    def on_remember_device(self, _, event_params, __):
        if (tracker_data := event_params.get("tracker_data")) is None:
            self.error_log("Missing field `tracker_data` in event")
            return
        if (friendly_name := event_params.get("reply_text")) is None:
            self.error_log("Missing field `reply_text` in event")
            return
        friendly_name = FriendlyName(friendly_name.strip())

        tracker = DeviceTracker.deserialise(tracker_data)
        self.info_log(f"Remembering {tracker} as {friendly_name}")
        with self._device_registry_lock:
            self._device_registry.add(tracker, friendly_name)
            # Could batch saves but realistically they'll be entered slowly and infrequently enough
            # for it not to matter.
            self._device_registry.save()
