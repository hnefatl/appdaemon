from __future__ import annotations

import appdaemon.plugins.hass.hassapi as hass  # type: ignore
import abc
import asyncio
import enum
from typing import (
    Callable,
    DefaultDict,
    Generic,
    Hashable,
    List,
    Optional,
    Mapping,
    Set,
    Tuple,
    TypeVar,
)


class ButtonPress(enum.Enum):
    SINGLE = 1
    HOLD = 2


# Identifies a single physical Button on a ButtonDevice. Some buttons have
# multiple ids (e.g. on the IKEA remote, there's different numbers for a button
# being tapped or held), so this has to be something generic and we need to
# treat it flexibly.
ButtonType = TypeVar("ButtonType", bound=Button)
ButtonDataType = TypeVar("ButtonDataType")
ButtonPressCallback = Callable[[ButtonPress], None]


class ButtonDevice(abc.ABC, Generic[ButtonType, ButtonDataType]):
    """A device with one or more buttons."""

    def __init__(self, hassio: hass.Hass, name: Optional[str]):
        self._hass = hassio
        self._listeners: DefaultDict[ButtonType, list[ButtonPressCallback]] = DefaultDict(list)
        self._listeners_lock = asyncio.Lock()
        self._name = name

    async def _on_press(self, button_data: ButtonDataType, press: ButtonPress):
        """Run all the callbacks for a press of a specific button."""
        async with self._listeners_lock:
            for button, listeners in self._listeners.items():
                if not button.matches_button_data(button_data):
                    continue
                while listeners:
                    listeners[0](press)
                    listeners.pop()

    @abc.abstractmethod
    def get_all_buttons(self) -> List[ButtonType]:
        pass

    async def _add_button_press_callback(self, button: ButtonType, callback: ButtonPressCallback):
        async with self._listeners_lock:
            self._listeners[button].append(callback)

    def __str__(self):
        return self._name if self._name else "unnamed device"


# This could probably be rewritten so that all devices share the same dumb button class, and the device itself
# implements the data->button logic. Then we'd only need to be generic in ButtonDataType and we avoid needing to define
# minor classes like ZhaButton.
class Button(abc.ABC, Generic[ButtonDataType]):
    """A single logical button on a ButtonDevice."""

    def __init__(self, name: Optional[str], button_device: ButtonDevice):
        self._name = name
        self._button_device = button_device

    async def wait_for_press(self) -> Optional[ButtonPress]:
        out = None
        event = asyncio.Event()

        def callback(press):
            nonlocal out
            out = press
            event.set()

        await self._button_device._add_button_press_callback(self, callback)
        await event.wait()
        return out

    @abc.abstractmethod
    def matches_button_data(self, button_data: ButtonDataType) -> bool:
        """Return true iff this button matches the identifying data."""
        pass

    def __str__(self):
        button_name = self._name if self._name else "unnamed button"
        return f"{button_name} on {self._button_device}"


class ZhaButton(Button[Tuple[int, ...]]):
    def __init__(self, name, button_device, zha_button_args: Set[Tuple[int, ...]]):
        super().__init__(name, button_device)
        self._zha_button_args = zha_button_args

    def matches_button_data(self, button_data: Tuple[int, ...]) -> bool:
        return button_data in self._zha_button_args


class ZhaButtonDevice(ButtonDevice[ZhaButton, Tuple[int, ...]]):
    def __init__(
        self,
        hassio: hass.Hass,
        name: Optional[str],
        device_id: str,
        command_press_mapping: Mapping[str, ButtonPress],
    ):
        super().__init__(hassio, name)
        self._command_press_mapping = command_press_mapping
        self._handle = self._hass.listen_event(event="zha_event", device_id=device_id, callback=self._callback)

    async def _callback(self, _, data, __):
        args = data.get("args")
        press = self._command_press_mapping.get(data.get("command"))
        if args is not None and press is not None:
            await self._on_press(tuple(args), press)

    def __str__(self):
        return self._name if self._name else "unnamed ZHA device"


class IkeaRemote(ZhaButtonDevice):
    def __init__(self, hassio: hass.Hass, device_id: str):
        _command_press_mapping = {
            "toggle": ButtonPress.SINGLE,  # centre button
            "press": ButtonPress.SINGLE,  # left and right buttons
            "step_with_on_off": ButtonPress.SINGLE,  # top button
            "step": ButtonPress.SINGLE,  # top button
            "move_with_on_off": ButtonPress.HOLD,  # bottom button
            "move": ButtonPress.HOLD,  # bottom button
            "hold": ButtonPress.HOLD,  # left and right buttons
        }
        super().__init__(hassio, "IKEA Remote", device_id, _command_press_mapping)

        self.centre_button = ZhaButton("Centre", self, {()})
        self.top_button = ZhaButton("Top", self, {(0, 43, 5), (0, 84)})
        self.bottom_button = ZhaButton("Bottom", self, {(1, 43, 5), (1, 84)})
        self.left_button = ZhaButton("Left", self, {(257, 13, 0), (3329, 0)})
        self.right_button = ZhaButton("Right", self, {(256, 13, 0), (3328, 0)})

    def get_all_buttons(self):
        return [self.centre_button, self.top_button, self.bottom_button, self.left_button, self.right_button]


class ButtonPlayground(hass.Hass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ikea_remote = IkeaRemote(self, "406a8b92e13d77d79941d59e37f03211")

    def initialize(self):
        self.log("Starting button playground")
        buttons = self._ikea_remote.get_all_buttons()

        async def print_when_pressed(button: Button):
            while True:
                press_type = await button.wait_for_press()
                if press_type is None:
                    continue
                readable_press = {ButtonPress.SINGLE: "pressed", ButtonPress.HOLD: "held"}.get(press_type)
                self.log(f"Button {readable_press}: {button}")

        async def main(*_, **__):
            await asyncio.wait([print_when_pressed(button) for button in buttons])

        # Don't block the initialize function.
        self.run_in(callback=main, delay=0)
