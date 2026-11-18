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
| Australian Phytoplankton Database (GBIF API and AODN manual download) | historical HAB taxa | **Go, background only** | CC BY 4.0; in our regions records stop in 2016, so no overlap with the Sentinel-3 era |
| IMOS NRS phytoplankton (AODN manual download) | HAB validation, *Karenia* case study | **Go** | CC BY 4.0; MAI, KI, GSV, USG stations to 2026; captures the 2025 SA *Karenia* bloom (GSV peak 113,000 cells/L on 2025-07-03); use the genus file for totals |
| AODN GeoServer (phyto DB ongoing, NRS/CPR phytoplankton) | historical HAB taxa | **Blocked for scripts** | robots.txt `Disallow: /` for all agents; use manual portal download instead |
| OpenFreeMap | basemap | **Go** | Free, no key, commercial use allowed; MapLibre adds attribution automatically |
| Copernicus OLCI 300 m chl (NRT + multi-year) | **primary** chl target + features | **Go** | NRT ~2 days behind; MY from 2016-04; 300 m reaches small harvest areas; dataset versions changing (D006) |
| Copernicus multi-sensor 4 km chl (L3, L4 gap-free) | fallback / background layer | **Go** | 1997→; too coarse inside harvest areas |
| Copernicus global BGC analysis-forecast (chl) | baseline 3 | **Go, with caveat** | 0.25° grid almost never reaches harvest areas, so take the nearest ocean cell |
| Copernicus global physics analysis-forecast | SST, MLD, currents (7-day forecasts) | **Go** | 1/12°; history only from 2022-06; nearest-ocean-cell extraction needed |
| SILO | long climate records | **Deferred** | Optional; Open-Meteo covers needs so far |
| River discharge (Murray Mouth, Derwent, Huon) | runoff features | **Not tested yet** | Optional |

---

## IMOS ocean colour: VIIRS daily chlorophyll-a

- **Access:** AODN THREDDS, catalog `https://thredds.aodn.org.au/thredds/catalog/IMOS/SRS/OC/gridded/` (listed directly). OPeNDAP base `https://thredds.aodn.org.au/thredds/dodsC/`. robots.txt allows the catalog.
- **Files:** `IMOS/SRS/OC/gridded/{noaa20,snpp}/P1D/YYYY/MM/{J,V}.P1D.YYYYMMDDT053000Z.aust.<var>.nc`, one file per variable per day. The variables include `chl_oci`, `chl_oc3`, `chl_gsm`, `K_490`, `par`, `ipar`, `sst`, `l2_flags` and `owtd_csiro`. Script: `pipeline/fetch/recon_imos.py` (variable `chl_oci`).
- **Grid:** 0.01° (~1 km), 12°N–60°S, 78–180°E (Australia-wide file ~2 GB uncompressed; OPeNDAP subsetting pulls only the box).
- **Licence:** CC BY 4.0 (`license` global attribute). Required acknowledgement (global attribute `acknowledgement`): *"Data was sourced from Australia's Integrated Marine Observing System (IMOS) - IMOS is enabled by the National Collaborative Research Infrastructure Strategy (NCRIS)."*
- **History in this collection:** SNPP folders from 2022, NOAA-20 from 2023. An `aqua` (MODIS-Aqua) folder also exists (`P1D`, file prefix `A.`). Checked 2026-11-18 via the THREDDS NetCDF Subset Service (`/thredds/ncss/grid/IMOS/SRS/OC/gridded/...`): daily files exist for 2,095 of 2,192 days in 2019-2024 (the other 97 requests failed and are treated as missing days). Per the brief, MODIS production ended Dec 2024. Used only for the Maria Island independence check (`pipeline/fetch/recon_mai_independent.py`; D006 update).
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

### Manual AODN downloads (Timothy, 2026-11-17, AODN portal, guest access)

Subset box 129–150°E, 31–44.5°S, full time range, CSV. Files are in git-ignored `data/raw/aodn_manual/`. Metadata read from the GeoNetwork XML (`https://catalogue-imos.aodn.org.au/geonetwork/srv/api/records/<uuid>/formatters/xml`).

**1. `phyto_db_ongoing_2026-11-17.csv`: "The Australian Phytoplankton Database (1844 - ongoing) - abundance and biovolume"** (uuid `75f4f1fc-bee3-4498-ab71-aa1ab29ab2c0`, CC BY 4.0)
- 521 MB, 1,063,937 rows, long format (one row per taxon per sample). Columns include `LATITUDE, LONGITUDE, LOCATION, SAMPLE_TIME_UTC, TAXON_NAME, GENUS, SPECIES, CELLS_L, PRESENCE_ABSENCE, BIOVOLUME_UM3_L, PROJECT_DESCRIPTION, SAMPLE_METHOD`.
- **Despite "ongoing", records in our regions stop in 2016:** SA 2,525 samples (1954–2016; only 130 in 2016), Tas 3,105 samples (1939–2016; only 13 in 2016). The main contributors are AusCPR (SA), Huon River sampling (Tas) and a Tas "Bloom monitoring program".
- Harmful taxa, records (max cells/L, last date):

  | Taxon | SA | Tas |
  |---|---|---|
  | *Karenia* | 779 (5,000; 2013-08) | 393 (50; 2013-01) |
  | *Alexandrium* | 930 (57; 2016-05) | 129 (19,500; 2016-07) |
  | *Gymnodinium catenatum* | 45 (220; 2016-05) | 1,213 (510,987; 2016-07) |
  | *Pseudo-nitzschia* | 5,421 (38,589; 2016-08) | 3,894 (1,662,681; 2016-07) |
  | *Dinophysis* | 3,924 (1,104; 2016-08) | 5,110 (19,500; 2016-07) |

- **`CELLS_L` is empty for ~90% of rows** (presence-only or biovolume-only records). This needs investigating before use.
- **Use:** background seasonality of harmful taxa (which months, which places) and model-card context. **Almost no overlap with the Sentinel-3 era (2016-04 →), so it can't be used for model validation.**
- Citation: Davies CH et al. (Year), *The Australian Phytoplankton Database (1844 - ongoing) - abundance and biovolume*, AODN. For multi-project use, also cite Davies et al. 2016, *Scientific Data* 3:160043 (doi:10.1038/sdata.2016.43). IMOS acknowledgement for IMOS projects.

**2. `nrs_phyto_species_2026-11-17.csv`: "IMOS - Phytoplankton Abundance and Biovolume (reference stations)", species-level abundance** (uuid `f098f0d0-88ac-4f4b-addb-24b3e5e8d0b9`, CC BY 4.0)
- 393 samples, wide format (17 metadata columns + 429 species columns, cells/L), light microscopy. Record extent 2009-01 → 2026-06.
- Stations in the box: **Maria Island MAI** (Tas, 180 samples, 2009 → 2026-06, ~monthly), **Kangaroo Island KAI** (73, 2009 → 2026-03) plus depth stations KAID1/2/3 (5/50/60 m, 29 each, 2018 → 2025-10), **SA Gulf St Vincent mooring GSV** (23, 2019 → 2025-10), **SA Upper Spencer Gulf mooring USG** (22, 2019 → 2025-12), Bonney Coast VBM (8, 2024 →; Vic border).
- Species-level harmful taxa (positive samples; max cells/L): *Alexandrium* 36 (818), ***G. catenatum*** 11 (10,495; mostly MAI), *Pseudo-nitzschia* 30 (2,000), *Dinophysis* 63 (3,000). Species-level *Karenia*: GSV 2025-07-03 *K. mikimotoi* 3,000; GSV 2025-10-17 43,750 (*K. cristata* 42,000).
- **Gotcha:** the species product **leaves out genus-only identifications**. Compare the genus file below: *Pseudo-nitzschia* positive in 30 samples here vs 306 there. **Use the genus file for harmful-genus totals. Use the species file only for *G. catenatum*** (the genus *Gymnodinium* includes non-toxic species).

**2b. `nrs_phyto_genus_2026-11-17.csv`: same record (uuid `f098f0d0-…`), genus-level abundance** (downloaded 2026-11-17, same box)
- 393 samples (same as the species file), 17 metadata columns + 289 genus columns (cells/L).
- Harmful genera (positive samples; max cells/L): ***Karenia*** 38 (**113,000**), *Alexandrium* 56 (1,020), *Pseudo-nitzschia* **306** (205,863; MAI 158, KAI 63), *Dinophysis* 72 (3,000), *Gymnodinium* 20 (10,495; genus, not all toxic).
- **The 2025 SA *Karenia* event (genus totals), a dated, independent record for the case study:**
  - Before 2025, the maximum at any station was 1,200 cells/L.
  - **Onset, May 2025:** low counts at four SA stations at once: GSV 05-01 (50), USG 05-08 (100), KAI/KAID1-3 05-20 (82–800).
  - **Peak: GSV 2025-07-03, 113,000 cells/L** (only 3,000 identified to species, so most were *Karenia* spp.).
  - GSV 2025-10-17: 43,800. KI 2025-10-28: up to 1,200. USG 2025-12-02: 650.
  - Tas: MAI 2025-02-27 (206) and 2025-09-30 (100). Low.
- Stations are fixed points, not harvest areas, so validation is regional and qualitative (lead time vs the onset of a station exceedance).
- Citation: IMOS; CSIRO Oceans and Atmosphere; AIMS; DCCEEW NSW; SARDI [year], *IMOS - Phytoplankton Abundance and Biovolume (reference stations)*, downloaded from https://portal.aodn.org.au on 2026-11-17. Plus the IMOS/NCRIS acknowledgement.

**3. AusCPR phytoplankton** (uuid `8e594cd1-…`): **not downloaded** (mainly offshore and Southern Ocean routes; semi-quantitative).

## OpenFreeMap (basemap)

- **Read:** https://openfreemap.org/, https://openfreemap.org/tos/ (updated 14 Oct 2026), https://openfreemap.org/quick_start/.
- *"Using our public instance is completely free: there are no limits on the number of map views or requests. There's no registration, no user database, no API keys, and no cookies."* Commercial use: *"Yes."*
- **Style URL:** `https://tiles.openfreemap.org/styles/liberty` (also `.../bright` and `.../positron`).
- **Attribution:** *"If you are using MapLibre, they are automatically added."* Required text otherwise: "OpenFreeMap © OpenMapTiles Data from OpenStreetMap".
- **ToS limit:** no *"collect[ing] data from the service in automated ways"* except small offline downloads. We only use it as a live basemap in the browser.
- **No SLA:** *"may discontinue it at any time without notice."* Fallback: the OSM-based Positron/Bright styles from another free host, to be decided in Phase 5.
- **Verdict:** **Go.**

## Copernicus Marine Service

- **Access:** `copernicusmarine` toolbox 2.5.1 (pinned), free account. Credentials go in `.env` / GitHub secrets as `COPERNICUSMARINE_SERVICE_USERNAME` / `_PASSWORD` (names verified with `copernicusmarine login --help`). Check with `uv run python -m pipeline.check_copernicus`. Script: `pipeline/fetch/recon_copernicus.py`.
- **Every dataset ID, variable and time range below comes from `copernicusmarine.describe(dataset_id=...)` on 2026-11-17.**
- **Hosting:** data is served from `s3.waw3-1.cloudferro.com` (CloudFerro, Warsaw) and `wmts.marine.copernicus.eu`. **Not AWS, so no egress cost to us.**
- **Speed:** all 14 recon subsets (7 datasets × 2 regions) took **45 s** (IMOS OPeNDAP: ~7 min for less).
- **Licence** (https://marine.copernicus.eu/user-corner/service-commitments-and-licence, read 2026-11-17): *"This Licence is granted free of charge."* Clause 2.2(b) allows creating and distributing value-added and derivative products *"for any purpose"*. Attribution (2.4a), clearly visible on the home page or the page giving access: **"Generated using E.U. Copernicus Marine Service Information"** plus the DOI links of the products used. No volume limit is stated. Logins are *"personal … and non-transferable"*. The SLA says the service is free until **30 June 2028** (planned end of the current service period). That is a long-term risk to monitor.

### Datasets tested

| Use | dataset_id (product, DOI) | Variable(s) | Grid | Time range on 2026-11-17 |
|---|---|---|---|---|
| **Primary chl, operational** | `cmems_obs-oc_glo_bgc-plankton_nrt_l3-olci-300m_P1D` (OCEANCOLOUR_GLO_BGC_L3_NRT_009_101, 10.48670/moi-00278) | `CHL`, `CHL_uncertainty`, `flags` | 1/180° (~300 m) | rolling: 2026-10-30 → **2026-11-15 (~2 days behind)** |
| **Primary chl, training history** | `cmems_obs-oc_glo_bgc-plankton_my_l3-olci-300m_P1D` (OCEANCOLOUR_GLO_BGC_L3_MY_009_103, 10.48670/moi-00280) | `CHL`, … | ~300 m | **2016-04-25** → 2026-11-09 |
| Fallback chl, NRT | `cmems_obs-oc_glo_bgc-plankton_nrt_l3-multi-4km_P1D` (moi-00278) | `CHL` + phytoplankton functional types (`DINO`, `DIATO`, …) | 1/24° (~4 km) | 2026-10-30 → 2026-11-15 |
| Gap-free chl, NRT | `cmems_obs-oc_glo_bgc-plankton_nrt_l4-gapfree-multi-4km_P1D` (OCEANCOLOUR_GLO_BGC_L4_NRT_009_102, 10.48670/moi-00279) | `CHL` | ~4 km | 2026-11-04 → 2026-11-15 |
| Gap-free chl, history | `cmems_obs-oc_glo_bgc-plankton_my_l4-gapfree-multi-4km_P1D` (OCEANCOLOUR_GLO_BGC_L4_MY_009_104, 10.48670/moi-00281) | `CHL` | ~4 km | 1997-09-04 → 2026-11-09 |
| **Baseline 3 (modelled chl forecast)** | `cmems_mod_glo_bgc-pft_anfc_0.25deg_P1D-m` (GLOBAL_ANALYSISFORECAST_BGC_001_028, 10.48670/moi-00015) | `chl` (depth levels, top 0.494 m) | 0.25° | 2021-11-01 → **2026-11-26 (+9 days)** |
| **BGC hindcast (baseline 3, used)** | `cmems_mod_glo_bgc_my_0.25deg_P1D-m` (GLOBAL_MULTIYEAR_BGC_001_029, 10.48670/moi-00019), version 202406 | `chl` (variables chl, no3, nppv, o2, po4, si; top depth 0.506 m) | 0.25° | 1993-01-01 → 2026-09-30 (describe(), 2026-11-18). Fetched by `pipeline/fetch/history_bgc.py`. |
| SST forecast | `cmems_mod_glo_phy-thetao_anfc_0.083deg_P1D-m` (GLOBAL_ANALYSISFORECAST_PHY_001_024, 10.48670/moi-00016) | `thetao` (top 0.494 m) | 1/12° | 2022-06-01 → 2026-11-26 |
| Mixed-layer depth | `cmems_mod_glo_phy_anfc_0.083deg_P1D-m` (moi-00016) | `mlotst` | 1/12° | 2022-06-01 → 2026-11-26 |
| Currents | `cmems_mod_glo_phy-cur_anfc_0.083deg_P1D-m` (moi-00016) | `uo`, `vo` | 1/12° | 2022-06-01 → 2026-11-26 |
| SST anomaly (model) | `cmems_mod_glo_phy_anfc_0.083deg-sst-anomaly_P1D-m` (moi-00016) | `sea_surface_temperature_anomaly` | 1/12° | 2022-11-01 → 2026-11-26 |

### Recon results (1–7 Nov 2026 observations; 17–24 Nov forecasts)

- **OLCI 300 m daily valid fraction of the box:** SA 11–50%, Tas 3–48% (cloud). Multi-sensor 4 km: SA 31–63%, Tas 11–64%.
- **Pixel coverage of the 57 Tas harvest areas** (weekly composite; ≥1 valid pixel inside the polygon, and median pixels per area):

  | Product | 0 km buffer | 2 km buffer | 5 km buffer |
  |---|---|---|---|
  | OLCI 300 m | **52/57**, median 3 | **57/57**, median 37 | 57/57, median 144 |
  | IMOS VIIRS 1 km | 28/57, median 0 | — | 57/57, median 59 |
  | Multi-sensor 4 km | 6/57, median 0 | 38/57, median 1 | 54/57, median 3 |
  | BGC model 0.25° (one forecast day) | 0/57 | 0/57 | **2/57** |
  | Physics model 1/12° (one forecast day) | 2/57 | 12/57 | 36/57 |

- **OLCI vs IMOS VIIRS agreement** (SA, binned to 0.05°, log10 chl): 2 Nov r = 0.96 (n = 1,900 cells, median ratio 0.97); 3 Nov r = 0.97 (n = 4,038, 1.07); 5 Nov r = 0.96 (n = 4,362, 0.91). **The two products agree closely, so IMOS is a good independent cross-check.**
- Model MLD (SA, forecast week): 3–111 m.

### Gotchas

- **Dataset versions are changing.** The default NRT versions (`202207` for OLCI 300 m, `202411` for multi 4 km) retire on **2027-01-12**. The MY OLCI 300 m `202211` version retires on **2026-11-24** (next week). The replacement `202611` versions currently offer only `original-files` and `wmts`, not the ARCO subset service, so we can't subset them yet. They also add phytoplankton functional types at 300 m, **including `DINO` (dinoflagellates)**, a promising feature since *Karenia* is a dinoflagellate. See D006.
- **Models barely reach the coast:** the BGC (0.25°) and physics (1/12°) land masks exclude most harvest areas, even with a 5 km buffer. Features and baseline 3 must use the **nearest valid ocean cell(s)** within a set radius, recorded per area.
- **Depth:** model 3-D variables start at 0.494 m. Request `minimum_depth=0, maximum_depth=1` to get the surface layer (the toolbox warns but returns the top level).
- **Estuaries saturate:** weekly OLCI and VIIRS both show chl ≥ 10 mg m⁻³ across the Derwent, Huon and D'Entrecasteaux Channel (`docs/img/phase0_tas_zoom_300m_vs_1km.png`). That is probably partly coloured dissolved organic matter (tannins) and turbidity, not phytoplankton. Our anomaly-vs-own-climatology target partly absorbs this persistent bias, but we should note it as a limitation and consider the `flags` and `CHL_uncertainty` fields.
- **The NRT archive is a rolling window** (~2–3 weeks). The daily pipeline must cache what it needs, and history must come from the MY product.
- Baseline-3 history only starts **2021-11**, and physics forecasts only **2022-06**. That covers the validation (2023) and test (2024→) periods but not training before then. See D005.


## Phase 3 verification notes (2026-11-18)

- **BGC analysis-forecast has no archive of issued forecasts.** `copernicusmarine.describe` for `cmems_mod_glo_bgc-pft_anfc_0.25deg_P1D-m` (version 202311) shows a single `default` part: one best-estimate time series. So baseline 3 uses the multi-year hindcast as a "perfect forecast" (D012/D013).
- **OLCI `flags` and `CHL_uncertainty` (version 202211):** `flags` has `flag_masks = 1`, `flag_meanings = "LAND"` (land only, no cloud flags), and `CHL_uncertainty` (%) has a median of 50% with an interquartile range of 49.5–50% over valid Tas pixels, so neither can filter cloud edges (checked from file attributes and values).
- **Open-Meteo Previous Runs API** (https://open-meteo.com/en/docs/previous-runs-api; endpoint `https://previous-runs-api.open-meteo.com/v1/forecast`): variables take a `_previous_dayN` suffix (N = 0…7), and `start_date`/`end_date`, `models` and `cell_selection=sea` are accepted (verified by real requests). Coverage probed at (−42.75, 147.5) on four dates: `best_match` and `gfs_seamless` have data from 2024-02-01 onwards; `ecmwf_ifs025` has none on 2024-02-01 but has data from 2024-07-01; `bom_access_global` has data in 2024–2025 but none on 2026-01-01. The pricing page marks the Previous Runs API as available on the free tier. **Not used in the end**: the shipped forecast needs no weather (D013).
- **MODIS-Aqua on AODN THREDDS:** see the IMOS section above.

## Phase 4 verification notes (2026-11-18)

- **OLCI 300 m NRT** `cmems_obs-oc_glo_bgc-plankton_nrt_l3-olci-300m_P1D`, version `202207`. The toolbox warns it retires on **2027-01-12T13:00Z**.
  - On 2026-11-18 at 13:45 UTC, its time axis ran **2026-10-30 → 2026-11-16**.
  - It matches the MY 202211 history over 1–7 Nov 2026 (median area ratio 1.000; D014).
  - Used by `pipeline/forecast/inputs.py`.
- **OSTIA NRT** `METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2` (default version), variable `analysed_sst` (K).
  - Newest day was 2026-11-17 on 2026-11-18.
  - Same 0.05° grid as the reprocessed product; the daily job checks this on every run.
- **OSTIA reprocessed** `METOFFICE-GLO-SST-L4-REP-OBS-SST`, version `202003`.
  - Downloaded 1991–2020 for SA_BBOX (132–139°E, 36.5–32°S), about 264 MB uncompressed (dry run), with `pipeline/fetch/history_sst_map.py`.
  - Tasmania reuses `history_ocean_tas/ostia_rep.nc`.
- **Not used:** `cmems_mod_glo_phy_anfc_0.083deg-sst-anomaly_P1D-m` (variable `sea_surface_temperature_anomaly`, °C, source "MERCATOR GLO12"). Neither `copernicusmarine.describe` nor the file's global attributes give a reference period for the anomaly (D014).
- **GitHub Actions:** the latest `actions/cache` release is **v6.1.0** (GitHub API, 2026-11-18). The workflow uses `@v6`.
