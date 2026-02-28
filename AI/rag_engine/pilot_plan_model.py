"""
Pilot Plan AI Model for HumanLoop

Accepts structured form inputs (Type of Activity, Location, Target Date, Budget,
Volunteers, Target Beneficiaries) and returns a generated Pilot Plan + sources.
Designed to connect to the "Generate Pilot Plan" web form.

Connecting the form later (e.g. Django / fetch):
  1. On "Generate Pilot Plan" submit, POST JSON:
     {
       "type_of_activity": "<dropdown value>",
       "location_area": "e.g. Sector 15, Rajasthan",
       "target_date": "dd-mm-yyyy",
       "estimated_budget": 25000,
       "expected_volunteers": 30,
       "target_beneficiaries": 200
     }
  2. Backend: result = generate_pilot_plan_from_dict(request.json())
  3. Return result["plan"] and result["sources"] to the page.
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

# Fastest models first (smallest = quickest). Install with: ollama pull qwen2:0.5b
FAST_MODELS = ["qwen2:0.5b", "tinyllama", "phi3:mini", "mistral"]

# Suggested dropdown options for "Type of Activity" (use on the form)
ACTIVITY_TYPE_OPTIONS = [
    "Education & Literacy",
    "Health & Nutrition",
    "Environment & Conservation",
    "Women Empowerment",
    "Rural Development",
    "Child Welfare",
    "Livelihoods & Skill Development",
    "Water & Sanitation",
    "Disaster Relief",
    "Tribal Welfare",
    "Urban Slum Development",
    "Youth & Sports",
]


@dataclass
class PilotPlanInput:
    """Input fields matching the Generate Pilot Plan form."""
    type_of_activity: str          # e.g. "Education", "Health", "Environment"
    location_area: str             # e.g. "Sector 15, Rajasthan"
    target_date: str               # e.g. "dd-mm-yyyy"
    estimated_budget: Optional[int] = None   # ₹
    expected_volunteers: Optional[int] = None
    target_beneficiaries: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _ngo_name_from_chunk(text: str, source: str) -> str:
    """Extract NGO/organization name from chunk text. Fallback to source filename."""
    # Common patterns: "X Foundation is...", "X Trust is...", "X is a non-profit"
    m = re.search(r"^([A-Za-z0-9\s\-]+?)\s+(?:is a non-profit|Foundation|Trust|Society|Sanstha)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Fallback: source filename without .txt
    return source.replace(".txt", "").replace("_", " ").title()


def _build_ngo_recommendations(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build NGO recommendations with match scores from retrieved chunks (category=ngos)."""
    ngos: Dict[str, Dict[str, Any]] = {}
    for c in chunks:
        if c.get("category") != "ngos":
            continue
        src = c["source"]
        score = c.get("score", 0)
        if src not in ngos or score > ngos[src]["match_score"]:
            ngos[src] = {
                "name": _ngo_name_from_chunk(c["text"], src),
                "source": src,
                "match_score": round(score * 100, 1),  # 0-100 scale
            }
    return sorted(ngos.values(), key=lambda x: x["match_score"], reverse=True)[:5]


def _query_from_form(data: PilotPlanInput) -> str:
    """Build a retrieval query from form fields so we fetch relevant chunks."""
    parts = [
        f"pilot plan {data.type_of_activity}",
        data.location_area,
        f"budget {data.estimated_budget or 'unknown'} rupees" if data.estimated_budget else "",
        f"{data.expected_volunteers} volunteers" if data.expected_volunteers else "",
        f"target {data.target_beneficiaries} beneficiaries" if data.target_beneficiaries else "",
    ]
    return " ".join(p for p in parts if p).strip() or "social impact pilot plan"


def _build_pilot_plan_prompt(
    data: PilotPlanInput,
    chunks: List[Dict[str, Any]],
    max_chars_per_chunk: Optional[int] = 400,
    fast: bool = True,
) -> str:
    """Build prompt for generating a structured pilot plan from form + retrieved context."""
    from llm.prompt_builder import format_chunks_for_prompt

    context = format_chunks_for_prompt(chunks, max_chars_per_chunk)

    budget_str = f"₹{data.estimated_budget:,}" if data.estimated_budget else "Not specified"
    volunteers_str = str(data.expected_volunteers) if data.expected_volunteers else "Not specified"
    beneficiaries_str = str(data.target_beneficiaries) if data.target_beneficiaries else "Not specified"

    if fast:
        inst = "- Output brief bullet points only: Objective (1 line), Key Activities (3-5), Resource Plan, Timeline (4-5 milestones), Expected Outcomes. Max 150 words. Be very concise."
    else:
        inst = "- Output a structured Pilot Plan: Objective, Key Activities, Resource Plan, Timeline, Expected Outcomes. Use context only; mention NGOs/guidelines when relevant. Be concise."

    return f"""Generate a Pilot Plan for social innovation.

Form: Activity={data.type_of_activity}, Location={data.location_area}, Date={data.target_date}, Budget={budget_str}, Volunteers={volunteers_str}, Beneficiaries={beneficiaries_str}

Context:
{context}

{inst}"""


def generate_pilot_plan(
    type_of_activity: str,
    location_area: str,
    target_date: str,
    estimated_budget: Optional[int] = None,
    expected_volunteers: Optional[int] = None,
    target_beneficiaries: Optional[int] = None,
    top_k: int = 6,
    model: Optional[str] = None,
    timeout: Optional[int] = 60,
    fast: bool = True,
) -> Dict[str, Any]:
    """
    Generate a Pilot Plan from the form fields. Use this when connecting the web form.

    Args:
        type_of_activity: From dropdown (e.g. "Education", "Health", "Environment").
        location_area: e.g. "Sector 15, Rajasthan".
        target_date: e.g. "15-03-2025" (dd-mm-yyyy).
        estimated_budget: Budget in ₹ (optional).
        expected_volunteers: Number of volunteers (optional).
        target_beneficiaries: Target number of beneficiaries (optional).
        top_k: Number of chunks to retrieve (default 6 to include NGOs).
        model: Ollama model name. None = use tinyllama if fast else mistral.
        timeout: Request timeout in seconds (default 60 for fast mode).
        fast: If True, use shorter output and faster model for ~5-15s response.

    Returns:
        {
            "plan": "<generated pilot plan text>",
            "sources": [{"source": "filename", "category": "..."}, ...],
            "ngo_recommendations": [{"name": "...", "source": "...", "match_score": 85.2}, ...]
        }
    """
    from retriever import retrieve
    from llm.ollama_client import generate

    data = PilotPlanInput(
        type_of_activity=type_of_activity.strip(),
        location_area=location_area.strip(),
        target_date=target_date.strip(),
        estimated_budget=estimated_budget,
        expected_volunteers=expected_volunteers,
        target_beneficiaries=target_beneficiaries,
    )

    query = _query_from_form(data)
    chunks = retrieve(query, top_k=top_k)

    if not chunks:
        return {
            "plan": "No relevant context found. Run build_index.py and try different activity or location.",
            "sources": [],
            "ngo_recommendations": [],
        }

    # NGO recommendations (instant, from retrieval scores)
    ngo_recommendations = _build_ngo_recommendations(chunks)

    # Pilot plan (LLM call - main latency)
    prompt = _build_pilot_plan_prompt(data, chunks, max_chars_per_chunk=400, fast=fast)
    timeout_sec = timeout or 45
    if model:
        model_list = [model]
    else:
        model_list = FAST_MODELS if fast else ["mistral"]
    # Try fastest models first; fall back if not installed
    plan_text = ""
    last_error = None
    for model_name in model_list:
        kwargs: Dict[str, Any] = {"model": model_name, "timeout": timeout_sec}
        if fast:
            kwargs["num_predict"] = 250  # shorter = faster
        try:
            plan_text = generate(prompt, **kwargs)
            break
        except Exception as e:
            last_error = e
            continue
    if not plan_text:
        raise last_error or RuntimeError("No model responded")

    sources = [{"source": c["source"], "category": c["category"]} for c in chunks]

    return {
        "plan": plan_text.strip(),
        "sources": sources,
        "ngo_recommendations": ngo_recommendations,
    }


def generate_pilot_plan_from_dict(
    form_data: Dict[str, Any],
    fast: bool = True,
) -> Dict[str, Any]:
    """
    Same as generate_pilot_plan but accepts a single dict (e.g. from JSON body).
    Keys: type_of_activity, location_area, target_date, estimated_budget (optional),
    expected_volunteers (optional), target_beneficiaries (optional).
    """
    return generate_pilot_plan(
        type_of_activity=form_data.get("type_of_activity", ""),
        location_area=form_data.get("location_area", ""),
        target_date=form_data.get("target_date", ""),
        estimated_budget=form_data.get("estimated_budget"),
        expected_volunteers=form_data.get("expected_volunteers"),
        target_beneficiaries=form_data.get("target_beneficiaries"),
        fast=fast,
    )


if __name__ == "__main__":
    # Demo: same shape as form submit
    result = generate_pilot_plan(
        type_of_activity="Education",
        location_area="Sector 15, Rajasthan",
        target_date="15-06-2025",
        estimated_budget=25000,
        expected_volunteers=30,
        target_beneficiaries=200,
    )
    print("Sources:", result["sources"])
    print("\nPilot Plan:\n", result["plan"])
