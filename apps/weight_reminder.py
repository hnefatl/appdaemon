from typing import Any

from whenever import SystemDateTime, TimeDelta, days

import typed_hass
from typed_hass import MediaPlayer, InputBoolean, BinarySensor

BEDROOM_SENSORS = [
    BinarySensor("bedroom_motion_occupancy"),
    BinarySensor("bedroom_entrance_motion_occupancy"),
]
SHOWER_ACTIVE = InputBoolean("shower_active")


def _next_morning(d: SystemDateTime) -> SystemDateTime:
    return d.replace(hour=5) + days(1)


class WeightReminder(typed_hass.Hass):
    def initialize(self):
        # Last activation. Default to as old as possible.
        self._last_shower_on: SystemDateTime | None = None
        self._last_reminder = SystemDateTime.from_timestamp(0)

        for bedroom_sensor in BEDROOM_SENSORS:
            self.listen_state(callback=self.bedroom_motion, entity_id=bedroom_sensor)
        self.listen_state(callback=self.shower_on, new="on", entity_id=SHOWER_ACTIVE)

    def shower_on(self, *_: Any):
        self._last_shower_on = SystemDateTime.now()

    def bedroom_motion(self, *_: Any):
        # If shower hasn't been used since initialisation (e.g. I'm tinkering with appdaemon),
        # then don't trigger spuriously.
        if self._last_shower_on is None:
            return

        now = SystemDateTime.now()
        recent_after_shower = now < self._last_shower_on + TimeDelta(minutes=60)
        havent_reminded_today = now >= _next_morning(self._last_reminder)
        if recent_after_shower and havent_reminded_today:
            self._last_reminder = now
            self.info_log("Weight reminder triggered")
            self.run_in(
                after_seconds=15,
                callback=lambda _: self.tts_speak(
                    message="Weigh yourself.",
                    media_player=MediaPlayer("bedroom_speaker"),
                ),
            )
