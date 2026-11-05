# 방문 기록 사진 업로드 멱등성·동시성 사례

응답 유실 뒤 재시도가 같은 사진을 두 번 저장하지 않게 만든 과정과, 그
과정에서 발견한 검사 순서 결함을 기록한다. 정본 코드는
`archive/services.py`의 `create_visit_record_photo`, 제약은 `archive/models.py`의
`VisitRecordPhoto`, 테스트는 `tests/archive/test_archive_services.py`다.
수치는 단위와 출처를 함께 적었다. `[코드]`는 저장소에서 읽은 값,
`[실측 날짜]`는 그 날짜에 실행해 얻은 값이다.

## 1. 문제

방문 기록 수정 화면(`static/js/pages/visit_edit.js`)은 업로드에 실패한 항목을
큐 맨 앞에 남겨 두고 저장 버튼을 다시 열어 둔다. 서버가 사진을 커밋한 뒤
응답만 유실되면, 다음 저장에서 같은 `File` 객체가 다시 전송돼 같은 사진이
두 행으로 저장됐다. `VisitRecord`·`CollectionItem`은 이미 `client_token`으로
재전송을 걸러내고 있었지만 `VisitRecordPhoto`와 `PersonalEntry`에는 그 키가
없었다(2026-07-28 커밋 `bff9c353` 본문 `[코드]`).

## 2. 원인 분석

- 외부 코드 검토는 작성 화면의 실패 경로를 위험 지점으로 지목했다. 코드를
  따라가 보니 작성 화면은 실패 시 재전송 채널 자체가 없고, 실제 재전송은
  수정 화면의 큐에서만 일어났다. 검토 결과를 그대로 믿지 않고 재확인해
  적용 범위를 좁혔다.
- 형제 패턴(`create_visit_record`)을 그대로 옮기면 상한 검사가 재전송 조회보다
  먼저 실행된다. 기록당 사진 상한은 5장(`MAX_PHOTOS_PER_RECORD` `[코드]`)이라,
  5번째 사진을 저장한 요청이 재전송되면 이미 저장된 행을 돌려주는 대신
  "상한 초과"로 거부된다. 멱등 키가 필요한 바로 그 경우를 깨뜨리는 순서였다.
- 토큰을 업로드 직전에 발급하면 재시도마다 새 토큰이 생겨 아무것도 막지
  못한다. 토큰은 파일을 고른 시점에 발급해 큐 항목에 보관해야 재시도까지
  살아남는다.

## 3. 선택한 해결

| 계층 | 적용 | 이유 |
|---|---|---|
| DB | `UniqueConstraint(visit_record, client_token)` `unique_archive_visit_record_photo_visit_record_client_token` `[코드 archive/models.py]` | 서비스 코드를 우회하는 경로까지 최종 차단 |
| 서비스 | `transaction.atomic()` 안에서 부모 `VisitRecord` 행을 `select_for_update()`로 잠근 뒤 재전송 조회 → 상한 검사 → 저장 순으로 실행 `[코드 archive/services.py]` | 사진이 4장일 때 동시 요청 두 건이 모두 4장을 보고 저장하는 경합을 막고, 같은 토큰의 동시 요청은 락에서 대기한 뒤 커밋된 행을 보게 함 |
| 서비스 2차 방어 | `IntegrityError`를 atomic 블록 밖에서 잡아 같은 토큰의 행을 재조회 | PostgreSQL은 세이브포인트 롤백 전까지 같은 트랜잭션의 추가 문장을 거부하므로 블록 안에서 재조회하면 안 됨 |
| 클라이언트 | 파일 선택 시점에 `client_token` 발급, 큐 항목에 보관 | 재시도 요청이 같은 토큰을 싣게 함 |
| 뷰 | DRF `ScopedRateThrottle` `visit_record_photo_create` 30회/분 `[코드 config/settings.py]` | 재시도 폭주 억제 |

멱등 키의 범위를 `(user, client_token)`이 아니라 `(visit_record, client_token)`으로
둔 이유는 사진이 사용자 소유 최상위 자원이 아니라 방문 기록의 하위 행이기
때문이다. 한 사용자가 여러 기록에 여러 사진을 만들며, 같은 클라이언트 토큰이
다른 기록에서 재사용돼도 충돌하면 안 된다.

대안으로 사진 테이블에 부분 유니크 인덱스만 두고 락을 생략하는 방식을
검토했지만, 상한 검사가 어차피 개수를 세야 하므로 모든 호출이 같은 락을
잡는다. 락을 잡은 뒤 재전송을 조회해도 추가 비용이 없다.

## 4. 검증

`tests/archive/test_archive_services.py` `[코드]`:

| 테스트 | 검증하는 실패 상황 |
|---|---|
| `test_방문기록_사진을_추가하면_동시_업로드_방지를_위해_부모_방문기록_행을_잠근다` | `select_for_update` 호출을 스파이로 가로채 부모 행 잠금이 빠지면 실패 |
| 상한 초과 테스트(`PhotoLimitExceededError`) | 토큰 없는 6번째 업로드는 여전히 거부 |
| 5번째 사진 재전송 테스트 | 상한을 채운 업로드의 재전송이 상한 초과가 아니라 기존 행을 돌려줌. 검사 순서를 되돌리면 `PhotoLimitExceededError`로 실패하도록 설계 |
| 같은 토큰 2회 요청 테스트 | 행이 1건만 생기고 두 번째 호출이 첫 행을 반환 |
| 범위 경계 테스트 | 서로 다른 두 기록에 같은 토큰을 쓰면 각각 1건씩 저장 |

브라우저 검증(2026-07-28, 커밋 `bff9c353` 본문 `[코드]`): fetch를 가로채
서버가 커밋한 뒤 응답을 버리고 재시도했을 때, 재시도가 저장된 사진을
돌려주고 사진 수가 4장에서 5장이 됐다(6장이 아님).

## 5. 한계

- 작성 화면에는 재시도 채널이 없어 토큰을 적용하지 않았고, 그 사유를 코드
  주석에 남겼다. 작성 화면에 재시도가 생기면 같은 키를 실어야 한다.
- 락 테스트는 `select_for_update` 호출 여부를 스파이로 확인한다. 별도 커넥션
  두 개로 실제 경합을 재현한 테스트는 방문 완료 처리(RACE-02,
  `docs/BE/visit-completion-concurrency.md`)에만 있고 사진 업로드에는 없다.
- SQLite는 `select_for_update()`를 무시한다. 이 계약은 PostgreSQL에서만
  성립하며 로컬·CI 테스트는 PostgreSQL로 실행한다(`.github/workflows/ci.yml`
  `[코드]`).
- 이미지 파일 저장(S3 호환 저장소 호출)이 락 안에서 일어난다. 저장소 지연이
  길어지면 같은 기록의 다른 업로드가 그만큼 대기한다. 근본 해법은 트랙 32
  이연 항목이다(`docs/backlog.md` "DB 락·트랜잭션 검수(트랙 32)" 행).

## 6. 관련 문서

- 방문 완료 처리의 실제 경쟁 재현: `docs/BE/visit-completion-concurrency.md`
- 멱등 키를 쓰는 다른 생성 경로(`PersonalEntry`·`VisitRecord`·`CollectionItem`):
  `archive/services.py`의 각 `create_*` 함수 docstring
