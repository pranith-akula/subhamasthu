# Telugu NRI Dharmic Sankalp Platform

A WhatsApp-first Sankalp & Seva platform for Telugu NRI families.

## Tech Stack

- **API**: FastAPI
- **Database**: Neon Postgres
- **Cache**: Upstash Redis
- **WhatsApp**: Gupshup BSP
- **Payments**: Razorpay
- **LLM**: OpenAI GPT-4o-mini

## Setup

1. Clone and install dependencies:
```bash
python -m venv venv
.\venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and fill in your credentials.

3. Run database migrations:
```bash
python -m app.database migrate
```

4. Start the server:
```bash
uvicorn app.main:app --reload
```

## Project Structure

```
app/
├── api/webhooks/     # Gupshup + Razorpay webhooks
├── api/admin/        # Admin endpoints
├── services/         # Business logic
├── fsm/              # Conversation state machine
├── models/           # Database models
├── schemas/          # Pydantic schemas
└── workers/          # Celery tasks
```

## Environment Variables

See `.env.example` for required configuration.
