from runtime import APPLICATION_NAME, request_shutdown, service_is_ready, show_message


if not service_is_ready():
    show_message(APPLICATION_NAME, "本地服务当前没有运行。", 0x40)
    raise SystemExit(0)

choice = show_message(
    f"关闭 {APPLICATION_NAME}",
    "确定关闭本地服务吗？正在运行的生成任务会被中断。",
    0x21,
)
if choice != 1:
    raise SystemExit(0)

if not request_shutdown():
    show_message(
        APPLICATION_NAME,
        "无法安全关闭服务。它可能由诊断终端启动，请在对应终端中停止。",
        0x10,
    )
    raise SystemExit(1)
