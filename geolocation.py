import appdaemon.plugins.hass.hassapi as hass
import json
from typing import List

# Time to wait before turning off lights
AWAY_DURATION = 30 * 60
ENTITY = "person.keith"


class Geolocation(hass.Hass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._timer_handler = None

    def initialize(self):
        self.log("Starting geolocation service")
        self.listen_state(entity=ENTITY, callback=self.on_zone_change)

    def on_zone_change(self, entity, attribute, old, new, kwargs):
        self.log(f"{entity} changed zone: was {old}, now {new} ({kwargs})")
        if new == "not_home" and self._timer_handler is None:
            self.log("Starting away timer")
            self._timer_handler = self.run_in(delay=AWAY_DURATION, callback=self.double_check_away)
        elif new == "home":
            if self._timer_handler is not None:
                self.log("Cancelling away timer")
                self.cancel_timer(self._timer_handler)
                self._timer_handler = None
            # TODO: restore lights to normal, should probably write a dedicated light
            # service for maintaining state and preventing stomping etc.

    def double_check_away(self, kwargs):
        current_state = self.get_state(entity_id=ENTITY)
        self.log(f"{ENTITY} current state: {current_state}")
        if current_state != "home":
            self.call_service("light/turn_off", entity_id="group.all_lights")
