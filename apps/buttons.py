"""Handle simple button presses to remove duplication in HA automations."""

import re
from typing import Any, Dict

import appdaemon.plugins.hass.hassapi as hass  # type: ignore

import zha_buttons
import default_scene_service


class Buttons(hass.Hass):
    def initialize(self):
        self.listen_event(event=zha_buttons.EVENT_TYPE, callback=self._button_press)

    def _button_press(self, _event_name: str, data: Dict[str, Any], _kwargs: Any):
        info = zha_buttons.button_click_from_event_kwargs(data)
        self.log(info)
        if info is None:
            return
        (device, button, press) = info

        if device.name == "remote_control":
            if button == "right":
                self.call_service(service="switch/toggle", entity_id="switch.table_light")
            elif button == "left":
                self.call_service(service="switch/toggle", entity_id="switch.daisy_chain")
            elif button == "bottom":
                self.call_service(service="light/turn_off", area_id="living_room")
            else:
                self.fire_event(event=default_scene_service.EVENT_NAME, rooms=["living_room"])
        elif device.name.endswith("dimmer"):
            room_match = re.match(r"(.*)_dimmer", device.name)
            if room_match is None:
                return
            room = room_match[1]
            self.log(room)
            if button == "top":
                self.fire_event(event=default_scene_service.EVENT_NAME, rooms=[room])
            else:
                self.call_service(service="light/turn_off", area_id=room)
