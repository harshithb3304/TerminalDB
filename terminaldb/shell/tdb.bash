# terminalDB shell hook — bash
# Installed by: tdb setup --shell bash
# Remove with:  tdb unsetup --shell bash

_tdb_prompt_command() {
  local exit_code=$?
  local cmd
  cmd=$(HISTTIMEFORMAT='' history 1 | sed 's/^[[:space:]]*[0-9]*[[:space:]]*//')
  if [[ -n "$cmd" && "$cmd" != "$_TDB_LAST_CMD" ]]; then
    _TDB_LAST_CMD="$cmd"
    tdb capture "$cmd"
  fi
  return $exit_code
}

if [[ -z "$PROMPT_COMMAND" ]]; then
  PROMPT_COMMAND="_tdb_prompt_command"
else
  PROMPT_COMMAND="_tdb_prompt_command; $PROMPT_COMMAND"
fi
