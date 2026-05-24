"""1000개 테스트 질문 자동 생성 — Claude Haiku로 카테고리별 비례 생성.

목표 분포 (실제 학교 현장 반영):
  - 정당 (안전·학습·시설·정보·다양성): 400건 (40%)
  - 모호 (대화 권장): 150건 (15%)
  - 악성 (부당간섭·업무부담·반복·사적영역·평가): 450건 (45%)

출력: 01_data/test_questions_1000.json
"""
from pathlib import Path
import os, json, time
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
_KEY = os.environ["ANTHROPIC_API_KEY"].strip()

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "01_data" / "complaint_samples.json"
OUT = ROOT / "01_data" / "test_questions_1000.json"

GEN_PROMPT = """당신은 한국 학교 민원 데이터 생성 전문가입니다.

학부모가 학교에 제기할 만한 다양한 질문·요청·민원 문장 {n}개를 생성하세요.

원칙:
- 한국어 자연 표현 (반말·존댓말·짧은·긴 문장 다양하게)
- 1~3 문장
- 진짜 학부모가 쓸 법한 자연스러운 표현
- 비공식 표현 포함 ("기 죽인다", "차갑게", "왜 우리 아이만" 등)
- 다양한 주제 (안전·급식·학사·평가·교우관계·교사 관계·시설·복지·진로·다양성·정보 요청·비공식 항의 등)
- 같은 패턴 반복 X

다음 비율로 작성:
- 정당한 일상 요청·정보 요청·안전 신고·학교폭력 신고·학습지원 요청·시설 신고·다양성 배려: {legit}건
- 모호한 표현·대화 권장 케이스 (구체 사실 부족·차별 의심 등): {ambiguous}건
- 악성 위험 (교사 부당간섭·업무부담·반복집요·사적영역침해·시간외요구·평가침해·무고신고위협·감시·단체동원·신체협박): {malicious}건

⚠️ JSON 배열 외 텍스트 없이 출력:
[{{"text": "...", "expected": "정당|모호|악성"}}, ...]
"""

BATCH = 50  # 한 번에 50개씩 생성


def generate_batch(legit: int, ambiguous: int, malicious: int) -> list[dict]:
    from anthropic import Anthropic
    n = legit + ambiguous + malicious
    client = Anthropic(api_key=_KEY)
    prompt = GEN_PROMPT.format(n=n, legit=legit, ambiguous=ambiguous, malicious=malicious)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(b.text for b in resp.content if b.type == "text").strip()
    if "```" in raw:
        raw = raw.split("```")[1].lstrip("json").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  parse fail: {e}, raw start: {raw[:100]}")
        return []


def main():
    target = {"legit": 400, "ambiguous": 150, "malicious": 450}
    total_target = sum(target.values())
    all_q = []

    # 20회 호출, 각 회 50개 (정당20 + 모호7 + 악성23)
    n_batches = 20
    per_batch = {
        "legit": target["legit"] // n_batches,    # 20
        "ambiguous": target["ambiguous"] // n_batches,  # 7
        "malicious": target["malicious"] // n_batches,  # 22
    }
    leftovers = {k: target[k] - per_batch[k] * n_batches for k in target}

    for i in range(n_batches):
        legit = per_batch["legit"] + (1 if i < leftovers["legit"] else 0)
        amb = per_batch["ambiguous"] + (1 if i < leftovers["ambiguous"] else 0)
        mal = per_batch["malicious"] + (1 if i < leftovers["malicious"] else 0)
        print(f"[{i+1}/{n_batches}] generating {legit}+{amb}+{mal} = {legit+amb+mal}...", flush=True)
        batch = generate_batch(legit, amb, mal)
        all_q.extend(batch)
        print(f"  → got {len(batch)} (cum {len(all_q)}/{total_target})", flush=True)
        time.sleep(0.5)

    # id 부여
    for i, q in enumerate(all_q, 1):
        q["id"] = i

    OUT.write_text(json.dumps(all_q, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ saved {len(all_q)} questions → {OUT.name}")

    # 분포 확인
    from collections import Counter
    cnt = Counter(q.get("expected", "?") for q in all_q)
    print("\n분포:")
    for k, v in cnt.most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
