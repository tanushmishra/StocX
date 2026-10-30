# 🤝 Contributing to Market-Neutral Hedge Builder

Thank you for your interest in contributing to the **Market-Neutral Hedge Builder**!

## 1. Core Principles & Quantitative Safety Invariants

Before writing code, understand our non-negotiable architectural invariant:

> **LLMs never guess numbers, and math models never read the news.**

1. **Deterministic Quant Modules (`engine/`):**
   * Never introduce LLMs, prompt calls, or stochastic sampling into the `engine/` package.
   * All computations must be reproducible using `numpy`, `scipy`, `pandas`, or `statsmodels`.
   * Edge cases (e.g. zero variance, missing prices, negative betas) must be handled gracefully without silent errors.
2. **Agentic Orchestration (`agents/`):**
   * LLMs must only read computed numbers from state; they must never perform arithmetic, portfolio sizing, or statistical tests in prompt text.
   * Agent nodes must output structured Pydantic models where applicable.

---

## 2. Development Setup

```bash
# Fork & clone the repo
git clone https://github.com/your-username/market-neutral-hedge-builder.git
cd market-neutral-hedge-builder

# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows
# source .venv/bin/activate  # macOS/Linux

# Install package in editable mode with development dependencies
pip install -e ".[dev]"
```

---

## 3. Code Standards & Style

* **Python Version:** Target Python `3.11`+.
* **Type Annotations:** Use modern Python type hints (`list[str]`, `dict[str, Any]`, `tuple[int, float]`).
* **Docstrings:** Use Google-style docstrings with `Args:`, `Returns:`, `Raises:`, and `Example:` sections.
* **Formatting:** Format with `black` (100 character line limit) and lint with `ruff`.

```bash
# Run linter
ruff check .

# Run auto-formatter
black .
```

---

## 4. Testing Requirements

Every new mathematical function or agent node must include unit tests under `tests/`.

```bash
# Run the complete test suite
pytest

# Run with coverage report
pytest --cov=engine --cov=agents --cov-report=term-missing
```

Ensure all tests pass before opening a Pull Request.

---

## 5. Pull Request Workflow

1. Create a feature branch (`git checkout -b feat/dynamic-kalman-beta`).
2. Implement your changes following all architectural guidelines.
3. Add unit tests covering the new functionality.
4. Verify that `pytest` passes with 100% success.
5. Commit with descriptive commit messages (`git commit -m "feat(quant): add Kalman filter beta estimator"`).
6. Push to your fork and submit a Pull Request.
