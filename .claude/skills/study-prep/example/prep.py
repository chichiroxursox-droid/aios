# Format example + build.py self-test:  python3 build.py example
# Real preps live at references/<course>/prep/<slug>/prep.py and follow this shape.
# Math: \( inline \) and $$ display $$ only. A bare $ is left alone, so prices like $20 are safe.

META = dict(
    course="MATH 101",
    title="Format Example",
    exam="Fixture for build.py, not a real quiz",
    scope="§2.5 Continuity · §2.6 Limits at infinity",
)
SOURCES = ["Fixture: hand-written to exercise every question type"]
MISSING = ["Example of a gap: assigned video had no transcript"]

C, L = "Continuity (§2.5)", "Limits at infinity (§2.6)"

QUESTIONS = [
    MC(C, r"A function \(f\) is continuous at \(x=a\) when:",
       [r"*\(\lim_{x\to a} f(x) = f(a)\)", r"\(f(a)\) is defined", r"\(\lim_{x\to a^-} f(x)\) exists",
        r"\(f\) has a horizontal asymptote at \(y=a\)"],
       why="All three conditions collapse into this one equation: the limit exists, \\(f(a)\\) exists, and they match.",
       src="fixture"),
    MC(C, r"What kind of discontinuity does \(f(x)=\dfrac{x^2-4}{x-2}\) have at \(x=2\)?",
       ["Jump", "*Removable", "Infinite", "None, it is continuous"],
       why=r"\(\lim_{x\to 2}\frac{(x-2)(x+2)}{x-2} = \lim_{x\to 2}(x+2) = 4\) exists, but \(f(2)\) is undefined.",
       src="fixture"),
    MC(C, r"Which theorem guarantees \(x^3+x-1=0\) has a root in \([0,1]\)?",
       ["Squeeze Theorem", "Mean Value Theorem", "*Intermediate Value Theorem", "Limit Laws"],
       why=r"The polynomial is continuous on \([0,1]\), \(f(0)=-1<0\) and \(f(1)=1>0\).", src="fixture"),
    MC(C, r"What does \(g(x)=\dfrac{1}{x-3}\) have at \(x=3\)?",
       ["Removable discontinuity", "Jump discontinuity", "Continuity", "*Infinite discontinuity"],
       why=r"\(\lim_{x\to 3^+} g(x)=\infty\), so there is a vertical asymptote.", src="fixture"),
    MC(L, r"$$\lim_{x\to\infty}\frac{3x^2+1}{5x^2-x}$$",
       [r"*\(\tfrac{3}{5}\)", "0", r"\(\infty\)", r"\(-1\)"],
       why="Equal degrees, so the limit is the ratio of leading coefficients.", src="fixture"),
    MC(L, r"$$\lim_{x\to\infty}\frac{2x+7}{x^3}$$",
       ["2", "*0", r"\(\infty\)", "7"],
       why="The denominator's degree is higher, so the fraction goes to 0.", src="fixture"),
    MC(L, r"\(\lim_{x\to -\infty} e^{x} =\) ?",
       [r"\(\infty\)", "1", "*0", "Does not exist"],
       why=r"\(e^x\) flattens toward \(y=0\) on the left.", src="fixture"),
    MC(L, r"A horizontal asymptote \(y=L\) means:",
       [r"\(\lim_{x\to L} f(x)=\infty\)", r"\(f(L)=0\)", r"\(\lim_{x\to 0} f(x)=L\)",
        r"*\(\lim_{x\to\infty} f(x)=L\) or \(\lim_{x\to-\infty} f(x)=L\)"],
       why="Horizontal asymptotes describe end behavior only.", src="fixture"),
    TF(L, "A function can cross its own horizontal asymptote.", True,
       why=r"\(\frac{\sin x}{x}\) crosses \(y=0\) infinitely often and still has \(\lim_{x\to\infty}\frac{\sin x}{x}=0\).",
       src="fixture"),
    TF(C, r"If \(\lim_{x\to a} f(x)\) exists, then \(f\) is continuous at \(a\).", False,
       why=r"\(f(a)\) must also be defined and equal the limit.", src="fixture"),
    SA(L, r"Evaluate \(\displaystyle\lim_{x\to\infty}\frac{4x^3-x}{2x^3+5}\). Show every step.",
       r"""Divide numerator and denominator by \(x^3\), keeping the limit on every line:

$$\lim_{x\to\infty}\frac{4x^3-x}{2x^3+5} = \lim_{x\to\infty}\frac{4-\frac{1}{x^2}}{2+\frac{5}{x^3}}$$

By the Quotient Law, then \(\lim_{x\to\infty}\frac{1}{x^n}=0\):

$$= \frac{\lim_{x\to\infty}\left(4-\frac{1}{x^2}\right)}{\lim_{x\to\infty}\left(2+\frac{5}{x^3}\right)} = \frac{4-0}{2+0} = 2$$""",
       src="fixture", why="Write `=` between lines, never an arrow."),
    SA(C, r"State the three conditions for \(f\) to be continuous at \(x=a\).",
       "1. \\(f(a)\\) is defined\n2. \\(\\lim_{x\\to a} f(x)\\) exists\n3. \\(\\lim_{x\\to a} f(x) = f(a)\\)",
       src="fixture"),
]
