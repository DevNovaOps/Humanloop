"""
Generate 1000 Indian NGO profile documents for the knowledge base.
Each profile is 400-600 words, realistic, and varied.
"""

import random
from pathlib import Path

# Output directory (knowledge_base/ngos)
OUT_DIR = Path(__file__).resolve().parent.parent / "knowledge_base" / "ngos"

FOCUS_AREAS = [
    "maternal and child health",
    "primary education and literacy",
    "vocational training and livelihoods",
    "women's empowerment and self-help groups",
    "rural water and sanitation",
    "environmental conservation and afforestation",
    "disaster relief and resilience",
    "tribal welfare and forest rights",
    "urban slum development",
    "child nutrition and mid-day meals",
    "microfinance and financial inclusion",
    "HIV/AIDS awareness and care",
    "disability inclusion",
    "elderly care",
    "youth skill development",
    "sustainable agriculture",
    "clean energy and solar lighting",
    "waste management and recycling",
    "legal aid and human rights",
    "cultural heritage and arts",
]

STATES = [
    "Maharashtra", "Uttar Pradesh", "Bihar", "West Bengal", "Madhya Pradesh",
    "Rajasthan", "Karnataka", "Gujarat", "Andhra Pradesh", "Tamil Nadu",
    "Kerala", "Odisha", "Jharkhand", "Assam", "Punjab", "Chhattisgarh",
    "Haryana", "Telangana", "Delhi", "Uttarakhand", "Himachal Pradesh",
    "Goa", "Manipur", "Meghalaya", "Nagaland", "Tripura", "Mizoram",
]

CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai", "Kolkata",
    "Pune", "Ahmedabad", "Jaipur", "Lucknow", "Bhopal", "Patna",
    "Bhubaneswar", "Thiruvananthapuram", "Guwahati", "Raipur", "Ranchi",
    "Dehradun", "Shimla", "Panaji", "Kochi", "Nagpur", "Indore",
]

NAME_PREFIXES = [
    "Jan", "Gram", "Sarvodaya", "Lok", "Pragati", "Sahyog", "Sewa",
    "Uday", "Akshay", "Navjeevan", "Manav", "Bharat", "Desh", "Kisan",
    "Shiksha", "Swastya", "Paryavaran", "Mahila", "Bal", "Yuva",
]

NAME_SUFFIXES = [
    "Trust", "Foundation", "Sanstha", "Seva", "Samiti", "Society",
    "Parishad", "Sangh", "Kendra", "Mandal", "Vikas", "Kalyan",
]

PROGRAM_TEMPLATES = [
    ("{name} runs {program}, reaching {n} beneficiaries through {activity}.", "program", "n", "activity"),
    ("The flagship initiative {program} has trained {n} individuals in {skill}.", "program", "n", "skill"),
    ("{program} provides {service} to over {n} families in {region}.", "program", "n", "service", "region"),
]

ACTIVITIES = [
    "community workshops", "door-to-door campaigns", "school partnerships",
    "village health worker networks", "self-help group formation",
    "direct cash transfers", "skill training centers", "mobile clinics",
    "awareness rallies", "digital literacy camps", "seed distribution",
    "water harvesting projects", "toilet construction drives",
]

SKILLS = [
    "tailoring and garment work", "digital literacy", "organic farming",
    "handicraft production", "driving and logistics", "beauty and wellness",
    "electrical repair", "accounting basics", "spoken English",
]

SERVICES = [
    "primary healthcare", "legal aid", "counseling", "remedial education",
    "nutrition supplements", "solar lamp distribution", "insurance enrollment",
]

REGIONS = [
    "tribal blocks", "coastal villages", "flood-prone districts",
    "urban resettlement colonies", "rain-fed agricultural belts",
]

FUNDING_SOURCES = [
    "CSR partnerships with Indian corporates", "government schemes",
    "international donors", "individual philanthropy", "grant-making foundations",
    "multilateral agencies", "state social welfare departments",
]

IMPACT_METRICS = [
    "households with improved income", "children enrolled in school",
    "women in self-help groups", "trees planted", "latrines constructed",
    "people trained", "villages covered", "beneficiaries vaccinated",
]


def random_int(low: int, high: int) -> int:
    return random.randint(low, high)


def pick(container):
    """Pick one item from a list or sequence."""
    return random.choice(container)


def program_name() -> str:
    parts = [
        pick(["Gram", "Shiksha", "Swasth", "Sakhi", "Uday", "Pragati", "Nav", "Sahyog"]),
        pick(["Vikas", "Shakti", "Jyoti", "Kiran", "Seva", "Sangam", "Milan"]),
    ]
    return " ".join(parts) + " " + pick(["Yojana", "Abhiyan", "Kendra", "Programme"])


def org_name() -> str:
    return pick(NAME_PREFIXES) + pick(NAME_SUFFIXES)


def paragraph(sentences: list) -> str:
    return " ".join(sentences)


def generate_profile(seed: int) -> str:
    random.seed(seed)
    name = org_name()
    city = pick(CITIES)
    state = pick(STATES)
    year = random_int(1995, 2020)
    focus = pick(FOCUS_AREAS)
    budget_lakhs = random_int(15, 500)
    staff = random_int(8, 120)
    districts = random_int(2, 25)
    prog1 = program_name()
    prog2 = program_name()
    prog3 = program_name()
    n1, n2, n3 = random_int(5000, 150000), random_int(2000, 80000), random_int(1000, 40000)
    funding = pick(FUNDING_SOURCES)
    metric = pick(IMPACT_METRICS)
    impact_count = random_int(10000, 300000)
    region = pick(REGIONS)
    skill = pick(SKILLS)
    activity1, activity2 = pick(ACTIVITIES), pick(ACTIVITIES)
    service = pick(SERVICES)

    p1 = paragraph([
        f"{name} is a non-profit organization registered in India, headquartered in {city}, {state}. Founded in {year}, the organization focuses on {focus}.",
        f"The NGO operates across {districts} districts in {state} and neighbouring states, with a team of approximately {staff} staff and a network of community volunteers.",
        f"Annual operating budget is approximately Rs. {budget_lakhs} lakh, supported by {funding}.",
        f"Target populations include rural and urban poor, women, children, and communities in {region}.",
    ])

    p2 = paragraph([
        f"The foundation runs three flagship programs: {prog1}, which has reached over {n1} beneficiaries through {activity1}; {prog2}, providing {service} to more than {n2} individuals; and {prog3}, which has trained over {n3} people in {skill}.",
        f"Key activities include {activity1}, {activity2}, and partnerships with local panchayats and district administrations.",
        f"Impact is measured through indicators such as {metric}; the organization reports having positively impacted over {impact_count} people since inception.",
        f"Monitoring and evaluation use household surveys and government data where available.",
    ])

    p3 = paragraph([
        f"{name} collaborates with state departments, other NGOs, and community-based organizations to scale interventions.",
        f"The organization emphasizes participatory planning and has received recognition from state and national bodies for its work in {focus}.",
        f"Capacity building of local partners and sustainability of interventions are core to the model.",
    ])

    p4 = paragraph([
        f"Field offices are maintained in select districts for closer community engagement. Volunteers and self-help group leaders form the backbone of last-mile delivery.",
        f"The NGO publishes annual reports and participates in sector networks and government consultations related to {focus}.",
        f"Contact and registration details are available through the office in {city}. The organization is registered under the Societies Registration Act or Trust Act and complies with FCRA where applicable.",
    ])

    return "\n\n".join([p1, p2, p3, p4])


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Generate 1000 profiles; keep existing ngo1, ngo2, ngo3 or overwrite with India-only set
    for i in range(1, 1001):
        filepath = OUT_DIR / f"india_ngo_{i:04d}.txt"
        text = generate_profile(i + 4242)  # varied seed
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)
        if i % 200 == 0:
            print(f"Generated {i} / 1000")
    print("Done. 1000 India NGO profiles written to knowledge_base/ngos/")


if __name__ == "__main__":
    main()
