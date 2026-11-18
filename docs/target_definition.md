# Target definition

**Status:** v1.2 (2026-11-18), Tasmania only. Implemented in `pipeline/features/target.py` and tested in `tests/test_target.py`. Reviewed in the EDA (`notebooks/02_eda.ipynb`) and Phase 3 (decisions D011 updates, D013): the forward window is now **weighted by each day's clear-sky fraction**.

## In one sentence

For harvest area *a* and issue date *t*, **y = 1** if the area's mean chlorophyll-a anomaly over days **t+1…t+7** is above that area's **90th percentile for that calendar month**, where both the "normal" level and the 90th percentile are computed from **training years only**.

## Step by step

| Step | Definition | Why |
|---|---|---|
| 1. Area pixels | All Copernicus OLCI 300 m L3 pixels whose centre lies inside the area polygon **+ 2 km buffer** (theLIST layer 92, buffered in EPSG:28355) | Phase 0: 2 km is the smallest buffer that gives every one of the 57 Tas areas satellite pixels (56–210 pixels each); a bigger buffer would dilute the signal with open water |
| 2. Daily value | Median chl of the valid pixels (chl > 0) | The median resists the odd bad pixel near shore |
| 3. Valid day | ≥ **5** valid pixels (confirmed in EDA, D011) | One or two pixels at a cloud edge are unreliable. Stricter minimums give no clear noise improvement for the coverage they cost |
| 4. Log scale | `log_chl = log10(chl)` | Chlorophyll is roughly log-normal: 0.5→1 matters as much as 5→10 |
| 5. Baseline | Median `log_chl` per area × calendar month over **2016-04 → 2022-12** (≥ 10 valid days, else missing) | Each area is compared with itself, which removes fixed biases such as tannin-stained estuaries reading "high" all year, and removes the normal seasonal cycle |
| 6. Anomaly | `log_chl − baseline` | "How unusual is today for this place and season?" |
| 7. Forward window | **Clear-sky-weighted** mean anomaly over **t+1…t+7** (weight = valid pixels / area pixels), needing ≥ **2** valid days of the 7 | Matches the 7-day forecast horizon. Averaging smooths noisy single days. Partly cloudy days are much noisier (cloud-edge pixels read ~29% high), so they count less without being thrown away (D011 updates, D013). Day *t* itself is excluded. |
| 8. Threshold | **90th percentile** of the forward-window mean per area × issue month, from training issue dates whose whole window lies in training (t ≤ 2022-12-24) | About 10% positives: rare enough to mean "unusual", common enough to train on |
| 9. Label | `y = 1` if window mean > threshold, `0` if not, **missing** if the window is too cloudy | A cloudy week is not a "no bloom" week. Calling it 0 would teach false negatives. |

## Gaps and cloud

We use **L3 (cloud-masked)**, not the gap-filled L4. L4 is 4 km (too coarse for ~1 km² farms), and its gap-filling interpolates values that weren't observed. Missing data are handled explicitly at every step (steps 3, 5, 7, 9), and the cloud-free-pixel count is kept as a data-quality feature.

## Splits and leakage

- **Train ≤ 2022 · validate 2023 · test 2024 → present** (time-ordered; brief §6). The 2025–26 *Karenia* period is in the test set.
- The baseline and threshold use training years only, so the model never "knows" what is normal in the years it is graded on.
- Features use only data available at issue time. Chlorophyll is available up to *t*−2 (NRT latency), SST, ocean-model analysis and weather up to *t*−1 (`pipeline/features/availability.py`), enforced by `tests/test_leakage.py`.

## Known issues and the alternative baseline

1. **Processing boundary and drift (docs/decisions.md D006 update).** The OLCI history is fully reprocessed to 2021 and interim from 2022. Over Tasmania, OLCI chl declines 2022→2026 while in-situ chl at Maria Island rises. The newer Copernicus version (202611) is ~10% *lower* still in 2024, so reprocessing doesn't remove it. A drifting baseline shifts how often the fixed 90th percentile is exceeded in validation/test.
2. **Alternative (option C): trailing baseline.** The same definition, but step 5 uses the median of the same calendar month over the **previous 3 years** only (still leakage-free). It is more robust to slow drift, at the cost of also absorbing genuine multi-year change. Both labels (`y_fixed`, `y_trailing`) are built. **Decision (D011, from validation only): `y_fixed` is the primary label.** The two are nearly identical on validation, and the fixed one keeps 29% more training labels. `y_trailing` is reported alongside it in the Phase 3 test evaluation as a drift sensitivity check.
3. **Chlorophyll is a proxy.** High-chlorophyll events aren't necessarily harmful, and some harmful species (e.g. *Alexandrium*, *Dinophysis*) cause problems at low biomass. The secondary evaluation against official closures and harmful-species counts (Phase 3) checks how far this proxy can be trusted.
4. **Estuarine optics.** Tannin-rich estuaries (Derwent, Huon, D'Entrecasteaux) read high chl year-round. The per-area baseline absorbs the *level*, but optical noise may still inflate variability there.

## Operational note

On issue day *t* the newest chlorophyll is from about *t*−2, so the model effectively forecasts 3–9 days beyond its latest chlorophyll observation. This is honest about latency, and is reflected in both training and operation.
