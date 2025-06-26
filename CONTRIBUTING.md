# 🤝 Contributing to FastAPI-Cap

Thank you for your interest in contributing to **FastAPI-Cap**!  
We welcome bug reports, feature requests, documentation improvements, and code contributions.

---

## 🛠️ Development Setup

### 1. Fork & Clone the Repository

```bash
git clone https://github.com/your-username/fastapi-cap.git
cd fastapicap
```

### 2. Install Development Dependencies

We recommend using [uv](https://github.com/astral-sh/uv) for fast, modern Python dependency management, but you can also use `pip`.

#### Using uv (recommended)

```bash
uv sync --dev
```

#### Or, install manually with pip

```bash
pip install \
    httpx>=0.28.1 \
    mkdocs-material>=9.6.14 \
    mkdocstrings[python]>=0.29.1 \
    pytest>=8.4.1 \
    pytest-asyncio>=1.0.0 \
    pytest-xdist>=3.7.0 \
    testcontainers>=4.10.0
```

---

## 🧪 Running Tests

Make sure you have a docker running as the unit test will create test container:


_Then run the test suite:_

```bash
pytest
```

You can also run tests in parallel for faster feedback:

```bash
pytest -n auto
```

---

## 📝 Code Style

- Please follow [PEP8](https://www.python.org/dev/peps/pep-0008/) and use Ruff for formatting.
- Type hints are required for all new code.

---

## 📚 Documentation

- Documentation is built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/).
- To serve the docs locally:

```bash
mkdocs serve
```

---

## 🙏 Thank You

Your contributions make FastAPI-Cap better for everyone!  
If you have any questions, open an issue or start a discussion.

---