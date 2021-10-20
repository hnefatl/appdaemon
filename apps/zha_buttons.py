from __future__ import annotations
import abc
import enum
from typing import Any, Dict, Tuple, Optional

import appdaemon.plugins.hass.hassapi as hass  # type: ignore

EVENT_TYPE = "zha_button_press"


ButtonName = str


class ButtonPress(enum.Enum):
    SINGLE = enum.auto()
    HOLD = enum.auto()


class Button(abc.ABC):
    def __init__(self, name: str):
        self.name = name

    @abc.abstractmethod
    def get_press_info(self, command: str, args: Tuple[int, ...]) -> Optional[Tuple[ButtonName, ButtonPress]]:
        pass


def button_click_to_event_kwargs(device: Button, button: ButtonName, press: ButtonPress) -> Optional[Dict[str, str]]:
    return {"device": device.name, "button": button, "press": press.name.lower()}


def button_click_from_event_kwargs(kwargs: Dict[str, str]) -> Optional[Tuple[Button, ButtonName, ButtonPress]]:
    device_name = kwargs.get("device")
    button = kwargs.get("button")
    press_name = kwargs.get("press")
    if device_name is None or button is None or press_name is None:
        return None

    press = next((press for press in ButtonPress if press.name == press_name.upper()), None)
    device = next((device for device in DEVICE_MAPPING.values() if device.name == device_name), None)
    if press is None or device is None:
        return None
    return (device, button, press)


class IkeaRemote(Button):
    ARGS_BUTTON_MAPPING = {
        (): "centre",
        (0, 43, 5): "top",
        (0, 84): "top",
        (1, 43, 5): "bottom",
        (1, 84): "bottom",
        (257, 13, 0): "left",
        (3329, 0): "left",
        (256, 13, 0): "right",
        (3328, 0): "right",
    }
    COMMAND_PRESS_MAPPING = {
        "toggle": ButtonPress.SINGLE,  # centre button
        "press": ButtonPress.SINGLE,  # left and right buttons
        "step_with_on_off": ButtonPress.SINGLE,  # top button
        "step": ButtonPress.SINGLE,  # top button
        "move_with_on_off": ButtonPress.HOLD,  # bottom button
        "move": ButtonPress.HOLD,  # bottom button
        "hold": ButtonPress.HOLD,  # left and right buttons
    }

    def get_press_info(self, command: str, args: Tuple[int, ...]) -> Optional[Tuple[ButtonName, ButtonPress]]:
        button = self.ARGS_BUTTON_MAPPING.get(tuple(args))
        if button is None:
            return None
        press = self.COMMAND_PRESS_MAPPING.get(command)
        if press is None:
            return None
        return (button, press)


class IkeaDimmer(Button):
    def get_press_info(self, command: str, args: Tuple[int, ...]) -> Optional[Tuple[ButtonName, ButtonPress]]:
        return {
            ("on", ()): ("top", ButtonPress.SINGLE),
            ("off", ()): ("bottom", ButtonPress.SINGLE),
            ("move_with_on_off", (0, 83)): ("top", ButtonPress.HOLD),
            ("move", (1, 83)): ("bottom", ButtonPress.HOLD),
        }.get((command, args))


DEVICE_MAPPING: Dict[str, Button] = {
    "406a8b92e13d77d79941d59e37f03211": IkeaRemote("remote_control"),
    "132631a4a3ccafe42b642066622f70ca": IkeaDimmer("living_room_dimmer"),
    "08a5b2fcc6bab34e04c26f24b04ba75f": IkeaDimmer("bedroom_dimmer"),
}


class ZhaButtonEvents(hass.Hass):
    def initialize(self):
        self.listen_event(callback=self._on_zha_event, event="zha_event")

    def _on_zha_event(self, _event_name: str, data: Dict[str, Any], _kwargs: Dict[str, Any]):
        self.log(data)

        device_id = data.get("device_id")
        if device_id is None or not isinstance(device_id, str):
            self.log(f"Unknown device: {device_id}")
            return
        device = DEVICE_MAPPING.get(device_id)
        if device is None:
            self.log(f"Unknown device id->device: {device_id}")
            return

        command = data.get("command")
        if command is None or not isinstance(command, str):
            self.log(f"Invalid command: {command}")
            return
        args = data.get("args")
        if args is None or not isinstance(args, list):
            self.log(f"Invalid args: {args}")
            return

        result = device.get_press_info(command, tuple(args))
        if result is None:
            return None
        (button, press) = result

        self.log(f"{press} on {device.name} {button}")
        self.fire_event(EVENT_TYPE, **button_click_to_event_kwargs(device, button, press))
