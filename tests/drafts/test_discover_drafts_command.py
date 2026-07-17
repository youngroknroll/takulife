"""Tests for the discover_drafts management command (prompt_plan.md §2-1/2/5,
scratchpad pr3-test-design.md).

Mocks are patched at the command's import location
(drafts.management.commands.discover_drafts.{fetch_html, extract_candidate_urls,
create_draft_from_url, RobotsChecker}), never the underlying submodules —
except test 12b (real create_draft_from_url, drafts.services.fetch_html
stubbed) and test 15 (real RobotsChecker, drafts.robots.fetch_html patched),
which are deliberate exceptions documented inline.

DRAFT_DISCOVERY_ENABLED defaults to True for every test via the autouse
`_discovery_enabled` fixture below; tests that need the flag off set it back
to False explicitly (via the `settings` fixture) in the test body.
"""
import pytest
from django.core.management import CommandError, call_command

from drafts.discovery import DiscoveryParseError
from drafts.fetching import FetchError
from drafts.models import DraftSource, EventDraft
from drafts.robots import ROBOTS_DISALLOWED, ROBOTS_FETCH_FAILED, RobotsCheckResult
from drafts.services import DraftCreationDuplicateError, DraftCreationEmptyExtractionError, DraftCreationFetchError


pytestmark = [pytest.mark.django_db, pytest.mark.domain]


@pytest.fixture(autouse=True)
def _discovery_enabled(settings):
    settings.DRAFT_DISCOVERY_ENABLED = True


@pytest.fixture(autouse=True)
def _no_inter_request_delay(monkeypatch):
    # The command's per-source etiquette pause (INTER_REQUEST_DELAY_SECONDS)
    # is not itself under test anywhere in this file (out of scope per
    # pr3-test-design.md) — multi-source tests would otherwise pay a real
    # 1s sleep per extra source.
    monkeypatch.setattr("drafts.management.commands.discover_drafts.time.sleep", lambda seconds: None)


class _FakeRobotsChecker:
    """Stand-in for drafts.robots.RobotsChecker, patched at the command's
    import location (`RobotsChecker`, the class itself, replaced by a
    zero-arg factory returning one shared instance) — every test that cares
    about robots outcomes configures this instead of hitting the network.
    """

    def __init__(self, outcomes=None, default=RobotsCheckResult(True, None), crawl_delay_value=None):
        self.outcomes = outcomes or {}
        self.default = default
        self.calls = []
        self.crawl_delay_value = crawl_delay_value
        self.crawl_delay_calls = []

    def check(self, url):
        self.calls.append(url)
        return self.outcomes.get(url, self.default)

    def crawl_delay(self, url):
        self.crawl_delay_calls.append(url)
        return self.crawl_delay_value


def _patch_robots_checker(monkeypatch, checker):
    monkeypatch.setattr(
        "drafts.management.commands.discover_drafts.RobotsChecker", lambda: checker
    )


class TestFlagGating:
    def test_DRAFT_DISCOVERY_ENABLED가_꺼져_있으면_실행을_거부하고_설정명을_안내한다(self, settings, monkeypatch, capsys, fail_if_called):
        settings.DRAFT_DISCOVERY_ENABLED = False
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.fetch_html", fail_if_called
        )
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.extract_candidate_urls",
            fail_if_called,
        )
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.create_draft_from_url",
            fail_if_called,
        )

        call_command("discover_drafts")

        # The message must name the actual setting an operator needs to
        # flip, not just say "disabled" in the abstract.
        output = capsys.readouterr().out
        assert "DRAFT_DISCOVERY_ENABLED" in output

    def test_활성_소스가_없으면_안내_문구를_출력하고_정상_종료한다(self, monkeypatch, capsys, fail_if_called):
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.fetch_html", fail_if_called
        )
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.extract_candidate_urls",
            fail_if_called,
        )
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.create_draft_from_url",
            fail_if_called,
        )

        call_command("discover_drafts")

        # A bare "0" would also match an unrelated count in the summary —
        # the message must specifically say there is no active source.
        output = capsys.readouterr().out
        assert "활성 소스가 없습니다" in output

    def test_비활성_소스는_처리되지_않는다(self, monkeypatch, make_source, fail_if_called):
        make_source(enabled=False)
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.fetch_html", fail_if_called
        )
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.extract_candidate_urls",
            fail_if_called,
        )
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.create_draft_from_url",
            fail_if_called,
        )

        call_command("discover_drafts")


class TestListingLevel:
    @pytest.mark.parametrize(
        "reason", [ROBOTS_DISALLOWED, ROBOTS_FETCH_FAILED], ids=["robots_불허", "robots_페치_실패"]
    )
    def test_리스팅_페이지가_robots에_의해_차단되면_소스를_건너뛰고_사유를_기록한다(self, monkeypatch, reason, make_source, fail_if_called):
        source = make_source()
        checker = _FakeRobotsChecker(outcomes={source.url: RobotsCheckResult(False, reason)})
        _patch_robots_checker(monkeypatch, checker)
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.fetch_html", fail_if_called
        )
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.extract_candidate_urls",
            fail_if_called,
        )
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.create_draft_from_url",
            fail_if_called,
        )

        call_command("discover_drafts")

        source.refresh_from_db()
        assert reason in source.last_error
        assert source.last_checked_at is not None

    def test_후보가_없으면_이전_에러를_지우고_0건을_보고한다(self, monkeypatch, capsys, make_source, fail_if_called):
        source = make_source(last_error="이전 실행에서 남은 에러")
        _patch_robots_checker(monkeypatch, _FakeRobotsChecker())
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.fetch_html",
            lambda url, **kwargs: "<xml></xml>",
        )
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.extract_candidate_urls",
            lambda *args, **kwargs: [],
        )
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.create_draft_from_url", fail_if_called
        )

        call_command("discover_drafts")

        source.refresh_from_db()
        assert source.last_error == ""
        output = capsys.readouterr().out
        assert "0" in output

    @pytest.mark.parametrize("failure_mode", ["fetch", "parse"], ids=["페치_실패", "파싱_실패"])
    def test_소스_레벨_실패는_다른_소스에_전파되지_않고_0이_아닌_종료코드를_유발한다(self, monkeypatch, failure_mode, make_draft, make_source):
        source_a = make_source(name="A", url="https://a.example.com/feed.xml")
        source_b = make_source(name="B", url="https://b.example.com/feed.xml")
        _patch_robots_checker(monkeypatch, _FakeRobotsChecker())

        def fake_fetch(url, **kwargs):
            if url == source_a.url and failure_mode == "fetch":
                raise FetchError()
            return "<xml></xml>"

        def fake_extract(source_type, content, base_url, selector=""):
            if base_url == source_a.url:
                if failure_mode == "parse":
                    raise DiscoveryParseError("malformed xml")
                return []
            return ["https://b.example.com/event-1"]

        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.fetch_html", fake_fetch
        )
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.extract_candidate_urls", fake_extract
        )
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.create_draft_from_url",
            lambda source_url, source_name="": make_draft(source_url, source_name=source_name),
        )

        with pytest.raises(CommandError):
            call_command("discover_drafts")

        source_a.refresh_from_db()
        assert source_a.last_error != ""
        assert EventDraft.objects.filter(source_url="https://b.example.com/event-1").exists()

    def test_손상된_source_type을_가진_소스는_자신에게만_실패가_격리된다(self, monkeypatch, make_draft, make_source):
        """A source_type outside DraftSource.SourceType.choices can still
        reach the DB — Model.objects.create() does not validate choices, so
        a stale/typo'd source_type is a real (if rare) production state, not
        just a test artifact. It must fail only that source, not crash the
        whole run before source B is ever processed."""
        source_a = make_source(
            name="A", url="https://a.example.com/feed.xml", source_type="atom"
        )
        source_b = make_source(name="B", url="https://b.example.com/feed.xml")

        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.fetch_html",
            lambda url, **kwargs: "<xml></xml>",
        )
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.extract_candidate_urls",
            lambda *args, **kwargs: ["https://b.example.com/event-1"],
        )
        _patch_robots_checker(monkeypatch, _FakeRobotsChecker())
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.create_draft_from_url",
            lambda source_url, source_name="": make_draft(source_url, source_name=source_name),
        )

        with pytest.raises(CommandError):
            call_command("discover_drafts")

        source_a.refresh_from_db()
        assert source_a.last_error != ""
        assert EventDraft.objects.filter(source_url="https://b.example.com/event-1").exists()


def _install_listing(monkeypatch, candidate_urls):
    monkeypatch.setattr(
        "drafts.management.commands.discover_drafts.fetch_html", lambda url, **kwargs: "<xml></xml>"
    )
    monkeypatch.setattr(
        "drafts.management.commands.discover_drafts.extract_candidate_urls",
        lambda *args, **kwargs: list(candidate_urls),
    )


class TestCandidateLevel:
    def test_신규_후보는_소스_이름과_함께_드래프트로_생성된다(self, monkeypatch, make_source):
        source = make_source()
        _install_listing(monkeypatch, ["https://target.example.com/event-1"])
        _patch_robots_checker(monkeypatch, _FakeRobotsChecker())

        calls = []

        def spy(source_url, source_name=""):
            calls.append((source_url, source_name))

        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.create_draft_from_url", spy
        )

        call_command("discover_drafts")

        assert calls == [("https://target.example.com/event-1", source.name)]

    def test_이미_존재하는_URL은_후보_robots_점검_전에_중복_제거된다(self, monkeypatch, make_draft, make_source, fail_if_called):
        source = make_source()
        candidate_url = "https://target.example.com/event-1"
        make_draft(candidate_url, review_status=EventDraft.ReviewStatus.REJECTED)
        _install_listing(monkeypatch, [candidate_url])
        checker = _FakeRobotsChecker()
        _patch_robots_checker(monkeypatch, checker)
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.create_draft_from_url", fail_if_called
        )

        call_command("discover_drafts")

        # The listing URL itself is robots-checked, but the deduped
        # candidate must never reach a robots check at all — dedup runs
        # first.
        assert candidate_url not in checker.calls

    @pytest.mark.parametrize(
        "reason, report_substring",
        [
            (ROBOTS_DISALLOWED, "robots 불허 1건"),
            (ROBOTS_FETCH_FAILED, "robots 페치 실패 1건"),
        ],
        ids=["robots_불허", "robots_페치_실패"],
    )
    def test_후보_URL이_robots에_의해_차단되면_실행_실패_없이_사유별로_건너뛴다(self, monkeypatch, reason, report_substring, capsys, make_source, fail_if_called):
        source = make_source()
        candidate_url = "https://target.example.com/event-1"
        _install_listing(monkeypatch, [candidate_url])
        checker = _FakeRobotsChecker(outcomes={candidate_url: RobotsCheckResult(False, reason)})
        _patch_robots_checker(monkeypatch, checker)
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.create_draft_from_url", fail_if_called
        )

        call_command("discover_drafts")

        # Confirms the skip lands in its own reason bucket in the summary,
        # not merely that the run didn't raise.
        output = capsys.readouterr().out
        assert report_substring in output

    def test_중복_생성_오류는_실행_실패로_이어지지_않고_건너뛴다(self, monkeypatch, make_source):
        source = make_source()
        _install_listing(monkeypatch, ["https://target.example.com/event-1"])
        _patch_robots_checker(monkeypatch, _FakeRobotsChecker())

        def raise_duplicate(source_url, source_name=""):
            raise DraftCreationDuplicateError()

        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.create_draft_from_url", raise_duplicate
        )

        call_command("discover_drafts")

    def test_빈_추출_오류도_실행_실패로_이어지지_않고_건너뛴다(self, monkeypatch, make_source):
        source = make_source()
        _install_listing(monkeypatch, ["https://target.example.com/event-1"])
        _patch_robots_checker(monkeypatch, _FakeRobotsChecker())

        def raise_empty(source_url, source_name=""):
            raise DraftCreationEmptyExtractionError()

        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.create_draft_from_url", raise_empty
        )

        call_command("discover_drafts")

    def test_후보_생성_실패는_다른_후보에_전파되지_않지만_0이_아닌_종료코드를_유발하고_소스_에러는_바꾸지_않는다(self, monkeypatch, capsys, make_draft, make_source):
        source = make_source()
        failing_url = "https://target.example.com/event-1"
        succeeding_url = "https://target.example.com/event-2"
        _install_listing(monkeypatch, [failing_url, succeeding_url])
        _patch_robots_checker(monkeypatch, _FakeRobotsChecker())

        def flaky_create(source_url, source_name=""):
            if source_url == failing_url:
                raise DraftCreationFetchError()
            return make_draft(source_url, source_name=source_name)

        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.create_draft_from_url", flaky_create
        )

        with pytest.raises(CommandError):
            call_command("discover_drafts")

        assert EventDraft.objects.filter(source_url=succeeding_url).exists()
        # A candidate-level failure must never touch the source's own
        # last_error — that field reflects only the listing-level outcome
        # (PO decision 3, module docstring).
        source.refresh_from_db()
        assert source.last_error == ""
        # The failure must be diagnosable (URL + exception class) without
        # leaking the exception's message body, which could carry secrets.
        stderr_output = capsys.readouterr().err
        assert failing_url in stderr_output
        assert "DraftCreationFetchError" in stderr_output

    def test_같은_실행에서_서로_다른_소스가_같은_URL을_후보로_내면_한_건만_생성되고_나머지는_건너뛴다(self, monkeypatch, make_source):
        """Sociable exception (pr3-test-design.md 12b): real
        create_draft_from_url, only drafts.services.fetch_html stubbed — this
        is the one test that exercises the actual IntegrityError ->
        DraftCreationDuplicateError path inside create_draft_from_url, which
        a same-source dedup-only test could never reach (see module
        docstring's phase-2 rationale)."""
        shared_url = "https://target.example.com/event-1"
        source_a = make_source(name="A", url="https://a.example.com/feed.xml")
        source_b = make_source(name="B", url="https://b.example.com/feed.xml")

        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.fetch_html", lambda url, **kwargs: "<xml></xml>"
        )
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.extract_candidate_urls",
            lambda *args, **kwargs: [shared_url],
        )
        _patch_robots_checker(monkeypatch, _FakeRobotsChecker())
        monkeypatch.setattr(
            "drafts.services.fetch_html",
            lambda url: "<html><title>Event</title><body>본문 내용입니다</body></html>",
        )

        call_command("discover_drafts")

        assert EventDraft.objects.filter(source_url=shared_url).count() == 1


class TestCaps:
    def test_생성_상한에_도달하면_이후_후보_생성을_멈추고_보류_건수를_보고한다(self, monkeypatch, settings, capsys, make_draft, make_source):
        settings.DRAFT_DISCOVERY_MAX_PER_RUN = 1
        make_source()
        url1 = "https://target.example.com/event-1"
        url2 = "https://target.example.com/event-2"
        _install_listing(monkeypatch, [url1, url2])
        checker = _FakeRobotsChecker()
        _patch_robots_checker(monkeypatch, checker)
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.create_draft_from_url",
            lambda source_url, source_name="": make_draft(source_url, source_name=source_name),
        )

        call_command("discover_drafts")

        assert EventDraft.objects.filter(source_url=url1).exists()
        assert not EventDraft.objects.filter(source_url=url2).exists()
        # Etiquette: once the creation cap is reached, the held-back
        # candidate must not even get a robots check.
        assert url2 not in checker.calls
        # A bare "1" would also match "생성 1건" or an unrelated count — the
        # message must specifically attribute the held-back count.
        output = capsys.readouterr().out
        assert "1건 보류" in output

    def test_중복_제거된_후보는_소스별_페치_상한을_소비하지_않는다(self, monkeypatch, settings, make_draft, make_source):
        settings.DRAFT_DISCOVERY_MAX_FETCHES_PER_SOURCE = 1
        make_source()
        dup_url = "https://target.example.com/existing"
        new_url1 = "https://target.example.com/event-1"
        new_url2 = "https://target.example.com/event-2"
        make_draft(dup_url, review_status=EventDraft.ReviewStatus.REJECTED)
        _install_listing(monkeypatch, [dup_url, new_url1, new_url2])
        checker = _FakeRobotsChecker()
        _patch_robots_checker(monkeypatch, checker)
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.create_draft_from_url",
            lambda source_url, source_name="": make_draft(source_url, source_name=source_name),
        )

        call_command("discover_drafts")

        # The dup candidate consumed no fetch budget, so new_url1 (the first
        # genuinely new candidate) still gets the source's one fetch slot;
        # new_url2 is held back by the now-exhausted per-source budget even
        # though the creation cap (default 10) is nowhere near reached.
        assert EventDraft.objects.filter(source_url=new_url1).exists()
        assert not EventDraft.objects.filter(source_url=new_url2).exists()
        assert new_url2 not in checker.calls

    def test_생성_상한은_소스별이_아니라_실행_전체에서_공유된다(self, monkeypatch, settings, make_draft, make_source):
        """If DRAFT_DISCOVERY_MAX_PER_RUN were (incorrectly) applied
        per-source instead of once for the whole run, both sources' single
        candidate would be created here — this pins the total-across-the-run
        semantics (prompt_plan.md §2-5)."""
        settings.DRAFT_DISCOVERY_MAX_PER_RUN = 1
        source_a = make_source(name="A", url="https://a.example.com/feed.xml")
        source_b = make_source(name="B", url="https://b.example.com/feed.xml")
        url_a = "https://target.example.com/event-a"
        url_b = "https://target.example.com/event-b"

        def fake_extract(source_type, content, base_url, selector=""):
            return [url_a] if base_url == source_a.url else [url_b]

        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.fetch_html",
            lambda url, **kwargs: "<xml></xml>",
        )
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.extract_candidate_urls", fake_extract
        )
        _patch_robots_checker(monkeypatch, _FakeRobotsChecker())
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.create_draft_from_url",
            lambda source_url, source_name="": make_draft(source_url, source_name=source_name),
        )

        call_command("discover_drafts")

        assert EventDraft.objects.filter(source_url=url_a).exists()
        assert not EventDraft.objects.filter(source_url=url_b).exists()

    def test_소스별_페치_상한은_다른_소스의_예산을_굶기지_않는다(self, monkeypatch, settings, make_draft, make_source):
        """If the per-source fetch budget were (incorrectly) shared globally
        instead of tracked per source, source B's candidate would also be
        held back once source A exhausts the shared budget — this pins the
        per-source independence (prompt_plan.md §2-5)."""
        settings.DRAFT_DISCOVERY_MAX_FETCHES_PER_SOURCE = 1
        source_a = make_source(name="A", url="https://a.example.com/feed.xml")
        source_b = make_source(name="B", url="https://b.example.com/feed.xml")
        url_a1 = "https://a-target.example.com/event-1"
        url_a2 = "https://a-target.example.com/event-2"
        url_b1 = "https://b-target.example.com/event-1"

        def fake_extract(source_type, content, base_url, selector=""):
            return [url_a1, url_a2] if base_url == source_a.url else [url_b1]

        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.fetch_html",
            lambda url, **kwargs: "<xml></xml>",
        )
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.extract_candidate_urls", fake_extract
        )
        _patch_robots_checker(monkeypatch, _FakeRobotsChecker())

        def fake_create(source_url, source_name=""):
            if source_url in (url_a1, url_a2):
                # Both of source A's candidates consume A's one fetch slot
                # via an empty-extraction skip, exhausting it before A's
                # second candidate can be attempted.
                raise DraftCreationEmptyExtractionError()
            return make_draft(source_url, source_name=source_name)

        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.create_draft_from_url", fake_create
        )

        call_command("discover_drafts")

        assert not EventDraft.objects.filter(source_url=url_a2).exists()
        assert EventDraft.objects.filter(source_url=url_b1).exists()


class TestCandidatePacing:
    def test_페치_예산을_소비한_후보마다_한_번씩_일시정지한다(self, monkeypatch, make_draft, make_source):
        """Etiquette pacing after every candidate that actually consumed
        network fetch budget (a robots check, at minimum) — behavior only;
        exact seconds are out of scope (pr3-test-design.md), so this checks
        that the pause happens the right number of times and consults the
        checker's Crawl-delay, not any particular duration."""
        make_source()
        url1 = "https://target.example.com/event-1"
        url2 = "https://target.example.com/event-2"
        _install_listing(monkeypatch, [url1, url2])
        checker = _FakeRobotsChecker()
        _patch_robots_checker(monkeypatch, checker)
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.create_draft_from_url",
            lambda source_url, source_name="": make_draft(source_url, source_name=source_name),
        )
        sleep_calls = []
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.time.sleep",
            lambda seconds: sleep_calls.append(seconds),
        )

        call_command("discover_drafts")

        assert len(sleep_calls) == 2
        assert checker.crawl_delay_calls == [url1, url2]

    def test_보류되거나_중복_제거된_후보는_일시정지를_유발하지_않는다(self, monkeypatch, settings, make_draft, make_source):
        settings.DRAFT_DISCOVERY_MAX_PER_RUN = 1
        make_source()
        url1 = "https://target.example.com/event-1"
        url2 = "https://target.example.com/event-2"
        _install_listing(monkeypatch, [url1, url2])
        checker = _FakeRobotsChecker()
        _patch_robots_checker(monkeypatch, checker)
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.create_draft_from_url",
            lambda source_url, source_name="": make_draft(source_url, source_name=source_name),
        )
        sleep_calls = []
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.time.sleep",
            lambda seconds: sleep_calls.append(seconds),
        )

        call_command("discover_drafts")

        # url2 is held back by the creation cap before it ever reaches a
        # robots check, so it never consumes fetch budget and must not pace.
        assert len(sleep_calls) == 1
        assert checker.crawl_delay_calls == [url1]


class TestRobotsCache:
    def test_robots_txt는_전체_실행에서_호스트당_최대_한_번만_페치된다(self, monkeypatch, make_draft, make_source):
        """Exception to the module's general mocking rule: uses the real
        RobotsChecker (not patched at the command import location), with
        only drafts.robots.fetch_html patched to count calls — this is what
        actually proves the run shares one RobotsChecker cache across
        sources and candidates on the same host, not merely that a fake
        object recorded calls (instance-count assertions are out of scope,
        pr3-test-design.md — this checks behavior, not implementation)."""
        source_a = make_source(name="A", url="https://shared.example.com/feedA.xml")
        make_source(name="B", url="https://shared.example.com/feedB.xml")

        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.fetch_html",
            lambda url, **kwargs: "<xml></xml>",
        )

        def fake_extract(source_type, content, base_url, selector=""):
            if base_url == source_a.url:
                return ["https://shared.example.com/event-1"]
            return ["https://shared.example.com/event-2"]

        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.extract_candidate_urls", fake_extract
        )
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.create_draft_from_url",
            lambda source_url, source_name="": make_draft(source_url, source_name=source_name),
        )

        robots_fetch_calls = []

        def counting_fetch_html(url, **kwargs):
            robots_fetch_calls.append(url)
            return "User-agent: *\nAllow: /\n"

        monkeypatch.setattr("drafts.robots.fetch_html", counting_fetch_html)

        call_command("discover_drafts")

        assert len(robots_fetch_calls) == 1


class TestListingContentType:
    @pytest.mark.parametrize(
        "source_type",
        [DraftSource.SourceType.RSS, DraftSource.SourceType.SITEMAP],
        ids=["RSS", "사이트맵"],
    )
    def test_RSS와_사이트맵_리스팅_페치는_XML_content_type을_명시적으로_허용한다(self, monkeypatch, source_type, make_source):
        make_source(source_type=source_type)
        captured = {}

        def capture_fetch(url, **kwargs):
            captured["allowed_content_types"] = kwargs.get("allowed_content_types")
            return "<xml></xml>"

        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.fetch_html", capture_fetch
        )
        monkeypatch.setattr(
            "drafts.management.commands.discover_drafts.extract_candidate_urls",
            lambda *args, **kwargs: [],
        )
        _patch_robots_checker(monkeypatch, _FakeRobotsChecker())

        call_command("discover_drafts")

        allowed_content_types = captured["allowed_content_types"]
        assert allowed_content_types is not None
        assert "text/html" not in allowed_content_types
