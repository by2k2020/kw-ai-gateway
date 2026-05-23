"""HWPX 파일에서 텍스트 + 표 데이터 추출.

HWPX는 ZIP 압축 + XML(OWPML) 구조. namespace 무시하고 모든 텍스트 노드 추출.
표 데이터는 <hp:tbl>/<hp:tr>/<hp:tc> 구조 → 행렬로 복원.
"""
from pathlib import Path
import zipfile
import re
import xml.etree.ElementTree as ET
import json

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "01_data" / "kw" / "kw_committee.hwpx"
OUT_TXT = ROOT / "01_data" / "kw" / "kw_committee.txt"
OUT_JSON = ROOT / "01_data" / "kw" / "kw_committee_tables.json"


def localname(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def collect_text(elem) -> str:
    """엘리먼트 안의 모든 텍스트(t 노드)를 순서대로."""
    parts = []
    for sub in elem.iter():
        if localname(sub.tag) == "t" and sub.text:
            parts.append(sub.text)
    return "".join(parts)


def parse_table(tbl_elem) -> list[list[str]]:
    """hp:tbl → 2D 리스트 (행렬). cellAddr 속성으로 좌표 잡으면 더 정확."""
    rows = []
    for tr in tbl_elem.iter():
        if localname(tr.tag) != "tr":
            continue
        row = []
        for tc in tr:
            if localname(tc.tag) != "tc":
                continue
            row.append(collect_text(tc).strip())
        if row:
            rows.append(row)
    return rows


def main():
    if not SRC.exists():
        raise SystemExit(f"파일 없음: {SRC}")

    with zipfile.ZipFile(SRC) as z:
        section_names = sorted([n for n in z.namelist() if re.search(r"section\d+\.xml$", n)])
        print(f"섹션 파일: {section_names}")

        full_text = []
        all_tables = []

        for name in section_names:
            with z.open(name) as f:
                tree = ET.parse(f)
                root = tree.getroot()
                # 본문 텍스트
                full_text.append(f"\n=== {name} ===\n")
                full_text.append(collect_text(root))
                # 모든 표
                for elem in root.iter():
                    if localname(elem.tag) == "tbl":
                        tbl = parse_table(elem)
                        if tbl:
                            all_tables.append({"section": name, "rows": tbl})

    OUT_TXT.write_text("\n".join(full_text), encoding="utf-8")
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_tables, f, ensure_ascii=False, indent=2)

    print(f"✅ {len(all_tables)}개 표 추출 → {OUT_JSON.name}")
    print(f"✅ 본문 텍스트 → {OUT_TXT.name} ({len(''.join(full_text)):,} chars)")
    print("\n=== 표 미리보기 ===")
    for i, t in enumerate(all_tables[:5]):
        print(f"\n[표 {i+1}] {t['section']} - {len(t['rows'])} rows × {len(t['rows'][0]) if t['rows'] else 0} cols")
        for r in t["rows"][:6]:
            print("  ", " | ".join(c[:25] for c in r))


if __name__ == "__main__":
    main()
