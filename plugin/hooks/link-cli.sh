#!/usr/bin/env sh
# Link the bundled CLI into ~/.local/bin. A hook is the only place
# ${CLAUDE_PLUGIN_ROOT} is substituted, so this is what spares every project a
# manual `ln -s`. Silent and idempotent: prints only when it changes something.
set -e

PLUGIN_ROOT="${1:-$CLAUDE_PLUGIN_ROOT}"
[ -n "$PLUGIN_ROOT" ] || exit 0

TARGET="$PLUGIN_ROOT/bin/epod"
[ -x "$TARGET" ] || exit 0

BIN_DIR="$HOME/.local/bin"
LINK="$BIN_DIR/epod"

# Never clobber a real file — only this plugin's own symlink is ours to move.
if [ -e "$LINK" ] && [ ! -L "$LINK" ]; then
  echo "epod plugin: $LINK exists and is not a symlink; leaving it alone." >&2
  exit 0
fi

if [ "$(readlink -f "$LINK" 2>/dev/null)" = "$(readlink -f "$TARGET")" ]; then
  exit 0
fi

mkdir -p "$BIN_DIR"
ln -sfn "$TARGET" "$LINK"
echo "epod plugin: linked $LINK -> $TARGET"

# Said once, at the moment of install, and only for the one pack that needs a
# credential of its own: `epod vi` talks to a text gateway rather than to the
# store, so no .mcp.json can supply its key. Every other group works untouched
# without this, which is why it is a notice and not a failure.
VI_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/vi-natural/config.json"
if [ ! -f "$VI_CONFIG" ] && [ -z "$MUSETOOLS_API_KEY" ]; then
  echo "epod plugin: \`epod vi\` needs a gateway endpoint and key — run: epod vi install --key <key>" >&2
fi

# Retire the per-script commands this plugin used to install.
for stale in epod-store-init epod-skill-root; do
  path="$BIN_DIR/$stale"
  case "$(readlink -f "$path" 2>/dev/null)" in
    "$PLUGIN_ROOT"/*) rm -f "$path"; echo "epod plugin: removed superseded $path" ;;
  esac
done
