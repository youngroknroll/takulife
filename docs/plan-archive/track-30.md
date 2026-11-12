# 트랙 30: 키워드 탐색 → 판별 → 승인 가능한 드래프트·소스 등록 (2026-09-11) [v3.1 — 델타 검토 5역할(AIA·SRR·DAR·WED·BIR) 반영, v2 9역할 검토 계승, **착수 승인 대기**]

> **재편 배경(사용자 원문 2026-09-11)**: "스태프가 맥의 클로드코드로 소스를 수집할 때 검색어를 '하츠네미쿠'라고 적으면 관련 팝업·굿즈·콘서트 등을 수집하고, 그 중
> 잘못된 것을 판별하고, 후에 정확한 소스가 생기면 파이프라인으로 등록 — 이 과정을 자동화". 사용자 승인("ok", 2026-09-11): ① 키워드 탐색을 본체로 재편 ② 탐색(URL·판단)과
> 읽기(결정론)·해석(도구 없는 LLM) 분리 ③ 일반 웹 URL은 서버가 존재 재확인 ④ X 소스 유형 추가(아래 실측으로 **조건부**) + v2 ★1~★7·U1 권고안 승인.
> **트랙 분할(오케스트레이터 판단)**: 트랙 30 = 탐색 본체(검색어 입력 → 탐색 → 읽기·해석 → 드래프트·소스 등록) / **트랙 31 = 등록된 계정 소스의 정기 수집**(v2 계획을
> 아래 "트랙 31" 절로 이관, 공용 모듈은 트랙 30이 만든다). PR은 트랙마다 하나 [문서 pr-granularity].
> **실측 추가(2026-09-11)**: 네이버 통합검색 `search.naver.com`은 일반 httpx·데스크톱 UA로 HTTP 200·1,486,819바이트·네이버 블로그/뉴스 링크 54개 [실측 검색어 "하츠네 미쿠
> 팝업스토어"] / X 타임라인 `syndication.twitter.com/srv/timeline-profile/<handle>`은 일반 httpx로 **HTTP 429, 2회(6초 간격)** [실측] — insane-search 플러그인은 여기에
> curl_cffi TLS 위장을 쓰는데 [코드 플러그인 engine/phase0.py:125-151] 우회 금지 결정과 충돌해 채택하지 않음 → X 계정 타임라인 읽기는 **조건부**, 개별 트윗
> `cdn.syndication.twimg.com/tweet-result`·`publish.twitter.com/oembed`는 실제 트윗 id로 착수 시 실측(미실측). 플러그인은 탐색 에이전트에 로드하지 않는다(Bash 필요·
> `pip install` 자동 실행 [코드 플러그인 engine/executor.py:146-150]·우회 체인·Jina 제3자 경유 — 사용자 승인 2026-09-11).
> **현행 코드 [실측/코드]**: 탐색 요청은 검색어 없는 버튼 [코드 `templates/staff/dashboard.html:173-176`], `SourceDiscoveryRun`·러너 프롬프트에 query 필드 0건 [실측 rg],
> 러너 탐색 도구 `--tools "WebSearch,WebFetch"` [코드 `local_runner/claude_code_adapter.py:77-90`], claim 응답 `existing_source_urls`·`excluded_hostnames`(SNS 호스트
> 제외 목록에 instagram·x 포함 [코드 `drafts/discovery.py:26-35`]). v2 검토 결과(스로틀 XFF 우회, 기간 인자 누락, `--strict-mcp-config`, "승인 가능" 정의, FE 접기 없음 등)는
> 전부 계승 — 상세는 아래 트랙 31 절의 "검토 반영 요약(v1 → v2)".

> **델타 검토 반영 요약(v3 → v3.1)** [5역할 병렬 산출 2026-09-11, 인용은 오케스트레이터가 sed/rg로 재확인]
> - DAR(수정 요구 1): `complete_run`은 `SourceCandidate` 상태만으로 실행 상태를 산출 [코드 `drafts/discovery_runs.py:134-161`] → 이벤트만 제출한 실행은 전부 실패해도 SUCCEEDED.
>   SRR F1(High)과 같은 해법: **`EventDraft.discovery_run` FK(null, SET_NULL)** 신설 → 실행당 상한을 `run.events.count()`로 잠긴 트랜잭션에서 재검사(기존 `run.candidates.count()`
>   패턴 [코드 `candidate_validation.py:126,161-162`])하고, `complete_run`이 이벤트 결과(생성 수는 FK 집계, 시도·실패 수는 러너 보고)를 상태 산출에 넣는다(KW-12).
> - SRR: F2 **요청당 이벤트 1건**(배치 금지 — 재확인 왕복 최악 40초 [계산 (5초×4)×2, `fetching.py:10-11`]가 20건 배치면 800초) / F3 **SSRF 불안전 URL은 400 거부**(미검증
>   저장 아님, 기존 `URL_SAFETY` 단계와 동급) / F4 계정형 소스 등록에 호스트 allowlist·핸들 정규식·정규화 후 중복 검사 / F6 **러너 `page_fetch`에 사설·루프백·링크로컬 IP 차단**
>   (stdlib 복제, Django 미임포트 — `url_safety.py`는 stdlib만 씀 [코드]) / F7 403·429는 그 URL만 skip, 실행 전체 정지 아님 / F5 검색어는 `<query>` 구획 태그 / F8 robots 캐시 이연.
>   gunicorn `--timeout` 부재 [코드 `docker/entrypoint.sh:13-15`]는 **사용자 보류 항목(G2)**이라 재제안하지 않고 최악 지연만 기록.
> - AIA: events 필드 길이 상한(url≤200·title_guess≤255·official_basis≤200·duplicate_urls≤5개), `why_excluded`는 고정 enum, `same_as`→**`duplicate_urls`**(트랙 31
>   `same_event_as`와 의미 다름), 프롬프트에 "판단엔 본문 참고 가능·행사 필드 추출 금지" 명문화, ★8은 **URL 단위 런타임 판정**, "안정적"=실제 트윗 id 3건 이상 성공·429/403 없음,
>   `<caption>` 태그 감싸기는 WebFetch tool_result에는 해당 없음(텍스트 지시로 충분). **"콘서트"는 어휘 밖**(CATEGORY 6종 [코드 `core/vocab.py:21-28`]) → PSO/사용자 결정 ★10.
>   검색 변형별 CLI 분리 호출은 첫 실기동 소요 실측 후 결정(이연, 트리거 = 600초 타임아웃 관측). 네이버 코드화 트리거를 "표본 URL 중 WebSearch 경로 2회 연속 미발견"으로 구체화.
> - WED(Standard): 검색어 입력은 **헤더 아래 별도 행**(헤더는 2.25rem 고정 1행 [코드 `dashboard.css:121-129`], 1280px 본문 칼럼 644px [계산]이 1024px보다 좁음) + 시각 라벨
>   "검색어" + placeholder "검색어 예: 하츠네 미쿠" + `required minlength=2 maxlength=100 autocomplete=off` / 오프라인 분기에서 **입력은 활성, 버튼만 disabled** / 검증 실패는
>   `messages.error`(문안 2종) / 성공 메시지에 검색어 반영(plain 이스케이프) / **최근 탐색 실행 표에 검색어 열 추가**(2번째 열, CSS 말줄임+`title`, 빈 값 "-") / 대시보드 전용 입력
>   CSS(`.cin`은 `drafts.css`에만 있음 [코드]) / 기존 결함: 대시보드에 `.staff-cta:disabled` 규칙 없음 [실측 rg — `drafts.css`·`events.css`에만].
> - BIR(Standard): **스태프 셸 메시지 컨테이너에 `role="status"` 없음** [코드 `templates/staff/base_staff.html:59`, 소비자 `base.html:102`는 있음] → 검증 실패 안내가 스크린리더에
>   무음 → ★11 같은 트랙 수정 / 검증 실패 응답은 클라이언트 `required·minlength·maxlength` 1차 방어 + 서버 거부는 PRG·`messages.error`(값 소실은 우회 제출에 한정, 수용) /
>   `data-submit-guard`는 `submit` 리스너라 `required` 실패 시 잠기지 않음 [코드 `staff_submit_guard.js:19-33`, 선례 `delete_account.html`] / 오프라인 사유는 `title` 단독이 아니라
>   버튼·입력이 공유하는 `aria-describedby` 텍스트 / Enter 제출 기본 동작 유지.

## 승인 범위 (★ = 사용자 결정, v2에서 승인된 항목은 "확정")

**A. 키워드 탐색 요청** — `SourceDiscoveryRun.query = CharField(max_length=100, blank=True)` 신설(0009에 포함) / 대시보드 「새 소스 탐색」 폼에 검색어 입력 1개(필수,
2~100자 [계산 권고값], `sanitize_text`) → `create_run(requested_by, query)` / 서버 검증 실패(빈 값·길이)는 실행 미생성 + `messages.error`("검색어를 입력하세요." / "검색어는 2자
이상 100자 이하로 입력하세요.") + PRG(클라이언트 `required·minlength·maxlength`가 1차 방어라 값 소실은 우회 제출에 한정 — 수용) / 성공 메시지 "'<검색어>' 탐색 요청을
만들었습니다. 러너가 곧 가져갑니다."(plain `{{ }}` 이스케이프, `mark_safe`·`format_html` 금지) / 감사 로그 `SOURCE_DISCOVER` 유지(검색어는 run에만 저장, 로그 미보간) /
claim 응답에 `query`와 `vocab`(카테고리·지역 slug) 추가, 프롬프트에서는 `<query>` 구획 태그로 감싼다(SRR F5). 기존 스로틀(사용자당 분당 10회 [코드 `staff/views/discovery.py:31-47`])·
활성 실행 1개 제약·러너 오프라인 표시 유지. FE(WED·BIR 사전 산출 완료, 깊이 **Standard**): 입력은 패널 헤더 **아래 별도 행**(`.dash-panel-query-row`, 좌우 패딩 0.75rem
[코드 `dashboard.css:126` 패턴]) + 시각 `<label for>` "검색어" + placeholder "검색어 예: 하츠네 미쿠" + `autocomplete="off"` + 대시보드 전용 입력 클래스(`dashboard.css` 신설) /
오프라인 분기: 입력 활성·버튼 `disabled`, 사유 텍스트를 버튼·입력 공유 `aria-describedby`로(현행 `title` 단독 [코드 `dashboard.html:185`] 대체) / **최근 탐색 실행 표에
검색어 열**(시각 다음 2번째, `<col style="width: 9rem">` [계산 권고], CSS 말줄임+`title`=전체값, 빈 값 "-") / Enter 제출·`data-submit-guard` 기존 동작 유지.

**B. 탐색 단계(맥, Claude Code, 도구 WebSearch·WebFetch + `--strict-mcp-config`)** — 프롬프트를 키워드 기반으로 개정: 출력 `{"events": [{"url", "platform"(instagram|x|web),
"title_guess"≤255, "judgment": "official"|"unofficial"|"unclear", "official_basis"≤200, "why_excluded"(고정 enum: same_name|fan_made|ended|cancelled|restock_only|other),
"is_event", "duplicate_urls"(≤5개, 각 ≤200자)}], "sources": [기존 목록형 후보 계약 + 계정형 {"name", "url", "source_type": "instagram"|"x", "official_basis", "note"}]}`
(길이 상한은 [계산 권고값], 모델 필드 max_length [코드]와 정합; AIA). 탐색은 **URL과 판단만** 낸다 — 프롬프트에 "공식 여부·is_event 판단에는 페이지 본문을 참고해도 되나
행사 필드(날짜·장소·제목 확정값)는 절대 추출·기입하지 않는다"를 명문화(결정 ②). 판별 기준: official = 주최사·공식 계정·공식 사이트에서 직접 확인 / unofficial = 비공식 채널임을
명시적으로 확인 / unclear = 확인 신호 없음(다운스트림은 official 외 둘을 같게 처리, 표시 문구 "탐색 판단: 비공식"/"불명"). 동명·2차 창작·종료·취소·재입고 단독은 `why_excluded`와
함께, 같은 행사의 여러 공지는 **대표 URL 1개만 events에** 내고 나머지는 `duplicate_urls`(읽기·해석은 대표 URL만 처리). 검색어 확장은 한/영/일 표기 3계열 × 관련 행사 유형
조합, 프롬프트에 검색 6회·WebFetch 10회 상한 [계산 권고값]을 숫자로 명시(강제 수단은 600초 타임아웃뿐 [코드 `local_runner/config.py:10`] — 소프트 상한임을 문서화). 상한:
이벤트 후보 20건·소스 후보 10건/실행 [계산 권고값, 기존 `MAX_CANDIDATES_PER_RUN=10` [코드 `drafts/candidate_validation.py:25`]]. SNS 도메인 제외 목록은 **목록형 소스
후보에만** 적용하고 계정형·이벤트 URL에는 적용하지 않는다(현행 프롬프트 금지 문구 수정). 지시문 주입 방어는 현행 텍스트 지시(`build_prompt` [코드 `:56-57`]) 유지·확장
(`<caption>` 태그 감싸기는 도구 0개 해석 호출 전용). 검색 변형별 CLI 분리 호출은 첫 실기동 소요 실측 후 결정(이연, 트리거 = 600초 타임아웃 관측).

> **착수 실측 정정(2026-09-11, 오케스트레이터)** — 인스타 게시물 `og:description`은 **사용자 에이전트에 따라 갈린다**. 표본 `Dck7ZVUoG4i` 1건으로 측정: 데스크톱 크롬 UA는 HTTP 200에
> 본문 624,693바이트인데 `og:` 메타 0건(JS 앱 셸), 반면 curl 기본·`python-httpx/0.28`·러너 자체 이름 UA는 HTTP 200에 `og:description` 542자로 v2 실측치와 일치 [실측 5종 UA].
> → §C 인스타 경로는 **브라우저 UA를 쓰지 않는다**(쓰면 캡션이 사라진다). 러너는 자기 이름을 밝히는 UA를 쓰고, 메타 크롤러 사칭(`facebookexternalhit` 등)은 하지 않는다 — 사칭 없이도
> 같은 542자가 나오므로 필요도 없다 [실측]. 일반 웹 경로의 브라우저 UA 권고는 그대로 둔다(호스트별로 UA가 다르다는 뜻).
> **X 개별 트윗 ★8 판정(2026-09-11, 오케스트레이터 결정 = 편입)** — 실제 트윗 4건(크립톤 공식 계정 2종)으로 `cdn.syndication.twimg.com/tweet-result` 측정: 4건 전부 HTTP 200,
> 본문·작성시각·계정명 포함, 건당 약 0.6초, 429·403 0건 [실측]. 계획이 정한 편입 조건(실제 트윗 3건 이상 성공·429/403 없음 [문서])을 넘었으므로 **트랙 30에 편입**한다.
> 폴백 `publish.twitter.com/oembed`도 HTTP 200이나 리다이렉트 1회를 따라가야 한다 [실측]. 계정 타임라인(429 [실측 v3])은 계속 제외.

**C. 읽기 단계(맥, 결정론, 도구 없음)** — `local_runner/page_fetch.py`(v2 `caption_fetch.py` 일반화): 호스트별 라우팅 — 인스타 게시물 → `og:description` 캡션(IG-R2) /
일반 웹 → httpx GET(브라우저 UA, 15초·1MB [계산 권고값]) + BeautifulSoup으로 `og:title`·`<title>`·description·본문 텍스트(서버 `parse_raw_fields` 규칙과 동일, bs4는
주 의존성 [코드 `pyproject.toml`]) / X 게시물 → **URL 단위 런타임 판정**(tweet-result → oEmbed 순으로 시도, 실패면 "X 원문 미확보"로 미제출·카운터만 — ★8은 착수 시
실제 트윗 id 3건 이상 [계산 권고]으로 두 엔드포인트 성공·429/403 없음을 확인해야 코드에 편입) / 404·로그인 벽·비HTML은 사유와 함께 skip / **403·429는 그 URL만 skip(재시도
없음), 같은 호스트에서 2회째 [계산 권고]면 그 호스트를 실행 내 skip** — 실행 전체 정지는 아님(트랙 31의 "차단 시 정지"는 단일 제공자 계정 순회 전제, SRR F7) / **GET 직전
SSRF 차단**: 호스트 해석 결과가 사설·루프백·링크로컬·멀티캐스트·예약 IP면 GET하지 않음(`drafts/url_safety.py`의 판정을 stdlib로 복제, Django 미임포트 — SRR F6, KW-13).
러너는 robots를 검사하지 않는다(개인 맥 브라우징 범주, 결정 유지) 대신 요청 간 1초 대기·실행당 상한 [계산 권고값]. `known` 필터로 이미 드래프트가 있는 URL은 읽지 않는다.

> **착수 실측 — 도구 제약 전제 2건 파기(2026-09-11, 오케스트레이터)**: `claude` CLI의 `--tools`는 **쉼표로 구분된 유효 이름이 둘 이상일 때만** 제약이 걸린다.
> 실측 6종 [실측, 각 호출에 "사용 가능한 도구를 JSON으로만 나열하라" + 실제 파일 읽기 시도로 행위 확인]: `--tools "" --strict-mcp-config` → **기본 도구 전체**(Bash·Write·Edit·Read 포함, 실제로
> Read 호출 시도) / `--tools "WebFetch"` 단일 값 → 기본 도구 전체 / `--tools "Nonexistent,Nonexistent"` → 기본 도구 전체(유효 이름 0개면 무시) / `--tools "WebSearch,WebFetch" --strict-mcp-config`
> → **WebSearch 하나**(파일 읽기 요청에 `NO_TOOL` 응답) / 같은 인자에서 `--strict-mcp-config` 빼면 → WebSearch + MCP 플러그인 도구 전부(브라우저 제어 포함) / `--tools "TodoWrite,TodoWrite"
> --strict-mcp-config` → 파일 읽기 불가. → **§D의 "도구 0개" 전제는 거짓**이고, **§B의 WebFetch 전제도 거짓**이다(이 맥 전역 설정 `permissions.deny`에 `WebFetch`·`WebFetch(*)` [실측] —
> 탐색 에이전트는 검색만 되고 페이지를 못 연다). 기존 결함도 같이 드러났다: 현행 어댑터는 `--strict-mcp-config` 없이 호출해 [코드 `local_runner/claude_code_adapter.py:77-90`]
> MCP 플러그인 도구가 전부 열린 채 돈다.
> **AIA·PSO·SRR 판정(2026-09-11, 반영 확정)**:
> - **해석 단계 도구 구성**: `--tools "TodoWrite,TodoWrite" --strict-mcp-config`. 유효 이름을 **중복 나열**해야 제약이 걸린다(단일 값은 조용히 무시). TodoWrite는 세션 내 메모라 파일·네트워크
>   부작용이 없고, 어댑터는 `envelope["result"]` 텍스트만 읽으므로 [코드 `local_runner/claude_code_adapter.py:104,111`] 호출이 있어도 파싱 결과에 섞이지 않는다.
> - **판별 이관(PSO 승인)**: §B 탐색은 **URL + 배제 판별만**(`is_event`·`why_excluded`·`duplicate_urls`), **`judgment`·`official_basis`는 §D 해석 단계가 채운다**. 탐색 프롬프트에서 공식 여부
>   판별 기준 문단과 "본문을 참고해도 된다" 문장을 들어내 §D로 옮긴다. §B 헤더의 도구 표기도 "WebSearch"만으로 고친다. **서버 계약은 불변**(필드명·길이·저장 규칙·KW-08 전부 유지) —
>   바뀌는 것은 값을 채우는 단계뿐이라 `drafts/agent_drafts.py`는 무변경. 추가 LLM 호출 0건(해석은 이미 계획된 호출). 이벤트 상한 20건/실행도 유지(판별 위치는 읽기 진입 여부를 가르지
>   않았으므로 비용이 늘지 않는다). §E 메모 접두는 "탐색 판단:" → **"판단:"**으로 정정 완료(커밋 a49e73ed).
> - **SRR 판정 = Critical, 트랙 30 실기동(8단계) 선행 조건**: `bypassPermissions`와 `--strict-mcp-config`는 **쌍 불변식**으로 다룬다. 러너는 상시 가동이 아니다(`DRAFT_DISCOVERY_ENABLED`
>   기본 false [코드 `config/settings.py:81-82,267`], 토큰 기본 빈 문자열 [코드 `:280`], 콘솔 스크립트 0건 [실측]) — 지금 인시던트는 아니나 다음 실기동 전에 닫아야 한다. 필요한 것:
>   ① 두 호출 모두 `--strict-mcp-config` ② `subprocess.run` argv를 스텁으로 단언하는 계약 테스트(현재 0건 [실측] — §B 탐색 호출용 항목이 §T에 없어 IG-R9를 `tools` parametrize로 확장)
>   ③ `bypassPermissions`가 있으면 `--strict-mcp-config`도 반드시 있음을 단언하는 불변식 가드 ④ `docs/BE/draft-source-agent-discovery.md`의 2026-08-20 "Conforms" 기록은 지우지 말고
>   "측정 전 기록"으로 표시한 뒤 정정 항목을 덧붙인다. 미검증 이연: chrome-devtools MCP가 상시 로그인 브라우저 프로파일에 붙는지(붙으면 격리 조치 우선순위 상향).

**D. 해석 단계(맥, `claude -p --output-format json --tools "" --strict-mcp-config`)** — v2 §E (4)~(5) 그대로(필드별 confidence·evidence 인용·missing 고정 사유·연도 창·
지역 추론·`is_event`·제목 빈 결과 미제출·서버 어휘로 로컬 선검사). 입력은 캡션 대신 "읽기 단계 텍스트 + 탐색 단계의 `platform`·`judgment`·`official_basis`"이며 이 셋은
제출 페이로드까지 그대로 전달한다. 어휘 밖 행사 유형(예: 콘서트, ★10 미승인 시)은 카테고리 빈 값 + `missing.reason="category_out_of_vocab"`로 저장하고 §I 지표에 건수를 남긴다.

**E. 제출 API(서버)** — v2 §C-3을 일반화: `POST /api/discovery/runner/runs/<run_id>/drafts/`(**임대 토큰 필수** — 탐색 실행에 귀속, 기존 `locked_run_with_valid_lease` 재사용)
+ `POST /api/discovery/runner/drafts/known/`. 신설 엔드포인트 2종 [계산]. **요청당 이벤트 1건**(배치 금지 — 기존 후보 제출 전례 [코드 `runner_views.py:88`], SRR F2).
페이로드 = v2 계약 + `"platform"`, `"judgment"`, `"official_basis"≤200`, `"source_name"≤100`(공식 채널명 — 승인 시 소비자에 "N 제공"으로 노출되므로 검색어를 넣지 않는다).
규칙(v2 계승): 400 schema / 어휘·날짜·confidence 정정+메모 / duplicate 200(타임아웃 뒤 재제출 포함) / 생성 201 / **실행당 이벤트 상한 20건 [계산 권고값]**을 신설
`EventDraft.discovery_run` FK(null, SET_NULL, related_name `events`)로 `run.events.count()`를 잠긴 트랜잭션에서 재검사(기존 `run.candidates.count()` 패턴, SRR F1·DAR)
/ 토큰 단일 버킷 스로틀(v2 SR-1). **일반 웹 URL 서버 재확인(결정 ③)**: 호스트가 SNS 목록 밖이면 `validate_fetch_url`(DNS 핀) → `RobotsChecker` → `fetch_html`로 존재·HTML만
확인(추출 없음, 결과 버림) 후 저장 — **`InvalidFetchUrlError`·`UnsafeFetchUrlError`는 400 거부**(기존 `URL_SAFETY` 단계와 동급, SRR F3), robots 불허·네트워크·타임아웃 실패만
**저장하되** note에 "서버 미검증(사유)". 세 단계 판정은 `candidate_validation.py`의 공유 헬퍼(`(ok, stage, reason)` 반환)로 뽑아 두 경로가 함께 쓴다(DAR — 실패 처리 정책만
다름). 최악 지연 1건당 약 40초 [계산 robots 20초 + 본문 20초, `fetching.py:10-11` 5초×리다이렉트 4회] vs gunicorn 기본 30초 — G2는 사용자 보류라 재제안하지 않고 위험만
기록(통상 수 초 이내 [추정, 첫 실기동에서 실측]). **SNS 호스트는 fetch 경로에 절대 들어가지 않는다** — IG-16을 정적 임포트 가드에서 **행위 계약**으로 바꾼다(인스타·X URL
제출 시 `fetch_html`이 호출되지 않음을 monkeypatch로 단언, KW-07). `judgment != official` 이벤트는 저장하되 `intake_note` 앞머리에 "탐색 판단: 비공식/불명 — 근거"를 붙인다
(자동 폐기 없음 — 승인 게이트 원칙, 스태프가 큐에서 걸러냄). 저장 필드: `origin=collected`, `extraction_method=llm`, `raw_text`=읽기 단계 텍스트(≤5,000자 [계산]), `intake_note`,
`discovery_run`. **실행 완료 판정(DAR)**: `complete_run(..., events_attempted, events_failed)`가 러너 보고 2개 정수(상한 clamp)를 run에 저장하고, 생성 수는 `run.events.count()`로
집계해 상태 산출에 넣는다 — 소스 후보 0건·이벤트 시도 있음·생성 0건이면 FAILED, 일부 생성이면 PARTIALLY_FAILED(KW-12).

**F. 소스 등록** — 목록형(RSS·sitemap·HTML)은 기존 `submit_candidate` 8단계 검증·승격 그대로 [코드 `drafts/candidate_validation.py:152-294`]. **계정형(instagram·x)은
서버가 fetch 없이 검증해 `DraftSource(enabled=False)`로 만든다**(PSO "계정 추가는 건별 사용자 승인" — 스태프가 admin에서 활성화, 정기 수집은 트랙 31). 경로: 기존
`RunnerCandidateSubmitView`가 `source_type`으로 분기해 `candidate_validation.py`의 신설 `register_account_source`를 호출(신규 엔드포인트 없음, DAR). 최소 검증(SRR F4):
호스트 allowlist(`instagram.com`/`www.instagram.com`, `x.com`/`www.x.com`) + 핸들 정규식 `^/[A-Za-z0-9_.]{1,30}/?$` [계산 권고] + 소문자·쿼리 제거·후행 슬래시 정규화 후
중복 검사(`DraftSource.url` unique는 완전일치만 [코드 `models.py:75`]) — 미통과는 schema 격리. `SourceType`에 `INSTAGRAM`·`X` 추가(choices 2종 [계산], 무SQL),
`discover_drafts`·`enabled_draft_sources_exist`·`validate_payload` 유형 필터(v2 §B, IG-12·13·14 그대로 — 계정형은 목록형 9단계 [코드 `candidate_validation.py:152-294`]에
섞지 않고 별도 함수).

**G. 스키마** — 0009 한 파일: `EventDraft.intake_note`(v2 §D, immutable) + **`EventDraft.discovery_run` FK**(SRR F1·DAR, 시리얼라이저 읽기 전용+immutable) +
`SourceDiscoveryRun.query` + `SourceDiscoveryRun.events_attempted`·`events_failed`(PositiveSmallInteger, default 0) + `DraftSource.source_type` choices. ADD COLUMN 5문장
+ FK 인덱스·제약 [계산, `sqlmigrate` 실측 예정] + choices 무SQL. 롤백 전 계정형 소스 비활성(DOR).

**H. FE** — (1) 대시보드 검색어 입력 + 최근 실행 표 검색어 열(Standard, WED·BIR 사전 산출 완료 — §A) (2) 검수 상세 에이전트 메모 블록(Light, v2 §F 사전 산출 완료 —
접기 없음·`.review-agent-note`·1280·1024px) (3) ★7 기존 결함 2건 [실측 rg, v2 §F] 수정(확정) (4) **★11 스태프 셸 기존 결함 2건 같은 트랙 수정(권고)**: `templates/staff/base_staff.html:59`
`.staff-messages`에 `role="status"`(소비자 셸 `base.html:102`와 동일) + 대시보드 `.staff-cta:disabled` 규칙(`dashboard.css`, `drafts.css:86-89`와 동일).

**I. 지표·문서** — v2 §G 계승 + 탐색 실행 단위 지표(실행당 이벤트 후보·읽기 성공·제출·duplicate·judgment 분포 — 러너 로그 요약 + 서버 카운트). 문서 대상 v2 §G +
`docs/BE/draft-source-agent-discovery.md`에 "탐색 = 키워드 기반, 출력 2종(이벤트·소스)" 개정, 런북에 insane-search 미채택 결정과 X 429 실측 기록.

## 명시적 제외 / 이연 (v2 목록 계승 + 추가)
- 제외: 계정 소스 정기 수집(트랙 31) / X 타임라인 읽기(429 실측 — 우회 없이는 불가, 트랙 31에서 재실측) / 탐색 에이전트에 Bash·브라우저 MCP·insane-search 로드 /
  자동 승인·자동 소스 활성화 / 서버의 인스타·X 접속 / 우회 체인·Jina 경유.
- 이연: v2 이연 전부 + 네이버 검색을 탐색 발견 경로로 코드화(지금은 Claude WebSearch에 맡기고, **트리거 = 동결 표본 URL 중 하나라도 WebSearch 경로로 연속 두 번 [계산 권고]
  미발견**이면 `search.naver.com` 링크 추출 모듈 추가 — 실측 200 확보) / 실행 귀속 이벤트 후보 모델(`SourceCandidate`형, 판별 결과 표시 — FK·카운트 필드는 이번에 넣고 행 단위
  모델은 이연) / 소스당 일일 상한(트랙 31) / 검색 변형별 CLI 분리 호출(트리거 = `AGENT_TIMEOUT_SECONDS` [코드] 타임아웃 관측, AIA) / robots 판정 실행 내 호스트 캐시(SRR F8) /
  claim 응답 조립을 뷰에서 서비스로 이동(트리거 = 필드가 하나 더 늘 때, DAR) / 서버·러너 SSRF IP 판정 로직 중복의 공용 순수 패키지화(SRR F6 후) / 메시지 종류의 색상 외 구분(BIR 정보).

> **실기동 결과(2026-09-12, 검색어 "하츠네 미쿠 팝업스토어", 로컬 서버 + 러너 1회 폴)** — 파이프라인이 처음부터 끝까지 동작함을 확인했다.
> **1차 시도가 결함 3건을 잡았다**(단위 테스트로는 안 보이던 통합 결함): ① 제출 5건 전부 400 — 해석 모델은 주소·원문·출처명을 모르는데 흐름이 채워주지 않았다
> ② 해석이 JSON 복구에 실패하자 예외가 흐름 밖으로 나가 실행 전체가 죽었다(읽기 실패는 항목만 건너뛰는데 해석 실패는 전체 중단 — 일관성 없음)
> ③ 예외로 죽어 완료 보고를 못 보내 실행이 임대를 쥔 채 `claimed`로 남았다. 세 건 모두 테스트로 고정 후 수정.
> **2차 시도 결과** [실측]: 폴 성공, 실행 상태 `partially_failed`, **드래프트 3건 생성**(하츠네 미쿠 EXPO 2026 북미 투어 팝업 / 프로젝트 세카이 신세계 강남 팝업 / 프로젝트 세카이 부산 팝업),
> 전부 `extraction_method=llm`·카테고리 `popup_store` 채움·승인 전 체크 5항 전부 통과. 계정형 소스 3건이 **`enabled=False`로 등록**(X 공식 계정 3종).
> **서버 로그에 instagram 요청 0건** [실측 grep] — 서버 무fetch 계약이 실기동에서도 지켜졌다. 러너는 인스타 게시물을 정상적으로 읽었다(HTTP 200).
> 관찰된 품질: `judgment`는 3건 모두 `unclear`(검색 결과만으로는 공식 확인이 어렵다는 뜻, 설계대로 저장하되 메모에 근거 기록), 지역·장소·기간은 본문에 있을 때만 채워졌다(그라운딩 동작).

## 수용 기준 (v2 9항 계승, 변경분만)
1. 스태프가 검색어를 넣어 탐색을 요청하면 러너가 그 검색어로 탐색해 관련 행사 드래프트(승인 전 체크 5항 ✓·배지 0·장소명·카테고리 채움)를 만들고, 비공식 판단 이벤트는
   메모 앞머리에 판단·근거가 붙은 채 대기 큐에 들어간다 — KW-01~05·08·IG-04 + 실기동(검색어 "하츠네 미쿠", 표본 게시물 `Dck7ZVUoG4i` 포함).
2. 계정형 소스 후보는 비활성으로 등록되고 스태프가 활성화하기 전엔 어떤 경로도 읽지 않는다 — KW-06·IG-12·13.
3. 일반 웹 URL은 서버가 존재를 재확인하고, 인스타·X URL은 서버가 fetch하지 않는다 — KW-07.
4. v2 2·4·5·7·8·9항 그대로(엔드포인트 2종·실행당 상한·임대 귀속) [계산].

## Activated Roles / Not Activated
- v2와 동일(11역할 전부). v3 델타 검토 **완료(2026-09-11)**: AIA·SRR·DAR 산출 반영, WED·BIR 사전 산출(대시보드 검색어 입력) 반영 — §A·요약 참조. 착수 후 TDD 코치가
  §T를 최종 확정하고, 사후 리뷰는 v2 절차(FE 이중 게이트 사후 판정·QVL 완료 판정) 그대로.

## 파일 목록 (v2 목록 기준 이관·추가) [계산 — §A~§I에서 도출]
- 트랙 31로 이관: `local_runner/instagram_reader.py`·`instagram_flow.py`·`instagram.py`, `sources/`·`sources/<id>/checked/` 엔드포인트, `tests/local_runner/test_instagram_reader.py`·
  `test_instagram_flow.py`, Test List IG-09·11·R1·R1b·R6·R7·R7b·R8·R8b(9건 [계산]).
- 트랙 30: ✎ `drafts/models.py`(query·events 시도/실패 카운트·discovery_run FK·choices·intake_note), ✚ `drafts/migrations/0009_*.py`, ✚ `drafts/agent_drafts.py`, ✎ `drafts/services.py`,
  ✎ `drafts/discovery_runs.py`(`create_run(query)`·`complete_run` 이벤트 집계), ✎ `drafts/runner_views.py`(drafts·known 뷰·claim 응답·스로틀·계정형 분기), ✎ `drafts/runner_urls.py`,
  ✎ `drafts/candidate_validation.py`(`register_account_source`·판정 공유 헬퍼), ✎ `templates/staff/base_staff.html`(★11), ✎ `local_runner/runner.py`(`_process_run` 세 갈래 디스패처·complete 이벤트 집계 보고),
  ✎ `drafts/candidate_intake.py`, ✎ `drafts/queries.py`, ✎ `drafts/management/commands/discover_drafts.py`, ✎ `drafts/serializers.py`, ✎ `staff/views/discovery.py`,
  ✎ `templates/staff/dashboard.html`, ✎ `static/css/staff/pages/dashboard.css`, ✎ `templates/core/drafts/detail.html`, ✎ `static/css/staff/pages/drafts.css`,
  ✚ `local_runner/page_fetch.py`, ✚ `local_runner/caption_interpreter.py`, ✚ `local_runner/exploration_flow.py`(탐색 결과 → known → 읽기 → 해석 → 제출),
  ✎ `local_runner/claude_code_adapter.py`(프롬프트 v2·`parse_json_object`·`tools/strict_mcp`), ✎ `local_runner/client.py`,
  ✎ `local_runner/config.py`; 테스트 ✚ `tests/drafts/test_agent_drafts.py`, ✚ `tests/drafts/test_runner_draft_api.py`, ✎ `tests/drafts/test_discovery_runner_api.py`,
  ✎ `tests/drafts/test_discovery_runs.py`, ✎ `tests/staff/test_staff_source_discovery_request_view.py`, ✎ `tests/staff/test_staff_draft_api.py`, ✎ `tests/drafts/test_candidate_validation.py`,
  ✎ `tests/drafts/test_discover_drafts_command.py`, ✎ `tests/drafts/test_drafts_queries.py`, ✎ `tests/core/test_architecture_boundaries.py`, ✎ `tests/core/test_service_signature_conventions.py`,
  ✚ `tests/local_runner/test_page_fetch.py`, ✚ `tests/local_runner/test_caption_interpreter.py`, ✚ `tests/local_runner/test_exploration_flow.py`, ✎ `tests/local_runner/test_claude_code_adapter.py`,
  ✎ `tests/local_runner/test_runner_loop.py`, ✚ `tests/local_runner/fixtures/`; 문서는 v2 §G.

## §T Test List — 트랙 30 실행분 (총 41건 [계산 v2 IG 27 + KW 14])
> **착수 중 계약 충돌 정정(2026-09-11, 코치 발견 → PSO 판정)**: IG-07·IG-07b는 "제출 URL이 전부 인스타 게시물"이라는 트랙 31 전제 위에 쓰였는데, 트랙 30 §B는
> `platform`이 instagram·x·web 3종이라 성립하지 않는다. → **IG-07은 "스킴·길이 위반 거부"로 재정의**(기존 `validate_payload` 스킴·길이 검사 재사용), **IG-07b는 KW-16으로
> 재번호·재정의**: "source_url의_알려진_추적_파라미터만_제거되고_그_외_쿼리스트링과_경로는_보존된다"(parametrize: 추적 파라미터만/의미 있는 쿼리 혼재/추적 없음).
> PSO 판정 = **선택지 B**(고정 목록의 추적 파라미터만 제거, `platform` 3종 공통). **경로 정준화는 제외**(인스타 `/p/`·`/reel/`, X `/status/` 정준화) — 트랙 31 이연,
> 트리거 = 동결 표본·실기동에서 경로 형식만 다른 같은 행사가 별개 드래프트로 등록되는 사례 1건 이상 실측. 근거: `source_url`은 전역 unique [코드 `drafts/models.py:19`]이고
> `duplicate_urls`는 한 실행 안에서만 묶으므로 [문서 §B] 다른 검색어·다른 시점의 같은 행사가 큐에 중복으로 쌓인다. 의미 있는 쿼리(`?id=123`)는 절대 제거하지 않는다.
> **IG-05 용어 정정**: "같은 소스/다른 소스"는 트랙 31의 `source_id` 개념 → 트랙 30은 "같은 실행/다른 실행"(중복 판정 자체는 전역 unique라 실행과 무관).

- v2 IG 27건 [계산]: IG-01·02·02b·03·04·05·07·07b·08·10·12·13·14·15·17·R2·R2b·R3·R4·R5·R5b·R9·R10·R11 그대로 + 재정의 3건: IG-06 → "임대가_없거나_만료된_실행으로의_제출은_거부된다"
  (domain, `LeaseInvalidError` 재사용) / IG-16 → KW-07로 흡수(행위 계약) / IG-18 → "실행당_이벤트_상한을_넘는_제출은_거부되고_드래프트가_생성되지_않는다"(domain, `discovery_run`
  FK 집계 — 재임대·`renew_lease` 뒤에도 유지되는지 parametrize). IG-05는 "타임아웃 뒤 재제출"을 같은 URL 재제출 케이스로 포함, IG-15는 `discovery_run`도 immutable로 parametrize.
| ID | 행위(한국어 테스트명) | 마커 | 첫 Red 사유 | 파일 |
|---|---|---|---|---|
| KW-01 | 검색어_없이_탐색을_요청하면_실행이_만들어지지_않고_안내_메시지가_뜬다 | web | 폼에 필드 없어 실행 생성됨 | ✎ `tests/staff/test_staff_source_discovery_request_view.py` |
| KW-02 | 검색어를_넣어_요청하면_실행에_검색어가_저장되고_claim_응답에_실린다 | web | `query` 컬럼 없음 | ✎ `tests/drafts/test_discovery_runner_api.py` |
| KW-03 | claim_응답은_카테고리와_지역_어휘_목록을_포함한다 | web | 키 없음 | 상동 |
| KW-04 | 탐색_출력의_events와_sources를_분리_파싱하고_상한을_넘는_항목은_잘라낸다 | unit | `exploration_flow` ImportError | ✚ `tests/local_runner/test_exploration_flow.py` |
| KW-05 | 이벤트_URL은_호스트별로_읽기_경로가_정해지고_알_수_없는_호스트는_일반_웹으로_간다 | unit | `page_fetch` ImportError | ✚ `tests/local_runner/test_page_fetch.py` |
| KW-06 | 계정형_소스_후보는_fetch_없이_비활성_소스로_등록되고_비허용_호스트나_정규화_후_중복은_거부된다(parametrize) | domain | 목록형 경로로 가서 robots/fetch 실패 | ✎ `tests/drafts/test_candidate_validation.py` |
| KW-07 | 일반_웹_URL_제출은_서버가_존재를_재확인하고_인스타_URL_제출은_fetch를_호출하지_않으며_안전하지_않은_URL은_거부된다(parametrize) | contract | 함수 없음 | ✚ `tests/drafts/test_agent_drafts.py` |
| KW-08 | 비공식_판단_이벤트는_메모_앞머리에_판단과_근거가_붙어_저장된다 | domain | `judgment` 무시 | 상동 |
| KW-09 | 일반_웹_페이지_텍스트는_og_title_title_description_본문_순으로_추출된다 | unit | 함수 없음 | ✚ `tests/local_runner/test_page_fetch.py` |
| KW-10 | 탐색_흐름은_known_필터_후_읽기_해석_제출을_순서대로_수행하고_실패_항목을_건너뛴다(가짜 client/fetch/interpreter) | unit | 함수 없음 | ✚ `tests/local_runner/test_exploration_flow.py` |
| KW-11 | 탐색_프롬프트는_검색어와_판별_기준과_출력_스키마를_포함하고_SNS_제외는_목록형에만_적용된다 | unit | 프롬프트에 검색어 인자 없음 | ✎ `tests/local_runner/test_claude_code_adapter.py` |
| KW-12 | 소스_후보_없이_이벤트만_시도한_실행은_생성_0건이면_실패로_일부_생성이면_부분_실패로_완료된다(parametrize) | domain | 이벤트 무시하고 SUCCEEDED | ✎ `tests/drafts/test_discovery_runs.py` |
| KW-13 | 사설_루프백_링크로컬_IP로_해석되는_이벤트_URL은_러너가_GET하지_않는다 | contract | 판정 함수 없음 | ✚ `tests/local_runner/test_page_fetch.py` |
| KW-14 | 일반_웹_응답이_403이나_429면_그_URL만_건너뛰고_같은_호스트_두_번째부터는_호스트를_건너뛴다(임계 [계산 권고]) | unit | 예외로 흐름 중단 | ✚ `tests/local_runner/test_exploration_flow.py` |
- 테스트하지 않는 것: v2 목록 그대로(실제 네트워크·브라우저·httpx 래퍼·템플릿·프롬프트 품질·launchd).
- 첫 계약(코치 확정 2026-09-11, 착수 시): **IG-13**. v2 문구 "첫 계약은 IG-01"은 트랙 31 시절 잔재라 폐기 — 위 "구현 단계" 1단계가 §G 스키마 정합이고, IG-01은 2단계
  `agent_drafts.py` 항목이다. 1단계 Red 순서는 **IG-13 → IG-12 → IG-14 → IG-15 → KW-02(서버분)** [계산 5건]: IG-13·12는 무스키마(`LISTING_CONTENT_TYPES_BY_SOURCE_TYPE`
  재사용 [코드 `drafts/candidate_intake.py:24-28`]), IG-14는 `SourceType`에 choices를 먼저 넣어야 "이미-Green" 함정을 피하고(현행 `validate_payload`는 choices에 없는
  `instagram`을 이미 schema에서 거부 [코드 `drafts/candidate_validation.py:80-82`]), IG-15·KW-02가 실제 ADD COLUMN을 강제한다.

## 구현 단계 (커밋 단위, 브랜치 `feat/keyword-exploration-drafts` from main — §F 유형 필터와 choices·컬럼은 같은 PR·같은 배포)
1. §G 모델·0009·시리얼라이저·서버 경로 정합(IG-12·13·14·15, KW-02 서버분) → 2. §E 서비스 `agent_drafts.py`(IG-01~07b·18·KW-07·08) → 3. §E 뷰·URL·스로틀·claim 응답
(IG-08·10·17, KW-03) → 4. §A `create_run(query)`·요청 뷰(KW-01·02) → 5. §B·§C·§D 러너(어댑터 일반화·프롬프트 v2·page_fetch·interpreter: KW-04·05·09·11·IG-R2~R11) →
6. `exploration_flow`·`_process_run` 연결(KW-10) → 7. FE: WED·BIR 사전 산출(검색어 입력) → FIE(입력·메모 블록·★7) → 8. 실기동(로컬 서버·검색어 "하츠네 미쿠"·표본 게시물·
동결 표본 평가·로그 grep) + 브라우저 증거 + 사후 리뷰 → 9. 문서·백로그 → 10. 검증·PR.

## 검증 명령·기대 증거 — v2 절 계승. 변경: 표적에 `tests/staff/test_staff_source_discovery_request_view.py`·`tests/drafts/test_discovery_runs.py` 추가, 신규 38건 [계산] 이상 증가·
실패 0(기준선 2582 passed / 74.17초 [실측 2026-09-11]), 실기동 검색어 "하츠네 미쿠"로 탐색 요청 → 러너 1회 → 큐 확인·judgment 분포 기록, X 개별 트윗 엔드포인트 실측 결과 기록.

## 사용자 결정 (★)
- v2 ★1~★7·U1: **승인됨(2026-09-11 "ok")**. 재편 ①~④ 승인됨.
- ★8(신규, 권고 병기): X 개별 트윗 읽기(tweet-result·oEmbed)가 착수 실측에서 안정적이면 트랙 30에 포함, 아니면 "X 원문 미확보"로 미제출 처리 — **권고: 실측 결과에 따라
  오케스트레이터가 결정하고 보고**(사용자 재확인 불필요).
- ★9(신규): 계정형 소스는 `enabled=False`로 등록하고 스태프가 admin에서 활성화 — **권고 승인**(PSO 결정과 정합). 대안: 자동 활성(공식 판단이 틀리면 잘못된 계정을 주기적으로 읽음).
- ★10(신규, AIA 발견): "콘서트"는 카테고리 어휘 6종 [코드 `core/vocab.py:21-28`]에 없어 그대로면 콘서트 드래프트는 "승인 가능" 정의(카테고리 채움)를 영원히 못 넘는다 —
  **권고: `CATEGORY`에 `("concert", "콘서트")` 1건 추가**(어휘 개수 고정 테스트 0건 [실측 rg], 소비자 칩은 별도 큐레이션이라 자동 노출 없음). 대안: 어휘 밖으로 두고 빈 카테고리
  + 사유 메모로만 수집(§D).
- ★11(신규, WED·BIR 발견): 스태프 셸 기존 결함 2건을 같은 트랙에서 수정 — `base_staff.html:59` 메시지 컨테이너 `role="status"`, 대시보드 `.staff-cta:disabled` 규칙 —
  **권고 승인**(2026-08-25 규약: 같은 성격 소규모 결함은 같은 트랙).
- U2(신규, 사용자 액션): 첫 실기동에 쓸 검색어와 기대 행사 목록(정답표 시드, 한두 건 [계산 권고]). AIA 권고 표본 유형 5가지 [계산](정탐 다수·어휘 밖 유형·공식 결과 없음·
  인스타 편중·일본어 표기 전용)은 착수 후 동결 표본 구성 시 반영.

## Deferred / 문서 대상 / 핸드오프
- v2 절 계승. 추가 핸드오프: 탐색은 URL·판단만, 읽기는 결정론, 해석은 도구 0개 / 계정형 소스는 비활성 등록 / SNS 호스트 서버 무fetch는 행위 계약(KW-07) / X는 URL 단위
  런타임 판정 / 요청당 이벤트 1건 / 실행당 상한·완료 판정은 `discovery_run` FK 기준 / `_process_run`은 소스 후보·계정형·이벤트 세 갈래를 부르는 얇은 디스패처(DAR) /
  insane-search는 미채택(참고만) / **트랙 30 완료 시 공용 함수 시그니처(`agent_drafts`·`page_fetch`·`caption_interpreter`·`register_account_source`)를
  `docs/BE/draft-source-agent-discovery.md`에 동결 기록하고 트랙 31은 그 위에 얹는다**(DAR).

---

