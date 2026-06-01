# 🤖 DevMate AI

> Trợ lý lập trình thông minh cho developer — CLI tool tích hợp Claude API với khả năng review code, sinh test, giải thích code, và autonomous agent.




---
# RUN
 python devmate.py


## ✨ Tính năng

### 💬 Multi-mode Chat
6 chế độ chuyên biệt, mỗi mode có system prompt tối ưu riêng:

| Mode | Mô tả |
|------|-------|
| `/chat` | Chat thường về kỹ thuật |
| `/code <file>` | Review code chuyên nghiệp |
| `/test <file>` | Sinh unit tests đầy đủ cases |
| `/explain <file>` | Giải thích code chi tiết |
| `/review <file>` | Code review chuẩn JSON (structured output) |
| `/agent <task>` | Autonomous agent có thể đọc file, search code, run command |

### 🛠️ Code Review chuyên nghiệp
- Support glob pattern: `/code "src/**/*.py"`
- Auto-detect ngôn ngữ từ extension (Python, JS, TS, Java, Dart, Go...)
- Safety limits: max 100KB/file, 10 files/request

![Code Review Demo](./docs/images/demo-code-review.png) 

### 🤖 Autonomous Agent
Agent có thể tự khám phá codebase với các tools:
- `read_file` — đọc nội dung file
- `list_files` — list folder
- `search_in_code` — grep trong code
- `run_command` — chạy shell command an toàn


### 📊 Structured Code Review (Pydantic)
Output JSON validated, dùng được trong pipeline khác:
- Score 1-10 chất lượng code
- Issues phân loại theo severity (critical/high/medium/low/info)
- Mỗi issue có line number, suggested fix, explanation


### 💰 Token Tracking
Hiển thị chi phí real-time cho mỗi câu trả lời + tổng session.


### 💾 Save / Load Chat
Lưu lịch sử ra JSON, load lại bất kỳ session nào.

---

## 🚀 Cài đặt

### Yêu cầu
- Python 3.12+
- macOS / Linux / Windows
- API key của Anthropic ([đăng ký miễn phí](https://console.anthropic.com), có $5 free)

### Setup

```bash
# Clone repo
git clone https://github.com//devmate-ai.git
cd devmate-ai

# Tạo virtual environment
python3.12 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Cài dependencies
pip install -r requirements.txt

# Tạo file .env và paste API key
echo "ANTHROPIC_API_KEY=sk-ant-api03-your-key-here" > .env

# Chạy
python devmate.py
```

---

## 📚 Hướng dẫn sử dụng

### Khởi động
```bash
python devmate.py
```

### Các lệnh cơ bản

```bash
# Chat thường
💬 Bạn: Giải thích async/await trong Python

# Review file đơn
💬 Bạn: /code src/auth.py

# Review cả folder
💬 Bạn: /code src/auth/

# Review với glob pattern
💬 Bạn: /code "src/**/*.py"

# Sinh unit test
💬 Bạn: /test utils/helper.js

# Giải thích code
💬 Bạn: /explain components/Login.tsx

# Structured review (output JSON)
💬 Bạn: /review src/payment.py

# Agent tự khám phá
💬 Bạn: /agent
🤖 Bạn: Project có chỗ nào dùng MD5 không? Có nguy hiểm không?
```

### Tiện ích

```bash
/save           # Lưu lịch sử chat hiện tại
/load           # Load chat đã lưu
/clear          # Xóa lịch sử session hiện tại
/stats          # Xem token usage & chi phí
/help           # Hiện tất cả commands
/quit           # Thoát
```

---

## 🏗️ Kiến trúc
devmate-ai/
├── devmate.py              # Entry point, main loop, CLI
├── prompts.py              # System prompts cho mỗi mode
├── file_handler.py         # Đọc file/folder, glob pattern
├── tools.py                # Tools cho Agent (read_file, search, ...)
├── schemas.py              # Pydantic schemas (CodeIssue, ReviewReport)
├── structured_output.py    # Helper gọi LLM với structured output
├── data/                   # Lưu chat history & review reports (gitignored)
└── .env                    # API keys (gitignored)

### Tech Stack
- **LLM:** Claude Sonnet 4.5 ([Anthropic API](https://docs.claude.com))
- **CLI UI:** [Rich](https://github.com/Textualize/rich) cho panels, tables, syntax highlighting
- **Validation:** [Pydantic v2](https://docs.pydantic.dev) cho structured output
- **Tools:** subprocess + Python stdlib

### Patterns được áp dụng
- **Multi-turn conversation** với context window management
- **System prompt versioning** (tách prompts ra file riêng)
- **Tool Use / Function Calling** cho agent autonomous
- **Structured Output** qua forced tool_use + Pydantic validation
- **Streaming response** cho UX tốt
- **Token tracking & cost calculation** real-time


---

## 💰 Chi phí

DevMate dùng Claude Sonnet 4.5 với giá:
- **Input:** $3 / 1M tokens
- **Output:** $15 / 1M tokens

Chi phí thực tế:
- Câu hỏi đơn giản: ~$0.001 - $0.005
- Code review 1 file: ~$0.01 - $0.04
- Agent task (5-10 iterations): ~$0.02 - $0.10

Với $5 free credit của Anthropic → đủ dùng vài trăm câu trả lời.

---

## 🔒 Bảo mật

- ✅ API key lưu trong `.env`, không bao giờ commit
- ✅ `run_command` whitelist các lệnh an toàn (ls, cat, git, ...)
- ✅ File size limits để tránh leak data lớn
- ✅ Path validation cho mọi file operation

---

## 🛣️ Roadmap

- [ ] Web UI với Next.js + FastAPI
- [ ] RAG để chat với codebase lớn (1000+ files)
- [ ] Memory persistence với vector DB
- [ ] Multi-agent (planner + coder + reviewer)
- [ ] Fine-tune model nhỏ cho task đơn giản
- [ ] Deploy lên cloud với Docker

---

## 📄 License

MIT License — feel free to fork, modify, and use.

---

## 🙏 Acknowledgments

- Powered by [Anthropic Claude](https://www.anthropic.com)
- CLI styling với [Rich](https://github.com/Textualize/rich)
- Inspired by [Cursor](https://cursor.sh), [Claude Code](https://www.anthropic.com/claude-code), [Aider](https://aider.chat)

---

**Built with ❤️ as an AI Engineering learning project.**