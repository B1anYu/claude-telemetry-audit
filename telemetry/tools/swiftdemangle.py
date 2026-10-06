#!/usr/bin/env python3
"""Crude Swift mangled-name -> dotted-path extractor (no swift toolchain needed).

Usage: swiftdemangle.py <file-with-symbols-one-per-line>
Outputs: "<dotted.path>    <raw>" for lines that look like Swift symbols.
Not a full demangler: it recovers the identifier path (module.Type.member) and the
trailing function/type kind codes are left as-is.
"""
import re, sys

KIND = {
    "F": "func", "f": "func", "Z": "static", "y": "getter", "Y": "setter",
    "O": "enum", "V": "struct", "C": "class", "P": "protocol", "S": "typealias",
    "M": "metatype", "W": "witness", "T": "init", "i": "init", "c": "init",
    "g": "getter", "s": "setter", "m": "method", "v": "var", "a": "arg",
}


def extract(sym):
    s = sym[1:] if sym.startswith("_") else sym
    if not s.startswith("$s"):
        return None
    i = 2
    parts = []
    n = len(s)
    while i < n:
        m = re.match(r"(\d+)", s[i:])
        if not m:
            break
        ln = int(m.group(1))
        j = i + len(m.group(1))
        if ln <= 0 or j + ln > n:
            break
        token = s[j:j + ln]
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", token):
            break
        parts.append(token)
        i = j + ln
    if not parts:
        return None
    tail = s[i:]
    kind = KIND.get(tail[:1], "") if tail else ""
    return ".".join(parts), kind, tail


def main():
    path = sys.argv[1]
    seen = set()
    for line in open(path, encoding="utf-8", errors="replace"):
        raw = line.strip()
        if not raw:
            continue
        r = extract(raw)
        if not r:
            continue
        dotted, kind, tail = r
        key = (dotted, tail[:1])
        if key in seen:
            continue
        seen.add(key)
        print("%-90s %-7s %s" % (dotted, kind, raw))


if __name__ == "__main__":
    main()
