import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

import app.ai_providers as ai_providers_module
from app.ai_providers import (
    AiModelOption,
    AiProviderError,
    AiProviderResult,
    AiProviderStatus,
    AntigravityCli,
    CodexAppServer,
    LoginAttempt,
    TurnState,
    build_subprocess_environment,
    friendly_codex_runtime_error,
    friendly_provider_launch_error,
    resolve_codex_executable,
)
from app.models import AiProvider, AiRun, AiRunStatus, AiRunTask


def structured_items() -> list[dict]:
    return [
        {
            "position": position,
            "item_type": "single_choice" if position <= 4 else "short_answer",
            "difficulty": "basic" if position <= 4 else "intermediate",
            "stem_markdown": f"Question {position}",
            "options": (
                [{"id": "A", "label": "Option A"}, {"id": "B", "label": "Option B"}]
                if position <= 4
                else []
            ),
            "answer_key": {
                "selected_options": ["A"] if position <= 4 else [],
                "answer_markdown": "Reference answer",
            },
            "rubric_markdown": "Check the key idea.",
            "source_refs": [],
        }
        for position in range(1, 13)
    ]


def test_ai_run_can_be_cancelled_and_retried_from_the_original_action(
    client: TestClient, app: FastAPI
) -> None:
    session_factory: sessionmaker[Session] = app.state.session_factory
    with session_factory() as session:
        run = AiRun(
            provider=AiProvider.CODEX,
            task=AiRunTask.PRACTICE_GENERATION,
            status=AiRunStatus.RUNNING,
            context_snapshot="context",
            prompt_text="prompt",
        )
        session.add(run)
        session.commit()
        run_id = run.id

    response = client.post(f"/api/ai-runs/{run_id}/cancel")
    assert response.status_code == 204
    with session_factory() as session:
        cancelled = session.get(AiRun, run_id)
        assert cancelled is not None
        assert cancelled.status == AiRunStatus.FAILED
        assert "已取消" in cancelled.error_text
    assert client.post(f"/api/ai-runs/{run_id}/cancel").status_code == 409


class FakeCodex:
    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.last_options: dict = {}

    async def login(self) -> dict[str, str]:
        return {"auth_url": "https://example.test/login", "login_id": "login-1"}

    async def logout(self) -> None:
        return None

    def login_status(self, login_id: str) -> LoginAttempt:
        assert login_id == "login-1"
        return LoginAttempt(status="succeeded")

    async def model_entries(self) -> list[dict]:
        return [
            {
                "model": "gpt-5.5",
                "displayName": "GPT-5.5",
                "defaultReasoningEffort": "medium",
                "supportedReasoningEfforts": [
                    {"reasoningEffort": "low"},
                    {"reasoningEffort": "medium"},
                    {"reasoningEffort": "high"},
                ],
            }
        ]

    model_options = CodexAppServer.model_options

    async def generate(
        self,
        prompt: str,
        output_schema: dict | None = None,
        **options,
    ) -> AiProviderResult:
        self.last_options = options
        self.prompts.append(prompt)
        handoff = {
            "confirmed_points": ["已确认 A"],
            "corrections": [],
            "key_concepts": ["概念 A"],
            "key_formulas": [],
            "unresolved_points": [],
            "error_patterns": [],
            "source_refs": [],
        }
        memory = {
            "summary": "本节摘要",
            "core_concepts": ["概念 A"],
            "key_methods": ["方法 A"],
            "unresolved_questions": ["问题 A"],
            "error_patterns": ["错误 A"],
        }
        properties = output_schema.get("properties", {}) if output_schema else {}
        if "items" in properties:
            text = json.dumps(
                {"items": structured_items(), "handoff": handoff},
                ensure_ascii=False,
            )
        elif "results" in properties:
            text = json.dumps(
                {
                    "results": [
                        {
                            "position": position,
                            "verdict": "correct",
                            "feedback_markdown": "Answer accepted.",
                        }
                        for position in range(1, 13)
                    ],
                    "handoff": handoff,
                },
                ensure_ascii=False,
            )
        elif "questions" in properties:
            text = json.dumps(
                {
                    "questions": ["问题一", "问题二", "问题三"],
                    "handoff": handoff,
                },
                ensure_ascii=False,
            )
        elif (
            "display_markdown" in properties
            and "section_memory" in properties
        ):
            text = json.dumps(
                {
                    "display_markdown": "今日摘要",
                    "handoff": handoff,
                    "section_memory": memory,
                    "chapter_memory": {**memory, "summary": "本章摘要"},
                },
                ensure_ascii=False,
            )
        elif "display_markdown" in properties:
            text = json.dumps(
                {
                    "display_markdown": "AI 生成结果",
                    "handoff": handoff,
                },
                ensure_ascii=False,
            )
        elif "section_memory" in properties:
            text = json.dumps(
                {
                    "section_memory": memory,
                    "chapter_memory": {**memory, "summary": "本章摘要"},
                },
                ensure_ascii=False,
            )
        else:
            text = "AI 生成结果"
        return AiProviderResult(
            text=text,
            model=options.get("model", "fake-codex"),
            thread_id="fresh-thread",
        )


class FakeGemini:
    def __init__(self) -> None:
        self.disconnected = False
        self.prompts: list[str] = []

    async def login(self) -> dict[str, str]:
        return {"login_id": "gemini-login-1"}

    def login_status(self, login_id: str) -> LoginAttempt:
        assert login_id == "gemini-login-1"
        return LoginAttempt(status="succeeded")

    async def cancel_login(self, login_id: str) -> None:
        assert login_id == "gemini-login-1"

    async def disconnect(self) -> None:
        self.disconnected = True

    async def model_options(self) -> list[AiModelOption]:
        return [
            AiModelOption(
                model="Gemini 3.5 Flash",
                display_name="Gemini 3.5 Flash",
                reasoning_efforts=("low", "medium", "high"),
                default_reasoning_effort="high",
            )
        ]

    async def generate(self, prompt: str, model: str | None = None) -> AiProviderResult:
        assert "Markdown" in prompt
        self.prompts.append(prompt)
        return AiProviderResult(text="# 润色后的笔记", model=model or "fake-gemini")


class FakeAiService:
    def __init__(self) -> None:
        self.codex = FakeCodex()
        self.gemini = FakeGemini()

    async def close(self) -> None:
        return None

    async def statuses(
        self,
        *,
        gemini_enabled: bool = True,
        **preferences,
    ) -> list[AiProviderStatus]:
        del preferences
        return [
            AiProviderStatus("codex", True, True, "已连接", account="test@example.com"),
            AiProviderStatus(
                "gemini",
                True,
                gemini_enabled,
                "已连接" if gemini_enabled else "已从本工具断开 Antigravity",
                version="1.0.0",
                state="connected" if gemini_enabled else "disconnected",
            ),
        ]


class InvalidPracticeCodex(FakeCodex):
    async def generate(
        self,
        prompt: str,
        output_schema: dict | None = None,
        **options,
    ) -> AiProviderResult:
        result = await super().generate(prompt, output_schema, **options)
        if output_schema and "items" in output_schema.get("properties", {}):
            payload = json.loads(result.text)
            payload["items"] = payload["items"][:-1]
            result.text = json.dumps(payload, ensure_ascii=False)
        return result


def create_record(client: TestClient) -> tuple[dict, dict, dict]:
    course = client.post(
        "/api/courses",
        json={"name": "测试课程", "description": "", "learning_goal": "理解主题"},
    ).json()
    chapter = client.post(
        f"/api/courses/{course['id']}/chapters",
        json={"title": "第一章"},
    ).json()
    section = client.post(
        f"/api/chapters/{chapter['id']}/sections",
        json={"title": "第一节"},
    ).json()
    record = client.post(f"/api/sections/{section['id']}/daily-records/today").json()
    client.patch(
        f"/api/daily-records/{record['id']}",
        json={
            "recall_last_learned": "上次内容",
            "reconstruct_main_learning": "本次内容",
            "study_material_scope": "第一章第一节",
        },
    )
    return course, section, record


def test_provider_status_and_login(client: TestClient, app: FastAPI) -> None:
    app.state.ai_service = FakeAiService()

    providers = client.get("/api/ai/providers")
    assert providers.status_code == 200
    assert providers.json()[0]["connected"] is True

    login = client.post("/api/ai/providers/codex/login")
    assert login.json()["auth_url"] == "https://example.test/login"
    assert client.get("/api/ai/providers/codex/login/login-1").json()["status"] == "succeeded"
    assert client.post("/api/ai/providers/codex/logout").status_code == 204
    gemini_login = client.post("/api/ai/providers/gemini/login")
    assert gemini_login.json()["login_id"] == "gemini-login-1"
    assert (
        client.get("/api/ai/providers/gemini/login/gemini-login-1").json()["status"] == "succeeded"
    )
    assert client.post("/api/ai/providers/gemini/login/gemini-login-1/cancel").status_code == 204
    assert client.post("/api/ai/providers/gemini/disconnect").status_code == 204
    assert client.get("/api/ai/providers").json()[1]["connected"] is False
    assert client.post("/api/ai/providers/gemini/enable").status_code == 204
    assert client.get("/api/ai/providers").json()[1]["connected"] is True


def test_provider_preferences_use_live_model_options(client: TestClient, app: FastAPI) -> None:
    service = FakeAiService()
    app.state.ai_service = service

    options = client.get("/api/ai/provider-options")
    assert options.status_code == 200
    assert options.json()[0]["selected_model"] == "gpt-5.5"
    assert options.json()[0]["selected_reasoning_effort"] == "medium"
    assert options.json()[1]["selected_model"] == "Gemini 3.5 Flash"
    assert options.json()[1]["selected_reasoning_effort"] == "high"

    codex = client.put(
        "/api/settings/ai-providers/codex",
        json={"model": "gpt-5.5", "reasoning_effort": "high"},
    )
    assert codex.status_code == 200
    assert codex.json()["selected_reasoning_effort"] == "high"

    gemini = client.put(
        "/api/settings/ai-providers/gemini",
        json={"model": "Gemini 3.5 Flash", "reasoning_effort": "medium"},
    )
    assert gemini.status_code == 200
    assert gemini.json()["selected_reasoning_effort"] == "medium"

    invalid = client.put(
        "/api/settings/ai-providers/codex",
        json={"model": "gpt-missing", "reasoning_effort": "medium"},
    )
    assert invalid.status_code == 422

    _, _, record = create_record(client)
    generated = client.post(f"/api/daily-records/{record['id']}/ai-review/recall_review")
    assert generated.status_code == 201
    assert service.codex.last_options["model"] == "gpt-5.5"
    assert service.codex.last_options["reasoning_effort"] == "high"


def test_provider_snapshot_combines_status_and_options(
    client: TestClient,
    app: FastAPI,
) -> None:
    app.state.ai_service = FakeAiService()

    response = client.get("/api/ai/provider-snapshot")

    assert response.status_code == 200
    assert [item["provider"] for item in response.json()["providers"]] == [
        "codex",
        "gemini",
    ]
    assert [item["provider"] for item in response.json()["options"]] == [
        "codex",
        "gemini",
    ]


def test_model_list_probes_are_reused_for_a_short_refresh_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    codex = CodexAppServer(tmp_path / "codex", tmp_path / "workspace")
    codex_calls = 0

    async def fake_request(method: str, params: dict) -> dict:
        nonlocal codex_calls
        assert method == "model/list"
        assert params["limit"] == 100
        codex_calls += 1
        return {"data": [{"model": "gpt-5.5"}]}

    monkeypatch.setattr(codex, "request", fake_request)
    async def read_codex_models_twice():
        return await asyncio.gather(codex.model_entries(), codex.model_entries())

    first, second = asyncio.run(read_codex_models_twice())
    assert first == second
    assert codex_calls == 1

    antigravity = AntigravityCli(tmp_path / "workspace")
    antigravity.executable = "agy"
    gemini_calls = 0

    async def fake_command(*args: str, timeout: float = 30):
        nonlocal gemini_calls
        del args, timeout
        gemini_calls += 1
        return 0, "Gemini 3.5 Flash (High)", ""

    monkeypatch.setattr(antigravity, "_run_command", fake_command)

    async def read_models_twice():
        return await asyncio.gather(
            antigravity._run_models(),
            antigravity._run_models(),
        )

    first_models, second_models = asyncio.run(read_models_twice())
    assert first_models == second_models
    assert gemini_calls == 1


def test_provider_model_option_parsers() -> None:
    codex_options = CodexAppServer.model_options(
        [
            {
                "model": "gpt-5.5",
                "displayName": "GPT-5.5",
                "defaultReasoningEffort": "medium",
                "supportedReasoningEfforts": [
                    {"reasoningEffort": "low"},
                    {"reasoningEffort": "medium"},
                    {"reasoningEffort": "high"},
                ],
            }
        ]
    )
    assert codex_options[0].reasoning_efforts == ("low", "medium", "high")

    gemini_options = AntigravityCli.parse_model_options(
        "\n".join(
            [
                "* Gemini 3.5 Flash (Medium)",
                "* Gemini 3.5 Flash (High)",
                "* Gemini 3.5 Flash (Low)",
                "* Claude Sonnet 4.6 (Thinking)",
            ]
        )
    )
    assert len(gemini_options) == 1
    assert gemini_options[0].model == "Gemini 3.5 Flash"
    assert gemini_options[0].reasoning_efforts == ("low", "medium", "high")

    slug_options = AntigravityCli.parse_model_options(
        "\n".join(
            [
                "gemini-3.6-flash-high",
                "gemini-3.5-flash-medium",
                "gemini-3.5-flash-high",
                "gemini-3.5-flash-low",
                "claude-sonnet-4-6",
            ]
        )
    )
    assert [option.model for option in slug_options] == [
        "Gemini 3.6 Flash",
        "Gemini 3.5 Flash",
    ]
    assert slug_options[1].reasoning_efforts == ("low", "medium", "high")


def test_learner_profile_and_completed_course_enter_later_context(
    client: TestClient,
    app: FastAPI,
) -> None:
    service = FakeAiService()
    app.state.ai_service = service
    profile = "我是一名工科研究生，具备高等数学、线性代数和机器学习基础。"
    settings = client.put(
        "/api/settings/learner-profile",
        json={"learner_profile": profile},
    )
    assert settings.status_code == 200
    assert settings.json()["learner_profile"] == profile

    course, section, _ = create_record(client)
    client.patch(f"/api/sections/{section['id']}", json={"status": "completed"})
    completed = client.post(f"/api/courses/{course['id']}/complete")
    assert completed.status_code == 200
    assert completed.json()["completion_summary"] == "AI 生成结果"

    _, _, later_record = create_record(client)
    review = client.post(
        f"/api/daily-records/{later_record['id']}/ai-review/recall_review"
    )
    assert review.status_code == 201
    assert profile in service.codex.prompts[-1]
    assert "测试课程：AI 生成结果" in service.codex.prompts[-1]


def test_subprocess_environment_replaces_a_dead_local_proxy() -> None:
    source = {
        "HTTP_PROXY": "http://127.0.0.1:18080",
        "HTTPS_PROXY": "http://127.0.0.1:18080",
        "ALL_PROXY": "http://127.0.0.1:18081",
    }

    env = build_subprocess_environment(
        source,
        probe=lambda value: value.endswith(":18081"),
    )

    assert env["HTTP_PROXY"] == "http://127.0.0.1:18081"
    assert env["HTTPS_PROXY"] == "http://127.0.0.1:18081"
    assert env["ALL_PROXY"] == "http://127.0.0.1:18081"


def test_subprocess_environment_populates_missing_proxy_variants() -> None:
    env = build_subprocess_environment(
        {"ALL_PROXY": "http://127.0.0.1:18081"},
        probe=lambda value: value.endswith(":18081"),
    )

    assert env["HTTP_PROXY"] == "http://127.0.0.1:18081"
    assert env["HTTPS_PROXY"] == "http://127.0.0.1:18081"
    assert env["http_proxy"] == "http://127.0.0.1:18081"
    assert env["https_proxy"] == "http://127.0.0.1:18081"


def test_codex_login_completion_exposes_a_friendly_error(tmp_path) -> None:
    codex = CodexAppServer(tmp_path / "home", tmp_path / "workspace")

    codex.complete_login(
        {
            "loginId": "login-1",
            "success": False,
            "error": (
                "Token exchange failed: error sending request for url "
                "(https://auth.openai.com/oauth/token)"
            ),
        }
    )

    attempt = codex.login_status("login-1")
    assert attempt.status == "failed"
    assert attempt.error == "Codex 登录失败：无法连接授权服务器，请检查本机代理后重试。"


def test_codex_refresh_token_error_requires_reconnecting() -> None:
    assert (
        friendly_codex_runtime_error(
            "Your access token could not be refreshed because your refresh token was revoked."
        )
        == "Codex 登录已失效，请先在设置中重新连接 Codex。"
    )
    assert friendly_codex_runtime_error(
        "Invalid request: readOnlyAccess is no longer supported"
    ) == "Codex CLI 权限协议已更新，请重启 Study Web 后重试。"
    assert friendly_codex_runtime_error(
        "turn/start.runtimeWorkspaceRoots requires experimentalApi capability"
    ) == "Codex CLI 工作区能力协商失败，请重启 Study Web 后重试。"


def test_codex_declares_experimental_api_capability_on_initialize(
    tmp_path,
    monkeypatch,
) -> None:
    codex = CodexAppServer(tmp_path / "home", tmp_path / "workspace")
    captured: dict = {}

    class FakeStream:
        async def readline(self):
            return b""

    class FakeProcess:
        returncode = None
        stdout = FakeStream()
        stderr = FakeStream()

    async def fake_create_subprocess_exec(*args, **kwargs):
        del args, kwargs
        return FakeProcess()

    async def fake_request(method: str, params: dict):
        captured[method] = params
        return {}

    async def fake_notify(method: str, params: dict):
        captured[method] = params

    monkeypatch.setattr(
        ai_providers_module.asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    monkeypatch.setattr(codex, "request", fake_request)
    monkeypatch.setattr(codex, "notify", fake_notify)

    asyncio.run(codex.start())

    assert captured["initialize"]["capabilities"] == {"experimentalApi": True}


def test_access_denied_recommends_the_local_launcher() -> None:
    error = OSError("Access is denied")
    error.winerror = 5

    message = friendly_provider_launch_error("Codex CLI", error)

    assert "Windows 错误代码 5" in message
    assert "不代表你的账号或文件没有权限" in message
    assert "start-local.cmd" in message


def test_codex_resolver_prefers_the_npm_native_binary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shim = tmp_path / "codex.cmd"
    shim.touch()
    native = (
        tmp_path
        / "node_modules"
        / "@openai"
        / "codex"
        / "node_modules"
        / "@openai"
        / "codex-win32-x64"
        / "vendor"
        / "x86_64-pc-windows-msvc"
        / "bin"
        / "codex.exe"
    )
    native.parent.mkdir(parents=True)
    native.touch()

    monkeypatch.setattr(
        ai_providers_module.shutil,
        "which",
        lambda name: str(shim) if name == "codex.cmd" else "C:/WindowsApps/codex.exe",
    )

    assert resolve_codex_executable() == str(native)


def test_codex_refuses_to_fall_back_when_gpt_5_5_is_unavailable(
    tmp_path,
    monkeypatch,
) -> None:
    codex = CodexAppServer(tmp_path / "home", tmp_path / "workspace")

    async def fake_account():
        return {"email": "test@example.com"}

    async def fake_request(method: str, params: dict):
        del params
        assert method == "model/list"
        return {"data": [{"model": "gpt-5.4"}, {"model": "gpt-5.2"}]}

    monkeypatch.setattr(codex, "account", fake_account)
    monkeypatch.setattr(codex, "request", fake_request)

    with pytest.raises(AiProviderError, match="没有提供 GPT-5.5"):
        asyncio.run(codex.generate("测试"))


def test_codex_uses_gpt_5_5_with_medium_effort(tmp_path, monkeypatch) -> None:
    codex = CodexAppServer(tmp_path / "home", tmp_path / "workspace")

    async def fake_account():
        return {"email": "test@example.com"}

    async def fake_request(method: str, params: dict):
        if method == "model/list":
            return {"data": [{"model": "gpt-5.5"}, {"model": "gpt-5.4"}]}
        if method == "thread/start":
            assert params["model"] == "gpt-5.5"
            assert "网络" in params["baseInstructions"]
            return {"thread": {"id": "thread-1"}}
        if method == "turn/start":
            assert params["model"] == "gpt-5.5"
            assert params["effort"] == "medium"
            assert params["permissions"] == ":read-only"
            assert params["runtimeWorkspaceRoots"] == [str(tmp_path / "workspace")]
            assert "sandboxPolicy" not in params
            state = codex.turns.setdefault("turn-1", TurnState())
            state.text = "完成"
            state.completed.set()
            return {"turn": {"id": "turn-1"}}
        raise AssertionError(f"Unexpected method: {method}")

    monkeypatch.setattr(codex, "account", fake_account)
    monkeypatch.setattr(codex, "request", fake_request)

    result = asyncio.run(codex.generate("测试"))

    assert result.text == "完成"
    assert result.model == "gpt-5.5"
    assert codex.active_model == "gpt-5.5"


def test_codex_cancellation_interrupts_the_active_turn(tmp_path, monkeypatch) -> None:
    codex = CodexAppServer(tmp_path / "home", tmp_path / "workspace")
    calls: list[str] = []
    turn_started = asyncio.Event()

    async def fake_account():
        return {"email": "test@example.com"}

    async def fake_request(method: str, params: dict):
        calls.append(method)
        if method == "model/list":
            return {"data": [{"model": "gpt-5.5"}]}
        if method == "thread/start":
            return {"thread": {"id": "thread-1"}}
        if method == "turn/start":
            turn_started.set()
            return {"turn": {"id": "turn-1"}}
        if method == "turn/interrupt":
            assert params == {"threadId": "thread-1", "turnId": "turn-1"}
            return {}
        raise AssertionError(f"Unexpected method: {method}")

    monkeypatch.setattr(codex, "account", fake_account)
    monkeypatch.setattr(codex, "request", fake_request)

    async def cancel_active_generation() -> None:
        task = asyncio.create_task(codex.generate("测试取消", timeout_seconds=30))
        await turn_started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel_active_generation())

    assert "turn/interrupt" in calls
    assert "turn-1" not in codex.turns


def test_antigravity_print_mode_uses_plain_output(tmp_path, monkeypatch) -> None:
    antigravity = AntigravityCli(tmp_path / "workspace")
    antigravity.executable = "agy"
    captured: tuple[str, ...] = ()

    async def fake_run_command(*args: str, timeout: float = 30):
        nonlocal captured
        captured = args
        assert timeout == 300
        return 0, "润色后的笔记", ""

    monkeypatch.setattr(antigravity, "_run_command", fake_run_command)
    result = asyncio.run(antigravity.generate("润色这份笔记"))

    assert captured == (
        "-p",
        "润色这份笔记",
        "--model",
        "gemini-3.5-flash-high",
        "--sandbox",
    )
    assert result.text == "润色后的笔记"


def test_antigravity_status_keeps_login_when_preferred_model_is_unavailable(
    tmp_path,
    monkeypatch,
) -> None:
    antigravity = AntigravityCli(tmp_path / "workspace")
    antigravity.executable = "agy"

    async def fake_run_command(*args: str, timeout: float = 30):
        del timeout
        if args == ("--version",):
            return 0, "1.1.3", ""
        return (
            0,
            "Gemini 3.5 Flash (Medium)",
            "I0000 applyAuthResult: email=learner@example.com, authMethod=consumer",
        )

    monkeypatch.setattr(antigravity, "_run_command", fake_run_command)
    status = asyncio.run(antigravity.status())

    assert status.connected is True
    assert status.state == "model_unavailable"
    assert status.model_available is False
    assert status.account == "learner@example.com"
    assert "当前模型" in status.detail


def test_antigravity_account_parser_ignores_invalid_diagnostics() -> None:
    assert (
        AntigravityCli.account_from_diagnostics(
            "I0000 OAuth: authenticated successfully as learner@example.com"
        )
        == "learner@example.com"
    )
    assert (
        AntigravityCli.account_from_diagnostics(
            "I0000 applyAuthResult: email=, authMethod=consumer"
        )
        == ""
    )


def test_antigravity_status_reads_account_from_temporary_cli_log(
    tmp_path,
    monkeypatch,
) -> None:
    antigravity = AntigravityCli(tmp_path / "workspace")
    antigravity.executable = "agy"

    async def fake_run_command(*args: str, timeout: float = 30):
        del timeout
        if args == ("--version",):
            return 0, "1.1.3", ""
        assert args[0] == "--log-file"
        assert args[2] == "models"
        log_path = Path(args[1])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            "I0000 OAuth: authenticated successfully as learner@example.com",
            encoding="utf-8",
        )
        return 0, "Gemini 3.5 Flash (High)", ""

    monkeypatch.setattr(antigravity, "_run_command", fake_run_command)
    status = asyncio.run(antigravity.status())

    assert status.account == "learner@example.com"
    assert not list((tmp_path / "workspace").glob(".antigravity-status-*.log"))


def test_antigravity_login_completes_without_waiting_for_interactive_exit(
    tmp_path,
    monkeypatch,
) -> None:
    antigravity = AntigravityCli(tmp_path / "workspace")
    antigravity.executable = "agy"
    antigravity.login_check_interval = 0
    login_id = "login-1"
    antigravity.login_attempts[login_id] = LoginAttempt(detail="等待登录")

    class FakeProcess:
        returncode = None
        terminated = False
        waited = False

        def terminate(self) -> None:
            self.terminated = True
            self.returncode = 0

        def kill(self) -> None:
            self.returncode = 1

        async def wait(self) -> int:
            self.waited = True
            return self.returncode or 0

    process = FakeProcess()

    async def fake_create_subprocess_exec(*args, **kwargs):
        del args, kwargs
        return process

    async def fake_run_command(*args: str, timeout: float = 30):
        assert args == ("models",)
        assert timeout == 20
        return 0, "Gemini 3.5 Flash (High)", ""

    monkeypatch.setattr(
        ai_providers_module.asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    monkeypatch.setattr(antigravity, "_run_command", fake_run_command)

    asyncio.run(antigravity._run_login(login_id))

    assert antigravity.login_attempts[login_id].status == "succeeded"
    assert process.terminated is True
    assert process.waited is True


def test_embedded_ai_workflow_and_learning_memory(client: TestClient, app: FastAPI) -> None:
    app.state.ai_service = FakeAiService()
    course, section, record = create_record(client)

    review = client.post(f"/api/daily-records/{record['id']}/ai-review/recall_review")
    assert review.status_code == 201
    assert review.json()["feedback_text"] == "AI 生成结果"

    exercise = client.post(f"/api/daily-records/{record['id']}/ai-practice")
    assert exercise.status_code == 201
    exercise_body = exercise.json()
    assert exercise_body["format_version"] == 2
    assert len(exercise_body["items"]) == 12
    assert sum(item["item_type"] == "single_choice" for item in exercise_body["items"]) == 4
    exercise_id = exercise_body["id"]
    assert client.delete(f"/api/exercises/{exercise_id}").status_code == 409
    for item in exercise_body["items"]:
        payload = (
            {
                "selected_options": ["B"] if item["position"] == 1 else ["A"],
                "answer_markdown": "",
            }
            if item["options"]
            else {"selected_options": [], "answer_markdown": f"Answer {item['position']}"}
        )
        response = client.put(f"/api/exercise-items/{item['id']}/response", json=payload)
        assert response.status_code == 200
    assert client.post(f"/api/exercises/{exercise_id}/complete").status_code == 200
    grading = client.post(f"/api/exercises/{exercise_id}/ai-grade")
    assert grading.status_code == 200
    assert grading.json()["ai_feedback"] == ""
    assert all(item["response"]["status"] == "graded" for item in grading.json()["items"])
    assert all(item["response"]["score"] is None for item in grading.json()["items"])
    assert grading.json()["items"][0]["response"]["verdict"] == "incorrect"
    assert grading.json()["items"][1]["response"]["verdict"] == "correct"
    assert "本地选择题判定：incorrect" in app.state.ai_service.codex.prompts[-1]
    refreshed_record = client.get(f"/api/daily-records/{record['id']}").json()
    review_node = next(
        node for node in refreshed_record["workflow_nodes"] if node["node_key"] == "review"
    )
    assert review_node["status"] == "pending"

    preview = client.post(f"/api/daily-records/{record['id']}/ai-preview-questions")
    assert preview.json()["question_1"] == "问题一"

    completed = client.post(f"/api/daily-records/{record['id']}/complete")
    assert completed.status_code == 200
    assert completed.json()["is_completed"] is True
    assert completed.json()["context_summary"] == "今日摘要"
    note = client.post(
        f"/api/daily-records/{record['id']}/ai-section-note",
        json={"existing_content": "已有内容", "mode": "revise"},
    )
    assert note.json()["text"] == "AI 生成结果"
    background_run = client.post(
        f"/api/daily-records/{record['id']}/ai-section-note-runs",
        json={"existing_content": "已有内容", "mode": "revise"},
    )
    assert background_run.status_code == 202
    run_id = background_run.json()["id"]
    for _ in range(40):
        background_result = client.get(f"/api/ai-runs/{run_id}/result")
        if background_result.json()["run"]["status"] != "running":
            break
        asyncio.run(asyncio.sleep(0.01))
    assert background_result.json()["run"]["status"] == "completed"
    assert background_result.json()["result"]["text"] == "AI 生成结果"
    polished = client.post(
        f"/api/sections/{section['id']}/ai-polish-note",
        json={"content": "# 原始笔记"},
    )
    assert polished.json()["text"] == "# 润色后的笔记"
    polish_prompt = app.state.ai_service.gemini.prompts[-1]
    assert "不承担事实核查或内容纠错任务" in polish_prompt
    assert "不得新增原文未明确写出的疑点" in polish_prompt
    assert client.post("/api/ai/providers/gemini/disconnect").status_code == 204
    disabled_polish = client.post(
        f"/api/sections/{section['id']}/ai-polish-note",
        json={"content": "# 原始笔记"},
    )
    assert disabled_polish.status_code == 409
    assert disabled_polish.json()["detail"] == "请先在设置中重新连接 Antigravity"
    assert client.post("/api/ai/providers/gemini/enable").status_code == 204

    refreshed = client.post(f"/api/sections/{section['id']}/learning-memory/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["summary"] == "本节摘要"

    memory = client.get(f"/api/courses/{course['id']}/learning-memory")
    assert memory.status_code == 200
    assert memory.json()["chapters"][0]["summary"] == "本章摘要"
    assert memory.json()["sections"][0]["core_concepts"] == "- 概念 A"

    updated = client.put(
        f"/api/courses/{course['id']}/learning-memory",
        json={
            "overview": "课程概览",
            "core_concepts": "核心概念",
            "key_methods": "关键方法",
            "unresolved_questions": "",
            "error_patterns": "",
        },
    )
    assert updated.json()["overview"] == "课程概览"


def test_invalid_structured_output_marks_ai_run_failed(
    client: TestClient,
    app: FastAPI,
) -> None:
    service = FakeAiService()
    service.codex = InvalidPracticeCodex()
    app.state.ai_service = service
    _, _, record = create_record(client)

    response = client.post(f"/api/daily-records/{record['id']}/ai-practice")

    assert response.status_code == 502
    assert response.json()["detail"] == "练习生成结果不是完整的 12 道题"
    runs = client.get(f"/api/ai-runs?daily_record_id={record['id']}").json()
    assert runs[0]["task"] == "practice_generation"
    assert runs[0]["status"] == "failed"
    assert datetime.fromisoformat(runs[0]["created_at"].replace("Z", "+00:00")).tzinfo == UTC


def test_business_ai_error_returns_actionable_http_status_after_local_material_setup(
    client: TestClient,
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.state.ai_service = FakeAiService()
    _, _, record = create_record(client)

    async def fail_business_task(*args, **kwargs):
        del args, kwargs
        raise AiProviderError("Codex 登录已失效，请先在设置中重新连接 Codex。")

    monkeypatch.setattr(app.state.ai_service.codex, "generate", fail_business_task)

    response = client.post(f"/api/daily-records/{record['id']}/ai-review/recall_review")

    assert response.status_code == 409
    assert response.json()["detail"] == "Codex 登录已失效，请先在设置中重新连接 Codex。"


def test_note_manual_prompt_matches_generation_and_excludes_practice_history(
    client: TestClient,
    app: FastAPI,
) -> None:
    service = FakeAiService()
    app.state.ai_service = service
    _, _, record = create_record(client)
    for index in range(1, 3):
        exercise = client.post(f"/api/daily-records/{record['id']}/exercises").json()
        client.patch(
            f"/api/exercises/{exercise['id']}",
            json={
                "ai_questions": f"题目组 {index}",
                "user_answers": f"答案组 {index}",
                "ai_feedback": f"批改组 {index}",
            },
        )

    payload = {"existing_content": "# 已有笔记\n保留这一段", "mode": "revise"}
    manual = client.post(
        f"/api/daily-records/{record['id']}/section-note-prompt",
        json=payload,
    )
    assert manual.status_code == 200
    prompt = manual.json()["prompt_text"]
    assert "章节：第一章" in prompt
    assert "题目组 1" not in prompt
    assert "题目组 2" not in prompt
    assert "批改组 1" not in prompt
    assert "# 已有笔记" in prompt

    generated = client.post(
        f"/api/daily-records/{record['id']}/ai-section-note",
        json=payload,
    )
    assert generated.status_code == 200
    assert service.codex.prompts[-1] == prompt
