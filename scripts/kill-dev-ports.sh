#!/usr/bin/env bash
set -euo pipefail

ports=(8000 5173)
dry_run=false
diagnose=false

for arg in "$@"; do
  case "$arg" in
    --dry-run)
      dry_run=true
      ;;
    --diagnose)
      diagnose=true
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Usage: $0 [--dry-run] [--diagnose]" >&2
      exit 2
      ;;
  esac
done

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

pids_for_port() {
  local port="$1"

  if command_exists lsof; then
    lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
  fi

  if command_exists ss; then
    ss -ltnp "sport = :$port" 2>/dev/null \
      | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p'
  fi

  if command_exists fuser; then
    fuser "${port}/tcp" 2>/dev/null | tr ' ' '\n' || true
  fi
}

diagnose_port() {
  local port="$1"

  echo "== Port $port diagnostics =="
  if command_exists lsof; then
    echo "-- lsof --"
    lsof -nP -iTCP:"$port" 2>/dev/null || true
  fi

  if command_exists ss; then
    echo "-- ss --"
    ss -ltnp "sport = :$port" 2>/dev/null || true
  fi

  if command_exists fuser; then
    echo "-- fuser --"
    fuser -v "${port}/tcp" 2>&1 || true
  fi
}

kill_pids() {
  local port="$1"
  shift
  local pids=("$@")

  if [[ "${#pids[@]}" -eq 0 ]]; then
    echo "Port $port: no listening process found"
    return
  fi

  echo "Port $port: stopping PID(s) ${pids[*]}"

  if [[ "$dry_run" == true ]]; then
    return
  fi

  kill "${pids[@]}" 2>/dev/null || true
  sleep 1

  local still_running=()
  for pid in "${pids[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      still_running+=("$pid")
    fi
  done

  if [[ "${#still_running[@]}" -gt 0 ]]; then
    echo "Port $port: force killing PID(s) ${still_running[*]}"
    kill -9 "${still_running[@]}" 2>/dev/null || true
  fi
}

if ! command_exists lsof && ! command_exists ss && ! command_exists fuser; then
  echo "Need one of: lsof, ss, or fuser" >&2
  exit 1
fi

for port in "${ports[@]}"; do
  if [[ "$diagnose" == true ]]; then
    diagnose_port "$port"
  fi
  mapfile -t pids < <(pids_for_port "$port" | sed '/^$/d' | sort -u)
  kill_pids "$port" "${pids[@]}"
done
