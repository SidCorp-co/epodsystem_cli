#!/usr/bin/env python3
"""epod — one entry point over the page CLI (epod.py) and the store bootstrap (store_init.py).

  epod <page command>     context, list, build-doc, sync-md, get-block, put-theme...
  epod store <command>    doctor, install, sync-nav, home, verify
  epod skill-root         print the skill directory (references/, assets/, scripts/)
"""
import os
import sys

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPTS_DIR)
sys.path.insert(0, SCRIPTS_DIR)

GROUPS_HELP = (
    "\ngroups:\n"
    "  store <command>  bootstrap a store: doctor, install, sync-nav, home, verify\n"
    "                   (epod store --help)\n"
    "  skill-root       print the skill directory holding references/ and assets/\n"
)


def main():
    argv = sys.argv[1:]

    if argv and argv[0] == "store":
        import store_init
        sys.argv = ["epod store"] + argv[1:]
        return store_init.main()

    if argv and argv[0] == "skill-root":
        print(SKILL_DIR)
        return

    import epod

    # epod.py's parser knows nothing of the groups above, so append them to its help.
    if not argv or argv[0] in ("-h", "--help", "help"):
        sys.argv = ["epod", "--help"]
        code = 0
        try:
            epod.main()
        except SystemExit as exit_:
            code = exit_.code
        print(GROUPS_HELP)
        sys.exit(code)

    sys.argv = ["epod"] + argv
    return epod.main()


if __name__ == "__main__":
    main()
