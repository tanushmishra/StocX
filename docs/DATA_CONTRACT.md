# Data Contract

## Price files (data_cache/)
- Filename: `<SECTOR>__<WINDOW>.csv`, e.g. `NIFTY_IT__covid_2020.csv`
- Sectors: NIFTY_IT, NIFTY_BANK, NIFTY_AUTO, NIFTY_PHARMA
- Windows: main_3y, gfc_2008, covid_2020, tech_2022, election_2024
- First column: `Date` (YYYY-MM-DD), sorted oldest to newest
- Other columns: one per ticker (e.g. `TCS.NS`) plus `^NSEI`
- Values: adjusted closing prices, no zeros, no negatives
- Missing data: forward-filled up to 3 days; tickers with >5% missing are dropped

## Other files
- `data/fundamentals.csv`: columns ticker, pe, roe, revenue_growth, debt_to_equity, fetched_on. Blank means missing, never 0.
- `data/nse_lot_sizes.csv`: columns ticker, lot_size, source_date
- `data/headlines/<TICKER>.json`: list of {title, date, source}

## Rules
- Nobody changes a column name or file name without telling the group first.
- Real data only: ALLOW_SYNTHETIC stays false.