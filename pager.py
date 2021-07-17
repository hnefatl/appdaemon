import asyncio
import base64
import re

import appdaemon.plugins.hass.hassapi as hass

IMAP_SENSOR = 'sensor.imap_hnefatl_pager'
LIGHT_FLASH_COUNT = 3

class Pager(hass.Hass):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._lock = asyncio.Lock()

  def initialize(self):
    self.log('Starting Pager service')
    self.listen_state(
      entity=IMAP_SENSOR, attribute='all', callback=self.on_email)

  async def on_email(self, _entity, _attribute, state_info, *_):
    self.log(f'Email received: {state_info}')
    attributes = state_info.get('attributes', {})
    sender = attributes.get('from')
    self.log(f'Email from: {sender}')

    self.log(f'Confirmed page, subject: {attributes.get("subject")}')
    await self.red_alert()

  # Renamed in honour of Maximus
  async def red_alert(self):
    async with self._lock:
      bedroom_light_on = await self.get_state('group.bedroom_lights') == 'on'

      for i in range(LIGHT_FLASH_COUNT):
        self.call_service('scene/turn_on', entity_id='scene.bedroom_red')
        self.call_service('scene/turn_on', entity_id='scene.office_red')
        await self.sleep(1)
        self.call_service('scene/turn_on', entity_id='scene.bedroom_dim')
        self.call_service('scene/turn_on', entity_id='scene.office_concentrate')
        await self.sleep(1)

      if not bedroom_light_on:
        await self.call_service('light/turn_off', entity_id='group.bedroom_lights')