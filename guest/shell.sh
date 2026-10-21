#!/bin/bash
# Poslední exit/Ctrl+D nezavře studentovi jediný příkazový řádek.
trap 'exit 0' HUP TERM
while true; do
    /bin/bash --rcfile /opt/linux-exam/bashrc -i
    stty -g >/dev/null 2>&1 || exit 0
    sleep 0.2
    printf '\n\033[33mTerminál byl zavřen. Otevírám nový; body a čas zůstaly zachované.\033[0m\n'
done
