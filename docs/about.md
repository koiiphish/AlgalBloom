# About

> **Experimental research tool.** Indicates chlorophyll-a (algal biomass), not toxins or harmful species. Not a substitute for official harvest decisions by ShellMAP (Tasmania) or SASQAP (South Australia).

## Overview

The outlook gives the probability that satellite chlorophyll-a in each Tasmanian shellfish harvest area will exceed the area's 90th percentile for the calendar month (2016–2022) over the next 7 days. It indicates algal biomass. It does not forecast toxins or harmful species.

| Tier | Definition |
|---|---|
| **H** High | Probability ≥ 36%. In 2023–2026, 63% of weeks rated High exceeded the threshold. |
| **M** Moderate | Probability 19–36%. |
| **L** Low | Probability < 19%. Does not indicate the absence of harmful species. |

Map layers: chlorophyll-a (7-day median) and sea surface temperature (SST) anomaly relative to 1991–2020. South Australia is shown as layers only, until harvest-area boundaries are available.

## Method

1. **Input.** Copernicus Sentinel-3 OLCI chlorophyll-a, 300 m, daily, about 2 days behind real time.
2. **Area value.** The median of cloud-free pixels within each harvest area and a 2 km buffer.
3. **Score.** The 14-day mean of the log anomaly against the area's monthly median, weighted by cloud-free fraction.
4. **Probability.** Logistic (Platt) calibration fitted on 2023–2026. Tier thresholds are set at 20% and 5% false-alarm rates.

A gradient-boosted model using weather, SST, currents and seasonality did not outperform this persistence method in year-by-year testing (2018–2023). Full evaluation: [model card](model-card.html). Ongoing results: [verification](verification.html).

## Limitations

- **Proxy.** Chlorophyll-a does not measure toxins. *Alexandrium* and *Dinophysis* can be harmful at low biomass. The forecast did not discriminate harmful-species events at Maria Island (IMOS NRS).
- **Persistence.** The forecast responds to observed conditions; it does not predict bloom onset.
- **Optical contamination.** Inshore values may be inflated by sediment and dissolved organic matter, particularly after rainfall.
- **Cloud.** About one-third of area-days have usable imagery. After 14 days without imagery, the seasonal baseline probability is shown.
- **Locations.** Areas are shown as points pending boundary licensing.
- **Regional skill.** Lowest in northern and north-western Tasmania.

## Data sources

- **Chlorophyll-a and SST.** Generated using E.U. Copernicus Marine Service Information.
  - OLCI: [10.48670/moi-00278](https://doi.org/10.48670/moi-00278), [10.48670/moi-00280](https://doi.org/10.48670/moi-00280)
  - OSTIA: [10.48670/moi-00165](https://doi.org/10.48670/moi-00165), [10.48670/moi-00168](https://doi.org/10.48670/moi-00168)
  - Evaluation only: [10.48670/moi-00019](https://doi.org/10.48670/moi-00019), [10.48670/moi-00021](https://doi.org/10.48670/moi-00021)
- **Harvest-area status.** © State of Tasmania (NRE Tas, ShellMAP), non-commercial use. [ShellMAP](https://nre.tas.gov.au/aquaculture/shellmap/growing-and-harvest-areas).
- **Harvest-area locations.** Derived from theLIST, © State of Tasmania.
- **Phytoplankton counts (evaluation).** Data was sourced from Australia's Integrated Marine Observing System (IMOS). IMOS is enabled by the National Collaborative Research Infrastructure Strategy (NCRIS). CC BY 4.0.
- **Weather (model testing only).** [Weather data by Open-Meteo.com](https://open-meteo.com/) (ERA5), CC BY 4.0.
- **Basemap.** [OpenFreeMap](https://openfreemap.org), © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.
- **Software.** [MapLibre GL JS](https://maplibre.org) (BSD-3-Clause), [uPlot](https://github.com/leeoniya/uPlot) (MIT), [Inter](https://rsms.me/inter/) (SIL OFL 1.1).

## Operation

The forecast is updated daily by a scheduled GitHub Actions job and published as static files. There is no server, tracking or cost. If an update fails, the previous forecast remains visible and is marked as not updated. Source code and the decision log are in the project's public GitHub repository.
