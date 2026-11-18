# 트랙 44: 스태프 게시물(행사)의 다국어 자동 등록 (2026-10-21) [v1 — **사용자 승인 완료(2026-10-24)**. PSO·DAR·AAA·SRR·DOR 사전 검토 통합(§2), 44-1 확정 설계·Test List는 §10. 44-1은 PR #399로 머지 완료(2026-10-27, main `e38a0db9` [실측 gh]), 44-2·44-3·44-4는 미착수] · **폐기(2026-11-18)**: 미착수 슬라이스 44-2·44-3·44-4는 폐기한다 `[문서 사용자 지시 2026-11-18 "열린 트랙 폐기. 작업 혼동 가능성."]`. 머지된 44-1은 그대로 유효하다. 이 절은 실행 계획이 아니라 기록이다.

> **출처**: 사용자 요청(2026-10-21) "스태프가 생성하는 게시물도 자동으로 4가지 언어가 등록되어야한다." 같은 메시지의 "번역검수는 AI로만 할것이다"는 트랙 43-1 UI 문구 검수 지시이며 §8에 처리 결과를 적었다.
> **기준선**: PR #395가 머지돼(2026-10-21 13:02Z [실측 gh]) main 기준으로 시작한다. 44-1 착수 때 전체 회귀를 다시 잰다(마지막 측정 3254 passed / 10 deselected [실측 2026-10-21 main 8b7a9458]).
> **오케스트레이터 재확인**: 사전 검토 인용의 file:line은 소스로 대조했고 틀린 주장은 §7에 기록했다 [실측 rg·sed 2026-10-21]. 게시 이벤트 수·글자 수는 검토 역할 중 아무도 재측정하지 못해 오케스트레이터 실측값만 쓴다.

## 1. 요청 해석과 범위

- **대상**: `Event`의 자유 텍스트 필드 `title`·`work_title`·`location_name`·`summary`를 en·ja·zh-hans로 옮긴다. 한국어가 원문이다 [코드 events/models.py:14-23].
- **"자동"의 뜻**: 스태프의 추가 조작이 없다는 뜻이다. "게시 즉시"는 보장하지 않는다. 실행 주체가 러너라 러너가 켜져 있는 동안 채워진다.
- **쓰기 경로는 서비스 함수 둘뿐이다**: `create_published_event`(events/services.py:172)와 `update_published_event`(:219). 호출자는 스태프 생성(staff/views/events.py:424)·수정(:499)·초안 승인(drafts/services.py:363)이다 [코드].
- **제외**: `category`·`region`·`source_name`(어휘·출처명), 공개 API·JSON-LD·검색·사이트맵(44-2 이후), 법률 문서, 건별 사람 검수(사용자가 배제).
- **[2026-10-22 사용자 결정으로 범위 편입] `Category.label`**: 스태프가 새로 만드는 카테고리도 자동으로 en·ja·zh-hans가 등록돼야 한다(사용자: "새로운 카테고리가 생기면 그것도 자동으로 4가지의 언어로 등록이 되어야"). 초안의 "제외"는 폐기한다. 설계는 §4-1에 적었다.
- **규모 [실측 Django shell 2026-10-21]**: 게시 172건, 요약 보유 52건, 평균 글자 수 42.9자(제목 16.3·작품명 1.6·장소 7.6·요약 17.4), 최근 30일 신규 0건.

## 2. 사전 검토 수렴 (PSO·DAR·AAA·SRR·DOR 일치)

- **D1 실행 주체 = A 로컬 러너(사용자 맥 `claude` CLI)**. 서버에는 LLM 호출 코드도 키도 두지 않는다. 사유는 2026-07-04 사용자 결정(LLM API 불허, 메모 cost-constraint)이며 해제할 수 있는 사람은 사용자뿐이다. 서버 직접 호출(B)은 후보에서 뺐고, 포트 추상화(C)는 구현이 하나뿐이라 과설계로 기각했다(DAR·AAA).
- **D2 저장 = `Event.text_translations` JSONField**(`default=dict`, `AddField` 하나, 기존 0004·0006 선례 [코드 events/migrations]). 조인과 추가 쿼리가 없다. 한 이벤트의 모든 언어를 한 번에 제출받아 `select_for_update`로 한 번만 쓴다(부분 제출 금지, lost-update 방지).
- **D3 트리거 = 쓰기 훅 없음**. "번역이 없거나 `source_hash`가 현재 원문 해시와 다름"을 읽는 시점에 계산해 큐로 쓴다. 두 서비스 함수는 한 줄도 바꾸지 않으므로 번역 실패가 게시를 막을 수 없다는 요구가 구조로 성립한다(DAR). 동기 호출은 gunicorn 워커 점유(백로그 G2와 같은 축), 데몬 스레드는 서버 production 선례가 없고 재시작 때 유실되어 기각했다(DOR).
- **D4 최신성**: 해시가 다르면 번역을 버리고 한국어 원문을 `lang="ko"`로 보인다. 스태프가 수동 수정한 번역(`manual=true`)은 재번역에서 영구 제외한다.
- **D6 범위 = Event 텍스트 필드만**. 변경 소유는 `events` 안 새 모듈(해시·신선도·노출 선택 순수 함수, 제출 서비스 함수 하나)이다.

## 3. 사용자 결정 (이의 없으면 아래 기본값으로 44-1 착수)

1. **D1**: 러너 방식으로 확정할지. 기본값 = 확정. 서버 API를 원하면 비용 정책 해제를 사용자가 직접 승인해야 하고, 그때의 비용 상한은 이벤트 1건당 Opus 0.0289달러·Sonnet 0.0144달러·Haiku 0.00047달러, 기존 172건 일괄 Opus 4.96달러·Sonnet 2.48달러·Haiku 0.08달러다 [계산·상한 가정: 한글 2토큰/글자, 사고 토큰 1000개/건, 요금표 2026-10-06 캐시. AAA는 번역에 사고가 불필요할 수 있어 과대추정 가능성을 지적].
2. **러너 꺼짐 중 동작**: 방문자는 한국어 원문을 본다. 알림 채널(SMTP·유료 서비스)이 없어 스태프 대시보드의 "번역 대기 N건"(44-3)이 유일한 감지 경로다. 기본값 = 수용.
3. **`Category.label`**: **[2026-10-22 사용자 결정 — 편입으로 확정]** 새 카테고리 라벨도 같은 러너 파이프라인으로 자동 번역한다. 이 항목은 더 묻지 않는다. 남은 확인은 저장 위치·시드 카테고리 우선순위·언어 내 중복 처리 세 가지 기본값이며 §4-1에 있다 [문서 §4-1].

## 4. 44-1 설계 (백엔드 + 러너)

- **러너 API**: `events/runner_urls.py`·`runner_views.py`를 신설한다(`drafts` 임포트 금지). 인증·스로틀(drafts/runner_views.py:42-70 [코드])은 두 번째 소비자가 생기므로 `core/runner_auth.py`로 올려 두 앱이 공유한다. 엔드포인트는 대기 목록(원문 필드 + `source_hash`, 건수 상한)과 제출(`event_id`·`source_hash`·언어별 번역) 둘이다.
- **제출 검증(서버)**: `source_hash` 불일치 거부(경합), 스키마·필드별 길이 상한, 번역문에 원문에 없는 HTML 태그·URL·이메일 출현 금지, 숫자·날짜 보존 대조, 목표 언어의 문자 블록 포함 여부(한국어가 그대로 나오면 해당 언어 격리), 성공 제출마다 감사 로그 한 행. 원문·번역문은 로그에 남기지 않는다(`drafts/llm_extraction.py:252-254` 패턴).
- **러너 측**: 번역 호출의 `--tools`는 이중 이름 관례(`TodoWrite,TodoWrite` 형태)와 `strict_mcp=True`로 고정하고 핀 테스트를 둔다. 프롬프트는 외부 본문을 데이터 구획 안에 넣는 `drafts/llm_extraction.py` 패턴을 따른다. 러너는 Django를 임포트하지 않는다.
- **경계 가드 신설**: `events`가 `core.llm`을 임포트하면 실패하는 테스트(AAA·DAR). 서버에 동기 LLM 호출이 조용히 들어오는 것을 막는다.
- **백필**: 큐가 계산이라 별도 재큐가 필요 없고 러너를 켜면 기존 게시 172건 [실측]도 처리된다. 관리 명령은 `--dry-run`으로 대기 건수만 보고한다.
- **문서**: `docs/BE/i18n.md` 가드레일 11("번역 문자열을 DB에 저장하지 않는다")은 요청자 언어에 따라 달라지는 gettext 결과를 뜻하므로 "언어를 키로 명시 저장하는 콘텐츠 번역은 별개 데이터"로 좁힌다(SRR High). 런북에는 마이그레이션 역적용 시 번역 데이터가 전량 사라진다는 경고와 러너 절차를 넣는다(DOR).

### 4-1. 새 카테고리 라벨 자동 번역 (2026-10-22 사용자 결정, 계획 초안 — 사전 검토 전)

- **현재 상태(43-2, PR #396)**: 시드 카테고리 7개 [코드 core/vocab.py]는 gettext 카탈로그(AI 검수)가 번역한다. DB에만 있는 새 카테고리는 필터 체크박스·홈 타일에서 한국어 라벨 + 조건부 `lang="ko"`로 보이고, 목록 행·상세·적용 칩은 슬러그가 그대로 나온다 [코드 web/views/_helpers.py:61]. 새 카테고리는 스태프 화면의 `Category.objects.create(slug=slug, label=label)`로만 생긴다 [코드 staff/views/categories.py:130].
- **저장 위치 기본값**: `Category.label_translations` JSONField(`{언어: {"text", "source_hash"}}`, `default=dict`), `Event.text_translations`와 같은 형식·같은 해시 규칙(D2·D4)이다. 라벨이 짧아(최대 64자 [코드 core/models.py:49]) 제출은 카테고리 단위 한 번이다.
- **큐·실행 기본값**: 쓰기 훅 없이 읽기 시점에 계산한다(D3). 시드 7개처럼 카탈로그가 이미 번역한 라벨(`gettext(label) != label`)은 큐에서 제외해 카탈로그(검수 완료)가 항상 우선한다. 러너 API·검증·감사 로그는 이벤트와 같은 모듈을 쓰고, 제출 검증에 "한 언어 안에서 다른 카테고리와 번역이 같으면 격리"를 더한다(같은 언어 필터에서 두 체크박스가 같은 이름이 되는 것을 막는다).
- **표시 규칙**: 번역이 있고 해시가 현재 라벨과 같으면 번역을 보이고 `lang="ko"`를 붙이지 않는다. 없거나 낡았으면 지금처럼 한국어 + 조건부 `lang="ko"`다(43-2 동작 그대로).
- **같은 슬라이스에서 고칠 기존 결함**: 새 카테고리가 행·상세·칩에서 슬러그로 나오는 문제는 번역된 라벨이 어디에도 보이지 않게 만들므로 이 슬라이스에서 라벨 조회로 바꾼다. 사용자 결정(2026-08-25 같은 유형 소규모 결함 즉시 수정)과 맞는다.
- **개인 항목 제안 칩은 이 트랙이 아니다**: `PERSONAL_ENTRY_CATEGORY_SUGGESTIONS`는 `Category` 행이 아니라 코드 상수라 43-3에서 카탈로그로 번역한다(사용자 결정 2026-10-22).

## 5. 슬라이스와 수용 기준

- **44-1** 저장·해시·선택 함수·러너 API·검증·감사·`core` 인증 승격·가드·명령·문서. **44-2** 공개 화면 노출(목록·상세·홈·달력). 43-2가 같은 템플릿의 UI 문구를 바꾸므로 43-2 머지 뒤에 착수한다(PSO). **44-3** 스태프 상태 표시·다시 번역. **44-4** 새 카테고리 라벨 자동 번역(§4-1) — 44-1의 러너 API·검증·감사를 재사용하므로 44-1 뒤에 둔다.
- **AC1** 번역기 불가·시간 초과여도 생성·수정·초안 승인은 성공한다. **AC2** 러너 가동 중 처리하면 서버 검증 규칙을 통과한 언어가 모두 채워진다(규칙에 걸린 언어는 `null`로 격리되고 한국어 원문이 보이며, 격리 언어의 복구는 원문 변경 또는 44-3의 "다시 번역"이다. 2026-10-26 QVL 권고로 문구를 좁혔다). **AC3** 러너가 꺼졌거나 번역이 없거나 낡았으면 한국어 원문이 `lang="ko"`로 보이고 빈 필드·깨진 문자열은 없다. **AC4** 44-2에서 번역문이 보이는 모든 위치에 "AI 번역" 표시와 원문 보기가 붙는다. **AC5** 재실행은 이미 번역된 항목을 다시 처리하지 않는다. **AC6** 44-1에서 공개 API·JSON-LD·검색·사이트맵 응답은 변경 전과 같다.

## 6. 보안·운영 조건

- 러너 토큰은 단일 공유 비밀이고 범위 구분이 없다 [코드 drafts/runner_views.py:42-49]. 토큰이 새면 공개 번역문을 바꿀 수 있으므로 해시 대조·감사 로그·길이·URL 검증이 방어선이다. 토큰 읽기·쓰기 분리는 사용자 결정 후보로 남긴다(SRR).
- `summary`·`title`은 외부 웹 본문이 정제되어 들어온 신뢰할 수 없는 입력이다. 번역이 오염된 원문을 더 자연스럽게 만들 위험이 있어 위 검증이 필수다(PSO·SRR).
- 마이그레이션은 단일 `AddField`이고 컨테이너 기동 시 자동 실행된다 [코드 docker/entrypoint.sh:4-8]. 코드만 이전 이미지로 롤백하는 것은 안전하고 스키마 역적용만 위험하다(DOR).
- 번역은 러너의 `claude` CLI 구독으로 처리하므로 서버 비용은 없다. 평가는 기존 게시 이벤트를 입력으로 쓰고 게이트 통과율로 자동 채점한다. AAA 권고 임계는 통과율 95% 이상과 임의 20~30건 수작업 평균 4점 이상이며 [문서 AAA 보고], 자동 등록 허용 임계는 제품 결정이다.

## 7. 정정 기록

1. 브리프의 "홈 쿼리 수를 지키는 기존 테스트가 있다"는 틀렸다. `tests`에 홈을 대상으로 한 쿼리 수 단언이 없고 트랙 17의 홈 쿼리 단축은 구현되지 않았다 [실측 rg, DAR 지적을 오케스트레이터가 재확인]. JSON 컬럼의 추가 쿼리가 없다는 장점은 유효하되 "지킬 기존 테스트"는 없다.
2. SRR의 "Critical: `--tools` 단일·빈 값이면 도구 제한이 풀려 착수 불가"는 함정은 사실이나 신규 위험은 아니다. 어댑터 주석에 실측 함정으로 이미 기록되어 있고 기존 호출자 둘이 `WebSearch,WebFetch`·`TodoWrite,TodoWrite`로 피하며 핀 테스트가 있다 [코드 local_runner/claude_code_adapter.py:151-166, local_runner/caption_interpreter.py:163, tests/local_runner/test_claude_code_adapter.py:233-244]. 신규 번역 호출이 같은 관례와 자체 핀 테스트를 따른다는 요구사항으로 낮춘다.
3. 비용표의 사고 토큰 가정은 상한이다. 번역은 확장 사고가 필요 없을 수 있어 서버 API를 택하면 다시 계산한다(AAA).
4. 게시 이벤트 수 등 수치는 DAR·PSO·DOR가 재측정하지 못했다. §1 수치는 오케스트레이터 실측이다.

## 8. 같은 메시지의 "번역검수는 AI로만" 처리 (트랙 43-1)

영어·일본어·중국어 독립 AI 검수자가 각자 카탈로그 전체를 읽었다. 제안 중 구조(자리표시자·태그·개행) 검증을 통과한 것을 반영했다. 반영 건수는 일본어 19건, 중국어 30건, 영어 35건이다 [실측 apply_review.py 출력 2026-10-21]. 번역으로 풀리지 않는 문맥 4건(찜·기록·종료·단위 복수형)은 코드로 고쳐 커밋했다(단위는 `npgettext`, 같은 글자의 품사 분리는 `msgctxt`). 변이 테스트로 Red를 확인했고 WED·BIR 사후 판정은 모두 Conforms이며 전체 회귀는 3254건 통과했다 [실측 uv run pytest -q 2026-10-21]. 원어민 사람 검수는 하지 않았다는 사실은 `docs/BE/i18n.md`에 위험으로 남겼다.

## 9. 역할

PSO(범위)·DAR(스키마·경계)·AAA(번역 자동화·게이트)·SRR(신뢰 경계)·DOR(마이그레이션·운영) 사전 검토 완료. 44-1 착수 시 백엔드 TDD 코치 계약, 구현 엔지니어, QVL, 러너 쪽은 SRR 페어. 44-2 착수 시 WED·BIR 사전·사후 산출물.

## 10. 44-1 확정 설계 v1 (2026-10-24, 사용자 승인 후)

> **사용자 승인**: 2026-10-24 "트랙 44 진행하도록." — §3 기본값(D1 러너 확정, 러너 꺼짐 중 한국어 폴백 수용, `Category.label` 편입)으로 44-1에 착수한다. 구현 브랜치 `feat/i18n-event-content-44-1`(main `adffc819`). 기준선은 전체 회귀 3985 passed / 10 deselected / 136.72초 [실측 uv run pytest -q 2026-10-24]. PR은 44-1 하나로 한다(사용자 규약: 슬라이스당 PR 하나, 후속·증식 지양). 코치의 PR 2분할 권고는 채택하지 않고 커밋 묶음 순서만 채택했다.

### 10-1 활성 역할

Activated: Product Scope Owner(v0, 2026-10-21), Domain Architecture Reviewer(v0 + 2026-10-24 재검토), Backend TDD Coach(2026-10-24 판정 두 차례), Backend & Integration Engineer(구현), Security & Resilience Reviewer(v0 + 2026-10-24 재검토), Deployment & Operations Reviewer(v0, 마이그레이션·런북), AI Automation Architect(v0, 번역 프롬프트·게이트), Quality Verification Lead(사후). Not Activated: Web Experience Designer·Browser Interaction Reviewer·Frontend Implementation Engineer(44-1은 화면 변경이 없다).

### 10-2 2026-10-24 사전 검토에서 설계가 바뀐 것

- **코치 판정 채택**: 데이터 모양(O1)·해시(O2)·큐 계산(O3)·엔드포인트 계약(O4)·검증 우선순위(O6)·Tidy First 인증 승격(O5)·첫 실패 테스트 TR-02.
- **오케스트레이터가 소스로 재현해 고친 코치안 두 곳**: 숫자 다중집합 동일 규칙은 정상 번역을 거부한다(원문 "2026 도쿄 코믹마켓 10월 24일" ↔ 번역 "Tokyo Comic Market, October 24, 2026"에서 숫자 `10`이 단어가 된다 [실측 python3]). 일본어 "가나 없으면 격리"는 `東京` 같은 한자 전용 지명을 거부한다 [실측 python3]. 코치가 개정 단계에서 평가 순서·천단위 구분자 빈틈을 추가로 짚었고 모두 채택했다.
- **DAR 판정 반영(결함 1건)**: 번역 러너가 `discovery_runner` 스로틀 버킷(60/minute [코드 config/settings.py:628])을 같이 쓰면 탐색 run의 하트비트·후보 제출 폭주 때 서로 예산을 깎는다. 새 scope `translation_runner`를 설정 한 줄로 둔다. 모듈 이름은 앱 관례(앱당 `services.py` 하나, `drafts`는 능력 이름)에 맞춰 `events/translation_queue.py`로 바꾼다. 러너 클라이언트는 기반 클래스 없이 독립 `TranslationRunnerClient`로 둔다(Pythonic Code Design의 broad base class 회피, `_post` 중복은 세 번째 반복 전까지 둔다). AC1 계약의 검사 대상에 `events/signals.py`·`events/apps.py`·`events/models.py`를 더해 44-3에서 신호로 번역 호출이 숨어드는 길을 막는다.
- **SRR 판정 반영**: 번역문 저장 전 NFC 정규화(NFD 한글이 음절 블록 검사를 우회함 [실측 python3]), Cf(방향 제어·제로폭)·NUL 처리(기존 `sanitize_text`는 Cc만 거른다 [코드 drafts/candidate_validation.py:104-105]), 길이 상한 확정, 감사 로그에 사유 코드·요청 IP 포함·WARNING 분리, 러너 프롬프트에 구획 종료 리터럴 스트립 복제(`drafts/llm_extraction.py:108-113` 패턴), 관리 명령에 격리 언어 집계.
- **사용자 정정(2026-10-24 "1000원 = 약$1 달러야")**: 천단위 구분자 예시로 든 `50000원 ↔ $50,000`은 틀린 예시였다(환율이 1,000원 ≈ $1이면 50,000원은 약 $50). 숫자만 비교하는 규칙은 기호만 바뀐 `$50,000`을 통과시키므로, 원문에 없는 통화 기호·코드가 번역에 나오면 격리하는 규칙(`currency_changed`)을 더하고 프롬프트에 환산 금지 지시를 둔다. 환산한 "약 $50"은 지어낸 숫자로도 격리된다.
- **오케스트레이터가 추가한 결함 방지**: 서버가 전체 거부를 돌려주면 이벤트가 큐에 남아 러너가 20초마다 같은 이벤트를 다시 번역·제출한다. 러너는 같은 (이벤트, 해시)가 두 번 거부되면 프로세스 생존 중 다시 시도하지 않는다. 번역 단계는 하트비트 티커 안에서 돈다(대시보드 신선도 기준 120초 [코드 drafts/discovery_runs.py:15]). 러너 진행 단계 어휘는 서버와 문자 그대로 같아야 하는 동등 가드가 있어 [코드 local_runner/progress.py:10] 44-1에서 새 단계를 만들지 않는다.
- **수용하는 잔여 위험(사용자 결정 "건별 사람 검수 배제"의 결과)**: 자동 규칙은 의미 충실성을 검증하지 못한다. 숫자·태그가 없는 임의의 문장이 토큰 유출 시 통과한다. 방어선은 토큰 비밀·격리 로그·44-2의 "AI 번역" 표시다. 토큰 읽기·쓰기 분리는 이 슬라이스의 선결 조건이 아니다(기존 단일 토큰이 이미 읽기·쓰기를 겸한다 [코드 drafts/runner_views.py:100-243]).

### 10-3 확정 규칙

- **저장 모양**: `text_translations = {"source_hash": "<sha256 hex>", "manual": false, "en": {"title","work_title","location_name","summary"} 또는 null, "ja": …, "zh-hans": …}`. 격리된 언어 칸은 `null`이고 표시는 한국어 폴백이다. 원문 필드가 빈 문자열이면 번역도 빈 문자열이다. 번역문은 NFC로 저장한다.
- **해시**: 4필드를 NFC 정규화하고 `\x1f`로 결합해 sha256 hex. 4필드 외 변경(view_count 등)에는 불변.
- **큐**: `Event.objects.published()`만, 엔트리가 없거나 `source_hash`가 현재 해시와 다른 이벤트, `manual`이면 제외, `id` 오름차순, 한 응답 최대 20건. 격리된 언어가 있어도 해시가 같으면 큐에 오르지 않는다(무한 재시도 없음). 격리 언어의 재시도는 원문 변경 또는 44-3의 "다시 번역"뿐이다.
- **엔드포인트**: 마운트 `api/translation/runner/`(`config/urls.py`, 공개 `api/events/`와 분리). `pending/`·`submit/` 모두 POST, `core/runner_auth.py`의 인증·스로틀(scope `translation_runner`)을 쓴다. pending 응답은 `{"events": [{"event_id","source_hash","fields":{4필드}}]}`이고 대기가 없으면 200과 빈 목록이다. 제출 본문은 `{"event_id","source_hash","translations":{"en":{4필드},"ja":{…},"zh-hans":{…}}}`이다.
- **전체 거부(아무것도 쓰지 않음)**: 키 집합·타입이 어긋남 또는 NUL 포함은 400, `source_hash` 불일치는 409(`stale_source`), `manual` 이벤트는 409(`manual_locked`), 없거나 비게시 이벤트는 404. 러너는 `null`을 보낼 수 없다(격리는 서버만 만든다).
- **언어 격리(해당 언어만 `null`, 사유 코드)**: 한 언어 안에서 평가 순서는 ① 제어 문자(Cc, `\n`·`\t` 제외)·Cf 포함(`control_char`) ② 길이(`too_long`) ③ 원문에 없는 HTML 태그·URL·이메일(`unexpected_markup`) ③' 원문에 없는 통화 기호·코드(`$`·`US$`·USD·€·EUR·£·GBP·¥·JPY·CNY·円)가 번역에 나옴(`currency_changed`) ④ 숫자(`number_invented`·`number_missing`) ⑤ 빈 칸 규칙(`empty_translation`·`nonempty_for_empty_source`) ⑥ 한글 잔존(`hangul_residue`, NFKC 후 음절·자모 블록 전부) ⑦ 원문이 ASCII뿐이고 번역이 같으면 세 언어 모두 통과 ⑧ 언어별 문자 판정(`wrong_script`: en은 라틴 문자 필수, ja는 가나 필수이되 NFKC 공백 제거 후 10자 이하면 한자만도 통과, zh-hans는 한자 필수·가나 금지). 간체와 번체는 문자 블록으로 구분할 수 없어 프롬프트의 간체 지시에 맡긴다.
- **숫자 규칙**: NFKC 후 숫자 사이 쉼표를 제거하고 `\d+`를 뽑는다. 번역의 숫자 집합은 원문 숫자 집합의 부분집합이어야 하고, 원문의 4자리 이상 숫자는 번역에 모두 있어야 한다. 4자리 미만 숫자의 누락은 의도적으로 허용한다(날짜는 구조화 필드 `start_date`·`end_date`에 있다). 원화 금액은 환산하지 않고 "KRW 50,000"처럼 원화 그대로 옮긴다(예: 50000원 ↔ KRW 50,000 통과, `$50,000`은 `currency_changed`, 환산한 "약 $50"은 `currency_changed` 또는 `number_invented`로 격리). "5만원"→"KRW 50,000" 같은 단위 풀어쓰기도 지어낸 숫자로 격리되며 알려진 한계다.
- **길이 상한 [문서 설계값, 미측정]**: `title`·`work_title`·`location_name` 400자, `summary` 2000자, 그리고 번역(NFKC 공백 제거)이 `max(40, 6 × 원문 길이)`자를 넘으면 격리한다. 상한 위반은 전체 거부가 아니라 언어 격리다(전체 거부는 러너 재시도 루프를 만든다).
- **성공 응답**: 200 `{"status": "saved" | "already_current", "saved": [언어], "quarantined": {언어: 사유}}`. 저장된 `source_hash`가 제출 해시와 같고 엔트리가 이미 있으면 덮어쓰지 않고 `already_current`다. 쓰기는 `select_for_update` 트랜잭션 한 번이다.
- **감사 로그**: 제출마다 로거 한 줄. 성공 INFO, 격리·거부 WARNING. 이벤트 id·결과·언어 목록·사유 코드·해시 앞 8자·`core.ip.get_client_ip` 결과를 남기고 원문·번역문·토큰은 남기지 않는다.
- **러너(`local_runner/translation_flow.py`)**: `claude` CLI 호출은 `--tools TodoWrite,TodoWrite`·`--strict-mcp-config`로 고정하고 핀 테스트를 둔다. 원문은 데이터 구획 안에 넣고 구획 종료 리터럴을 지운다. 프롬프트는 간체 지시, 통화 환산 금지 지시(원화는 원화 그대로), 세 언어·네 필드 JSON 스키마를 담는다. 비 JSON 출력은 교정 접미사로 한 번만 재시도한다(`caption_interpreter.py` 패턴). 폴링 한 번에 처리하는 이벤트 수·호출 시간 상한·같은 이벤트의 재시도 상한은 [문서 설계값, 미측정]으로 각각 3건·120초·2회다. 폴링 루프는 폴링이 성공한 반복마다 번역 단계를 돌리고(탐색 run을 처리한 반복 뒤에도 돈다 — 단일 스레드 순차 실행이라 동시 실행은 없다) 그 단계의 실패가 루프를 멈추지 않는다. (2026-10-26 전수검사에서 "탐색 run이 없을 때만"이던 문구를 코드 `local_runner/runner.py`·`docs/BE/i18n.md`·테스트 `tests/local_runner/test_translation_runner_step.py`와 일치하도록 정정.)

### 10-4 파일

서버: `core/runner_auth.py`(신설), `drafts/runner_views.py`(import 교체), `events/models.py`, `events/migrations/0008_*.py`, `events/content_translation.py`(순수: 해시·검증·노출 선택), `events/translation_queue.py`(DB: 큐 조회·제출·감사 로그), `events/runner_views.py`, `events/runner_urls.py`, `config/urls.py`, `config/settings.py`(scope 한 줄), `events/management/commands/report_translation_queue.py`. 러너: `local_runner/translation_flow.py`, `local_runner/client.py`(독립 클래스 추가), `local_runner/runner.py`. 테스트: `tests/events/test_content_translation_*.py`, `tests/events/test_translation_queue*.py`, `tests/events/test_translation_runner_api.py`, `tests/local_runner/test_translation_*.py`, `tests/core/test_architecture_boundaries.py`. 문서: `docs/BE/i18n.md`(가드레일 11 문구 조정, 44-1 절), `docs/deploy-runbook.md`(마이그레이션 역적용 시 번역 데이터 전량 소실 경고, 러너 번역 절차), `docs/backlog.md`.

### 10-5 커밋 묶음과 Test List(코치 TR 번호 유지, 신규 번호는 오케스트레이터 보충)

묶음 순서는 ①인증 승격(Tidy) ②모델·해시 ③검증 ④큐·제출 서비스 ⑤러너 API ⑥러너 쪽 ⑦가드·명령·문서다. 각 묶음의 첫 실패 테스트는 TR-02·TR-05·TR-06·TR-14·TR-35·TR-33이고 ①은 Red 없이 기존 러너 테스트를 한 글자도 바꾸지 않고 Green으로 유지한다(TR-13). TR-14의 첫 Red 이유는 경로 부재로 인한 404이며, 이것을 의도한 Red로 인정한다. 표의 건수 표기 외 숫자는 [문서 설계값]이고 테스트 수는 구현 뒤 [실측]으로 대체한다.

| 묶음 | 테스트 ID와 행동 | 계층 |
|---|---|---|
| ② | TR-01 같은 4필드면 해시 같음 · TR-02 4필드 외 변경에는 불변 · TR-03 필드 경계 이동 시 변경 · TR-02b NFC·NFD 같은 글자는 같은 해시 · TR-02m 새 이벤트의 `text_translations` 기본값은 빈 dict [문서 설계값] | unit·domain |
| ③ | TR-05 언어 하나만 제출하면 전체 거부 · TR-16 키·타입 오류 전체 거부 · TR-16b NUL 전체 거부 · TR-17 원문에 없는 태그·URL·이메일 격리(원문에 있던 것은 통과) · TR-18 숫자 부분집합 통과("10월"→October) · TR-18b 지어낸 숫자 격리 · TR-18c 4자리 이상 누락 격리 · TR-18e 전각 숫자 · TR-18f 작은 숫자 누락 허용 핀 · TR-18g 쉼표 천단위 통과(50000원 ↔ KRW 50,000) · TR-18h 통화 기호만 바뀐 번역(`$50,000`) 격리 · TR-18i 원문에 `$`가 있으면 번역의 `$`는 통과 · TR-18j 환산한 "약 $50" 격리 · TR-19 ja 가나·한자 모두 없으면 격리 · TR-19b ja 10자 이하 한자만 통과 · TR-19c ja 11자 한자만 격리 · TR-20 zh-hans 가나 혼입 격리 · TR-20b 한자 없으면 격리 · TR-21 ASCII 원문 동일 번역 세 언어 통과 · TR-21c ASCII 우회가 문자 판정보다 먼저 · TR-26 한글 음절 잔존 격리 · TR-26b NFD 한글 잔존 격리 · TR-26c 저장은 NFC · TR-27c Cf 포함 격리 · TR-27d Cc 포함 격리(`\n` 제외) · TR-28c 절대 길이 초과 격리 · TR-28d 상대 길이 초과 격리 · TR-29c 빈 원문·빈 번역 규칙 · TR-34 노출 선택(해시 일치+번역이면 번역, null·불일치·언어 없음이면 원문) | unit |
| ④ | TR-04 빈 원문 필드는 빈 번역 · TR-06 비게시 제외 · TR-07 20건 상한 [문서 설계값] · TR-08 id 오름차순 · TR-27 manual은 큐에서 제외 · TR-28 manual 제출 거부 · TR-29 `already_current` 멱등 · TR-30 성공 제출 후 큐에서 빠짐 · TR-30b 격리 뒤에도 큐에 오르지 않음 · TR-31 원문 변경 시 큐 재진입 · TR-32 로그 INFO·WARNING 분리·원문·번역문·토큰 미포함·필수 필드 포함 · TR-33l 제출은 행 잠금(`FOR UPDATE`)으로 읽음 | domain |
| ⑤ | TR-14 토큰 없으면 403 · TR-14b 없거나 비게시 이벤트 제출 404 · TR-09 대기 없으면 200 빈 목록 · TR-09b pending 응답 모양 · TR-10 해시 불일치 409 · TR-11 한국어 그대로인 언어만 격리 · TR-12 전체 거부와 격리가 응답으로 구분됨 · TR-15 번역 러너와 드래프트 러너는 서로의 스로틀 예산을 쓰지 않음 · TR-15b 번역 scope 한도 초과 시 429 | web·contract |
| ⑥ | TR-35 `--tools` 이중 이름·strict MCP 핀 · TR-36 데이터 구획과 구획 종료 리터럴 스트립 · TR-36b 간체 지시·통화 환산 금지 지시·스키마 포함 · TR-37 출력 파싱 · TR-38 비 JSON은 교정 재시도 한 번 · TR-39 클라이언트 경로·헤더·토큰 미기록 · TR-40 번역 단계 실패가 폴링을 멈추지 않음 · TR-42 두 번 거부된 (이벤트, 해시)는 재시도 안 함 · TR-43 번역 단계가 하트비트 티커 안에서 돎 · TR-44 폴링당 처리 상한 · TR-45 호출 시간 상한 전달 | local_runner |
| ⑦ | TR-22 `events`는 `core.llm`을 임포트하지 않음 · TR-23 쓰기 경로(`events/services.py`·`drafts/services.py`·`events/signals.py`·`events/apps.py`·`events/models.py`)는 번역 모듈을 임포트하지 않음(AC1) · TR-24 공개 이벤트 API 키 불변(AC6) · TR-24b JSON-LD·검색·사이트맵 소스가 `text_translations`를 참조하지 않음(AC6) · TR-33 관리 명령 `report_translation_queue`는 대기 건수와 격리 언어 수를 보고하고 쓰지 않음(구현 때 쓰기 모드가 없어 `--dry-run` 인자를 두지 않았다) · TR-41 서버·러너 언어·필드 상수 동등(AST 추출, `test_phase_vocabulary_parity.py` 방식) | contract |

처음부터 Green일 수 있어 변이로 판별력을 확인할 테스트: TR-22(신설 모듈에 `core.llm` 한 줄), TR-23(`events/services.py`에 번역 모듈 한 줄), TR-24·TR-24b(`events/serializers.py` 필드 목록에 한 줄), TR-18f·TR-30b(해당 분기 제거). TR-13은 새 테스트가 아니라 기존 러너 테스트 재실행이다.

### 10-6 검증

묶음마다 해당 파일 단독 실행으로 Red→Green을 확인하고 묶음 끝에 전체 `uv run pytest -q`, 마지막에 `uv run pytest -q -m e2e tests/e2e`, `uv run python manage.py check`, `uv run python manage.py makemigrations --check --dry-run`을 실행한다. pytest는 오케스트레이터만 실행한다. 최종에는 러너 실기동으로 AC2를 확인한다(로컬 서버·로컬 DB의 시연 이벤트를 입력으로 실제 `claude` CLI를 호출해 세 언어가 채워지고 격리 사유가 기록되는지, 번역 게이트 통과율을 측정해 보고한다). AAA 권고 임계는 통과율 95% 이상과 수작업 표본 평균 4점 이상이며 [문서 §6], 자동 등록 허용 임계는 제품 결정이다.

### 10-7 경계·결합·파이썬 설계

- **Domain Boundary**: `events`가 `text_translations`의 해시·검증·큐·제출을 소유한다. `core/runner_auth.py`는 러너 신원 확인·속도 제한 하나만 소유하고 어떤 도메인 앱도 임포트하지 않는다(R1). `drafts`는 import만 교체한다. `local_runner`는 Django·서버 모듈을 임포트하지 않고 서버와는 AST 동등 테스트로만 묶인다. 금지: `events/services.py`·`drafts/services.py`·`signals`·`apps`·`models` → 번역 모듈, `events` → `core.llm`.
- **Coupling and Cohesion**: 번역 전용 모듈 분리로 기존 쓰기 경로와의 결합을 늘리지 않는다. 순수 규칙(`content_translation.py`)과 DB 쓰기(`translation_queue.py`)는 테스트 계층이 달라 분리하고, 큐 읽기는 `queries.py`(공개·스태프 읽기)에 넣지 않는다.
- **Pythonic Code Design**: DRF `BasePermission`·`ScopedRateThrottle` 재사용, 순수 함수는 값(dict·str)만 받고 모델을 모른다, 상수는 모듈 상단에 한 번, 새 기반 클래스·플러그인 구조 없음.

### 10-8 알려진 한계·이연

- 의미 충실성은 자동 검증 불가(10-2 잔여 위험). 간체·번체 구분 불가. 단위 풀어쓰기 숫자("5만원")는 격리된다.
- `manual` 플래그는 이벤트 단위 하나다. 언어별로 쪼갤지는 44-3 착수 때 사용자 재확인.
- 격리 언어는 44-3 전까지 영구 null이고 가시성은 로그와 관리 명령 집계뿐이다.
- 큐는 게시 이벤트를 파이썬에서 훑는다. 규모가 커지면 SQL로 갈아탄다(숫자 트리거는 주석만, 강제 안 함).
- 44-2로 넘길 조건: 번역문은 `|safe` 없이 렌더하고(계약 테스트), 44-2 SRR이 "사람 검수 없음 + 단일 토큰" 위험을 상속해 검토한다.

### 10-9 구현·검증 결과 (2026-10-26)

- **커밋과 회귀**: 묶음 ①~⑦, 실기동 오탐 보정, SRR 보강, 문서가 `adffc819` 위에 쌓였고 `git log --oneline adffc819..HEAD`로 확인한다 [실측 git]. 전체 회귀는 3985 → 4229 passed, 10 deselected, 128.91초 [실측 uv run pytest -q 2026-10-26], 증가 244건 [계산]. `manage.py check` 0건, 마이그레이션은 `0008_event_text_translations` 하나뿐 [실측].
- **변이 검증**: 분기마다 한 줄씩 깨뜨려 테스트가 Red가 되는지 영역별로 확인했다 [실측 변이 스크립트, 커밋하지 않음]. 당시 "동등 변이"로 적었던 1건(원본 마크업 토큰 검사 제거)은 전수검사에서 테스트 공백으로 정정됐다 — 전각 `＜b＞`→반각 `<b>`를 원본 검사가 격리하며, 이제 핀 테스트가 있다.
- **Red 기록 누락(정직 기록)**: 묶음 ①~⑦의 Red는 구현 중 관측했으나 묶음별 산출물을 보존하지 않았고, 테스트와 구현이 같은 커밋이라 git에서 재현할 수 없다. 전수검사 수정분부터는 묶음별 Red 출력을 보존했다(아래).
- **전수검사(2026-10-26, 7역할 병렬 + 오케스트레이터 재현)**: 운영 코드 결함 15건·가드/테스트 공백 12건·문서 오류 8건을 같은 PR에서 수정(사용자 승인, 결정 1~5는 권장안). 핵심 — 0008이 DB 기본값을 지워 구 코드 INSERT가 NOT NULL 위반(로컬 PG `column_default=None` [실측]) → `0009` RunSQL로 `'{}'::jsonb` 복구(적용 후 `'{}'::jsonb` [실측]); 빈 원문 조기 반환이 길이·제어문자 검사를 건너뜀; 외톨이 서로게이트(PG jsonb 거부 [실측]); 러너가 5xx·429를 이벤트 탓으로 집계; 드래프트 구획 리터럴 제거가 1,000,025자 중첩 입력에 43.57초 [실측] → 선절단; `select_display` 필드 누락 엔트리; 숫자 규칙 오탐(`2:00`·`03.15`·`5만원`)·URL 끝 구두점·`<Blue Archive>`(SRR 조건부 허용으로 완화); `_LATIN_RE`의 ×·÷; 어댑터 봉투 모양; 러너 이벤트별 로그; 스캐너가 `from X import Y` 별칭 미탐지. Red [실측 묶음별 pytest]: S 16 failed/119 passed, R 14/70, D 2/38, M 4/61(사유 전부 기대와 일치). Green 후 전체 회귀 4229 → 4284 passed, 10 deselected, 141.65초 [실측 uv run pytest -q 2026-10-26], 증가 55건 [계산]. Green-first 핀 변이 23건 전부 KILLED [실측 변이 스크립트, 커밋하지 않음](검색 2건은 스태프 필터를 잘못 겨눠 공개 검색 `events/querysets.py:32`로 재조준). `manage.py check` 0건, 드리프트 없음, 마이그레이션 `0008`·`0009` [실측]. 계획 §10-3 "탐색 run이 없을 때만"은 코드·문서·테스트("폴링 성공마다", 순차)에 맞춰 정정. 이연(트리거 포함)은 `docs/backlog.md` K절.
- **러너 실기동(AC2)**: 로컬 서버·로컬 DB(게시 172건)에서 실제 `claude` CLI로 이벤트 15건 번역 — 45개 언어 칸 중 43칸 저장(95.6%) [계산], 2칸은 라틴 고유명사 오탐(`wrong_script`)이라 규칙을 보정했고 보정 후 재번역은 9개 언어 칸 전부 저장 [실측]. 이벤트당 약 10.3초 [계산]. 표본 수작업 평점은 매기지 않았다(사용자 결정: AI 검증만).
- **사후 검토**: QVL은 조건부 완료(AC1·AC3·AC5·AC6 검증됨, AC2 문구를 좁힘). SRR 지적 7건 중 4건(구획 리터럴 재조립, `source_hash` 로그 위조, 전각 마크업 위장, 길이 검사 순서)을 같은 PR에서 TDD로 고쳤고 3건(장식 유니코드 저장, 개별 이벤트 탓 비 HTTP 예외의 배치 중단, 고유명사 라틴 예외 폭)은 이연했으며, 선점된 번역 복구는 운영 런북 절차로 처리했다.
- **PR 전 사용자에게 알릴 결정·확인 항목**: ① `manual` 플래그를 이벤트 단위로 둔 것(언어별 분리는 44-3에서 재확인) ② 건별 사람 검수 없음에 따른 의미 충실성 잔여 위험 ③ 고유명사 라틴 예외 폭 축소 여부 ④ 장식 유니코드는 44-2 착수 전 정규화 통일 여부 ⑤ 관리 명령에 `--dry-run` 인자를 두지 않은 편차.
