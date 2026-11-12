# 트랙 19: 스태프 계정 운영 화면 — H1 수직 슬라이스 (2026-09-06)

> 배경: `docs/backlog.md` H1(P0) — `accounts.User`가 Django admin 미등록이라
> `is_staff`·`is_active` 변경이 `manage.py shell`뿐 [실측 2026-09-05, 런북 §5].
> 2026-09-06 외부 검토로 착수 전 계약 3건(조작 주체·감사 대상·RBAC 트리거)이
> 붙었고 [문서 backlog H1 행], WED·BIR 사전 검토 완료 [문서 backlog H절
> "프론트 필요 기능", `.docs/FE/2026-09-06-staff-backoffice-frontend-review.md`].
> 사용자 지시(2026-09-06): "머지 승인, 남은 백로그 정리, 구현 및 계획서 착수
> 및 진행". 회귀 기준선 [실측 2026-09-06] `uv run pytest -q` → 2364 passed, 72.34초.
> 계획서 v2 = v1을 PSO·DAR·SRR·TDD 코치 4역할 검토로 정정한 통합본(정정 위치는
> 역할명으로 표기). 로컬 DB superuser 1명·스태프 5명 [실측 2026-09-06 로컬,
> 프로덕션 미실측]. 브랜치 `feat/staff-account-operations`(main 9b55d56 기준).

## 승인 범위 (★ = 사용자 미확인 가정 — PSO 판정 병기)

1. **관문**: `staff/permissions.py`에 `superuser_console_required` 신설 —
   기존 `staff_console_required` 위에 합성해(미인증 리다이렉트·`is_staff` 403
   재사용) `is_superuser` 아님→403만 얹는다(DAR: 단독 재구현은 드리프트 위험).
   계정 화면 뷰 전부 이 관문. ★1 조작 주체 = superuser 한정 — PSO 승인(가장
   좁은 기본값, RBAC 보류와 충돌 없음). 403 대 404 구분은 위협모델 차이 없음(SRR).
2. **도메인 규칙**(`accounts/services.py` 소유 — DAR 승인, 탈퇴 상태기계와 같은
   파일): `set_staff_flag(user, *, enabled) -> bool`, `set_active_flag(user, *,
   enabled) -> bool`. 대상이 `is_superuser`면 `ProtectedAccountError`(조작 주체가
   superuser라 자기 계정도 자동 보호). 이미 목표 상태면 저장 없이 False(멱등),
   바뀌면 `update_fields` 저장 후 True. ★2 "마지막 관리자 보호" = superuser 계정
   전체를 콘솔 대상에서 제외(superuser 변경은 shell 유지) — PSO: MVP 기본값으로
   수용하되 **사용자 확인 필요**(H1 목적 "shell 없이"의 영구 예외가 됨). 확인 전
   구현은 이 가정으로 진행하고, 카운트 기반 보호로 바꾸는 것은 이연 항목.
   유예(탈퇴 신청) 계정은 서버가 변경을 허용하고 버튼 비활성화는 UI 안내뿐
   (SRR Low — 문서에 명기).
3. **감사**: `StaffActionLog.target_user` FK(`settings.AUTH_USER_MODEL`, null,
   SET_NULL) + Action 4종 `staff_grant`·`staff_revoke`·`user_deactivate`·
   `user_reactivate`(모두 `max_length=16` 이내 [코드 `staff/models.py:31`]).
   `_action_log_kwargs(..., target_user=None)`(`_helpers.py`는 값 준비 로직만 —
   DAR). `ACTION_LABELS` 4건 추가(`tests/staff/test_staff_action_labels.py`가
   누락 시 Red). **SRR Medium 반영**: 감사 로그 화면·대시보드·검색은
   `staff_console_required`(is_staff 전체)라 대상 회원 이메일을 넣으면 superuser
   경계를 우회해 노출된다 → 대상 라벨은 모든 운영자에게 `계정 #<id>`로만
   렌더(superuser에게는 `/staff/accounts/<id>/` 링크), `?q=` 검색은
   `target_user__email`에 매칭하지 않는다(존재 여부 되묻기 우회 차단).
   대상 FK 3종 상호 배타는 기존처럼 독스트링 관례(CheckConstraint 0건
   [실측 `rg CheckConstraint staff/`]) — 이연.
4. **뷰**(`staff/views/accounts.py` 신설):
   - 목록 `GET /staff/accounts/`(`account-list`): 이메일 부분 일치 `?q=`(`staff/search.py`
     재사용), 최신 가입순, 페이지 20건 [코드 상수 `STAFF_ACCOUNT_LISTING_PAGE_SIZE`].
   - 상세 `GET /staff/accounts/<pk>/`(`account-detail`).
   - 상태 변경 `POST /staff/accounts/<pk>/staff/`·`POST /staff/accounts/<pk>/active/`
     (`account-set-staff`·`account-set-active`): 본문 `enabled`는 문자열 `"1"`/`"0"`만
     허용하는 명시 매핑, 그 외(누락·빈 값·`true`·`2`)는 400 + DB 무변경·로그 0건
     (SRR Medium — truthy 판정 금지). **목표 상태 지정**(토글 아님 — H2 검토가
     지적한 반전 재시도 위험 회피). `confirmed=yes` 없으면 확인 화면 렌더(삭제
     2단계 패턴 `staff/views/events.py:480-483`·`501-510`), 확인 후
     `transaction.atomic()` + `User.objects.select_for_update()` + 서비스 호출 +
     감사 로그를 같은 트랜잭션에서 → PRG + `messages`. `ProtectedAccountError`는
     뷰 경계에서 `messages.error`로 번역(DAR), 무변경은 `messages.info`(로그 없음).
     GET→405. 공통 헬퍼 `_apply_flag_change(...)`는 `staff/views/accounts.py`
     내부 비공개 함수(DAR: `_helpers.py` 자체 규칙상 atomic·로그 생성은 호출부 소유).
   - **컨텍스트 계약(BIE·FIE 공유)** [문서 이 계획서]: 목록 = `account_rows`(dict:
     `id`·`email`·`date_joined`·`last_login`·`is_staff`·`is_superuser`·`is_active`·
     `deletion_requested_at`·`status_key`∈{active,inactive,deletion_pending}·
     `role_key`∈{superuser,staff,member})·`page_obj`·`pager_query`·`search`.
     상세 = `account`(User)·`deletion_scheduled_for`(datetime|None)·`is_protected`.
     확인 = `account`·`field`∈{staff,active}·`enabled`(bool)·`action_label`·
     `description`·`post_url`. URL 이름은 `staff:account-list`·`account-detail`·
     `account-set-staff`·`account-set-active`.
5. **조회**(`accounts/queries.py` 신설 — DAR 승인): `list_accounts_for_staff(search="")`
   — `values()` 최소 필드(id·email·date_joined·last_login·is_staff·is_superuser·
   is_active·deletion_requested_at). 상세는 뷰가
   `deletion_scheduled_for = deletion_requested_at + DELETION_GRACE_PERIOD`
   계산(`web/views/account.py:199-200` 패턴). 상세 컨텍스트에 `is_protected`(=is_superuser).
6. **프론트**(WED 명세대로, JS 신규 없음): `templates/staff/accounts/list.html`·
   `detail.html`·`confirm.html`(액션 라벨·설명·enabled를 컨텍스트로 받는 확인
   화면 1개), `static/css/staff/pages/accounts.css`(`tokens.css` `--c-*`만,
   `<main class="page" id="staff-main">` 래퍼), `_console_shell.html` 사이드바
   "계정" 그룹(기록 그룹 뒤, `request.user.is_superuser`일 때만 렌더 — 링크 숨김은
   UX일 뿐 경계는 관문)·crumb·title 분기, `staff/search.py` `SEARCHABLE_URL_NAMES`에
   `account-list`. 상태 변경 폼은 `data-submit-guard`. 보호 계정은 버튼
   disabled + 사유 문단, 유예 계정은 안내 문단만(버튼 활성 유지 — 2번 항목과
   일치하도록 2026-09-07 SRR 사후 검토 반영 정정; 이전 문안 "보호 계정·유예는
   버튼 disabled"는 2번과 모순이었다). CSRF 미들웨어 전역 활성 확인
   [실측 `config/settings.py:322`].
7. **문서**: `docs/operations-runbook.md` §5 정정(계정 운영은 `/staff/accounts/`,
   superuser 한정, shell은 superuser 대상·비상용), `docs/BE/staff-account-operations.md`
   신설(가드레일: 관문·보호 계정·목표 상태 멱등·`enabled` 엄격 파싱·감사 대상
   비식별 라벨·유예 보호는 UI 전용·세션 무효 사실), 백로그 H1 해결 표기·H14 종결,
   pr-log(머지 시).

## 배제 (범위 밖)

- RBAC/Groups(사용자 보류 2026-07-03), superuser 플래그 변경, 계정 생성·이메일
  변경·비밀번호 재설정(트랙 12 인접)·탈퇴 즉시 실행·유예 취소(재로그인만 취소
  `accounts/models.py:15-18`), 일괄 처리, 알림 메일, H14 스로틀 변경, admin
  User 등록(기각), `staff/admin.py` list_display 확장, 상태 변경 전 비밀번호
  재확인(step-up — SRR 이연, 기존 콘솔 액션과 일관).
- `is_active=False` 시 세션 강제 삭제: SRR 판정 불필요 — `SessionAuthentication`
  단일 경로 [코드 `config/settings.py:568-576`], allauth 백엔드는 `get_user`
  미오버라이드 [실측 allauth 65.18.0], `ModelBackend.get_user`가 다음 요청에서
  None 반환. `request_deletion`의 세션 삭제는 유예 중 `is_active`가 그대로라
  필요한 별개 경로(`accounts/services.py:97-108`).

## 수용 기준

- AC1 익명→로그인 리다이렉트, 비-superuser 스태프→403(계정 URL 4개 전부), superuser→200. 상태 변경 URL은 GET→405(PSO 누락 지적 반영).
- AC2 목록: 이메일 부분 일치 검색, 페이지네이션, 상태 배지(활성/비활성/탈퇴 유예)·권한 배지(전체 권한/검수 권한/일반).
- AC3 상세: 플래그·가입일·마지막 로그인·유예 배지(예정 삭제일 = 신청 시각 + 10일 [코드 `DELETION_GRACE_PERIOD`]).
- AC4 상태 변경: `confirmed` 없는 POST는 확인 화면만(DB 무변경·로그 0건), 확인 POST는 DB 변경 + 감사 로그(actor·action·target_user·ip·ua)가 같은 트랜잭션, PRG 리다이렉트 + 성공 메시지. 로그 저장 실패 시 플래그 변경도 롤백. `select_for_update` 계약(FOR UPDATE 관찰).
- AC5 보호: superuser 대상(자기 계정 포함)은 무변경·오류 메시지·로그 없음. 이미 목표 상태면 무변경·안내 메시지·로그 없음. `enabled`가 `"1"`/`"0"` 외면 400·무변경·로그 없음(SRR AC-S2).
- AC6 비활성화된 계정의 기존 세션은 다음 요청에서 익명 처리.
- AC7 감사 로그 화면·대시보드 대상 열은 `계정 #<id>`(superuser에게만 상세 링크), 비-superuser 스태프 응답 본문에 대상 회원 이메일 0건(SRR AC-S1), `?q=`는 대상 이메일에 매칭하지 않음, ip·ua 미노출 유지. 라벨 4종 한국어 표시.
- AC8 사이드바 링크는 superuser에게만 — 비-superuser 스태프 응답 본문에 `/staff/accounts/` 0건.
- AC9 `makemigrations --check` 드리프트 없음, `manage.py check` 0 issues, 회귀 전부 통과, Chrome DevTools MCP 브라우저 캡처(목록·검색·상세·확인·성공·403·사이드바 조건), WED·BIR 사후 `Conforms`, QVL 완료 판정.

## Activated Roles / Not Activated

- Activated [문서 4역할 검토 결과 2026-09-06]: Product Scope Owner(v1 검토 완료 — 범위 1:1 일치, ★1 승인·★2 사용자 확인 권고·AC 누락 1건), Domain Architecture Reviewer(v1 검토 완료 — 분할 승인·정정 2건·이연 3건), Security & Resilience Reviewer(v1 검토 완료 — Medium 2·Low 1·세션 판정), Backend TDD Coach(Test List 확정 — 아래), Backend & Integration Engineer(백엔드·테스트·문서), Frontend Implementation Engineer(템플릿·CSS·셸), Web Experience Designer·Browser Interaction Reviewer(사전 산출 완료 — 사후 판정), Quality Verification Lead(최종 매트릭스).
- Not activated: Deployment & Operations Reviewer(추가 nullable FK + choices 변경만, env·프로세스·배포 절차 무변경), AI Automation Architect(LLM 없음).

## Domain Boundary and Dependency Direction

- `staff → accounts(services·queries)` 허용(`web → accounts` 선례 `web/views/account.py:9`; 경계 가드는 accounts→archive만 검사 [코드 `tests/core/test_architecture_boundaries.py:319-332`], 도메인→staff 금지 가드는 events·drafts·archive만 [코드 `:362-374`]). `accounts`는 `staff`를 임포트하지 않는다.
- 플래그 변경 규칙(보호 계정·멱등)은 `accounts`가 소유, 감사 기록은 `staff` 뷰가 같은 트랜잭션에서(`_helpers.py:1-6` 규칙 유지).
- 테스트 계층 순수성 가드의 앱 튜플에 `accounts`가 없어 [코드 `:626`] 뷰 테스트가 `accounts.services`를 임포트해도 자동으로 잡히지 않는다 — 뷰 테스트는 client 픽스처로 HTTP 경계만, 서비스 단위 테스트는 별도 파일로 수동 분리(DAR).

## Coupling and Cohesion / Pythonic Code Design

- 서비스 시그니처 `(user, *, enabled) -> bool`, 예외 1종 `ProtectedAccountError`(accounts.services) — 형제 함수(`request_deletion(user)` 등)와 같은 스타일. `update_fields` 저장.
- 두 뷰(staff/active)는 `staff/views/accounts.py` 내부 `_apply_flag_change(request, pk, *, field, service, actions, labels)`로 중복 제거하되 URL·감사 액션은 분리.
- 확인 템플릿 하나를 컨텍스트로 재사용. 조회는 `values()`로 필요한 열만.
- `superuser_console_required`는 합성(DAR 코드 제안 채택).

## 파일 (N 신규 / M 수정) — 착수 시 `ls`로 실측

- N: `accounts/queries.py`, `staff/views/accounts.py`, `staff/migrations/0008_staffactionlog_target_user_and_more.py`(0001~0007 존재 [실측 `ls`]), `templates/staff/accounts/list.html`·`detail.html`·`confirm.html`, `static/css/staff/pages/accounts.css`, `docs/BE/staff-account-operations.md`, `tests/staff/test_staff_account_views.py`, `tests/auth/test_account_flag_services.py`, `tests/auth/test_account_staff_queries.py`(코치: `tests/accounts/`는 없고 `tests/auth/`가 accounts 서비스 테스트 관례 [실측 `ls tests/auth`]).
- M: `accounts/services.py`, `staff/permissions.py`, `staff/models.py`, `staff/action_labels.py`, `staff/views/_helpers.py`, `staff/views/__init__.py`(export), `staff/urls.py`, `staff/queries.py`(select_related·values에 `target_user_id`만), `staff/views/audit_log.py`(대상 라벨 `계정 #id`), `staff/search.py`, `templates/staff/_console_shell.html`, `templates/staff/dashboard.html`(대상 열 분기), `docs/operations-runbook.md`, `docs/backlog.md`, `tests/staff/test_staff_audit_log_view.py`(비식별 라벨·이메일 0건).

## Test List (Backend TDD Coach 확정, SRR 정정 반영)

파일: `tests/staff/test_staff_account_views.py`(web), `tests/auth/test_account_flag_services.py`·`tests/auth/test_account_staff_queries.py`(domain), 확장 `tests/staff/test_staff_audit_log_view.py`, 재사용 `tests/staff/test_staff_action_labels.py`·`tests/core/test_migrations_in_sync.py`. 뷰 테스트는 client 픽스처만, 서비스 테스트는 domain 파일에.

- T1 목록 관문 [문서 코치 검토 결과]: S1 `익명_사용자가_계정_목록에_접근하면_로그인_페이지로_리다이렉트된다`(Red: URL 미등록→404) / S2 `슈퍼유저가_아닌_사용자가_계정_목록에_접근하면_403을_응답한다`(parametrize 일반_사용자·슈퍼유저_아닌_스태프).
- T2 목록: S1 `슈퍼유저가_계정_목록에_접근하면_200과_함께_대상_행을_본다` / S2(domain) `list_accounts_for_staff는_필요한_필드만_최신_가입순으로_반환한다` / S3(domain) `list_accounts_for_staff는_검색어와_이메일이_부분_일치하는_사용자만_반환한다` / S4 `계정_목록_화면은_q_검색어와_일치하는_사용자만_보여준다` / S5 `계정_목록은_페이지당_STAFF_ACCOUNT_LISTING_PAGE_SIZE건으로_나뉜다`.
- T3 상세: S1 `슈퍼유저가_아닌_사용자가_계정_상세에_접근하면_403을_응답한다` / S2 `탈퇴_신청이_없는_대상의_상세_컨텍스트에는_유예_예정일이_없다` / S3 `탈퇴_유예_중인_대상의_상세_컨텍스트_유예_예정일은_신청_시각에_10일을_더한_값이다` / S4 `is_protected는_대상이_슈퍼유저면_참이고_아니면_거짓이다`.
- T4 `set_staff_flag`(domain): S1 스태프 아닌 대상 enabled=True→스태프·True / S2 이미 목표 상태→무변경·False / S3 슈퍼유저 대상→`ProtectedAccountError`·무변경.
- T5 `set_active_flag`(domain): T4와 동형(활성→비활성·True / 멱등 False / 슈퍼유저 보호).
- T6 상태 변경 관문: S1 익명 POST→로그인 리다이렉트(두 필드) / S2 비-superuser POST→403(필드×주체) / S3 GET→405·무변경.
- T7 `confirmed_없이_상태_변경_POST하면_확인_화면을_보여주고_대상을_바꾸지_않는다`(두 필드). SRR 추가: `enabled가_1_또는_0이_아니면_400을_응답하고_대상을_바꾸지_않고_로그를_남기지_않는다`(누락·빈 값·true·2).
- T8 확인 POST: S1 `confirmed_yes로_상태_변경_POST하면_대상이_바뀌고_감사_로그가_남고_성공_메시지와_함께_상세로_리다이렉트된다`(grant/revoke/deactivate/reactivate) / S2(contract) `상태_변경_확인_POST는_대상_행을_잠그고_처리한다`(`CaptureQueriesContext`, `FOR UPDATE` 존재만 — `test_게시_토글은_대상_행을_잠그고_읽는다` 선례) / S3(contract) `감사_로그_저장이_실패하면_상태_변경도_롤백된다`(`StaffActionLog.objects.create` 몽키패치로 실패 주입, 관찰은 DB 재조회·로그 0건).
- T9 무변경 경로: S1 `슈퍼유저_대상에_확인_상태_변경_POST를_보내면_변경없이_오류_메시지를_보여주고_로그를_남기지_않는다`(타인_슈퍼유저·본인_계정) / S2 `이미_목표_상태인_대상에_확인_상태_변경_POST를_보내면_변경없이_안내_메시지를_보여주고_로그를_남기지_않는다`.
- T10 `비활성화된_대상의_기존_세션은_다음_요청에서_익명으로_처리된다`(대상 클라이언트 force_login → 다른 superuser가 비활성화 → 대상 요청이 익명 취급; 목킹 없음. Green이면 추가 코드 없음).
- T11 감사 표시(SRR 정정): S1 `계정_행동_로그_행의_대상_라벨은_계정_번호이고_본문에_대상_이메일이_없다`(비-superuser 스태프 클라이언트) / S2 `감사_로그_q_검색어는_대상_계정_이메일과_매칭하지_않는다` / S3 `대시보드_최근_처리_내역의_계정_행동_행에_대상_이메일이_없다`.
- T12 라벨 계약(이미 Green): 순서 고정 — `Action` 4종을 먼저 추가하고 `uv run pytest -q tests/staff/test_staff_action_labels.py`로 Red(missing 4건)를 확인한 뒤 `ACTION_LABELS`를 채운다. 이 Red가 뮤테이션 증거다.
- T13 마이그레이션 계약(이미 Green): `target_user` FK 추가 후 마이그레이션 파일 생성 전에 `tests/core/test_migrations_in_sync.py` Red 확인 → `makemigrations staff` → Green.
- T14 사이드바: S2 `슈퍼유저의_콘솔_화면_본문에는_계정_링크가_있다`를 먼저 Green(링크 추가) → S1 `슈퍼유저가_아닌_스태프의_콘솔_화면_본문에는_계정_링크가_없다`(조건 추가). 파일은 `tests/staff/test_staff_account_views.py`.

## 구현 순서 (슬라이스별 커밋, pytest 실행·판정은 오케스트레이터 단독)

1. BIE: 백엔드 테스트 전부 선작성(T1~T11, T14; 프로덕션 코드 무변경) → 오케스트레이터 실행으로 Red 사유 확인.
2. BIE 슬라이스 A(관문·조회·목록·상세 뷰 — T1~T3) / 슬라이스 B(서비스 — T4·T5) / 슬라이스 C(모델·마이그레이션·라벨 — T12·T13 순서 고정) / 슬라이스 D(상태 변경 뷰·감사 — T6~T10) / 슬라이스 E(감사 표시 — T11, 사이드바 T14). 슬라이스마다 오케스트레이터가 Green 확인 후 커밋.
3. FIE 병행: 컨텍스트 계약대로 템플릿(list·detail·confirm)·CSS·셸(사이드바·crumb·title)·`search.py`. BIE는 템플릿 파일을 만들지 않는다(뷰 테스트가 템플릿을 요구하면 FIE 산출을 기다린다).
4. 브라우저 검증(오케스트레이터, Chrome DevTools MCP) → WED·BIR 사후 판정 → QVL 매트릭스 → 문서(런북 §5·`docs/BE/staff-account-operations.md`·백로그) → 전체 회귀 → PR.

## 검증 명령과 기대 증거

- `uv run pytest -q tests/staff/test_staff_account_views.py tests/auth/test_account_flag_services.py tests/auth/test_account_staff_queries.py` → 신규 전부 passed.
- `uv run python manage.py makemigrations --check --dry-run` → "No changes detected". `uv run python manage.py check` → 0 issues.
- `uv run pytest -q` → 기준선 2364 + 신규 건수 passed [실측으로 기록].
- 브라우저: Chrome DevTools MCP, 1280px, `/staff/accounts/` 목록·검색·상세·확인·성공 메시지·비-superuser 403·사이드바 링크 유무 캡처, 콘솔 오류 0건. 캡처는 검증 후 삭제.

## Frontend Review Evidence

- 깊이 High(신규 화면·내비게이션·확인 흐름·크로스 페이지 셸 변경).
- 사전: WED 명세·BIR 기준 = `.docs/FE/2026-09-06-staff-backoffice-frontend-review.md` + 백로그 H절 "프론트 필요 기능" H1 항목(서버 렌더 2단계 확인 채택).
- 계획된 브라우저 증거: 위 검증 명령 절.
- 사후 판정 기록 [문서 `.docs/FE/2026-09-06-staff-backoffice-frontend-review.md` "사후 판정" 절, 2026-09-07]:
  - **WED 사후 판정: Conforms**(2026-09-07) — 1차 `Deviates` 1건(목록 열 순서가 명세 "이메일/가입일/상태/권한/마지막 로그인/상세"와 다름, `templates/staff/accounts/list.html:25-30`) → 커밋 c825208로 재정렬 → 재판정 `Conforms`(캡처 t19-list.png 헤더·첫 행 실측 일치). 보호 계정 화면 캡처(t19-protected.png: 버튼 disabled 2개·사유 문단·form 0개)로 Unverified 해소. 그 외(사이드바 진입 조건·상세 헤더·유예 배지 읽기 전용·rail-card·서버 렌더 2단계 확인·감사 비식별 라벨·CSS 토큰 격리) 명세 일치. Optional polish: 성공 메시지 "부여이(가)" 조사, 확인 화면 새로고침 링크 GET 405(delete_confirm과 동일 기존 셸 특성).
  - **BIR 사후 판정: Conforms**(2026-09-07) — 관문 403/405·`enabled` 400·확인 2단계·보호 계정·`data-submit-guard`·취소→확정 탭 순서 모두 코드·테스트 일치. Low 1건: PRG 화면이라 `data-committed-redirect` 미사용, 뒤로가기 복원 후 확정 재클릭 가능 → 오케스트레이터 실측(Chrome DevTools MCP, `back_forward` 복원·버튼 `disabled=false`·재클릭 → "이미 해당 상태라 변경하지 않았습니다"·`StaffActionLog` 대상 84 행 staff_grant·staff_revoke 2건뿐)으로 서비스 멱등이 결과 안전을 보장함을 확인, 가드레일 (i)로 `docs/BE/staff-account-operations.md`에 기록.
  - QVL 1차: 백엔드 AC 전부 Passed, 사후 판정 산출물 미기록으로 Blocked → 위 기록으로 해소 재상신. 권고 반영: AC2 배지 3-state 테스트·AC1 상세 URL 익명 리다이렉트 테스트 추가.

## 재검토 (2026-09-07, 사용자 지시 "재검토" — PR #340 diff 전체, 신규 컨텍스트 4역할) [문서 각 역할 산출]

- 대상: `git diff main...HEAD` 27파일 / 2184줄 [실측 `wc -l`]. CI 4체크 pass [실측 `gh pr checks 340`]. `sqlmigrate staff 0008` = ADD COLUMN NULL + FK + CREATE INDEX(비-CONCURRENTLY) [실측].
- DAR 사후: 사전 경계 결정 5건 전부 코드 일치. **결함 1건** — 뷰 테스트가 `accounts.services.request_deletion`을 직접 호출(계층 순수성 가드가 `accounts`를 안 봐서 자동 미검출, `tests/core/test_base_site_messages.py:26-27` 선례는 필드 직접 대입) → 같은 트랙에서 수정. 권고: `staff/models.py` `__str__` 3중 조건식 → if/elif, `accounts/queries.py` 독스트링 인용 과장 정정 → 반영. `test_service_signature_conventions.py` 제외 사유 주석 부정확은 착수 전 이연 유지(호출자 1→2곳).
- TDD 코치 After Green: 이름-행동 불일치 0건, 사적 구현·쿼리 순서·호출 횟수 결합 0건, 성공 메시지 리터럴 결합 0건. **누락 2건** — 존재하지 않는 pk 404(뷰 분기 3곳 미검증), 확인 화면 컨텍스트 값 → 테스트 추가. 오케스트레이터 추가: 메시지 단언이 존재만 확인하던 4건을 텍스트 단언으로 강화. Refactoring allowed: Yes(범위 한정).
- SRR 신규 컨텍스트: 8개 공격 시나리오 중 7개 차단 확인(비-superuser 우회·파라미터 조작·감사 우회·정보 노출·레이스·DoS·마이그레이션 공존). **Medium 1건(★3 결정 대기)** — 상태 변경 POST에 액션 빈도 제한·스텝업 재인증이 없어 탈취된 superuser 세션이 HTTP만으로 비-superuser 계정을 순차 정지·권한 회수 가능(superuser 대상 보호로 피해 상한은 정지·회수). 완화 후보: `staff/views/discovery.py:31-36` 캐시 스로틀 패턴 재사용 또는 비밀번호 재확인. v1 SRR이 step-up을 이연했던 항목과 같은 축이라 구현하지 않고 사용자·PSO 결정으로 올린다. Low: `recent_staff_actions` select_related(기존 이연과 동일).
- DOR: 차단 없음 — 0003(target_event) 선례와 동일 패턴, env·프로세스 변경 0건, entrypoint가 migrate 선행이라 신코드-구DB 창 없음, 롤백은 코드만. 권고 반영: 런북 §5 `is_active` 예시, BE 문서에 sqlmigrate 사실. 관찰: `staff/admin.py` list_display에 target_event·target_user 미포함(트랙 이전부터, 이연).
- 오케스트레이터 선독: 성공 메시지 "이(가)"·확인 화면 "을(를)" 조사 표기 → 라벨 4종이 모음 종결이라 "가"/"를"로 정정.

## 이연 (Deferred Refactoring Note 포함)

- ★3 계정 상태 변경 POST 액션 빈도 제한 또는 step-up 재인증(SRR 재검토 Medium) — **사용자 결정 2026-09-07: 기본값(미구현) 수용, 이연 유지**. 트리거: superuser 세션 탈취 사고 또는 스태프 규모 확대. PR #340은 2026-09-07 머지(091429b).
- ★2 **사용자 확정(2026-09-07): superuser는 shell로만 만들고 바꾼다** — 콘솔 제외 규칙 확정, 카운트 기반 보호는 이연에서 제거. 계약 테스트(콘솔·서비스 소스에 `is_superuser` 대입 0건)로 고정(후속 PR). 계정 변경 알림 메일, `is_active=False` 시 세션 즉시 삭제(세션 외 인증 경로 추가 시), 상태 변경 step-up 재인증(SRR), `staff/admin.py` `list_display` target_user, 탈퇴 유예 스태프 취소, RBAC.
- SRR 사후(Low): `staff/queries.py` `recent_staff_actions`의 `select_related("target_user")`가 이메일을 메모리에 올리고 대시보드 템플릿 자제에만 의존 — 기존 ip·ua와 같은 패턴, 즉시 노출 없음. 하드닝 후보: `.values()` 요약으로 전환.
- DAR: `StaffActionLog` 대상 FK 3종 상호 배타 DB 제약(트리거: 네 번째 target FK 또는 동시 채움 사고) / `tests/core/test_service_signature_conventions.py`의 accounts.services 제외 사유 주석이 이미 부정확(`web/views/account.py:9`가 앱 밖 호출자) / 도메인→staff 금지 가드에 `accounts` 미포함(`tests/core/test_architecture_boundaries.py:362-374`).

## 문서 대상·핸드오프 조건

`docs/BE/staff-account-operations.md`(신설, 가드레일만), 런북 §5, 백로그 H1/H14, pr-log(머지 시), 메모리 `staff-backoffice-gap-review`. 사용자 확인 대기: ★2(superuser 계정 콘솔 제외 영구화).

---

