from typing import Any

from whenever import SystemDateTime, TimeDelta

import typed_hass
from typed_hass import EntityId

BEDROOM_SENSORS = [
    EntityId("binary_sensor.bedroom_motion_occupancy"),
    EntityId("binary_sensor.bedroom_entrance_motion_occupancy"),
]
SHOWER_ACTIVE = EntityId("input_boolean.shower_active")


class WeightReminder(typed_hass.Hass):
    def initialize(self):
        # Last activation. Default to as old as possible.
        self._last_shower_on = SystemDateTime.from_timestamp(0)
        self._last_reminder = SystemDateTime.from_timestamp(0)

        for bedroom_sensor in BEDROOM_SENSORS:
            self.listen_state(callback=self.bedroom_motion, entity_id=bedroom_sensor)
        self.listen_state(callback=self.shower_on, entity_id=SHOWER_ACTIVE)

    def bedroom_motion(self, *_: Any):
        now = SystemDateTime.now()

        recent_after_shower = now < self._last_shower_on + TimeDelta(minutes=60)
        havent_reminded_today = self._last_reminder.date() < now.date()
        if recent_after_shower and havent_reminded_today:
            self._last_reminder = now
            self.tts_speak(
                message="Weigh yourself.",
                media_player=EntityId("media_player.bedroom_speaker"),
            )

    def shower_on(self, *_: Any):
        self._last_shower_on = SystemDateTime.now()
