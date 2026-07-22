# Lumina 品牌图标

Lumina 的正式图标采用“晨光书页”方向：打开的书位于下半部，三束暖金色光从书脊升起，表达学习带来的理解和启发。图标使用 ImageGen 内置模式生成，并经过绿色背景移除、透明边缘检查和多尺寸缩放。

## 文件

- `candidates/`：三版 ImageGen 原始候选图，只用于设计追溯。
- `lumina-icon-transparent.png`：选定候选移除背景后的原始透明图。
- `lumina-icon-master.png`：裁切和留白规范化后的 1024px 正式主图。
- `lumina-icon-size-check.png`：浅色和深色背景下的 256/128/64/32/16px 检查图。
- `../../launcher/assets/lumina.ico`：Windows 多尺寸快捷方式图标。
- `../../frontend/public/favicon-32.png`、`favicon-192.png`、`apple-touch-icon.png`：Web 图标。

## 生成要求

主提示词要求暖陶土底板、暖白书页和三束宽金色光，不包含文字、字母、灯泡、毕业帽、人物、勾选、太阳、粒子或复杂背景。正式版本选择第二版，因为它在小尺寸下仍能同时辨认书本和光线，且与现有暖白、陶土橙界面一致。

`launcher/build-brand-assets.py` 只用于从透明 PNG 重新生成 ICO 和 Web 尺寸资源，需要 Pillow；它不是应用运行或安装依赖。
