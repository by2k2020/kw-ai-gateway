"""NEIS Open API → 전국 학원·교습소 데이터 수집.

엔드포인트: https://open.neis.go.kr/hub/acaInsTiInfo
17개 시도교육청 순회, 시도별 parquet 저장 후 마지막에 통합.
"""
from pathlib import Path
import os
import sys
import time
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
API_KEY = os.environ.get("NEIS_API_KEY", "").strip()

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "01_data" / "neis_per_sido"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FINAL = ROOT / "01_data" / "neis_academy.parquet"

SIDO = {
    "B10": "서울", "C10": "부산", "D10": "대구", "E10": "인천",
    "F10": "광주", "G10": "대전", "H10": "울산", "I10": "세종",
    "J10": "경기", "K10": "강원", "M10": "충북", "N10": "충남",
    "P10": "전북", "Q10": "전남", "R10": "경북", "S10": "경남",
    "T10": "제주",
}

URL = "https://open.neis.go.kr/hub/acaInsTiInfo"
PAGE_SIZE = 500


def fetch_sido(code: str, name: str) -> pd.DataFrame:
    rows = []
    p_index = 1
    total = None
    while True:
        params = {
            "KEY": API_KEY, "Type": "json",
            "pIndex": p_index, "pSize": PAGE_SIZE,
            "ATPT_OFCDC_SC_CODE": code,
        }
        r = requests.get(URL, params=params, timeout=30)
        r.raise_for_status()
        js = r.json()
        body = js.get("acaInsTiInfo")
        if not body:
            break
        if total is None:
            total = body[0]["head"][0]["list_total_count"]
        page_rows = body[1].get("row", []) if len(body) > 1 else []
        if not page_rows:
            break
        rows.extend(page_rows)
        print(f"  {name} page {p_index}: +{len(page_rows)} (cum {len(rows)}/{total})", flush=True)
        if len(page_rows) < PAGE_SIZE or len(rows) >= total:
            break
        p_index += 1
        time.sleep(0.15)
    df = pd.DataFrame(rows)
    df["SIDO_NAME"] = name
    return df


def main():
    if not API_KEY:
        sys.exit("NEIS_API_KEY 미설정")
    print(f"start collecting {len(SIDO)} sido (pSize={PAGE_SIZE})", flush=True)
    all_dfs = []
    for code, name in SIDO.items():
        cache = OUT_DIR / f"{code}_{name}.parquet"
        if cache.exists():
            df = pd.read_parquet(cache)
            print(f"[CACHED] {name}: {len(df):,}", flush=True)
        else:
            try:
                df = fetch_sido(code, name)
                df.to_parquet(cache, index=False)
                print(f"[SAVED]  {name}: {len(df):,} -> {cache.name}", flush=True)
            except Exception as e:
                print(f"[FAILED] {name}: {e}", flush=True)
                continue
        all_dfs.append(df)

    final = pd.concat(all_dfs, ignore_index=True)
    final.to_parquet(FINAL, index=False)
    print(f"\nDONE total={len(final):,} -> {FINAL}", flush=True)


if __name__ == "__main__":
    main()
