# About this forecast

> **Experimental research tool.** This is **not** a substitute for official harvest decisions by ShellMAP (Tasmania) or SASQAP (South Australia). Always follow the official harvest-area status.

## What it shows

For each Tasmanian shellfish harvest area, the map shows the chance that **satellite chlorophyll will be unusually high over the next 7 days**, as a risk tier:

| Tier | Meaning |
|---|---|
| **H** High | Chlorophyll has been well above normal for this area and month, and that tends to persist. In 2023–2026 data, about 6 in 10 weeks flagged High were unusually green. |
| **M** Moderate | Somewhat above normal, or a mixed recent record. |
| **L** Low | Near or below normal. **Low does not mean safe**: some toxic algae cause problems without raising chlorophyll. |

"Unusually high" means above that area's 90th percentile for the calendar month, compared with its own 2016–2022 record. Tier colours are grey, amber and red, always shown with a letter. Green is deliberately not used.

The map can also show two background layers: **satellite chlorophyll** (median of the last 7 days) and **sea-surface temperature anomaly** (difference from the 1991–2020 average for the time of year). South Australian forecasts will be added when harvest-area boundaries are available. Until then, South Australia has the map layers only.

## How it works, in plain terms

1. Every day, the European Copernicus programme publishes chlorophyll measured by the Sentinel-3 satellites at 300 m resolution, about 2 days after the overpass.
2. For each harvest area (plus a 2 km strip around it, because many areas are smaller than one satellite pixel), we take the median chlorophyll on every day with a clear view.
3. We compare it with the area's normal for that month, and average the last 14 days, giving partly cloudy days less weight.
4. A statistical calibration, fitted on 2023–2026 data, turns that into a probability. The tiers use fixed cut-offs chosen so that in an ordinary week only about 20% of areas are flagged Moderate or above and 5% High.

We also tested a machine-learning model that used weather, ocean temperature, currents and the seasons. **It did not beat this simple "recent chlorophyll" approach** in year-by-year tests, so the simpler method is used. The [model card](model-card.html) has the full evaluation.

## Limitations: please read

- **Chlorophyll is a proxy.** It measures how green the water is, not toxins. Harmful species such as *Alexandrium* and *Dinophysis* can be dangerous at low numbers. At the Maria Island monitoring station, the forecast did **not** distinguish weeks with harmful-species alerts from other weeks.
- **It reacts; it doesn't predict onsets.** It says "conditions have been unusual and are likely to stay so". It cannot see a bloom before chlorophyll rises.
- **Coastal satellite data is imperfect.** Sediment, tannin-stained river water and nearby land can read as chlorophyll, especially after heavy rain.
- **Cloud.** About two-thirds of days have no clear view of a given area. After two cloudy weeks, an area shows its usual risk for the time of year, and the panel says so.
- **Locations are points.** Harvest-area boundaries will be shown once their licence is confirmed.
- **Weakest in the north and north-west of Tasmania.**

## Data sources and licences

- **Satellite chlorophyll and sea-surface temperature:** Generated using E.U. Copernicus Marine Service Information.
  - OLCI chlorophyll, [doi:10.48670/moi-00278](https://doi.org/10.48670/moi-00278) and [doi:10.48670/moi-00280](https://doi.org/10.48670/moi-00280)
  - OSTIA SST, [doi:10.48670/moi-00165](https://doi.org/10.48670/moi-00165) and [doi:10.48670/moi-00168](https://doi.org/10.48670/moi-00168)
  - Used in the model evaluation only: the BGC model [doi:10.48670/moi-00019](https://doi.org/10.48670/moi-00019) and GLORYS12 [doi:10.48670/moi-00021](https://doi.org/10.48670/moi-00021)
- **Harvest-area status:** © State of Tasmania (NRE Tas, ShellMAP), reproduced for non-commercial use. [Current ShellMAP status](https://nre.tas.gov.au/aquaculture/shellmap/growing-and-harvest-areas).
- **Harvest-area locations** are derived from theLIST, © State of Tasmania.
- **Phytoplankton counts (evaluation):** Data was sourced from Australia's Integrated Marine Observing System (IMOS). IMOS is enabled by the National Collaborative Research Infrastructure Strategy (NCRIS). CC BY 4.0.
- **Weather (model testing only):** [Weather data by Open-Meteo.com](https://open-meteo.com/) (ERA5 reanalysis), CC BY 4.0.
- **Basemap:** [OpenFreeMap](https://openfreemap.org), © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.
- **Software:** [MapLibre GL JS](https://maplibre.org) (BSD-3-Clause) and [uPlot](https://github.com/leeoniya/uPlot) (MIT), included with their licence files.

## How it's built

A scheduled GitHub Actions job runs once a day. It downloads the newest satellite data, computes the forecast and publishes small static files to this site. There is no server, no tracking and no cost. If the daily update fails, the banner at the top says so and the previous forecast stays visible, marked as out of date. The code, the decision log and the full evaluation are in the project's public GitHub repository.
