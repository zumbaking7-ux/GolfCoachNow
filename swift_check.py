"""Cheap structural checks on the iOS sources.

There is no Mac on this project, so for a long time the only thing standing
between a Swift edit and production was a brace count. CI compiles it properly
now, but a round trip to a hosted Mac is minutes and this is seconds, so it is
worth running before pushing.

It checks three things, and the third is here because it actually happened:

  balanced braces and parens   - catches a truncated edit
  no references to symbols
    that no longer exist       - catches a half-finished rename
  no string literal that runs
    off the end of its line    - catches an escape that was turned into a real
                                 newline somewhere between a patch script and
                                 the file, which is legal in most languages and
                                 a compile error in Swift

That last one cost a full CI cycle. Braces balanced, so every check passed and
the file could not compile.

    python3 swift_check.py
"""

import glob
import io
import re
import sys

BS = chr(92)
STRING = re.compile('"(?:[^"' + BS + BS + ']|' + BS + BS + '.)*"')
COMMENT = re.compile("//[^" + BS + "n]*")
SOURCES = "iosapp/GolfCoachNow/**/*.swift"


def sources():
    return sorted(glob.glob(SOURCES, recursive=True))


def strip(text):
    """Remove strings and comments, so their contents never count."""
    return COMMENT.sub("", STRING.sub('""', text))


def check_balance():
    problems = []
    for path in sources():
        body = strip(io.open(path, encoding="utf-8").read())
        braces = body.count("{") - body.count("}")
        parens = body.count("(") - body.count(")")
        if braces or parens:
            problems.append("%s: braces %+d parens %+d" % (path, braces, parens))
    return problems


def check_unterminated_strings():
    """A literal that does not close on the line it opened on.

    Swift has no multi-line plain string: a real newline inside quotes is an
    error. Multi-line literals use three quotes, which are skipped here.
    """
    problems = []
    for path in sources():
        lines = io.open(path, encoding="utf-8").read().split("\n")
        inside_multiline = False
        for number, line in enumerate(lines, 1):
            if line.count('"""') % 2 == 1:
                inside_multiline = not inside_multiline
                continue
            if inside_multiline:
                continue
            rest = STRING.sub("", line)
            code = rest.split("//")[0]
            if code.count('"') % 2 == 1:
                problems.append("%s:%d  %s" % (path, number, line.strip()[:70]))
    return problems


def check_dangling(symbols):
    problems = []
    for path in sources():
        for number, line in enumerate(io.open(path, encoding="utf-8").read().split("\n"), 1):
            if line.strip().startswith("//"):
                continue
            for symbol in symbols:
                if symbol in line:
                    problems.append("%s:%d  %s" % (path, number, symbol))
    return problems


# Symbols removed during this contract. A reference to one of these is a
# rename that did not finish.
REMOVED = [
    "ModuleTapGesture",
    "playInstructionalVideo",
    "rememberedName",
    "Theme.bannerHeight",
]


def main():
    checks = [
        ("brace and paren balance", check_balance()),
        ("unterminated string literals", check_unterminated_strings()),
        ("references to removed symbols", check_dangling(REMOVED)),
    ]
    failed = False
    for label, problems in checks:
        if problems:
            failed = True
            print("FAIL  %s" % label)
            for p in problems:
                print("        %s" % p)
        else:
            print("ok    %s" % label)

    print()
    print("%d swift files checked" % len(sources()))
    if failed:
        print("These are the cheap faults. A clean run here does not mean it")
        print("compiles - only the CI build on a real Mac can say that.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
