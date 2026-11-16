# PS-22 Proactive Digital Engagement Agent

A full-stack, customer-selectable proactive engagement prototype.

## What this version does

- Loads every customer from `data/PS22_dataset.xlsx` into SQLite on first backend startup.
- Does **not** seed predefined demo customers or scenario buttons.
- Lets you select/search any customer from Customer Explorer.
- Runs the same multi-agent pipeline for the selected customer.
- Uses Groq for cautious need inference and message generation when configured.
- Uses deterministic rules for signal derivation, channel selection, consent/suppression and escalation.
- Stores generated AI decisions, escalation cases and audit logs in SQLite.
- Dashboard and analytics use database records rather than hard-coded demo metrics.

## Project layout

```text
ps22-proactive-agent/
├── backend/
│   ├── app/
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
├── data/
│   └── PS22_dataset.xlsx
├── frontend/
│   ├── src/
│   ├── package.json
│   └── Dockerfile
└── docker-compose.yml
```

## 1. Backend setup (Windows PowerShell)

Open a terminal in the project root:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell says script execution is disabled, use Command Prompt instead:

```cmd
.venv\Scripts\activate.bat
```

## 2. Configure Groq

Inside `backend`, copy `.env.example` to `.env` and set your key:

```env
AI_PROVIDER=groq
GROQ_API_KEY=YOUR_GROQ_API_KEY
MODEL_NAME=llama-3.3-70b-versatile
DATABASE_URL=sqlite:///./ps22.db
```

`DATABASE_URL=sqlite:///./ps22.db` means: create/use a local SQLite file named `ps22.db` in the backend working directory. You do not need to create this file yourself.

Never commit your real API key.

## 3. Start the backend

From `backend`:

```powershell
uvicorn app.main:app --reload --port 8000
```

On startup the application imports the workbook into SQLite if the customer table is empty.

## 4. Start the frontend

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

## 5. How to demonstrate the project

1. Open **Customer Explorer**.
2. Search or select any customer, for example `CUST00001`.
3. Inspect the customer's profile, behavioral snapshots, transactions and engagement history.
4. Click **Run AI Analysis**.
5. The application sends that customer's actual context through the agent pipeline.
6. The Need Inference and Message Generation stages use Groq when the key is configured.
7. Review the final decision, suppression/consent result, channel, message and escalation result.
8. Open Decision Center or Audit Logs to see the generated decision stored in SQLite.

There are no predefined financial-stress/investment/savings demo buttons in this version.

## Important: resetting the local database

If you previously ran an older version that contained hard-coded demo customers, stop the backend and delete:

```text
backend/ps22.db
```

Then start the backend again. It will rebuild the database from the workbook.

Do **not** delete `data/PS22_dataset.xlsx`.

## Agent flow

```text
Customer selection
      ↓
Signal Ingestion Agent
      ↓
Behavioral Shift Agent
      ↓
Need Inference Agent ── Groq
      ↓
Next Best Action Agent
      ↓
Message Generation Agent ── Groq
      ↓
Channel & Timing Agent
      ↓
Suppression & Consent Agent
      ↓
Response Tracking Agent
      ↓
Sensitive Escalation Agent
      ↓
Orchestrator Agent
      ↓
Final decision + audit record
```

## Data / AI boundary

The LLM is instructed to treat life events, financial stress, vulnerability and intent as hypotheses rather than facts. Governance decisions are kept deterministic so that opt-out, suppression, cooldown and escalation rules are not left entirely to the LLM.

## Docker

Create `backend/.env` first, then from the project root:

```powershell
docker compose up --build
```

The browser frontend runs on port `5173` and the API on port `8000`.
