/**
 * 보관함 목록의 디바운스 실시간 검색. JS 없이도 기존 GET 폼 검색은 그대로
 * 동작하며, 이 스크립트는 그 위에 얹혀 결과 조각(?partial=1)만 받아
 * #archive-results에 갈아끼운다.
 * 입력마다 250ms 디바운스 후 요청하고, AbortController로 이전 요청을
 * 취소해 느린 응답이 최신 결과를 덮어쓰는 경쟁을 없앤다.
 * history.pushState로 공유 가능한 URL을 유지하고 뒤로/앞으로가기는
 * popstate로 입력과 결과를 다시 맞춘다. 세션 만료로 로그인 페이지로
 * 리다이렉트되면 그 응답을 감지해 실제로 이동한다.
 * 갈아끼우는 HTML은 서버가 이스케이프해 렌더링한 것이라 검색어를 직접
 * 마크업에 끼워넣지 않는다. 교체 후에는 `archive:listswapped` 이벤트를
 * 보내 status.js 등이 새로 삽입된 컨트롤을 다시 연결하게 한다.
 * 정렬 메뉴는 #archive-results 밖에 있어 교체되지 않으므로, 매 교체 후
 * 그 링크들의 `q` 파라미터만 직접 갱신해 검색어가 사라지지 않게 한다.
 */
(function () {
  "use strict";

  var DEBOUNCE_MS = 250;

  var form = document.querySelector(".archive-search");
  var results = document.getElementById("archive-results");
  if (!form || !results) { return; }

  var input = form.querySelector('input[name="q"]');
  if (!input) { return; }
  var clearLink = form.querySelector(".archive-search-clear");

  var path = window.location.pathname;
  var controller = null;
  var timer = null;

  // 현재 URL에서 쿼리 파라미터를 만들어 활성 필터를 유지한다. 새 검색어는
  // 페이지를 1로 되돌린다.
  function buildParams(term) {
    var params = new URLSearchParams(window.location.search);
    if (term) {
      params.set("q", term);
    } else {
      params.delete("q");
    }
    params.delete("page");
    params.delete("partial");
    return params;
  }

  function userUrl(params) {
    var qs = params.toString();
    return qs ? path + "?" + qs : path;
  }

  // "지우기" 링크는 서버가 전체 페이지 로드 시에만 렌더링하므로, 실시간
  // 검색이 결과 조각만 바꾸는 동안에는 여기서 직접 보이기/숨기기를 맞춘다.
  function syncClearLink(term) {
    if (!clearLink) { return; }
    clearLink.hidden = !term;
  }

  function setLoading(on) {
    results.classList.toggle("is-loading", on);
  }

  // 정렬 메뉴는 #archive-results 밖에 있어 처음 로드될 때 한 번만
  // 렌더링된다. 그대로 두면 검색어를 새로 입력했을 때 링크에 박힌 `q`가
  // 낡아져, 정렬을 누르면 방금 검색한 내용이 조용히 사라진다. 그래서
  // `q`만 갱신하고 `sort` 등 나머지 값은 그대로 둔다. 정렬 메뉴가 없는
  // 페이지에서는 아무 동작도 하지 않는다.
  var sortMenu = document.querySelector("[data-sort-menu]");
  var sortLinks = sortMenu ? sortMenu.querySelectorAll("a[href]") : [];

  function syncSortLinks(term) {
    for (var i = 0; i < sortLinks.length; i++) {
      var link = sortLinks[i];
      var url = new URL(link.getAttribute("href"), window.location.href);
      if (term) {
        url.searchParams.set("q", term);
      } else {
        url.searchParams.delete("q");
      }
      link.setAttribute("href", url.pathname + url.search);
    }
  }

  // 새 시도를 시작하기 전에 먼저 지워, 이전 실패 메시지가 성공한 검색
  // 결과 위에 계속 남아 있지 않게 한다.
  var searchError = document.getElementById("archive-search-error");

  function setSearchError(message) {
    if (searchError) { searchError.textContent = message; }
  }

  // innerHTML 교체 자체는 접근성 이벤트를 일으키지 않으므로, 스크린리더에게
  // 검색 결과를 알리는 유일한 수단이 이 영역이다.
  var searchStatus = document.getElementById("archive-search-status");

  // 방금 교체된 조각에서 서버가 렌더링한 결과 개수를 읽어 알린다. 검색어가
  // 비었으면 조용히 지우고, 마커를 못 찾으면 깨진 상태를 알리는 대신 그냥 둔다.
  function announceResultCount(term) {
    if (!searchStatus) { return; }
    if (!term) {
      searchStatus.textContent = "";
      return;
    }
    var marker = results.querySelector("[data-result-count]");
    if (!marker) { return; }
    var count = parseInt(marker.getAttribute("data-result-count"), 10);
    if (isNaN(count)) { return; }
    var message = count > 0 ? count + "건 검색됨" : "검색 결과가 없습니다";

    // 같은 메시지를 다시 알릴 때도 스크린리더가 변화를 감지하도록 일단 비운다.
    searchStatus.textContent = "";
    requestAnimationFrame(function () {
      searchStatus.textContent = message;
    });
  }

  // `term`에 대한 결과 조각을 받아 교체한다. `push`는 새 히스토리 항목을
  // 만들지 여부(popstate 재실행 시에는 false).
  function runSearch(term, push) {
    var params = buildParams(term);

    if (controller) { controller.abort(); }
    controller = new AbortController();

    var fetchParams = new URLSearchParams(params);
    fetchParams.set("partial", "1");

    setLoading(true);
    setSearchError("");

    fetch(path + "?" + fetchParams.toString(), {
      credentials: "same-origin",
      headers: { "X-Requested-With": "fetch" },
      signal: controller.signal,
    })
      .then(function (response) {
        // 세션 만료 등으로 조각이 아닌 다른 페이지로 리다이렉트되면 그대로 따라간다.
        if (response.redirected) {
          window.location.href = response.url;
          return null;
        }
        if (!response.ok) {
          setSearchError("검색 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.");
          return null;
        }
        return response.text();
      })
      .then(function (html) {
        // 취소가 아닌 모든 결과(리다이렉트나 실패 응답 포함)에서 로딩 표시를
        // 지워, 서버 오류 후에도 흐림 상태가 그대로 남지 않게 한다.
        setLoading(false);
        if (html === null) { return; }
        results.innerHTML = html;
        announceResultCount(term);
        syncSortLinks(term);
        if (push) {
          window.history.pushState({ q: term }, "", userUrl(params));
        }
        // 교체된 컨트롤(상태/찜/삭제/제보/캐러셀 등)을 다시 연결한다.
        document.dispatchEvent(new CustomEvent("archive:listswapped"));
      })
      .catch(function (error) {
        // 빠르게 입력할 때 취소되는 요청은 정상이므로 무시한다.
        if (error && error.name === "AbortError") { return; }
        // 네트워크 실패 시 로딩 상태만 해제하고 기존 결과는 그대로 둔다.
        setLoading(false);
        setSearchError("검색 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.");
      });
  }

  input.addEventListener("input", function (evt) {
    // 한글 등 조합 입력 중에는 글자가 완성되기 전에도 input 이벤트가
    // 계속 발생한다. 그 중간 상태로 검색하면 요청이 낭비되고 화면이
    // 깜빡인다. 조합이 끝나면 브라우저가 isComposing:false인 input을
    // 한 번 더 보내주므로 이 검사만으로 충분하다.
    if (evt.isComposing) { return; }
    if (timer) { window.clearTimeout(timer); }
    var term = input.value.trim();
    syncClearLink(term);
    timer = window.setTimeout(function () {
      runSearch(term, true);
    }, DEBOUNCE_MS);
  });

  // Enter(폼 제출)는 전체 새로고침 대신 즉시 검색한다.
  form.addEventListener("submit", function (evt) {
    evt.preventDefault();
    if (timer) { window.clearTimeout(timer); }
    var term = input.value.trim();
    syncClearLink(term);
    runSearch(term, true);
  });

  // 뒤로/앞으로가기: URL에서 입력값을 다시 맞추고 새 히스토리 없이 검색을 재실행한다.
  window.addEventListener("popstate", function () {
    var term = new URLSearchParams(window.location.search).get("q") || "";
    input.value = term;
    syncClearLink(term);
    runSearch(term, false);
  });
})();
