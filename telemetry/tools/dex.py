#!/usr/bin/env python3
"""Minimal DEX inspector (no external deps) for statically analyzing Android .dex / .apk artifacts.

Subcommands (accepts either a .apk or a .dex; .apk scans every classes*.dex member):
  strings <file> [needle]   list the string pool (index + value); with <needle>, only matching entries
  xref <file> <needle>      for every string containing <needle>, list the classes/methods whose code
                            loads it via const-string (0x1a) / const-string/jumbo (0x1b)
  classes <file> [needle]   class descriptors (+ direct/virtual method counts); with <needle>, filtered
  code <file> <descriptor>  method table of one class (descriptor form, e.g. Ldefpackage/xru;)

Why: R8 full-mode output often defeats source-level decompilers; string->code cross references stay
usable and are the cheapest way to attribute a literal (endpoint, header name, pref key) to an owner
class even when the enclosing method fails to decompile.
"""
import sys, struct, zipfile

# instruction width in 16-bit code units, per DEX opcode table (0x1a/0x1b handled by the scanner)
WIDTHS = {}


def _init_widths():
    for op in range(0x00, 0x3E):
        WIDTHS[op] = 1
    for op in (0x02, 0x05, 0x08, 0x13, 0x15, 0x16, 0x19, 0x1C, 0x1F, 0x20, 0x22, 0x23,
               0x29, 0x2D, 0x2E, 0x2F, 0x30, 0x31):
        WIDTHS[op] = 2
    for op in (0x03, 0x06, 0x09, 0x14, 0x17, 0x24, 0x25, 0x26, 0x2A, 0x2B, 0x2C,
               0x6E, 0x6F, 0x70, 0x71, 0x72, 0x74, 0x75, 0x76, 0x77, 0x78):
        WIDTHS[op] = 3
    WIDTHS[0x18] = 5
    for op in range(0x32, 0x3E):
        WIDTHS[op] = 2
    for op in range(0x3E, 0x44):
        WIDTHS[op] = 1
    for op in range(0x44, 0x52):
        WIDTHS[op] = 1
    for op in range(0x52, 0x60):
        WIDTHS[op] = 2
    for op in range(0x60, 0x6E):
        WIDTHS[op] = 2
    for op in range(0x73, 0x7C):
        WIDTHS[op] = 1
    for op in range(0x7B, 0x90):
        WIDTHS[op] = 1
    for op in range(0x90, 0xB0):
        WIDTHS[op] = 2
    for op in range(0xB0, 0xD0):
        WIDTHS[op] = 1
    for op in range(0xD0, 0xE3):
        WIDTHS[op] = 2
    for op in range(0xE3, 0xFA):
        WIDTHS[op] = 1
    WIDTHS[0xFA] = 4; WIDTHS[0xFB] = 4
    WIDTHS[0xFC] = 3; WIDTHS[0xFD] = 3
    WIDTHS[0xFE] = 2; WIDTHS[0xFF] = 2


_init_widths()


class Dex:
    def __init__(self, data, name="<dex>"):
        self.b = data
        self.name = name
        if data[:4] != b"dex\n":
            raise ValueError("%s: not a dex file (magic %r)" % (name, data[:8]))
        (self.string_ids_size, self.string_ids_off, self.type_ids_size, self.type_ids_off,
         _proto_size, _proto_off, _field_size, _field_off, self.method_ids_size, self.method_ids_off,
         self.class_defs_size, self.class_defs_off, _data_size, _data_off) = struct.unpack_from("<14I", data, 0x38)

    def uleb(self, off):
        r = 0; s = 0
        while True:
            x = self.b[off]; off += 1
            r |= (x & 0x7f) << s
            if not (x & 0x80):
                return r, off
            s += 7

    def string(self, idx):
        off = struct.unpack_from("<I", self.b, self.string_ids_off + 4 * idx)[0]
        n, p = self.uleb(off)
        return self.b[p:p + n].decode("utf-8", "replace")

    def type_desc(self, idx):
        si = struct.unpack_from("<I", self.b, self.type_ids_off + 4 * idx)[0]
        return self.string(si)

    def method_sig(self, idx):
        class_idx, _proto, name_idx = struct.unpack_from("<HHI", self.b, self.method_ids_off + 8 * idx)
        return "%s.%s" % (self.type_desc(class_idx), self.string(name_idx))

    def each_class(self):
        """yield (descriptor, [(method_idx, code_off)])"""
        for ci in range(self.class_defs_size):
            off = self.class_defs_off + 32 * ci
            class_idx, _af, _sup, _if, _src, _ann, class_data_off, _sv = struct.unpack_from("<8I", self.b, off)
            desc = self.type_desc(class_idx)
            methods = []
            if class_data_off:
                o = class_data_off
                sf, o = self.uleb(o); inf, o = self.uleb(o)
                dm, o = self.uleb(o); vm, o = self.uleb(o)
                for _ in range(sf + inf):
                    _, o = self.uleb(o); _, o = self.uleb(o)
                for count in (dm, vm):  # direct_methods and virtual_methods are separate diff-coded arrays
                    midx = 0
                    for _ in range(count):
                        diff, o = self.uleb(o); _, o = self.uleb(o); code_off, o = self.uleb(o)
                        midx += diff
                        methods.append((midx, code_off))
            yield desc, methods

    def scan_const_string(self, want):
        """return [(class_desc, method_sig)] for every method whose code loads string index `want`."""
        for desc, methods in self.each_class():
            for midx, code_off in methods:
                if not code_off or code_off + 16 > len(self.b):
                    continue
                insns_size, = struct.unpack_from("<I", self.b, code_off + 12)
                base = code_off + 16
                if insns_size == 0 or base + 2 * insns_size > len(self.b):
                    continue
                i = 0
                while i < insns_size:
                    code = struct.unpack_from("<H", self.b, base + 2 * i)[0]
                    op = code & 0xFF
                    if op == 0x1A:
                        sid = struct.unpack_from("<H", self.b, base + 2 * (i + 1))[0]
                        i += 2
                    elif op == 0x1B:
                        sid = struct.unpack_from("<I", self.b, base + 2 * (i + 1))[0]
                        i += 3
                    else:
                        i += WIDTHS.get(op, 1)
                        continue
                    if sid == want:
                        yield desc, self.method_sig(midx)
                        break


def load(path):
    """return [(name, Dex)] — .apk yields one Dex per classes*.dex member."""
    if path.lower().endswith(".apk"):
        out = []
        with zipfile.ZipFile(path) as z:
            for nm in sorted(n for n in z.namelist() if n.endswith(".dex")):
                out.append((nm, Dex(z.read(nm), nm)))
        if not out:
            raise ValueError("%s: no .dex member" % path)
        return out
    with open(path, "rb") as fh:
        return [(path, Dex(fh.read(), path))]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    dexes = load(sys.argv[2])
    needle = sys.argv[3] if len(sys.argv) > 3 else None

    if cmd == "strings":
        for name, d in dexes:
            for i in range(d.string_ids_size):
                s = d.string(i)
                if needle is None or needle in s:
                    print("%s\t%d\t%s" % (name, i, s))
    elif cmd == "xref":
        if needle is None:
            print(__doc__); return 1
        for name, d in dexes:
            for i in range(d.string_ids_size):
                s = d.string(i)
                if needle not in s:
                    continue
                print("%s\tstring[%d]\t%s" % (name, i, s))
                for desc, msig in d.scan_const_string(i):
                    print("    %s\t%s" % (desc, msig))
    elif cmd == "classes":
        for name, d in dexes:
            for desc, methods in d.each_class():
                if needle is not None and needle not in desc:
                    continue
                print("%s\t%s\tmethods=%d" % (name, desc, len(methods)))
    elif cmd == "code":
        if needle is None:
            print(__doc__); return 1
        for name, d in dexes:
            for desc, methods in d.each_class():
                if desc != needle:
                    continue
                print("%s\t%s" % (name, desc))
                for midx, code_off in methods:
                    print("    code_off=0x%x\t%s" % (code_off, d.method_sig(midx)))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
