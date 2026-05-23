"""KOSIS 사교육비조사 CSV 로더.

사용 전제: KOSIS 통계표에서 받은 CSV들을 01_data/kosis/ 폴더에 둔다.
예상 파일:
  - DT_1PE105.csv  학교급·시도별 1인당 월평균 사교육비
  - DT_1PE107.csv  학년별·과목별
  - DT_1PE110.csv  소득수준별
  - DT_1PE201.csv  사교육 참여율

KOSIS CSV는 보통 EUC-KR(cp949) 인코딩, 와이드 포맷 (시점=컬럼).
이를 long 포맷으로 재구성한다.
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "01_data" / "kosis"


def read_kosis(filename: str) -> pd.DataFrame:
    """KOSIS 와이드 CSV → long 포맷.

    KOSIS CSV 일반 구조:
      행: 분류항목들 (시도, 학교급, 과목 등)
      열: 시점 (2007, 2008, ... 2024)
    """
    path = DATA / filename
    df = pd.read_csv(path, encoding="cp949", low_memory=False)

    id_cols = [c for c in df.columns if not c.replace(".", "").isdigit()]
    value_cols = [c for c in df.columns if c not in id_cols]

    long = df.melt(id_vars=id_cols, value_vars=value_cols,
                   var_name="year", value_name="value")
    long["year"] = long["year"].astype(str).str.extract(r"(\d{4})").astype(int)
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    return long


def load_all() -> dict[str, pd.DataFrame]:
    out = {}
    for fname in ["DT_1PE105.csv", "DT_1PE107.csv",
                  "DT_1PE110.csv", "DT_1PE201.csv"]:
        p = DATA / fname
        if p.exists():
            out[fname.replace(".csv", "")] = read_kosis(fname)
            print(f"loaded {fname}: {len(out[fname.replace('.csv','')])} rows")
        else:
            print(f"missing {fname}")
    return out


if __name__ == "__main__":
    DATA.mkdir(parents=True, exist_ok=True)
    dfs = load_all()
    for name, df in dfs.items():
        print(f"\n{name}")
        print(df.head())
