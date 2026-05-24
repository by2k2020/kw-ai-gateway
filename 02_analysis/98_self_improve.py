"""AI 자가개선 루프 — 분류기 시스템 프롬프트가 스스로 진화.

각 iteration:
  1. 현재 프롬프트로 200건 분류
  2. 오분류 패턴 분석 (악성→비악성, 정당→악성 등)
  3. Claude Meta에게 "이 결과 보고 프롬프트 개선" 요청 → 새 프롬프트
  4. 새 프롬프트로 200건 재테스트 (다른 샘플)
  5. 정확도 비교, +3%p 이상 향상 + 5회 미만 → 다음 iteration

종료 조건:
  - 5 iteration 도달
  - 정확도 향상 < 3%p
  - 정확도 90%+

출력:
  - prompts/system_v{N}.txt (각 버전)
  - 05_submission/self_improve_log.md (전체 로그)
"""
from pathlib import Path
import os, json, time, random
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
_KEY = os.environ["ANTHROPIC_API_KEY"].strip()

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = ROOT / "01_data" / "test_questions_1000.json"
SAMPLES = ROOT / "01_data" / "complaint_samples.json"
PROMPTS_DIR = ROOT / "02_analysis" / "prompts"
PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
LOG_MD = ROOT / "05_submission" / "self_improve_log.md"

# 매 iteration 100건 (시간·비용 절감 + 네트워크 안정성)
SAMPLE_SIZE = 100
MAX_ITER = 3
MIN_IMPROVE = 0.03  # +3%p

# 초기 프롬프트 (45_rag_classifier.py의 PROMPT_SYS)
import importlib.util
_spec = importlib.util.spec_from_file_location("rag", ROOT / "02_analysis" / "45_rag_classifier.py")
_rag = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rag)
INITIAL_PROMPT = _rag.PROMPT_SYS

# 가상 사례 로드 (user prompt에 사용)
SAMPLES_DATA = json.loads(SAMPLES.read_text(encoding="utf-8"))


def build_user_prompt(query: str) -> str:
    parts = [f"학부모 입력:\n\"{query}\"\n\n=== 라벨링된 가상 사례 {len(SAMPLES_DATA)}건 ==="]
    for s in SAMPLES_DATA:
        parts.append(
            f"\n[id={s['id']}] [{s['category']}]\n"
            f"  사례: \"{s['text']}\"\n  판정: {s['verdict']}\n  근거: {s['rationale']}"
        )
    parts.append("\n\n위 사례·가이드 적용해 JSON으로 출력.")
    return "\n".join(parts)


def classify(client, query: str, system_prompt: str) -> dict:
    for attempt in range(3):
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=800,
                system=system_prompt,
                messages=[{"role": "user", "content": build_user_prompt(query)}],
            )
            raw = "".join(b.text for b in resp.content if b.type == "text").strip()
            if "```" in raw:
                raw = raw.split("```")[1].lstrip("json").strip()
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"category": "기타", "risk_score": 0, "reasoning": "parse_fail"}
        except Exception as e:
            if attempt == 2:
                return {"category": "기타", "risk_score": 0, "reasoning": f"net_error:{e}"}
            time.sleep(3 * (attempt + 1))
    return {"category": "기타", "risk_score": 0, "reasoning": "max_retry"}


def classify_3way(category: str) -> str:
    c = (category or "").strip()
    if "악성" in c: return "악성"
    if "모호" in c: return "모호"
    if "정당" in c: return "정당"
    return "기타"


def run_test(prompt: str, sample: list[dict]) -> dict:
    """200건 분류 후 정확도 등 반환."""
    from anthropic import Anthropic
    results = []
    def _one(q):
        client = Anthropic(api_key=_KEY)
        r = classify(client, q["text"], prompt)
        return {
            "text": q["text"],
            "expected": q["expected"],
            "predicted": classify_3way(r.get("category", "")),
            "category": r.get("category", ""),
            "risk_score": float(r.get("risk_score", 0)),
        }
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = [ex.submit(_one, q) for q in sample]
        for f in as_completed(futures):
            results.append(f.result())
    correct = sum(1 for r in results if r["expected"] == r["predicted"])
    acc = correct / len(results)
    # 카테고리별 recall
    by_cat = {}
    for cat in ["정당", "모호", "악성"]:
        sub = [r for r in results if r["expected"] == cat]
        if sub:
            by_cat[cat] = sum(1 for r in sub if r["predicted"] == cat) / len(sub)
    # 오분류 샘플 (악성 누락 위주)
    miss_malicious = [r for r in results if r["expected"] == "악성" and r["predicted"] != "악성"]
    miss_legit = [r for r in results if r["expected"] == "정당" and r["predicted"] != "정당"]
    return {
        "accuracy": acc,
        "n": len(results),
        "by_category": by_cat,
        "miss_malicious_examples": miss_malicious[:15],
        "miss_legit_examples": miss_legit[:5],
    }


def improve_prompt(client, current_prompt: str, test_result: dict, iteration: int) -> str:
    """현재 프롬프트 + 오분류 분석 → 새 프롬프트."""
    sample_miss = "\n".join(
        f"- 입력: \"{r['text'][:60]}\" / 정답: {r['expected']} / AI 분류: {r['category']} (risk {r['risk_score']:.2f})"
        for r in test_result["miss_malicious_examples"][:10]
    )
    meta_prompt = f"""당신은 학교 민원 분류 LLM 시스템의 프롬프트 엔지니어입니다.

[현재 시스템 프롬프트 v{iteration}]
{current_prompt}

[이번 200건 테스트 결과]
- 전체 정확도: {test_result['accuracy']*100:.1f}%
- 카테고리별 Recall: {json.dumps(test_result['by_category'], ensure_ascii=False)}

[악성을 비악성으로 잘못 분류한 사례 (악성 recall ↑ 필요)]
{sample_miss}

당신의 임무:
이 오분류 패턴을 보고 시스템 프롬프트를 개선하세요.
- 악성 recall을 올리되, 정당 recall(현재 매우 높음)은 유지
- 구체적인 한국어 표현·패턴 예시를 프롬프트에 추가
- 임계값·분류 기준 명확화
- 무리한 단정 피하면서 false negative 줄이기

⚠️ 출력: 개선된 전체 시스템 프롬프트만 (다른 텍스트·설명 없이).
"""
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4000,
        messages=[{"role": "user", "content": meta_prompt}],
    )
    new_prompt = "".join(b.text for b in resp.content if b.type == "text").strip()
    return new_prompt


def main():
    from anthropic import Anthropic
    client = Anthropic(api_key=_KEY)
    all_q = json.loads(QUESTIONS.read_text(encoding="utf-8"))

    # 매 iteration 다른 200건 샘플 (무작위, 시드 고정)
    random.seed(42)
    samples_per_iter = []
    pool = all_q.copy()
    random.shuffle(pool)
    for i in range(MAX_ITER + 1):
        samples_per_iter.append(pool[i*SAMPLE_SIZE:(i+1)*SAMPLE_SIZE])

    log = []
    log.append("# 🔁 AI 자가개선 루프 로그\n")
    log.append(f"**시작**: 2026-05-24")
    log.append(f"**iteration당 샘플**: {SAMPLE_SIZE}건, 최대 {MAX_ITER}회\n")

    current_prompt = INITIAL_PROMPT
    (PROMPTS_DIR / "system_v0.txt").write_text(current_prompt, encoding="utf-8")

    accuracies = []
    history = []  # [(iter, acc, by_cat)]

    for it in range(MAX_ITER):
        print(f"\n{'='*60}\n[Iteration {it+1}/{MAX_ITER}] 테스트 시작 ({SAMPLE_SIZE}건)\n{'='*60}", flush=True)
        t0 = time.time()
        result = run_test(current_prompt, samples_per_iter[it])
        elapsed = time.time() - t0
        print(f"  ⏱  {elapsed:.0f}s")
        print(f"  📊 정확도: {result['accuracy']*100:.1f}%")
        for k, v in result["by_category"].items():
            print(f"     {k}: {v*100:.1f}%")
        accuracies.append(result["accuracy"])
        history.append((it+1, result["accuracy"], result["by_category"]))

        log.append(f"\n## Iteration {it+1}")
        log.append(f"- 정확도: **{result['accuracy']*100:.1f}%**")
        for k, v in result["by_category"].items():
            log.append(f"- {k} recall: {v*100:.1f}%")

        # 종료 조건 체크 (마지막 iteration이 아니면)
        if it > 0 and accuracies[-1] - accuracies[-2] < MIN_IMPROVE:
            print(f"  🛑 향상 < {MIN_IMPROVE*100:.0f}%p → 종료")
            log.append(f"\n→ 향상 {(accuracies[-1] - accuracies[-2])*100:.1f}%p < {MIN_IMPROVE*100:.0f}%p, 종료")
            break
        if result["accuracy"] >= 0.90:
            print(f"  🎉 90%+ 도달 → 종료")
            log.append("\n→ 90%+ 도달, 종료")
            break

        # 프롬프트 개선
        print(f"  🛠  프롬프트 개선 중...", flush=True)
        t0 = time.time()
        new_prompt = improve_prompt(client, current_prompt, result, it+1)
        print(f"  ✨ 새 프롬프트 생성 완료 ({time.time()-t0:.0f}s, {len(new_prompt):,} chars)")
        current_prompt = new_prompt
        (PROMPTS_DIR / f"system_v{it+1}.txt").write_text(new_prompt, encoding="utf-8")
        log.append(f"- 프롬프트 v{it+1} 저장: prompts/system_v{it+1}.txt")

    # 최종 보고
    log.append("\n## 📊 정확도 추이")
    log.append("| Iteration | 정확도 | 변화 |\n|---:|---:|---:|")
    prev = None
    for it, acc, _ in history:
        delta = f"+{(acc-prev)*100:.1f}%p" if prev is not None else "-"
        log.append(f"| {it} | {acc*100:.1f}% | {delta} |")
        prev = acc

    log.append("\n## 🏆 최종 결과")
    best_iter = max(range(len(accuracies)), key=lambda i: accuracies[i])
    log.append(f"- 최고 정확도: **{accuracies[best_iter]*100:.1f}%** (Iteration {best_iter+1})")
    log.append(f"- 최종 프롬프트: prompts/system_v{best_iter+1 if best_iter > 0 else 0}.txt")

    LOG_MD.write_text("\n".join(log), encoding="utf-8")
    print(f"\n✅ 자가개선 완료, 로그: {LOG_MD}")
    print(f"   최고 정확도: {accuracies[best_iter]*100:.1f}% (Iter {best_iter+1})")


if __name__ == "__main__":
    main()
