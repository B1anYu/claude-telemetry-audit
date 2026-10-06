#!/usr/bin/env python3
"""Minimal Mach-O inspector (no external deps) for statically analyzing darwin .node/.dylib/.dylib-less binaries.

Subcommands:
  info <file>                 header(s), arch(s), uuid, build version, dylibs, weak dylibs, install name, section table
  exports <file>              exported symbol names (export trie), one per line
  symbols <file>              all names in LC_SYMTAB string table (defined + undefined), with N_UNDF marker
  imports <file>              undefined (imported) symbol names only
  section <file> <sectname>   dump raw bytes of a section (all archs) to stdout
  strings <file> [minlen]     printable strings from the whole file (min length default 5)
"""
import sys, struct, re

MH_MAGIC_64 = 0xFEEDFACF
MH_CIGAM_64 = 0xCFFAEDFE
FAT_MAGIC = 0xCAFEBABE
FAT_MAGIC_64 = 0xCAFEBABF

LC_SEGMENT_64 = 0x19
LC_SYMTAB = 0x2
LC_UUID = 0x1B
LC_LOAD_DYLIB = 0xC
LC_LOAD_WEAK_DYLIB = 0x80000018
LC_REEXPORT_DYLIB = 0x8000001F
LC_ID_DYLIB = 0xD
LC_BUILD_VERSION = 0x32
LC_VERSION_MIN_MACOSX = 0x24
LC_DYLD_INFO = 0x22
LC_DYLD_INFO_ONLY = 0x80000022
LC_DYLD_EXPORTS_TRIE = 0x80000033
LC_DYLD_CHAINED_FIXUPS = 0x80000034
LC_CODE_SIGNATURE = 0x1D
LC_MAIN = 0x80000028

PLATFORMS = {1: "macOS", 2: "iOS", 3: "tvOS", 4: "watchOS", 5: "bridgeOS", 6: "macCatalyst", 7: "iOSSimulator"}


def uleb(b, i):
    r = 0; s = 0
    while True:
        x = b[i]; i += 1
        r |= (x & 0x7F) << s
        if not x & 0x80:
            return r, i
        s += 7


class Slice:
    def __init__(self, data, off=0, name="thin"):
        self.d = data
        self.base = off
        magic = struct.unpack_from("<I", data, off)[0]
        if magic != MH_MAGIC_64:
            raise ValueError("not MH_MAGIC_64 (0x%x)" % magic)
        self.cputype, self.cpusubtype, self.filetype, self.ncmds, self.sizeofcmds, self.flags, _ = \
            struct.unpack_from("<7I", data, off + 4)
        self.cpu = {0x0100000C: "arm64", 0x01000007: "x86_64"}.get(self.cputype, hex(self.cputype))
        self.sections, self.dylibs, self.weak_dylibs, self.install_name = [], [], [], None
        self.uuid, self.build, self.exports_trie, self.symtab = None, None, None, None
        p = off + 32
        for _ in range(self.ncmds):
            cmd, cmdsize = struct.unpack_from("<2I", data, p)
            if cmd == LC_SEGMENT_64:
                segname = data[p + 8:p + 24].split(b"\0")[0].decode("latin1")
                nsects = struct.unpack_from("<I", data, p + 64)[0]
                for k in range(nsects):
                    s = p + 72 + k * 80
                    sect = data[s:s + 16].split(b"\0")[0].decode("latin1")
                    soff, ssize = struct.unpack_from("<QI", data, s + 32)[0], struct.unpack_from("<Q", data, s + 40)[0]
                    off2, = struct.unpack_from("<I", data, s + 48)
                    self.sections.append((segname, sect, off2, ssize, soff))
            elif cmd == LC_UUID:
                self.uuid = data[p + 8:p + 24].hex()
            elif cmd in (LC_LOAD_DYLIB, LC_LOAD_WEAK_DYLIB, LC_REEXPORT_DYLIB, LC_ID_DYLIB):
                noff, = struct.unpack_from("<I", data, p + 8)
                nm = data[p + noff:p + cmdsize].split(b"\0")[0].decode("latin1")
                # LC_ID_DYLIB is this binary's own install name, not a dependency;
                # LC_LOAD_WEAK_DYLIB is a dependency that may be absent at runtime.
                # Keep them out of `dylibs` so the list means "dependencies".
                if cmd == LC_ID_DYLIB:
                    self.install_name = nm
                elif cmd == LC_LOAD_WEAK_DYLIB:
                    self.weak_dylibs.append(nm)
                else:
                    self.dylibs.append(nm)
            elif cmd == LC_BUILD_VERSION:
                plat, minos, sdk, _nt = struct.unpack_from("<4I", data, p + 8)
                self.build = "%s minos=%d.%d.%d sdk=%d.%d.%d" % (
                    PLATFORMS.get(plat, plat), minos >> 16, (minos >> 8) & 0xFF, minos & 0xFF,
                    sdk >> 16, (sdk >> 8) & 0xFF, sdk & 0xFF)
            elif cmd == LC_VERSION_MIN_MACOSX:
                v, s = struct.unpack_from("<2I", data, p + 8)
                self.build = "macOS minos=%d.%d.%d sdk=%d.%d.%d" % (
                    v >> 16, (v >> 8) & 0xFF, v & 0xFF, s >> 16, (s >> 8) & 0xFF, s & 0xFF)
            elif cmd in (LC_DYLD_INFO, LC_DYLD_INFO_ONLY):
                eo, es = struct.unpack_from("<2I", data, p + 40)
                if es:
                    self.exports_trie = (eo, es)
            elif cmd == LC_DYLD_EXPORTS_TRIE:
                do, ds = struct.unpack_from("<2I", data, p + 8)
                self.exports_trie = (do, ds)
            elif cmd == LC_SYMTAB:
                self.symtab = struct.unpack_from("<4I", data, p + 8)  # symoff,nsyms,stroff,strsize
            p += cmdsize

    def sect(self, name):
        for sg, sn, off, size, _addr in self.sections:
            if sn == name:
                return self.d[self.base + off:self.base + off + size]
        return b""

    def exports(self):
        """Walk the dyld export trie. Returns (names, ok) where ok=False means the trie looked malformed."""
        if not self.exports_trie:
            return [], False
        off, size = self.exports_trie
        b = self.d[self.base + off:self.base + off + size]
        out = set()
        stack = [(0, "", 0)]
        seen_nodes = 0
        ok = True
        while stack:
            i, prefix, depth = stack.pop()
            if i >= len(b) or depth > 400:
                ok = False
                continue
            seen_nodes += 1
            if seen_nodes > 4 * len(b):
                ok = False
                break
            try:
                j = i
                tsize, j = uleb(b, j)
            except IndexError:
                ok = False
                continue
            if tsize:
                p_payload = j
                try:
                    flags, j = uleb(b, j)
                    if flags & 0x08:  # REEXPORT
                        _ord, j = uleb(b, j)
                        _nm, j = uleb(b, j)
                    elif flags & 0x10:  # STUB_AND_RESOLVER
                        _a, j = uleb(b, j)
                        _r, j = uleb(b, j)
                    else:
                        _a, j = uleb(b, j)
                except IndexError:
                    ok = False
                    continue
                out.add(prefix)
                j = p_payload + tsize
                if j > len(b):
                    ok = False
                    continue
            if j >= len(b):
                continue
            nchild = b[j]; j += 1
            for _ in range(nchild):
                if j >= len(b):
                    ok = False
                    break
                k = j
                while k < len(b) and b[k] != 0:
                    k += 1
                if k >= len(b):
                    ok = False
                    break
                edge = b[j:k].decode("latin1")
                if k + 1 >= len(b):
                    ok = False
                    break
                child, j = uleb(b, k + 1)
                if child == i:
                    ok = False
                    continue
                stack.append((child, prefix + edge, depth + 1))
        return sorted(out), ok

    def symtab_names(self):
        if not self.symtab:
            return []
        symoff, nsyms, stroff, strsize = self.symtab
        syms = self.d[self.base + symoff:self.base + symoff + nsyms * 16]
        strs = self.d[self.base + stroff:self.base + stroff + strsize]
        out = []
        for i in range(nsyms):
            strx, ntype = struct.unpack_from("<IB", syms, i * 16)[0], syms[i * 16 + 4]
            nm = strs[strx:strs.find(b"\0", strx)].decode("latin1")
            if nm:
                out.append(("UNDF" if (ntype & 0x0E) == 0 else "DEF", nm))
        return out


def slices(data):
    if len(data) < 8:
        return []
    magic = struct.unpack_from(">I", data, 0)[0]
    if magic in (FAT_MAGIC, FAT_MAGIC_64):
        n = struct.unpack_from(">I", data, 4)[0]
        out = []
        for i in range(n):
            if magic == FAT_MAGIC:
                ct, cs, off, size, _al = struct.unpack_from(">5I", data, 8 + i * 20)
            else:
                ct, cs, off, size, _al = struct.unpack_from(">2I2Q", data, 8 + i * 32)
            out.append(Slice(data, off))
        return out
    return [Slice(data, 0)]


def main():
    if len(sys.argv) < 3:
        print(__doc__); return 1
    cmd, path = sys.argv[1], sys.argv[2]
    data = open(path, "rb").read()
    sl = slices(data)
    if cmd == "info":
        print("file:", path, "size:", len(data), "archs:", len(sl))
        for i, s in enumerate(sl):
            print("\n== slice %d: %s (%s) filetype=%d flags=0x%x uuid=%s" % (i, s.cpu, hex(s.cpusubtype), s.filetype, s.flags, s.uuid))
            print("   build:", s.build)
            print("   dylibs (%d):" % len(s.dylibs))
            for d in s.dylibs:
                print("     ", d)
            if s.weak_dylibs:
                print("   weak dylibs (%d; may be absent at runtime):" % len(s.weak_dylibs))
                for d in s.weak_dylibs:
                    print("     ", d)
            if s.install_name:
                print("   install name:", s.install_name)
            print("   sections (%d):" % len(s.sections))
            for sg, sn, off, size, addr in s.sections:
                if size:
                    print("     %-16s %-22s off=%-10d size=%-10d addr=0x%x" % (sg, sn, off, size, addr))
    elif cmd == "exports":
        for s in sl:
            names, ok = s.exports()
            if not ok: print("WARN: trie malformed/truncated", file=sys.stderr)
            for e in names:
                print(e)
    elif cmd in ("symbols", "imports"):
        for s in sl:
            for kind, nm in s.symtab_names():
                if cmd == "imports" and kind != "UNDF":
                    continue
                print(kind, nm)
    elif cmd == "section":
        want = sys.argv[3]
        for s in sl:
            b = s.sect(want)
            sys.stdout.buffer.write(b)
    elif cmd == "strings":
        ml = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        pat = re.compile(rb"[\x20-\x7e]{%d,}" % ml)
        for m in pat.finditer(data):
            print(m.group().decode("latin1"))
    else:
        print(__doc__); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
