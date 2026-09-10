import os 
import warnings
warnings.filterwarnings("ignore")
import certifi
import re
from dotenv import load_dotenv

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

from typing import TypedDict, Annotated
import operator
import uuid

import psycopg
from psycopg.rows import dict_row

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)
from langchain_groq import ChatGroq
from tools.tavily_tool import tavily_search
from tools.flight_tool import search_flights, find_location_mentions
from tools.railkit_tool import search_trains_between_stations, get_seat_availability
from database import get_db_url

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing. Please add it to your .env file.")


# =========================
# LLM & Clean Helper
# =========================

# =========================
# LLM & Fallback Helper
# =========================

def invoke_groq_llm(messages, max_tokens: int = 3500, temperature: float = 0.3):
    """
    Invokes Groq LLM with fallback chain across top-performing high-capacity models:
    1. openai/gpt-oss-120b (Primary: Best quality & reasoning)
    2. qwen/qwen3.8-27b (Fallback 1: High detail output)
    3. openai/gpt-oss-20b (Fallback 2: Fast & reliable)
    """
    candidate_models = [
        "openai/gpt-oss-120b",
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-20b"
    ]
    
    last_error = None
    for model_name in candidate_models:
        try:
            llm_inst = ChatGroq(
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return llm_inst.invoke(messages)
        except Exception as e:
            print(f"[LLM Fallback Warning] Model {model_name} failed: {e}. Trying next model...", flush=True)
            last_error = e
            
    raise RuntimeError(f"All candidate Groq models failed. Last error: {last_error}")

def clean_llm_response(text: str) -> str:
    """
    Strips raw <think>...</think> tags (both closed and unclosed) and any meta-draft preambles
    so the output starts cleanly at the first markdown header.
    """
    if not text:
        return ""
    # 1. Remove closed <think>...</think> tags
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # 2. Handle unclosed <think> tags
    if "<think>" in cleaned:
        if "</think>" in cleaned:
            cleaned = cleaned.split("</think>")[-1].strip()
        else:
            match = re.search(r"(#+\s+.*)", cleaned, flags=re.DOTALL)
            if match:
                cleaned = match.group(1).strip()
            else:
                cleaned = re.sub(r"<think>.*", "", cleaned, flags=re.DOTALL).strip()
    
    # 3. Strip any preamble before the first Markdown header (# 🌍 1. Trip Summary or # ...)
    header_match = re.search(r"(#+\s+.*)", cleaned, flags=re.DOTALL)
    if header_match:
        cleaned = header_match.group(1).strip()

    return cleaned


# =========================
# State
# =========================

class TravelState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    flight_results: str
    hotel_results: str
    ground_transport_results: str
    weather_results: str
    budget_breakdown: str
    itinerary: str
    llm_calls: Annotated[int, operator.add]


# =========================
# Flight Agent
# =========================

def flight_agent(state: TravelState):
    query = state["user_query"]
    try:
        flight_data = search_flights(query)
    except Exception as e:
        flight_data = f"Could not fetch flight data: {e}"

    return {
        "flight_results": str(flight_data)[:1200],
        "messages": [
            AIMessage(content="Flight results fetched.")
        ],
        "llm_calls": 1
    }


# =========================
# Hotel Agent
# =========================

def hotel_agent(state: TravelState):
    query = f"Best hostels hotels homestays near top monuments for {state['user_query']}"
    try:
        hotel_results = tavily_search(query)
    except Exception as e:
        hotel_results = f"Could not fetch hotel data: {e}"

    return {
        "hotel_results": str(hotel_results)[:1200],
        "messages": [
            AIMessage(content="Hotel and lodging options fetched.")
        ],
        "llm_calls": 1
    }


# =========================
# Ground Transport Agent
# =========================

def ground_transport_agent(state: TravelState):
    query = state["user_query"]
    output = ""
    try:
        mentions = find_location_mentions(query)
        
        date_match = re.search(
            r"(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*|\d{1,2}[-/\s.]+\d{1,2}[-/\s.]+\d{2,4})", 
            query, 
            re.IGNORECASE
        )
        date_str = date_match.group(1) if date_match else None

        if len(mentions) >= 2:
            origin = mentions[0]
            destination = mentions[1]
        elif len(mentions) == 1:
            origin = "Delhi"
            destination = mentions[0]
        else:
            origin = "Delhi"
            destination = "Jaipur"
            
        print(f"[Ground Agent] Querying trains between {origin} and {destination} for date: {date_str}", flush=True)
        res = search_trains_between_stations(origin, destination, date_str)
        
        if res.get("success") and res.get("trains"):
            trains = res["trains"][:3]
            output += f"### Live Direct Train Schedule from {res['from_code']} to {res['to_code']} ({res['date']}):\n\n"
            for t in trains:
                output += f"- **Train {t['train_no']}** ({t['train_name']})\n"
                output += f"  - Departs: {t['from_time']} | Arrives: {t['to_time']} | Duration: {t['travel_time']}\n"
                
                avail_data = None
                queried_class = "3A"
                for cls in ["3A", "CC", "SL"]:
                    avail_res = get_seat_availability(t['train_no'], t['from_stn_code'], t['to_stn_code'], res['date'], cls)
                    if avail_res.get("success") and "data" in avail_res:
                        avail_data = avail_res["data"]
                        queried_class = cls
                        break
                
                if avail_data:
                    fare = avail_data.get("fare", {}).get("totalFare", "N/A")
                    output += f"  - Fare ({queried_class}): ₹{fare}\n"
                    
                    dates_avail = avail_data.get("availability", [])[:3]
                    if dates_avail:
                        avail_texts = [f"{d['date']}: {d['availabilityText']} ({d['prediction']})" for d in dates_avail]
                        output += f"  - Availability: {', '.join(avail_texts)}\n"
                output += "\n"
        else:
            print(f"[Ground Agent] Falling back to web search for driving/bus directions for {origin} to {destination}", flush=True)
            tavily_query = f"How to travel from {origin} to {destination} by bus or taxi schedule fares"
            output = tavily_search(tavily_query)
    except Exception as e:
        output = f"Could not fetch ground transport data: {e}"
        
    return {
        "ground_transport_results": str(output)[:1200],
        "messages": [
            AIMessage(content="Ground transport details fetched.")
        ],
        "llm_calls": 1
    }


# =========================
# Weather Agent
# =========================

def weather_agent(state: TravelState):
    query = f"Current weather conditions and climate forecast for {state['user_query']}"
    try:
        weather_results = tavily_search(query)
    except Exception as e:
        weather_results = f"Could not fetch weather data: {e}"

    return {
        "weather_results": str(weather_results)[:800],
        "messages": [
            AIMessage(content="Weather and climate forecast fetched.")
        ],
        "llm_calls": 1
    }


# =========================
# Detailed Itinerary Agent Node
# =========================

def itinerary_agent(state: TravelState):
    prompt = f"""
User Query: {state['user_query']}
Flight Information: {state['flight_results']}
Train & Ground Transit: {state['ground_transport_results']}
Hotel & Hostel Options: {state['hotel_results']}
Weather & Season: {state['weather_results']}

Generate a deeply detailed Day-by-Day itinerary. Include:
- Morning, Afternoon, Evening, and Night time slots for each day.
- Exact names of historical monuments, heritage spots, and local markets.
- Specific authentic dining recommendations (named local restaurants, famous street food items).
- Ticket prices in INR and transport choices between attractions.
"""
    res = invoke_groq_llm([
        SystemMessage(content="You are an expert travel itinerary planner. Generate rich, detailed day-by-day travel plans."),
        HumanMessage(content=prompt)
    ], max_tokens=3000)
    return {
        "itinerary": res.content,
        "llm_calls": 1
    }


# =========================
# Master Travel Planner Agent Node
# =========================

def travel_planner_agent(state: TravelState):
    prompt = f"""
User Request:
{state['user_query']}

Retrieved Real-Time Flight Data:
{state['flight_results']}

Retrieved Train / Ground Transit Data:
{state['ground_transport_results']}

Retrieved Hotel / Hostel Recommendations:
{state['hotel_results']}

Retrieved Weather Forecast:
{state['weather_results']}

Detailed Day-by-Day Itinerary Plan:
{state['itinerary']}

INSTRUCTIONS FOR MASTERPLAN SYNTHESIS:
- Output clean, beautiful, publication-ready Markdown.
- You MUST start directly at "# 🌍 1. Trip Summary" without any preambles, draft notes, or echoing these instructions.
- Ensure all 8 sections are fully populated with rich tables, prices, landmark names, local food, and step-by-step guidance.

Use these exact Markdown section headings:

# 🌍 1. Trip Summary
- **Origin & Destination**: Origin → Destination
- **Duration**: Days & Nights
- **Budget Target**: Total per person ceiling with buffer estimate
- **Traveler Persona & Vibe**: Tailored travel style

# 🌤️ 2. Weather Forecast & Smart Packing Checklist
- **Expected Weather**: Temperatures, humidity, rain probability
- **Packing Essentials**: Apparel, footwear, electronics, gear tailored to destination

# ✈️ 3. Flight & Air Route Options
Markdown table of routes, carriers, layovers, and approximate fares.

# 🚂 4. Train & Ground Transit Guide
Markdown table of direct trains (train numbers, departure/arrival times, classes, fares) and local commute guidelines (auto, bus, rentals).

# 🏨 5. Recommended Stays (Hostels & Hotels)
Markdown table of top budget hostels/hotels with nightly rates, location perks, and key highlights.

# 💰 6. Itemized Budget Breakdown
Markdown table with itemized categories (Transit, Lodging, Food, Sightseeing & Tickets, Buffer, Total).

# 🗺️ 7. Day-by-Day Detailed Itinerary
Full Day-by-Day schedule (Morning, Afternoon, Evening, Night) with exact times, monuments, ticket prices, and named local food joints.

# 🎟️ 8. Step-by-Step Booking & Execution Guide
Concrete step-by-step instructions for booking train, stay, local transport, entry tickets, and execution.
"""

    response = invoke_groq_llm([
        SystemMessage(content="You are MoodyTrips AI master concierge. Output publication-ready markdown starting immediately at '# 🌍 1. Trip Summary'."),
        HumanMessage(content=prompt)
    ], max_tokens=3500)

    clean_content = clean_llm_response(response.content)

    return {
        "budget_breakdown": clean_content,
        "messages": [AIMessage(content=clean_content)],
        "llm_calls": 1
    }


# =========================
# Build Graph Pipeline
# =========================

graph = StateGraph(TravelState)

graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("ground_transport_agent", ground_transport_agent)
graph.add_node("weather_agent", weather_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("travel_planner_agent", travel_planner_agent)

# Fan-out parallel research execution
graph.add_edge(START, "flight_agent")
graph.add_edge(START, "hotel_agent")
graph.add_edge(START, "ground_transport_agent")
graph.add_edge(START, "weather_agent")

# Fan-in into itinerary_agent
graph.add_edge("flight_agent", "itinerary_agent")
graph.add_edge("hotel_agent", "itinerary_agent")
graph.add_edge("ground_transport_agent", "itinerary_agent")
graph.add_edge("weather_agent", "itinerary_agent")

# Flow into travel_planner_agent
graph.add_edge("itinerary_agent", "travel_planner_agent")
graph.add_edge("travel_planner_agent", END)


# =========================
# PostgreSQL Checkpointer
# =========================
DATABASE_URL = get_db_url()

_conn = psycopg.connect(
    DATABASE_URL,
    autocommit=True,
    row_factory=dict_row
)

checkpointer = PostgresSaver(_conn)
checkpointer.setup()

travel_graph = graph.compile(checkpointer=checkpointer)


# =========================
# Function for FastAPI
# =========================

def run_travel_agent(user_input: str, thread_id: str | None = None):
    if not thread_id:
        thread_id = f"user_{uuid.uuid4().hex}"

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    result = travel_graph.invoke(
        {
            "messages": [
                HumanMessage(content=user_input)
            ],
            "user_query": user_input,
            "flight_results": "",
            "hotel_results": "",
            "ground_transport_results": "",
            "weather_results": "",
            "budget_breakdown": "",
            "itinerary": "",
            "llm_calls": 0
        },
        config=config
    )

    final_answer = result["messages"][-1].content

    return {
        "thread_id": thread_id,
        "answer": final_answer,
        "flight_results": result.get("flight_results", ""),
        "hotel_results": result.get("hotel_results", ""),
        "ground_transport_results": result.get("ground_transport_results", ""),
        "weather_results": result.get("weather_results", ""),
        "budget_breakdown": result.get("budget_breakdown", ""),
        "itinerary": result.get("itinerary", ""),
        "llm_calls": result.get("llm_calls", 0),
    }
