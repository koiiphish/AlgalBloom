# Data sources

Status of every source evaluated in Phase 0. Each fact cites where and when it was checked (all checks on 2026-11-17 unless stated). "Unverified" means not yet confirmed, so don't rely on it.

Recon week used for test pulls: **2026-11-01 → 2026-11-07**. Test regions: SA box 132–139°E, 32–36.5°S; Tas box 144–149°E, 39.5–44°S (`pipeline/config.py`).

## Summary (go / no-go)

| Source | Purpose | Status | Notes / blocker |
|---|---|---|---|
| IMOS VIIRS ocean colour (NOAA-20, SNPP) | chl-a target + features, history | **Go** (history/validation) | CC BY 4.0. Lags ~10 days behind real time, so it is **too slow for daily forecasting** |
| IMOS SST L3SM-1d (multi-sensor) | observed SST history | **Go** | 2012→, ~7 days behind |
| IMOS SST RAMSSA L4 (gap-free, ~9 km) | SST + anomaly feature | **Go** | 2006→, ~2 days behind |
| Open-Meteo (archive, forecast, marine) | wind, radiation, air temp, rain, waves | **Go** | Non-commercial terms satisfied; marine grid is coarse near shore |
| theLIST ShellMAP Harvest Area Boundaries | Tas prediction polygons | **Go technically; licence pending** | Layer has no licence text; asked theLIST |
| NRE Tas ShellMAP Current Harvest Status (PDF) | Tas labels (Phase 1) | **Go** | robots.txt allows it; one PDF/day; Tas Govt licence: non-commercial reuse with acknowledgement |
| NRE Tas Tasmanian Biotoxin News (PDF) | Tas labels | **Go** | Weekly; latest edition only (no visible archive) |
| PIRSA SASQAP boundaries + status | SA polygons + labels | **Blocked** | pir.sa.gov.au returns 403 to scripts; asked PIRSA |
| Australian Phytoplankton Database via GBIF API | historical HAB taxa | **Partial** | CC BY 4.0, but the GBIF copy ends ~2013–15 |
| AODN GeoServer (phyto DB ongoing, NRS/CPR phytoplankton) | historical HAB taxa | **Blocked for scripts** | robots.txt `Disallow: /` for all agents; use manual portal download instead |
| OpenFreeMap | basemap | **Go** | Free, no key, commercial use allowed; MapLibre adds attribution automatically |
| Copernicus Marine (OLCI chl, BGC + physics forecasts) | NRT chl, forecasts, baseline | **Not tested yet** | Needs a free account (Timothy) |
| SILO | long climate records | **Deferred** | Optional; Open-Meteo covers needs so far |
| River discharge (Murray Mouth, Derwent, Huon) | runoff features | **Not tested yet** | Optional |

---

## IMOS ocean colour: VIIRS daily chlorophyll-a

- **Access:** AODN THREDDS, catalog `https://thredds.aodn.org.au/thredds/catalog/IMOS/SRS/OC/gridded/` (listed directly). OPeNDAP base `https://thredds.aodn.org.au/thredds/dodsC/`. robots.txt allows the catalog.
- **Files:** `IMOS/SRS/OC/gridded/{noaa20,snpp}/P1D/YYYY/MM/{J,V}.P1D.YYYYMMDDT053000Z.aust.<var>.nc`, one file per variable per day. The variables include `chl_oci`, `chl_oc3`, `chl_gsm`, `K_490`, `par`, `ipar`, `sst`, `l2_flags` and `owtd_csiro`. Script: `pipeline/fetch/recon_imos.py` (variable `chl_oci`).
- **Grid:** 0.01° (~1 km), 12°N–60°S, 78–180°E (Australia-wide file ~2 GB uncompressed; OPeNDAP subsetting pulls only the box).
- **Licence:** CC BY 4.0 (`license` global attribute). Required acknowledgement (global attribute `acknowledgement`): *"Data was sourced from Australia's Integrated Marine Observing System (IMOS) - IMOS is enabled by the National Collaborative Research Infrastructure Strategy (NCRIS)."*
- **History in this collection:** SNPP folders from 2022, NOAA-20 from 2023. An `aqua` (MODIS) folder also exists (`P1D`). Its date range is not yet checked. Per the brief, MODIS production ended Dec 2024.
- **Latency:** on 2026-11-17 the newest NOAA-20 file was 2026-11-07 (~10 days behind), and the newest SNPP file was 2026-11-02 (~15 days).
- **Recon results (1–7 Nov):** NOAA-20 had 5/7 days (6 Nov absent from the catalogue; 1 Nov listed but returned HTTP 502 on that run). SNPP had 2/7. Daily valid-pixel fraction of the box ranged 0–57% (cloud). A weekly two-satellite composite covered 58% (SA) and 66% (Tas) of the box, and the box includes land.
- **Gotchas:**
  - **Undeclared fill value:** some daily files store missing pixels as `-999` with no `_FillValue` (e.g. NOAA-20 2026-11-02, where 60% of SA pixels were -999). Other days use NaN. Always apply `pipeline.qc.mask_invalid_chl` (≤ 0 → NaN).
  - **Latitude order:** chl files store latitude north→south. `pipeline/fetch/opendap.py` handles both orders (unit-tested).
  - **Inland water and the turbid/tannin-stained coast** show very high "chl" (e.g. Tas Central Plateau lakes and the west coast). These need a land/inland mask and care near shore.
  - **Speed:** one week × 4 products × 2 regions took ~7 min over OPeNDAP. Fine for a daily run; **too slow for a multi-year backfill**, so Phase 2 needs a bulk route (to be evaluated).
- **Verdict:** **Go** for history and validation. Because of the ~10-day lag, the near-real-time chlorophyll for the daily forecast must come from Copernicus (to be tested).

## IMOS SST: GHRSST L3SM-1d (multi-sensor) and RAMSSA L4

- **Access:** catalog `https://thredds.aodn.org.au/thredds/catalog/IMOS/SRS/SST/ghrsst/` (listed directly).
- **L3SM-1d, day+night, foundation SST:** `IMOS/SRS/SST/ghrsst/L3SM-1d/dn/YYYY/YYYYMMDD092000-ABOM-L3S_GHRSST-SSTfnd-MultiSensor-1d_dn.nc`. Variables include `sea_surface_temperature` (K) and `quality_level`. 0.02° grid (4500 × 6000, 20°N–70°S, 70–190°E). Years 2012→. Newest file 2026-11-10 (~7 days behind). Recon: 7/7 days, 42–62% of the box valid.
- **RAMSSA L4 (gap-free analysis):** `IMOS/SRS/SST/ghrsst/L4/RAMSSA/YYYY/YYYYMMDD120000-ABOM-L4_GHRSST-SSTfnd-RAMSSA_09km-AUS-v02.0-fv01.0.nc`. Variables `analysed_sst` (K) and `analysis_error`. ~1/12° grid (1081 × 1561, 70°S–20°N, 60–190°E). Years 2006→. Newest file 2026-11-15 (~2 days behind). Recon: 7/7 days, all ocean pixels filled.
- **Not used:** `L3S-1d` (AVHRR-only) ends 2025-06-06.
- **Licence:** global attribute `license` = *"GHRSST protocol describes data use as free and open"*. The IMOS CC BY 4.0 acknowledgement also applies. **To do:** confirm the exact licence on the AODN metadata record.
- **Verdict:** **Go.** RAMSSA is the main SST feature (long, gap-free, low latency); L3SM is a higher-resolution check near the coast.

## Open-Meteo

- **Endpoints used (validated by real requests, which return HTTP 400 on unknown variables):**
  - Archive: `https://archive-api.open-meteo.com/v1/archive`
  - Forecast: `https://api.open-meteo.com/v1/forecast` (16 days)
  - Marine: `https://marine-api.open-meteo.com/v1/marine` (8 days requested)
  - Hourly variables: `temperature_2m, precipitation, wind_speed_10m, wind_direction_10m, shortwave_radiation`; marine `wave_height, sea_surface_temperature`. Script: `pipeline/fetch/recon_open_meteo.py`.
- **Terms** (https://open-meteo.com/en/terms): *"You may only use the free API services for non-commercial purposes."* Listed as non-commercial: *"Private or non-profit websites or apps that do not have subscriptions or advertising."* **This project qualifies** (free, no ads, no subscriptions, no revenue). Limits: *"Less than 10'000 API calls per day, 5'000 per hour and 600 per minute"* (300,000/month), applied *"by IP addresses and application"*.
- **Licence** (https://open-meteo.com/en/licence): CC BY 4.0. A link must be shown next to any display of the data, e.g. `<a href="https://open-meteo.com/">Weather data by Open-Meteo.com</a>`. Upstream model licences also apply (e.g. Copernicus for reanalysis and waves).
- **robots.txt:** `api.`, `archive-api.` and `marine-api.open-meteo.com` all serve `User-agent: * / Disallow: /`. We read this as an instruction to web crawlers not to index the API hosts. The terms explicitly describe free programmatic API use with call limits. See `docs/decisions.md` D003.
- **Recon results:** archive and forecast had no nulls at either point. Grid snapping: Coffin Bay → (-34.55, 135.51), Huon → (-43.20, 147.09).
- **Gotchas:**
  - **The marine API grid is coarse:** Coffin Bay snapped to (-34.625, 135.375), about 10 km away on the open-ocean side (waves 1–3.4 m), and Huon to (-43.21, 147.21), about 10 km away. Marine values describe offshore conditions, not the sheltered bays.
  - Forecast `shortwave_radiation` has occasional -1 values. Clip at 0.
  - GitHub Actions runners share IPs, so rate limits may hit earlier than our own call count suggests. Keep calls batched (multi-location requests) and few.
- **Not yet checked:** Open-Meteo's *Historical Forecast API* (archived forecasts). That would let training use real past forecasts instead of observed values (leakage-honest emulation, brief §6).

## theLIST: ShellMAP Harvest Area Boundaries (Tasmania)

- **Service:** https://services.thelist.tas.gov.au/arcgis/rest/services/Public/MarineAndCoastal/MapServer (HTTP 200, ArcGIS 10.91). robots.txt allows `/query`.
- **Layer 92, "ShellMAP Harvest Area Boundaries":** polygon. Fields `OBJECTID`, `GA_NAME` (Growing Area Name), `HA_NAME` (Harvest Area Name), `AREA_HA`. Capabilities `Map,Query,Data`. geoJSON output. maxRecordCount 2000. Native EPSG:3857; we request `outSR=4326`.
- **Related layers:** 87 Marine Farming Zones (polygon), 89 Marine Farming Development Plan Areas, 90 Marine Farming Licences (point), 107 ShellMAP Water Quality Sample Sites (point).
- **Recon:** one request (`pipeline/fetch/recon_tas_boundaries.py`) returned **57 polygons in 29 growing areas** (51 Polygon, 6 MultiPolygon), bounds 144.93–148.33°E, 43.53–40.71°S. Median area **133 ha**, about one 1 km satellite pixel.
- **Pixel coverage** (`notebooks/00_recon_map.ipynb`, weekly composite): only **28/57** areas had ≥1 valid pixel inside the polygon. With a **5 km buffer** all 57 did (median 59 pixels), and with 10 km the median was 246. **This confirms the brief's coastal-buffer approach.**
- **Terms:** LIST Web Services Terms and Conditions, Dec 2014 (http://listdata.thelist.tas.gov.au/public/LISTWebServicesTermsConditions.pdf). Clause 7: *"All material published via the Service is protected so far as is allowed by the provisions of the Copyright Act 1968 (C'th). Further Licensing conditions are detailed in the Copyright Text section of the relevant service or service layer."* No rate limit is stated.
- **Licence gap:** the service copyrightText is "the LIST © State of Tasmania", and layer 92's copyrightText is **empty**. The data.gov.au listing reportedly shows "Not Specified" (search snippet; the page returned 403 to our fetcher). **Kept in git-ignored `data/` only. Not to be published until theLIST replies** (email sent by Timothy).
- **Dataset caveat (search snippet):** the boundaries are indicative only. For legal status and corner coordinates, contact ShellMAP.

## NRE Tas: ShellMAP Current Harvest Status and Biotoxin News

- **Status:** a single PDF classification notice, `https://nre.tas.gov.au/SiteAssets/ShellMAP%20Current%20Harvest%20Status.pdf`, linked from https://nre.tas.gov.au/sea-fishing-site/Pages/Growing-and-Harvest-Areas.aspx. The current file is notice **2026/067**, 17 pages, effective "1948hrs 16 November 2026". It *"revokes and replaces all previous classification notices"*, so the same URL always holds the current notice.
- **Structure (text extracted with pypdf):** each area has a line like `Zone 4 Harvest Area (Moulting Bay) OPEN`, then classification text, then `… is OPEN for the taking of all regulated fish from 1050hrs 02/11/2026`. Harvest and growing area names match theLIST `HA_NAME`/`GA_NAME`. **Each snapshot includes the date of the last status change**, so even our first snapshot carries some history.
- **Archive:** revoked notices are *"archived as monthly collections"*. Individual notices are available from ShellMAP Regulatory Services on request. That could be a source of **historical** Tas labels, so ask ShellMAP.
- **Biotoxin News:** `https://nre.tas.gov.au/SiteAssets/Tasmanian%20Biotoxin%20News.pdf`, linked from https://nre.tas.gov.au/aquaculture/shellmap/biotoxins-and-chemical-testing. *"a weekly update of biotoxin flesh and algal sampling results"*. Only the latest edition is linked, with no visible archive. Contents not yet inspected.
- **robots.txt** (https://nre.tas.gov.au/robots.txt): the `*` agent is blocked only from `/search`, `/feedback`, `/*?*` (any query string), `/_layouts/` and a few others. **Both PDFs are allowed.** Never add query strings (e.g. cache-busters).
- **Copyright** (https://www.tas.gov.au/stds/codi.htm, read by Timothy in a browser on 2026-11-17, because it returns 403 to scripts): *"The Tasmanian Government grants users of this website a licence to download, print and reproduce the information for non-commercial purposes only."* and *"Users must acknowledge the copyright owner's name and source location when the information is reproduced or quoted (either in whole or in part)."* Use beyond this needs permission from the relevant agency.
  - **Implication:** recording the status notice and Biotoxin News, and showing derived status in a free, non-commercial app, fits this licence, **provided** we credit "© State of Tasmania (NRE Tas, ShellMAP)" with the source URL. Note that this is **non-commercial only**, unlike the CC BY sources.
  - It is a website licence. Whether it also covers theLIST layer 92 is unclear, so we're still waiting on theLIST's reply.

## PIRSA SASQAP (South Australia)

- **Pages:** maps and GPS boundaries https://pir.sa.gov.au/fishing-and-aquaculture/seafood-quality-and-safety/shellfish-sasqap/gps_boundaries_and_maps_sasqap. Current status https://pir.sa.gov.au/fishing-and-aquaculture/seafood-quality-and-safety/shellfish-sasqap/harvesting-statuses (from a web search).
- **Search snippets show** per-area PDF maps (e.g. `…/coffin-bay-kellidie-east-west-growing-area-map.pdf`). Machine-readable coordinates are **unverified**.
- **Access:** automated fetches of the boundaries page and `https://pir.sa.gov.au/robots.txt` both returned **HTTP 403**. Per the respectful-scraping rule, no workaround was attempted. **Timothy has emailed PIRSA** asking about boundary data, licence, and permission for one automated status read per day.
- **Implication:** SA polygons and SA labels (Phase 1) wait on PIRSA's reply.

## Australian Phytoplankton Database (Davies et al.) and IMOS phytoplankton

- **Via GBIF** (dataset `a57985ac-a9af-4ccb-803c-f5b803af0318`, "The Australian Phytoplankton Database (1844 onwards)", https://www.gbif.org/dataset/a57985ac-a9af-4ccb-803c-f5b803af0318). The GBIF API (`https://api.gbif.org/v1/occurrence/search`) is keyless, and robots.txt allows it. Licence **CC BY 4.0** (API dataset record). Fields include `eventDate`, `decimalLatitude/Longitude`, `scientificName`, `organismQuantity` and `organismQuantityType` ("Cells per litre").
  - **Counts in our boxes:** SA 7,782 records, Tas 17,323. Harmful taxa: SA *Alexandrium* 22, *G. catenatum* 1, *Pseudo-nitzschia* 112, *Dinophysis* 37; Tas 51 / 472 / 1,052 / 683. ***Karenia*: 0 in both.**
  - **Years:** SA records end 2015 (most in 2010–2013); Tas records end 2013. **The GBIF copy cannot cover the 2025–26 *Karenia* event.**
- **Live AODN version:** the IMOS catalogue record `75f4f1fc-bee3-4498-ab71-aa1ab29ab2c0` (from search results; not opened). AODN GeoServer layers exist, including `imos:aus_phyto_db_ongoing_data`, the NRS `imos:bgc_phytoplankton_abundance_{raw,genus,species,htg}_data` and the AusCPR `imos:cpr_phytoplankton_abundance_*_data` (seen in one WFS GetCapabilities request).
- **robots.txt for `geoserver-123.aodn.org.au`:** `User-agent: * / Disallow: /` (only `LinkChecker` is allowed). **Scripts must not use it.** (One GetCapabilities request was made before robots.txt was read; none since.)
- **Alternative:** a **one-off manual download** through the AODN portal (https://portal.aodn.org.au) by Timothy in a browser. These are historical labels, so a single download is enough. Relevant portal records: AusCPR phytoplankton `8e594cd1-363a-4b58-b741-9fa3624adb77`; NRS phytoplankton abundance and biovolume `f098f0d0-88ac-4f4b-addb-24b3e5e8d0b9` (Maria Island Tas long-term; Kangaroo Island SA newer).
- **Caveat:** AusCPR counts are *"semi-quantitative"* (IMOS news article, 9 Nov 2026), so they are not absolute cell densities.

## OpenFreeMap (basemap)

- **Read:** https://openfreemap.org/, https://openfreemap.org/tos/ (updated 14 Oct 2026), https://openfreemap.org/quick_start/.
- *"Using our public instance is completely free: there are no limits on the number of map views or requests. There's no registration, no user database, no API keys, and no cookies."* Commercial use: *"Yes."*
- **Style URL:** `https://tiles.openfreemap.org/styles/liberty` (also `.../bright` and `.../positron`).
- **Attribution:** *"If you are using MapLibre, they are automatically added."* Required text otherwise: "OpenFreeMap © OpenMapTiles Data from OpenStreetMap".
- **ToS limit:** no *"collect[ing] data from the service in automated ways"* except small offline downloads. We only use it as a live basemap in the browser.
- **No SLA:** *"may discontinue it at any time without notice."* Fallback: the OSM-based Positron/Bright styles from another free host, to be decided in Phase 5.
- **Verdict:** **Go.**

## Copernicus Marine Service (not yet tested; needs an account)

To test once Timothy has a free account (credentials go in `.env` only):
1. Sentinel-3 OLCI chl-a: daily NRT L3/L4 (global or regional) and the 300 m plankton product. Check latency, which matters because IMOS is ~10 days behind.
2. Global biogeochemical analysis-forecast (modelled chl forecast; baseline 3).
3. Global physics analysis-forecast (SST, currents, salinity, MLD; multi-day forecast).
4. Whether access uses Copernicus's own servers (no AWS egress risk to us).
