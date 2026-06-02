# 🤖 DevMate AI

> **AI Engineering project** — Trợ lý lập trình production-grade với multi-provider, agent loop, structured output, eval system, và resilience layer.

# RUN
python devmate.py

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Claude](https://img.shields.io/badge/Claude-Sonnet%204.5-purple.svg)](https://www.anthropic.com/)
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

🤖 Bạn: Project có chỗ nào dùng MD5 không?
🔧 Tool call: search_in_code({'pattern': 'md5'})
🔍 Kết quả: test_code/auth.py:12: hashed = hashlib.md5(...)
🔧 Tool call: read_file({'path': 'test_code/auth.py'})
📄 [reading file content...]
→ Có 1 chỗ dùng MD5 ở auth.py line 12.
MD5 không an toàn cho password vì: (1) fast hash dễ brute-force,
(2) đã có collision attacks, (3) thiếu salt mặc định.
Đề xuất: dùng bcrypt hoặc argon2.

![Agent Demo](./docs/images/demo-agent.png)
<!-- 📸 PASTE ẢNH: Output /agent với các tool calls hiển thị -->

### 📊 Structured Code Review

Output JSON validated với Pydantic schema, lưu file để dùng pipeline khác:
💬 Bạn: /review test_code/auth.py
📊 Code Review Report
Score: 2/10
Total Issues: 7
🐛 Issues:
#1 [CRITICAL] SQL Injection vulnerability
📁 test_code/auth.py:5
💡 Why: Attacker có thể inject SQL...
✨ Fix: dùng parameterized query
...
💾 Đã lưu report vào data/review_20260601_111821.json
![Structured Review](./docs/images/demo-review.png)
<!-- 📸 PASTE ẢNH: Output /review với panel báo cáo + issues -->

### 🛡️ Resilience: Auto Fallback

Khi provider chính lỗi (rate limit, quota exceeded, server overload), DevMate tự switch sang provider backup:
💬 Bạn: /fallback on
✅ Fallback ON
💬 Bạn: hello
⚠️  openai fail: Hết quota
🔄 Thử fallback: anthropic/claude-sonnet-4-5
✅ Fallback thành công với anthropic
[Claude trả lời, app không crash]
### 🧪 Eval Suite (LLM-as-Judge)

Đánh giá quality tự động với LLM-as-judge, compare giữa nhiều providers:

```bash
python run_evals.py --providers claude-sonnet claude-haiku groq-llama
```

Output: terminal table + HTML report với cards summary, chi tiết từng test case.

![Eval Report](./docs/images/demo-eval.png)
<!-- 📸 PASTE ẢNH: HTML eval report -->

---

## 🏗️ Architecture
devmate-ai/
├── devmate.py                  # Main entry, CLI loop
├── prompts.py                  # System prompts cho mỗi mode
├── schemas.py                  # Pydantic schemas (Issue, ReviewReport)
├── tools.py                    # Tools cho agent (read_file, grep, ...)
├── file_handler.py             # Đọc file/folder, glob pattern
├── structured_output.py        # Helper gọi LLM với schema
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

# API keys
cp .env.example .env
# Edit .env với keys của bạn
```

### Required API Keys

Thêm vào `.env`:

```bash
# Anthropic (có $5 free credit cho account mới)
ANTHROPIC_API_KEY=sk-ant-api03-xxx

# Groq (HOÀN TOÀN FREE, không cần thẻ)
GROQ_API_KEY=gsk_xxx

# OpenAI (cần nạp $5 - optional)
OPENAI_API_KEY=sk-proj-xxx

# Google Gemini (FREE limited - optional)
GOOGLE_API_KEY=AIzaSy-xxx
```

Lấy keys tại:
- [Anthropic Console](https://console.anthropic.com) — Claude
- [Groq Console](https://console.groq.com) — Free Llama
- [OpenAI Platform](https://platform.openai.com) — GPT
- [Google AI Studio](https://aistudio.google.com/apikey) — Gemini

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
| **OpenAI** | GPT-4o, GPT-4o-mini | ❌ Phải nạp $5 | ❌* | ❌* | Standard |
| **Groq** | Llama 3.3 70B, Mixtral | ✅ Unlimited | ❌* | ❌* | **Siêu nhanh** |
| **Gemini** | Flash variants | ✅ Limited | ❌* | ❌* | Quota biến động |

*\* Có thể implement sau, hiện tại Tool Use & Structured Output chỉ Anthropic*

---

## 🧪 Running Evals

```bash
# Test với Groq (free)
python run_evals.py --providers groq-llama

# Compare 3 providers
python run_evals.py --providers groq-llama claude-haiku claude-sonnet
```

Bạn sẽ thấy:
- ✅ Progress bar realtime
- ✅ Summary table với pass rate, avg score, latency, cost
- ✅ HTML report tự mở browser với chi tiết từng test
- ✅ JSON export để dùng trong CI/CD

![Eval Terminal](./docs/images/demo-eval-terminal.png)
<!-- 📸 PASTE ẢNH: Terminal khi chạy eval xong, có bảng summary -->

---

## 💰 Cost Tracking

Token usage và cost được track real-time:
📊 [anthropic] 245 in + 678 out = $0.010917
📊 [groq] 245 in + 678 out = $0.000000   ← FREE!
Production pattern: **dùng Groq cho 90% tasks (free), Claude cho 10% critical tasks (paid)** → tiết kiệm chi phí 90% vs all-Claude.

---

## 🛡️ Resilience Features

DevMate có khả năng tự phục hồi khi gặp lỗi API:

| Feature | Mô tả |
|---------|-------|
| **Error Classification** | Phân loại 7 loại lỗi với suggestion cụ thể |
| **Exponential Backoff Retry** | Tự retry với delay 1s, 2s, 4s... |
| **Auto Fallback** | Provider chính lỗi → tự switch backup |
| **Context Management** | Auto trim/summarize khi vượt token limit |
| **Graceful Degradation** | App không crash trước người dùng |

---

## 🛣️ Roadmap

- [x] Multi-mode chat (chat/code/test/explain/review/agent)
- [x] Multi-provider abstraction (Claude/GPT/Groq/Gemini)
- [x] Autonomous agent với tool use
- [x] Structured output với Pydantic
- [x] Resilience layer (retry + fallback)
- [x] Smart context management
- [x] Eval suite với LLM-as-judge
- [ ] Observability với Langfuse
- [ ] RAG: Chat với codebase 1000+ files
- [ ] Multi-agent chain (planner → coder → reviewer)
- [ ] Web UI với Next.js + FastAPI
- [ ] Deploy với Docker + cloud

---

## 📊 Tech Stack

- **LLM:** Claude Sonnet 4.5, GPT-4o-mini, Llama 3.3 70B (Groq), Gemini Flash
- **CLI:** [Rich](https://github.com/Textualize/rich) (panels, tables, syntax highlighting)
- **Validation:** [Pydantic v2](https://docs.pydantic.dev)
- **Eval:** Custom LLM-as-judge với YAML test datasets
- **Tools:** subprocess + Python stdlib

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
10. **Production Patterns** — defensive programming, observability mindset

---

## 📄 License

MIT License — feel free to fork và customize.

---

## 🙏 Acknowledgments

- [Anthropic Claude](https://www.anthropic.com) — primary LLM
- [Groq](https://groq.com) — free fast Llama inference
- [Rich](https://github.com/Textualize/rich) — beautiful CLI
- Inspired by [Cursor](https://cursor.sh), [Claude Code](https://www.anthropic.com/claude-code), [Aider](https://aider.chat)

---

**Built with ❤️ as a learning journey into AI Engineering.**

*If you find this useful or want to discuss AI Engineering, feel free to reach out!*