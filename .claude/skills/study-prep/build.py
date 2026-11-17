#!/usr/bin/env python3
"""Build a /study-prep artifact page from a prep folder.

    python3 build.py <prep-dir>

<prep-dir> holds prep.py (META, SOURCES, optional MISSING, and QUESTIONS or SETS)
and/or guide.md. Writes <prep-dir>/<dir-name>.html. Validates every question and
prints the answer-letter spread; exits 1 on any defect so a bad bank never ships.
See example/ beside this script for the authoring format.
"""
import datetime, hashlib, html, json, pathlib, re, sys
from collections import Counter

HERE = pathlib.Path(__file__).parent
LETTERS = "ABCD"
MAX_SHARE = 0.40  # one letter may hold at most this share of a set's MC answers
MATHJAX = ('<script>window.MathJax={tex:{inlineMath:[["\\\\(","\\\\)"]],displayMath:[["$$","$$"]]},'
           'svg:{fontCache:"global"}};</script>\n'
           '<script src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-svg-full.js"></script>')


def MC(topic, stem, options, why, src):
    """Multiple choice. Exactly 4 options; prefix the correct one with '*'."""
    return {"type": "mc", "topic": topic, "stem": stem, "options": options, "why": why, "src": src}


def TF(topic, stem, answer, why, src):
    return {"type": "tf", "topic": topic, "stem": stem, "answer": answer, "why": why, "src": src}


def SA(topic, stem, answer, src, why=""):
    """Short answer or worked problem: revealed on tap, then self-graded."""
    return {"type": "sa", "topic": topic, "stem": stem, "answer": answer, "why": why, "src": src}


def load(prep_dir):
    import graphs  # supply/demand SVG helper for answers and explanations; see graphs.py
    ns = {"MC": MC, "TF": TF, "SA": SA, "graphs": graphs}
    f = prep_dir / "prep.py"
    if not f.exists():
        sys.exit(f"{f} not found (it carries META and SOURCES even for a guide-only build)")
    exec(compile(f.read_text(), str(f), "exec"), ns)
    guide = (prep_dir / "guide.md").read_text() if (prep_dir / "guide.md").exists() else ""
    sets = ns.get("SETS") or ({"Practice quiz": ns["QUESTIONS"]} if ns.get("QUESTIONS") else {})
    return ns, guide, sets


def validate(sets):
    errors, out, seen = [], [], {}
    for si, (name, raw) in enumerate(sets.items()):
        qs = []
        for qi, q in enumerate(raw):
            where = f"[{name}] Q{qi + 1}"
            # id = hash of what the saved answer refers to, so a rebuild keeps answers for unchanged questions
            fp = json.dumps([q["type"], q["stem"], q.get("options"), q.get("answer") if q["type"] != "sa" else None], ensure_ascii=False)
            q = dict(q, id="q" + hashlib.sha1(fp.encode()).hexdigest()[:10])
            for field in ("topic", "stem", "src"):
                if not str(q.get(field, "")).strip():
                    errors.append(f"{where}: empty {field}")
            if q["type"] in ("mc", "tf") and not q["why"].strip():
                errors.append(f"{where}: empty why")
            if q["type"] == "mc":
                starred = [i for i, o in enumerate(q["options"]) if o.startswith("*")]
                if len(starred) != 1:
                    errors.append(f"{where}: {len(starred)} starred options, need exactly 1")
                if len(q["options"]) != 4:
                    errors.append(f"{where}: {len(q['options'])} options, need 4")
                q["options"] = [o.lstrip("*").strip() for o in q["options"]]
                if len({o.lower() for o in q["options"]}) != len(q["options"]):
                    errors.append(f"{where}: duplicate options")
                q["answer"] = starred[0] if starred else 0
            elif q["type"] == "tf" and not isinstance(q["answer"], bool):
                errors.append(f"{where}: TF answer must be True or False")
            elif q["type"] == "sa" and not str(q["answer"]).strip():
                errors.append(f"{where}: empty answer")
            key = re.sub(r"\W+", " ", q["stem"].lower()).strip()[:80]
            if key in seen:
                errors.append(f"{where}: duplicate stem of {seen[key]}")
            seen[key] = where
            qs.append(q)

        mc = Counter(LETTERS[q["answer"]] for q in qs if q["type"] == "mc")
        tf = Counter(q["answer"] for q in qs if q["type"] == "tf")
        n_mc = sum(mc.values())
        spread = " ".join(f"{l}{mc[l]}" for l in LETTERS)
        print(f"{name}: {len(qs)} questions · MC {n_mc} ({spread}) · TF {sum(tf.values())} "
              f"(T{tf[True]} F{tf[False]}) · SA {sum(q['type'] == 'sa' for q in qs)}")
        if n_mc >= 8 and max(mc.values()) > MAX_SHARE * n_mc:
            errors.append(f"[{name}] answer letters skewed ({spread}); move correct options so none exceeds {MAX_SHARE:.0%}")
        if sum(tf.values()) >= 6 and max(tf.values()) > 0.75 * sum(tf.values()):
            print(f"  warning: TF answers lopsided (T{tf[True]} F{tf[False]})")
        topics = Counter(q["topic"] for q in qs)
        print("  topics: " + ", ".join(f"{t} {c}" for t, c in topics.items()))
        out.append({"name": name, "questions": qs})
    return errors, out


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    prep_dir = pathlib.Path(sys.argv[1]).resolve()
    ns, guide, sets = load(prep_dir)
    meta = ns.get("META", {})
    for field in ("course", "title"):
        if not meta.get(field):
            sys.exit(f"META needs '{field}'")
    if not ns.get("SOURCES"):
        sys.exit("SOURCES is empty; list every source the content came from")
    if not guide and not sets:
        sys.exit("nothing to build: add guide.md and/or QUESTIONS/SETS in prep.py")

    errors, sets_out = validate(sets)
    if errors:
        print("\n".join("ERROR " + e for e in errors))
        sys.exit(1)

    data = {
        "course": meta["course"], "title": meta["title"], "exam": meta.get("exam", ""), "scope": meta.get("scope", ""),
        "sources": ns["SOURCES"], "missing": ns.get("MISSING", []),
        "built": datetime.date.today().strftime("%b %-d, %Y"),
        "guide": guide, "sets": sets_out,
        # One stable storage slot per page; answers inside it are keyed by question id (a content hash).
        "key": re.sub(r"\W+", "-", f"{meta['course']} {meta['title']}").strip("-").lower(),
    }
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    needs_math = bool(re.search(r"\\\(|\$\$", guide + json.dumps(sets_out)))
    page = (HERE / "template.html").read_text()
    page = page.replace("__TITLE__", html.escape(f"{meta['course']} {meta['title']}"))
    page = page.replace("/*__DATA__*/null", blob).replace("__MATHJAX__", MATHJAX if needs_math else "")
    out = prep_dir / f"{prep_dir.name}.html"
    out.write_text(page)
    print(f"guide: {'yes' if guide else 'no'} · math: {'yes' if needs_math else 'no'}\nwrote {out}")


if __name__ == "__main__":
    main()
