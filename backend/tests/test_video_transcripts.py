from io import BytesIO

import pytest
import yt_dlp

import app.materials as materials
from app.materials import MaterialError, fetch_video_transcript

VIDEO_URL = "https://www.youtube.com/watch?v=test"
VTT = b"WEBVTT\n\n00:00:01.000 --> 00:00:04.000\nBernoulli trials are independent.\n"


def track(language, *, translated=False):
    url = f"https://www.youtube.com/api/timedtext?lang={language}"
    if translated:
        url += "&tlang=zh-Hans"
    return {"ext": "vtt", "url": url}


@pytest.fixture
def video_source(monkeypatch):
    class Downloader:
        info = {"title": "Bernoulli Process", "webpage_url": VIDEO_URL}
        replies = {}
        requests = []
        extractions = []
        options = None

        def __init__(self, options):
            self.options = options
            type(self).options = options

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def extract_info(self, url, download):
            self.extractions.append((url, download))
            if isinstance(self.info, Exception):
                raise self.info
            return self.info

        def urlopen(self, request):
            self.requests.append(request.url)
            reply = self.replies.get(request.url, VTT)
            if isinstance(reply, Exception):
                raise reply
            return BytesIO(reply)

    monkeypatch.setattr(yt_dlp, "YoutubeDL", Downloader)
    monkeypatch.setattr(materials, "validate_public_url", lambda url: None)
    monkeypatch.setattr(materials, "build_subprocess_environment", lambda: {})
    monkeypatch.setattr(materials.time, "sleep", lambda seconds: pytest.fail("unexpected retry"))
    return Downloader


def test_english_provided_subtitles_precede_rate_limited_translation(video_source):
    english, chinese = track("en"), track("ar", translated=True)
    video_source.info.update(subtitles={"en": [english]}, automatic_captions={"zh-Hans": [chinese]})
    video_source.replies[chinese["url"]] = RuntimeError("HTTP Error 429: Too Many Requests")
    url, title, content, chunks = fetch_video_transcript(VIDEO_URL)
    assert (url, title, content) == (VIDEO_URL, "Bernoulli Process", VTT)
    assert chunks == [("00:01-00:04", None, "Bernoulli trials are independent.")]
    assert video_source.requests == [english["url"]]
    assert video_source.extractions == [(VIDEO_URL, False)]


@pytest.mark.parametrize("failure", [RuntimeError("HTTP Error 429"), b"WEBVTT\n\n"])
def test_unusable_chinese_falls_back_to_english(video_source, failure):
    chinese, english = track("zh-Hans"), track("en")
    video_source.info["subtitles"] = {"en": [english], "zh-Hans": [chinese]}
    video_source.replies[chinese["url"]] = failure
    assert fetch_video_transcript(VIDEO_URL)[2] == VTT
    assert video_source.requests == [chinese["url"], english["url"]]


def test_native_automatic_subtitles_precede_translations(video_source):
    native, translated = track("en"), track("en", translated=True)
    video_source.info["automatic_captions"] = {
        "zh-Hans": [translated],
        "en-orig": [native],
        "en": [native],
    }
    assert fetch_video_transcript(VIDEO_URL)[2] == VTT
    assert video_source.requests == [native["url"]]


def test_provided_chinese_remains_preferred(video_source):
    chinese, english = track("zh-Hans"), track("en-US")
    video_source.info["subtitles"] = {"en-US": [english], "zh-Hans": [chinese]}
    assert fetch_video_transcript(VIDEO_URL)[2] == VTT
    assert video_source.requests == [chinese["url"]]


def test_translation_only_video_still_supported(video_source):
    translated = track("ar", translated=True)
    video_source.info["automatic_captions"] = {"zh-Hans": [translated]}
    assert fetch_video_transcript(VIDEO_URL)[2] == VTT
    assert video_source.requests == [translated["url"]]


def test_repeated_rate_limits_stop_without_full_restart(video_source):
    tracks = {lang: [track(lang)] for lang in ("zh-Hans", "zh-Hant", "zh", "en")}
    video_source.info["subtitles"] = tracks
    video_source.replies = {
        items[0]["url"]: RuntimeError("HTTP Error 429") for items in tracks.values()
    }
    with pytest.raises(MaterialError, match="429.*稍后"):
        fetch_video_transcript(VIDEO_URL)
    assert len(video_source.requests) == 2
    assert video_source.extractions == [(VIDEO_URL, False)]


def test_metadata_rate_limit_is_not_retried(video_source):
    video_source.info = RuntimeError("HTTP Error 429")
    with pytest.raises(MaterialError, match="429.*稍后"):
        fetch_video_transcript(VIDEO_URL)
    assert video_source.extractions == [(VIDEO_URL, False)]
    assert video_source.requests == []


def test_no_supported_subtitles(video_source):
    video_source.info["subtitles"] = {"fr": [track("fr")]}
    with pytest.raises(MaterialError, match="没有可用的中文或英文字幕"):
        fetch_video_transcript(VIDEO_URL)
    assert video_source.requests == []


def test_empty_subtitles_are_not_success(video_source):
    english = track("en")
    video_source.info["subtitles"] = {"en": [english]}
    video_source.replies[english["url"]] = b"WEBVTT\n\n"
    with pytest.raises(MaterialError, match="没有可用字幕"):
        fetch_video_transcript(VIDEO_URL)


def test_duplicate_urls_only_requested_once(video_source):
    english = track("en")
    video_source.info["automatic_captions"] = {"en-orig": [english], "en": [english]}
    video_source.replies[english["url"]] = b"WEBVTT\n\n"
    with pytest.raises(MaterialError):
        fetch_video_transcript(VIDEO_URL)
    assert video_source.requests == [english["url"]]


def test_metadata_transient_errors_keep_bounded_retry(video_source, monkeypatch):
    calls, sleeps = [], []

    def extract(self, url, download):
        calls.append(url)
        if len(calls) < 3:
            raise RuntimeError("HTTP Error 503")
        return {"subtitles": {"en": [track("en")]}}

    monkeypatch.setattr(video_source, "extract_info", extract)
    monkeypatch.setattr(materials.time, "sleep", sleeps.append)
    assert fetch_video_transcript(VIDEO_URL)[2] == VTT
    assert len(calls) == 3
    assert sleeps == [1, 2]


def test_large_subtitle_rejected(video_source, monkeypatch):
    monkeypatch.setattr(materials, "MAX_URL_BYTES", 10)
    video_source.info["subtitles"] = {"en": [track("en")]}
    with pytest.raises(MaterialError, match="超过大小限制"):
        fetch_video_transcript(VIDEO_URL)


def test_track_fallback_has_request_limit(video_source):
    tracks = {f"en-{i}": [track(f"en-{i}")] for i in range(8)}
    video_source.info["subtitles"] = tracks
    video_source.replies = {items[0]["url"]: b"WEBVTT\n\n" for items in tracks.values()}
    with pytest.raises(MaterialError, match="没有可用字幕"):
        fetch_video_transcript(VIDEO_URL)
    assert len(video_source.requests) == 4


def test_current_proxy_and_subtitle_headers_are_preserved(video_source, monkeypatch):
    monkeypatch.setattr(
        materials, "build_subprocess_environment", lambda: {"HTTPS_PROXY": "http://proxy.test"}
    )
    video_source.info.update(
        subtitles={"en": [track("en")]}, http_headers={"User-Agent": "subtitle-test"}
    )

    def urlopen(self, request):
        assert request.headers["User-Agent"] == "subtitle-test"
        return BytesIO(VTT)

    monkeypatch.setattr(video_source, "urlopen", urlopen)
    fetch_video_transcript(VIDEO_URL)
    assert video_source.options["proxy"] == "http://proxy.test"
    assert video_source.options["cachedir"] is False
