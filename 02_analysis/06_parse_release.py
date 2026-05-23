"""교육부 2025-05-14 보도자료 hwpx 파싱 — 시도별·학교급별·유형별 표 추출.

출력: 01_data/kw/kw_2024_release_tables.json + .txt
"""
from pathlib import Path
import zipfile, re, json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "01_data" / "kw" / "kw_2024_release.hwpx"
OUT_TXT = ROOT / "01_data" / "kw" / "kw_2024_release.txt"
OUT_JSON = ROOT / "01_data" / "kw" / "kw_2024_release_tables.json"


def localname(tag): return tag.split("}")[-1] if "}" in tag else tag


def collect_text(elem):
    return "".join(s.text for s in elem.iter()
                   if localname(s.tag) == "t" and s.text)


def parse_table(tbl):
    rows = []
    for tr in tbl.iter():
        if localname(tr.tag) != "tr": continue
        row = []
        for tc in tr:
            if localname(tc.tag) != "tc": continue
            row.append(collect_text(tc).strip())
        if row: rows.append(row)
    return rows


def main():
    with zipfile.ZipFile(SRC) as z:
        sections = sorted([n for n in z.namelist()
                           if re.search(r"section\d+\.xml$", n)])
        print(f"섹션: {sections}")
        all_text, all_tables = [], []
        for name in sections:
            with z.open(name) as f:
                root = ET.parse(f).getroot()
                all_text.append(f"\n=== {name} ===\n" + collect_text(root))
                for e in root.iter():
                    if localname(e.tag) == "tbl":
                        rows = parse_table(e)
                        if rows: all_tables.append({"section": name, "rows": rows})

    OUT_TXT.write_text("\n".join(all_text), encoding="utf-8")
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_tables, f, ensure_ascii=False, indent=2)
    print(f"✅ {len(all_tables)}개 표, 본문 {len(''.join(all_text)):,} chars")
    for i, t in enumerate(all_tables):
        cols = len(t['rows'][0]) if t['rows'] else 0
        print(f"\n[표 {i+1}] {len(t['rows'])} rows × {cols} cols")
        for r in t["rows"][:8]:
            print("  ", " | ".join(c[:30] for c in r))


if __name__ == "__main__":
    main()
