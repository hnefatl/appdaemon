from gcsa.google_calendar import GoogleCalendar
import datetime

import appdaemon.plugins.hass.hassapi as hass


EVENT_LOOKAHEAD = datetime.timedelta()


class CalendarEvents(hass.Hass):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._calendar = None

  def initialize(self):
    self._calendar = GoogleCalendar(
      self.args.get('calendar_email'),
      credentials_path='/config/secrets/calendar_credentials.json',
      token_path='/config/secrets/calendar_token.pickle')

    self.log('To bootstrap, run:')
    self.log('from gcsa.google_calendar import GoogleCalendar')
    self.log(f"GoogleCalendar('{self.args.get('calendar_email')}', " +
    "credentials_path='credentials.json', token_path='token.pickle')")

  async def _wait_until_next_event():
    #upcoming_events = calendar.get_events(start_date, end_date, order_by='startTime', single_events=True)
    pass
