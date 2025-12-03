# save_btc_okx_csv.py
import requests
import pandas as pd
import time

def fetch_okx_5min_csv(symbol="BTC-USDT", total_candles=105000, limit_per_request=5000, filename="btc_5min.csv"):
    url = "https://www.okx.com/api/v5/market/history-candles"
    all_candles = []
    before = None
    fetched = 0

    print("Fetching BTC 5-min candles from OKX...")

    while fetched < total_candles:
        params = {"instId": symbol, "bar": "5m", "limit": limit_per_request}
        if before:
            params["before"] = before

        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if "data" not in data or not data["data"]:
            print("No more data returned by API.")
            break

        candles = data["data"]
        all_candles.extend(candles)
        fetched += len(candles)
        before = candles[-1][0]
        print(f"Fetched {fetched} / {total_candles} candles...")
        time.sleep(0.12)  # avoid rate limit

    # Convert to DataFrame
    df = pd.DataFrame(all_candles, columns=[
        "timestamp", "open", "high", "low", "close", "volume"
    ])
    df = df.astype({
        "open": float, "high": float, "low": float, "close": float, "volume": float
    })
    df = df.sort_values("timestamp").reset_index(drop=True)
    df.to_csv(filename, index=False)
    print(f"Saved {len(df)} candles to {filename}")

if __name__ == "__main__":
    fetch_okx_5min_csv()
