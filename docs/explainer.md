# Algal Bloom Outlook, in plain language

> **Experimental research tool.** It indicates algal biomass, not toxins. It is not a substitute for the official harvest decisions by ShellMAP (Tasmania) or SASQAP (South Australia).

## What is this?

It is a free website that gives a **7-day outlook for each of 57 shellfish harvest areas in Tasmania**. For each area, it gives the chance that the water will turn **unusually green** in the coming week. It updates itself every day.

## Why "green"?

Algae are tiny plants, and like all plants they contain **chlorophyll**, the green pigment. When algae multiply into a "bloom", the water holds more chlorophyll. Satellites can measure that colour from space. More chlorophyll means more algae.

The catch is that **green water is not the same as toxic water.** Some harmful algae are dangerous even in small numbers, too few to change the colour. So this tool shows how much algae is likely to be present, not whether shellfish are safe to eat. The official programs still decide that, by testing the water and the shellfish.

## Where does the information come from?

- **A European satellite (Sentinel-3)** photographs the whole coast almost every day. Each image pixel covers about 300 by 300 metres.
- For each harvest area (plus a 2 km margin around it), we take the **typical reading on each cloud-free day**. Clouds block the view, so on about two-thirds of days there is no reading for a given area.
- **Satellite records from 2016 to 2022** taught the system what "normal" looks like for each area in each month. A bay is naturally greener in some seasons than others.

## How does it make a prediction?

The idea is simple, and it is a little like a weather saying: **"if it has been unusually green lately, it will probably stay unusually green next week."**

1. **Compare with normal.** For each area, the latest readings are compared with that area's usual level for the time of year. For example, "3 times greener than a normal November".
2. **Look back two weeks.** The last 14 days are averaged. Clear days count fully, and partly cloudy days count less.
3. **Turn it into a percentage.** A formula, tuned on past data, converts "how unusual" into "chance of an unusually green week ahead", for example 64%.
4. **Sort into three levels.** **High**, **Moderate** or **Low**. The cut-offs are set so that in an ordinary week only about 1 area in 20 is rated High.

If an area has been cloudy for two weeks, there is nothing recent to go on. The tool then shows the usual chance for that time of year, and says so.

## How was it trained and tested?

The data was split by time, the way a fair exam is set:

- **2016–2022 (learning):** each area's normal levels and its "unusually green" threshold.
- **2023 (practice):** tuning the percentages and the cut-offs between High, Moderate and Low.
- **2024–2026 (the exam):** marked once, after everything was locked, so the results could not be adjusted to look better.

**What the exam showed:**

- The simple "it tends to stay green" rule **beat every comparison**: guessing, the usual seasonal pattern, and a European ocean computer model. It did so in every test year.
- Weeks rated **High** turned out unusually green about **7 times in 10**. Weeks rated **Low** did so about **1 time in 10**.
- The advantage is **modest in ordinary years**. A long green spell in 2026 made the overall score look better than a typical year would.
- A more complex model that also used **weather, sea temperature and currents did not do better**, so the simpler method was kept.
- In **South Australia**, applied with no changes, it showed High **11 days before** a major toxic *Karenia* bloom sample in Gulf St Vincent in July 2025. That is one encouraging case, not proof.

## What it cannot do

- **It does not detect toxins.** Checked against harmful-algae counts at a monitoring station near Maria Island, it flagged weeks with harmful algae no more often than weeks without.
- **It cannot see a bloom before it starts.** It reacts once the water begins to change.
- **Coastal readings can be fooled.** Muddy or tea-coloured water after heavy rain can look like algae from space.
- **Areas are shown as dots, not outlines**, until the boundary data licence is confirmed. Each area links to the official ShellMAP map.
- **South Australia shows map layers only** for now, until its harvest-area boundaries are available.

## Is it being checked?

Yes. Every published outlook is saved. Once each week has passed, the website's **Verification** page compares it with what the satellite actually saw, with any official harvest-area changes, and with the weekly government algae and toxin test results.

**Live site:** https://koiiphish.github.io/AlgalBloom/
