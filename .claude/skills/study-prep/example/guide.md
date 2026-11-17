## Continuity (§2.5)

A function is continuous at \(x=a\) when all three hold:

1. \(f(a)\) is defined
2. \(\lim_{x\to a} f(x)\) exists
3. \(\lim_{x\to a} f(x) = f(a)\)

| Discontinuity | What fails | Example |
|---|---|---|
| Removable | limit exists, \(f(a)\) missing or different | \(\frac{x^2-4}{x-2}\) at 2 |
| Jump | one-sided limits differ | piecewise step |
| Infinite | limit is \(\pm\infty\) | \(\frac{1}{x-3}\) at 3 |

> **Notation rule:** carry \(\lim\) on every line until you substitute, and write `=` between lines, never an arrow.

## Limits at infinity (§2.6)

Divide by the highest power of \(x\) in the denominator.

$$\lim_{x\to\infty}\frac{1}{x^n} = 0 \quad (n>0)$$

- Top degree lower: limit is **0**
- Degrees equal: ratio of **leading coefficients**
- Top degree higher: limit is \(\pm\infty\) (no horizontal asymptote)

## Know cold

- The three continuity conditions, in order
- IVT needs continuity on a **closed** interval
