from typing import Any, Iterable, Collection

import dataclasses
import datetime
import json
import dateutil.parser
import requests
import zoneinfo

import typed_hass

TIMEZONE = zoneinfo.ZoneInfo("Europe/London")

MOCK_DATA = """{"data":{"timelines":[{"timestep":"1h","endTime":"2024-09-16T23:00:00+01:00","startTime":"2024-09-12T23:00:00+01:00","intervals":[{"startTime":"2024-09-12T23:00:00+01:00","values":{"dewPoint":5.5,"humidity":87,"precipitationIntensity":0,"precipitationProbability":0,"temperature":7.5}},{"startTime":"2024-09-13T00:00:00+01:00","values":{"dewPoint":5.38,"humidity":87,"precipitationIntensity":0,"precipitationProbability":0,"temperature":7.31}},{"startTime":"2024-09-13T01:00:00+01:00","values":{"dewPoint":5.19,"humidity":88,"precipitationIntensity":0,"precipitationProbability":0,"temperature":7.13}},{"startTime":"2024-09-13T02:00:00+01:00","values":{"dewPoint":4.88,"humidity":87,"precipitationIntensity":0,"precipitationProbability":0,"temperature":6.81}},{"startTime":"2024-09-13T03:00:00+01:00","values":{"dewPoint":4.63,"humidity":88,"precipitationIntensity":0,"precipitationProbability":0,"temperature":6.5}},{"startTime":"2024-09-13T04:00:00+01:00","values":{"dewPoint":4.38,"humidity":87,"precipitationIntensity":0,"precipitationProbability":0,"temperature":6.31}},{"startTime":"2024-09-13T05:00:00+01:00","values":{"dewPoint":4.13,"humidity":87,"precipitationIntensity":0,"precipitationProbability":0,"temperature":6.13}},{"startTime":"2024-09-13T06:00:00+01:00","values":{"dewPoint":3.88,"humidity":88,"precipitationIntensity":0,"precipitationProbability":0,"temperature":5.69}},{"startTime":"2024-09-13T07:00:00+01:00","values":{"dewPoint":3.81,"humidity":88,"precipitationIntensity":0,"precipitationProbability":0,"temperature":5.63}},{"startTime":"2024-09-13T08:00:00+01:00","values":{"dewPoint":4.88,"humidity":84,"precipitationIntensity":0,"precipitationProbability":0,"temperature":7.5}},{"startTime":"2024-09-13T09:00:00+01:00","values":{"dewPoint":5.69,"humidity":77,"precipitationIntensity":0,"precipitationProbability":0,"temperature":9.63}},{"startTime":"2024-09-13T10:00:00+01:00","values":{"dewPoint":6,"humidity":67,"precipitationIntensity":0,"precipitationProbability":0,"temperature":11.88}},{"startTime":"2024-09-13T11:00:00+01:00","values":{"dewPoint":4.69,"humidity":56,"precipitationIntensity":0,"precipitationProbability":0,"temperature":13.38}},{"startTime":"2024-09-13T12:00:00+01:00","values":{"dewPoint":4,"humidity":50,"precipitationIntensity":0,"precipitationProbability":0,"temperature":14.31}},{"startTime":"2024-09-13T13:00:00+01:00","values":{"dewPoint":3.88,"humidity":48,"precipitationIntensity":0,"precipitationProbability":0,"temperature":15}},{"startTime":"2024-09-13T14:00:00+01:00","values":{"dewPoint":3.5,"humidity":44,"precipitationIntensity":0,"precipitationProbability":0,"temperature":15.63}},{"startTime":"2024-09-13T15:00:00+01:00","values":{"dewPoint":3.31,"humidity":44,"precipitationIntensity":0,"precipitationProbability":0,"temperature":15.63}},{"startTime":"2024-09-13T16:00:00+01:00","values":{"dewPoint":3.19,"humidity":43,"precipitationIntensity":0,"precipitationProbability":0,"temperature":15.63}},{"startTime":"2024-09-13T17:00:00+01:00","values":{"dewPoint":3.31,"humidity":45,"precipitationIntensity":0,"precipitationProbability":0,"temperature":15.19}},{"startTime":"2024-09-13T18:00:00+01:00","values":{"dewPoint":4,"humidity":49,"precipitationIntensity":0,"precipitationProbability":0,"temperature":14.69}},{"startTime":"2024-09-13T19:00:00+01:00","values":{"dewPoint":6.63,"humidity":65,"precipitationIntensity":0,"precipitationProbability":0,"temperature":13}},{"startTime":"2024-09-13T20:00:00+01:00","values":{"dewPoint":4.5,"humidity":54,"precipitationIntensity":0,"precipitationProbability":0,"temperature":13.5}},{"startTime":"2024-09-13T21:00:00+01:00","values":{"dewPoint":5.13,"humidity":61,"precipitationIntensity":0,"precipitationProbability":0,"temperature":12.5}},{"startTime":"2024-09-13T22:00:00+01:00","values":{"dewPoint":5.63,"humidity":70,"precipitationIntensity":0,"precipitationProbability":0,"temperature":10.81}},{"startTime":"2024-09-13T23:00:00+01:00","values":{"dewPoint":5.31,"humidity":76,"precipitationIntensity":0,"precipitationProbability":0,"temperature":9.38}},{"startTime":"2024-09-14T00:00:00+01:00","values":{"dewPoint":5.09,"humidity":83.63,"precipitationIntensity":0,"precipitationProbability":0,"temperature":7.68}},{"startTime":"2024-09-14T01:00:00+01:00","values":{"dewPoint":4.99,"humidity":85.97,"precipitationIntensity":0,"precipitationProbability":0,"temperature":7.18}},{"startTime":"2024-09-14T02:00:00+01:00","values":{"dewPoint":5.01,"humidity":87.46,"precipitationIntensity":0,"precipitationProbability":0,"temperature":6.95}},{"startTime":"2024-09-14T03:00:00+01:00","values":{"dewPoint":5.04,"humidity":90.91,"precipitationIntensity":0,"precipitationProbability":0,"temperature":6.41}},{"startTime":"2024-09-14T04:00:00+01:00","values":{"dewPoint":4.95,"humidity":93.09,"precipitationIntensity":0,"precipitationProbability":0,"temperature":5.98}},{"startTime":"2024-09-14T05:00:00+01:00","values":{"dewPoint":4.98,"humidity":93.49,"precipitationIntensity":0,"precipitationProbability":0,"temperature":5.95}},{"startTime":"2024-09-14T06:00:00+01:00","values":{"dewPoint":4.54,"humidity":94.9,"precipitationIntensity":0,"precipitationProbability":0,"temperature":5.29}},{"startTime":"2024-09-14T07:00:00+01:00","values":{"dewPoint":5.09,"humidity":94.31,"precipitationIntensity":0,"precipitationProbability":0,"temperature":5.93}},{"startTime":"2024-09-14T08:00:00+01:00","values":{"dewPoint":5.93,"humidity":85.71,"precipitationIntensity":0,"precipitationProbability":0,"temperature":8.18}},{"startTime":"2024-09-14T09:00:00+01:00","values":{"dewPoint":7.13,"humidity":77.96,"precipitationIntensity":0,"precipitationProbability":0,"temperature":10.82}},{"startTime":"2024-09-14T10:00:00+01:00","values":{"dewPoint":7.23,"humidity":66.69,"precipitationIntensity":0,"precipitationProbability":0,"temperature":13.29}},{"startTime":"2024-09-14T11:00:00+01:00","values":{"dewPoint":7.09,"humidity":59.27,"precipitationIntensity":0,"precipitationProbability":0,"temperature":14.96}},{"startTime":"2024-09-14T12:00:00+01:00","values":{"dewPoint":6.95,"humidity":54.34,"precipitationIntensity":0,"precipitationProbability":0,"temperature":16.17}},{"startTime":"2024-09-14T13:00:00+01:00","values":{"dewPoint":7.05,"humidity":51.84,"precipitationIntensity":0,"precipitationProbability":0,"temperature":17.02}},{"startTime":"2024-09-14T14:00:00+01:00","values":{"dewPoint":6.7,"humidity":48,"precipitationIntensity":0,"precipitationProbability":0,"temperature":17.86}},{"startTime":"2024-09-14T15:00:00+01:00","values":{"dewPoint":6.75,"humidity":46.99,"precipitationIntensity":0,"precipitationProbability":0,"temperature":18.25}},{"startTime":"2024-09-14T16:00:00+01:00","values":{"dewPoint":7.31,"humidity":47.89,"precipitationIntensity":0,"precipitationProbability":0,"temperature":18.56}},{"startTime":"2024-09-14T17:00:00+01:00","values":{"dewPoint":7.94,"humidity":53.85,"precipitationIntensity":0,"precipitationProbability":0,"temperature":17.38}},{"startTime":"2024-09-14T18:00:00+01:00","values":{"dewPoint":8.44,"humidity":59.36,"precipitationIntensity":0,"precipitationProbability":0,"temperature":16.38}},{"startTime":"2024-09-14T19:00:00+01:00","values":{"dewPoint":8.56,"humidity":65.11,"precipitationIntensity":0,"precipitationProbability":0,"temperature":15.06}},{"startTime":"2024-09-14T20:00:00+01:00","values":{"dewPoint":8.44,"humidity":71.58,"precipitationIntensity":0,"precipitationProbability":0,"temperature":13.47}},{"startTime":"2024-09-14T21:00:00+01:00","values":{"dewPoint":8.33,"humidity":75.16,"precipitationIntensity":0,"precipitationProbability":0,"temperature":12.61}},{"startTime":"2024-09-14T22:00:00+01:00","values":{"dewPoint":8.14,"humidity":77.8,"precipitationIntensity":0,"precipitationProbability":0,"temperature":11.89}},{"startTime":"2024-09-14T23:00:00+01:00","values":{"dewPoint":7.84,"humidity":80.53,"precipitationIntensity":0,"precipitationProbability":0,"temperature":11.05}},{"startTime":"2024-09-15T00:00:00+01:00","values":{"dewPoint":7.49,"humidity":82.18,"precipitationIntensity":0,"precipitationProbability":0,"temperature":10.4}},{"startTime":"2024-09-15T01:00:00+01:00","values":{"dewPoint":7.41,"humidity":86.04,"precipitationIntensity":0,"precipitationProbability":0,"temperature":9.63}},{"startTime":"2024-09-15T02:00:00+01:00","values":{"dewPoint":7.36,"humidity":90.31,"precipitationIntensity":0,"precipitationProbability":0,"temperature":8.86}},{"startTime":"2024-09-15T03:00:00+01:00","values":{"dewPoint":7.33,"humidity":92.04,"precipitationIntensity":0,"precipitationProbability":0,"temperature":8.55}},{"startTime":"2024-09-15T04:00:00+01:00","values":{"dewPoint":7.42,"humidity":92.63,"precipitationIntensity":0,"precipitationProbability":0,"temperature":8.54}},{"startTime":"2024-09-15T05:00:00+01:00","values":{"dewPoint":7.41,"humidity":93.22,"precipitationIntensity":0,"precipitationProbability":0,"temperature":8.44}},{"startTime":"2024-09-15T06:00:00+01:00","values":{"dewPoint":7.36,"humidity":93.81,"precipitationIntensity":0,"precipitationProbability":0,"temperature":8.3}},{"startTime":"2024-09-15T07:00:00+01:00","values":{"dewPoint":7.46,"humidity":94.22,"precipitationIntensity":0,"precipitationProbability":0,"temperature":8.34}},{"startTime":"2024-09-15T08:00:00+01:00","values":{"dewPoint":8.43,"humidity":88.51,"precipitationIntensity":0,"precipitationProbability":0,"temperature":10.25}},{"startTime":"2024-09-15T09:00:00+01:00","values":{"dewPoint":9.4,"humidity":80.92,"precipitationIntensity":0,"precipitationProbability":0,"temperature":12.58}},{"startTime":"2024-09-15T10:00:00+01:00","values":{"dewPoint":10.16,"humidity":73.07,"precipitationIntensity":0,"precipitationProbability":0,"temperature":14.94}},{"startTime":"2024-09-15T11:00:00+01:00","values":{"dewPoint":9.66,"humidity":63.3,"precipitationIntensity":0,"precipitationProbability":0,"temperature":16.66}},{"startTime":"2024-09-15T12:00:00+01:00","values":{"dewPoint":9.83,"humidity":60.05,"precipitationIntensity":0,"precipitationProbability":0,"temperature":17.67}},{"startTime":"2024-09-15T13:00:00+01:00","values":{"dewPoint":9.88,"humidity":57.98,"precipitationIntensity":0,"precipitationProbability":0,"temperature":18.29}},{"startTime":"2024-09-15T14:00:00+01:00","values":{"dewPoint":10.01,"humidity":55.79,"precipitationIntensity":0,"precipitationProbability":0,"temperature":19.05}},{"startTime":"2024-09-15T15:00:00+01:00","values":{"dewPoint":10.27,"humidity":55.31,"precipitationIntensity":0,"precipitationProbability":0,"temperature":19.46}},{"startTime":"2024-09-15T16:00:00+01:00","values":{"dewPoint":10.31,"humidity":56.74,"precipitationIntensity":0,"precipitationProbability":0,"temperature":19.09}},{"startTime":"2024-09-15T17:00:00+01:00","values":{"dewPoint":10.17,"humidity":57.71,"precipitationIntensity":0,"precipitationProbability":0,"temperature":18.67}},{"startTime":"2024-09-15T18:00:00+01:00","values":{"dewPoint":10.38,"humidity":61.26,"precipitationIntensity":0,"precipitationProbability":0,"temperature":17.94}},{"startTime":"2024-09-15T19:00:00+01:00","values":{"dewPoint":10.82,"humidity":70.32,"precipitationIntensity":0.23,"precipitationProbability":5,"temperature":16.22}},{"startTime":"2024-09-15T20:00:00+01:00","values":{"dewPoint":11.54,"humidity":79.75,"precipitationIntensity":0,"precipitationProbability":0,"temperature":15.01}},{"startTime":"2024-09-15T21:00:00+01:00","values":{"dewPoint":11.56,"humidity":79.75,"precipitationIntensity":0.04,"precipitationProbability":5,"temperature":15.03}},{"startTime":"2024-09-15T22:00:00+01:00","values":{"dewPoint":11.84,"humidity":82.07,"precipitationIntensity":0,"precipitationProbability":0,"temperature":14.87}},{"startTime":"2024-09-15T23:00:00+01:00","values":{"dewPoint":11.95,"humidity":85.29,"precipitationIntensity":0.1,"precipitationProbability":5,"temperature":14.39}},{"startTime":"2024-09-16T00:00:00+01:00","values":{"dewPoint":12.15,"humidity":86.7,"precipitationIntensity":0,"precipitationProbability":0,"temperature":14.33}},{"startTime":"2024-09-16T01:00:00+01:00","values":{"dewPoint":12.27,"humidity":88.12,"precipitationIntensity":0,"precipitationProbability":0,"temperature":14.21}},{"startTime":"2024-09-16T02:00:00+01:00","values":{"dewPoint":12.44,"humidity":89.03,"precipitationIntensity":0,"precipitationProbability":0,"temperature":14.22}},{"startTime":"2024-09-16T03:00:00+01:00","values":{"dewPoint":12.61,"humidity":89.59,"precipitationIntensity":0.01,"precipitationProbability":5,"temperature":14.3}},{"startTime":"2024-09-16T04:00:00+01:00","values":{"dewPoint":12.48,"humidity":93.86,"precipitationIntensity":0,"precipitationProbability":0,"temperature":13.45}},{"startTime":"2024-09-16T05:00:00+01:00","values":{"dewPoint":11.79,"humidity":94.6,"precipitationIntensity":0,"precipitationProbability":0,"temperature":12.63}},{"startTime":"2024-09-16T06:00:00+01:00","values":{"dewPoint":11.06,"humidity":94.76,"precipitationIntensity":0,"precipitationProbability":0,"temperature":11.88}},{"startTime":"2024-09-16T07:00:00+01:00","values":{"dewPoint":10.08,"humidity":95.52,"precipitationIntensity":0,"precipitationProbability":0,"temperature":10.77}},{"startTime":"2024-09-16T08:00:00+01:00","values":{"dewPoint":10.55,"humidity":91.66,"precipitationIntensity":0,"precipitationProbability":0,"temperature":11.86}},{"startTime":"2024-09-16T09:00:00+01:00","values":{"dewPoint":10.85,"humidity":85.17,"precipitationIntensity":0,"precipitationProbability":0,"temperature":13.29}},{"startTime":"2024-09-16T10:00:00+01:00","values":{"dewPoint":11.57,"humidity":79.91,"precipitationIntensity":0,"precipitationProbability":0,"temperature":15.01}},{"startTime":"2024-09-16T11:00:00+01:00","values":{"dewPoint":12.05,"humidity":74.44,"precipitationIntensity":0,"precipitationProbability":0,"temperature":16.61}},{"startTime":"2024-09-16T12:00:00+01:00","values":{"dewPoint":11.28,"humidity":64.05,"precipitationIntensity":0,"precipitationProbability":0,"temperature":18.19}},{"startTime":"2024-09-16T13:00:00+01:00","values":{"dewPoint":10.24,"humidity":55.52,"precipitationIntensity":0,"precipitationProbability":0,"temperature":19.37}},{"startTime":"2024-09-16T14:00:00+01:00","values":{"dewPoint":9.44,"humidity":50.67,"precipitationIntensity":0,"precipitationProbability":0,"temperature":19.97}},{"startTime":"2024-09-16T15:00:00+01:00","values":{"dewPoint":8.74,"humidity":47.63,"precipitationIntensity":0,"precipitationProbability":0,"temperature":20.2}},{"startTime":"2024-09-16T16:00:00+01:00","values":{"dewPoint":8.91,"humidity":48.33,"precipitationIntensity":0,"precipitationProbability":0,"temperature":20.16}},{"startTime":"2024-09-16T17:00:00+01:00","values":{"dewPoint":8.65,"humidity":48.35,"precipitationIntensity":0,"precipitationProbability":0,"temperature":19.87}},{"startTime":"2024-09-16T18:00:00+01:00","values":{"dewPoint":9.53,"humidity":55.01,"precipitationIntensity":0,"precipitationProbability":0,"temperature":18.75}},{"startTime":"2024-09-16T19:00:00+01:00","values":{"dewPoint":9.63,"humidity":63.68,"precipitationIntensity":0,"precipitationProbability":0,"temperature":16.53}},{"startTime":"2024-09-16T20:00:00+01:00","values":{"dewPoint":9.48,"humidity":69.36,"precipitationIntensity":0,"precipitationProbability":0,"temperature":15.04}},{"startTime":"2024-09-16T21:00:00+01:00","values":{"dewPoint":10.2,"humidity":79.26,"precipitationIntensity":0,"precipitationProbability":0,"temperature":13.73}},{"startTime":"2024-09-16T22:00:00+01:00","values":{"dewPoint":10.51,"humidity":83.51,"precipitationIntensity":0,"precipitationProbability":0,"temperature":13.24}},{"startTime":"2024-09-16T23:00:00+01:00","values":{"dewPoint":10.31,"humidity":84.11,"precipitationIntensity":0,"precipitationProbability":0,"temperature":12.93}}]}]}}"""


def mean(xs: Collection[float]) -> float:
    return sum(xs) / len(xs)


@dataclasses.dataclass(frozen=True)
class ForecastSnapshot:
    precipitation_probability: float | None
    precipitation_intensity: float | None
    temperature: float | None
    humidity: float | None
    dew_point: float | None
    uv_index: float | None


class Forecast:
    def __init__(self, data: str):
        self.days = dict[datetime.date, dict[datetime.time, ForecastSnapshot]]()

        for timeline in json.loads(data)["data"]["timelines"][0]["intervals"]:
            time = dateutil.parser.parse(timeline["startTime"]).astimezone(TIMEZONE)

            if time.date() not in self.days:
                self.days[time.date()] = {}
            self.days[time.date()][datetime.time(hour=time.hour)] = ForecastSnapshot(
                precipitation_probability=timeline["values"].get(
                    "precipitationProbability"
                ),
                precipitation_intensity=timeline["values"].get(
                    "precipitationIntensity"
                ),
                temperature=timeline["values"].get("temperature"),
                humidity=timeline["values"].get("humidity"),
                dew_point=timeline["values"].get("dewPoint"),
                uv_index=timeline["values"].get("uvIndex"),
            )

    def _get_value(self, field: str, day_delta: int, hour: int) -> float | None:
        key = datetime.date.today() + datetime.timedelta(days=day_delta)
        return getattr(self.days.get(key), field)

    def _get_values(
        self, field: str, hours: Iterable[int], day_delta: int = 0
    ) -> list[float]:
        day = datetime.date.today() + datetime.timedelta(days=day_delta)
        return [
            val
            for i in hours
            if (val := getattr(self.days[day].get(datetime.time(hour=i)), field, None))
        ]

    def precipitation_probability(self, hour: int, day_delta: int = 0) -> float | None:
        return self._get_value("precipitation_probability", hour, day_delta)

    def precipitation_intensity(self, hour: int, day_delta: int = 0) -> float | None:
        return self._get_value("precipitation_intensity", hour, day_delta)

    def temperature(self, hour: int, day_delta: int = 0) -> float | None:
        return self._get_value("temperature", hour, day_delta)

    def temperatures(self, hours: Iterable[int], day_delta: int = 0) -> list[float]:
        return self._get_values("temperature", hours, day_delta)


class WakeupInfo(typed_hass.Hass):
    async def initialize(self):
        self.listen_event(event="ANNOUNCE_WEATHER", callback=self.on_event)

    async def on_event(
        self, _event_name: str, data: dict[str, Any], _user_args: dict[str, Any]
    ):
        use_mock_data = data.get("mock", False)
        result: str
        if use_mock_data:
            result = MOCK_DATA
            self.log("using mock data")
        else:
            self.log("Fetching weather")
            response = requests.post(
                url="https://api.tomorrow.io/v4/timelines",
                params={"apikey": self.args.get("api_key")},
                # https://docs.tomorrow.io/reference/post-timelines
                json={
                    "location": self.args.get("location"),
                    "units": "metric",
                    # https://docs.tomorrow.io/reference/data-layers-core
                    "fields": [
                        "precipitationProbability",
                        "precipitationIntensity",
                        "temperature",
                        "humidity",
                        "dewPoint",
                        "uvIndex",
                    ],
                    "timesteps": ["1h"],
                    "timezone": "auto",
                    "startTime": "nowMinus1d",
                    "endTime": "nowPlus1d",
                },
            )
            self.log("Fetched weather")
            if response.status_code != 200:
                raise RuntimeError(f"{response.status_code}: {response.text}")
            result = response.text

        forecast = Forecast(result)

        messages = list[str]()

        if datetime.datetime.today().weekday() <= 5:
            # On workdays, warn about rain only during commute times.
            if (forecast.precipitation_probability(hour=9) or 0) + (
                forecast.precipitation_probability(hour=10) or 0
            ) > 0:
                messages.append("It'll rain in the morning.")
            if (forecast.precipitation_probability(hour=18) or 0) + (
                forecast.precipitation_probability(hour=19) or 0
            ) > 0:
                messages.append("It'll rain in the evening.")
        else:
            # On weekends, warn about any rain since I might go out at any time.
            # TODO
            pass

        today_mean_temp = mean(forecast.temperatures(hours=range(9, 18)))
        yesterday_mean_temp = mean(
            forecast.temperatures(hours=range(9, 18), day_delta=-1)
        )
        self.log(
            f"today mean temp: {today_mean_temp}, yesterday mean temp: {yesterday_mean_temp}"
        )
        if today_mean_temp <= yesterday_mean_temp - 2:
            messages.append("It'll be cold today.")
        if today_mean_temp >= yesterday_mean_temp + 2:
            messages.append("It'll be hot today.")

        if messages:
            self.tts_speak(
                "\n".join(messages),
                media_player=typed_hass.EntityId("media_player.bedroom_speaker"),
            )
