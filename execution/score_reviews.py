"""
QB 블로그 후기 품질 채점 모듈
=================================================
QUEBON_Review 페이지의 '블로그 품질 평가 루브릭'을 기준으로 Claude가 블로그 본문을 채점합니다.

- 지표 5개(각 0~100): 경험 구체성 / 효과 근거 / 메시지 적합성 / 정보 유용성 / 콘텐츠 완성도
- 함께 기록: 채점 근거(지표별 근거 요약), 인용 문장(2차 콘텐츠용), 검토 필요(사실 오류·고지 누락)
- 평균 점수·후기 평가도(별점)·우수·2차 활용 후보는 노션 수식이 자동 계산 (여기서는 요약 표시용으로만 동일 계산)

루브릭을 바꾸면 노션 토글과 아래 SCORE_PROMPT를 함께 수정해야 합니다.
"""

import os
import re
import json
import time
from datetime import datetime

# 채점은 판단이 섬세해야 하므로 태깅(Haiku)보다 상위 모델 사용
SCORE_MODEL = os.getenv("SCORE_MODEL") or "claude-sonnet-5-5"
SCORE_BODY_LIMIT = 8000          # 채점에 보내는 본문 최대 길이(자)

# 내부 키 → 노션 컬럼명 (순서 = 루브릭 지표 순서)
METRICS = [
    ("experience", "경험 구체성"),
    ("evidence", "효과 근거"),
    ("message", "메시지 적합성"),
    ("info", "정보 유용성"),
    ("completeness", "콘텐츠 완성도"),
]
FLAG_OPTIONS = ["사실 오류", "고지 누락"]

SCORE_PROMPT = """당신은 깨봉수학(초등 수학 온라인 학습 서비스)의 마케팅 담당자로서 학부모 블로그 후기의 품질을 채점합니다.
아래 루브릭에 따라 5개 지표를 각각 0~100 정수로 채점하고 JSON 하나만 출력하세요.

[공통 원칙]
1. 분량이 아니라 구체성으로 평가한다. 길다는 이유만으로 점수를 올리지 않는다.
2. 지표마다 근거가 된 본문 표현을 짧게 인용한다. 근거 표현이 없으면 그 지표는 50점을 넘길 수 없다.
3. 0/25/50/75/100 기준을 기둥으로 하되, 두 기준 사이면 중간값(예: 60, 85)을 준다.
4. 커넥터즈·협찬 여부는 점수에 반영하지 않는다.
5. 솔직한 단점 언급은 감점하지 않는다. 장단점을 균형 있게 담으면 정보 유용성에서 가점한다.
6. 이미지는 내용을 볼 수 없다. [이미지 수]와 본문 속 사진 설명으로만 판단한다.

[지표 1. 경험 구체성 - experience] 실제 이용 경험(학습·강연·도서)을 구체적으로 썼는가
100: 이용 기간·빈도·과정(단계명)이 모두 명시되고, 구체적인 학습 장면과 아이의 실제 말·행동이 여러 번 등장
75: 기간·과정이 명시되고, 구체적인 장면이나 아이 반응이 1~2개
50: 이용 사실은 분명하지만 "재밌어해요" 같은 일반적 서술 위주
25: 실제 이용 여부가 모호하고 서비스 소개·정보 정리 위주
0: 실제 경험 없음 (홍보 문구 전재, 단순 정보 글)

[지표 2. 효과 근거 - evidence] 학습 성과나 태도 변화를 보여 주는 근거가 있는가
100: 전후 비교가 분명하고 객관적 지표(점수·단원평가·학습 데이터)와 구체적 사례가 함께 있음
75: 구체적인 변화 사례(문제를 푸는 장면, 아이의 말) 또는 객관적 지표 하나
50: 변화를 언급하지만 "이해가 좋아졌어요"처럼 추상적
25: 기대·예상 수준 ("도움이 될 것 같아요")
0: 효과·변화 언급 없음

[지표 3. 깨봉 메시지 적합성 - message] 깨봉의 차별점(개념·원리 이해, 생각하는 수학, 암기가 아닌 이해, 보이지 않는 것을 보는 힘)을 정확히 전달하는가
100: 핵심 메시지를 자기 경험과 연결해 정확히 설명하고, 그대로 인용할 만한 문장이 있음
75: 핵심 메시지 하나 이상을 자기 경험과 연결
50: 메시지를 언급하지만 일반적 ("개념 위주예요")
25: 일반 학습지·인강과 구별되지 않는 설명
0: 깨봉 메시지와 무관하거나 잘못 전달

[지표 4. 정보 유용성 - info] 구매를 고민하는 부모에게 도움이 되는가
판단 요소: ①과정·커리큘럼 ②활용법·학습 루틴 ③가격·혜택 ④장단점 ⑤추천 대상
100: 판단 요소 4개 이상 + 장점과 아쉬운 점을 균형 있게 정리
75: 판단 요소 3개 이상 + 장단점 언급
50: 판단 요소 1~2개
25: 단편적인 정보만
0: 구매 판단에 도움되는 정보 없음

[지표 5. 콘텐츠 완성도 - completeness] 읽기 쉽고 직접 만든 자료로 완성도 있게 구성했는가
100: 소제목 등 구성이 명확하고, 직접 찍은 학습 화면·결과물 사진이 많고 설명이 붙어 있음
75: 구성이 양호하고 직접 찍은 사진이 일부 있음
50: 읽는 데 무리가 없으나 사진이 적거나 퍼온 이미지 위주
25: 두서가 없거나 매우 짧음
0: 내용을 파악하기 어려움

[추가 기록]
- quote: 2차 콘텐츠(광고·인스타)에 그대로 쓸 만한 본문 원문 1~2문장. 학습 효과나 깨봉다운 메시지가 드러나는 문장 우선. 아이 실명 등 개인정보는 "아이"로 바꾼다. 마땅한 문장이 없으면 빈 문자열.
- flags: 확실한 경우에만 아래 값을 넣는다. 애매하면 넣지 않는다.
  - "사실 오류": 깨봉에 대한 설명(과정명·서비스 방식 등)이 본문 안에서 명백히 틀리거나 앞뒤가 모순됨
  - "고지 누락": 원고료·제품 제공·활동 혜택을 받은 정황이 있는데 협찬/제공/활동 고지 문구가 없음

[출력 형식] JSON만 출력
{"scores": {"experience": 0, "evidence": 0, "message": 0, "info": 0, "completeness": 0},
 "rationale": {"experience": "근거 인용 포함 한 줄", "evidence": "...", "message": "...", "info": "...", "completeness": "..."},
 "quote": "...",
 "flags": []}

[후기 제목]
{title}

[이미지 수]
{images}

[후기 본문]
{body}
"""


def _extract_json(text):
    """응답에서 JSON 객체 추출 (코드펜스·설명문 허용). 없으면 None"""
    text = re.sub(r"```(?:json)?", "", text or "")
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text[m.start():])
            if isinstance(obj, dict):
                return obj
        except ValueError:
            continue
    return None


def _short_error(e):
    """예외를 비고·요약에 넣기 좋은 짧은 사유로 변환"""
    status = getattr(e, "status_code", None)
    if status:
        return f"{type(e).__name__} {status}"
    return (str(e).split("(")[0].strip() or type(e).__name__)[:60]


def normalize(data):
    """모델 응답을 검증·정리. 지표가 하나라도 없으면 ValueError"""
    raw = data.get("scores") or {}
    scores = {}
    for key, _ in METRICS:
        if key not in raw:
            raise ValueError(f"지표 누락: {key}")
        scores[key] = max(0, min(100, int(round(float(raw[key])))))  # 0~100 정수로 보정
    rationale = {k: str((data.get("rationale") or {}).get(k, "")).strip() for k, _ in METRICS}
    flags = [f for f in (data.get("flags") or []) if f in FLAG_OPTIONS]
    return {"scores": scores, "rationale": rationale,
            "quote": str(data.get("quote") or "").strip(), "flags": flags, "error": ""}


def score_review(title, body, images=0, api_key=None):
    """
    블로그 본문 채점. 반환: dict(scores, rationale, quote, flags, error)
    실패 시 scores=None, error=사유
    """
    empty = {"scores": None, "rationale": {}, "quote": "", "flags": [], "error": ""}
    if not api_key or not body:
        return {**empty, "error": "API 키 또는 본문 없음"}
    import anthropic  # 채점할 때만 임포트

    client = anthropic.Anthropic(api_key=api_key)
    prompt = (SCORE_PROMPT.replace("{title}", title or "")
              .replace("{images}", str(images))
              .replace("{body}", body[:SCORE_BODY_LIMIT]))
    last_error = None
    for attempt in range(2):  # 1회 재시도
        try:
            msg = client.messages.create(
                model=SCORE_MODEL,
                max_tokens=2000,
                system="You are a strict, consistent grader. Reply with a single JSON object only.",
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text")
            data = _extract_json(text)
            if data is None:
                raise ValueError(f"JSON 없음 (stop_reason={getattr(msg, 'stop_reason', '?')}, 응답앞부분={text[:150]!r})")
            return normalize(data)
        except Exception as e:
            print(f"  [WARN] 채점 실패({attempt + 1}/2): {e}")
            last_error = e
            time.sleep(2)
    return {**empty, "error": _short_error(last_error)}


# ---------------------------------------------------------------------------
# 노션 반영·요약용 계산 (노션 수식과 동일한 규칙)
# ---------------------------------------------------------------------------
def average(scores):
    """5개 지표 평균 (소수 첫째 자리)"""
    return round(sum(scores[k] for k, _ in METRICS) / len(METRICS), 1)


def stars(avg):
    """평균 ÷ 20을 0.5 단위로 반올림한 별점 문자열 (노션 '후기 평가도' 수식과 동일)"""
    half_steps = int(avg / 10 + 0.5)          # = round(avg/10), 0.5는 올림
    full, half = divmod(half_steps, 2)
    return "★" * full + ("½" if half else "") + f" ({half_steps / 2:g})"


def is_excellent(scores):
    """우수: 평균 75점 이상"""
    return average(scores) >= 75


def is_reuse_candidate(result):
    """2차 활용 후보: (효과 근거 + 메시지 적합성) ÷ 2 ≥ 75 이고 인용 문장 있음"""
    s = result["scores"]
    return (s["evidence"] + s["message"]) / 2 >= 75 and bool(result["quote"])


def rationale_text(result):
    """채점 근거 컬럼용 텍스트 (지표별 한 줄)"""
    s, r = result["scores"], result["rationale"]
    return "\n".join(f"{name} {s[key]}: {r.get(key, '')}" for key, name in METRICS)


def score_properties(result, rt):
    """채점 결과 → 노션 속성 페이로드 (rt: rich_text 생성 함수)"""
    props = {name: {"number": result["scores"][key]} for key, name in METRICS}
    props["채점 근거"] = rt(rationale_text(result))
    props["인용 문장"] = rt(result["quote"])
    props["검토 필요"] = {"multi_select": [{"name": f} for f in result["flags"]]}
    props["채점일"] = {"date": {"start": datetime.now().strftime("%Y-%m-%d")}}
    return props
