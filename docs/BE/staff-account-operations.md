# 스태프 계정 운영 화면(`/staff/accounts/`) 가드레일

트랙 19(H1)로 도입한 `/staff/accounts/` 계정 운영 화면이 지키는 경계와 왜
그렇게 정했는지를 남긴다. 작업 일지가 아니라 이후 이 코드를 건드릴 때
깨뜨리기 쉬운 계약만 적는다.

## (a) 관문은 `superuser_console_required` — 사이드바 링크 숨김은 UX일 뿐

계정 화면 4개 뷰(`staff_accounts`, `staff_account_detail`,
`staff_account_set_staff`, `staff_account_set_active`)는 모두
`superuser_console_required`로 게이트한다(`staff/views/accounts.py:56`,
`:84`, `:150-151`, `:166-167`). 이 데코레이터는 `staff_console_required`
위에 `is_superuser` 검사만 더한 합성이다(`staff/permissions.py:28-39`).
`templates/staff/_console_shell.html`의 사이드바 "계정" 그룹을
`request.user.is_superuser`일 때만 렌더하는 것은 화면 안내일 뿐이고, 실제
경계는 이 데코레이터다 — 링크를 숨기지 않아도 비-superuser 스태프는 URL을
직접 두드려도 403을 받는다.

## (b) 보호 계정 — `is_superuser` 대상은 `ProtectedAccountError`(★ 사용자 확인 대기)

`set_staff_flag`·`set_active_flag`(`accounts/services.py:138-150`,
`:153-162`)는 대상 `user.is_superuser`가 참이면 저장 없이
`ProtectedAccountError`를 던진다. 조작 주체가 superuser 한정이라 이 규칙은
자기 자신을 포함해 **superuser 계정 전체**를 이 화면의 변경 대상에서
제외하는 결과를 낳는다 — superuser가 아닌 계정만 이 화면에서 다룰 수 있고,
superuser 계정은 여전히 `manage.py shell`로만 다룬다
(`docs/operations-runbook.md` §5).

★ 이 "superuser 전체 제외" 범위는 트랙 19 계획서(prompt_plan.md) ★2에서
**사용자 확인 대기** 상태로 남아 있다. H1이 원래 목표한 "shell 없이"가
superuser 계정에 대해서는 영구 예외로 남는다는 뜻이라, 승인 시점의
판단 없이는 이연 상태를 바꾸지 않는다. 승인되면 "마지막 관리자 1명만 보호"
같은 카운트 기반 보호로 좁히는 안이 이연 항목으로 대기 중이다.

## (c) 상태 변경은 토글이 아니라 목표 상태 지정 — `enabled`는 `"1"`/`"0"`만

폼은 항상 `enabled` 값을 명시해 보낸다(현재 상태의 반대값을 서버가 계산하지
않고 템플릿이 렌더 시점에 계산해 hidden input에 박는다,
`templates/staff/accounts/detail.html:47`, `:79`). 뷰는
`_ENABLED_VALUES = {"1": True, "0": False}` 명시 매핑으로만 파싱하고
(`staff/views/accounts.py:30`, `:103-106`), 이 두 값이 아니면(누락·빈
값·`"true"`·`"2"` 등) `HttpResponseBadRequest`로 400을 반환하며 DB
변경과 로그 생성 둘 다 없다. 문자열 truthy 판정(`bool("0")` 같은 함정)을
피하려는 의도적 설계다.

이미 목표 상태와 같으면 `set_staff_flag`/`set_active_flag`가 저장 없이
`False`를 반환하고(`accounts/services.py:146-147`, `:158-159`), 뷰는 이를
`messages.info`로만 안내하고 감사 로그를 남기지 않는다
(`staff/views/accounts.py:143-146`). 멱등 재시도(같은 요청이 중복
도착해도 상태·로그가 늘지 않음)가 이 계약의 목적이다.

## (d) 확인은 `confirmed=yes` 2단계, 변경은 원자적 트랜잭션

`request.POST.get("confirmed") != "yes"`이면 뷰는 DB를 건드리지 않고
`confirm.html`만 렌더한다(`staff/views/accounts.py:110-123`). 확인 후에는
`transaction.atomic()` 블록 안에서 `User.objects.select_for_update()`로
대상 행을 잠그고, 서비스 호출과 `StaffActionLog.objects.create(...)`가 같은
트랜잭션에서 실행된다(`staff/views/accounts.py:126-138`). 감사 로그 저장이
실패하면 플래그 변경도 함께 롤백된다 — 삭제 확인 패턴
(`staff/views/events.py:480-483`, `:501-510`)과 같은 흐름이다.

## (e) 감사 대상은 `target_user`, 운영자 화면에는 이메일을 노출하지 않는다

`StaffActionLog.target_user`는 `settings.AUTH_USER_MODEL`을 가리키는 nullable
FK다(`staff/models.py:46-51`, `related_name="+"`). `Action`에 `staff_grant`·
`staff_revoke`·`user_deactivate`·`user_reactivate` 4종이 있다
(`staff/models.py:25-28`, 모두 `max_length=16` 이내).

감사 로그 화면(`staff/views/audit_log.py`)과 대시보드는 `staff_console_required`
(is_staff 전체)로 게이트되고, 계정 운영 화면(superuser 한정)보다 넓은
대상이 본다. 그래서 대상 라벨은 이메일이 아니라 `계정 #<id>`로만 렌더한다
(`staff/views/audit_log.py:28-30`: "이 화면은 is_staff 전체가 보므로 대상
이메일 대신 번호만 노출한다"). 이유는 이메일을 넣으면 계정 화면 자체의
superuser 경계를 감사 로그 화면이 우회해 노출하기 때문이다. `?q=` 검색도
`target_user__email`을 대상에 넣지 않는다 —
`list_staff_action_log`(`staff/queries.py:47-68`)가 검색하는 필드는
행위자 이메일·대상 드래프트·대상 이벤트 세 가지뿐이고 대상 계정은
포함하지 않는다(존재 여부를 검색으로 되물어 알아내는 우회를 막기 위해서,
`staff/queries.py:54-56` 독스트링). superuser는 `staff/admin.py`로 전체
`StaffActionLog`(ip·user-agent 포함)를 계속 볼 수 있다.

## (f) 탈퇴 유예 계정은 변경을 허용한다 — 버튼 비활성화 없음, 안내만

`staff_account_detail`은 `deletion_scheduled_for`를
`account.deletion_requested_at + accounts_services.DELETION_GRACE_PERIOD`로
계산해 컨텍스트에 넣는다(`staff/views/accounts.py:87-89`, 유예 10일은
`accounts/services.py:22`). 서버는 유예 중인 계정의 상태 변경을 그대로
허용한다 — `set_staff_flag`/`set_active_flag`는 `deletion_requested_at`을
전혀 검사하지 않는다. 화면은 버튼을 비활성화하지 않고 안내 문단만 붙인다
(`templates/staff/accounts/detail.html:42-43`, `:74-75`: "탈퇴 유예 중인
계정입니다. 변경은 가능하지만 재로그인 시 유예가 취소됩니다"). 유예
취소는 재로그인 시 별도 신호로만 일어나고(`accounts/models.py:15-18`),
이 화면의 상태 변경 자체는 유예 취소와 무관하다.

## (g) `is_active=False`는 다음 요청부터 세션 무효 — 세션을 직접 삭제하지 않는다

`set_active_flag`는 `user.is_active`만 저장하고 세션 테이블을 건드리지
않는다(`accounts/services.py:153-162`). 로그인 유지는
`SessionAuthentication` 단일 경로이고, `ModelBackend.get_user`가
`user_can_authenticate` 실패 시 `None`을 반환해 다음 요청부터 대상이
익명으로 처리된다(`docs/operations-runbook.md` §5, allauth 65.18.0은
`get_user`를 오버라이드하지 않는다). 이는 `request_deletion`이 탈퇴 신청
시 세션을 즉시 삭제하는 것(`accounts/services.py:97-108`)과는 다른 별개
경로다 — 유예 신청 중에는 `is_active`가 그대로라 세션 삭제가 따로 필요했던
반면, 이 화면의 비활성화는 `is_active` 변경 자체가 다음 요청을 막아 세션을
직접 지울 필요가 없다.

## (h) 대상 FK 3종 상호 배타는 독스트링 관례 — DB 제약 없음

`StaffActionLog`는 `target_draft`·`target_event`·`target_user` 세 FK를
동시에 가진다(`staff/models.py:36-51`). 한 로그 행이 셋 중 하나만
채운다는 규칙은 `__str__`의 우선순위 처리(`staff/models.py:59-69`)와
호출부 관례로만 지켜지고, `CheckConstraint`는 없다
(`[코드] rg CheckConstraint staff/` 결과 0건). 트랙 19에서 DB 제약 추가는
스코프 밖으로 이연했다.
