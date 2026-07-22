# 真实材料全链路与内置示例验收

- 验收日期：2026-07-22
- 结论：通过
- 验收方式：隔离 SQLite、隔离材料目录、隔离 Obsidian Vault、真实 Codex 与 Antigravity 调用

## 材料与授权

本次使用同一小节的两种官方材料，验证 URL 与 PDF 可以同时参与完整流程：

- [MIT OpenCourseWare 18.06 Lecture 1 课程页](https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/resources/lecture-1-the-geometry-of-linear-equations/)
- [MIT 18.06 Lecture 1 官方逐字稿 PDF](https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/50702172c7cdc969615b81e6f22499fd_MIT18_06S10_L01.pdf)
- [MIT OpenCourseWare 使用条款](https://ocw.mit.edu/pages/privacy-and-terms-of-use/)

课程材料按 MIT OpenCourseWare 标注的 CC BY-NC-SA 4.0 条款使用。内置示例只保留为说明完整流程所需的模型输出、短学习输入和来源链接，不内置原始 PDF 或网页快照。

## 全流程结果

六个每日节点、跨自然日交接和小节完成均在隔离环境中实际执行：

| 环节 | 结果 | 实际耗时 |
| --- | --- | ---: |
| 回顾评阅 | 成功，能够依据两份材料指出已有知识与遗漏 | 90.1 秒 |
| 重构检查 | 成功，材料会话重启后可恢复 | 84.3 秒 |
| 练习生成 | 成功，12 题中 4 道选择题，题型和题位完整 | 103.5 秒 |
| 逐题批改 | 成功，准确识别 2 道刻意错误，其余 10 道判定正确 | 48.4 秒 |
| 下次问题 | 成功，生成 3 条问题 | 23.1 秒 |
| 今日完成 | 成功，生成每日摘要并更新学习记忆 | 50.3 秒 |
| GPT 笔记初稿 | 成功，基于完整材料和已有编辑内容生成 | 109.7 秒 |
| Gemini 润色 | 成功，保留事实边界并改善 Obsidian Markdown | 43.0 秒 |

注入下一自然日后，新学习记录自动获得上一日的 3 条衔接问题。最终笔记约 7,800 字符，包含 9 个二级标题、4 张 GFM 表格、28 个块公式和 5 个 Obsidian Callout；Web 与 Obsidian 文件使用同一份 Markdown。

## 质量判断

- 材料引用：模型声明 11 条来源定位，均来自本次启用的 URL 或 PDF 版本。
- 练习完整性：12 个连续题位、4 道选择题、逐题答案与逐题反馈均存在。
- 批改有效性：测试作答只故意错第 2、10 题，结果恰好识别这两题，不显示总分。
- 笔记完整性：保留原学习内容，公式、GFM 表格与 Callout 可在 Web 正常渲染；未出现“待核对”“原笔记此处”或疑似虚构纠错。
- 数据隔离：验收没有读取或改写正式数据库、真实材料目录或用户 Obsidian Vault。
- 静态示例：示例页不调用 API、不写数据库、不调用模型，也不进入课程统计、搜索或导出。

## 验收中发现并修复的问题

1. Gemini OAuth 完成后令牌交换失败：CLI 子进程继承了已停用的代理或缺少 HTTP/HTTPS 代理变量。现在会在不修改系统设置的前提下，从可达的 `ALL_PROXY` 补齐子进程代理。
2. Antigravity 1.1.5 模型标识变化：兼容新的 `gemini-3.5-flash-high` 标识，同时保留旧输出解析。
3. 材料会话跨进程恢复失败：材料锚点改为持久线程；遇到旧的无效锚点时自动清理并重建一次。
4. Gemini 润色引入额外事实判断：提示词收紧为语言、结构和 Obsidian 格式优化，不新增疑点、纠错或外部知识。
5. 移动端批改反馈被错误横向拆列：将宽泛子元素选择器收紧到反馈标题行。
6. 移动端长笔记整页横向溢出：笔记网格允许收缩，宽表格只在自己的滚动容器中横向滚动。

## 自动化与视觉验收

- 前端：ESLint、TypeScript、80 项 Vitest、Vite 8.1.4 生产构建通过。
- 后端：全仓库 Ruff、82 项 pytest、Alembic 漂移检查通过。
- 浏览器：390、1440、2560、3840px 均无整页横向溢出，控制台 0 error/0 warning。
- 390px 笔记页：120 个 KaTeX 节点、1 张 GFM 表格、5 个 Callout 正常；表格内部宽 910px，但页面宽仍等于视口宽。
- 路由：生产构建的 `/example` 支持直接打开和刷新。

完整原始响应、隔离数据库、临时 Vault、导出 ZIP 和截图保存在被忽略的 `output/e2e-qa/2026-07-22-example-flow/` 与 `output/playwright/example-page/`，不会进入开源仓库。
