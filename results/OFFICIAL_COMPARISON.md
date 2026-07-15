# Official APY comparison

Compared at: **2026-07-15T17:56:28.932340+00:00**

Vaults remain independent; this is a display-alignment check only.

## Lido EarnETH

- UI: [APY* (14d avg.)](https://stake.lido.fi/earn/eth/deposit) → window label **14d**
- API (Mellow): **3.8677%** over **7d**
- Ours 7d hold: **3.920034%** (Δ vs API: 0.052374)
- Ours 14d hold: **3.841907%** (Δ vs API: -0.025753)
- Alignment: Mellow API time_range=7d (weekly); Lido UI label is 14d avg — both windows reported.

## Fluid Lite ETH

- UI: [Net APY](https://fluid.io/lite/1) — methodology **spot_projected** (no trailing window)
- API Net (`apyWithoutFee`): **5.8394%**
- API Gross (`apyWithFee`): **7.2993%**
- Implied perf fee from Gross→Net: **20.00%** (docs: 20%)
- Ours trailing hold APY — 7d: 3.185953% | 14d: 2.93222% | 30d: 3.07243%
- Note: Official Net APY is spot/projected from live protocol rates, not a trailing share-price window — no identical window to add.

