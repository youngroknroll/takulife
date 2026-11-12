# 트랙 27 후보: 카테고리 어휘 스태프 CRUD (2026-09-12 사용자 요청, **범위 산정만 — 계획 미작성**)

> 사용자 요청 원문(2026-09-12): "대시보드에서 카테고리를 스태프가 생성 수정 삭제를 할 수 있도록".
> **트랙 26에 넣지 않는 이유**: 상수 어휘를 런타임 데이터로 바꾸는 **스키마 변경**이다. `CLAUDE.md` HARD-GATE(신규 기능은 파일 [문서 3개] 이상이면 계획 선행)와 PR 단위 규칙(PR 하나 = 트랙 하나)에 따라 별도 트랙으로 세운다.

## 현행 실태 [실측 2026-09-12]

- 카테고리는 **모델이 아니라 상수**다 — `core/vocab.py`의 `CATEGORY` 튜플 [실측 7종]. `Category` 모델 0건 [실측 `rg 'class.*Category' --glob '*.py'`]
- `Event.category`는 `choices` 없는 `CharField(max_length=100, blank=True)` [코드 `events/models.py:15`]. `core/vocab.py:199-208` 주석이 `choices=`를 **의도적으로 기각**한 이유를 적고 있다("어휘를 고칠 때마다 AlterField 마이그레이션만 늘어난다")
- `CATEGORY`/`CATEGORY_LABELS`를 참조하는 파일 [실측 23개 `rg -l`]: `core/models.py`·`core/vocab.py`·`drafts/llm_extraction.py`·`drafts/runner_views.py`·`staff/views/{drafts,events,home_categories}.py`·`web/views/{_helpers,archive,events}.py`·템플릿 5개·테스트 9개
- 어휘 밖 자유 텍스트 오염 [실측 0건], 빈 값 [실측 3건]뿐 — 지금은 데이터가 깨끗하다

## 착수 전에 풀어야 할 설계 문제

1. ⚠️ **색 토큰 계약이 정면으로 걸린다.** `tests/core/test_category_token_contract.py`가 **계약 가드**로 "`static/css/tokens.css`는 `CATEGORY`의 모든 슬러그에 `--cat-{slug}-soft`와 `--cat-{slug}-ink`를 정의해야 한다"를 강제한다(G10 "슬러그 = CSS 이름" 원칙). 런타임에 만든 카테고리는 **정적 CSS에 토큰이 없다**. 선택지: 저장된 색상값을 인라인 스타일로 주입 / 고정 팔레트 풀에서 배정 / 색 없는 카테고리 허용. 이 결정 없이는 착수 불가
2. **삭제 의미론**: 그 카테고리를 쓰던 이벤트는 어떻게 되나. 지금은 `is_valid_category`가 어휘 밖 값을 막고 `PublishEventCategoryError`가 게시를 거부한다 — 삭제하면 기존 이벤트가 그 가드에 걸리는 상태가 된다
3. **홈 노출 설정과의 상호작용**: `core/models.py`의 `HomeConfig.featured_category_pairs`는 어휘에 없는 슬러그를 **조용히 제외**한다 [코드 `core/models.py:39-44`]. 카테고리를 지우면 홈에서 소리 없이 사라진다
4. **읽기 빈도와 캐싱**: 어휘는 목록·달력·홈이 렌더할 때마다 읽힌다. DB 조회로 바꾸면 캐싱 전략이 필요하다
5. **탐색 러너 어휘 전달**: `drafts/runner_views.py`가 어휘를 러너에 내려보낸다(트랙 30 해석 프롬프트). 런타임 어휘가 되면 그 계약도 바뀐다
6. **LLM 추출 어휘**: `drafts/llm_extraction.py`가 같은 상수로 재검증한다(현재 `DRAFT_LLM_EXTRACTION_ENABLED`는 off)

## 예상 역할

Product Scope Owner(삭제 의미론·색 정책), Domain Architecture Reviewer(어휘 소유 계층 이동), Backend TDD Coach, Backend & Integration Engineer, **Deployment & Operations Reviewer**(마이그레이션 + 데이터 이관 [계산 7종]), Web Experience Designer·Browser Interaction Reviewer(관리 화면), Quality Verification Lead. 트랙 26보다 큰 역할 집합이다.

## PSO 판정 (2026-09-12)

| 항목 | 결정 |
|---|---|
| 색 | 스태프가 임의 hex를 고르지 않고 **사전 정의 팔레트 풀에서 자동 배정**. 접근성 대비와 브랜드 일관성이 검증 안 된 색이 소비자 화면에 그대로 나가는 것을 막는다 |
| 계약 테스트 | "`CATEGORY`의 모든 슬러그마다 CSS 토큰" → **"팔레트 풀의 모든 슬롯마다 토큰 + 모든 활성 카테고리는 슬롯 하나에 배정"**으로 개정. G10 "슬러그=CSS 이름" 원칙은 폐기가 아니라 "카테고리 → 팔레트 슬롯 참조"로 대체 |
| 삭제 | **하드 삭제 없음, 비활성화만**. 기존 이벤트 값은 계속 유효하고 `PublishEventCategoryError`가 새로 발생하지 않아야 한다 |
| 수정 | **라벨만**. 슬러그는 생성 후 불변 — `Event.category` 저장값이자 URL 파라미터이자 CSS 이름을 겸한다 |
| 권한 | **superuser 전용**(`superuser_console_required`, `staff/permissions.py:28` [실측 존재 확인]). 어휘는 소비자 화면 전체에 영향을 준다 |
| 위치 | `staff/views/home_categories.py` 확장이 아닌 **별도 화면**. 그 화면은 "무엇을 홈에 노출할지"(큐레이션), 이번은 "어휘 자체의 존재·라벨·활성"(생명주기)으로 관심사가 다르다 |
| 감사 | 생성·수정·비활성화를 `StaffActionLog`에 기록. 현재 대상 필드가 `target_draft`·`target_event`·`target_user`뿐이라 확장 필요(H1과 동형 문제) |

## DAR 판정 (2026-09-12)

- **소유 앱 = `core`**. `core/models.py`에 `HomeConfig`·`AnalyticsEvent`와 나란히 둔다. 앱 간 의존 방향 위반 **없음** — `core`는 어떤 도메인 앱도 되참조하지 않는다 [실측 `rg '^from (events|drafts|archive|staff|web)' core/*.py` → 0건]
- ⚠️ **`core` 패키지 내부에 실제 순환 import가 생긴다**: `core/models.py:8`이 `core.vocab`을 import 중이라, `vocab`이 `Category` 모델을 되읽으면 `vocab → models → vocab` 순환이다. 해소 = `HomeConfig.featured_category_pairs`가 `vocab` 튜플 대신 같은 파일의 `Category`를 직접 쿼리하도록 먼저 바꾼다
- **`Event.category`는 CharField(슬러그) 유지, FK 전환 이연**. 근거: `EventDraft.extracted_category`는 무효 값도 보존해야 하는 자유 문자열이라 FK로 못 바꾸는데, Event만 FK가 되면 초안→이벤트 승격 경로에 슬러그↔FK 변환 계층이 새로 생겨 결합이 는다. 대신 "사용 중인 카테고리는 삭제 금지, 비활성화만"을 애플리케이션 계층 불변식으로 강제한다
- **읽기는 캐시 없이 매 요청 ORM 조회**. `CACHES`가 `DatabaseCache`라 [코드 `config/settings.py`] 캐시를 넣어도 같은 Postgres를 치므로 I/O 계층이 분리되지 않는다. 행 수가 [실측 7종] 규모라 직접 조회 비용이 무시 가능하다. 병목이 실측되면 그때 프로세스 내 캐시 + 시그널 무효화
- **응집 경고**: `core/vocab.py`는 스스로 "순수 튜플·딕셔너리, 매직 없음"을 선언한 모듈이다. ORM을 쓰는 부분은 별도 모듈(`core/categories.py`)이나 `Category` 모델 classmethod로 분리하고, `REGION`·`ARCHIVE_STATUS` 등 순수 축은 `vocab.py`에 남긴다

## 착수 전 반드시 고쳐야 할 기존 결함 (DAR 발견, 오케스트레이터 재확인 대상)

1. ⚠️ **`drafts/llm_extraction.py:28`의 `CATEGORY_SLUGS`가 모듈 import 시점 스냅샷**이다. 어휘를 DB로 옮겨도 **워커 프로세스 재시작 전까지** 새 카테고리가 LLM 추출 enum에 반영되지 않는다. 스키마 생성 함수 안(호출 시점)으로 옮겨야 한다
2. ⚠️ **`web/views/archive.py:267-269`가 라벨 → 슬러그 역조회**를 하며 **라벨 유일성을 암묵 전제**한다. 스태프가 라벨을 자유 편집하면 서로 다른 두 카테고리가 한 칩으로 조용히 합쳐진다. `Category` 모델에 **`label` 유일 제약**을 걸고 이 호출부를 슬러그 직접 필터로 재작성해야 한다
3. **`core/models.py:8`의 순환 import** (위 DAR 판정 참고)
4. **`templates/core/home.html`이 `var(--cat-{{ tile.slug }}-ink)`를 폴백 없이 보간**한다 [문서 `tests/core/test_category_token_contract.py` 독스트링, 오케스트레이터 실측 확인]. 토큰 없는 슬러그가 들어오면 `var()`가 무효화돼 **스와치 배경이 조용히 사라진다**. PSO의 팔레트 풀 안이 이 지점을 막는다

## 참조 표면 (착수 전 재측정 완료)

- `CATEGORY`/`CATEGORY_LABELS` 참조 파일 [실측 2026-09-12 23개 `rg -l`]
- `is_valid_category` 호출 파일은 **별개 표면**이다 [실측 6개: `core/vocab.py`·`drafts/agent_drafts.py`·`drafts/services.py`·`events/services.py`·`staff/views/drafts.py`·`tests/core/test_vocab.py`]. DAR가 이 둘을 합쳐 세어 "23개에 `agent_drafts.py`가 빠졌다"고 보고했으나, 그 파일은 `CATEGORY` 상수가 아니라 `is_valid_category` 함수를 import한다 [실측 `drafts/agent_drafts.py:10`] — 23개 집계는 정확하다
- CSS 토큰은 라이트·다크 각 [실측 7슬러그 × 2토큰 × 2테마]로 `static/css/tokens.css`에 정적 하드코딩돼 있다

## 사용자 결정 (2026-09-12 확정)

PSO가 제기한 [계산 3가지]에 사용자가 전부 권고안으로 답했다.

1. **팔레트 풀 = [결정 12슬롯]** — 현재 [실측 7종] + 여유 [계산 5개]. 슬롯 하나당 CSS [계산 4줄](라이트·다크 × soft·ink)이므로 총 [계산 48줄]. 서로 구분되는 색을 라이트·다크 양쪽에서 대비까지 맞추는 것이 12슬롯에서는 현실적이고, 더 늘리면 뒤쪽 색이 서로 비슷해진다. 늘리는 것 자체는 CSS 추가라 나중에도 쉽다
2. **슬러그 = 스태프가 직접 입력** — 라벨("콘서트")과 슬러그(`concert`)를 따로 받고 검증한다(소문자·숫자·밑줄, 중복 불가). 슬러그는 URL에 영구히 남는 값이라 읽히게 만드는 편이 낫고, superuser 전용 화면이라 감당 가능하다. 자동 생성(`category_8`)은 기존 [실측 7종](`popup_store` 등)과 형식이 어긋나 기각
3. **비활성 카테고리의 소비자 노출 = 쓰는 이벤트가 있으면 유지** — 그 카테고리로 **게시된 이벤트가 [계산 1건] 이상이면** 소비자 필터에 남기고, 0건이 되면 자동으로 사라진다. 사용자가 기존 이벤트를 계속 찾을 수 있고, 나중에 수동으로 치울 필요가 없다. 스태프 신규 등록 목록에서 빼는 것은 PSO 판정대로 별개로 적용된다

4. **슬롯 반납 = 비활성 + 게시 이벤트 0건일 때만** (2026-09-12 확정, BIR Critical 지적 후 정정)
5. **슬롯 재획득 = 빈 슬롯이 있으면 자동 배정, 없으면 중립색 폴백** (2026-09-12 확정)

### ⚠️ 정정 기록 — 오케스트레이터의 질문 설계 오류

슬롯 반납 규칙의 최초 표현은 **"게시 이벤트 0건일 때만 반납"**이었고, 오케스트레이터가 선택지를 만들 때 **"비활성 +"를 빠뜨렸다.** BIR가 이것을 **Critical(D1)**로 잡았다:

> 새로 만든 카테고리는 정의상 게시 이벤트가 0건이다. "0건이면 반납"을 그대로 구현하면 **생성 직후 자기 슬롯을 즉시 반납한다.** 그사이 다른 스태프가 카테고리를 만들면 그 슬롯을 가져가고, 방금 만든 카테고리는 색이 없거나 남의 색과 겹친다.

정정된 규칙:
- **활성 카테고리는 게시 이벤트가 0건이어도 슬롯을 지킨다**(생성 직후 포함)
- 스태프가 **비활성화한 뒤** 그 카테고리의 게시 이벤트가 0건이 되면 반납한다. 그 시점은 소비자 화면에서도 완전히 사라진 뒤라 **색 충돌이 구조적으로 불가능하다**
- **재획득(BIR D2)**: 반납 후 그 카테고리 이벤트가 다시 게시되면 **빈 슬롯이 있으면 자동 배정**한다. 빈 슬롯이 없으면 **중립색 폴백**으로 렌더하고 스태프 화면에 "미배정"으로 표시한다 — 게시를 막지 않는다
- **BIR D3 해소**: 따라서 "슬롯 미배정"이 정상 상태로 존재한다. 목록·수정 화면의 스와치와 소비자 렌더가 **모두 정의된 폴백을 가져야** 하며, 인라인 `style` 보간이 빈 문자열이나 `None`으로 깨지면 안 된다
- ⚠️ **반납은 게시상태 전이 시점에만 재계산한다. 조회(GET) 시점 재계산은 금지한다** — BIR 수용 기준 [문서 1번]

## 오케스트레이터 판정 — 역할 산출이 남긴 미결 항목 [계산 2건]

TDD 코치가 "코치 권한 밖"으로 남긴 항목 중 둘을 기존 근거로 정리했다. 사용자 재확인이 필요하면 뒤집을 수 있다.

1. **감사 로그 대상 = `StaffActionLog.target_category` FK 신설**. 기존 `target_draft`·`target_event`·`target_user` [실측 `staff/models.py:39-49`]와 같은 패턴이고, DOR도 같은 방향으로 판정했다. `context` JSON 활용안은 기존 관례와 어긋나 기각. ⚠️ 이 FK 때문에 **롤백 순서가 강제된다**(아래 DOR 판정 참고)
2. **`web/views/archive.py`의 라벨 → 슬러그 역조회는 재작성하지 않는다.** DAR는 재작성을 권고했으나, TDD 코치가 `tests/archive/test_archive_visits_filter.py`가 `filter=cat:<라벨>`을 **공개 URL 계약으로 이미 고정**해 뒀음을 찾아냈다. 라벨 유일 제약(C-02)만으로 원래 결함(라벨 충돌로 두 카테고리가 한 칩에 합쳐짐)이 해소되므로, 공개 계약을 건드리는 재작성은 이 트랙 범위 밖이다

## DOR 판정 — 배포·롤백 (2026-09-12)

| 심각도 | 내용 |
|---|---|
| **High** | ⚠️ **롤백 순서가 강제된다.** `StaffActionLog`가 `core.Category`를 FK로 참조하므로, 되돌릴 때 **`staff` 먼저 → `core` 나중**이어야 한다. 반대로 하면 Postgres가 `cannot drop table core_category because other objects depend on it`으로 거부한다. `on_delete=SET_NULL`은 Django ORM 동작이지 DB 레벨 제약이 아니라 이걸 막지 못한다 |
| **Medium** | **라벨 폴백이 설계에 없다.** 카테고리 행이 사라지면 그 슬러그를 쓰던 이벤트가 라벨을 못 찾는다. 이 저장소에 이미 `archive_status_label`의 `.get(slug, slug)` 패턴이 있다 [실측 `core/vocab.py:87-88`] — 같은 폴백을 **구현 필수 요구사항으로 못 박는다** |
| **Medium** | `StaffActionLog.target_category`가 계획에 없었다 → 위 오케스트레이터 판정 1번으로 해소 |
| Low | entrypoint 순서 위험은 현재 단일 인스턴스 구성에서 실재하지 않는다 — `set -e` + `migrate` → `bundle_shell_css` → `collectstatic` → `gunicorn` 순차 실행 [실측 `docker/entrypoint.sh:1-16`]. 마이그레이션 실패 시 기동 자체가 중단되므로 새 코드가 테이블 없이 뜨는 창이 없다 |
| Low | CSS·마이그레이션 배포 분리 위험은 **같은 PR·같은 이미지** 규칙만 지키면 발생하지 않는다. WhiteNoise `CompressedManifestStaticFilesStorage`가 콘텐츠 해시 파일명을 쓰므로 캐시 어긋남이 구조적으로 없다 |

**시딩 마이그레이션의 `reverse_code`는 `noop`이 아니라 "슬러그 정확 매칭 삭제"다.** 선례 `archive/migrations/0017`이 그 형태이고, `0018`·`accounts 0006`이 `noop`을 쓴 것은 정보 손실 근거가 있을 때다 — 단순 삽입인 시딩에는 그 근거가 없다.

**마이그레이션 번호** [실측]: `core`는 0004가 최신이라 다음이 0005, `staff`는 0010이 최신이라 다음이 0011.

## TDD 코치 Test List (2026-09-12)

영역별 ID 체계 [계산]: C(모델 계약 7) / D(어휘가 DB를 본다 2) / E(빈 값 회귀 핀 1) / F(노출 분기 5) / G(권한 4) / H(시딩 마이그레이션 2) / I(HomeConfig 2) / J(순환 import 가드 1) / K(감사 3).

**반드시 짚을 항목** [계산 3개]:
- **D-02** `test_LLM_추출_스키마_생성_함수는_호출_시점에_카테고리_enum을_다시_읽는다` — `drafts/llm_extraction.py:28`의 `CATEGORY_SLUGS`가 모듈 스코프에 있는 한 **절대 Green이 안 된다**. 테스트가 구현을 강제하는 지점
- **F-04** `test_비활성_카테고리를_쓰던_기존_이벤트는_재게시해도_카테고리_오류가_나지_않는다` — "비활성 ≠ 삭제" 핵심 계약
- **F-03** `test_비활성_카테고리를_쓰는_게시_이벤트가_0건이_되면_소비자_필터에서_사라진다` — 위 사용자 결정 3번의 직접 검증

**이미 Green 예상 핀 [계산 3건]과 뮤테이션 지점**: E-01(`is_valid_category("")` — `value == "" or` 절을 지워 DB 조회를 타게 만들면 Red) / J-01(`core/vocab.py`에 `from core.models import Category` 한 줄 임시 추가하면 AST 가드가 Red) / F-05(존재 검사 조건을 `True`로 하드코딩하면 임의 문자열이 통과해 Red).

**계약 테스트 개정**: `tests/core/test_category_token_contract.py`를 "슬러그마다 토큰" → **"팔레트 [결정 12슬롯] 전부에 토큰이 있다" + "모든 활성 카테고리가 유효 슬롯에 배정됐다"** 두 단언의 AND로 바꾼다. 이래야 "토큰 없는 슬롯을 가리키는 카테고리"가 원천 차단된다.

⚠️ **N+1 회피**: 카테고리별로 `Event.objects.published().filter(category=slug).exists()`를 도는 구현은 최대 [계산 12회] 쿼리다. `staff/views/home_categories.py`가 이미 쓰는 `values("category").annotate(count=Count("id"))` 집계를 재사용하면 [계산 1회]로 끝난다.

## WED 설계 명세 (2026-09-12, High)

- **화면 [계산 4개] 분리**: `templates/staff/categories/{list,create,edit,confirm}.html` + `static/css/staff/pages/categories.css` 신설. 클래스는 `cat-` 접두사로 독립 정의, 다른 페이지 CSS를 import하지 않는다(`accounts.css`가 선언한 관행)
- **활성/비활성 전환은 `staff/views/accounts.py`의 `_apply_flag_change` 2단계 확인을 그대로 이식**한다. **양방향 모두** 확인을 거친다 — accounts 선례가 재활성화에도 같은 확인을 요구하므로, 되돌릴 수 있다는 이유로 예외를 두면 superuser 화면 간 상호작용 모델이 어긋난다. `confirm-modal.js`는 쓰지 않는다
- **슬러그는 수정 화면에서 `<input disabled>`가 아니라 `<span class="mono cat-slug-readonly">` + "(불변)"**. `disabled` 입력은 포커스를 못 받아 "고장난 컨트롤"로 오인된다
- **슬롯 소진**: "배정 슬롯 N/12" 카운터, 12/12면 CTA `disabled` + `aria-describedby`로 사유 연결, 생성 라우트 직접 접근 시 목록 리다이렉트 + `messages.error`
- **활성·비활성을 한 표에 섞는다**(최대 [계산 12행]이라 나눌 비용이 없다). 표 위 `cat-rule-list`로 소비자 노출 규칙 [계산 3줄]을 명시
- `staff/search.py`의 `SEARCHABLE_URL_NAMES`에는 **추가하지 않는다** — `home-categories`도 같은 이유로 빠져 있다

### ⚠️ WED가 푼 `--cat-*` 토큰 문제 (이 트랙의 숨은 관문)

스태프 셸은 소비자 `static/css/tokens.css`를 로드하지 않는다(S6). 그런데 이 화면은 소비자 카테고리 색을 보여줘야 한다.

- 기각 ①: 이 페이지에만 소비자 `tokens.css` 추가 로드 → S6 위반, `--brand`·`--surface` 등이 캐스케이드에 새어 든다
- 기각 ②: 스태프 `tokens.css`에 `--cat-*` 복제 → 슬롯→hex 매핑을 CSS로 이중 유지보수
- **채택: 뷰가 슬롯의 hex 값을 계산해 컨텍스트로 내리고, 템플릿은 인라인 `style`에 그대로 찍는다.** 스태프 템플릿은 `--cat-*` 변수 이름을 한 글자도 참조하지 않는다. 수정 화면 팔레트 카드는 라이트·다크 두 칩을 나란히 보여준다 — "지금 스태프 화면이 무슨 테마인가"가 아니라 "소비자가 실제로 볼 두 값이 무엇인가"가 이 화면의 목적이기 때문이다
- 선행 조건(백엔드 소유): [계산 12슬롯 × soft/ink × light/dark = 48개] hex 값이 Python 쪽에 **단일 출처**로 존재해야 한다

## 오케스트레이터 정정 기록

1. **`core/vocab.py` 행 번호가 낡았다**. 이 계획서가 `is_valid_category`를 210-216행으로 적었으나 실제는 **225행**이다 [실측 `grep -n`]. 원인은 **트랙 26이 같은 파일에 `STAFF_EVENT_SORT`를 추가하면서(커밋 `7a32eb00`) 줄이 밀린 것**이다 — 같은 세션 안에서 인용이 낡았다. TDD 코치가 정정했다
2. **카테고리 색 토큰은 [실측 28개]다**(고유 이름 14개 × 라이트·다크 2테마). 이 계획서의 "29개"는 `grep -c`로 센 **행 수**였고 주석 한 줄이 섞였다. WED가 정정했다

## BIR 상호작용 명세 (2026-09-12, High)

**결함 [계산 3건]은 위 "정정 기록"의 사용자 결정으로 해소됐다**(D1 Critical·D2 High·D3 High). 남은 것:

- **D4 (Medium) 생성 경합 TOCTOU** — "12/12면 CTA disabled + 생성 라우트 직접 접근 시 리다이렉트"는 **GET 시점만** 방어한다. 생성 폼을 11/12로 열어 둔 채 다른 superuser가 마지막 슬롯을 채우면 POST 시점 재검증 없이 [계산 13번째] 배정이 생긴다. `staff/views/accounts.py:129`의 `select_for_update()` 관용구를 **생성 경로에도** 적용한다
- **D5 (정보, 결함 아님)** — `disabled` 버튼 접근성 처리가 저장소에 [계산 3갈래]로 혼재한다. 이번 트랙은 **`dashboard.html:185`의 `disabled aria-describedby` 방식을 그대로 따르고** 새 방식을 추가하지 않는다 [실측 존재 확인]

**BIR가 확인한 전역 사실**:
- **CSP 미들웨어 0건** [실측 `rg 'CSP|Content-Security-Policy' config/settings.py` → 0건, `django-csp` 미설치] → **WED의 인라인 `style` hex 해법이 성립한다**
- `confirm.html`은 CSS로 오버레이처럼 보이지만 실제로는 `base_staff.html`을 상속한 **완전한 페이지**다. 진짜 모달이 아니므로 포커스 트랩·ESC 처리 대상이 아니다 — 계정 화면과 같은 기존 전제
- `data-submit-guard`는 같은 문서 내 버튼만 비활성화한다. 뒤로가기 후 재제출은 못 막으므로 **서버가 멱등 처리**해야 한다(`staff/views/accounts.py:130-146`의 `changed` 플래그 패턴 이식)
- `superuser_console_required`는 **뷰마다 개별 데코레이터**다. 사이드바 `{% if request.user.is_superuser %}`는 경계가 아니다 — 화면 [계산 4개] + 활성/비활성 POST 엔드포인트 **전부**에 개별 적용돼야 한다

### BIR 수용 기준 (구현 후 검증, 미달 시 Deviates)

1. 슬롯 반납은 **게시상태 전이 액션 시점에만** 재계산되고, 목록·생성·수정 화면의 단순 GET은 슬롯을 반납·재배정하지 않는다
2. 방금 생성한 카테고리(게시 이벤트 0건)는 같은 응답과 직후 재조회에서 **배정된 슬롯을 유지**한다(D1 회귀 핀)
3. 슬롯 반납 후 재게시 시 동작이 문서와 일치한다(빈 슬롯 자동 배정 / 없으면 중립색 폴백)
4. 슬롯 미배정 카테고리가 목록·수정 화면에서 **정의된 폴백**으로 렌더되고 인라인 `style`이 깨지지 않는다
5. 생성 POST가 슬롯 가용성을 **트랜잭션 내에서 재검사**하고, 소진됐으면 만들지 않고 `messages.error` + 입력값 보존 재렌더
6. 생성·수정 검증 실패 시 입력값이 보존된 채 같은 폼이 재렌더된다(`events/edit.html`의 `form_values.*` 관례)
7. 화면 [계산 4개] 뷰 + 활성/비활성 POST 엔드포인트 **전부**에 `@superuser_console_required`가 개별 적용돼 URL 직접 접근 시에도 403
8. `disabled` CTA는 `dashboard.html:185`와 동일하게 버튼 자체에 `aria-describedby`를 달고, JS 없이 서버가 12/12 상태를 판단해 렌더한다

## 구현 단계와 커밋 경계

브랜치: `feat/category-vocabulary-crud`, **`feat/staff-event-list-filters`(트랙 26)에서 분기**한다. 트랙 26이 `core/vocab.py`에 `STAFF_EVENT_SORT`를 추가했고 이 트랙이 같은 파일을 크게 고치므로, main에서 분기하면 충돌이 난다. **PR #364 머지 후 main으로 리베이스**하고 그때 PR을 연다.

| # | 내용 | 테스트 |
|---|---|---|
| 1 | `core/models.py`에 `Category` 모델 + 마이그레이션 `core/0005`(스키마만). 필드: `slug`(unique), `label`(unique), `is_active`, `palette_slot`(null 허용 — 미배정이 정상 상태), `sort_order` | C-01~C-07 |
| 2 | 시딩 데이터 마이그레이션 `core/0006`. 기존 [실측 7종]을 **현재 색 토큰과 일치하게** 슬롯 배정. `reverse_code`는 **슬러그 정확 매칭 삭제**(`archive/0017` 선례) | H-01, H-02 |
| 3 | 팔레트 CSS [계산 12슬롯 × soft/ink × light/dark = 48줄] + Python 단일 출처(`core/categories.py`) + 계약 테스트 개정 | 개정된 `test_category_token_contract.py` |
| 4 | `core/categories.py` 신설 — 어휘 조회를 DB로. `core/vocab.py`는 순수 상수 모듈로 유지(DAR 응집 판정). `is_valid_category` 시그니처 불변, 내부만 교체 | D-01, E-01(뮤테이션), J-01(뮤테이션) |
| 5 | `HomeConfig.featured_category_pairs`가 `Category`를 직접 쿼리 → **`core/models.py:8`의 `core.vocab` import 제거**(순환 해소 선결) | I-01, I-02 |
| 6 | `drafts/llm_extraction.py`의 `CATEGORY_SLUGS`를 **모듈 스코프에서 함수 내부로** 이동 | D-02 |
| 7 | 슬롯 배정·반납·재획득 로직. ⚠️ **반납은 게시상태 전이 시점에만**, GET 재계산 금지. 재획득은 빈 슬롯 자동 배정, 없으면 미배정(중립색 폴백) | 신규(사용자 결정 4·5번 검증) + BIR 수용 기준 1·2·3 |
| 8 | 소비자·스태프 노출 분기. ⚠️ **N+1 금지** — `values("category").annotate(count=Count("id"))` 집계 [계산 1회] | F-01~F-05 |
| 9 | 라벨 폴백 `.get(slug, slug)` 전 소비처 적용(DOR Medium) | 신규 |
| 10 | `StaffActionLog.target_category` FK + `staff/0011` + 액션 [계산 3종] | K-01~K-03 |
| 11 | 관리 화면 [계산 4개] — 뷰·템플릿·CSS(WED 명세). ⚠️ **생성 POST에 `select_for_update` 재검사**(BIR D4), 모든 뷰에 `@superuser_console_required` 개별 적용 | G-01~G-04, BIR 수용 기준 5·6·7 |
| 12 | 전체 회귀 + 마이그레이션 왕복 실측 + 브라우저 검증 | — |

## 검증 명령과 기대 증거

표적 테스트는 단계마다, 전체 회귀는 `uv run pytest -q`. 게이트는 `manage.py check`와 `makemigrations --check --dry-run`.

- 기준선: **2721 passed**(트랙 26 기준) [실측 2026-09-12]
- 마이그레이션 [계산 3벌]: `core/0005`·`core/0006`·`staff/0011`
- **마이그레이션 왕복 실측**(DOR 요구): forward → reverse에서 시딩 [실측 7종]이 정확히 삭제되는지 `psql` 카운트로 확인
- ⚠️ **롤백 순서 실측**: `staff` 먼저 → `core` 나중이 성공하고, **반대 순서는 FK 오류로 실패하는 것을 둘 다 재현**한다(DOR High)
- 뮤테이션 [계산 3건]: E-01·J-01·F-05
- 브라우저: 팔레트 [계산 12슬롯]을 라이트·다크 양쪽에서 렌더해 색 구분 확인, 슬롯 소진 상태, 미배정 폴백, 생성·비활성화 왕복
- WED·BIR **사후 판정** 필수

## 상태

**6역할 산출 완료**(PSO·DAR·DOR·TDD 코치·WED·BIR), **사용자 결정 [계산 5건] 확정**, BIR Critical [계산 1건] 정정 완료, **착수 승인(2026-09-13)**.

---

