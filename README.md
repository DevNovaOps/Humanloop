# 🌍 HumanLoop — Social Pilot Management Platform

**HumanLoop** connects **Innovators**, **NGOs**, and **Beneficiaries** to launch, manage, and track social impact pilots. It features AI-powered planning, smart NGO matching, integrated payments (Razorpay + Stripe), and real-time dashboards.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔐 Role-Based Access | Separate dashboards for Innovator, NGO, Admin, and Beneficiary |
| 🤖 AI-Powered Planning | Auto-generates pilot plans, estimates team size & beneficiaries |
| 🏢 Smart NGO Matching | Location-aware scoring with proximity detection (area → city) |
| 💳 Dual Payment Gateway | Razorpay + Stripe with 5% platform commission |
| 📊 Expense Tracking | NGOs manage expenses; Innovators have read-only view |
| 📋 Task Management | Checklist-based pilot progress tracking |
| 🔔 Notifications | Real-time alerts for assignments, payments, milestones |
| 🌐 Multilingual | Gujarati, Hindi, English support for Beneficiaries |
| 📄 Document Vault | Upload/download files per pilot |
| 🏆 Certificates | Issue completion certificates with PDF export |
| 🔒 Two-Factor Auth | TOTP-based 2FA with QR code setup |

---

## 🛠️ Tech Stack

- **Backend:** Django 4.2 (Python)
- **Database:** MySQL
- **AI Engine:** Ollama (qwen2:0.5b) + RAG engine (FAISS)
- **Payments:** Razorpay + Stripe
- **Frontend:** HTML, CSS, JavaScript (Django Templates)
- **Email:** Gmail SMTP with OTP verification

---

## 🚀 Quick Setup

### Prerequisites

- Python 3.10+
- MySQL 8.0+
- Ollama (optional, for AI features)

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/humanloop.git
cd humanloop/humanloop_backend
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
# Copy the example env file
cp .env.example .env

# Edit .env with your actual values
# (Database credentials, API keys, email config)
```

### 5. Setup MySQL Database

```sql
CREATE DATABASE humanloop CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 6. Run Migrations

```bash
python manage.py migrate
```

### 7. Create Superuser (Admin)

```bash
python manage.py createsuperuser
```

### 8. Start the Development Server

```bash
python manage.py runserver
```

Visit: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

## 📁 Project Structure

```
humanloop_backend/
├── core/                    # Main Django app
│   ├── models.py            # Database models (User, Pilot, Payment, etc.)
│   ├── views.py             # All API endpoints & page views
│   ├── ai_service.py        # AI plan generation & NGO matching
│   ├── translations.py      # Multilingual translations
│   ├── urls.py              # URL routing
│   ├── admin.py             # Django admin config
│   └── migrations/          # Database migrations
├── templates/               # HTML templates
│   ├── index.html           # Landing page
│   ├── login.html           # Login page
│   ├── register.html        # Registration page
│   ├── dashboard.html       # Innovator dashboard
│   ├── dashboard-ngo.html   # NGO dashboard
│   ├── dashboard-admin.html # Admin dashboard
│   ├── planner.html         # AI-powered pilot planner
│   ├── pilot.html           # Pilot detail & task management
│   ├── expenses.html        # Expense tracker
│   └── settings.html        # User settings & 2FA
├── static/                  # CSS, JS, images
│   ├── style.css            # Global styles
│   ├── script.js            # Global JavaScript
│   └── *.css                # Page-specific styles
├── humanloop_backend/       # Django project config
│   ├── settings.py          # Settings (reads from .env)
│   ├── urls.py              # Root URL config
│   └── wsgi.py              # WSGI entry point
├── .env                     # Environment variables (⚠️ NOT committed)
├── .env.example             # Template for .env
├── .gitignore               # Git ignore rules
├── requirements.txt         # Python dependencies
├── manage.py                # Django management script
└── README.md                # This file
```

---

## 🔑 Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | `django-insecure-xxx` |
| `DEBUG` | Debug mode | `True` |
| `DB_NAME` | MySQL database name | `humanloop` |
| `DB_USER` | MySQL username | `root` |
| `DB_PASSWORD` | MySQL password | `your_password` |
| `EMAIL_HOST_USER` | Gmail address for OTP | `you@gmail.com` |
| `EMAIL_HOST_PASSWORD` | Gmail App Password | `xxxx xxxx xxxx xxxx` |
| `RAZORPAY_KEY_ID` | Razorpay test/live key | `rzp_test_xxx` |
| `RAZORPAY_KEY_SECRET` | Razorpay secret | `xxx` |
| `STRIPE_PUBLISHABLE_KEY` | Stripe publishable key | `pk_test_xxx` |
| `STRIPE_SECRET_KEY` | Stripe secret key | `sk_test_xxx` |
| `AI_MODEL` | Ollama model name | `qwen2:0.5b` |

---

## 💳 Payment Setup

### Razorpay (Indian cards)
1. Create account at [razorpay.com](https://razorpay.com)
2. Get test keys from Dashboard → Settings → API Keys
3. Add to `.env`

### Stripe (International cards)
1. Create account at [stripe.com](https://stripe.com)
2. Get test keys from Dashboard → Developers → API Keys
3. Add to `.env`
4. Test card: `4242 4242 4242 4242` (any future date, any CVC)

---

## 🤖 AI Setup (Optional)

1. Install [Ollama](https://ollama.ai)
2. Pull the model:
   ```bash
   ollama pull qwen2:0.5b
   ```
3. The AI features will work automatically when Ollama is running

> Without Ollama, the platform uses intelligent fallback templates for plan generation.

---

## 👥 User Roles

| Role | Access |
|------|--------|
| **Innovator** | Create pilots, choose NGOs, make payments, view expenses |
| **NGO** | Accept/reject assignments, manage pilots, add expenses, manage team |
| **Admin** | Approve assignments, manage users, view audit logs |
| **Beneficiary** | Explore programs, enroll, provide feedback, multilingual support |

---

## 📝 License

This project is built for educational and social impact purposes.

---

## 🙌 Team

Built with ❤️ by the HumanLoop Team
