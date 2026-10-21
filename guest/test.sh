#!/bin/bash
set -euo pipefail
export LANG=cs_CZ.UTF-8
[[ $(id -un) == student ]] || { echo 'Spusť starttest jako student. Z účtu otevřeného přes su se vrať příkazem exit.'; exit 1; }
stty -ixon -ixoff 2>/dev/null || true
first=0
[[ -e "$HOME/.linux-exam-instructions-shown" ]] || first=1
sudo /usr/bin/python3 /opt/linux-exam/grader.py start
python3 /opt/linux-exam/session.py go shell
if [[ $first == 1 ]]; then
    touch "$HOME/.linux-exam-instructions-shown"
    python3 /opt/linux-exam/session.py go assignment
fi
if [[ -n ${TMUX:-} ]]; then
    current=$(tmux display-message -p -t "${TMUX_PANE:-}" '#{session_name}')
    [[ "$current" == praktikum ]] && exit 0
    exec tmux switch-client -t praktikum
fi
exec tmux attach-session -d -t praktikum
