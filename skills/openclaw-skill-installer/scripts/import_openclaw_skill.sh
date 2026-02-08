#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Import a skill from OpenClaw/ClawHub/GitHub/local path into Codex skill directories.

Usage:
  import_openclaw_skill.sh [SOURCE] [OPTIONS]

SOURCE (exactly one required):
  --from-dir <path>               Local skill directory (must contain SKILL.md)
  --from-openclaw <skill-name>    Skill in ~/.openclaw/skills (or --openclaw-dir)
  --from-clawhub <slug>           Install via clawhub CLI, then import
  --from-github <repo-url>        Clone repo and import one skill directory

OPTIONS:
  --github-skill-path <path>      Skill path inside cloned repository
  --github-ref <ref>              Git ref for clone (branch/tag/commit-ish)
  --openclaw-dir <path>           OpenClaw skills root (default: ~/.openclaw/skills)
  --skill-name <name>             Override destination folder name
  --mode <copy|symlink>           Install mode (default: copy)
  --scope <user|project|both>     Destination scope (default: user)
  --project-root <path>           Project root for project scope (default: current dir)
  --target-layout <agents|codex-home|both>
                                  Destination layout family (default: agents)
  --dest-dir <path>               Explicit destination root; overrides scope/layout
  --dry-run                       Print actions without writing
  -h, --help                      Show help

Examples:
  import_openclaw_skill.sh --from-openclaw my-skill --scope user
  import_openclaw_skill.sh --from-clawhub my-skill-slug --mode symlink
  import_openclaw_skill.sh --from-github https://github.com/acme/skills.git \
    --github-skill-path skills/my-skill --scope both --target-layout both
EOF
}

log() {
  echo "[openclaw-skill-installer] $*"
}

die() {
  echo "[openclaw-skill-installer] ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

contains_skill_md() {
  [[ -f "$1/SKILL.md" ]]
}

first_skill_dir_under() {
  local root="$1"
  local expected_name="${2:-}"
  local -a skill_md_files=()

  mapfile -t skill_md_files < <(find "$root" -type f -name "SKILL.md" | sort)
  (( ${#skill_md_files[@]} > 0 )) || return 1

  if [[ -n "$expected_name" ]]; then
    local f=""
    for f in "${skill_md_files[@]}"; do
      if [[ "$(basename "$(dirname "$f")")" == "$expected_name" ]]; then
        dirname "$f"
        return 0
      fi
    done
  fi

  if (( ${#skill_md_files[@]} == 1 )); then
    dirname "${skill_md_files[0]}"
    return 0
  fi

  echo "Multiple skill folders detected under $root:" >&2
  local f=""
  for f in "${skill_md_files[@]}"; do
    echo "  - $(dirname "$f")" >&2
  done
  return 2
}

read_frontmatter_name() {
  local skill_md="$1"
  awk '
    BEGIN { in_fm = 0 }
    /^---[[:space:]]*$/ {
      if (in_fm == 0) { in_fm = 1; next }
      else { exit }
    }
    in_fm == 1 && /^name:[[:space:]]*/ {
      sub(/^name:[[:space:]]*/, "", $0)
      gsub(/^["'\'' ]+|["'\'' ]+$/, "", $0)
      print $0
      exit
    }
  ' "$skill_md"
}

SOURCE_TYPE=""
SOURCE_VALUE=""
SOURCE_COUNT=0
GITHUB_SKILL_PATH=""
GITHUB_REF=""
OPENCLAW_DIR="${OPENCLAW_SKILLS_DIR:-$HOME/.openclaw/skills}"
SKILL_NAME_OVERRIDE=""
MODE="copy"
SCOPE="user"
PROJECT_ROOT="$(pwd)"
TARGET_LAYOUT="agents"
DEST_DIR_OVERRIDE=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from-dir)
      ((SOURCE_COUNT += 1))
      SOURCE_TYPE="dir"
      SOURCE_VALUE="${2:-}"
      shift 2
      ;;
    --from-openclaw)
      ((SOURCE_COUNT += 1))
      SOURCE_TYPE="openclaw"
      SOURCE_VALUE="${2:-}"
      shift 2
      ;;
    --from-clawhub)
      ((SOURCE_COUNT += 1))
      SOURCE_TYPE="clawhub"
      SOURCE_VALUE="${2:-}"
      shift 2
      ;;
    --from-github)
      ((SOURCE_COUNT += 1))
      SOURCE_TYPE="github"
      SOURCE_VALUE="${2:-}"
      shift 2
      ;;
    --github-skill-path)
      GITHUB_SKILL_PATH="${2:-}"
      shift 2
      ;;
    --github-ref)
      GITHUB_REF="${2:-}"
      shift 2
      ;;
    --openclaw-dir)
      OPENCLAW_DIR="${2:-}"
      shift 2
      ;;
    --skill-name)
      SKILL_NAME_OVERRIDE="${2:-}"
      shift 2
      ;;
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --scope)
      SCOPE="${2:-}"
      shift 2
      ;;
    --project-root)
      PROJECT_ROOT="${2:-}"
      shift 2
      ;;
    --target-layout)
      TARGET_LAYOUT="${2:-}"
      shift 2
      ;;
    --dest-dir)
      DEST_DIR_OVERRIDE="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

[[ -n "$SOURCE_TYPE" ]] || die "Missing source argument. Use one of --from-dir/--from-openclaw/--from-clawhub/--from-github."
[[ "$SOURCE_COUNT" -eq 1 ]] || die "Provide exactly one source argument."
[[ -n "$SOURCE_VALUE" ]] || die "Source value cannot be empty."
[[ "$MODE" == "copy" || "$MODE" == "symlink" ]] || die "--mode must be copy or symlink."
[[ "$SCOPE" == "user" || "$SCOPE" == "project" || "$SCOPE" == "both" ]] || die "--scope must be user, project, or both."
[[ "$TARGET_LAYOUT" == "agents" || "$TARGET_LAYOUT" == "codex-home" || "$TARGET_LAYOUT" == "both" ]] || die "--target-layout must be agents, codex-home, or both."

if [[ "$SCOPE" != "user" ]]; then
  [[ -d "$PROJECT_ROOT" ]] || die "--project-root does not exist: $PROJECT_ROOT"
fi

TMP_DIR=""
cleanup() {
  if [[ -n "$TMP_DIR" && -d "$TMP_DIR" ]]; then
    rm -rf "$TMP_DIR"
  fi
}
trap cleanup EXIT

SOURCE_DIR=""
case "$SOURCE_TYPE" in
  dir)
    SOURCE_DIR="$SOURCE_VALUE"
    ;;
  openclaw)
    SOURCE_DIR="$OPENCLAW_DIR/$SOURCE_VALUE"
    ;;
  clawhub)
    require_cmd clawhub
    TMP_DIR="$(mktemp -d)"
    log "Installing ClawHub slug '$SOURCE_VALUE' into temp dir"
    (
      cd "$TMP_DIR"
      clawhub install "$SOURCE_VALUE"
    )
    if SOURCE_DIR="$(first_skill_dir_under "$TMP_DIR" "$SOURCE_VALUE")"; then
      :
    else
      rc=$?
      if [[ $rc -eq 2 ]]; then
        die "Multiple skills found after clawhub install. Re-run with --from-dir for explicit path."
      fi
      die "No SKILL.md found in clawhub output."
    fi
    ;;
  github)
    require_cmd git
    TMP_DIR="$(mktemp -d)"
    if [[ -n "$GITHUB_REF" ]]; then
      log "Cloning '$SOURCE_VALUE' (ref: $GITHUB_REF)"
      git clone --depth 1 --branch "$GITHUB_REF" "$SOURCE_VALUE" "$TMP_DIR/repo"
    else
      log "Cloning '$SOURCE_VALUE'"
      git clone --depth 1 "$SOURCE_VALUE" "$TMP_DIR/repo"
    fi
    if [[ -n "$GITHUB_SKILL_PATH" ]]; then
      SOURCE_DIR="$TMP_DIR/repo/$GITHUB_SKILL_PATH"
    else
      if SOURCE_DIR="$(first_skill_dir_under "$TMP_DIR/repo")"; then
        :
      else
        rc=$?
        if [[ $rc -eq 2 ]]; then
          die "Multiple skills found in repository. Use --github-skill-path."
        fi
        die "No SKILL.md found in repository."
      fi
    fi
    ;;
  *)
    die "Internal error: unknown source type '$SOURCE_TYPE'"
    ;;
esac

[[ -d "$SOURCE_DIR" ]] || die "Source directory not found: $SOURCE_DIR"
contains_skill_md "$SOURCE_DIR" || die "Source directory does not contain SKILL.md: $SOURCE_DIR"
SOURCE_DIR="$(realpath "$SOURCE_DIR")"

if [[ "$MODE" == "symlink" && ( "$SOURCE_TYPE" == "clawhub" || "$SOURCE_TYPE" == "github" ) ]]; then
  die "Symlink mode cannot be used with --from-clawhub/--from-github because source is temporary. Use --mode copy or install from a persistent local path."
fi

RESOLVED_SKILL_NAME="$SKILL_NAME_OVERRIDE"
if [[ -z "$RESOLVED_SKILL_NAME" ]]; then
  RESOLVED_SKILL_NAME="$(read_frontmatter_name "$SOURCE_DIR/SKILL.md")"
fi
if [[ -z "$RESOLVED_SKILL_NAME" ]]; then
  RESOLVED_SKILL_NAME="$(basename "$SOURCE_DIR")"
fi

declare -a DEST_ROOTS=()
if [[ -n "$DEST_DIR_OVERRIDE" ]]; then
  DEST_ROOTS+=("$DEST_DIR_OVERRIDE")
else
  add_scope_destinations() {
    local scope="$1"
    local layout="$2"
    if [[ "$layout" == "agents" || "$layout" == "both" ]]; then
      if [[ "$scope" == "user" ]]; then
        DEST_ROOTS+=("$HOME/.agents/skills")
      else
        DEST_ROOTS+=("$PROJECT_ROOT/.agents/skills")
      fi
    fi
    if [[ "$layout" == "codex-home" || "$layout" == "both" ]]; then
      if [[ "$scope" == "user" ]]; then
        DEST_ROOTS+=("${CODEX_HOME:-$HOME/.codex}/skills")
      else
        DEST_ROOTS+=("$PROJECT_ROOT/.codex/skills")
      fi
    fi
  }

  if [[ "$SCOPE" == "user" || "$SCOPE" == "both" ]]; then
    add_scope_destinations "user" "$TARGET_LAYOUT"
  fi
  if [[ "$SCOPE" == "project" || "$SCOPE" == "both" ]]; then
    add_scope_destinations "project" "$TARGET_LAYOUT"
  fi
fi

(( ${#DEST_ROOTS[@]} > 0 )) || die "No destination roots resolved."

log "Source directory: $SOURCE_DIR"
log "Skill name: $RESOLVED_SKILL_NAME"
log "Mode: $MODE"
log "Destinations:"
for root in "${DEST_ROOTS[@]}"; do
  log "  - $root/$RESOLVED_SKILL_NAME"
done

for root in "${DEST_ROOTS[@]}"; do
  target="$root/$RESOLVED_SKILL_NAME"
  if [[ -e "$target" || -L "$target" ]]; then
    die "Target already exists: $target"
  fi
done

if [[ "$DRY_RUN" -eq 1 ]]; then
  log "Dry run only; no files were written."
  exit 0
fi

for root in "${DEST_ROOTS[@]}"; do
  target="$root/$RESOLVED_SKILL_NAME"
  mkdir -p "$root"
  if [[ "$MODE" == "copy" ]]; then
    cp -R "$SOURCE_DIR" "$target"
  else
    ln -s "$SOURCE_DIR" "$target"
  fi
  log "Installed: $target"
done

log "Completed successfully."
