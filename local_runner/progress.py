"""러너 진행 상태를 문장으로 조립해 터미널에 찍고 서버 heartbeat에 실어
보낸다. django·drafts를 임포트하지 않는다(격리 계약)."""
import logging
import time

logger = logging.getLogger(__name__)

# drafts.queries.DISCOVERY_PHASE_LABELS와 문자 그대로 같아야 한다(S14 가드).
PHASE_LABELS = {
    "idle": "대기",
    "exploring": "검색 중",
    "reading": "행사 확인 중",
    "submitting": "소스 후보 제출 중",
    "completing": "완료 보고 정리 중",
}

_PHASE_TEMPLATES = {
    "exploring": lambda query: f'검색어 "{query}" 검색 중',
    "reading": lambda index, total: f"{PHASE_LABELS['reading']} ({index}/{total})",
    "submitting": lambda index, total: f"{PHASE_LABELS['submitting']} ({index}/{total})",
    "completing": lambda: PHASE_LABELS["completing"],
    "idle": lambda: "",
}


def _build_detail(phase, fields):
    template = _PHASE_TEMPLATES.get(phase)
    if template is None:
        return ""
    if phase == "exploring":
        return template(fields.get("query"))
    if phase in ("reading", "submitting"):
        return template(fields.get("index"), fields.get("total"))
    return template()


class ProgressReporter:
    def __init__(self, client, clock=time.monotonic, provider="claude-code"):
        self._client = client
        self._clock = clock
        self._provider = provider
        self._phase = "idle"
        self._detail = ""
        self.run_id = None
        self.lease_token = None
        self.last_index = None
        self._last_sent_at = None

    def begin_run(self, run_id, lease_token):
        self.run_id = run_id
        self.lease_token = lease_token

    def end_run(self):
        self.run_id = None
        self.lease_token = None
        self.last_index = None

    def set(self, phase, **fields):
        detail = _build_detail(phase, fields)
        host = fields.get("host")
        changed = (phase, detail) != (self._phase, self._detail)
        self._phase = phase
        self._detail = detail
        if phase == "reading":
            self.last_index = fields.get("index")

        if not changed:
            return

        line = detail + (f" — {host}" if host else "")
        logger.info("%s", line)

        # 얕은 규칙: 한 번이라도 보냈으면 더 이상 즉시 전송하지 않는다
        # (다음 사이클 R03b가 시간 비교를 넣어 대체한다).
        if self._last_sent_at is not None:
            return
        self.heartbeat()
        self._last_sent_at = self._clock()

    def heartbeat(self):
        # detail이 빈 문자열이어도 그대로 보낸다 — idle 전이에서 서버
        # phase_detail을 실제로 비워야 대시보드 진행 행이 사라진다.
        self._client.send_heartbeat(
            self._provider,
            phase=self._phase,
            detail=self._detail,
            run_id=self.run_id,
        )

    @property
    def phase(self):
        return self._phase

    @property
    def detail(self):
        return self._detail
