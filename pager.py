import appdaemon.plugins.hass.hassapi as hass
import base64
import re

IMAP_SENSOR = 'sensor.imap_hnefatl'
# Minor obfuscation to hide google service from scrapers
PAGER_SERVICE_REGEX = base64.b64decode('LipAYWNrXC5tb25pdG9yaW5nXC5nb29nbGVcLmNvbSQ=').decode()
LIGHT_FLASH_COUNT = 3

class Pager(hass.Hass):
  def initialize(self):
    self.log('Starting Pager service')
    self.log(f'Using pager service regex: "{PAGER_SERVICE_REGEX}"')
    self.listen_state(
      entity=IMAP_SENSOR, attribute='all', callback=self.on_email)

  async def on_email(self, _entity, _attribute, state_info, *_):
    self.log(f'Email received: {state_info}')
    attributes = state_info.get('attributes', {})
    sender = attributes.get('from')
    self.log(f'Email from: {sender}')
    if not sender or not re.match(PAGER_SERVICE_REGEX, sender):
      self.log('Not a page')
      return

    bedroom_light_on = await self.get_state('group.bedroom_lights') == 'on'

    self.log(f'Confirmed page, subject: {attributes.get("subject")}')
    for i in range(LIGHT_FLASH_COUNT):
      self.call_service('scene/turn_on', entity_id='scene.bedroom_red')
      self.call_service('scene/turn_on', entity_id='scene.office_red')
      await self.sleep(1)
      self.call_service('scene/turn_on', entity_id='scene.bedroom_dim')
      self.call_service('scene/turn_on', entity_id='scene.office_concentrate')
      await self.sleep(1)

    if not bedroom_light_on:
      await self.call_service('light/turn_off', entity_id='group.bedroom_lights')