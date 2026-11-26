# labels/

Ground-truth label data for the HAB risk forecaster. **This folder is committed on purpose.** Official status pages only show the *current* state, so history is lost unless we record it (see design note D001).

## Files

| File | What | Written by |
|---|---|---|
| `status_snapshots.csv` | Daily, **append-only** snapshot of every Tasmanian harvest area's official status | `archive_status` GitHub workflow → `pipeline/labels/archive.py` |
| `raw/tas_shellmap/*.pdf` | Each distinct ShellMAP classification notice (saved when its content changes) | same |
| `raw/tas_biotoxin_news/*.pdf` | Each distinct weekly *Tasmanian Biotoxin News* (raw only; not parsed yet) | same |
| `raw/manifest.csv` | Provenance of every saved raw file: URL, time retrieved, size, SHA-256 | same |
| `raw/last_fetch.csv` | Hobart date each source was last requested (guard: max 1 request per page per day) | same |
| `events.csv` | Harmful-taxon exceedances at IMOS reference stations, 2009→2026 | `pipeline/labels/events.py` (run locally) |
| `reference/tas_area_lookup.csv` | Notice area names ↔ theLIST polygon names/IDs (no geometry) | `pipeline/labels/tas_lookup.py` (run locally) |

## `status_snapshots.csv` columns

| Column | Meaning |
|---|---|
| `date` | Hobart calendar date of the snapshot |
| `region` | `tas` (SA to follow once PIRSA allows automated access) |
| `area_id` | Stable name-based ID, `tas:<growing_area>:<harvest_area>`; wild abalone blocks are `tas:abalone:<block>` |
| `status` | `OPEN`, `CLOSED`, `PARTIALLY_CLOSED`, `OPEN_CONDITIONAL` (open subject to depuration), `PROHIBITED`, `NURSERY_SOURCE` |
| `reason` | **The notice does not state reasons for farmed areas** ("not stated in notice"). Closures can be due to biotoxins *or* other causes such as rainfall, so **don't treat every closure as an algal bloom.** Only the abalone blocks give a reason (e.g. "biotoxins"). |
| `source_url` | The PDF URL requested |
| `retrieved_at` | UTC time of the request |
| `notice_id` | Classification notice number, e.g. `2026/067` |
| `status_since` | When the current status started, as printed ("from 1231hrs 14/11/2026"), ISO with Hobart offset. This gives some history from the very first snapshot. |
| `classification` | e.g. `approved area`, `restricted area`, `conditionally restricted area` |
| `harvest_area`, `growing_area` | Names exactly as printed in the notice |
| `source_sha256` | Fingerprint of the PDF the row was parsed from (matches `raw/manifest.csv`) |

## `events.csv`

One row per (sample, taxon) where a harmful taxon is at or above the **lab-alert action level** of the ShellMAP Biotoxin Management Plan v6.1, Appendix 3 (PALT). Genus-level mapping and the *Karenia* level choice are explained in `pipeline/labels/action_levels.py` and design note D009. Stations: Maria Island (Tas); Kangaroo Island (and its 5/50/60 m depth samples), Gulf St Vincent mooring and Upper Spencer Gulf mooring (SA). These are fixed stations, **not** harvest areas.

## Sources, licences and attribution

- **ShellMAP classification notices and Tasmanian Biotoxin News:** © State of Tasmania, Department of Natural Resources and Environment Tasmania (NRE Tas), ShellMAP. https://nre.tas.gov.au/aquaculture/shellmap. Reproduced under the Tasmanian Government website licence (download, print and reproduce for **non-commercial purposes**, with acknowledgement; https://www.tas.gov.au/stds/codi.htm).
- **Action levels:** ShellMAP Biotoxin Management Plan, Version 6.1, NRE Tas, Appendix 3.
- **IMOS reference-station phytoplankton (events.csv):** IMOS; CSIRO Oceans and Atmosphere; AIMS; DCCEEW NSW; SARDI (2026), *IMOS - Phytoplankton Abundance and Biovolume (reference stations)*, downloaded from https://portal.aodn.org.au on 2026-11-17. CC BY 4.0. *Data was sourced from Australia's Integrated Marine Observing System (IMOS) - IMOS is enabled by the National Collaborative Research Infrastructure Strategy (NCRIS).*
- **Area names in the lookup:** theLIST ShellMAP Harvest Area Boundaries layer, © State of Tasmania. Names only; the polygons are not redistributed until the licence is confirmed.

**This is not an official record.** For harvest decisions, always use the official ShellMAP (Tas) and SASQAP (SA) sources.
