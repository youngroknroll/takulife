# 계정 설정 영역 (에디토리얼) — 기술 기록

기준일: 2026-07-31 · 브랜치 `feat/account-settings-editorial`
대상: `/accounts/settings/`, `/accounts/email/`, `/accounts/password/change/`,
`/accounts/delete/`, `/accounts/confirm-email/<key>/`, `/accounts/delete/done/`

이 문서는 **가드레일만** 담는다. 계획 문서는 `.docs/FE/`에 있었고 git-ignored라
소실된다. 여기 적힌 것은 다음 작업자가 모르면 같은 실수를 반복할 것들이다.

## G1 ⚠️ 제출 가드가 버튼 `name`을 먹는다 — 자동 테스트가 구조적으로 못 잡는 결함

**현상**: 이메일 변경 화면의 폼 3개가 브라우저에서 **아무 동작도 하지 않았다.**
올바른 비밀번호를 넣어도 주소가 안 바뀌고, 틀린 비밀번호를 넣어도 오류가
안 떴다. 자동 테스트 2042건은 전부 통과했다.

**원인 사슬**:
1. `static/js/shared/staff_submit_guard.js`는 `submit` 핸들러 안에서 **동기적으로**
   `button.disabled = true`를 한다.
2. Chrome은 **disabled 컨트롤을 폼 전송 데이터에서 제외**한다.
3. allauth `EmailView.post`는 **버튼 `name`으로만 분기**한다
   (`action_add` / `action_send` / `action_remove`).
4. `email`만 있고 액션 키가 없으면 allauth는
   `res = res or HttpResponseRedirect(self.get_success_url())`로 **조용히 302 후
   아무것도 하지 않는다.**

**실측 증거** (같은 폼을 가드 유무로 비교):

| 조건 | 전송된 키 |
|---|---|
| 가드 없음 | `["email", "action_add"]` |
| 가드 있음 | `["email"]` ← `action_add` 소실 |

**가드레일**: `data-submit-guard`가 붙은 폼에서 **서버가 제출 버튼의 `name`에
의존하게 만들지 마라.** 액션 이름은 `<input type="hidden">`으로 보낸다.
`templates/account/email_change.html`이 그렇게 고쳐져 있고, 되돌리지 말라는
주석이 각 폼 위에 있다.

**왜 공유 가드를 안 고쳤나**: 스태프 콘솔 전체가 그 파일을 공유한다.
`[실측]` 현재 `data-submit-guard` 폼 중 제출 버튼에 `name`이 있는 템플릿은
**계정 이메일 화면 하나뿐**이었으므로(스태프 폼은 전부 무명 버튼) 범위를
좁힌 수정이 옳았다.

**교훈**: Django 테스트 클라이언트는 JS를 실행하지 않는다. 이 결함은 브라우저
실측으로만 드러났다. **폼 제출 경로가 JS 가드를 거치면 자동 테스트 초록은
기능이 산다는 증거가 아니다.**

## G2 `accounts`는 `archive`를 임포트하지 않는다

탈퇴 화면이 삭제 대상 6종 카운트를 보여줘야 하는데, `accounts`에서
`archive.queries`를 부르면 승인되지 않은 새 의존 방향이 생긴다.

**해결**: 탈퇴 뷰(GET+POST)를 `core/views/account.py`로 옮겼다. 경계 가드가
`core/views/` 전체를 도메인 간 합성 지점으로 이미 허용하고, 그 파일은 이미
`archive.queries`를 임포트한다. 락아웃 헬퍼와 상수는 `accounts/services.py`로
승격해 보안 규칙 소유권은 `accounts`에 남겼다.

⚠️ **`[실측]` 착수 시점에 이 방향을 지키는 가드가 없었다.** `archive` 임포트
금지 스캔 대상이 `["events", "drafts"]`뿐이라 `accounts`는 목록 밖이었다.
같은 커밋에서 `accounts` 방향을 신설했고, **뮤테이션 2회(정적 임포트 /
`__import__` 동적 임포트)로 실제로 잡는지 확인**했다.

## G3 탈퇴 완료 안내는 302 + 세션 적재다 (같은 응답 렌더 아님)

검토자 둘이 정면으로 충돌했다. 보안 검토는 "같은 POST 응답에서 직접 렌더",
도메인 검토는 "새 URL + 리다이렉트"를 주장했다.

**판정 근거**: `[실측]` 같은 응답 렌더(200)는 기존 테스트 **8건**을 깨뜨린다.
그 8건이 보호하는 것은 탈퇴 화면이 아니라 **락아웃 창 고정·타 기기 세션
종료·재로그인 차단**이라는 무관한 보안 행위다.

**구현**: `request_deletion()` → `logout(request)` → **그 다음에**
`request.session`에 적재 → `redirect("account-delete-done-page")`.
완료 뷰는 키를 `pop`하고 없으면 홈으로 보낸다. `@never_cache` 적용.

⚠️ **순서 필수**: `logout()`이 세션을 flush한다. 이전에 쓰면 사라진다.
기존 `messages.success`가 `logout()` 뒤에 있는 것과 같은 이유다.

## G4 오류·파괴적 동작은 `rose`, 계정 정체성은 `brand`

시안은 계정 영역 전체를 브랜드 레드 하나로 그렸으나 **사용자가 저장소 관례를
선택했다**(2026-07-31). 마이페이지 탈퇴 버튼, 컬렉션·방문기록 삭제 버튼, 전
오류 메시지가 이미 `rose`이고, 같은 화면에서 두 빨강이 다른 뜻으로 쓰이는 것을
피한다.

- `brand` / `brand-ink`: kicker, 활성 인덱스, 위험구역 테두리, 경고 배지, 1단계
- `rose`: 실패 오류(배너·필드), 최종 탈퇴 버튼, 3단계 "영구 삭제"
- `mint`: 2단계 "자동 취소", "인증됨" 배지

**토큰 실측**: bare `--mint`와 `--border-strong`은 **이 저장소에 없다**.
`--mint-soft`/`--mint-ink`, `--border-soft`를 쓴다.

## G5 픽스처가 숨기는 전제 4가지

1. **`make_user()`는 `EmailAddress` 행을 만들지 않는다.** 인증 정상 경로에는
   `make_verified_user()`, 레코드 없음 경계에만 `make_user()`. 뒤바꾸면 두
   테스트가 같은 경로만 두 번 검증하고 null 분기는 한 번도 안 돈다.
2. **`make_visit_photo`는 `visit_record`를 받는다**(user 아님). 두 사용자가 같은
   `visit_record`를 공유하면 소유자 스코프 분리가 전혀 검증되지 않는다.
3. **`user_collection_item_summary_counts`의 `total_count`는 보유 외 행도
   포함**한다. `quantity>0` 행만으로 픽스처를 짜면 우연히 일치한다.
4. 카운트 검증은 **6종을 서로 다른 건수**로. 전부 같으면 순서 뒤바뀜을 못 잡는다.

## G6 탈퇴 화면의 오류 경로는 컨텍스트를 잃기 쉽다

비밀번호 오류·락아웃 두 실패 경로가 `delete_targets`를 컨텍스트에 넣지 않아,
비밀번호를 한 번 틀리면 **삭제 대상 6종 표가 통째로 사라졌다**(브라우저 실측).
사용자가 탈퇴 여부를 판단하는 근거가 오류 한 번에 없어진다.

**해결**: `_build_delete_targets(user)` 하나로 모으고 GET·오류·락아웃 세 경로가
전부 그것을 호출한다. 회귀 가드 2건(AS-14/AS-15)을 추가했고, **호출 지점을
경로별로 하나씩 제거하는 뮤테이션 2회로 각각 Red를 확인**했다.

## G7 운영상 미해결 (이번 범위 밖, 실사용자 도입 전 필수)

- ⚠️ **`purge_deleted_accounts`에 스케줄러가 없다.** `[실측]` CI·entrypoint·
  runbook 전부 무참조. 완료 안내 화면이 "삭제 예정일"을 사용자에게 약속하므로,
  실사용자 도입 전 `docs/deploy-runbook.md` 사전 점검 항목에 추가해야 한다.
- **SMTP 미설정은 선재 갭**이다. 이메일 변경 흐름도 같은 갭을 상속한다(콘솔
  백엔드로 출력될 뿐 실제 발송 안 됨). 신규 항목을 열지 말고 기존 SMTP
  백로그에 붙인다.
- `ACCOUNT_CHANGE_EMAIL` **최초 프로덕션 전환 전** `EmailAddress` 중복 행 감사
  2건을 실행하라. 한 사용자가 검증된 주소를 2개 이상 갖고 있으면 단일 UI에
  안 보이면서도 로그인·비밀번호 재설정에는 계속 쓰인다.
  ```python
  EmailAddress.objects.values("user_id").annotate(n=Count("id")).filter(n__gt=1)
  EmailAddress.objects.filter(verified=True).values("user_id").annotate(n=Count("id")).filter(n__gt=1)
  ```

## 이월 (별도 트랙)

`templates/core/partials/_auth_field.html`은 오류 필드에 `aria-describedby`/
`aria-invalid`를 걸지 않는다. `[실측]` 이 파셜을 쓰는 템플릿은 범위 밖
**5개 템플릿 / 10개 include 사이트**(login/signup/password_reset* 등. 정정
2026-07-31: 당초 「12개」는 `auth.css`를 로드하는 템플릿 수였고 단위가
뒤바뀐 것이었다 — `.docs/FE/auth-editorial.md` M4)라 이번에 건드리지
않았다. 인증 화면 리스킨 트랙에서 파셜 자체를 고치는 것이 옳다.

## 검증 증거 (2026-07-31)

| 항목 | 결과 |
|---|---|
| 백엔드 회귀 | `[실측]` **2044 passed** (착수 시점 2028 → 신규 16건) |
| Django check | 0 issues |
| 마이그레이션 드리프트 | 없음 (모델 변경 0건) |
| 뮤테이션 검증 | 경계 가드 2회, `delete_targets` 가드 2회 — 전부 Red 후 복원 Green |
| 브라우저 | 1280×900 다크 / 375×800 / 320×720 라이트. 가로 오버플로 0, 넘치는 요소 0 |
| 이메일 3폼 | 변경·재발송·취소 전부 실제 브라우저에서 동작 확인 |
| 탈퇴 왕복 | 302 → 완료 안내 → 재방문 시 홈 리다이렉트 → 재로그인으로 예약 취소, 기록 6종 전부 보존 |
