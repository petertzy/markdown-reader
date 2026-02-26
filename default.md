# Math Rendering Test File

This file is used to test **inline and block math rendering**, including:
- Unicode
- LaTeX
- Edge cases
- Problematic symbols

---

## 1. Exponents (Inline)

- x²
- x³
- xⁿ
- x^2
- x^{10}
- a^{b+c}
- $x^2$
- $x^{n+1}$
- $e^{i\pi} + 1 = 0$

---

## 2. Subscripts (Inline)

- x₁
- x₂
- xᵢ
- a_n
- x_{n+1}
- $x_1$
- $x_{n+1}$

---

## 3. Fractions

### Inline
- 1/2
- ½
- ¾
- a/b
- $\frac{1}{2}$
- $\frac{a+b}{c+d}$

### Block
$$
\frac{1}{2}
$$

$$
\frac{x+1}{x-1}
$$

---

## 4. Roots

### Inline
- √2
- √x
- $\sqrt{2}$
- $\sqrt{x+1}$

### Block
$$
\sqrt{x^2 + y^2}
$$

---

## 5. Operators

- x + y
- x − y
- x × y
- x ÷ y
- x · y
- x * y
- x / y

---

## 6. Comparisons

- x = y
- x ≠ y
- x ≥ y
- x ≤ y
- x ≈ y
- x < y
- x > y

---

## 7. Trigonometry

### Inline
- sin(x)
- cos(x)
- tan(x)
- sin²(x)
- $\sin^2(x)$

### Block
$$
\sin^2(x) + \cos^2(x) = 1
$$

---

## 8. Limits, Derivatives and Integrals

### Limit
$$
\lim_{x \to 0} \frac{\sin x}{x} = 1
$$

### Derivative
$$
\frac{d}{dx} x^2 = 2x
$$

### Integral
$$
\int_0^1 x^2 \, dx
$$

$$
\iint f(x,y) \, dx \, dy
$$

---

## 9. Summations and Products

$$
\sum_{i=1}^{n} i
$$

$$
\sum_{k=0}^{\infty} \frac{1}{2^k}
$$

$$
\prod_{i=1}^{n} i
$$

---

## 10. Matrices

$$
\begin{matrix}
1 & 2 \\
3 & 4
\end{matrix}
$$

$$
\begin{bmatrix}
1 & 0 \\
0 & 1
\end{bmatrix}
$$

$$
\begin{vmatrix}
a & b \\
c & d
\end{vmatrix}
$$

---

## 11. Sets and Logic

### Inline
- ∈ ∉ ⊂ ⊆ ∪ ∩
- ∀ ∃ ∅
- ℕ ℤ ℚ ℝ ℂ

### Block
$$
A = \{ x \in \mathbb{R} \mid x > 0 \}
$$

$$
\forall x \in \mathbb{R}, \; x^2 \ge 0
$$

---

## 12. Greek Letters

### Inline
- α β γ δ ε
- λ μ π θ σ
- Ω Δ Σ

### Block
$$
\alpha + \beta = \gamma
$$

$$
\pi r^2
$$

---

## 13. Pure Unicode (Browser only)

- ∞ ± ∓
- ≤ ≥ ≠ ≈
- ∑ ∏ ∫
- √ ∛ ∜
- ← → ↑ ↓ ↔

---

## 14. Edge Cases (should be tested)

- x^
- \frac{1}
- \sqrt{}
- $x ^ 2$
- $$
- $$$$
- Inline formula inside **bold**: **$x^2$**
- Inline formula inside _italic_: _$x^2$_

---

## End of test file