import os
import time
import random
import pandas as pd
from playwright.sync_api import sync_playwright

OUTPUT_DIR = "data"
METADATA_FILE = os.path.join(OUTPUT_DIR, "last_updated.txt")

SECTOR_MAP = {
    "AGRI": "Agribusiness",
    "FOOD": "Food & Beverage",
    "FASHION": "Fashion",
    "HOME": "Home & Office Products",
    "PERSON": "Personal Products & Pharmaceuticals",
    "BANK": "Banking",
    "FIN": "Finance & Securities",
    "INSUR": "Insurance",
    "AUTO": "Automotive",
    "IMM": "Industrial Materials & Machinery",
    "PAPER": "Paper & Printing Materials",
    "PETRO": "Petrochemicals & Chemicals",
    "PKG": "Packaging",
    "STEEL": "Steel and Metal Products",
    "CONMAT": "Construction Materials",
    "CONS": "Construction Services",
    "PROP": "Property Development",
    "PF&REIT": "Property Fund & REITs",
    "ENERG": "Energy & Utilities",
    "MINE": "Mining",
    "COMM": "Commerce",
    "HELTH": "Health Care Services",
    "MEDIA": "Media & Publishing",
    "PROF": "Professional Services",
    "TOURISM": "Tourism & Leisure",
    "TRANS": "Transportation & Logistics",
    "ETRON": "Electronic Components",
    "ICT": "Information & Communication Technology",
}

def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def call_set_api(page, endpoint):
    url = f"https://www.set.or.th{endpoint}" if endpoint.startswith("/") else endpoint

    result = page.evaluate(
        f"""
        async () => {{
            try {{
                const resp = await fetch('{url}');
                return await resp.json();
            }} catch(e) {{
                return null;
            }}
        }}
        """
    )

    return result

def get_set50_companies():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(
            "https://www.set.or.th/en/market/index/set50/overview",
            wait_until="networkidle",
            timeout=60000,
        )

        page.wait_for_timeout(2000)

        comp_data = call_set_api(
            page,
            "/api/set/index/set50/composition?lang=en"
        )

        if not comp_data:
            browser.close()
            print("WARNING: Could not fetch SET50 composition data")
            return pd.DataFrame(columns=["symbol", "company_name", "sector"])

        stock_infos = comp_data.get("composition", {}).get("stockInfos", [])
        symbols = [s["symbol"] for s in stock_infos if s.get("symbol")]

        print(f"Found {len(symbols)} SET50 symbols")

        all_list = call_set_api(page, "/api/set/stock/list")
        browser.close()

        lookup = {}

        if all_list and "securitySymbols" in all_list:
            for stock in all_list["securitySymbols"]:
                lookup[stock["symbol"]] = {
                    "company_name": stock.get("nameEN", ""),
                    "sector": stock.get("sector", ""),
                }

        records = []

        for symbol in symbols:
            info = lookup.get(symbol, {})

            sector_code = info.get("sector", "")

            records.append(
                {
                    "symbol": symbol,
                    "company_name": info.get("company_name", ""),
                    "sector": SECTOR_MAP.get(sector_code, sector_code),
                }
            )

    return pd.DataFrame(records)

def get_top5_shareholders(symbol):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(
            f"https://www.set.or.th/en/market/product/stock/quote/{symbol}/major-shareholders",
            wait_until="networkidle",
            timeout=60000,
        )

        page.wait_for_timeout(2000)

        sh_data = call_set_api(
            page,
            f"/api/set/stock/{symbol}/shareholder?lang=en"
        )

        browser.close()

    records = []

    if sh_data and "majorShareholders" in sh_data:
        for row in sh_data["majorShareholders"][:5]:
            records.append(
                {
                    "symbol": symbol,
                    "rank": row.get("sequence", 0),
                    "shareholder_name": row.get("name", "").strip(),
                    "shares": row.get("numberOfShare", 0),
                    "percent_share": row.get("percentOfShare", 0.0),
                }
            )

    return pd.DataFrame(records)

def main():
    ensure_output_dir()

    print("Fetching SET50 company list...")

    companies_df = get_set50_companies()

    if companies_df.empty:
        print("No SET50 companies found. Exiting.")
        return

    companies_df = (
        companies_df
        .drop_duplicates(subset="symbol")
        .sort_values("symbol")
        .reset_index(drop=True)
    )

    companies_path = os.path.join(OUTPUT_DIR, "set50_companies.csv")
    companies_df.to_csv(companies_path, index=False, encoding="utf-8-sig")

    print(f"SET50 companies exported: {companies_path}")

    symbols = companies_df["symbol"].tolist()
    total = len(symbols)

    all_shareholders = []
    failed_symbols = []

    for idx, symbol in enumerate(symbols, 1):
        print(f"[{idx}/{total}] Processing {symbol}...")

        for attempt in range(3):
            try:
                sh_df = get_top5_shareholders(symbol)

                if not sh_df.empty:
                    all_shareholders.append(sh_df)
                    break

                raise ValueError("No shareholder data found")

            except Exception as error:
                if attempt < 2:
                    time.sleep(random.uniform(2, 4))
                else:
                    failed_symbols.append(
                        {
                            "symbol": symbol,
                            "error_message": str(error),
                        }
                    )

        time.sleep(random.uniform(2, 4))

    if all_shareholders:
        shareholders_df = pd.concat(all_shareholders, ignore_index=True)

        shareholders_path = os.path.join(OUTPUT_DIR, "shareholders.csv")
        shareholders_df.to_csv(
            shareholders_path,
            index=False,
            encoding="utf-8-sig",
        )

        print(f"Top 5 shareholders exported: {shareholders_path}")

    if failed_symbols:
        failed_df = pd.DataFrame(failed_symbols)

        failed_path = os.path.join(OUTPUT_DIR, "failed_symbols.csv")
        failed_df.to_csv(failed_path, index=False, encoding="utf-8-sig")

        print(f"Failed symbols exported: {failed_path}")

    print("\nDone.")
    print(f"Total SET50 companies: {total}")
    print(f"Failed symbols: {len(failed_symbols)}")

if __name__ == "__main__":
    main()