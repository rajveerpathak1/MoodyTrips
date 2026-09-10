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
# LLM
# =========================

llm = ChatGroq(
    model="qwen/qwen3.6-27b",
    temperature=0.2,
    max_tokens=800,
)


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
    llm_calls: int


# =========================
# Flight Agent
# =========================

def flight_agent(state: TravelState):
    query = state["user_query"]
    flight_data = search_flights(query)

    return {
        "flight_results": flight_data,
        "messages": [
            AIMessage(content="Flight results fetched.")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


# =========================
# Hotel Agent
# =========================

def hotel_agent(state: TravelState):
    query = f"Best hotels, hostels, and homestays for {state['user_query']}"
    hotel_results = tavily_search(query)

    return {
        "hotel_results": hotel_results,
        "messages": [
            AIMessage(content="Hotel and lodging options fetched.")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


# =========================
# Ground Transport Agent
# =========================

def ground_transport_agent(state: TravelState):
    query = state["user_query"]
    mentions = find_location_mentions(query)
    
    # Extract travel date matches (e.g. 15-08-2026 or 15 Aug)
    date_match = re.search(
        r"(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*|\d{1,2}[-/\s.]+\d{1,2}[-/\s.]+\d{2,4})", 
        query, 
        re.IGNORECASE
    )
    date_str = date_match.group(1) if date_match else None

    # Resolve origin and destination
    if len(mentions) >= 2:
        origin = mentions[0]
        destination = mentions[1]
    elif len(mentions) == 1:
        origin = "Delhi"
        destination = mentions[0]
    else:
        origin = "Delhi"
        destination = "Jaipur"
        
    print(f"[Ground Agent] Querying trains between {origin} and {destination} for date: {date_str}")
    res = search_trains_between_stations(origin, destination, date_str)
    
    output = ""
    if res.get("success") and res.get("trains"):
        trains = res["trains"][:3]  # Top 3 trains
        output += f"### Live Direct Train Schedule from {res['from_code']} to {res['to_code']} ({res['date']}):\n\n"
        for t in trains:
            output += f"- **Train {t['train_no']}** ({t['train_name']})\n"
            output += f"  - Departs: {t['from_time']} | Arrives: {t['to_time']} | Duration: {t['travel_time']}\n"
            
            # Fetch real-time seat availability & fares
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
                
                dates_avail = avail_data.get("availability", [])[:3]  # Next 3 dates
                if dates_avail:
                    avail_texts = [f"{d['date']}: {d['availabilityText']} ({d['prediction']})" for d in dates_avail]
                    output += f"  - Availability: {', '.join(avail_texts)}\n"
            output += "\n"
    else:
        # Fallback to Tavily Search for bus / taxi transport
        print(f"[Ground Agent] Falling back to web search for driving/bus directions for {origin} to {destination}")
        tavily_query = f"How to travel from {origin} to {destination} by bus or taxi schedule fares"
        output = tavily_search(tavily_query)
        
    return {
        "ground_transport_results": output,
        "messages": [
            AIMessage(content="Ground transport details fetched.")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


# =========================
# Weather Agent
# =========================

def weather_agent(state: TravelState):
    query = f"Current weather conditions and travel season forecast for {state['user_query']}"
    weather_results = tavily_search(query)

    return {
        "weather_results": weather_results,
        "messages": [
            AIMessage(content="Weather and climate forecast fetched.")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


# =========================
# Budget Optimizer Agent
# =========================

def budget_agent(state: TravelState):
    prompt = f"""
You are an expert value-oriented travel budget planner and cost optimizer.
Your goal is to maximize travel experiences while minimizing total cost, keeping it strictly within the user's budget if specified.

User Request:
{state['user_query']}

Retrieved Flight Information:
{state['flight_results']}

Retrieved Train / Ground Transport Information:
{state['ground_transport_results']}

Retrieved Hotel Information:
{state['hotel_results']}

Perform the following calculations and optimizations:
1. Estimate target allocations based on user's budget ceiling or typical destination costs (Flights/Trains, Accommodations, Food & Dining, Daily Activities & Transit).
2. Compare the retrieved options against this allocation. Mention if trains/buses are a cheaper alternative to flights for domestic routes!
3. Formulate an experience-maximizing cost-reduction strategy (e.g. recommending booking Zostel hostels, public transit passes, or free sightseeing events).
4. Output a Markdown table displaying the itemized Cost Breakdown:
   - Category
   - Estimated Cost (specify currency)
   - Optimization Strategy / Detail

Provide the markdown table and a brief explanation of the value-maximization choices. Keep the tone professional, structured, and easy to follow.
"""
    response = llm.invoke([
        SystemMessage(content="You are a value-focused travel budget planning specialist."),
        HumanMessage(content=prompt)
    ])

    return {
        "budget_breakdown": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


# =========================
# Itinerary Agent
# =========================

def itinerary_agent(state: TravelState):
    prompt = f"""
Create a complete day-by-day travel itinerary.

User Query:
{state['user_query']}

Flight Recommendations:
{state['flight_results']}

Hotel Recommendations:
{state['hotel_results']}

Train / Ground Recommendations:
{state['ground_transport_results']}

Weather Forecast & Climate:
{state['weather_results']}

Budget Breakdown & Cost Savings Strategy:
{state['budget_breakdown']}

Make the itinerary practical, budget-aware, weather-appropriate, and easy to follow.
Detail the activities, meals, and transit suggestions for each day.
If the user provided specific travel dates, build the itinerary starting exactly on those dates.
"""

    response = llm.invoke([
        SystemMessage(content="You are an expert travel planner."),
        HumanMessage(content=prompt)
    ])

    return {
        "itinerary": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


# =========================
# Final Response Agent
# =========================

def final_agent(state: TravelState):
    final_prompt = f"""
Generate the final, comprehensive travel plan response for the user.

User Request:
{state['user_query']}

Flights:
{state['flight_results']}

Train / Bus Transport:
{state['ground_transport_results']}

Hotels & Hostels:
{state['hotel_results']}

Weather Forecast:
{state['weather_results']}

Budget breakdown table:
{state['budget_breakdown']}

Itinerary:
{state['itinerary']}

Combine all of the information above and format the final answer beautifully using these exact sections:

1. Trip Summary
2. Weather Forecast & Packing Tips
3. Flight & Route Information (suggest Skyscanner links)
4. Train & Bus Schedule (for Indian routes, provide IRCTC/Redbus search recommendations and ticket prices!)
5. Lodging Suggestions (specifically mention options like Zostel/Hosteller if budget-friendly)
6. Cost Breakdown & Budget Optimization (include the markdown cost table here!)
7. Day-by-Day Itinerary (adapt based on weather, budget, transit, and dates)
8. Specific Booking Instructions (explain step-by-step how to book the flight, train on IRCTC, and hostel/hotel for these specific dates)

Important:
- Be clear, practical, and helpful.
- Mention that live flight API may not provide ticket prices if pricing is unavailable.
- Ensure the final document looks clean and professional.
"""

    response = llm.invoke([
        SystemMessage(content="You are a professional AI travel assistant for MoodyTrips."),
        HumanMessage(content=final_prompt)
    ])

    return {
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


# =========================
# Build Graph
# =========================

graph = StateGraph(TravelState)

graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("ground_transport_agent", ground_transport_agent)
graph.add_node("weather_agent", weather_agent)
graph.add_node("budget_agent", budget_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("final_agent", final_agent)

graph.add_edge(START, "flight_agent")
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "ground_transport_agent")
graph.add_edge("ground_transport_agent", "weather_agent")
graph.add_edge("weather_agent", "budget_agent")
graph.add_edge("budget_agent", "itinerary_agent")
graph.add_edge("itinerary_agent", "final_agent")
graph.add_edge("final_agent", END)


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
