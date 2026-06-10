# Daily Digest

AI + Frontend 每日技术晨报，为 Claude Code 打造的 skill。

每天 08:00 自动从 HN、RSS 采集 AI 和前端技术新闻，使用时由 Claude 总结呈报。

## 功能

- 从 Hacker News 采集热门 AI/前端故事（按关键词过滤）
- 从 17+ RSS 源采集新闻（Anthropic、OpenAI、HuggingFace、Vue、Nuxt 等）
- 缺天自动补报（catchup mode）
- 自动清理 7 天前的旧数据
- Claude 总结时结合用户技术栈高亮"与你相关"内容

## 快速安装

```bash
git clone https://github.com/HiraMafu/daily-digest.git
cd daily-digest
chmod +x install.sh
./install.sh
```

安装完成后，在 Claude Code 中输入 `/morning-briefing` 即可。

## 手动安装

如果不想用安装脚本：

```bash
# 1. 复制 skill 定义
mkdir -p ~/.claude/skills/morning-briefing
cp SKILL.md ~/.claude/skills/morning-briefing/

# 2. 复制脚本
mkdir -p ~/.cursor/scripts
cp morning-briefing.py requirements.txt ~/.cursor/scripts/

# 3. 安装 Python 依赖
cd ~/.cursor/scripts
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. 设置定时任务（可选，每天 08:00 自动采集）
(crontab -l 2>/dev/null; echo "0 8 * * * ~/.cursor/scripts/.venv/bin/python3 ~/.cursor/scripts/morning-briefing.py") | crontab -
```

## 触发方式

在 Claude Code 中说：
- `/morning-briefing`
- "晨报"
- "briefing"
- "今天有什么新闻"

## 数据源

### AI / LLM
- Hacker News（AI 关键词过滤）
- Anthropic Blog、OpenAI Blog
- HuggingFace Blog
- MIT Tech Review AI、Ars Technica
- TechCrunch AI
- arXiv cs.AI / cs.CL
- 36Kr

### Frontend
- Hacker News（前端关键词过滤）
- Vue.js Blog、Nuxt Blog
- Dev.to (Vue / TypeScript)
- CSS-Tricks、Smashing Magazine
- web.dev

## 自定义

编辑 `morning-briefing.py` 中的 `RSS_FEEDS` 和 `AI_KEYWORDS` / `FRONTEND_KEYWORDS` 来调整数据源和过滤关键词。

## 文件结构

```
~/.claude/skills/morning-briefing/SKILL.md    ← Claude Code skill 定义
~/.cursor/scripts/morning-briefing.py              ← 数据采集脚本
~/.cursor/scripts/requirements.txt                 ← Python 依赖
~/.cursor/briefing/YYYY-MM-DD.md                   ← 每日数据文件（自动生成）
```
