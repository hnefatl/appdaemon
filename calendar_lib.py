import datetime

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# https://developers.google.com/calendar/auth
SCOPES = ['https://www.googleapis.com/auth/calendar.events.readonly']
CREDS_FILE = '/config/secrets/google-calendar.json'
TOKEN_FILE = '/config/secrets/google-calendar-token.json'

###
# The authentication process SUCKS: creds file lets you get short-lived access
# tokens, but there's almost no docs on that + especially no docs on how to
# do that from a headless system.
# This is nonfunctional atm.
###

def get_client():
  try:
    token = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
  except FileNotFoundError:
    token = None
  if not token or not token.valid:
    if token and token.expired and token.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
      token = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open(TOKEN_FILE, 'w') as token_file:
      token_file.write(token.to_json())
  return build('calendar', 'v3', credentials=token)

class OnCalendarEvent:
  def __init__(self, client, on_event):
    self._client = client
    self._on_event = on_event

  async def start(self):
    while True:
      now = datetime.datetime.utcnow().isoformat() + 'Z'
      next_events = service.events().list(calendarId='primary', timeMin=now,
                                          maxResults=10, singleEvents=True,
                                          orderBy='startTime').execute()
      events = next_events.get('items', [])
      for event in events:
        #start_time = datetime.event.get('start', {}).get('dateTime', None)
        #if not start_time:
        #  continue

        #start_time = datetime.strptime(start_time, '%Y-%m-%dT%H:%M:%S.%f')
        #time_delta = datetime.datetime.now
        self.on_event(event)
