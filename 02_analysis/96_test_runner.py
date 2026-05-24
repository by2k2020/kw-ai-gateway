"""1000개 질문 분류 자동 실행 — prompt caching + 병렬 처리.

Anthropic prompt caching:
  - system 프롬프트(60건 사례 ~12K tokens) 캐시
  - 첫 호출 비용 그대로, 5분 내 재호출 90% 절감

병렬:
  - ThreadPoolExecutor 동시 6 (rate limit 안전)
  - 1000회 약 20~30분

출력: 01_data/test_results_1000.json
"""
from pathlib import Path
import os, json, time, importlib.util
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv(Path(__file__).parent / ".env")
_KEY = os.environ["ANTHROPIC_API_KEY"].strip()

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = ROOT / "01_data" / "test_questions_1000.json"
SAMPLES = ROOT / "01_data" / "complaint_samples.json"
OUT = ROOT / "01_data" / "test_results_1000.json"

# 45 모듈에서 시스템 프롬프트 + user 프롬프트 빌더 재사용
_spec = importlib.util.spec_from_file_location("rag", ROOT / "02_analysis" / "45_rag_classifier.py")
_rag = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rag)


def classify_one_cached(client, query: str) -> dict:
    """단일 분류, system 프롬프트는 caching."""
    user_prompt = _rag._build_user_prompt(query)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        system=[{"type": "text", "text": _rag.PROMPT_SYS,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw = "".join(b.text for b in resp.content if b.type == "text").strip()
    if "```" in raw:
        raw = raw.split("```")[1].lstrip("json").strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "parse_fail", "raw": raw[:200]}
    return {
        "category": parsed.get("category", ""),
        "risk_score": float(parsed.get("risk_score", 0)),
        "reasoning": parsed.get("reasoning", "")[:300],
        "answer": parsed.get("answer", "")[:200],
        "in_tokens": resp.usage.input_tokens,
        "out_tokens": resp.usage.output_tokens,
        "cache_read": getattr(resp.usage, "cache_read_input_tokens", 0),
        "cache_create": getattr(resp.usage, "cache_creation_input_tokens", 0),
    }


def run_one(args):
    from anthropic import Anthropic
    client = Anthropic(api_key=_KEY)
    q = args
    try:
        r = classify_one_cached(client, q["text"])
        r["id"] = q["id"]
        r["text"] = q["text"]
        r["expected"] = q.get("expected", "?")
        return r
    except Exception as e:
        return {"id": q["id"], "text": q["text"], "expected": q.get("expected", "?"),
                "error": str(e)[:200]}


def main():
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    print(f"총 {len(questions)}개 질문 분류 시작 (동시 6, caching ON)")
    results = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(run_one, q): q for q in questions}
        for i, f in enumerate(as_completed(futures), 1):
            r = f.result()
            results.append(r)
            if i % 50 == 0 or i == len(questions):
                elapsed = time.time() - t0
                rate = i / elapsed
                eta = (len(questions) - i) / rate if rate > 0 else 0
                print(f"  [{i}/{len(questions)}] {elapsed:.0f}s, "
                      f"{rate:.1f}/s, ETA {eta:.0f}s", flush=True)

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    elapsed = time.time() - t0
    print(f"\n✅ 완료: {len(results)}건, {elapsed:.0f}s ({elapsed/60:.1f}분)")
    # 비용 추정
    total_in = sum(r.get("in_tokens", 0) for r in results)
    total_out = sum(r.get("out_tokens", 0) for r in results)
    cache_read = sum(r.get("cache_read", 0) for r in results)
    cost = (total_in - cache_read) * 0.80 / 1e6 + cache_read * 0.08 / 1e6 + total_out * 4.0 / 1e6
    print(f"\n비용: input {total_in:,} (cache read {cache_read:,}) / output {total_out:,}")
    print(f"  추정 ${cost:.3f}")


if __name__ == "__main__":
    main()
