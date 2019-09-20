# UK train departure display

A Python service to display quasi-realtime UK railway station departure data in a hauntingly familiar fashion. This is designed for use on a Raspberry Pi and an SSD1322-based 256x64 SPI OLED screen.

This project uses the publicly available [Transport API][transport-api], and is strongly inspired by the work of [many others](#credits). It is structured for use on the [balenaCloud](https://balena.io/cloud) platform, which offers a free tier.

## Configuration

Sign up for the [Transport API][transport-api], and generate an app ID and API key (note the free tier has a limit of 1000 requests a day).

These environment variables can be specified using the [balenaCloud dashboard](https://www.balena.io/docs/learn/manage/serv-vars/), allowing you to set up mutiple signs in one application for different stations.

| Key                   | Default         | Description
|-----------------------|-----------------|-------------
| `activeTimes`         | (none)          | Optional. One or more time ranges during which the display will show data. See below for more details.
| `blankTimes`          | (none)          | Optional. One or more time ranges during which the display will be entirely blank. Takes precedence over `activeTimes`. See below for more details.
| `callingAt`           | (none)          | Optional. One or more [National Rail station codes][station-code], e.g. `BFR` or `BFR,CTK`.
| `departFrom`          | (none)          | **Required.** A [National Rail station code][station-code], e.g. `STP`.
| `displayRotation`     | `0`             | Optional. How much to rotate the display; either `0` or `180`. Useful if your display placement is constrained.
| `minDepartureMin`     | `0`             | Optional. If greater than zero, trains departing in less than this many minutes are not shown. This allows you to hide trains if you can't get to the platform in time to catch them.
| `outOfHoursName`      | (none)          | Optional. Name shown when current time is outside active hours, e.g. `London St Pancras`. If set to `_clock_`, the display will just show the current time. If set to `_blank_` then the display will be completely blanked.
| `slowStations`        | (none)          | Optional. If a train calls at a station in this list, it is marked "slow".
| `refreshTime`         | `120`           | Optional. Seconds between data refresh, during active hours. Values will be clamped to the range 15 - 3600, inclusive.
| `transportApi_apiKey` | (none)          | **Required.** Transport API key, e.g. `feedface8badf00ddecafbaddead`.
| `transportApi_appId`  | (none)          | **Required.** Transport API application ID, e.g. `12345678`.
| `TZ`                  | `Europe/London` | Optional. An [Olsen timezone name][tz-names] to use. You almost certainly don't want to change this.

### Time ranges

Active times are a comma-separated list of one or more time ranges. A time range has the following format:

 - An optional case-insensitive day (`Sun`, `Mon`, `Tue`, `Wed`, `Thu`, `Fri`, `Sat`, `weekday`, `weekend`) followed by a colon.
 - A start time, a hyphen, and an end time. The start and end times must be in the same format, which is one of:
   - A one- or two-digit hour (0-23).
   - A zero-padded two-digit hour (00-23).
   - A full zero-padded four-digit hour and minute (0000-2359).

Examples of valid time ranges:

 - `8-22` = every day, 08:00:00 until 22:00:00.
 - `08-22` = every day, 08:00:00 until 22:00:00.
 - `23-01` = every day, 23:00:00 until 01:00:00 _the following day_.
 - `weekday:8-22` = every day, 08:00:00 until 22:00:00.
 - `weekday:08-22` = every day, 08:00:00 until 22:00:00.
 - `weekend:1030-1545` = 19:00:00 Friday until 02:45:00 Saturday.
 - `fri:1930-0245` = 19:00:00 Friday until 02:45:00 Saturday.

It is permitted for time ranges to overlap.

### Active times, blank times, and out-of-hours times

 - During *active times*, the display will update with train data (if available) every `refreshTime` seconds.
 - During *blank times*, the display will be completely blank, not even showing the time. No train data will be fetched.
 - During *out-of-hours times*, the display will show out-of-hours content. No train data will be fetched.
   - If `outOfHoursName` is set to `_clock_`, then only a clock will be displayed.
   - If `outOfHoursName` is set to `_blank_`, then the display will be entirely blank.
   - If `outOfHoursName` is empty, then it will act as if it was set to the human-readable name of the `departFrom` station.
   - If `outOfHoursName` is any other value, a "Welcome to" message will be displayed along with a clock.

If `activeTimes` is not given, the display will be updated at all times. If `blankTimes` is not given, the display will not blank itself (unless `outOfHoursName` is `_blank_`).

For example, the configuration:

```
activeTimes=weekday:0730-0930,1715-1930,weekend:0900-2000
blankTimes=weekday:2100-0700,sat:0700-0800,sat:2200-0800,sun:2200-0700
outOfHoursName=My Home
```

would turn off the display overnight, and display a clock and "Welcome to My Home" message during the middle of a weekday.

### Calling at

If no station codes are given, all trains from the departure station are shown. If multiple station codes are given, then a train will be shown if it calls at _any_ of them.

### Slow stations

If a train calls at a station in this list, it is marked as "slow". For example, `TEA` would mark any trains calling at [Teesside Airport](https://en.wikipedia.org/wiki/Teesside_Airport_railway_station) as being "slow". This variable can have multiple stations listed, and any of them will cause the train to be marked as "slow".

There is also an advanced syntax, which looks like `SVG=2,PBO=1`. This assigns a slowness penalty of 1 to services calling at Peterborough, and a slowness penalty of 2 to services calling at Stevenage. The highest value from all of the applicable penalties is used. This allows fine distinction between different speeds of service, such as "nonstop", "fast" and "slow". If any station has an explicit penalty, then all must have one. Penalties are in the range 1-9, inclusive.

## Hardware

While this project can use a [pygame][pygame]-based emulated display for local development, it is designed to work with an SSD1322-based 256x64 SPI display, preferably yellow OLED for an authentic look. I have used [displays from AliExpress](https://www.aliexpress.com/item/32988174566.html) successfully.

The connections for one of these displays to the Raspberry Pi GPIO header are as follows, but **it would be a good idea to check the connections with the datasheet of your particilar display before powering on** as there's no guarantee yours will match the pinout of mine.

| Display pin | Connection                 | Raspberry Pi pin
|-------------|----------------------------|-------------------
| 1           | Ground                     | 6 (Ground)
| 2           | V+ (3.3V)                  | 1 (3v3 Power)
| 4           | `D0/SCLK`                  | 23 (`BCM11 SCLK`)
| 5           | `D1/SDIN`                  | 19 (`BCM10 MOSI`)
| 14          | `DC` (data/command select) | 18 (`BCM24`)
| 15          | `RST` (reset)              | 22 (`BCM25`)
| 16          | `CS` (chip select)         | 24 (`BCM8 CE0`)

## Credits

First of all, thanks to the team over at Balena who [blogged](https://balena.io/blog/build-a-raspberry-pi-powered-train-station-oled-sign-for-your-desk/) about their implementation, [put it on Github](https://github.com/balena-io-playground/UK-Train-Departure-Display), and inspired me to go one better.

Thanks also to [Chris Hutchinson](https://github.com/chrishutchinson/) who originally started this project, and [Blake](https://github.com/ghostseven) who made [some further improvements](https://github.com/ghostseven/UK-Train-Departure-Display).

The fonts used were painstakingly put together by `DanielHartUK` and can be found on GitHub at https://github.com/DanielHartUK/Dot-Matrix-Typeface. Huge thanks for making that resource available!

[pygame]: https://www.pygame.org/
[station-code]: https://www.nationalrail.co.uk/stations_destinations/48541.aspx
[transport-api]: https://www.transportapi.com/
[tz-names]: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
[rail-ticket-day]: https://www.nationalrail.co.uk/times_fares/ticket_types/46575.aspx
