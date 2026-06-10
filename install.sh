#!/bin/bash
set -e

SKILL_DIR="$HOME/.claude/skills/morning-briefing"
SCRIPT_DIR="$HOME/.cursor/scripts"

echo "==> Installing morning-briefing skill..."

# 1. Copy skill definition
mkdir -p "$SKILL_DIR"
cp SKILL.md "$SKILL_DIR/"
echo "    Skill definition installed to $SKILL_DIR"

# 2. Copy script and requirements
mkdir -p "$SCRIPT_DIR"
cp morning-briefing.py requirements.txt "$SCRIPT_DIR/"
echo "    Script installed to $SCRIPT_DIR"

# 3. Set up Python venv and install dependencies
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    python3 -m venv "$SCRIPT_DIR/.venv"
    echo "    Created Python virtual environment"
fi
"$SCRIPT_DIR/.venv/bin/pip" install -q -r "$SCRIPT_DIR/requirements.txt"
echo "    Python dependencies installed"

# 4. Add crontab entry (daily at 08:00)
CRON_CMD="$SCRIPT_DIR/.venv/bin/python3 $SCRIPT_DIR/morning-briefing.py"
CRON_ENTRY="0 8 * * * $CRON_CMD"

if crontab -l 2>/dev/null | grep -qF "morning-briefing.py"; then
    echo "    Crontab entry already exists, skipping"
else
    (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
    echo "    Added crontab entry (daily 08:00)"
fi

echo ""
echo "==> Done! Usage:"
echo "    In Claude Code, type: /morning-briefing"
echo "    Or say: 晨报、briefing、今天有什么新闻"
