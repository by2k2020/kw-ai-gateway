"""학교 실시간 데이터 조회 (NEIS Open API).

진짜 데이터 (실시간 호출):
  - search_school(name): 학교 검색
  - get_schedule(school): 학사일정
  - get_meal(school): 급식 식단

가상 데이터 (시연용 보강):
  - load_sample_notices(): 학교 공지·가정통신문 가상 샘플
"""
from pathlib import Path
import os
import json
import urllib.parse
import urllib.request
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
_KEY = os.environ.get("NEIS_API_KEY", "").strip()

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_NOTICES = ROOT / "01_data" / "sample_school_notices.json"


def _call(svc: str, **params) -> dict:
    params = {"KEY": _KEY, "Type": "json", "pIndex": 1, "pSize": 20, **params}
    qs = urllib.parse.urlencode(params)
    r = urllib.request.urlopen(f"https://open.neis.go.kr/hub/{svc}?{qs}", timeout=15)
    return json.loads(r.read().decode("utf-8"))


def search_school(name: str, limit: int = 10) -> list[dict]:
    """학교명으로 검색. 반환: [{name, sido, sido_code, school_code, kind, address, phone}]"""
    try:
        r = _call("schoolInfo", SCHUL_NM=name, pSize=limit)
    except Exception:
        return []
    if "schoolInfo" not in r or len(r["schoolInfo"]) < 2:
        return []
    rows = r["schoolInfo"][1].get("row", [])
    return [{
        "name": x["SCHUL_NM"],
        "sido": x["ATPT_OFCDC_SC_NM"],
        "sido_code": x["ATPT_OFCDC_SC_CODE"],
        "school_code": x["SD_SCHUL_CODE"],
        "kind": x.get("SCHUL_KND_SC_NM"),
        "address": x.get("ORG_RDNMA"),
        "phone": x.get("ORG_TELNO"),
        "estab": x.get("FOND_YMD"),
    } for x in rows]


def get_schedule(school: dict, from_ymd: str, to_ymd: str) -> list[dict]:
    """학사일정 조회."""
    try:
        r = _call("SchoolSchedule",
                  ATPT_OFCDC_SC_CODE=school["sido_code"],
                  SD_SCHUL_CODE=school["school_code"],
                  AA_FROM_YMD=from_ymd, AA_TO_YMD=to_ymd)
    except Exception:
        return []
    if "SchoolSchedule" not in r or len(r["SchoolSchedule"]) < 2:
        return []
    return [{
        "ymd": x["AA_YMD"],
        "event": x.get("EVENT_NM", ""),
        "content": x.get("EVENT_CNTNT", "").strip() or "-",
    } for x in r["SchoolSchedule"][1].get("row", [])]


def get_meal(school: dict, from_ymd: str, to_ymd: str) -> list[dict]:
    """급식 식단 조회."""
    try:
        r = _call("mealServiceDietInfo",
                  ATPT_OFCDC_SC_CODE=school["sido_code"],
                  SD_SCHUL_CODE=school["school_code"],
                  MLSV_FROM_YMD=from_ymd, MLSV_TO_YMD=to_ymd)
    except Exception:
        return []
    if "mealServiceDietInfo" not in r or len(r["mealServiceDietInfo"]) < 2:
        return []
    rows = []
    for x in r["mealServiceDietInfo"][1].get("row", []):
        dishes = x.get("DDISH_NM", "").replace("<br/>", "\n").strip()
        rows.append({
            "ymd": x["MLSV_YMD"],
            "type": x.get("MMEAL_SC_NM", ""),
            "dishes": dishes,
            "calorie": x.get("CAL_INFO", ""),
        })
    return rows


def load_sample_notices() -> list[dict]:
    if SAMPLE_NOTICES.exists():
        with open(SAMPLE_NOTICES, encoding="utf-8") as f:
            return json.load(f)
    return []


if __name__ == "__main__":
    schools = search_school("한빛초", limit=3)
    for s in schools:
        print(s)
    if schools:
        sch = schools[0]
        print("\n학사일정 3월:")
        for e in get_schedule(sch, "20260301", "20260331")[:8]:
            print(f"  {e['ymd']} {e['event']}")
        print("\n금주 급식:")
        for m in get_meal(sch, "20260302", "20260306")[:5]:
            print(f"  {m['ymd']} {m['type']}: {m['dishes'][:50]}…")
