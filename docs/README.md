# 架构图存放目录

何时读：修改架构图或核对图表与源码依赖说明。

## 来源与维护边界

图表真源为 [references/architecture.md](../references/architecture.md) 中的 Mermaid 块，本目录保存派生产物。先修改真源再重新生成，不用图片中的连线反向定义源码依赖；完整依赖仍以工程守护和测量为准。

## 产物

| 文件 | 说明 |
|---|---|
| architecture.mmd | 从 architecture.md 提取的 mermaid 源码快照 |
| architecture.svg | 与 mmd 节点连线一一对应的架构图；当前从 mmd 源码通过 Graphviz 渲染；可在自动渲染不可用时手工维护 |
| puppeteer.json | mermaid-cli 的浏览器沙箱配置，供可正常渲染的机器复用 |

## 更新流程

在仓库根目录操作：

1. 修改 references/architecture.md 中的 Mermaid 块；只有说明文字变化时无需重绘。
2. 重新提取源码快照：

   ```bash
   sed -n '/```mermaid/,/```$/p' references/architecture.md | sed '1d;$d' > docs/architecture.mmd
   ```

3. 同步更新 architecture.svg 的节点与连线。优先尝试自动渲染（本机曾长时间挂起，勿无限等待）：

   ```bash
   npx -y @mermaid-js/mermaid-cli -p docs/puppeteer.json -i docs/architecture.mmd -o docs/architecture.svg
   ```

   自动渲染不可用时可从同一源码通过 Graphviz 渲染，或手工排版更新 SVG；节点与连线必须与 mmd 一致。

## 核对与交付

真源、mmd 快照、README 中的 Mermaid 块保持一致；SVG 的节点与连线对应同一版本。`tests/test_runtime.py` 中的架构图守护验证源码快照和 README 一致性；`tests/test_architecture.py` 继续核对 SVG 的完整节点与连线。工程验证入口见 [验证](../references/validation.md)。

新增其他图表时按 `名称.mmd + 名称.svg` 成对存放，源码块仍在对应 references 文档中维护。
