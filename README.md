# AI Buildathon(Autonomous AI Payment Recovery Agent)

An enterprise-grade, multi-channel payment recovery system designed for e-commerce checkouts. Powered by **LangGraph**, **FastAPI**, **Razorpay**, **WhatsApp Business API**, and **Sarvam AI Voice**, this system autonomously re-engages customers with abandoned or failed checkouts using synchronized WhatsApp messaging and voice outreach.

---

## Key Features

- **Multi-Channel Orchestration**: Synchronizes voice calls (via Sarvam AI) and interactive WhatsApp messages in lockstep.
- **Autonomous Negotiation**: Authorizes the AI agent ("Arjun") to generate full-price or discounted (up to 5%) Razorpay payment links dynamically based on customer intent.
- **State Synchronization & Task Revocation**: Immediately revokes pending call tasks and recovery workflows via Celery when a `payment.captured` webhook is received.
- **Smart Context Resolution**: Features database entity resolution to map UUIDs, Razorpay Order IDs, and LangGraph `thread_id` context seamlessly.

---

## Tech Stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Framework** | FastAPI / Python 3.11+ | Asynchronous REST API and webhook processing |
| **Agent Framework** | LangGraph & LangChain | Stateful multi-turn conversation and tool orchestration |
| **Task Queue** | Celery  | Asynchronous scheduling and voice task execution |
| **Database** | PostgreSQL + SQLAlchemy | Transactional persistence and LangGraph state checkpoints |
| **LLM Provider** | OpenRouter / OpenAI | Conversational intelligence and reasoning |
| **Voice Engine** | Sarvam AI Telephony API | Localized outbound AI voice calls |
| **Messaging** | Meta WhatsApp Graph API (v20.0) | Direct customer messaging and interactive retry links |
| **Payment Gateway** | Razorpay | Checkout tracking and payment link generation |

---

## System Architecture

```text
                   ┌───────────────────────┐
                   │ Razorpay / WhatsApp   │
                   └──────────┬────────────┘
                              │
                       Webhook Event
                              │
                              ▼
                   ┌───────────────────────┐
                   │   FastAPI Webhooks    │
                   └──────────┬────────────┘
                              │
            ┌─────────────────┴─────────────────┐
            ▼                                   ▼
   ┌──────────────────┐                ┌──────────────────┐
   │ PostgreSQL Store │                │ LangGraph Agent  │
   │ (Checkouts/Jobs) │                │  (Arjun Logic)   │
   └────────┬─────────┘                └────────┬─────────┘
            │                                   │
            │          ┌─────────────────┐      │
            └─────────►│  Celery Worker  │◄─────┘
                       └────────┬────────┘
                                │
                 ┌──────────────┴──────────────┐
                 ▼                             ▼
        ┌────────────────────┐       ┌────────────────────┐
        │  WhatsApp Service  │       │   Sarvam Voice     │
        └────────────────────┘       └────────────────────┘
```

---

## Repository Structure

```text
├── src/
│   ├── agent/
│   │   ├── graph.py
│   │   │   # LangGraph compilation and execution thread management
│   │   ├── nodes.py
│   │   │   # LangGraph execution nodes
│   │   ├── prompts.py
│   │   │   # System prompt, guardrails, and negotiation limits
│   │   └── tools.py
│   │       # Agent tool definitions
│   │
│   ├── api/
│   │   └── webhooks/
│   │       # Razorpay, WhatsApp, and Sarvam webhooks
│   │
│   ├── application/
│   │   ├── payment_service.py
│   │   │   # Razorpay API integration
│   │   ├── recovery_service.py
│   │   │   # Task cancellation and state cleanup
│   │   ├── voice_service.py
│   │   │   # Sarvam voice dispatch and cooldown management
│   │   └── whatsapp_service.py
│   │       # Meta WhatsApp messaging client
│   │
│   ├── infrastructure/
│   │   ├── clients/
│   │   │   # OpenRouter, Sarvam, WhatsApp clients
│   │   └── postgres/
│   │       # DB models, sessions, and repositories
│   │
│   └── jobs/
│       ├── celery_app.py
│       │   # Celery queue configuration
│       └── tasks.py
│           # Background voice dispatch tasks
│
├── main.py
│   # FastAPI application entrypoint
│
├── requirements.txt
│   # Project dependencies
│
├── .env
│   # Environment variables
│
└── README.md


```

## Core Agent Tools

| Tool Name | Key Parameters | Purpose |
| :--- | :--- | :--- |
| `send_whatsapp_message` | `phone_number`, `text` | Sends text or interactive messages |
| `generate_payment_link` | `phone_number`, `amount_in_inr`, `checkout_id` | Generates a full-price Razorpay retry link |
| `generate_discounted_payment_link` | `phone_number`, `amount_in_inr`, `discount_pct`, `checkout_id` | Generates a discounted retry link capped at 5% |
| `trigger_immediate_voice_call` | `phone_number`, `checkout_id`, `force_call` | Triggers an outbound Sarvam AI call |
| `reschedule_voice_call` | `checkout_id`, `new_eta_seconds` | Reschedules a voice retry |
| `verify_payment_status` | `checkout_id` | Checks whether payment is completed |
| `cancel_recovery_workflow` | `checkout_id` | Cancels scheduled jobs and active recovery workflows |

---

## Agent Decision Flow

```text
                    ┌──────────────────────┐
                    │ Checkout Abandoned   │
                    │   / Payment Failed   │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    Arjun Agent       │
                    │    LangGraph         │
                    └──────────┬───────────┘
                               │
                  ┌────────────┴────────────┐
                  ▼                         ▼
          ┌───────────────┐         ┌───────────────┐
          │   WhatsApp    │         │     Voice     │
          └───────┬───────┘         └───────┬───────┘
                  │                         │
                  └────────────┬────────────┘
                               ▼
                    ┌──────────────────────┐
                    │ Customer Responds    │
                    └──────────┬───────────┘
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
        ┌─────────┐     ┌─────────────┐   ┌─────────────┐
        │   Pay   │     │ Negotiate   │   │ No Response │
        └────┬────┘     └──────┬──────┘   └──────┬──────┘
             │                 │                 │
             │                 ▼                 ▼
             │          ┌─────────────┐   ┌─────────────┐
             │          │ Up to 5%    │   │ Reschedule  │
             │          │ Discount    │   │ Voice Call  │
             │          └──────┬──────┘   └─────────────┘
             │                 │
             └────────┬────────┘
                      ▼
             ┌──────────────────┐
             │ Payment Captured │
             └────────┬─────────┘
                      ▼
             ┌──────────────────┐
             │ Cancel Recovery  │
             │    Workflow      │
             └──────────────────┘
```

---

## Payment Recovery Lifecycle

```text
Checkout Abandoned / Payment Failed
                │
                ▼
        FastAPI Webhook/API
                │
                ▼
        PostgreSQL Checkout
                │
                ▼
        LangGraph "Arjun"
                │
        ┌───────┴────────┐
        ▼                ▼
   WhatsApp          Voice Task
        │                │
        └───────┬────────┘
                ▼
        Customer Response
                │
        ┌───────┼───────────┐
        ▼       ▼           ▼
      Pay    Negotiate   No Response
        │       │           │
        │       ▼           ▼
        │   Discounted   Reschedule
        │      Link       Voice Call
        │
        ▼
 payment.captured
        │
        ▼
 Cancel Recovery Workflow
        │
        ▼
      COMPLETE
```



## Webhook Handling

The system treats successful payment events as authoritative termination signals.

When a `payment.captured` webhook is received:

1. Resolve the associated checkout.
2. Identify the corresponding Razorpay order/payment.
3. Mark the checkout as `PAID`.
4. Cancel pending Celery voice tasks.
5. Terminate active recovery workflows.
6. Stop further WhatsApp outreach.
7. Stop further voice outreach.
8. Persist the final recovery state.

This prevents customers who have already completed payment from receiving additional recovery messages or calls.

---



