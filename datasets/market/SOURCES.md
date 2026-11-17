# Market price data (Objective 3)

All prices are **Rs per quintal**, from Government of India open data (Agmarknet,
published on data.gov.in under the Government Open Data License - India).

| File | Built from | Used for |
|---|---|---|
| `current_prices.csv` | Agmarknet daily mandi prices, all India, collected 21 Jul - 24 Sep 2026 (mirror: github.com/herrrickshaw/agri-commodity-tracker, `data/mandi_prices_snapshot.csv`) | Current price = median modal price over the last 30 days; Karnataka if at least 20 records, otherwise all-India |
| `seasonal_index.csv` | Agmarknet monthly APMC prices, Maharashtra, Sep 2014 - Nov 2016 (mirror: github.com/vibhor98/Analysis-of-agricultural-trends-in-time-series-dataset, `Mandi_Data/Monthly_data_cmo.csv`) | Month-of-year price pattern per crop |
| `backtest.json` | same history | Out-of-sample accuracy of the seasonal forecast vs "price stays the same" |

Rebuild (e.g. with a fresh data.gov.in export):

```bash
python -m ml.market.build_market_data --history Monthly_data_cmo.csv \
    --recent mandi_prices_snapshot.csv --out datasets/market
```

Known limits: seasonal history is from Maharashtra, 2014-16 (27 months). A forecast
is shown only for crops where it beat the naive forecast (apple, chickpea, maize,
orange, watermelon). Coconut history mixes units and is not used. No mandi data
was found for moth beans.
