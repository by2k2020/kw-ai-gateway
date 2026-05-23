"""KOSIS Open API → 사교육비조사 4개 통계표 자동 수집.

요구사항: .env 에 KOSIS_API_KEY=... 필요.

엔드포인트: https://kkosis.kr/openapi/Param/statisticParameterData.do
파라미터:
  method=getList   고정
  apiKey=...       발급키
  itmId=ALL        모든 항목
  orgId=101        통계청
  tblId=DT_1PE105  통계표 코드
  prdSe=Y          연도별
  startPrdDe=2007  시작 연도
  endPrdDe=2024    종료 연도
  format=json
  jsonVD=Y         결측값 빈 문자열 처리
  objL1=ALL        분류1 전체
  objL2=ALL        분류2 전체 (필요 시)
"""
from pathlib import Path
import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
API_KEY = os.environ.get("KOSIS_API_KEY", "").strip()

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "01_data" / "kosis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

URL = "https://kosis.kr/openapi/Param/statisticsParameterData.do"

TABLES = {
    "DT_1PE105": "학교급_시도별_1인당_월평균_사교육비",
    "DT_1PE107": "학년_과목별_사교육비",
    "DT_1PE110": "소득수준별_사교육비",
    "DT_1PE201": "사교육_참여율",
}


def fetch_table(tbl_id: str) -> pd.DataFrame:
    params = {
        "method": "getList",
        "apiKey": API_KEY,
        "itmId": "ALL",
        "objL1": "ALL", "objL2": "ALL", "objL3": "ALL",
        "objL4": "", "objL5": "", "objL6": "", "objL7": "", "objL8": "",
        "format": "json", "jsonVD": "Y",
        "prdSe": "Y",
        "prdInterval": "1",
        "newEstPrdCnt": "30",  # 최근 30년 (사실상 전체)
        "orgId": "101",
        "tblId": tbl_id,
    }
    r = requests.get(URL, params=params, timeout=60)
    r.raise_for_status()
    js = r.json()
    if isinstance(js, dict) and js.get("err"):
        raise RuntimeError(f"{tbl_id}: {js}")
    df = pd.DataFrame(js)
    return df


if __name__ == "__main__":
    if not API_KEY:
        raise SystemExit("KOSIS_API_KEY 가 .env에 없습니다")
    for tbl_id, name in TABLES.items():
        try:
            df = fetch_table(tbl_id)
            out = OUT_DIR / f"{tbl_id}.csv"
            df.to_csv(out, index=False, encoding="utf-8-sig")
            print(f"OK {tbl_id} ({name}): {len(df):,} rows -> {out.name}")
        except Exception as e:
            print(f"FAIL {tbl_id}: {e}")
        time.sleep(0.5)
