from typing import Any, Iterable, Collection

import dataclasses
from dataclasses import field
import datetime
import json
import dateutil.parser
import requests
import zoneinfo

import typed_hass

TIMEZONE = zoneinfo.ZoneInfo("Europe/London")
type Hour = int


def mean[T](xs: Collection[float], default: T = None) -> float | T:
    if not xs:
        return default
    return sum(xs) / len(xs)


@dataclasses.dataclass(frozen=True)
class ForecastSnapshot:
    precipitation_probability: float | None = field(metadata={"display": "rain %"})
    precipitation_intensity: float | None = field(metadata={"display": "rain str"})
    temperature: float | None = field(metadata={"display": "temperature"})
    humidity: float | None = field(metadata={"display": "humidity"})
    dew_point: float | None = field(metadata={"display": "dew pt"})
    uv_index: float | None = field(metadata={"display": "uv index"})


class Forecast:
    def __init__(self, data: str):
        self.days = dict[datetime.date, dict[Hour, ForecastSnapshot]]()
        # For "serialisation"/"deserialisation"
        self.data = data

        for timeline in json.loads(data)["data"]["timelines"][0]["intervals"]:
            time = dateutil.parser.parse(timeline["startTime"]).astimezone(TIMEZONE)

            if time.date() not in self.days:
                self.days[time.date()] = {}
            self.days[time.date()][time.hour] = ForecastSnapshot(
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

    def _get_value(self, field: str, hour: Hour, day_delta: int) -> float | None:
        key = datetime.date.today() + datetime.timedelta(days=day_delta)
        if not (day_info := self.days.get(key)):
            return None
        if not (hour_info := day_info.get(hour)):
            return None
        return getattr(hour_info, field)

    def _get_values(
        self, field: str, hours: Iterable[Hour], day_delta: int = 0
    ) -> list[float]:
        return [
            val for hour in hours if (val := self._get_value(field, hour, day_delta))
        ]

    def precipitation_probability(self, hour: Hour, day_delta: int = 0) -> float | None:
        return self._get_value("precipitation_probability", hour, day_delta)

    def precipitation_intensity(self, hour: Hour, day_delta: int = 0) -> float | None:
        return self._get_value("precipitation_intensity", hour, day_delta)

    def temperature(self, hour: Hour, day_delta: int = 0) -> float | None:
        return self._get_value("temperature", hour, day_delta)

    def temperatures(self, hours: Iterable[Hour], day_delta: int = 0) -> list[float]:
        return self._get_values("temperature", hours, day_delta)

    def as_table(self) -> str:
        headers = ["day", "hour"] + [
            f.metadata.get("display", f.name)
            for f in dataclasses.fields(ForecastSnapshot)
        ]
        spacer = ["".ljust(len(h), "-") for h in headers]
        rows = list[list[str]]()
        for day, hour_forecasts in sorted(self.days.items()):
            for hour, forecast in sorted(hour_forecasts.items()):
                row = [str(day.day), str(hour)]
                for field in dataclasses.fields(forecast):
                    row.append(str(getattr(forecast, field.name)))
                rows.append(
                    [val.ljust(len(header)) for val, header in zip(row, headers)]
                )

        return "\n".join(" | ".join(row) for row in [headers, spacer] + rows)


class ForecastCache(dict[datetime.date, Forecast]):
    def save(self, path: str):
        with open(path, "tw") as f:
            for date, data in self.items():
                f.write(f"{date.isoformat()}\n")
                f.write(f"{data.data}\n")

    def load(self, path: str):
        with open(path, "tr") as f:
            while (date_string := f.readline().strip()) and (
                data_string := f.readline().strip()
            ):
                self[datetime.date.fromisoformat(date_string)] = Forecast(data_string)


class WakeupInfo(typed_hass.Hass):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._cache = ForecastCache()

    def initialize(self):
        self._cache.load("/tmp/weather_cache")
        self.listen_event(event="ANNOUNCE_WEATHER", callback=self._on_event)
        self._on_event("", {"use_cache": True, "print_forecast": True}, {})

    def terminate(self):
        self._cache.save("/tmp/weather_cache")

    def _fetch_forecast(self, from_cache: bool) -> Forecast:
        if from_cache and (forecast := self._cache.get(datetime.date.today())):
            self.info_log(f"Returning cached forecast for {datetime.date.today()}")
            return forecast

        self.info_log("Fetching weather")
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
        self.info_log("Fetched weather")
        if response.status_code != 200:
            raise RuntimeError(f"{response.status_code}: {response.text}")
        forecast = Forecast(response.text)
        self._cache[datetime.date.today()] = forecast
        return forecast

    def _on_event(
        self, _event_name: str, data: dict[str, Any], _user_args: dict[str, Any]
    ):
        use_cache = data.get("use_cache", False)
        print_forecast = data.get("print_forecast", False)

        forecast = self._fetch_forecast(from_cache=use_cache)
        if print_forecast:
            print(forecast.as_table())

        messages = list[str]()
        if datetime.datetime.today().weekday() <= 5:
            # On workdays, warn about rain only during commute times.
            rain_chances = {
                hour: forecast.precipitation_probability(hour=hour)
                for hour in [9, 10, 18, 19]
            }
            morning_rain_chance = (rain_chances.get(9) or 0) + (
                rain_chances.get(10) or 0
            )
            evening_rain_chance = (rain_chances.get(18) or 0) + (
                rain_chances.get(19) or 0
            )
            self.info_log(f"rain chances: {rain_chances}")
            if morning_rain_chance > 0:
                messages.append("It'll rain in the morning.")
            if evening_rain_chance > 0:
                messages.append("It'll rain in the evening.")
        else:
            # On weekends, warn about any rain since I might go out at any time.
            # TODO
            pass

        today_mean_temp = mean(forecast.temperatures(hours=range(9, 18)))
        yesterday_mean_temp = mean(
            forecast.temperatures(hours=range(9, 18), day_delta=-1)
        )
        self.info_log(
            f"today mean temp: {today_mean_temp}, yesterday mean temp: {yesterday_mean_temp}"
        )
        if yesterday_mean_temp is not None and today_mean_temp is not None:
            if today_mean_temp <= yesterday_mean_temp - 2:
                messages.append("It'll be cold today.")
            if today_mean_temp >= yesterday_mean_temp + 2:
                messages.append("It'll be hot today.")

        if messages:
            self.tts_speak(
                "\n".join(messages),
                media_player=typed_hass.MediaPlayer("bedroom_speaker"),
            )
