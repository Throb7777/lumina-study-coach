# AI Connections

Lumina can use external command-line tools for evaluation, practice, and note
polishing. These integrations are optional and do not use an API key stored by
Lumina.

## Codex

Install the official Codex CLI separately, then open **设置 → 模型连接** and
select **连接 Codex**. Complete the official ChatGPT sign-in in the browser.
Lumina keeps a project-specific Codex home under its local runtime directory;
it does not modify the user's global Codex configuration.

Codex handles recall review, reconstruction checks, practice generation,
answer review, next questions, daily summaries, learning memory, and the first
section-note draft.

## Gemini via Antigravity

Install Antigravity separately, then select **连接 Antigravity** in Settings
and finish Google's official sign-in. Gemini is used only for the optional
final language and Obsidian-format polishing step.

Disconnecting Antigravity in Lumina stops this application from using the
current connection. It does not delete the Google account's official CLI login.

## Availability

Models and reasoning levels are read from the installed CLI and connected
account. Lumina does not silently switch to a different model. Authentication,
membership, model names, quotas, and availability are controlled by the
providers and may change.

If an integration is unavailable, the generated prompt can still be copied and
used manually.
