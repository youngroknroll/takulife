# 트랙 17: DB 연결 재사용 + 집계 쿼리 병합 + 공개 달력 범위 제한 + 공개 데이터 캐시 + 런북 갱신 (2026-09-03, v3 2026-11-12) · **상태(2026-11-12)**: 계획 v3 작성(7역할 사전 검토 통합 `[문서 이 절]`), **사용자 결정 4건 확정(2026-11-12)**, **PR #415 머지 완료(2026-11-13T13:30:39Z, merge commit `6628dee1`, 사용자 "둘 다 승인") `[실측 gh]`** — 커밋 36개 + main 합치기 1개, 합친 커밋 `d5b623de`에서 CI 6잡 전부 pass `[실측 gh pr checks]`. 선행 긴급 수정 2건(robots.txt `6e659557`, ClaudeBot 쿼리 요청 서버 차단 `f386dd0e`)은 main 푸시·production 반영 완료 `[실측 git·접근 로그]`, 서버 차단은 유지 확정(사용자 결정 2026-11-13). Supabase Pool Size 15 확인으로 배포 전 블로킹 해소 `[대시보드, 사용자 확인 2026-11-12]`. gthread는 사용자 보류. 남은 일: deploy PR(main → production, 사용자 승인) 뒤 `docs/deploy-runbook.md` §3-20·§3-21 확인.

## 갱신본 v3 (2026-11-12) — 아래 v2 본문과 어긋나는 곳은 이 절이 이긴다

> 계기: Render 청구 `[실측 청구서 CSV]` takulife 아웃바운드 13.8GB / 277.82시간,
> 포함 한도 약 5GB `[계산: 13.87GB − 과금 9GB]`, 내역 HTTP 응답 7.49GB +
> Service-Initiated 6.38GB `[실측 Render Metrics]`. 2026-11-07 오전부터 시간당
> 약 8MB → 40~80MB `[실측 그래프 판독]`.
> 원인 `[실측 production 접근 로그 2026-11-12 22:59 KST]`: User-Agent
> `ClaudeBot/1.0`이 `/events/calendar/`를 초당 약 10건 `[로그 판독, 정밀 집계
> 아님]` 요청. 달력 `?month=`에 범위 제한이 없어 이전/다음 달 링크와 날짜 칸
> 링크가 끝없이 이어진다 `[코드 web/views/_helpers.py:90-107,
> templates/core/partials/_calendar_grid.html:37]`.
> 사용자 지시(2026-11-12): "DB 쿼리 요청 최적화가 필요해", 선택지 "3번"(연결
> 재사용 + 집계 병합 + 공개 데이터 캐시를 한 트랙), "백로그가 생기면 다음으로
> 넘기지 말고 처리하도록", robots.txt 선행 수정은 "선택 1 진행"(계획 승인 전
> 예외) `[문서 사용자 지시]`.
> 재측정 `[실측 2026-11-12, 로컬 Postgres, 게시 행사 181건, CaptureQueriesContext]`:
> 비로그인 `/` 8쿼리·SQL 6,495바이트(압축 HTML 5,977바이트 `[실측 curl]`),
> `/events/` 5쿼리·2,276바이트, `/events/calendar/` 3쿼리·2,055바이트,
> `/events/<id>/` 2쿼리, `/?month=2031-05` 200에 8쿼리, 로그인 `/` 26쿼리·
> 15,786바이트, 로그인 `/events/` 9쿼리. 404·`/robots.txt`·`/api/health/`는
> 0쿼리. 착수 시 재측정한다.
> 운영 사실 정정 `[실측 Render 배포 로그]`: Render가 `WEB_CONCURRENCY=1`을
> 넣어 **워커는 1개**다(v2와 검토 일부는 3개로 가정). 헬스 체크는 5초 간격
> `/api/health/`.

### 승인 범위 추가·정정 (v2 범위에 더한다)

- **A (v2 범위 첫 항목, 정정)**: 연결 수 재계산 `[계산]` — 상시 1(워커 1개),
  정기 명령 2종(`purge_deleted_accounts`, `prune_operational_data`)·운영자
  명령이 겹치면 4, 배포 중첩(구 워커 1 + migrate 1 + 신 워커 1)까지 겹치면
  최악 6. Pool Size 사전 블로킹 유지(비교 기준 6). 런북 새 항목 번호는
  §3-15가 아니라 **§3-20 이후**(§3은 현재 19번까지 사용
  `[실측 rg docs/deploy-runbook.md]`).
- **A+ 헬스 체크**(사용자 결정 2026-11-12 "db 확인은 30분으로 정정"
  `[문서 사용자 지시]`): `core/views.py` `health()`는 기본적으로 DB를 건드리지
  않고 200을 돌려준다. DB 확인은 커서로 `SELECT 1`을 실행하되, 마지막 확인
  뒤 30분(1,800초)이 지났을 때만 한다. 간격은 `core/views.py` 모듈 상수 한
  곳, 마지막 확인 시각은 프로세스 메모리에 둔다(워커 1개
  `[실측 Render 배포 로그]`). DB 확인이 실패하면 503이고 다음 호출에서 다시
  확인한다(실패는 간격을 채운 것으로 치지 않는다).
  근거 `[실측 production 접근 로그]`: Render 헬스 체크가 5초마다 1건, 30초마다
  1건 더 와서 하루 20,160건 `[계산]`인데, 지금은 호출마다 Supabase에 새 TLS
  연결을 맺어 월 약 0.87~1.44GB `[계산, 호출당 1.5~2.5KB는 DOR 추정]`를 쓴다.
  30분 간격이면 하루 48회, 월 1,440회 `[계산]`로 월 약 0.28~3.52MB
  `[계산, 호출당 0.2~2.5KB 추정]`다.
  감수하는 것: DB가 끊겨도 헬스 체크는 최대 30분 동안 200을 낸다(사용자
  요청은 즉시 실패). Supabase 7일 일시정지 방지는 하루 48회 확인으로 유지된다.
- **B+**: `web/views/events.py` `event_list`의 `qs.count()`를 지우고
  `get_page` 뒤 `total_count = paginator.count`로 읽는다(COUNT 2회 → 1회,
  기대 5 → 4쿼리 `[계산]`). 컨텍스트 키·값 계약 불변.
- **D 공개 달력 범위 제한**(홈 달력, `/events/calendar/` 두 곳만 `[코드]`):
  - 새 함수 `_parse_public_calendar_month(raw_month, *, today)`를
    `web/views/_helpers.py`에 두고 두 공개 호출처만 전환한다.
    `_parse_calendar_month`와 로그인 전용 `/archive/calendar/`
    (`web/views/activity.py:231` `[코드]`)는 건드리지 않는다(본인 기록 열람이
    핵심 가치, 크롤러 미도달 — PSO·DAR·SRR 일치).
  - 허용 범위: `timezone.localdate()` 기준 과거 24개월 ~ 미래 12개월, 경계
    포함, 37개 달 `[계산]`. 로컬 게시 행사는 최소 시작일 15개월 전, 최대
    종료일 2개월 뒤 `[실측 로컬 2026-11-12]`라 범위 안이다. **운영 DB는
    미측정** — 착수 시 운영 집계로 확인하고 넘치면 1개월 `[문서 PSO]` 여유로
    넓힌다. 값은 `_helpers.py` 모듈 상수 한 곳.
  - 범위 밖 처리 **(사용자 결정 대기 — 아래 "결정 필요" 첫 항목)**: 권고는
    쿼리 실행 전 302로 month·date를 뺀 같은 경로로 보내기(SRR). 대안은 기존
    invalid 경로 재사용(200, 이번 달 표시 — PSO·DAR)인데 지금과 같은 쿼리·
    응답 크기가 나간다 `[실측 /?month=2031-05 8쿼리]`.
  - 경계 달에서 `prev_month`/`next_month`는 `None`. 템플릿은 비활성 글리프를
    낸다(아래 Frontend Review Evidence).
  - 범위 밖 달의 채움 칸(`in_month=False`)은 링크가 아닌 요소로 낸다(BIR
    결함 High). 공개 달력의 월 이동·날짜 칸 링크에 `rel="nofollow"`.
  - robots.txt 6줄 `[코드 core/views.py]`은 선행 수정으로 반영 완료(main
    `6e659557`).
- **C 공개 데이터 캐시**(축소 범위 — PSO·DAR):
  - `config/settings.py` `CACHES`에 별칭 `"public"`(LocMemCache, 고유
    `LOCATION`, `MAX_ENTRIES` 200 `[선정: 키 종류는 홈 1 + 달 37 + 카테고리
    1 계산, 값 크기는 한 달 행사 8건 6,784바이트·게시 181건 전체 69,206바이트
    실측 pickle]`). `"default"`(DatabaseCache)는 그대로 — 스로틀·잠금
    카운터는 계속 `default`만 쓰고 공개 경로는 `default`를 호출하지 않는다
    (SRR).
  - 새 모듈 `web/public_cache.py`에 함수 셋: `home_public_sections(*, today)`
    (진행중·마감임박·최근·대표 목록 + 카테고리 건수 + HomeConfig 원문 쌍),
    `public_month_events(*, year, month, today)`(필터 없는 월 조회, 홈 달력과
    `/events/calendar/` 무필터 요청이 공유), `public_category_choices()`.
    로더는 `list(...)`로 평가한 Event 인스턴스를 돌려준다. 데코레이터·
    레지스트리·공용 헬퍼는 만들지 않는다.
  - 캐시 밖: 사용자별 상태(`_attach_display`), today 의존 파생값, 번역된
    라벨(`_translate_category_label`은 요청마다), 행사 상세, `/events/` 목록
    행, 필터(`q`·region·category·status·sort 등)가 하나라도 있는 요청, 범위
    밖 월, 조회 실패 결과.
  - 키에 로컬 날짜 포함. 언어는 키에 넣지 않는다(공개 화면에서
    `select_display` 호출 0건 `[실측 rg]`, 라벨은 지연 번역).
  - TTL 60초 `[문서 PSO]`, 무효화는 TTL만. 쓰기 경로에 캐시 삭제를 넣지
    않는다(`events → web` 임포트는 가드 금지, 워커별 메모리라 즉시 반영 보장
    불가). 결과: 게시·수정·비공개가 홈과 달력에 최대 60초 늦게 반영, 상세는
    즉시 404.
  - 끄는 스위치 env `PUBLIC_CACHE_TTL_SECONDS`(기본 60 `[문서 PSO]`, 0이면
    캐시 호출 생략, 비정수·음수는 `ImproperlyConfigured`) — DOR.
  - 테스트 격리: `config/settings_test.py`에서 `"public"`만 DummyCache로
    덮고(`default`는 유지), 캐시 테스트만 opt-in 픽스처로 LocMem을 켠다(코치
    X안). `settings_test.py:10-11` `[코드]` 독스트링을 "default는 덮지
    않는다"로 고친다.
- **같은 종류 소규모 결함(같은 트랙 처리)**: `events/serializers.py:29` `q`에
  `max_length=100`(archive `_archive_query`의 100자와 맞춤 `[코드
  web/views/_helpers.py:27]`); `event_detail`은 HEAD 요청에서 조회수 증가를
  건너뛴다(SRR).

### 배제 정정 (v2 "배제"에 더한다)

- v2 "Redis 등 외부 캐시·페이지 캐시" → **정정**: 외부·유료 캐시, CDN,
  DatabaseCache 재사용, 렌더된 HTML 캐시는 계속 배제. 프로세스 내 메모리
  캐시의 공개 데이터 캐시는 위 C로 승인 범위에 들어온다.
- v2 "홈 외 페이지의 추가 쿼리 감축" → B+ 외에는 계속 배제.
- `/events/` 목록 행 캐시, 스태프 화면 캐시, 스태프 액션 시 전 워커 무효화.
- `/archive/calendar/` 범위 제한.
- 공개 HTML 경로의 요청 수 제한 — **선행 조건 미충족**: 운영 프록시 홉 수
  (런북 §3-8 `[문서 docs/deploy-runbook.md:132]`) 미실측이라 IP 식별자를
  신뢰할 수 없다(SRR). 홉 수 실측은 사용자 몫.
- 조건부 GET(`ConditionalGetMiddleware`) — 페이지 본문에 요청마다 바뀌는
  CSRF 토큰이 들어가 ETag가 일치하지 않는다 `[코드 Django CSRF 마스킹]`.
- `/jsi18n/` 캐시 헤더 — 2,658바이트 gzip `[실측 curl]`, 쿼리 0건
  `[실측]`, 크롤러는 받지 않는다 `[실측 접근 로그]`.
- 접근 로그에 클라이언트 IP 추가 — 개인정보 판단이 필요한 사용자 결정
  (현재 `%(h)s`는 Render 내부 주소 `[실측 접근 로그]`).

### 수용 기준 추가 (v2 기준에 더한다)

- AC-B1: `/events/` 기본 조회 쿼리 수가 Red 실측 기준보다 1 `[계산]` 줄고
  COUNT는 1회. AC-B2: `total_count`·`page_obj`·`event_rows`와
  ValidationError 경로 불변(12건 > 페이지 크기 10
  `[코드 events/queries.py:13]`에서 12 표시).
- AC-D1: 공개 달력 두 화면 `[코드]`에서 하한·상한 달은 표시되고, 한 달
  밖은 결정 첫 항목대로 처리된다(302안이면 쿼리 0건, Location은 쿼리 없는
  같은 경로).
- AC-D2: 하한 달 `prev_month`, 상한 달 `next_month`가 `None`이고 범위
  안에서는 둘 다 값이 있다.
- AC-D3: 경계 달 그리드에서 범위 밖 달의 채움 칸에 `href`가 없다.
- AC-D4: 로그인 `/archive/calendar/`는 60개월 `[문서 PSO]` 전 달도 기존대로
  표시(회귀 핀).
- AC-D5: `?month=2031-5`처럼 한 자리 월도 같은 (연, 월)로 판정된다
  (`strptime`이 받는다 `[실측]`; 비ASCII 숫자는 거부된다 `[실측]`).
- AC-C1: 같은 공개 요청을 TTL 안에 반복하면 두 번째는 쿼리가 더 적고 행사
  제목 목록이 같다. AC-C2: 그 경로에서 `django_cache` 테이블 쿼리 0건
  `[계산]`.
- AC-C3: 캐시가 채워진 상태에서 사용자 A·B·비로그인의 찜·방문 상태가
  각자 값. AC-C4: 본인 상태 변경은 TTL 안에도 즉시 보인다.
- AC-C5: 비공개 전환 직후 상세는 404 `[코드 web/views/events.py:589]`,
  홈·달력은 TTL 경과 뒤 요청에서 빠진다.
- AC-C6: 로컬 날짜만 바뀌어도 값이 바뀐다. AC-C7: 필터 있는 요청·범위 밖
  월·조회 실패는 캐시에 쓰이지 않는다. AC-C8: `PUBLIC_CACHE_TTL_SECONDS=0`
  `[문서 DOR]`이면 캐시를 거치지 않는다.
- AC-H1: `/api/health/` 첫 호출은 DB에 `SELECT 1`을 실행해 200, 그 뒤
  30분 `[문서 사용자 지시]` 안의 호출은 쿼리 0건으로 200, 30분이 지난 뒤
  호출은 다시 DB를 확인한다. AC-H2: DB 확인 실패 시 503이고 바로 다음
  호출도 DB를 다시 확인한다(응답 본문 계약 불변 `[코드 core/views.py]`).
- AC-E1 [사후 비블로킹]: 배포 뒤 7일 `[문서 PSO]` Render 시간당 아웃바운드와
  접근 로그의 경로·UA별 건수를 기록해 2026-11-07 이후 구간과 비교. 통과
  임계값 없음.

### Test List 추가 (코치 확정, 상세 GWT는 구현 계약 때)

v2 S1~S10 유효 `[문서 코치 재확인]`. 보완: S1은 `DB_CONN_MAX_AGE` 삭제와
`BASE_DIR` 패치 필요(`_get_env`가 `.env`를 읽는다
`[코드 config/settings.py:11-23]`).

| # | 내용 | 위치 | 구분 |
|---|---|---|---|
| H1 | `/api/health/` 첫 호출은 DB 확인, 간격(30분 `[문서 사용자 지시]`) 안의 호출은 쿼리 없음 | tests/core (기존 health 테스트 파일) | Driving |
| H2 | 간격이 지나면 다시 DB 확인(가짜 시계) | 〃 | Driving |
| H3 | DB 확인 실패는 503, 바로 다음 호출도 다시 확인 | 〃 | Driving |
| H3b | 실패 뒤 복구된 확인은 간격을 채워 다음 호출은 쿼리 없음(코치 신규 발견 2026-11-13) | 〃 | 핀·뮤테이션 |
| H4 | 마지막 확인 뒤 정확히 30분이면 다시 확인, 29분 59초면 건너뜀(`>=` 경계, 코치 Green 뒤 판정에서 발견 `[문서 코치]`) | 〃 | 핀·뮤테이션 |
| B0 | 페이지 크기(`[코드 events/queries.py:13]` 10)보다 많은 12건에서 `total_count`가 전체 건수 | tests/events/test_event_list_view.py | 핀·뮤테이션 |
| B1 | `/events/` 쿼리 상한(Red 실측, 기대 5→4 `[계산]`) | 〃 | Driving |
| D0 | 기존 `test_유효한_극단적_월은_클램프_없이_그대로_렌더링된다`를 새 계약으로 개정(D1과 같은 커밋) | tests/core/test_events_calendar_view.py | 기존 테스트 개정 |
| D1 | 행사 달력: 하한·상한 안/밖 네 케이스 | 〃 | 밖 Driving, 안 핀·뮤테이션 |
| D2 | 홈: 범위 밖 `?month=` 처리 | tests/events/test_home_calendar.py | Driving |
| D3 | 경계 달 `prev_month`/`next_month` None | 두 파일 | Driving |
| D3b | 범위 중간은 둘 다 값 | 〃 | 핀·뮤테이션 |
| D3c | 경계 달 범위 밖 채움 칸 비링크 | 〃 | Driving |
| D6 | `/archive/calendar/`는 60개월 `[문서 PSO]` 전 달도 정상 | tests/core/test_activity_calendar_view.py | 핀·뮤테이션 |
| D7 | 고정 달을 쓰는 기존 테스트의 시계 의존 제거(`month=` 사용 11개 파일·52곳 `[실측 rg month= tests]` 중 today 미패치분, 착수 시 목록화) | 해당 파일 | 기존 테스트 보호 |
| Q1 | `q`가 상한(100자 `[코드 web/views/_helpers.py:27]`)을 넘으면 검증 오류, 상한까지는 통과 | tests/events | Driving |
| V1 | 상세 HEAD는 조회수 불변, GET은 증가 | tests/events | Driving / 핀 |
| C0a | 운영 설정에 `"public"` LocMem 별칭 | tests/core/test_settings_env.py | Driving |
| C0b | 테스트 설정은 `"public"`만 DummyCache | tests/core/test_test_settings_boundary.py | Driving |
| C0c | `PUBLIC_CACHE_TTL_SECONDS` 기본값(60 `[문서 PSO]`)·0·비정수 — 코치가 C0c-1(기본값)·C0c-2(0)·C0c-3(비정수)로 나눴다(2026-11-13). C0c-2·C0c-3은 C0c-1 Green 뒤 이미-Green 예상 → 핀·뮤테이션 | tests/core/test_settings_env.py | C0c-1 Driving |
| C0c-4 | `PUBLIC_CACHE_TTL_SECONDS`가 음수면 설정 오류(본문 "비정수·음수는 `ImproperlyConfigured`"와 짝, 코치 신규 발견 2026-11-13) | 〃 | Driving |
| C1 | TTL 안(+59초 `[문서 코치]`)은 낡은 값. `web/public_cache.py` `public_month_events` 함수 직접 호출(도메인 경계), 뷰 배선 없음 | tests/events/test_public_cache.py(신규) | Driving |
| C2 | TTL 뒤(+61초 `[문서 코치]`)는 새 값 | 〃 | 핀(C1 뒤)·뮤테이션 |
| C2b | TTL 0이면 두 번째 호출도 조회한다(AC-C8과 짝, 코치 신규 발견 2026-11-13) | 〃 | Driving |
| C3 | 날짜가 바뀌면 값이 바뀜 | 〃 | Driving |
| C4 | 언어가 달라도 라벨이 섞이지 않음 | 〃 | 핀·뮤테이션 |
| C5 | 달이 다르면 다른 결과 | 〃 | Driving |
| C6 | A의 찜·방문이 익명·B에 안 나옴 | 〃 | 핀·뮤테이션 |
| C7 | 본인 상태 변경 즉시 반영 | 〃 | 핀·뮤테이션 |
| C8 | 조회 실패는 캐시되지 않음 | 〃 | 핀·뮤테이션 |
| C9 | 준비→비움→콜드→웜에서 웜 < 콜드. 뷰 배선 확인 행이고, Then에 `django_cache` 쿼리 0건(AC-C2와 짝, 코치 신규 발견 2026-11-13)을 함께 둔다 | 〃 | Driving(보조) |
| C10 | 필터 있는 요청은 캐시 미사용(두 번 요청의 쿼리 수 동일) | 〃 | 핀·뮤테이션 |
| C11 | 기존 `test_월_조회가_실패하면_…`(`test_events_calendar_view.py:404` `[실측 rg 2026-11-13, 계획 작성 때 287행]`)의 패치 대상이 캐시 래퍼 뒤에서도 유효 | 기존 테스트 | 기존 테스트 보호 |

C 묶음 메모(2026-11-13 코치 계약): LocMem 가짜 시계는 `django.core.cache.backends.base.time`(만료 시각 계산)과 `django.core.cache.backends.locmem.time`(만료 판정) 두 곳을 같은 시계로 바꾼다 `[실측 inspect]`. DatabaseCache용 `cache_clock`(위 선례)은 그대로 쓸 수 없다.

C 묶음 추가 행(코치 2차 계약 2026-11-13, 위치는 전부 tests/events/test_public_cache.py, 도메인 경계):

| # | 내용 | 구분 |
|---|---|---|
| C-HOME-1 | `home_public_sections(today=...)`가 네 구간·카테고리 건수·`HomeConfig` 원문 쌍을 한 항목으로 담아 TTL 안 재호출은 쿼리 없이 같은 값 | Driving |
| C-HOME-2 | today가 다르면 홈 구간 캐시도 분리 | Driving |
| C-CAT-1 | `public_category_choices()`가 (slug, 원문 라벨)을 TTL 안 재호출 시 쿼리 없이 돌려줌(번역은 호출자) | Driving |
| C-CAT-2 | TTL 뒤 카테고리 선택지도 새로 조회 | 핀 예상 |
| C-HOME-3 | TTL 0이면 저장소 장애에도 홈 공개 섹션을 돌려준다(QVL이 표 누락 지적, 커밋 `6508345c`) | Driving |
| C-CAT-3 | TTL 0이면 저장소 장애에도 카테고리 선택지를 돌려준다(같은 지적, 커밋 `6508345c`) | Driving |
| C-HIDE | 비공개로 바뀐 행사는 달력에서 TTL 동안 남았다가 TTL 뒤 빠진다(AC-C5 제거 방향, QVL 잔여). 상세 즉시 404는 기존 `tests/events/test_event_detail_view.py:60-63`이 지켜 중복이라 뺐다(코치) | 핀 |
| S1 | 행사 달력의 인식되지 않는 필터 값은 조회 없이 빈 달력(SRR, `c52f28ba`) | Driving |
| S2 | TTL > 0에서 저장소 `get`·`set` 장애는 로그 후 DB 값(SRR, `4e127a41`) | Driving |

표 밖에서 추가됐던 행(QVL 지적 2026-11-13): B0b(잘못된 필터 → `total_count` 0, `3d4293e7`), S7b(방문 기록 0건 사용자 1쿼리 핀, `70d3f8da`) — 진행 기록 표에 증거가 있다.
| C9a | `/events/calendar/` 무필터(`not params` `[코드 events/queries.py:30-42]`)만 `public_month_events` 사용 + C11 패치 대상을 `web.public_cache.list_published_events_for_month`로 옮김(같은 커밋) | Driving |
| C9b | 홈 달력이 `public_month_events` 사용 | Driving |
| C9c | `_translated_category_choices()`가 `public_category_choices()` 원문을 받아 요청마다 번역 | Driving |
| C9d | 홈 네 구간·카테고리 건수·HomeConfig가 `home_public_sections` 사용, `_attach_display_many(user=...)`는 캐시 밖 그대로 | Driving |

순서(C 묶음): C1 → C2 → C2b → C3 → C5 → C8 → C-HOME-1 → C-HOME-2 → C-CAT-1 → C-CAT-2 → C9a(+C11) → C10(달력) → C9b → C9c → C10(선택지)·C4 → C9d → C4(홈 타일)·C6·C7 → C9(웜<콜드, `django_cache` 0건). 화면별 배선 계약(C9a~C9d·C4·C6·C7·C10의 GWT)은 그 단계에서 코치가 하나씩 낸다. 홈 달력은 조회 실패 완화(try/except)가 없고 `/events/calendar/`는 있다 `[코드 web/views/events.py:142, 474-480]` — 배선은 이 차이를 유지한다.

DAR 사후 검토(2026-11-13, 세 함수 Green 뒤): 의존 방향(`web → core.models·events.models·events.queries`)과 위치는 규칙에 맞고 캐시 값에 사용자별 데이터가 섞일 경로가 없다 `[문서 DAR]`. (1) 세 함수의 "TTL 0 분기 → get → 조회 → set" 반복은 모듈 내부 비공개 함수 `_cached(cache_key, load)` 하나로 묶는다 — 위 C 절의 "공용 헬퍼는 만들지 않는다"는 DAR이 데코레이터·레지스트리·모듈 밖 공유를 막는 뜻으로 재해석했다(사용자 전역 규칙 "반복 3회면 묶는다"). Refactor 커밋으로 따로 둔다. (2) **C9d 차단 조건**: `home_public_sections()`의 dict에는 행사 목록이 아닌 값(`category_counts`, `featured_category_pairs`)이 있어 그대로 `_attach_display_many`에 넘기면 깨진다 → 행사 목록 4개 키만 골라 로그인 `upcoming_planned`와 합쳐 한 번 부르고, 나머지 둘은 `category_tiles` 조립에만 쓴다. (3) 관찰: `_load_home_public_sections`의 ORM 체인은 원래 `home()` 뷰에 있던 것을 옮긴 기존 결함(규칙은 `events.queries` 명명 함수)이고, `events/` 쿼리 변경은 위 "대상 파일"의 "변경 없음"에 걸려 사용자 결정 대상이다.

정정 기록(오케스트레이터, 2026-11-13, C9a): C11 계약 때 같은 패치를 쓰는 다른 테스트를 저장소 전체 `rg`로 찾지 않아, `tests/core/test_event_ui_translations.py:754`(달력 조회 실패 번역, 매개변수 2개)가 C9a 뒤 전체 회귀에서 2건 실패로 드러났다 `[실측]`. 같은 커밋에서 C11과 같은 방식으로 고친다(C11b). 같은 `rg`로 C9d 영향도 미리 찾았다: `tests/core/test_error_pages.py:43,80`, `tests/core/test_error_groups.py:610`이 `web.views.events.list_published_events`를 패치하고 `/`를 요청해 500을 만든다 `[실측 rg]` — C9d에서 홈이 `web.public_cache`를 거치면 패치 대상을 `web.public_cache.list_published_events`로 옮겨야 한다.

DAR 배선 사후 확인(2026-11-13, C9a~C9d·핀 커밋 뒤): 결함 0건 `[문서 DAR]` — C9d 차단 조건 충족(행사 목록 네 키만 `_attach_display_many`), 달력 완화 있음·홈 달력 완화 없음 비대칭 유지, `HomeConfig`·`Count`·`consumer_category_choices` 임포트가 `web/views/events.py`에서 빠졌고 남은 사용처 0건, `web.views.events → web.public_cache`는 두 가드의 대상이 아니다. ORM 체인 관찰은 사용자 결정 대상 그대로.

SRR 사후 검토(2026-11-13, C 묶음 뒤): 사전 지적 4항목(범위 밖 302·캐시 별칭 분리·키 허용 조건·HEAD 조회수) 해소, Critical·High 0건, 캐시 키 동시 최대 39개 `[계산 SRR: 37 + 1 + 1]` < `MAX_ENTRIES` 200, `"public"` 교차 사용 0건 `[문서 SRR rg]`. 새 결함 2건 — 같은 종류 소규모라 같은 트랙에서 고친다(사용자 결정 2026-11-12): S1(Low) `event_calendar()`의 잘못된 필터 값(`ValidationError`)이 주석의 "매치 없음"과 달리 그 달 전체 목록을 보여준다(트랙 전부터의 동작, C9a 뒤 캐시 경로를 탄다); S2(Medium) TTL > 0에서 공개 캐시 저장소 `get`·`set` 예외가 그대로 전파돼 홈·목록·달력 선택지가 500(완화는 달력 월 조회 한 곳뿐). 차단 아님 기록: 긴급 비공개 전환에 60초 미만 반영이 필요해지면 전 워커 무효화 재검토, 피클 크기 수치는 운영 행사 수가 181건 `[문서 계획서]`을 넘기 전 재측정.

DOR 문서 사후 검토(2026-11-13, 문서 커밋 전): High 0건, Medium 2건(런북 `docker/entrypoint.sh:15` 인용 → 실제 `--workers`는 19행 `[실측 grep]`; 백로그 트랙 17 행의 코드 상수 숫자에 출처 태그 없음), Low 5건(§3 서두 개수 태그, 운영 런북 기본 60초 태그, §5 "재빌드 없음" 단정 미검증, 헬스 확인 빈도는 워커 수에 비례, `SELECT 1`이 Supabase 7일 비활성 판정에 잡히는지 미확인) `[문서 DOR]` — 전부 문서 커밋 전에 반영. 확인 완료: 헬스 1,800초·하루 48회, robots Disallow 11줄, 연결 최악 6 ≤ 15, 접근 로그 `awk -F'"'` 필드 2·4, 공개 캐시 env 검증 `[문서 DOR, 코드 대조]`.

C9 재판정(코치 2026-11-13): "준비→비움→콜드→웜에서 웜 < 콜드"는 화면별 C9a~C9d가 각자 증명하므로 버리고, 고유 주장인 AC-C2만 C9-DEFAULT("홈·목록·달력 요청에서 `django_cache` 테이블 쿼리 0건", 핀 예상, 뮤테이션 `CACHE_ALIAS = "default"`)로 남긴다. C9d 뒤 남은 행: C4-HOME(홈 타일 en→ko→en), C6(A의 찜이 익명·B 홈에 안 보임), C7(본인 찜 변경 즉시 반영) — 전부 핀 예상. 홈 500 테스트 세 개(`tests/core/test_error_pages.py:43,80`, `tests/core/test_error_groups.py:610`)는 패치 대상을 `web.public_cache.home_public_sections`로 옮긴다(내부 조회 순서에 묶이지 않는 홈의 유일한 공개 캐시 진입점, C9d 커밋).

함정 기록(C9b, 2026-11-13): 홈 두 번 요청 비교에서 C9b가 Red 없이 통과했다. 캐시 없이 SQL을 비교하니 첫 요청 11쿼리·둘째 8쿼리이고, 차이 3쿼리는 `HomeConfig.get_solo()`의 `get_or_create`가 첫 요청에서 행을 만드는 SAVEPOINT·INSERT·RELEASE였다 `[실측 CaptureQueriesContext]`. Given에서 `HomeConfig.get_solo()`를 먼저 불러 두니 `assert 8 < 8`로 맞는 Red가 났다 `[실측]`. 홈 쿼리를 비교하는 C9d·C9도 같은 Given이 필요하다.

C2b 판정(오케스트레이터, 2026-11-13): 코치는 Django가 `timeout=0`을 즉시 만료로 바꾸므로 핀으로 두자고 했으나, LocMem `set`은 TTL 0이어도 값을 피클하고 저장한다 `[실측 inspect LocMemCache.set]`. 계획 본문의 끄는 스위치("0이면 캐시 호출 생략", DOR)는 캐시 계층 장애 때도 들어야 하므로, "TTL 0이면 저장소가 `get`·`set`에서 예외를 던져도 조회 결과를 돌려준다"를 Driving으로 둔다.

시간 제어는 `tests/auth/test_account_deletion.py:47-97` `[코드 코치]`의 가짜
시계 선례를 LocMem용으로 쓴다(실제 sleep 금지). 쿼리 수 핀은 상한·상대 단언
+ 같은 테스트의 200 `[코드]`·내용 단언과 함께만 둔다.

순서: S1~S5 → H1·H2·H3 → S6 → S7 → S9/S8/S10 → B0/B1 → Q1·V1 → D0+D1 → D2 →
D3·D3b·D3c(+템플릿) → D6·D7 → C0a~c(+픽스처) → C1 → C2 → C3 → C4 → C5 →
C6 → C7 → C8 → C9 → C10. 제약: C2는 C1 뒤, C3·C5는 C1 최소 Green 뒤, C0b는
C1 생산 코드보다 앞, D0은 D1 Green과 같은 커밋, S1~S4 Green 직후 전체 회귀와
e2e 실행.

### 진행 기록 (2026-11-13, 브랜치 `perf/track-17-db-public-cache`)

| 묶음 | 커밋 | 항목 | 증거 |
|---|---|---|---|
| A | `a751a809` | S1~S5 Green, `.env.example`에 `DB_CONN_MAX_AGE=600` | S1~S4 Red 이유 4건이 코치 예상과 일치, S5 뮤테이션 Red→복원 Green, 전체 회귀 4,402 passed·e2e 10 passed `[실측]` |
| A+ | `a10bf421` | H1~H3, H3b Green | H1·H2 Red 이유 일치, H3·H3b 뮤테이션 2종 각각 Red, 전체 회귀 4,405 passed `[실측]` |
| A+ | `38023d09` | H4 경계 핀 2건 | `>`·간격−1초 뮤테이션이 각각 해당 핀만 Red `[실측]` |
| A+ | `fd10efaa` | 헬스 OpenAPI summary를 "DB 연결은 30분에 한 번 확인"으로 | 전체 회귀 4,407 passed `[실측]` |
| 집계 | `46fadbeb` | S6 컬렉션 요약 집계 `.count()` 4회 → `aggregate()` 1회, `OWNED_Q`·`TRADEABLE_Q` 상수 | Red "1 기대, 4회" `[실측]`; 뮤테이션 3종(교환가능 조건 제거·`gte`·4회 복귀) 각각 Red, 4회 복귀는 새 핀만 Red; 전체 회귀 4,408 passed `[실측]` |
| 집계 | `70d3f8da` | S7 방문 기록 요약 집계 `.count()` 2회 → `aggregate()` 1회, 핀 2건(일반·0건) | Red "1 기대, 2회" `[실측]`; 부호 반전은 새 일반 핀만 Red(기존 값 테스트는 후기 1:1이라 못 잡음), 조건 제거는 2건 Red, 2회 복귀는 새 핀 2건만 Red; 전체 회귀 4,410 passed `[실측]` |
| 집계 | `e955a48c` | S9/S8/S10 홈 다섯 구간 상태·관심 조회 병합(`_attach_display_many`) | 테스트 Given(다섯 구간 모두 채움) 로그인 29쿼리 중 상태 5·관심 5 `[실측 SQL 분류]` → 상한 21 `[계산 29−8]`, Green 뒤 정확히 21·비로그인 11 `[실측, 상한−1 탐침]`; 뮤테이션 4종(구간별 호출 복귀는 S9만, 첫 구간만 사용자 조회는 S10만, 행 정렬 어긋남은 S10+기존 1건, 구간 재평가는 S9·S8 Red); 전체 회귀 4,413 passed·e2e 10 passed `[실측]`. 로컬 데이터 로그인 `/` 22→18, 비로그인 8 불변 `[실측 스크래치 측정]` |
| 집계 | `c91d8144` | DAR 사후 검토 Low 1 반영: `_attach_display_many` 독스트링에 "입력마다 한 행, 입력 순서" 전제 명시 | 코드 줄 변경 없음 |
| 집계 | `2dc6dbd8` | DAR 관찰 반영(사용자 승인 2026-11-13 "같은 트랙에서 수정"): `not_owned()`·`not_tradeable()`을 `exclude(OWNED_Q)`·`exclude(TRADEABLE_Q)`로 | 기존 테스트가 지킴 — `not_owned()` 조건 반전 시 기존 2건 Red `[실측]`. 모델 프로퍼티 `is_owned`·`is_tradeable`은 파이썬 비교라 유지 |
| B | `3d4293e7` | B0·B0b·B1: `event_list`가 `qs.count()` 대신 `paginator.count` | Red 5쿼리 중 COUNT 2회 `[실측 SQL]` → 상한 4 `[계산 5−1]`; B0b(잘못된 필터 → `total_count` 0)는 코치가 찾은 AC-B2 무단언 빈틈; 이번 페이지 행 수 뮤테이션은 B0·B1 Red; 전체 회귀 4,415 passed `[실측]` |
| 소규모 | `08f76b07` | Q1 공개 목록 `q` `max_length=100` | 101자 Red "DID NOT RAISE" `[실측]`; 상한 99는 100자 핀만, 200은 101자 테스트만 Red; 전체 회귀 4,417 passed `[실측]`. API 단위 별도 핀은 두지 않음(400 배선은 다른 필드 테스트가 덮음) |
| 소규모 | `105f0138` | V1 상세 HEAD는 조회수 증가 생략(`!= "HEAD"`) | Red `2 == 0` `[실측]`; 조건 반전은 새 HEAD 테스트와 기존 GET 2회 테스트 둘 다 Red; 전체 회귀 4,418 passed `[실측]` |
| D | `c1e03322` | D0+D1 행사 달력 범위 제한(`_parse_public_calendar_month`, 범위 밖 302, `_redirect_without_calendar_params`) | Red: D0 `200 == 302`, D1-out "0 기대, 3회" `[실측]`; 범위를 한 달 넓히면 범위 밖 3건만, 좁히면 경계 핀 2건만 Red `[실측]`(코치의 "24→23이면 범위 밖 Red" 예측은 방향이 반대였다); 전체 회귀 4,423 passed `[실측]` |
| D | `320aeea8` | D5 공개 달력 month·date의 비ASCII 숫자 → 형식 오류(`_parse_public_calendar_date` 신설, 공용 파서 불변) | Red: 월·날짜 각 2건 오류 패널 없음 `[실측]`; 한 자리 월 핀은 길이 7 강제 뮤테이션에서만 Red `[실측]`; 전체 회귀 4,428 passed `[실측]` |
| D | `b0c52d40` | D2 홈 달력 범위 제한(`home()`이 조회 전에 파싱·302, `_home_calendar_context`는 파싱 결과를 받음) | Red: 범위 밖 "0 기대, 11회", 비ASCII `7 == 6` `[실측]`; 리다이렉트 앞 조회 삽입 뮤테이션은 0쿼리 테스트만 Red; 전체 회귀 4,435 passed·e2e 10 passed `[실측]` |
| D | `19cea7f6` | D3·D3b·D3c 경계 달 prev/next None + 비활성 글리프, 범위 밖 채움 칸 비링크(`linkable`), `month=` 링크 전부 `rel="nofollow"`(월 이동·날짜 칸·쿼리 있는 전환 탭·홈 "달력 전체 보기"·"모두 보기") | Red 8건 + nofollow 확대 2건 `[실측]`; 뮤테이션 3종(범위 판정 반전·linkable 항상 참·그리드 nofollow 제거) 각각 해당 테스트만 Red; Playwright 1280/390/320 × 라이트/다크 × en: 글리프 박스 경계·중간 달 차이 0, 가로 넘침 0, 같은 행 span/a 칸 높이·너비 동일, 비활성 글리프 Tab 제외, 콘솔 오류 0 `[실측]`; WED Conforms·BIR Conforms(결함 0); 전체 회귀 4,445 passed·e2e 10 passed `[실측]` |
| D | `847f1940` | D6 활동 달력 60개월 전 핀 + D7 기존 테스트 16건 today 고정 | D7 대상은 범위 상수 0/0 실험으로 찾음(실패 51건 중 today 미고정 16건, 요청 달 2026-03~08 → 2028년 3~8월부터 302 `[계산]`); 고정 뒤 같은 실험의 실패 19건은 전부 today를 고정한 경계 테스트 `[실측]`; 활동 뷰를 공개 파서로 바꾸는 뮤테이션은 D6만 Red; 전체 회귀 4,446 passed `[실측]` |
| C | `b749810a` | C0a `"public"` LocMem 별칭(`MAX_ENTRIES` 200), C0c-1~4 `load_public_cache_ttl_seconds()`(기본 60·0 허용·비정수·음수 거부) | 착수 기준선 4,446 passed / 45.83초 `[실측 2026-11-13]`; Red: C0a `KeyError: 'public'`, C0c-1 `AttributeError`, C0c-4 `DID NOT RAISE` `[실측]`; C0c-2·C0c-3은 C0c-1 Green 뒤 이미-Green → 뮤테이션 `int(raw) or 60`은 C0c-2만, `except ValueError: return 60`은 C0c-3만 새로 Red `[실측]` |
| C | `4ad62c8f` | C0b 테스트 설정은 `"public"`만 DummyCache, 독스트링 정정 | Red: public BACKEND가 LocMemCache `[실측]`; 두 커밋 뒤 전체 회귀 4,452 passed / 46.44초(C1 파일 제외, +6 `[계산]`), ruff·format·`manage.py check` 통과 `[실측]` |
| C | `62835807` | C1·C2·C2b·C3·C5·C8 `web/public_cache.py` `public_month_events`(키 = 달 + 로컬 날짜, TTL 0이면 저장소 미호출), `PUBLIC_CACHE_TTL_SECONDS` 설정 상수 | Red: C1 `ModuleNotFoundError`, C2b `RuntimeError: 공개 캐시 장애 주입`, C3 "1 기대, 0회" `[실측]`; C2 첫 실패는 기대값 정렬 오류(쿼리 수는 맞음) → 테스트 정정; 핀 뮤테이션: 캐시 적중 무력화 → C1, `timeout=9999` → C2, 키의 달 고정 → C5만, 조회 예외 삼킴 → C8만 Red `[실측]`; 전체 회귀 4,458 passed / 40.21초 `[실측]` |
| C | `6508345c` | C-HOME-1~3 `home_public_sections`(네 구간·카테고리 건수·HomeConfig 원문 쌍, 키 = 로컬 날짜), C-CAT-1~3 `public_category_choices`(원문 라벨, 고정 키) | Red: C-HOME-1·C-CAT-1 `ImportError`, C-HOME-3·C-CAT-3 `RuntimeError: 공개 캐시 장애 주입` `[실측]`(TTL 0 가드는 코치안과 달리 최소 Green에서 빼 각자 드라이빙); 핀 뮤테이션: 날짜 없는 고정 키 → C-HOME-2, `timeout=9999` → C-CAT-2 Red `[실측]`; `select_related`·`prefetch_related` 0건이라 캐시된 인스턴스의 추가 쿼리 없음 `[실측 rg events/ web/views/_helpers.py]`; 전체 회귀 4,464 passed / 39.85초 `[실측]` |
| C | `11835b9c` | Refactor: 세 함수의 반복을 모듈 내부 `_cached(cache_key, load)`로(DAR 권고) | 12개 도메인 테스트 그대로 Green; `_cached`의 TTL 0 가드 무력화 뮤테이션 → C2b·C-HOME-3·C-CAT-3 Red `[실측]` |
| C | `1bd04f16` | C9a `/events/calendar/` 무필터만 `public_month_events`, C10 필터 요청은 캐시 미사용, C11·C11b 달력 조회 실패 테스트 2개의 패치 대상을 `web.public_cache`로 | Red: C9a `assert 3 < 3` `[실측]`; C10 이미-Green, 뮤테이션 `if True:` → C10만 Red `[실측]`(코치안의 "쿼리 수 같음" 대신 "새 행사가 바로 보임"으로 단언 — C9c 뒤 카테고리 선택지 캐시로 쿼리 수가 흔들리므로); C11은 C9a Green 뒤 예측대로 Red → 패치 이동으로 Green; C11b는 전체 회귀에서 2건 실패로 발견(위 정정 기록); 옛 패치 대상 0건 `[실측 rg tests/]`; 전체 회귀 4,466 passed / 40.65초 `[실측]` |
| C | `cfe895d4` | C9b 홈 달력이 `public_month_events` 사용(조회 실패 완화 없음은 그대로) | 첫 시도는 Red 없이 통과 → 원인은 첫 요청의 `HomeConfig` 행 생성 3쿼리(아래 함정 기록) → Given 정정 뒤 Red `assert 8 < 8` → Green `[실측]`; 홈 관련 테스트 80 passed, 전체 회귀 4,467 passed / 40.39초(C9c 테스트 제외) `[실측]`; 테스트 파일은 C9c 함수를 뺀 내용만 인덱스에 올려 커밋 |
| C | `444b241f` | C9c `_translated_category_choices()`가 `public_category_choices()` 원문을 받아 요청마다 번역, C10-CAT 필터 요청도 선택지는 캐시(행사 행은 매번 조회), C4 en→ko→en 라벨 안 섞임 | Red: C9c `assert 4 < 4` `[실측]`; C10-CAT·C4 이미-Green → 뮤테이션: 캐시 전에 번역 → C4만, 필터 요청은 선택지 캐시 우회 → C10-CAT만 Red `[실측]`; C10(선택지)은 코치안의 Category SQL 골라 세기 대신 결과 단언(새 카테고리 안 보임·새 행사 보임); 전체 회귀 4,470 passed / 39.31초 `[실측]` |
| C | `5f1880a0` | C9d `home()`이 `home_public_sections` 한 번으로 네 구간·건수·카테고리 쌍을 받고, 행사 목록 네 키만 `_attach_display_many`에(DAR 차단 조건), 홈 500 테스트 세 곳의 패치 대상을 `web.views.events.home_public_sections`로 | Red: `assert 8 < 8`(두 요청의 달을 다르게 해 달력 캐시 효과를 뺌) `[실측]`; 코치안의 패치 대상 `web.public_cache.home_public_sections`는 뷰가 이름으로 임포트해 닿지 않으므로 정정; 옛 패치 대상 0건 `[실측 rg]`; 전체 회귀 4,471 passed / 39.07초 `[실측]` |
| C | `530a2a86` | 핀 네 개: C4-HOME 홈 타일 en→ko→en, C6 A의 찜이 익명·B 홈에 안 보임, C7 본인 찜 즉시 반영, C9-DEFAULT 홈·목록·달력 두 번씩 요청에 `django_cache` 쿼리 0건(AC-C2) | 전부 이미-Green; 뮤테이션: 홈 카테고리 쌍을 캐시 전 번역 → C4-HOME만, 개인화 행을 날짜 키로 캐시 → C6(`KeyError`)·C7(`assert False is True`)만, `CACHE_ALIAS = "default"` → C9-DEFAULT 포함 9건 Red `[실측]`; 전체 회귀 4,475 passed / 41.61초 `[실측]`, e2e 10 passed / 10.64초 `[실측]` |
| SRR | `c52f28ba` | S1 행사 달력의 인식되지 않는 필터 값(`ValidationError`)은 조회 없이 빈 달력(`params = None` → `events = []`) | Red: `?status=zzz`에서 2026-06-10 칸 `count`가 1 `[실측]` → Green; 코치안의 "쿼리 0건" 단언은 카테고리 선택지 조회가 남아 뺐다 |
| SRR | `4e127a41` | S2 `_cached`가 TTL > 0에서 저장소 `get`·`set` 예외를 `logger.exception`으로 남기고 DB 값을 쓴다(`load()` 예외는 전파 유지) | Red: 두 id(`조회_실패`·`저장_실패`) `RuntimeError: 공개 캐시 장애 주입` `[실측]` → Green; 오케스트레이터 지시 결함(별칭 조회를 읽기 `try` 안에 둠 → 설정 오류가 "write failed"로 잘못 기록) 정정해 별칭 조회는 `try` 밖; 오류 기록 규칙 가드 포함 69 passed, 전체 회귀 4,478 passed / 47.71초 `[실측]` |
| 문서 | `c1c2bcff`, `e2a94d17` | `.env.example` `PUBLIC_CACHE_TTL_SECONDS`; 배포·운영 런북과 백로그 트랙 17 행 | DOR 검토 Medium 2·Low 5 반영, 오케스트레이터가 백로그·런북 env 행의 사실 오류 3곳(상세 HEAD, `q` 근거, 목록 행은 캐시 안 함) 정정, Disallow 11줄·§3 항목 21개 `[실측]` |
| QVL | `c380625b` | C-HIDE 비공개 전환 행사는 달력에서 TTL 뒤 빠진다(AC-C5 제거 방향) | 이미-Green; 뮤테이션 `timeout=9999` → C2·C-CAT-2·C-HIDE Red `[실측]`; 최종 실측: 전체 회귀 4,479 passed / 45.17초, e2e 10 passed / 10.31초, ruff·format·`manage.py check`·`makemigrations --check` 통과 `[실측 2026-11-13]`; QVL 판정 PR 생성 가능 |
| ORM 이관 | `1d629b9c` | QF1~QF3 `events/queries.py` `CLOSING_SOON_WINDOW_DAYS`·`list_closing_soon_events`·`list_latest_published_events`·`published_category_counts`, QF5a 빈 슬러그 거부 케이스 | Red: 세 함수 각각 `ImportError` `[실측]`; QF5a 이미-Green; 뮤테이션: 창 4일 → QF1만, 종료 제외 삭제 → QF2만, `.exclude(category="")` → QF3만, 슬러그 `blank=True` → QF5a 빈 문자열만 Red `[실측]`(Django는 빈 값에 필드 검증기를 돌리지 않아 거부는 `blank=False`에서만 온다); 전체 회귀 4,483 passed / 44.60초 `[실측]` |
| ORM 이관 | `47e7bdb4` | QF4·QF6·QF7 `_load_home_public_sections`가 세 명명 함수 사용, `consumer_category_choices`가 `published_category_counts()` 사용, `web/public_cache.py`의 `Event`·`Count` 임포트 삭제 | Refactor — 보호망(`tests/events/test_home_view.py`·`test_public_cache.py`·`test_category_ui_translations.py`·`test_events_queries.py`·`test_architecture_boundaries.py`) 226 passed, 전체 회귀 4,483 passed / 40.79초, e2e 10 passed / 10.13초, ruff·format·`manage.py check` 통과 `[실측]`; `rg "Event\.\|Count\(" web/public_cache.py` 0건 `[문서 엔지니어 rg]` |

- 착수 기준선 `[실측 2026-11-13]`: 전체 회귀 4,397 passed / 49.41초. 쿼리
  재측정(로컬 Postgres, 게시 181건)은 위 v3 수치와 같다. 새로 본 값: 로그인
  상태 `/api/health/` 2쿼리(비로그인 0쿼리) `[실측 스크래치 측정 스크립트]`.
- 계약 정정(오케스트레이터): 코치 원안의 H1 최소 Green에 간격 비교가 들어
  있어 H2가 이미-Green이 되므로 H1을 "한 번도 확인 안 했을 때만"으로 줄였다.
  기존 503 테스트는 H1 Green이 깨뜨려 그 단계에서 패치 대상을
  `connection.cursor`로 바꿨고, H3가 이 테스트를 확장·개명해 흡수했다.
- 구현 형태: 마지막 성공 시각은 `core/views.py` 모듈 변수
  `_last_db_check_at`(`global` 재대입, `time.monotonic()`), 판정은
  `_db_check_is_due()`, 간격 상수 `HEALTH_DB_CHECK_INTERVAL_SECONDS`.
  `DB_CONN_MAX_AGE`는 `config/settings.py` `load_db_conn_max_age()`.
- 코치 Green 뒤 판정: 테스트 준비 코드 공용화 불허(DAMP, 파일 관례),
  `_db_check_is_due` 위치 유지, summary 문구 갱신 허용(반영함).
- S6·S7 계약 정정(코치): S6 Given의 "교환가능만(미보유)" 행은 DB 제약
  `collectionitem_tradeable_lte_quantity` `[코드 archive/models.py:323-326]`로
  만들 수 없어 "보유∧교환가능" 행으로 바꿨다. S7은 0건 사용자 핀(S7b)을
  따로 뒀다(기존 0건 테스트는 값만 본다). `~Q(short_review="")`는
  `exclude()`가 내부에서 만드는 식과 같고 필드가 NOT NULL이다
  `[코드 Django query.py exclude, archive/models.py short_review]`. S6
  독스트링은 바꾸지 않았다(Refactor 없음).
- S9/S8/S10 정정(오케스트레이터): 코치 원안의 `_attach_display_many`는
  행 dict 13개 키 조립을 새 함수에 복제했다. 대신 모든 구간 행사를 이어
  붙여 기존 `_attach_display`를 한 번 부르고 구간 길이로 다시 자른다
  (`_attach_display`는 입력마다 한 행을 순서대로 돌려준다
  `[코드 web/views/_helpers.py:56-79]`) — 기존 함수 본문 불변, 복제 없음.
  S8·S10은 계획의 "커밋 전체 되돌림" 뮤테이션으로는 Red가 나지 않는다(옛
  구현도 비로그인은 조회 없음, 같은 today로 같은 값 — 코치 지적) → 새
  코드 표적 뮤테이션으로 증거를 냈다. S10 Given은 상태·관심을 서로 다르게
  두고 최근 구간에만 있는 행사를 더했다(코치). 로컬 데이터 감축 폭이
  테스트(−8)보다 작은 것은 빈 구간이 원래 조회를 건너뛰기 때문이다
  `[코드 _helpers.py:44 and events]`.
- 사후 검토(Domain Architecture Reviewer, 집계 커밋 3개): 설계 조건 5개
  (dict 계약 불변·조건 이중화 금지·`_attach_display` 불변·같은 today·의존
  방향) 모두 충족. Low 1(독스트링) → `c91d8144`, 관찰 1(반대 조건 이중
  인코딩) → 사용자 승인 뒤 `2dc6dbd8`. 검토자는 Bash가 없어 커밋 diff를
  직접 못 봤고, 오케스트레이터가 `git show --stat`으로 커밋별 파일 범위가
  의도한 파일뿐임을 확인했다 `[실측]`.
- AC-D5 정정(오케스트레이터 실측 2026-11-13, python `datetime.strptime(s,
  "%Y-%m")`): 비ASCII 숫자는 **월 자리만** 거부된다(`2031-²`, `2031-٥` →
  ValueError). **연도 자리는 받아들여진다**(`٢٠٣١-05`, `２０３１-05` →
  2031-05). 위 AC-D5의 "비ASCII 숫자는 거부된다 `[실측]`"은 월 자리만 잰
  값이었다. 같은 달의 별칭 주소가 생기므로 공개 달력 파서에서 ASCII가 아닌
  입력을 형식 오류로 처리해 AC-D5를 충족시킨다(D5, D1 Green 뒤). 로그인
  활동 달력 파서(`_parse_calendar_month`)는 바꾸지 않는다. 코치 지적: AC-D5는
  Test List 어느 행과도 짝이 없었다. `?date=`도 같다 `[실측 python]`:
  `٢٠٢٦-06-10`·`２０２６-06-10` → 2026-06-10 허용. 같은 종류 소규모 결함이라
  사용자 결정(2026-11-12 "백로그가 생기면 다음으로 넘기지 말고 처리")에 따라
  D5에서 공개 달력 date 파싱에도 같은 검사를 넣는다.
- D 계약 정정(오케스트레이터): D3(경계 달 prev/next None)는 템플릿 가드와
  **같은 커밋**에 넣는다 — None이 그대로 렌더되면 `href="?month=None"`이
  생긴다 `[코드 Django template/base.py render_value_in_context, 코치]`.
  D3c는 칸마다 `linkable`(그 날짜의 달이 공개 범위 안인가)을 준다 —
  `in_month`와 다른 질문이다(범위 안 인접 달 채움 칸은 계속 링크).
- D3 사후 판정 메모: WED 선택 다듬기 — 라이트 모드 비활성 글리프 유효
  대비 약 1.77:1·다크 약 2.26:1 `[계산 WED]`(비활성 컨트롤이라 WCAG 1.4.3
  예외, 명세 opacity 0.4의 결과). 올리려면 디자인 변경이라 사용자 결정.
  BIR 미검증 — 실제 스크린리더 음성(NVDA·VoiceOver)은 이 환경에서 측정
  불가. 범위 밖 채움 칸이 화면에는 보이고 스크린리더에는 숨는 비대칭은 사전
  결정(887-910행)의 결과로 결함 아님.
- 전환 탭 nofollow는 D 명세 밖이었으나 측정에서 `month=`를 그대로 옮기는
  것이 드러나 같은 종류 소규모 결함으로 같은 커밋에서 처리(사용자 결정
  2026-11-12 "백로그가 생기면 다음으로 넘기지 말고 처리").
- **다음**: C0a~C11(코치 계약부터) → 문서 커밋 → PR 1개.
- D 운영 DB 범위 확인 — **해소(2026-11-13)**: 운영 DB에 게시 행사가 0건이라
  `[사용자 확인 2026-11-13]` 허용 범위(과거 24개월~미래 12개월 `[문서 v3 D]`)를
  넘는 데이터가 없다. 범위는 v3 그대로 둔다. 위 D 절의 "운영 DB는 미측정"은
  이 확인 전의 기록이다.

### Activated Roles (갱신)

- Product Scope Owner — 사전 판정 완료(C 축소, TTL 지연 수용, 달력 허용
  범위, 활동 달력 제외).
- Domain Architecture Reviewer — 사전 검토 완료(`web/public_cache.py`,
  TTL만, 인스턴스 캐시, 언어 키 없음, v2 근거 정정). 구현 후 재확인.
- Backend TDD Coach — Test List 확정. 구현 시 한 번에 하나씩 계약.
- Deployment & Operations Reviewer — 사전 검토 완료(헬스 의미, 연결 수,
  런북 번호, 끄는 스위치, 확인 절차). 구현 후 런북 문구 재확인.
- Security & Resilience Reviewer — 사전 검토 완료(범위 밖 302, 캐시 별칭
  분리, 키 허용 조건, HEAD 조회수). v2의 "SRR 비활성"은 갱신본에 해당 없음.
- Web Experience Designer / Browser Interaction Reviewer — 사전 산출물
  완료(아래). 구현 후 판정.
- Frontend Implementation Engineer — 아래 Frontend Review Evidence의 템플릿과
  CSS.
- Backend & Integration Engineer — 그 밖의 구현.
- Quality Verification Lead — 완료 판정.

Not Activated: AI Automation Architect(LLM 범위 없음).

### Frontend Review Evidence (사전)

- 대상 `[코드, 오케스트레이터 rg 확인]`:
  `templates/core/partials/_home_event_calendar.html`(34·36·55행),
  `templates/core/events/calendar.html`(139·141행),
  `templates/core/partials/_calendar_grid.html`(37행),
  `static/css/components/calendar.css`. 활동 달력 템플릿은 변경 없음.
- WED 명세: 경계에서 해당 방향 컨트롤은 자리를 유지한 비활성 글리프.
  제거하면 "오늘/이번 달" 링크가 약 24~48px `[계산 WED]` 밀린다.
  `components/calendar.css`에 `.calendar-month-glyph.is-off { opacity: 0.4;
  pointer-events: none; }` 규칙 하나 `[문서 WED]`. 새 색·새 문구 없음.
- BIR 기준: 월 이동을 가로채는 JS 0건 `[실측 rg static/js, BIR]`, 포커스 복원
  JS·라이브 영역 추가 없음, 기존 JS 상태 클래스 재사용 금지, 활성 대비 박스
  ±0.5px `[문서 BIR]`, 범위 밖 채움 칸 비링크.
- **마크업 불일치 정리(오케스트레이터 결정)**: 비활성 글리프는 WED안
  (`href` 없는 `<a class="calendar-month-glyph is-off" role="link"
  aria-disabled="true">`, 기존 aria-label 재사용)을 쓴다. 근거: 끝에 도달한
  사실이 보조기술에 전달되고, `pointer-events: none` 규칙 하나가 BIR이 지적한
  hover 색 전환을 함께 막는다. BIR의 `<span aria-hidden>`안은 채움 칸에만
  쓴다. 구현 후 두 역할이 각자 판정한다.
- 구현 후 확인: 두 화면 × 하한·중간·상한, 1280×800과 390×844, 320px 가로
  스크롤 `[문서 WED·BIR]`, 다크 모드, en 로케일. 측정 항목은 두 역할의
  체크리스트(박스 좌표, Tab 순서, `a[href*="month="]`의 rel, 범위 밖 직접
  진입, 콘솔 오류 0건).

### 대상 파일 (갱신)

- 백엔드: `config/settings.py`, `config/settings_test.py`, `.env.example`,
  `core/views.py`, `web/public_cache.py`(신규), `web/views/_helpers.py`,
  `web/views/events.py`, `events/serializers.py`, `archive/querysets.py`,
  `archive/queries.py`, `tests/conftest.py`와 위 Test List의 테스트 파일.
- 프론트: 위 Frontend Review Evidence의 템플릿과 CSS.
- 문서 `[문서 DOR, 절 번호는 오케스트레이터가 rg로 §3 항목 확인]`:
  `docs/deploy-runbook.md`(env 표·DB 항목, 헬스 의미 두 곳, §3 서두 항목 수,
  멀티워커 항목의 줄 번호·별칭 구분, robots 항목의 Disallow 확인, §3 새
  항목 두 개 신설, 롤백 절의 env 롤백 두 종, 미검증 표, "로그 판독 절" 참조
  정정), `docs/operations-runbook.md`(접근 로그 집계·헬스 주기, 정기 명령
  연결 수, LocMem에 카운터 금지), `docs/backlog.md`.
- 변경 없음: `events/` 쿼리·서비스·모델, `staff/`, `drafts/`, 마이그레이션.

### 근거 정정 (v2 본문의 낡은 file:line)

- `drafts/views.py:93` → 파일이 없다 `[실측 ls]`. `create_draft_from_url`
  정의는 `drafts/services.py:214` `[실측 rg]`.
- 홈 `upcoming_rows`는 `web/views/events.py:221-225`, `_attach_display`는
  `web/views/_helpers.py:30-79` `[코드, 오케스트레이터 열람]`.
- `archive/queries.py`의 `.count()` 네 번은 570-573행,
  `user_visit_record_counts`는 386-398행, `web/views/archive.py`의
  `_attach_display` 호출은 639행 `[코드 DAR·코치, 착수 시 재확인]`.
- "§3-15 신설" → §3-20 이후 `[실측 rg]`. "런북엔 코드 롤백만" → env 단독
  롤백 선례가 `docs/deploy-runbook.md:351`에 있다 `[코드 DOR, 착수 시 재확인]`.
- 로그인 홈 "26 → 16쿼리" `[문서 v2]` 목표는 C가 들어가면 달라진다. S9의 N은
  캐시 없는 첫 요청 기준으로 Red 시점에 실측한다.

### 사용자 결정 (2026-11-12 확정 `[문서 사용자 지시]`)

- 범위 밖 달 요청: **302**로 month·date를 뺀 같은 경로로 보낸다(쿼리 실행
  전). 위 D의 "사용자 결정 대기"와 AC-D1의 조건부 문구는 이 결정으로 확정.
- C(공개 데이터 캐시): **트랙 마지막 단계로 구현**한다.
- 배포 단위: **PR 1개**. 커밋은 기능별로 나눠 유지보수할 수 있게 한다
  (Test List 순서의 묶음 A·A+·B·소규모 결함·D·C·문서가 각각 독립 커밋
  묶음이 되게 하고, 한 커밋에 두 묶음을 섞지 않는다).
- 헬스 체크 DB 확인 간격: 30분(위 A+).

### 사용자 결정 (2026-11-13, PR #415 생성 뒤 `[문서 사용자 답변]`)

- PR #415 CI 의존성 감사 실패(`soupsieve 2.9.2` GHSA-4j63-6c4x-wfg4·GHSA-mmhr-3c5m-f64f, `beautifulsoup4` 하위 운영 의존성, 이 PR은 의존성 변경 0 `[실측 git diff --stat]`): **별도 PR**로 고친다. `uv lock --upgrade-package soupsieve` 시험 해석은 4.1(메이저) `[실측 --dry-run]`, `drafts/discovery.py:18`이 `soupsieve.util.SelectorSyntaxError`를 임포트하므로 전체 회귀로 확인.
- ClaudeBot 서버 차단(`CrawlerQueryBlockMiddleware`): **유지 확정** — 임시 조치 표시와 "사용자 결정 대기"를 문서에서 정정한다.
- `_load_home_public_sections`의 ORM 체인: **이 PR에서 `events/queries.py` 명명 함수로 옮긴다**(위 "대상 파일"의 "`events/` 쿼리 변경 없음"을 이 결정으로 정정).
- 경계 달 비활성 글리프 대비: 그대로.
- 별도 PR: #416 `chore/soupsieve-audit`(`uv.lock`만, 4.1) — main 기준 작업 트리에서 4,397 passed·`tests/drafts` 576 passed·e2e 10 passed `[실측]`. 작업 트리 함정: git 밖 `.env`(로컬 `DATABASE_URL`)가 없어 SQLite로 떨어지고(`ALTER` 구문 오류), 번역 `.mo`가 없어 다국어 테스트 436건이 실패했다 — `DATABASE_URL`만 환경 변수로 넘기고 CI와 같은 `compilemessages`로 해결 `[실측]`. 4.x는 모두 2주 안 공개 `[실측 PyPI]`라 PR에 위험으로 적었다.

ORM 이관 설계(DAR 2026-11-13 `[문서 DAR]`): `events/queries.py`에 `CLOSING_SOON_WINDOW_DAYS = 5`(상태 라벨용 `CLOSING_SOON_DAYS = 4`와 별개), `list_closing_soon_events(*, today=None, within_days=…)`, `list_latest_published_events(*, today=None)`(둘 다 QuerySet, 슬라이스는 호출자), `published_category_counts()`(빈 슬러그 `""` 키 포함, `consumer_category_choices`도 이것을 쓴다 — 동작 동일 조건은 `Category.slug`에 `""` 없음). `web/public_cache.py`는 `_cached`·키·dict 조립·`HomeConfig`만 남기고 `Event`·`Count` 임포트 삭제. 의존 방향 위반 없음.

ORM 이관 Test List(코치 2026-11-13): QF1 마감 임박 함수가 기본 창 5일로 위임(Driving), QF2 최신 함수가 종료 제외·id 내림차순(Driving), QF3 카테고리 건수 dict 1쿼리·`""` 키 포함(Driving), QF5a 빈 슬러그 형식 검증 거부(기존 테스트 확장, 핀 예상), QF4·QF6·QF7 호출부 전환·`consumer_category_choices` 전환·임포트 정리(Refactor — 보호망 `tests/events/test_home_view.py` 구간 테스트, C-HOME·C9d·C-CAT-1, `tests/core/test_category_ui_translations.py`). 코치 근거: `consumer_category_choices` 직접 테스트 0건 `[문서 코치 rg]`, C 묶음 테스트의 패치 대상 영향 0건 `[문서 코치 rg]`. 오케스트레이터 조정: 코치의 QF5("테스트 DB 시드에 빈 슬러그 없음")는 운영 DB를 지키지 못하고 뮤테이션으로 증명할 수 없는 데이터 확인이라 뺐다 — 실제 보호선은 QF5a(형식 검증).

### 선행 긴급 수정 (계획 승인 전 사용자 승인 예외, main 직접 커밋)

- `6e659557` robots.txt에 달력 쿼리 주소 `Disallow` 6줄
  `[코드 core/views.py]`. production 반영 확인 `[실측 curl 2026-11-12]`.
- `f386dd0e` `core/middleware.py` `CrawlerQueryBlockMiddleware` — User-Agent에
  `claudebot`이 있고 쿼리 문자열이 붙은 요청을 DB 조회 없이 403으로 거부,
  robots.txt에 `Disallow: /events/?` 추가. production에서 ClaudeBot의 달력·
  목록 요청이 `403 0`으로 바뀐 것 확인 `[실측 production 접근 로그
  2026-11-12 23:39:56 KST 이후]`. 회귀 4,397 passed `[실측]`.
- **임시 조치 성격**: 이 서버 차단은 D(범위 제한·`rel="nofollow"`)가 들어간
  뒤 유지할지 제거할지 트랙 종료 전에 사용자에게 묻는다. 런북에 차단 대상
  변경·해제 방법을 적는다(대상 파일에 포함).

### 사전 블로킹 — 해소 (2026-11-12)

- Supabase 값 `[대시보드, 사용자 확인 2026-11-12]`: Session pooler Pool Size
  15, Max Client Connections 200, Postgres max connections 60.
- 판정: 최악 6 연결 `[계산]` ≤ Pool Size 15이므로 연결 재사용(A) 배포를
  막는 조건은 없다. 여유는 9 `[계산: 15 − 6]`.
- 남은 일: 이 세 값과 확인일을 런북 DB 항목에 기입한다(문서 커밋 묶음).
  워커 수를 늘리거나 스레드 워커로 바꿀 때는 이 값과 다시 비교한다.

---

## v2 본문 (2026-09-03, 위 갱신본과 어긋나면 갱신본이 이긴다)

> 배경: 사용자 요청 "백엔드 최적화 검토"(10개 항목) → 오케스트레이터 1차
> 판정 → 리뷰 3역할(DAR·DOR·QVL) 병렬 재검토 → 정정본 → 사용자 결정
> (2026-09-03) "문서화 착수. 같은 트랙으로" → 계획서 v1 → **계획 검토
> 4역할(코치·DAR·DOR·QVL) 병렬, 지적 반영한 v2가 이 문서.**
> 근거 실측(로컬, **Postgres** — `.env`의 `DATABASE_URL` 적용,
> `connection.vendor == "postgresql"` [실측]): 행사 171건·로그인 사용자
> 컬렉션 13건에서 페이지별 쿼리 수(미들웨어·세션·auth·컨텍스트 프로세서
> 포함 전체 스택 [코드 `CaptureQueriesContext`가 `client.get` 전체를 감쌈])
> 홈 26 / `/events/` 7 / `/collection/` 12 / `/archive/visits/` 8 /
> `/mypage/` 12. 롤백 트랜잭션 안에서 행사 342건(=171×2)·컬렉션
> 52건(=13→26→52, 복제 2회)으로 늘려 재측정 → 홈 28(+2: 비어 있던 "예정
> 행사" 구간이 채워져 표시 헬퍼가 1회 더 실행 — 행 수 비례 아님), 나머지
> 전부 불변 [실측]. 행 수 비례 N+1은 없다. 재현 스크립트:
> `.docs/BE/2026-09-03-home-query-scaling-measure.py`(작업 측정이라
> `.docs/` — git-ignored, 소실 시 재작성 대상).
> 코드 근거: `config/settings.py` `load_database_config`가
> `dj_database_url.parse(database_url)`를 기본 인자로 호출 → 반환 dict에
> `CONN_MAX_AGE=0`·`CONN_HEALTH_CHECKS=False` 키가 **이미 존재하고 값만
> 기본값** [코드 `dj_database_url/__init__.py:165-166`] → **요청마다
> Supabase Session pooler에 새 TLS 접속**. 접속 1회의 ms 비용은 미실측.
> `DATABASE_URL` 쿼리스트링 `?conn_max_age=600`은 **동작하지 않는다** —
> parse()는 쿼리스트링을 전부 `OPTIONS`(psycopg 연결 kwargs)로 보내므로
> 알 수 없는 인자로 접속이 깨진다 [코드 `__init__.py:197-203`, DOR]. env
> 하나를 따로 두는 것이 유일한 경로다.
> 정정 기록(1차 판정 오류): "로컬 sqlite"→Postgres, "인덱스 31건"→제약까지
> 센 오류(재측정 [코드]: `db_index`·`models.Index` 10건, `UniqueConstraint`·
> `CheckConstraint` 18건), "요청 경로에 외부 I/O 없음"→오류
> (`drafts/views.py:93` 관리자 DRF API가 `create_draft_from_url`로 외부
> fetch 동기 호출, 타임아웃 5초 [코드 `drafts/fetching.py:10`]).
> 계획 v1 오류(QVL): 감축 산식 26→17은 산술 오류(정정 아래), 홈 표시 헬퍼
> 호출은 4구간이 아니라 **5구간**(`upcoming_rows`, `web/views/events.py:112`
> [코드]) — 1차 실측 사용자에게 예정 행사가 없어 이 구간이 0쿼리였다.
> gunicorn gthread 전환 권고는 **철회** — 워커 모델·timeout은 사용자 보류
> 항목(트랙 13 Deferred)이며 재승인 없이 격상하지 않는다.

## 승인 범위

1. **DB 연결 재사용** — `config/settings.py` `load_database_config`의
   Postgres 분기에 한해 `dj_database_url.parse(database_url,
   conn_max_age=<env>, conn_health_checks=True)`로 바꾼다(인자 지원·반환
   키 `CONN_MAX_AGE`/`CONN_HEALTH_CHECKS` [코드, 설치본 확인]). 값은 새 env
   `DB_CONN_MAX_AGE`(정수 초)로 읽고 `.env.example`에 추가한다. 기본값
   600초 [선정 근거: Django 문서 `CONN_MAX_AGE` 예시 관행 + 세션 풀러
   idle 종료보다 길어도 `conn_health_checks`가 요청 시작 시 ping 1회로
   끊긴 연결을 재접속하므로 안전 — ping은 왕복 1회 비용이 추가된다(DOR),
   "무비용"이 아니다]. sqlite 폴백 분기는 건드리지 않는다(두 키 부재 유지).
   Django 5.2 psycopg 서버측 풀(`OPTIONS["pool"]`)은 도입하지 않는다 —
   Session pooler 위에 풀을 겹치는 구조가 되고 접속 상한 계산이 이중화된다.
   연결 수 상한 [계산]: sync 워커 3개(`docker/entrypoint.sh` `WEB_CONCURRENCY`
   기본 3 [코드]) × 요청당 1연결 = **상시 최대 3개**. `migrate`는 gunicorn
   기동 전 순차 실행이라 겹치지 않는다(entrypoint.sh:4-9 [코드]).
   `purge_deleted_accounts` 스케줄러는 서비스 중 별도 프로세스로 돌아
   순간 +1 → **파기 실행 중 최대 4개** [계산, DOR 정정].
   **Supabase Session pooler Pool Size는 런북에 미기록** — 사용자가
   대시보드에서 확인해 3번 항목에 기입하기 전에는 배포하지 않는다(블로킹).
2. **집계 쿼리 병합 3곳** (DAR 발견, 반환 dict 키·타입 계약 불변 —
   `Count`는 0건에서 None이 아니라 0을 준다 [코드, Django]):
   (a) `archive/queries.py` `user_collection_item_summary_counts` —
   같은 `CollectionItem` 테이블에 `.count()` 4회 → 조건부
   `Count(..., filter=Q(...))` 단일 `aggregate()` 1회. **조건 이중화
   금지(DAR)**: `archive/querysets.py`에 `OWNED_Q = Q(quantity__gt=0)`,
   `TRADEABLE_Q = Q(tradeable_quantity__gt=0)` 모듈 상수를 두고 기존
   `owned()`/`tradeable()`이 그 상수로 filter하게 바꾼 뒤, aggregate가
   같은 상수를 import한다. 쿼리셋 메서드 시그니처·동작은 불변(호출처
   `archive/queries.py:517,519` 포함).
   (b) `archive/queries.py` `user_visit_record_counts` — `VisitRecord`
   `.count()` 2회 → `aggregate()` 1회. `memo_count`는
   `Count(filter=~Q(short_review=""))`로 기존 `.exclude(short_review="")`에
   정확히 대응해야 하며 0건 사용자 케이스를 테스트에 넣는다(S7).
   (c) `web/views/events.py` `home()` — `_attach_display`를 ongoing /
   closing / recent / featured / **upcoming** 5구간에 각각 호출해 인증
   사용자당 `UserEventStatus`·`EventInterest` 조회가 최대 10회 발생
   [코드 `web/views/_helpers.py:24-48`, `events.py:84-116`]. **새 헬퍼
   `_attach_display_many`를 `web/views/_helpers.py`에 추가**(DAR 권장 —
   기존 `_attach_display` 시그니처·본문은 손대지 않는다: 다른 호출처
   `web/views/archive.py:620`, `events.py` 4곳이 단일 리스트 계약에
   의존). 책임: 5구간 행사 ID 합집합 → 상태 맵·관심 맵 각 1회 생성 →
   구간별 dict 조립. 전제(계획 명시): 5구간 전부 **같은 `today` 하나**로
   맵을 만든다 — 마감임박 구간은 진행중 구간의 부분집합이라 같은 행사가
   두 구간에 항상 겹치는데 [코드 `events/querysets.py:51-52,70-75`],
   `today`가 같으면 `derived_status`·`interest_id`가 결정적으로 동일하다.
   기대 효과 [계산, QVL 정정]: (4→1)+(2→1)+(8→2) = 10 감축 → 로그인 홈
   **26 → 16쿼리**(예정 행사 있는 사용자는 28 → 16: (10→2) 포함). 실측치로
   확정(S9).
3. **`docs/deploy-runbook.md` 갱신** —
   (a) §1 env 표 `DATABASE_URL` 행 옆에 `DB_CONN_MAX_AGE` 행 추가(기본
   600초, 의미, "쿼리스트링 `?conn_max_age=`는 OPTIONS로 가서 동작하지
   않음" 한 줄 근거 [코드]),
   (b) §1 DB 항목(18-25행)에 Supabase Session pooler Pool Size 기입란
   (숫자·확인일·출처 [대시보드] — 사용자 확인 후 기입),
   (c) 같은 자리에 연결 수 계산식 "워커 수 × 1(상시) + 파기 스케줄러 1
   (순간) ≤ Pool Size"와 현재 값 3/4 [계산],
   (d) 24행 "7일 일시정지" 문장 옆에 "`conn_health_checks`는 끊긴 연결
   재접속일 뿐 일시정지를 깨우지 않는다(재개는 Restore 버튼)" 병기,
   (e) §3 배포 후 확인에 **15번 항목** 신설: 접속 비용 전/후 실측(아래
   수용 기준) + Supabase 연결 수 확인,
   (f) §5 롤백에 env 단독 변경 절차 추가(DOR 지적: 현재 런북엔 코드
   롤백만 있음): "Render Environment 탭에서 `DB_CONN_MAX_AGE=0` 변경 →
   Manual Deploy(재빌드 없음, §7 PR 흐름 미경유가 정상)".
   `docs/backlog.md`에는 gthread 워커 모델이 사용자 보류 항목임을
   재확인만 한다(신규 항목 없음).

## 배제 (범위 밖)

- gunicorn 워커 클래스·스레드·timeout 변경(사용자 보류 항목 — 재검토 시
  3-(c) 계산식과 연결: gthread 4스레드면 3×4=12 상시 연결 [계산]).
- Redis 등 외부 캐시·페이지 캐시(비용 제약: 배포 서버·DB 외 유료 금지).
- `drafts/views.py:93` 관리자 URL 드래프트 생성의 비동기화(관리자 저빈도
  경로, sync 워커 1개를 최대 5초 점유 — 기록만).
- CDN·로드밸런싱·마이크로서비스·서버리스(1차 판정 "해당 없음" 유지 —
  whitenoise가 해시 정적 파일에 `max-age=315360000, immutable`을 이미
  붙임 [코드, 설치본 `whitenoise/middleware.py:164-180`]).
- 홈 외 페이지의 추가 쿼리 감축(행 수 비례 아님이 실측됐고 섹션 수
  비례는 설계).
- `DB_CONN_MAX_AGE` 음수 가드 — 코치가 "보안 아닌 설정 오류라 별도 승인
  필요"로 분류. **미승인 상태로 범위 밖**(정수 파싱 실패만 S3로 막는다).
  사용자가 원하면 S3 옆에 한 건 추가.

## 수용 기준 (블로킹 여부 명시)

- [사전 블로킹] Supabase Session pooler Pool Size 확인·런북 기입 후에만
  배포.
- `load_database_config` Postgres 분기: `CONN_MAX_AGE == 600`(env 미설정)
  / env 값 반영 / `CONN_HEALTH_CHECKS is True`; sqlite 폴백은 두 키 없음
  유지; `DB_CONN_MAX_AGE` 비정수는 `ImproperlyConfigured`(S1~S5).
- 집계 3곳: 기존 값 테스트(`tests/archive/test_archive_collection_item_queries.py`
  272행 이후, `test_archive_visit_record_queries.py`) 무변경 Green +
  `django_assert_num_queries(1)` 핀(S6·S7). 핀 테스트는 두 파일의 모듈
  마커가 `domain`이라 `tests/archive/test_archive_query_contracts.py`에
  추가한다(코치 — 같은 이유로 분리된 전례).
- 홈: `tests/events/test_home_view.py`(모듈 마커 `web`)에 인증 쿼리 상한
  핀(S9, 값은 Red 단계 실측으로 확정 — 목표 16 [계산]), 비인증 불변
  핀(S8), 5구간 값 동일성(S10, 같은 행사가 두 구간에 걸치는 Given 포함).
- **뮤테이션 검증(S5·S8·S10 이미-Green 핀)**: 병합·설정 커밋을
  `git stash`로 되돌린 상태에서 해당 테스트만 실행해 Red 출력을 PR 본문에
  붙인 뒤 `git stash pop` → Green 재확인. 증거 없는 핀은 완료로 치지
  않는다(QVL).
- [사후 비블로킹] 배포 후 런북 §3-15: `curl -o /dev/null -s -w
  '%{time_starttransfer}\n' https://takulife.kr/` 20회 중앙값 전/후 [실측,
  ms] — **참고 지표**(콜드스타트·압축 교란, DOR). 연결 재사용 자체의
  증거는 Supabase 대시보드 연결 수 그래프/`pg_stat_activity` 신규 접속
  빈도로 별도 기록 [실측]. 개선이 0이어도 트랙은 종료.
- [사후 비블로킹, 조치 조건부] 배포 후 상시 연결 수 ≤ 3, 파기 스케줄러
  실행 중 ≤ 4 [계산]. 초과가 관측되면 종료를 막지 않되 `DB_CONN_MAX_AGE`를
  낮추는 env 조치를 §5 절차로 즉시 수행한다.
- 회귀: `uv run pytest -q` 0 failures, `manage.py check`,
  `makemigrations --check --dry-run` 변경 없음.

## Test List (코치 확정, Red-Green 순서)

| # | 내용 | 위치 | Red 근거 |
|---|---|---|---|
| S1 | Postgres URL → `CONN_MAX_AGE` 기본 600 | tests/core/test_settings_env.py | 현재 0 [코드] |
| S2 | `DB_CONN_MAX_AGE=0` → 0. **S1 Green 이후에만 유효**(이전엔 우연 Green) | 〃 | S1 후 기본 600≠0 |
| S3 | `DATABASE_URL`=postgres 명시 + `DB_CONN_MAX_AGE=abc` → `ImproperlyConfigured` | 〃 | env를 안 읽음 |
| S4 | Postgres URL → `CONN_HEALTH_CHECKS` True | 〃 | 현재 False [코드] |
| S5 | [이미-Green·뮤테이션] sqlite 폴백 dict에 두 키 없음(`DB_CONN_MAX_AGE` 설정된 채) | 〃 | sqlite 분기로 kwargs가 새는 구현 실수 감지 |
| S6 | `user_collection_item_summary_counts` 쿼리 1회 | tests/archive/test_archive_query_contracts.py | 현재 4회 [코드] |
| S7 | `user_visit_record_counts` 쿼리 1회 + 0건 사용자 값 0/0 | 〃 | 현재 2회 [코드] |
| S9 | 인증 홈 `django_assert_max_num_queries(N)` — N은 Red 시점 실측 | tests/events/test_home_view.py | 실측 26 > 목표 16 |
| S8 | [이미-Green·뮤테이션] 비인증 홈 쿼리 수 불변(N 실측 기록) | 〃 | S9와 같은 Green 커밋의 안전핀 |
| S10 | [이미-Green·뮤테이션] 5구간 `user_status`/`user_interested` 동일, 같은 행사가 ongoing∧closing에 겹치는 Given 포함 | 〃 | 〃 |

Driving 테스트는 S1~S4·S6·S7·S9. 코치 산출물에 "Mutation-verified"
필드를 두어 S5·S8·S10의 되돌림 Red 증거를 기록한다.

## Activated Roles

- Backend TDD Coach — 사전 검토 완료(Test List 확정·위치 정정·위장-Green
  순서 제약). 구현 시 한 번에 하나씩 계약 진행.
- Backend & Integration Engineer — settings·querysets 상수·queries·
  `_attach_display_many`·런북 구현(pytest 실행·판정은 오케스트레이터 단독).
- Deployment & Operations Reviewer — 사전 검토 완료(쿼리스트링 불가·
  연결 수 4·env 롤백 절차·§3-15 번호). 구현 후 런북 문구 재확인.
- Domain Architecture Reviewer — 사전 검토 완료(Q 상수·신규 헬퍼·같은
  today 전제·오케스트레이션 소유). 구현 후 계약 불변 재확인.
- Quality Verification Lead — 사전 검토 완료(산식 정정·5구간·뮤테이션
  증거·스크립트 보존·블로킹 라벨). 완료 판정.

Not Activated: 프론트 역할 2인(템플릿·CSS·JS 무접촉), SRR(신뢰 경계 변경
없음 — env 1개 추가는 비밀 아님), PSO(범위 결정 완료), AI 역할.

## Domain Boundary / Coupling

- `archive/querysets.py`가 보유·교환가능 조건의 단일 출처(Q 상수).
  `archive/queries.py` 2함수는 내부 구현만 변경(반환 계약 불변).
- **다중 구간 ID 합집합 → 맵 1회 생성 책임은 `web/views/_helpers.py`
  (오케스트레이션 계층)에 고정한다.** `archive/queries.py`·`events/queries.py`에
  홈 5구간을 아는 공개 함수를 추가하지 않는다(도메인 쿼리 모듈이 홈
  레이아웃을 알게 되는 역방향 결합 금지 — DAR). 기존 공개 함수
  `user_interest_event_ids(user, event_ids=)`와 `with_derived_status`만
  재사용한다.
- settings 변경은 `load_database_config` 한 함수. 마이그레이션 없음.

## 검증 커맨드

- `uv run pytest -q tests/core/test_settings_env.py`
- `uv run pytest -q tests/archive/test_archive_query_contracts.py tests/archive/test_archive_collection_item_queries.py tests/archive/test_archive_visit_record_queries.py tests/events/test_home_view.py`
- 뮤테이션: `git stash` → 위 두 번째 명령에서 S5·S8·S10 Red 출력 저장 →
  `git stash pop` → Green.
- `uv run pytest -q` / `uv run python manage.py check` /
  `uv run python manage.py makemigrations --check --dry-run`
- 근거 재현: `PYTHONPATH=. uv run python .docs/BE/2026-09-03-home-query-scaling-measure.py`
- 배포 후: curl 20회 ×2, Supabase 연결 수 그래프 캡처 → 런북 §3-15.

## Deferred

- gunicorn 워커 모델(사용자 보류 유지). 재검토 시 연결 수 계산식 필수.
- `drafts/views.py:93` 동기 외부 fetch의 비동기화(관리자 저빈도).
- `DB_CONN_MAX_AGE` 음수 가드(승인 시 S3 옆 1건).
- 홈 섹션별 집계의 추가 통합(섹션 수 비례는 설계 — 필요 시 별도).

## 롤백

- 연결 재사용: Render Environment 탭에서 `DB_CONN_MAX_AGE=0` → Manual
  Deploy(재빌드·코드 롤백 없음). 코드 되돌림 불필요.
- 집계 병합·헬퍼: 순수 리팩터라 커밋 revert로 복귀.
- 런북: 문서라 즉시 되돌릴 필요 없음.

