"""Supply/demand graphs as inline SVG for study-prep pages (guide.md or prep.py answers).

prep.py gets this module as `graphs`:

    p = graphs.Panel("$8 ceiling", (0, 400), (0, 20), notes=("CS $1,080 · PS $180",))
    p.through((0, 20), (400, 0), width=2)        # a line through two points, clipped to the box
    p.poly([(0, 20), (120, 14), (120, 8), (0, 8)], graphs.BLUE)
    p.dot(200, 10); p.drop(200, 10); p.ytick(10, "$10"); p.xtick(200, "200")
    why = "Explanation...\\n\\n" + graphs.fig("ceil", [p])

Data coordinates in, SVG out. Colors follow the textbook: CS blue, PS orange, revenue green, DWL yellow.
Text uses currentColor, so graphs work in light and dark themes.
"""
import html, math

BLUE, ORANGE, GREEN, YELLOW, CUR = "#3b82f6", "#f97316", "#22c55e", "#eab308", "currentColor"


class Panel:
    def __init__(s, title, x, y, notes=(), xlabel="Quantity", ylabel="Price", w=300, h=None, pad=(46, 26, 26, 62)):
        s.title, s.notes, s.xlabel, s.ylabel = title, notes, xlabel, ylabel
        (s.x0, s.x1), (s.y0, s.y1) = x, y
        s.l, s.r, s.t, s.b = pad
        s.b += 13 * (len(notes) - 2) if notes else -26  # caption lines under the graph, or none
        s.w, s.h = w, h or 188 + s.t - 26 + s.b
        s.out = []

    def X(s, q): return s.l + (q - s.x0) / (s.x1 - s.x0) * (s.w - s.l - s.r)
    def Y(s, p): return s.h - s.b - (p - s.y0) / (s.y1 - s.y0) * (s.h - s.t - s.b)

    def seg(s, q1, p1, q2, p2, color=CUR, width=1.6, dash=None, op=None):
        extra = (f' stroke-dasharray="{dash}"' if dash else "") + (f' opacity="{op}"' if op else "")
        s.out.append(f'<line x1="{s.X(q1):.1f}" y1="{s.Y(p1):.1f}" x2="{s.X(q2):.1f}" y2="{s.Y(p2):.1f}" '
                     f'stroke="{color}" stroke-width="{width}"{extra}/>')

    def through(s, a, b, **kw):
        """Line through points a and b, clipped to the plot box. Returns the clipped ends, a-side first."""
        (q1, p1), (q2, p2) = a, b
        dq, dp = q2 - q1, p2 - p1
        lo, hi = -1e9, 1e9
        for d, v, mn, mx in ((dq, q1, s.x0, s.x1), (dp, p1, s.y0, s.y1)):
            if d:
                ta, tb = (mn - v) / d, (mx - v) / d
                lo, hi = max(lo, min(ta, tb)), min(hi, max(ta, tb))
        ends = (q1 + lo * dq, p1 + lo * dp), (q1 + hi * dq, p1 + hi * dp)
        s.seg(*ends[0], *ends[1], **kw)
        return ends

    def curve(s, pts, color=CUR, width=1.6):
        s.out.append('<polyline points="' + " ".join(f"{s.X(q):.1f},{s.Y(p):.1f}" for q, p in pts)
                     + f'" fill="none" stroke="{color}" stroke-width="{width}"/>')

    def poly(s, pts, color, op=.45):
        s.out.append('<polygon points="' + " ".join(f"{s.X(q):.1f},{s.Y(p):.1f}" for q, p in pts)
                     + f'" fill="{color}" fill-opacity="{op}"/>')

    def box(s, q1, p1, q2, p2, color, op=.45):
        s.poly([(q1, p1), (q2, p1), (q2, p2), (q1, p2)], color, op)

    def outline(s, q1, p1, q2, p2):
        x, y = s.X(min(q1, q2)), s.Y(max(p1, p2))
        s.out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{abs(s.X(q2) - s.X(q1)):.1f}" '
                     f'height="{abs(s.Y(p2) - s.Y(p1)):.1f}" fill="none" stroke="currentColor" stroke-width="1.2" stroke-dasharray="4 3"/>')

    def px_text(s, x, y, t, anchor="start", size=10, bold=False, color=None):
        attrs = f' text-anchor="{anchor}"' + (f' font-size="{size}"' if size != 10 else "")
        attrs += (' font-weight="600"' if bold else "") + (f' fill="{color}"' if color else "")
        s.out.append(f'<text x="{x:.1f}" y="{y:.1f}"{attrs}>{html.escape(t)}</text>')

    def text(s, q, p, t, dx=0, dy=0, **kw): s.px_text(s.X(q) + dx, s.Y(p) + dy, t, **kw)

    def dot(s, q, p, label=None, dx=5, dy=-5, anchor="start"):
        s.out.append(f'<circle cx="{s.X(q):.1f}" cy="{s.Y(p):.1f}" r="2.8"/>')
        if label:
            s.text(q, p, label, dx, dy, anchor=anchor, bold=True)

    def drop(s, q, p):
        """Dotted guides from a point down to the Q axis and across to the P axis."""
        s.seg(q, p, q, s.y0, width=1, dash="2 3", op=.6)
        s.seg(q, p, s.x0, p, width=1, dash="2 3", op=.6)

    def grid(s, dx, dy, xevery=1, yevery=1, yfmt="${:g}"):
        """Faint worksheet grid every dx / dy, labeling every xevery-th and yevery-th line (like a handout graph)."""
        for i in range(1, round((s.x1 - s.x0) / dx) + 1):
            q = s.x0 + i * dx; s.seg(q, s.y0, q, s.y1, width=.6, dash="1 3", op=.35)
            if i % xevery == 0: s.xtick(q, f"{q:g}")
        for i in range(1, round((s.y1 - s.y0) / dy) + 1):
            p = s.y0 + i * dy; s.seg(s.x0, p, s.x1, p, width=.6, dash="1 3", op=.35)
            if i % yevery == 0: s.ytick(p, yfmt.format(p))

    def xtick(s, q, t, anchor="middle"): s.px_text(s.X(q), s.h - s.b + 13, t, anchor, size=9)
    def ytick(s, p, t): s.px_text(s.l - 5, s.Y(p) + 3, t, "end", size=9)

    def bracket(s, q, p1, p2, color, width=4):
        """Thick vertical bar from p1 to p2 at quantity q (who-bears-the-tax shares)."""
        s.seg(q, p1, q, p2, color=color, width=width)

    def arrow(s, a, b, color=CUR, both=False):
        (x1, y1), (x2, y2) = (s.X(a[0]), s.Y(a[1])), (s.X(b[0]), s.Y(b[1]))
        s.out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="1.4"/>')
        for (xa, ya), (xb, yb) in [((x1, y1), (x2, y2))] + ([((x2, y2), (x1, y1))] if both else []):
            ang = math.atan2(yb - ya, xb - xa)
            pts = [(xb, yb)] + [(xb - 6 * math.cos(ang + d), yb - 6 * math.sin(ang + d)) for d in (0.45, -0.45)]
            s.out.append('<polygon points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + f'" fill="{color}"/>')

    def svg(s, maxw):
        ax, ay = s.X(s.x0), s.Y(s.y0)
        top, right = s.Y(s.y1), s.X(s.x1)
        g = [f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{right + 6:.1f}" y2="{ay:.1f}" stroke="currentColor"/>',
             f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{ax:.1f}" y2="{top - 6:.1f}" stroke="currentColor"/>']
        if s.x0:  # axis break marks for zoomed-in axes, like the textbook's truncated graphs
            g.append(f'<path d="M{ax + 7:.1f} {ay + 4:.1f} l4 -8 M{ax + 11:.1f} {ay + 4:.1f} l4 -8" stroke="currentColor" fill="none"/>')
        if s.y0:
            g.append(f'<path d="M{ax - 4:.1f} {ay - 7:.1f} l8 -4 M{ax - 4:.1f} {ay - 11:.1f} l8 -4" stroke="currentColor" fill="none"/>')
        g += s.out
        g.append(f'<text x="{s.w / 2:.1f}" y="14" text-anchor="middle" font-size="11" font-weight="600">{html.escape(s.title)}</text>')
        g.append(f'<text x="4" y="{top - 8:.1f}" font-size="9" opacity=".75">{html.escape(s.ylabel)}</text>')
        g.append(f'<text x="{right + 6:.1f}" y="{ay + 25:.1f}" text-anchor="end" font-size="9" opacity=".75">{html.escape(s.xlabel)}</text>')
        for i, n in enumerate(s.notes):
            g.append(f'<text x="{s.w / 2:.1f}" y="{ay + 41 + 13 * i:.1f}" text-anchor="middle">{html.escape(n)}</text>')
        aria = html.escape(s.title + ". " + " ".join(s.notes))
        return (f'<svg viewBox="0 0 {s.w} {s.h}" role="img" aria-label="{aria}" '
                f'style="flex:1 1 250px;max-width:{maxw}px;height:auto"><g font-size="10" fill="currentColor">'
                + "".join(g) + "</g></svg>")


def fig(name, panels, maxw=300):
    """One or more panels side by side; they wrap to one per row on a phone."""
    return (f'<div data-graph="{name}" style="display:flex;flex-wrap:wrap;gap:6px 18px;margin:14px 0 20px">'
            + "".join(p.svg(maxw) for p in panels) + "</div>")
