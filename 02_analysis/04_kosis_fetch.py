"""KOSIS API → 사교육비 통계표 데이터 수집·저장.

DT_1PE105 (시도×학교급)은 itmId가 T00~T04로 확정됨.
다른 통계표는 사용자가 KOSIS 페이지에서 URL 받아온 후 추가.
"""
from pathlib import Path
import os
import urllib.request
import json
import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
API_KEY = os.environ["KOSIS_API_KEY"].strip()

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "01_data" / "kosis"
OUT.mkdir(parents=True, exist_ok=True)

URL = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
OUTPUT_FIELDS = "ORG_ID+TBL_ID+TBL_NM+OBJ_ID+OBJ_NM+OBJ_NM_ENG+NM+NM_ENG+ITM_ID+ITM_NM+ITM_NM_ENG+UNIT_NM+UNIT_NM_ENG+PRD_SE+PRD_DE+LST_CHN_DE+"

# 사용자가 KOSIS 페이지에서 받아온 URL의 itmId 패턴
TABLES = {
    "DT_1PE105": "T00+T01+T02+T03+T04+",   # 시도×학교급
    # 다른 통계표는 사용자 URL 추가 후 itmId 채울 것
}


def fetch(tbl_id: str, itm_id: str) -> pd.DataFrame:
    params = (
        f"method=getList&apiKey={API_KEY}"
        f"&itmId={itm_id}&objL1=ALL&objL2=&objL3=&objL4=&objL5=&objL6=&objL7=&objL8="
        f"&format=json&jsonVD=Y&prdSe=Y&newEstPrdCnt=30"
        f"&outputFields={OUTPUT_FIELDS}&orgId=101&tblId={tbl_id}"
    )
    full = URL + "?" + params
    r = urllib.request.urlopen(full, timeout=30)
    data = json.loads(r.read().decode("utf-8"))
    if isinstance(data, dict) and "err" in data:
        raise RuntimeError(f"{tbl_id}: {data}")
    return pd.DataFrame(data)


if __name__ == "__main__":
    for tbl_id, itm_id in TABLES.items():
        df = fetch(tbl_id, itm_id)
        out = OUT / f"{tbl_id}.parquet"
        df.to_parquet(out, index=False)
        print(f"OK {tbl_id}: {len(df):,} rows -> {out.name}")
