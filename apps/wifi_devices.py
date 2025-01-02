from typing import Any, NewType, Self, Callable
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
OUI_PATH = pathlib.Path("/conf/oui_snapshot.json")

Mac = NewType("Mac", str)
FriendlyName = NewType("FriendlyName", str)
CompanyName = NewType("CompanyName", str)


class OuiLookup:
    """Reads a snapshot file generated by `../snapshot_oui.py`."""

    def __init__(self, lookup: dict[str, CompanyName]):
        # Keyed by MAC prefix
        self._lookup = lookup

    def identify(self, mac: Mac) -> CompanyName | None:
        m = str(mac)
        while len(m) > 0:
            if (company_name := self._lookup.get(m)) is not None:
                return company_name
            m = m[:-3]  # Strip the last `:XX`
        return None

    @classmethod
    def load(cls) -> "OuiLookup":
        return OuiLookup(json.loads(OUI_PATH.read_text()))

    def __len__(self) -> int:
        return len(self._lookup)


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
    mac: Mac
    ip: str
    hostname: str | None

    @classmethod
    def new(
        cls, entity_id: typed_hass.EntityId, state: dict[str, Any]
    ) -> "DeviceTracker | None":
        attributes = state.get("attributes", {})
        mac = attributes.get("mac")
        ip = attributes.get("ip")
        if (
            attributes.get("source_type") != "router"
            or not isinstance(mac, str)
            or not isinstance(ip, str)
            or INTERNAL_IP_REGEX.match(ip) is None
        ):
            return None
        return DeviceTracker(
            entity_id=entity_id,
            mac=Mac(mac),
            ip=ip,
            hostname=attributes.get("hostname"),
        )


@dataclasses.dataclass(frozen=True)
class DeviceRegistry(Serialisable):
    macs: dict[Mac, FriendlyName]

    def contains(self, tracker: DeviceTracker) -> bool:
        return tracker.mac in self.macs

    def add(self, tracker: DeviceTracker, friendly_name: FriendlyName):
        self.macs[tracker.mac] = friendly_name

    @classmethod
    def load(cls) -> "DeviceRegistry | None":
        try:
            return DeviceRegistry.deserialise(REGISTRY_PATH.read_text())
        except:
            return None

    def save(self, on_fail: Callable[[], None]):
        old = self.load()
        new = self.serialise()
        if old is not None and len(old.serialise()) > len(new):
            on_fail()
            raise RuntimeError(
                "Tried to reduce size of wifi device registry, probably a bug."
                " Crashing to prevent data loss."
                f"Old:\n{old}\nNew:\n{self}"
            )
        REGISTRY_PATH.write_text(new)


class WifiDevices(typed_hass.Hass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._device_registry = DeviceRegistry(macs={})
        self._device_registry_lock = threading.Lock()

        self._last_notified_time = dict[typed_hass.EntityId, datetime.datetime]()

    def initialize(self):
        self._oui_lookup = OuiLookup.load()
        self.info_log(f"Loaded OUI lookup with {len(self._oui_lookup)} entries")
        with self._device_registry_lock:
            if (device_registry := DeviceRegistry.load()) is not None:
                self._device_registry = device_registry
                self.info_log(
                    f"Loaded device registry from {REGISTRY_PATH}: {self._device_registry}"
                )
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
                self._device_registry.save(on_fail=self._on_save_fail)
        except Exception as e:
            # Don't fail the termination since that breaks the next automatic start.
            self.error_log(f"Failed to save on termination: {e}")

    def update(self, _):
        trackers = [
            t
            for e, s in self.get_tracker_details().items()
            if (t := DeviceTracker.new(e, s)) is not None
        ]
        # Filter to only relevant new devices
        with self._device_registry_lock:
            trackers = [t for t in trackers if not self._device_registry.contains(t)]

        if not trackers:
            return

        for tracker in trackers:
            # Rate limit notifications per entity
            last_notified = self._last_notified_time.get(
                tracker.entity_id, datetime.datetime.min
            )
            if datetime.datetime.now() - last_notified <= datetime.timedelta(hours=1):
                continue

            message_lines = {
                "Hostname": tracker.hostname,
                "OUI": self._oui_lookup.identify(tracker.mac),
                "IP": tracker.ip,
                "MAC": tracker.mac,
            }
            if tracker.mac is None:
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
            self._device_registry.save(on_fail=self._on_save_fail)

    def _on_save_fail(self):
        self.notify_phone(
            title="Failed to save WiFi device registry",
            message="New data is smaller than old data.",
        )