#!/usr/bin/env python3
"""OS integrity scanner for the AIOS. Read-only. Prints a red/yellow/green report.

Mechanical complement to /audit (which scores strategy via the Four-Cs). This one
checks whether the routing table still matches reality: dead refs, unrouted files,
stale feeds, failing crons.

Usage: python3 check.py [PROJECT_ROOT]   (default: cwd)

The parser rules below are the ones that separated the 3 real findings from the 10
false positives on the 2026-07-23 run - keep them:
  - strip `bash `/`node `/`python3 ` command prefixes before treating a token as a path
  - skip glob (`*`) and placeholder (`<id>`, `{tool}`, `YYYY`) tokens
  - resolve sibling (`../`) + source-relative + parent-relative candidates
"""
import os, re, sys, time, subprocess, urllib.parse

ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.getcwd()
LABEL_PREFIX = "com.you.aios"  # launchd label prefix of your AIOS jobs
# auto-memory MEMORY.md for this project, if present
_slug = ROOT.replace("/", "-")
MEMDIR = os.path.expanduser(f"~/.claude/projects/{_slug}/memory")

ROUTERS = [(os.path.join(ROOT, "CLAUDE.md"), ROOT),
           (os.path.join(ROOT, "connections.md"), ROOT),
           (os.path.join(MEMDIR, "MEMORY.md"), MEMDIR)]

LINK = re.compile(r'\]\(([^)\s]+)\)')
TICK = re.compile(r'`([^`]+)`')
CMD_WORDS = ("bash", "sh", "node", "python3", "python", "source", ".")

def strip_cmd(t):
    parts = t.split()
    if len(parts) > 1 and parts[0] in CMD_WORDS:
        for p in parts[1:]:
            if "/" in p or p.endswith((".md",".py",".sh",".json",".html",".mjs",".txt")):
                return p
    return t

def is_placeholder(t):
    return bool(re.search(r'<[^>]*>|\{[^}]*\}|YYYY|/\*|\*', t))

def is_slash_cmd(t):
    return bool(re.match(r'^/[a-z][a-z0-9-]*$', t))

def is_github_slug(t):
    return bool(re.match(r'^[A-Za-z0-9_-]+/[A-Za-z0-9._-]+$', t)) and "." not in t.split("/")[0] \
        and not os.path.exists(os.path.join(ROOT, t))

def looks_like_path(t):
    t = t.strip()
    if not t or t.startswith(("http://","https://","mailto:","#","www.")): return False
    if is_slash_cmd(t) or is_placeholder(t): return False
    if t.startswith("file:///"): return True
    if " " in t and "/" not in t and "%20" not in t: return False
    if "/" in t: return True
    return t.endswith((".md",".py",".sh",".json",".html",".mjs"))

def collect():
    refs = {}
    for fp, base in ROUTERS:
        try: c = open(fp, encoding="utf-8", errors="replace").read()
        except OSError: continue
        toks = set(LINK.findall(c))
        for m in TICK.findall(c):
            if looks_like_path(strip_cmd(m)): toks.add(m)
        for t in toks:
            t = strip_cmd(urllib.parse.unquote(t).split("#")[0].strip())
            if t.startswith("file:///"): t = t[7:]
            if not looks_like_path(t): continue
            if is_github_slug(t): continue
            refs.setdefault(t, {"base": base, "srcs": set()})["srcs"].add(os.path.basename(fp))
    return refs

def resolve_exists(t, base):
    if t.startswith("~"): cands = [os.path.expanduser(t)]
    elif t.startswith("/"): cands = [t]
    elif t.startswith("../"): cands = [os.path.normpath(os.path.join(ROOT, t))]
    else: cands = [os.path.join(base, t), os.path.join(ROOT, t),
                   os.path.normpath(os.path.join(ROOT, "..", t))]
    return any(os.path.exists(c) for c in cands)

def age_days(p):
    try: return (time.time() - os.path.getmtime(p)) / 86400
    except OSError: return None

def main():
    refs = collect()
    dead = sorted((t, sorted(i["srcs"])) for t, i in refs.items() if not resolve_exists(t, i["base"]))
    ok = len(refs) - len(dead)
    print(f"=== ROUTING INTEGRITY ===  OK: {ok}   DEAD: {len(dead)}")
    for t, srcs in dead:
        print(f"  DEAD  {t}   <- {','.join(srcs)}")

    # index truth: top-level items not named in any router
    allc = ""
    for fp, _ in ROUTERS:
        try: allc += open(fp, encoding="utf-8", errors="replace").read() + " "
        except OSError: pass
    IGNORE = {".git",".tmp",".planning",".claude",".playwright-mcp",".gitignore",
              ".mcp.json",".DS_Store","CLAUDE.md","connections.md","README.md","LICENSE"}
    unrouted = []
    for n in sorted(os.listdir(ROOT)):
        if n in IGNORE or n.startswith("."): continue
        stem = os.path.splitext(n)[0]
        if n in allc or n+"/" in allc or stem in allc: continue
        unrouted.append(n + ("/" if os.path.isdir(os.path.join(ROOT, n)) else ""))
    print(f"\n=== INDEX TRUTH (on disk, unrouted) ===  {len(unrouted)} items")
    for u in unrouted: print("  ?  " + u)

    # freshness
    print("\n=== FRESHNESS ===")
    for rel in ["decisions/log.md", "parking-lot.md"]:
        a = age_days(os.path.join(ROOT, rel))
        print(f"  {rel}: {'MISSING' if a is None else f'{a:.1f}d old'}")
    dl = os.path.join(ROOT, "daily-log")
    if os.path.isdir(dl):
        fs = sorted(f for f in os.listdir(dl) if f.endswith(".md"))
        print(f"  daily-log/: {len(fs)} entries, latest={fs[-1] if fs else 'none'}")
    else:
        print("  daily-log/: MISSING")
    # launchd cron health (AIOS-specific; harmless elsewhere)
    try:
        out = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=10).stdout
        rows = [l.split("\t") for l in out.splitlines() if LABEL_PREFIX in l]
        for pid, status, label in ((r[0], r[1], r[2]) for r in rows if len(r) >= 3):
            flag = "OK" if status == "0" else f"EXIT {status} (FAIL)"
            print(f"  cron {label.split('.')[-1]}: {flag}")
    except Exception:
        pass
    # scan today's logs for error markers
    logdir = os.path.expanduser("~/.local/share/aios-logs")
    if os.path.isdir(logdir):
        bad = []
        for f in os.listdir(logdir):
            if not f.endswith(".log"): continue
            try: txt = open(os.path.join(logdir, f), errors="replace").read()
            except OSError: continue
            if re.search(r'EINTR|error:|Traceback|command not found', txt) and "run end" not in txt:
                bad.append(f)
        if bad: print(f"  log errors (no clean 'run end'): {', '.join(sorted(bad)[-5:])}")
    try:
        g = subprocess.run(["git","-C",ROOT,"status","--porcelain"], capture_output=True, text=True, timeout=10).stdout
        unt = sum(1 for l in g.splitlines() if l.startswith("??"))
        mod = sum(1 for l in g.splitlines() if l[:2].strip() and not l.startswith("??"))
        print(f"  git: {unt} untracked, {mod} modified uncommitted")
    except Exception:
        pass

if __name__ == "__main__":
    main()
