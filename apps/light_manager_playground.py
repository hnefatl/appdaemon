import asyncio
from typing import AsyncIterator, Tuple

import appdaemon.plugins.hass.hassapi as hass  # type: ignore
import light_manager


class LightManagerPlayground(hass.Hass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._light_manager = light_manager.LightManager(self)

    # def initialize(self):
    #    self.log("Starting light manager playground")

    #    # Test that locks work correctly
    #    # self.create_task(self._flash_async_test())
    #    # Test scene loads
    #    self.create_task(self._scene_load_test("living_room_dim"))

    async def initialize(self):
        self.log("Starting light manager playground")
        await self._scene_load_test("living_room_dim")

    async def _flash_async_test(self):
        light_id = light_manager.LightId("light.living_room_2")

        async def _flash(colour: Tuple[int, int, int]):
            async with self._light_manager.open_session(light_manager.Room.LIVING_ROOM, restore_lights=False):
                self.log(f"Setting {colour}")
                await self.turn_on(entity_id=light_id, rgb_color=list(colour))
                await self.sleep(2)

        tasks = []
        for _ in range(5):
            for colour in [(255, 0, 0), (0, 255, 0), (0, 255, 255)]:
                tasks.append(_flash(colour))
        await asyncio.wait(tasks)

    async def _scene_load_test(self, scene_name: str):
        async with self._light_manager.open_session(light_manager.Room.LIVING_ROOM, restore_lights=True) as session:
            # await session.load_scene(scene_name)
            await self.sleep(5)
