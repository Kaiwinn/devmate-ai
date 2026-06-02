# 🤖 DevMate AI

> **AI Engineering project** — Trợ lý lập trình production-grade với multi-provider, agent loop, structured output, eval system, resilience layer, và observability.

```bash
python devmate.py
```

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Claude](https://img.shields.io/badge/Claude-Sonnet%204.5-purple.svg)](https://www.anthropic.com/)
[![Langfuse](https://img.shields.io/badge/Observability-Langfuse-orange.svg)](https://langfuse.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

![Demo Main](./docs/images/demo-main.png)
<!-- 📸 PASTE ẢNH: Banner DevMate khi khởi động + 1 cuộc chat mẫu -->

---

## 🎯 Highlights

**Đây không phải là "thêm chatbot cho có"** — đây là một AI application với production patterns thật sự:

- ✅ **Multi-Provider Abstraction** — switch runtime giữa Claude / GPT / Groq / Gemini
- ✅ **Autonomous Agent** — tool use loop với 4 tools (read file, search code, run command...)
- ✅ **Structured Output** — Pydantic schema validation, output JSON parse được
- ✅ **Resilience Layer** — retry với exponential backoff, auto-fallback giữa providers
- ✅ **Smart Context Management** — sliding window + auto-summarize cho long conversations
- ✅ **Eval Suite** — LLM-as-judge với 10+ test cases, HTML report so sánh providers
- ✅ **Observability** — Langfuse tracing: mỗi LLM call được trace với cost, latency, token
- ✅ **Cost Tracking** — track token usage và cost real-time mỗi request

---

## ✨ Features Tour

### 💬 6 Multi-Mode Chat

| Command | Use Case |
|---------|----------|
| `/chat` | Chat thường về kỹ thuật |
| `/code <file>` | Code review chuyên nghiệp |
| `/test <file>` | Sinh unit tests đầy đủ cases |
| `/explain <file>` | Giải thích code chi tiết |
| `/review <file>` | Structured review với Pydantic schema |
| `/agent <task>` | Autonomous agent với tool use |

### 🤖 Autonomous Agent với Tool Use

Agent tự khám phá codebase, không cần user chỉ định file:

```
🤖 Bạn: /agent Project có chỗ nào dùng MD5 không?
🔧 Tool call: search_in_code({'pattern': 'md5'})
🔍 Kết quả: test_code/auth.py:12: hashed = hashlib.md5(...)
🔧 Tool call: read_file({'path': 'test_code/auth.py'})
→ Có 1 chỗ dùng MD5 ở auth.py line 12.
   MD5 không an toàn cho password — đề xuất dùng bcrypt hoặc argon2.
```

![Agent Demo](./docs/images/demo-agent.png)
<!-- 📸 PASTE ẢNH: Output /agent với các tool calls hiển thị -->

### 📊 Structured Code Review

Output JSON validated với Pydantic schema, lưu file để dùng pipeline khác:

```
💬 Bạn: /review test_code/auth.py
📊 Code Review Report
Score: 2/10 | Total Issues: 7
🐛 #1 [CRITICAL] SQL Injection vulnerability
   📁 test_code/auth.py:5
   💡 Why: Attacker có thể inject SQL...
   ✨ Fix: dùng parameterized query
💾 Đã lưu report vào data/review_20260601_111821.json
```

![Structured Review](./docs/images/demo-review.png)
<!-- 📸 PASTE ẢNH: Output /review với panel báo cáo + issues -->

### 🔭 Observability với Langfuse

Mọi LLM call đều được trace tự động — xem được cost, latency, input/output trên dashboard:

```
📊 [anthropic] 196 in + 738 out = $0.011658
Session: 4943e43b  ← link thẳng vào Langfuse trace
```

![Langfuse Dashboard](./docs/images/demo-langfuse.png)
<!-- 📸 PASTE ẢNH: Screenshot Langfuse dashboard với traces từ DevMate -->

**Những gì được trace:**
- Input messages (toàn bộ conversation history)
- Output của model
- Token count (input + output)
- Cost tính theo USD
- Provider, model name, mode (chat/code/agent...)
- Session grouping — thấy toàn bộ 1 lần dùng CLI

### 🛡️ Resilience: Auto Fallback

```
💬 Bạn: /fallback on
✅ Fallback ON
💬 Bạn: hello
⚠️  openai fail: Hết quota
🔄 Thử fallback: anthropic/claude-sonnet-4-5
✅ Fallback thành công với anthropic
```

### 🧪 Eval Suite (LLM-as-Judge)

```bash
python run_evals.py --providers groq-llama claude-haiku claude-sonnet
```

Output: terminal table + HTML report với cards summary, chi tiết từng test case.

![Eval Report](./docs/images/demo-eval.png)
<!-- 📸 PASTE ẢNH: HTML eval report -->

![Eval Terminal](./docs/images/demo-eval-terminal.png)
<!-- 📸 PASTE ẢNH: Terminal khi chạy eval xong, có bảng summary -->

---

## 🏗️ Architecture

```
devmate-ai/
├── devmate.py                  # Main entry, CLI loop
├── prompts.py                  # System prompts cho mỗi mode
├── schemas.py                  # Pydantic schemas (Issue, ReviewReport)
├── tools.py                    # Tools cho agent (read_file, grep, ...)
├── file_handler.py             # Đọc file/folder, glob pattern
├── structured_output.py        # Helper gọi LLM với schema
├── observability.py            # Langfuse tracing — mọi LLM call
├── context_manager.py          # Sliding window + auto-summarize
├── error_handler.py            # Phân loại 7 loại error
├── retry_helper.py             # Exponential backoff retry
├── fallback_chain.py           # Auto fallback giữa providers
│
├── providers/                  # Multi-provider abstraction
│   ├── base.py                 # LLMProvider ABC
│   ├── anthropic_provider.py   # Claude (Sonnet, Haiku)
│   ├── openai_provider.py      # GPT-4o, GPT-4o-mini
│   ├── groq_provider.py        # Llama 3.3 70B (FREE)
│   └── gemini_provider.py      # Gemini Flash
│
├── evals/                      # Eval suite
│   ├── datasets/basic.yaml     # Test cases (input + criteria)
│   ├── judge.py                # LLM-as-judge với Pydantic
│   ├── runner.py               # Test runner + HTML report
│   └── reports/                # Output reports
│
└── data/                       # Chat history, review reports
```

![Architecture Diagram](./docs/images/architecture.png)
<!-- 📸 PASTE ẢNH: Sơ đồ kiến trúc -->

### 🎨 Design Patterns Used

| Pattern | Áp dụng ở đâu |
|---------|---------------|
| **Abstract Base Class** | `LLMProvider` — define interface chung |
| **Factory Method** | `create_provider("claude-sonnet")` |
| **Strategy Pattern** | Context strategy (sliding/summarize/off) |
| **Chain of Responsibility** | Fallback chain |
| **Adapter Pattern** | Convert message format giữa providers |
| **Defensive Programming** | Try-except + graceful degradation |
| **Graceful Degradation** | Langfuse key chưa set → app vẫn chạy |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- macOS / Linux / Windows
- API key (ít nhất 1 trong các provider sau)

### Setup

```bash
# Clone
git clone https://github.com/<your-username>/devmate-ai.git
cd devmate-ai

# Virtual environment
python3.12 -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate   # Windows

# Dependencies
pip install -r requirements.txt

# API keys — tạo file .env và điền keys
```

### Required API Keys

Tạo file `.env` và thêm vào:

```bash
# Anthropic (có $5 free credit cho account mới)
ANTHROPIC_API_KEY=sk-ant-api03-xxx

# Groq (HOÀN TOÀN FREE, không cần thẻ)
GROQ_API_KEY=gsk_xxx

# OpenAI (cần nạp $5 - optional)
OPENAI_API_KEY=sk-proj-xxx

# Google Gemini (FREE limited - optional)
GOOGLE_API_KEY=AIzaSy-xxx

# Langfuse Observability (FREE tier tại cloud.langfuse.com - optional)
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
```

Lấy keys tại:
- [Anthropic Console](https://console.anthropic.com) — Claude
- [Groq Console](https://console.groq.com) — Free Llama
- [OpenAI Platform](https://platform.openai.com) — GPT
- [Google AI Studio](https://aistudio.google.com/apikey) — Gemini
- [Langfuse Cloud](https://cloud.langfuse.com) — Observability (free)

### Run

```bash
python devmate.py
```

---

## 📖 Usage Examples

```bash
# Chat thường
💬 Bạn: Giải thích async/await trong Python

# Review file
💬 Bạn: /code src/auth.py

# Review folder với glob
💬 Bạn: /code "src/**/*.py"

# Sinh unit test
💬 Bạn: /test utils/helper.js

# Structured review (output JSON)
💬 Bạn: /review src/payment.py

# Agent tự khám phá
💬 Bạn: /agent Project có security issues nào?

# Switch provider
💬 Bạn: /provider groq-llama       # FREE Llama
💬 Bạn: /provider claude-sonnet    # Best quality

# Bật auto-fallback
💬 Bạn: /fallback on

# Đổi strategy quản lý context
💬 Bạn: /strategy summarize    # Auto-tóm tắt khi dài
💬 Bạn: /context               # Xem token usage

# Save / Load conversation
💬 Bạn: /save
💬 Bạn: /load

# Stats & help
💬 Bạn: /stats
💬 Bạn: /help
```

---

## 🤖 Supported Providers

| Provider | Models | Free Tier | Tool Use | Structured Output | Notes |
|----------|--------|-----------|----------|-------------------|-------|
| **Anthropic** | Sonnet 4.5, Haiku 4.5 | $5 free | ✅ | ✅ | Best for code |
| **OpenAI** | GPT-4o, GPT-4o-mini | ❌ Phải nạp $5 | ❌ | ❌ | Standard |
| **Groq** | Llama 3.3 70B, Mixtral | ✅ Unlimited | ❌ | ❌ | **Siêu nhanh** |
| **Gemini** | Flash variants | ✅ Limited | ❌ | ❌ | Quota biến động |

*Tool Use & Structured Output hiện chỉ Anthropic*

---

## 🧪 Running Evals

```bash
# Test với Groq (free)
python run_evals.py --providers groq-llama

# Compare 3 providers
python run_evals.py --providers groq-llama claude-haiku claude-sonnet
```

---

## 💰 Cost Tracking

Token usage và cost được track real-time:

```
📊 [anthropic] 245 in + 678 out = $0.010917
📊 [groq]      245 in + 678 out = $0.000000   ← FREE!
```

Production pattern: **dùng Groq cho 90% tasks (free), Claude cho 10% critical tasks (paid)** → tiết kiệm 90% chi phí vs all-Claude.

---

## 🛡️ Resilience Features

| Feature | Mô tả |
|---------|-------|
| **Error Classification** | Phân loại 7 loại lỗi với suggestion cụ thể |
| **Exponential Backoff Retry** | Tự retry với delay 1s, 2s, 4s... |
| **Auto Fallback** | Provider chính lỗi → tự switch backup |
| **Context Management** | Auto trim/summarize khi vượt token limit |
| **Graceful Degradation** | App không crash trước người dùng |

---

## 🛣️ Roadmap

- [x] **Bậc 1-2** — Multi-mode chat + Structured Output
- [x] **Bậc 3** — Multi-provider abstraction (Claude/GPT/Groq/Gemini)
- [x] **Bậc 4** — Resilience layer (retry + fallback + context management)
- [x] **Bậc 5** — Eval suite với LLM-as-judge
- [x] **Bậc 6** — Observability với Langfuse (trace mọi LLM call)
- [ ] **Bậc 7** — Advanced RAG (hybrid search + re-ranking + doc index)
- [ ] **Bậc 8** — Multi-Agent với LangGraph (planner → coder → reviewer)

---

## 📊 Tech Stack

- **LLM:** Claude Sonnet 4.5, GPT-4o-mini, Llama 3.3 70B (Groq), Gemini Flash
- **Observability:** [Langfuse](https://langfuse.com/) — trace, cost, latency dashboard
- **CLI:** [Rich](https://github.com/Textualize/rich) — panels, tables, syntax highlighting
- **Validation:** [Pydantic v2](https://docs.pydantic.dev) — structured output, type safety
- **Eval:** Custom LLM-as-judge với YAML test datasets

---

## 🎓 What I Learned

Build project này, mình thực hành các skills của một AI Engineer:

1. **LLM API Integration** — streaming, multi-turn, system prompts
2. **Prompt Engineering** — role/task/format pattern, structured prompts
3. **Tool Use / Function Calling** — agent autonomous với JSON schema
4. **Structured Output** — Pydantic forced output, type-safe pipeline
5. **Multi-provider Abstraction** — interface design, adapter pattern
6. **Resilience Engineering** — error classification, retry strategies, fallback
7. **Context Management** — sliding window vs summarization trade-off
8. **LLM Evaluation** — LLM-as-judge, automated test suite, A/B compare
9. **Cost Optimization** — cheap inference + smart judge pattern
10. **Observability** — Langfuse tracing, trace/generation hierarchy, graceful degradation

---

## 📄 License

MIT License — feel free to fork và customize.

---

## 🙏 Acknowledgments

- [Anthropic Claude](https://www.anthropic.com) — primary LLM
- [Groq](https://groq.com) — free fast Llama inference
- [Langfuse](https://langfuse.com) — LLM observability
- [Rich](https://github.com/Textualize/rich) — beautiful CLI
- Inspired by [Cursor](https://cursor.sh), [Claude Code](https://www.anthropic.com/claude-code), [Aider](https://aider.chat)

---

**Built with ❤️ as a learning journey into AI Engineering.**

*If you find this useful or want to discuss AI Engineering, feel free to reach out!*
