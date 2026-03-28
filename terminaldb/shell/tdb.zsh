# terminalDB shell hook — zsh
# Installed by: tdb setup
# Remove with:  tdb unsetup

_tdb_preexec() {
  _TDB_LAST_CMD="$1"
}

_tdb_precmd() {
  local cmd="${_TDB_LAST_CMD:-}"
  _TDB_LAST_CMD=""
  [[ -z "$cmd" ]] && return
  tdb capture "$cmd"
}

autoload -Uz add-zsh-hook
add-zsh-hook preexec _tdb_preexec
add-zsh-hook precmd  _tdb_precmd
