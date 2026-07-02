# 🌍 MoodyTrips AI — Multi-Agent Intelligent Travel Planner

MoodyTrips AI is an AI-powered travel planning assistant that transforms natural language travel requests into personalized itineraries with flight recommendations, hotel suggestions, and destination insights. Built using **LangGraph**, **LangChain**, **FastAPI**, and **Groq LLMs**, it demonstrates how multiple AI agents can collaborate to solve complex real-world planning tasks.

---

## 🚀 Features

- 🤖 Multi-Agent architecture powered by LangGraph
- ✈️ Flight recommendations using AviationStack API
- 🏨 Hotel and destination research using Tavily Search
- 🗺️ Personalized day-wise travel itinerary generation
- 💬 Natural language trip planning
- ⚡ FastAPI backend with interactive web interface
- 🧠 LLM-powered reasoning using Groq
- 💾 PostgreSQL-based conversation persistence
- 🔄 Modular and extensible agent workflow

---

## 🏗️ System Architecture

```text
                    User Request
                          │
                          ▼
                FastAPI Backend
                          │
                          ▼
                 LangGraph Workflow
        ┌────────────┬────────────┬─────────────┐
        │            │            │
        ▼            ▼            ▼
 Flight Agent   Hotel Agent   Itinerary Agent
        │            │            │
        └────────────┴────────────┘
                     │
                     ▼
               Response Agent
                     │
                     ▼
              Final Travel Plan
```

---

## 🛠 Tech Stack

### Backend

- Python
- FastAPI
- LangGraph
- LangChain
- PostgreSQL

### AI & APIs

- Groq LLM
- Tavily Search API
- AviationStack API

### Frontend

- HTML
- CSS
- JavaScript
- Jinja2 Templates

---

## 📂 Project Structure

```text
MoodyTrips/
│
├── app.py                 # FastAPI entry point
├── backend.py             # LangGraph workflow
├── requirements.txt
├── Dockerfile
├── README.md
│
├── static/
│   ├── style.css
│   └── script.js
│
├── templates/
│   └── index.html
│
└── tools/
    ├── flight_tool.py
    └── tavily_tool.py
```

---

## ⚙️ Prerequisites

Before running the project, install:

- Python 3.10+
- PostgreSQL
- Git

You'll also need API keys for:

- Groq
- Tavily
- AviationStack

---

## 🔑 Environment Variables

Create a `.env` file in the project root.

```env
DATABASE_URL=postgresql://user:password@localhost:5432/travel_db

GROQ_API_KEY=your_groq_api_key

AVIATIONSTACK_API_KEY=your_aviationstack_api_key

TAVILY_API_KEY=your_tavily_api_key

DEFAULT_ORIGIN_IATA=DAC
```

---

## 📦 Installation

Clone the repository

```bash
git clone https://github.com/rajveerpathak1/MoodyTrips.git

cd MoodyTrips
```

Create virtual environment

```bash
python -m venv .venv
```

Activate environment

### Windows

```bash
.venv\Scripts\activate
```

### Linux / macOS

```bash
source .venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

## ▶️ Run the Application

```bash
python app.py
```

Open your browser:

```
http://127.0.0.1:8000
```

---

## 📡 API Endpoints

### Health Check

```
GET /health
```

### Generate Travel Plan

```
POST /api/travel
```

Example

```json
{
    "message": "Plan a 5-day trip to Bali under $1500"
}
```

---

## 🔄 Agent Workflow

### ✈️ Flight Agent

- Finds flight information
- Suggests travel routes

### 🏨 Hotel Agent

- Searches accommodation options
- Retrieves hotel recommendations

### 🗺️ Itinerary Agent

- Creates a personalized day-by-day itinerary
- Balances sightseeing, food, and activities

### 🤖 Response Agent

- Combines outputs from all agents
- Produces the final travel plan

---


## 🚀 Future Improvements

- Google Maps integration
- Weather forecasting
- Currency conversion
- Visa information
- Expense estimation
- Restaurant recommendations
- Interactive travel chat
- Multi-language support
- Booking integrations
- User authentication

---

## 🤝 Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch

```bash
git checkout -b feature-name
```

3. Commit changes

```bash
git commit -m "Add new feature"
```

4. Push

```bash
git push origin feature-name
```

5. Open a Pull Request

---


## 👨‍💻 Author

**Rajveer Pathak**

Final Year B.Tech (Mathematics & Computing)

National Institute of Technology Kurukshetra

GitHub: https://github.com/rajveerpathak1

---
