"""인증키 없이 17개 시도 학원·교습소 총량만 수집 (응답 head 활용).

사용자가 NEIS 인증키 받기 전에 미리 sido별 학원 수 분포를 확인하기 위함.
"""
from pathlib import Path
import time
import urllib.request
import json
import pandas as pd

SIDO = {
    "B10": "서울", "C10": "부산", "D10": "대구", "E10": "인천",
    "F10": "광주", "G10": "대전", "H10": "울산", "I10": "세종",
    "J10": "경기", "K10": "강원", "M10": "충북", "N10": "충남",
    "P10": "전북", "Q10": "전남", "R10": "경북", "S10": "경남",
    "T10": "제주",
}

URL = "https://open.neis.go.kr/hub/acaInsTiInfo"
OUT = Path(__file__).resolve().parent.parent / "01_data" / "sido_academy_totals.csv"


def fetch_total(code: str) -> int:
    params = f"?Type=json&pIndex=1&pSize=1&ATPT_OFCDC_SC_CODE={code}"
    r = urllib.request.urlopen(URL + params, timeout=15)
    js = json.loads(r.read().decode("utf-8"))
    return js["acaInsTiInfo"][0]["head"][0]["list_total_count"]


if __name__ == "__main__":
    rows = []
    for code, name in SIDO.items():
        try:
            n = fetch_total(code)
            print(f"{name:>4}: {n:>7,}")
            rows.append({"sido_code": code, "sido": name, "n_academy": n})
        except Exception as e:
            print(f"{name:>4}: ERROR {e}")
            rows.append({"sido_code": code, "sido": name, "n_academy": None})
        time.sleep(0.3)

    df = pd.DataFrame(rows).sort_values("n_academy", ascending=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"\nsaved {OUT}")
    print(f"\n전국 총합: {df['n_academy'].sum():,}개")
    print(df.to_string(index=False))
