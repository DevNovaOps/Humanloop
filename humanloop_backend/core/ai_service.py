"""
AI Service — Bridge between Django and the RAG engine.

Calls generate_pilot_plan from the AI engine using qwen2:0.5b.
Also provides NGO matching based on database records.
Includes smart auto-estimation and location-aware matching.
"""
import logging
import math
from django.conf import settings

logger = logging.getLogger(__name__)

AI_MODEL = getattr(settings, 'AI_MODEL', 'qwen2:0.5b')

# ═══════════════════════════════════════════
# ACTIVITY CATEGORIES — with smart defaults
# ═══════════════════════════════════════════
ACTIVITY_CATEGORIES = {
    'education': {
        'label': '📚 Education Drive',
        'members_per_10k': 8,       # 8 volunteers per ₹10k budget
        'beneficiaries_per_10k': 40, # 40 beneficiaries per ₹10k
        'min_members': 5,
        'min_beneficiaries': 20,
        'keywords': ['education', 'school', 'teaching', 'tuition', 'literacy', 'books'],
    },
    'health': {
        'label': '🏥 Healthcare Camp',
        'members_per_10k': 12,
        'beneficiaries_per_10k': 60,
        'min_members': 8,
        'min_beneficiaries': 30,
        'keywords': ['health', 'medical', 'doctor', 'clinic', 'medicine', 'hospital'],
    },
    'environment': {
        'label': '🌿 Environment / Cleanliness',
        'members_per_10k': 15,
        'beneficiaries_per_10k': 100,
        'min_members': 10,
        'min_beneficiaries': 50,
        'keywords': ['environment', 'clean', 'tree', 'plantation', 'waste', 'recycling', 'green'],
    },
    'awareness': {
        'label': '📣 Awareness Campaign',
        'members_per_10k': 6,
        'beneficiaries_per_10k': 80,
        'min_members': 4,
        'min_beneficiaries': 50,
        'keywords': ['awareness', 'campaign', 'rally', 'social', 'rights'],
    },
    'food_distribution': {
        'label': '🍽️ Food Distribution',
        'members_per_10k': 10,
        'beneficiaries_per_10k': 120,
        'min_members': 6,
        'min_beneficiaries': 40,
        'keywords': ['food', 'meal', 'hunger', 'nutrition', 'feeding'],
    },
    'digital_literacy': {
        'label': '💻 Digital Literacy',
        'members_per_10k': 5,
        'beneficiaries_per_10k': 25,
        'min_members': 3,
        'min_beneficiaries': 15,
        'keywords': ['digital', 'computer', 'internet', 'tech', 'coding', 'software'],
    },
    'housing_shelter': {
        'label': '🏠 Housing / Shelter',
        'members_per_10k': 8,
        'beneficiaries_per_10k': 15,
        'min_members': 6,
        'min_beneficiaries': 10,
        'keywords': ['housing', 'shelter', 'home', 'construction', 'repair'],
    },
    'skill_development': {
        'label': '👩‍🎓 Skill Development',
        'members_per_10k': 5,
        'beneficiaries_per_10k': 20,
        'min_members': 3,
        'min_beneficiaries': 15,
        'keywords': ['skill', 'training', 'workshop', 'vocational', 'employment'],
    },
    'child_welfare': {
        'label': '🧒 Child Welfare',
        'members_per_10k': 10,
        'beneficiaries_per_10k': 35,
        'min_members': 6,
        'min_beneficiaries': 20,
        'keywords': ['child', 'children', 'orphan', 'kid', 'youth', 'juvenile'],
    },
    'elder_care': {
        'label': '👴 Elder Care',
        'members_per_10k': 8,
        'beneficiaries_per_10k': 25,
        'min_members': 5,
        'min_beneficiaries': 15,
        'keywords': ['elder', 'senior', 'old age', 'retirement', 'geriatric'],
    },
    'cultural': {
        'label': '🎭 Cultural Activity',
        'members_per_10k': 10,
        'beneficiaries_per_10k': 80,
        'min_members': 8,
        'min_beneficiaries': 30,
        'keywords': ['cultural', 'art', 'music', 'dance', 'festival', 'heritage'],
    },
    'sports': {
        'label': '🏃 Sports & Recreation',
        'members_per_10k': 8,
        'beneficiaries_per_10k': 50,
        'min_members': 6,
        'min_beneficiaries': 25,
        'keywords': ['sports', 'recreation', 'fitness', 'game', 'tournament', 'athletic'],
    },
    'water_sanitation': {
        'label': '💧 Water & Sanitation',
        'members_per_10k': 10,
        'beneficiaries_per_10k': 80,
        'min_members': 6,
        'min_beneficiaries': 40,
        'keywords': ['water', 'sanitation', 'toilet', 'hygiene', 'sewage', 'drinking'],
    },
    'animal_welfare': {
        'label': '🐾 Animal Welfare',
        'members_per_10k': 6,
        'beneficiaries_per_10k': 30,
        'min_members': 4,
        'min_beneficiaries': 15,
        'keywords': ['animal', 'pet', 'stray', 'rescue', 'veterinary', 'wildlife'],
    },
}


def get_activity_label(key):
    """Get the display label for an activity type."""
    cat = ACTIVITY_CATEGORIES.get(key)
    return cat['label'] if cat else key.replace('_', ' ').title()


# ═══════════════════════════════════════════
# SMART AUTO-ESTIMATES
# ═══════════════════════════════════════════
def auto_estimate(form_data: dict) -> dict:
    """
    Auto-estimate team members and beneficiaries based on budget and activity type.
    Returns dict with estimated_members, estimated_beneficiaries, and reasoning.
    """
    activity = form_data.get('activity_type', 'awareness')
    budget = float(form_data.get('budget', 0) or 0)
    user_members = form_data.get('members')
    user_beneficiaries = form_data.get('beneficiaries')

    cat = ACTIVITY_CATEGORIES.get(activity, ACTIVITY_CATEGORIES['awareness'])
    budget_units = max(budget / 10000, 1)  # units of ₹10k

    # Smart member estimate
    est_members = max(cat['min_members'], round(cat['members_per_10k'] * budget_units))
    est_members = min(est_members, 200)  # cap

    # Smart beneficiary estimate
    est_beneficiaries = max(cat['min_beneficiaries'], round(cat['beneficiaries_per_10k'] * budget_units))
    est_beneficiaries = min(est_beneficiaries, 5000)  # cap

    # Budget breakdown estimation
    total_budget = budget if budget > 0 else 10000
    breakdown = estimate_budget_breakdown(activity, total_budget)

    reasoning = []
    if not user_members or int(user_members) == 0:
        reasoning.append(f"Estimated {est_members} team members based on ₹{budget:,.0f} budget for {cat['label']}")
    if not user_beneficiaries or int(user_beneficiaries) == 0:
        reasoning.append(f"Estimated {est_beneficiaries} target beneficiaries based on activity scope")

    return {
        'estimated_members': est_members,
        'estimated_beneficiaries': est_beneficiaries,
        'budget_breakdown': breakdown,
        'reasoning': reasoning,
    }


def estimate_budget_breakdown(activity: str, budget: float) -> dict:
    """Generate a smart budget breakdown based on activity type."""
    breakdowns = {
        'education': {'Materials & Books': 35, 'Venue & Infrastructure': 20, 'Instructor Fees': 20, 'Transport': 15, 'Miscellaneous': 10},
        'health': {'Medical Supplies': 30, 'Doctor/Staff Fees': 25, 'Venue': 15, 'Transport': 15, 'Food & Refreshments': 10, 'Miscellaneous': 5},
        'environment': {'Supplies & Equipment': 30, 'Transport': 20, 'Food & Refreshments': 20, 'Marketing': 15, 'Miscellaneous': 15},
        'awareness': {'Marketing & Outreach': 35, 'Venue & Equipment': 25, 'Transport': 15, 'Printing': 15, 'Miscellaneous': 10},
        'food_distribution': {'Food & Groceries': 50, 'Packaging': 15, 'Transport': 15, 'Volunteers Support': 10, 'Miscellaneous': 10},
        'digital_literacy': {'Equipment & Software': 40, 'Instructor Fees': 25, 'Venue': 15, 'Internet & Infra': 10, 'Miscellaneous': 10},
        'housing_shelter': {'Materials': 45, 'Labor': 25, 'Transport': 15, 'Permits': 10, 'Miscellaneous': 5},
        'skill_development': {'Training Materials': 30, 'Instructor Fees': 30, 'Venue': 20, 'Certificates': 10, 'Miscellaneous': 10},
        'child_welfare': {'Supplies & Toys': 30, 'Food & Nutrition': 25, 'Venue': 20, 'Activities': 15, 'Miscellaneous': 10},
        'elder_care': {'Medical Supplies': 30, 'Food & Nutrition': 25, 'Transport': 15, 'Activities': 20, 'Miscellaneous': 10},
        'cultural': {'Venue & Stage': 30, 'Props & Materials': 25, 'Marketing': 15, 'Food & Refreshments': 15, 'Transport': 10, 'Miscellaneous': 5},
        'sports': {'Equipment': 35, 'Venue': 25, 'Prizes & Awards': 15, 'Food & Water': 15, 'Miscellaneous': 10},
        'water_sanitation': {'Infrastructure': 40, 'Materials': 25, 'Labor': 15, 'Testing & Quality': 10, 'Miscellaneous': 10},
        'animal_welfare': {'Medical & Vet': 35, 'Food & Shelter': 30, 'Transport': 15, 'Supplies': 15, 'Miscellaneous': 5},
    }
    default = {'Materials & Supplies': 40, 'Venue & Logistics': 20, 'Marketing': 15, 'Food': 15, 'Miscellaneous': 10}
    breakdown = breakdowns.get(activity, default)
    return {k: round(budget * v / 100) for k, v in breakdown.items()}


# ═══════════════════════════════════════════
# SMART LOCATION MATCHING
# ═══════════════════════════════════════════
# Area → City mapping for Gujarat (extensible)
AREA_TO_CITY = {
    # Vadodara areas
    'gorwa': 'vadodara', 'sayajigunj': 'vadodara', 'alkapuri': 'vadodara',
    'fatehgunj': 'vadodara', 'manjalpur': 'vadodara', 'karelibaug': 'vadodara',
    'vaghodia': 'vadodara', 'akota': 'vadodara', 'gotri': 'vadodara',
    'nizampura': 'vadodara', 'harni': 'vadodara', 'sama': 'vadodara',
    'subhanpura': 'vadodara', 'tarsali': 'vadodara', 'makarpura': 'vadodara',
    'dabhoi': 'vadodara', 'sindhrot': 'vadodara', 'bill': 'vadodara',
    'vasna': 'vadodara', 'padra': 'vadodara', 'sevasi': 'vadodara',

    # Ahmedabad areas
    'navrangpura': 'ahmedabad', 'maninagar': 'ahmedabad', 'satellite': 'ahmedabad',
    'bopal': 'ahmedabad', 'vastrapur': 'ahmedabad', 'paldi': 'ahmedabad',
    'naranpura': 'ahmedabad', 'gota': 'ahmedabad', 'chandkheda': 'ahmedabad',
    'thaltej': 'ahmedabad', 'sg highway': 'ahmedabad', 'prahlad nagar': 'ahmedabad',
    'ellis bridge': 'ahmedabad', 'sabarmati': 'ahmedabad', 'bapunagar': 'ahmedabad',
    'naroda': 'ahmedabad', 'odhav': 'ahmedabad', 'isanpur': 'ahmedabad',

    # Surat areas
    'adajan': 'surat', 'vesu': 'surat', 'varachha': 'surat',
    'katargam': 'surat', 'piplod': 'surat', 'udhna': 'surat',
    'althan': 'surat', 'pal': 'surat', 'dindoli': 'surat',
    'rander': 'surat', 'athwa': 'surat', 'dumas': 'surat',

    # Rajkot areas
    'kalawad road': 'rajkot', 'university road': 'rajkot', 'mavdi': 'rajkot',
    'kothariya': 'rajkot', 'sadhu vaswani': 'rajkot', 'gondal': 'rajkot',

    # Mumbai areas
    'andheri': 'mumbai', 'bandra': 'mumbai', 'borivali': 'mumbai',
    'dadar': 'mumbai', 'juhu': 'mumbai', 'malad': 'mumbai',
    'goregaon': 'mumbai', 'powai': 'mumbai', 'worli': 'mumbai',
    'colaba': 'mumbai', 'lower parel': 'mumbai', 'kurla': 'mumbai',
    'chembur': 'mumbai', 'mulund': 'mumbai', 'thane': 'mumbai',
    'navi mumbai': 'mumbai', 'vashi': 'mumbai', 'kharghar': 'mumbai',

    # Delhi areas
    'dwarka': 'delhi', 'rohini': 'delhi', 'saket': 'delhi',
    'karol bagh': 'delhi', 'lajpat nagar': 'delhi', 'connaught place': 'delhi',
    'hauz khas': 'delhi', 'janakpuri': 'delhi', 'pitampura': 'delhi',
    'noida': 'delhi', 'gurgaon': 'delhi', 'gurugram': 'delhi',
    'faridabad': 'delhi', 'ghaziabad': 'delhi',

    # Bangalore areas
    'koramangala': 'bangalore', 'indiranagar': 'bangalore', 'whitefield': 'bangalore',
    'hsr layout': 'bangalore', 'jayanagar': 'bangalore', 'electronic city': 'bangalore',
    'marathahalli': 'bangalore', 'bannerghatta': 'bangalore', 'yelahanka': 'bangalore',

    # Pune areas
    'kothrud': 'pune', 'hinjewadi': 'pune', 'wakad': 'pune',
    'baner': 'pune', 'viman nagar': 'pune', 'hadapsar': 'pune',
    'shivaji nagar': 'pune', 'kharadi': 'pune', 'aundh': 'pune',
}


def resolve_location(location: str) -> dict:
    """
    Resolve a location to its parent city and extract area info.
    Returns dict with: input, area, city, all_keywords
    """
    loc_lower = location.lower().strip()
    parts = [p.strip() for p in loc_lower.replace(',', ' ').split() if len(p.strip()) > 1]

    detected_city = None
    detected_area = None

    # Check each word/phrase against area mapping
    for area, city in AREA_TO_CITY.items():
        if area in loc_lower:
            detected_city = city
            detected_area = area
            break

    # If no area match, check if the location IS a city
    all_cities = set(AREA_TO_CITY.values())
    for part in parts:
        if part in all_cities:
            detected_city = part
            break

    # Build keyword list for fuzzy matching
    keywords = list(set(parts))
    if detected_city and detected_city not in keywords:
        keywords.append(detected_city)

    return {
        'input': location,
        'area': detected_area,
        'city': detected_city,
        'keywords': keywords,
    }


def match_ngos(form_data: dict) -> list:
    """
    Match top 3 NGOs from the database based on pilot form data.
    
    Enhanced scoring with smart location matching:
    - Activity type match (30 pts)
    - Location: exact area match (30 pts), same city (20 pts), same state (10 pts)
    - Budget range compatibility (10 pts)
    - Success rate (15 pts)
    - Team experience (20 pts)
    
    Returns list of dicts: [{id, name, organization, score, reasons, past_pilots}]
    """
    from core.models import User, Pilot

    activity = form_data.get('activity_type', '').lower()
    location = form_data.get('location', '').lower()
    budget = float(form_data.get('budget', 0) or 0)

    # Resolve location to city
    loc_info = resolve_location(location)
    resolved_city = loc_info['city']
    loc_keywords = loc_info['keywords']

    ngos = User.objects.filter(role='ngo', is_active=True)
    scored = []

    for ngo in ngos:
        score = 0
        reasons = []

        # Get all pilots previously assigned to this NGO
        past_pilots = Pilot.objects.filter(assigned_ngo=ngo)
        total_pilots = past_pilots.count()
        completed_pilots = past_pilots.filter(status='completed').count()

        # Factor 1: Activity type match (30 pts)
        if activity:
            matching_activity = past_pilots.filter(
                activity_type__icontains=activity
            ).count()
            if matching_activity > 0:
                score += 30
                reasons.append(f'{matching_activity} similar {get_activity_label(activity)} pilot(s)')
            else:
                # Check keywords for fuzzy activity match
                cat = ACTIVITY_CATEGORIES.get(activity, {})
                for kw in cat.get('keywords', []):
                    if past_pilots.filter(activity_type__icontains=kw).exists():
                        score += 15
                        reasons.append(f'Experience with related activities')
                        break

        # Factor 2: Smart Location Match (up to 30 pts)
        if location:
            ngo_name_lower = (ngo.name or '').lower()
            ngo_org_lower = (ngo.organization or '').lower()
            ngo_locations = set()

            # Collect all locations from NGO's past pilots
            for pilot in past_pilots:
                if pilot.location:
                    ngo_locations.add(pilot.location.lower())

            # Check for exact area match (30 pts)
            exact_match = False
            for kw in loc_keywords:
                for nl in ngo_locations:
                    if kw in nl:
                        score += 30
                        reasons.append(f'Active in {location.title()} area')
                        exact_match = True
                        break
                if exact_match:
                    break

            # Check for same-city match via area→city resolution (20 pts)
            if not exact_match and resolved_city:
                for nl in ngo_locations:
                    ngo_loc_info = resolve_location(nl)
                    if ngo_loc_info['city'] == resolved_city:
                        score += 20
                        reasons.append(f'Active in {resolved_city.title()} city')
                        exact_match = True
                        break

                # Also check NGO name/org for city match
                if not exact_match:
                    if resolved_city in ngo_name_lower or resolved_city in ngo_org_lower:
                        score += 20
                        reasons.append(f'Based in {resolved_city.title()}')
                        exact_match = True

            # Fallback: keyword overlap (10 pts)
            if not exact_match:
                for kw in loc_keywords:
                    if kw in ngo_name_lower or kw in ngo_org_lower:
                        score += 10
                        reasons.append(f'Based in matching region')
                        break

        # Factor 3: Experience / track record (up to 20 pts)
        if total_pilots > 0:
            score += min(total_pilots * 5, 20)
            reasons.append(f'{total_pilots} pilot(s) on record')

        # Factor 4: Completion rate (up to 15 pts)
        if total_pilots > 0:
            rate = completed_pilots / total_pilots
            score += int(rate * 15)
            if rate > 0.5:
                reasons.append(f'{int(rate*100)}% completion rate')

        # Factor 5: Budget familiarity (10 pts)
        if budget > 0 and total_pilots > 0:
            from django.db.models import Avg
            avg_budget = past_pilots.aggregate(avg=Avg('budget'))['avg'] or 0
            if avg_budget > 0:
                ratio = min(budget, float(avg_budget)) / max(budget, float(avg_budget))
                if ratio > 0.5:
                    score += 10
                    reasons.append(f'Familiar budget range')

        # Always give min score for being an active NGO
        if score == 0:
            score = 5
            reasons.append('Active NGO on platform')

        scored.append({
            'id': ngo.id,
            'name': ngo.name,
            'organization': ngo.organization or ngo.name,
            'email': ngo.email,
            'score': score,
            'reasons': reasons,
            'past_pilots': total_pilots,
            'completed_pilots': completed_pilots,
        })

    # Sort by score descending
    scored.sort(key=lambda x: x['score'], reverse=True)

    # Deduplicate by name — keep highest score per name
    seen_names = set()
    unique_scored = []
    for entry in scored:
        name_key = entry['name'].strip().lower()
        if name_key not in seen_names:
            seen_names.add(name_key)
            unique_scored.append(entry)

    return unique_scored[:3]


def generate_plan(form_data: dict) -> dict:
    """
    Generate a pilot plan using the RAG engine.
    Includes auto-estimation for members and beneficiaries.

    Args:
        form_data: dict with keys activity_type, location, date, budget, members, beneficiaries

    Returns:
        dict with keys: plan, ngo_recommendations, sources, estimates
    """
    # Auto-estimate team & beneficiaries
    estimates = auto_estimate(form_data)

    # Fill in missing data with estimates
    enriched_data = dict(form_data)
    if not form_data.get('members') or int(form_data.get('members', 0)) == 0:
        enriched_data['members'] = estimates['estimated_members']
    if not form_data.get('beneficiaries') or int(form_data.get('beneficiaries', 0)) == 0:
        enriched_data['beneficiaries'] = estimates['estimated_beneficiaries']

    # Get NGO recommendations from database
    ngo_recs = match_ngos(enriched_data)

    try:
        from pilot_plan_model import generate_pilot_plan

        result = generate_pilot_plan(
            type_of_activity=enriched_data.get('activity_type', ''),
            location_area=enriched_data.get('location', ''),
            target_date=str(enriched_data.get('date', '')),
            estimated_budget=int(enriched_data['budget']) if enriched_data.get('budget') else None,
            expected_volunteers=int(enriched_data['members']) if enriched_data.get('members') else None,
            target_beneficiaries=int(enriched_data['beneficiaries']) if enriched_data.get('beneficiaries') else None,
            model=AI_MODEL,
            fast=True,
        )

        return {
            'plan': result.get('plan', ''),
            'ngo_recommendations': ngo_recs,
            'sources': result.get('sources', []),
            'estimates': estimates,
        }

    except ImportError as e:
        logger.warning(f"AI engine not available: {e}. Using fallback plan.")
        plan = generate_fallback_plan(enriched_data)
        return {
            'plan': plan,
            'ngo_recommendations': ngo_recs,
            'sources': [],
            'estimates': estimates,
        }
    except ConnectionError as e:
        logger.error(f"Ollama connection failed: {e}")
        plan = generate_fallback_plan(enriched_data)
        return {
            'plan': plan,
            'ngo_recommendations': ngo_recs,
            'sources': [],
            'estimates': estimates,
            'error': 'AI engine offline — using template plan',
        }
    except Exception as e:
        logger.error(f"AI plan generation failed: {e}")
        plan = generate_fallback_plan(enriched_data)
        return {
            'plan': plan,
            'ngo_recommendations': ngo_recs,
            'sources': [],
            'estimates': estimates,
            'error': str(e),
        }


def generate_fallback_plan(form_data: dict) -> str:
    """Generate a structured plan as clean HTML. Supports variations for regeneration."""
    activity_key = form_data.get('activity_type', 'awareness')
    activity = get_activity_label(activity_key)
    activity_clean = activity.split(' ', 1)[-1] if ' ' in activity else activity
    location = form_data.get('location', 'TBD')
    date = form_data.get('date', 'TBD')
    budget = form_data.get('budget', 0)
    members = form_data.get('members', 0)
    beneficiaries = form_data.get('beneficiaries', 0)
    variation = int(form_data.get('regenerate', 0))

    breakdown = estimate_budget_breakdown(activity_key, float(budget) if budget else 10000)
    breakdown_html = ''.join([f'<li><strong>{k}</strong>: ₹{v:,}</li>' for k, v in breakdown.items()])

    task_lists = {
        'education': ['Arrange classroom/venue', 'Recruit instructors', 'Prepare study materials', 'Register students', 'Conduct sessions', 'Collect feedback'],
        'health': ['Arrange medical venue', 'Recruit doctors and nurses', 'Source medical supplies', 'Register patients', 'Conduct checkups', 'Distribute health kits', 'Follow-up cases'],
        'environment': ['Survey target area', 'Procure supplies/saplings', 'Brief volunteers', 'Conduct drive', 'Document impact', 'Install signage'],
        'food_distribution': ['Identify beneficiaries', 'Source food packages', 'Arrange transport', 'Distribute food', 'Document distribution', 'Follow-up'],
        'digital_literacy': ['Set up equipment', 'Install software', 'Recruit trainers', 'Create curriculum', 'Conduct training', 'Assess progress'],
        'skill_development': ['Identify skill gaps', 'Hire trainers', 'Arrange venue', 'Conduct workshops', 'Give certificates', 'Connect with opportunities'],
        'child_welfare': ['Identify children', 'Arrange safe space', 'Plan activities', 'Provide nutrition', 'Conduct sessions', 'Document progress'],
    }
    tasks = task_lists.get(activity_key, ['Confirm venue', 'Recruit team', 'Purchase materials', 'Notify beneficiaries', 'Execute activity', 'Collect feedback', 'Compile report'])
    tasks_html = ''.join([f'<li>{t}</li>' for t in tasks])

    templates = [
        # Template 0: Standard 4-Phase
        f"""<h3>{activity} Plan — {location}</h3>
<h4>Overview</h4>
<p>A {activity_clean.lower()} pilot targeting <strong>{beneficiaries} beneficiaries</strong> in <strong>{location}</strong>, planned for <strong>{date}</strong>. Team size: <strong>{members} volunteers</strong>.</p>
<h4>Phase 1: Preparation (Weeks 1–2)</h4>
<ul><li>Confirm venue and logistics in {location}</li><li>Recruit {members} team members</li><li>Procure materials within ₹{budget:,} budget</li><li>Coordinate with community leaders</li></ul>
<h4>Phase 2: Outreach (Week 3)</h4>
<ul><li>Notify beneficiaries through local channels</li><li>Distribute awareness materials</li><li>Register participants (target: {beneficiaries})</li></ul>
<h4>Phase 3: Execution (Week 4)</h4>
<ul><li>Conduct the {activity_clean.lower()} activity</li><li>Document outcomes with photos and attendance</li><li>Collect real-time feedback</li></ul>
<h4>Phase 4: Follow-up (Week 5)</h4>
<ul><li>Compile impact report</li><li>Submit financial reconciliation</li><li>Plan for sustainability</li></ul>
<h4>Task Checklist</h4><ul>{tasks_html}</ul>
<h4>Budget Breakdown (₹{budget:,})</h4><ul>{breakdown_html}</ul>
<h4>Key Metrics</h4>
<ul><li><strong>Beneficiaries:</strong> {beneficiaries}</li><li><strong>Team:</strong> {members}</li><li><strong>Budget:</strong> ₹{budget:,}</li><li><strong>Location:</strong> {location}</li><li><strong>Date:</strong> {date}</li></ul>""",

        # Template 1: Agile Sprint
        f"""<h3>{activity} — Sprint Plan for {location}</h3>
<h4>Mission</h4>
<p>Deliver a high-impact {activity_clean.lower()} initiative reaching <strong>{beneficiaries} beneficiaries</strong> with <strong>{members} volunteers</strong> by <strong>{date}</strong>.</p>
<h4>Sprint 1: Foundation (Days 1–7)</h4>
<ul><li>Assemble core team of {max(3, members // 3)} coordinators</li><li>Secure venue and permits in {location}</li><li>Begin essential procurement</li><li>Set up team communication</li></ul>
<h4>Sprint 2: Build-up (Days 8–14)</h4>
<ul><li>Complete volunteer recruitment ({members} total)</li><li>Conduct orientation session</li><li>Finalize logistics</li><li>Launch community outreach in {location}</li></ul>
<h4>Sprint 3: Execution (Days 15–21)</h4>
<ul><li>Execute the {activity_clean.lower()} program</li><li>Engage {beneficiaries} beneficiaries</li><li>Track attendance and gather feedback</li><li>Address issues in real-time</li></ul>
<h4>Sprint 4: Impact (Days 22–30)</h4>
<ul><li>Compile photos, videos, and testimonials</li><li>Prepare impact report</li><li>Reconcile budget (₹{budget:,})</li><li>Celebrate and plan next phase</li></ul>
<h4>Action Items</h4><ul>{tasks_html}</ul>
<h4>Resource Allocation (₹{budget:,})</h4><ul>{breakdown_html}</ul>""",

        # Template 2: Community-Led
        f"""<h3>Community-Led {activity_clean} — {location}</h3>
<h4>Vision</h4>
<p>Empower the community of <strong>{location}</strong> through a participatory {activity_clean.lower()} program serving <strong>{beneficiaries} beneficiaries</strong> with lasting impact.</p>
<h4>Stage 1: Community Engagement</h4>
<ul><li>Meet local leaders and stakeholders</li><li>Conduct community needs assessment</li><li>Form a local advisory committee</li><li>Recruit {members} community volunteers</li></ul>
<h4>Stage 2: Planning and Resources</h4>
<ul><li>Co-design program with community input</li><li>Allocate budget of ₹{budget:,}</li><li>Source materials locally</li><li>Train volunteer team</li></ul>
<h4>Stage 3: Implementation</h4>
<ul><li>Launch the {activity_clean.lower()} program</li><li>Ensure inclusive participation</li><li>Provide hands-on support</li><li>Document stories and progress</li></ul>
<h4>Stage 4: Sustainability</h4>
<ul><li>Hand over to community leaders</li><li>Create maintenance plan</li><li>Publish impact report</li><li>Schedule follow-up in 3 months</li></ul>
<h4>Key Tasks</h4><ul>{tasks_html}</ul>
<h4>Investment Plan (₹{budget:,})</h4><ul>{breakdown_html}</ul>""",

        # Template 3: Lean Pilot
        f"""<h3>{activity_clean} — Lean Execution Plan</h3>
<h4>Objective</h4>
<p>Rapidly deploy a {activity_clean.lower()} pilot at <strong>{location}</strong>, targeting <strong>{beneficiaries} beneficiaries</strong> with <strong>{members} team members</strong>, optimising every rupee of ₹{budget:,}.</p>
<h4>Week 1: Validate and Prepare</h4>
<ul><li>Validate demand with 10+ potential beneficiaries</li><li>Identify the best sub-location within {location}</li><li>Recruit a lean core team of {min(members, 10)} volunteers</li><li>Purchase only essential materials</li></ul>
<h4>Week 2: Minimum Viable Pilot</h4>
<ul><li>Run small-scale test with {max(beneficiaries // 5, 10)} beneficiaries</li><li>Gather immediate feedback and iterate</li><li>Refine approach based on learnings</li><li>Scale volunteer team to {members}</li></ul>
<h4>Week 3: Full Launch</h4>
<ul><li>Execute full {activity_clean.lower()} program</li><li>Reach all {beneficiaries} target beneficiaries</li><li>Deploy entire team</li><li>Real-time monitoring</li></ul>
<h4>Week 4: Measure and Report</h4>
<ul><li>Measure impact against targets</li><li>Final budget reconciliation (₹{budget:,})</li><li>Create visual impact report</li><li>Share findings with stakeholders</li></ul>
<h4>Deliverables</h4><ul>{tasks_html}</ul>
<h4>Budget (₹{budget:,})</h4><ul>{breakdown_html}</ul>""",
    ]

    idx = variation % len(templates)
    return templates[idx]


def generate_insights(user, lang='en') -> list:
    """
    Generate AI-powered insights for a user based on their role and real DB data.
    Uses the RAG engine when available, falls back to data-driven analysis.
    Supports multilingual output via lang parameter.
    
    Returns list of dicts: [{title, message, type, icon}]
    """
    from core.models import User, Pilot, Feedback, Expense, BeneficiaryEnrollment, Certificate
    from django.db.models import Sum, Avg, Count, Q

    role = user.role
    insights = []

    # ─── Multilingual insight text (compact) ───
    _T = {
        'en': {
            'active_progress': ('Active Pilot Progress', 'You have {active} active pilot(s) with average progress of {progress}%. Keep pushing!'),
            'budget_low': ('Budget Utilization Low', 'Only {pct}% of your total budget (₹{budget}) utilized. Consider allocating resources.'),
            'budget_ok': ('Budget On Track', '{pct}% of your budget (₹{budget}) spent. Total: ₹{spent}.'),
            'satisfaction': ('Beneficiary Satisfaction', 'Average feedback: {avg}/5 stars from {count} responses.'),
            'completion': ('Completion Rate', '{done}/{total} pilots completed ({pct}%). Impacted {bene} beneficiaries.'),
            'get_started': ('Get Started', 'Create your first pilot to start making an impact!'),
            'field_ops': ('Field Operations', '{active} active pilot(s) at {progress}% progress. {bene} beneficiaries enrolled.'),
            'financial': ('Financial Summary', 'Budget: ₹{budget} | Spent: ₹{spent} ({pct}% utilized).'),
            'track_record': ('Track Record', '{done} completed pilot(s). Strong execution record.'),
            'stale_alert': ('Stale Pilots Alert', '{count} pilot(s) below 20% progress need attention.'),
            'ngo_start': ('Ready to Go!', 'No pilots assigned yet. Insights appear once assigned.'),
            'admin_overview': ('Platform Overview', '{users} users, {pilots} pilots, {ngos} NGOs registered.'),
            'admin_finance': ('Financial Health', 'Total budget: ₹{budget} | Spent: ₹{spent} ({pct}%).'),
            'admin_pending': ('Action Required', '{count} pending assignment request(s) awaiting review.'),
            'admin_satisfaction': ('Satisfaction Score', 'Platform avg feedback: {avg}/5 from {count} responses.'),
            'admin_clean': ('All Clear!', 'No pending requests. Platform running smoothly. 🎉'),
            'program_status': ('Program Status', 'Enrolled in {total} program(s): {active} active, {done} completed.'),
            'certs_earned': ('Certificates Earned', 'Congratulations! You earned {count} certificate(s).'),
            'your_feedback': ('Your Feedback', "Submitted {count} feedback(s), avg rating {avg}/5. Thank you!"),
            'share_exp': ('Share Your Experience', 'Help improve programs by sharing feedback!'),
            'ai_rec': ('AI Recommendation', None),
        },
        'hi': {
            'active_progress': ('सक्रिय पायलट प्रगति', '{active} सक्रिय पायलट, औसत प्रगति {progress}%। आगे बढ़ें!'),
            'budget_low': ('बजट उपयोग कम', 'कुल बजट (₹{budget}) का केवल {pct}% उपयोग हुआ।'),
            'budget_ok': ('बजट सही', 'बजट (₹{budget}) का {pct}% खर्च। कुल: ₹{spent}।'),
            'satisfaction': ('लाभार्थी संतुष्टि', 'औसत रेटिंग: {avg}/5 - {count} प्रतिक्रियाएं।'),
            'completion': ('पूर्णता दर', '{total} में से {done} पायलट पूर्ण ({pct}%)। {bene} लाभार्थी।'),
            'get_started': ('शुरू करें', 'पहला पायलट बनाकर प्रभाव शुरू करें!'),
            'field_ops': ('फील्ड ऑपरेशन', '{active} सक्रिय पायलट {progress}% पर। {bene} लाभार्थी।'),
            'financial': ('वित्तीय सारांश', 'बजट: ₹{budget} | खर्च: ₹{spent} ({pct}%)।'),
            'track_record': ('ट्रैक रिकॉर्ड', '{done} पायलट पूर्ण। मजबूत निष्पादन।'),
            'stale_alert': ('चेतावनी', '{count} पायलट 20% से कम प्रगति पर।'),
            'ngo_start': ('तैयार!', 'पायलट आवंटित होने पर अंतर्दृष्टि दिखेगी।'),
            'admin_overview': ('प्लेटफॉर्म', '{users} उपयोगकर्ता, {pilots} पायलट, {ngos} NGO।'),
            'admin_finance': ('वित्तीय स्वास्थ्य', 'बजट: ₹{budget} | खर्च: ₹{spent} ({pct}%)।'),
            'admin_pending': ('कार्रवाई', '{count} लंबित आवंटन अनुरोध।'),
            'admin_satisfaction': ('संतुष्टि', 'औसत प्रतिक्रिया: {avg}/5 - {count} प्रतिक्रियाएं।'),
            'admin_clean': ('सब ठीक!', 'कोई लंबित अनुरोध नहीं। 🎉'),
            'program_status': ('कार्यक्रम', '{total} कार्यक्रम: {active} सक्रिय, {done} पूर्ण।'),
            'certs_earned': ('प्रमाणपत्र', 'बधाई! {count} प्रमाणपत्र अर्जित।'),
            'your_feedback': ('प्रतिक्रिया', '{count} प्रतिक्रिया दी, औसत {avg}/5। धन्यवाद!'),
            'share_exp': ('अनुभव साझा करें', 'प्रतिक्रिया देकर कार्यक्रम सुधारें!'),
            'ai_rec': ('AI सिफारिश', None),
        },
        'gu': {
            'active_progress': ('સક્રિય પાયલોટ પ્રગતિ', '{active} સક્રિય પાયલોટ, સરેરાશ પ્રગતિ {progress}%।'),
            'budget_low': ('બજેટ ઉપયોગ ઓછો', 'બજેટ (₹{budget})નો માત્ર {pct}% ઉપયોગ।'),
            'budget_ok': ('બજેટ યોગ્ય', 'બજેટ (₹{budget})નો {pct}% ખર્ચ। કુલ: ₹{spent}।'),
            'satisfaction': ('લાભાર્થી સંતોષ', 'સરેરાશ રેટિંગ: {avg}/5 - {count} પ્રતિસાદો।'),
            'completion': ('પૂર્ણતા દર', '{total}માંથી {done} પૂર્ણ ({pct}%)। {bene} લાભાર્થીઓ।'),
            'get_started': ('શરૂ કરો', 'પહેલો પાયલોટ બનાવો!'),
            'field_ops': ('ફિલ્ડ', '{active} સક્રિય પાયલોટ {progress}% પર। {bene} લાભાર્થીઓ।'),
            'financial': ('આર્થિક', 'બજેટ: ₹{budget} | ખર્ચ: ₹{spent} ({pct}%)।'),
            'track_record': ('ટ્રેક રેકોર્ડ', '{done} પૂર્ણ પાયલોટ। મજબૂત અમલ।'),
            'stale_alert': ('ચેતવણી', '{count} પાયલોટ 20% કરતાં ઓછી પ્રગતિ।'),
            'ngo_start': ('તૈયાર!', 'પાયલોટ ફાળવ્યા પછી આંતરદૃષ્ટિ દેખાશે।'),
            'admin_overview': ('પ્લેટફોર્મ', '{users} વપરાશકર્તા, {pilots} પાયલોટ, {ngos} NGO।'),
            'admin_finance': ('આર્થિક', 'બજેટ: ₹{budget} | ખર્ચ: ₹{spent} ({pct}%)।'),
            'admin_pending': ('કાર્યવાહી', '{count} બાકી ફાળવણી વિનંતી।'),
            'admin_satisfaction': ('સંતોષ', 'સરેરાશ પ્રતિસાદ: {avg}/5 - {count} પ્રતિસાદો।'),
            'admin_clean': ('બધું બરાબર!', 'કોઈ બાકી વિનંતી નથી। 🎉'),
            'program_status': ('કાર્યક્રમ', '{total} કાર્યક્રમ: {active} સક્રિય, {done} પૂર્ણ।'),
            'certs_earned': ('પ્રમાણપત્ર', 'અભિનંદન! {count} પ્રમાણપત્ર મેળવ્યા।'),
            'your_feedback': ('પ્રતિસાદ', '{count} પ્રતિસાદ, સરેરાશ {avg}/5। આભાર!'),
            'share_exp': ('અનુભવ શેર કરો', 'પ્રતિસાદ આપીને કાર્યક્રમ સુધારો!'),
            'ai_rec': ('AI ભલામણ', None),
        },
    }

    def t(key, **kwargs):
        """Get translated insight text, falling back to English."""
        table = _T.get(lang, _T['en'])
        entry = table.get(key, _T['en'].get(key))
        if not entry:
            return ('', '')
        title, msg_tpl = entry
        if msg_tpl and kwargs:
            try:
                msg = msg_tpl.format(**kwargs)
            except (KeyError, ValueError):
                msg = msg_tpl
        else:
            msg = msg_tpl or ''
        return title, msg

    try:
        from rag_pipeline import RAGPipeline
        rag_available = True
    except ImportError:
        rag_available = False

    if role == 'innovator':
        my_pilots = Pilot.objects.filter(created_by=user)
        total = my_pilots.count()
        active = my_pilots.filter(status='active').count()
        completed = my_pilots.filter(status='completed').count()
        total_budget = float(my_pilots.aggregate(t=Sum('budget'))['t'] or 0)
        total_spent = float(Expense.objects.filter(pilot__in=my_pilots).aggregate(t=Sum('amount'))['t'] or 0)
        avg_progress = my_pilots.filter(status='active').aggregate(a=Avg('progress'))['a'] or 0
        total_beneficiaries = my_pilots.aggregate(t=Sum('target_beneficiaries'))['t'] or 0
        feedbacks = Feedback.objects.filter(pilot__in=my_pilots)
        avg_rating = feedbacks.aggregate(a=Avg('rating'))['a'] or 0

        if total > 0:
            if active > 0:
                title, msg = t('active_progress', active=active, progress=round(avg_progress))
                insights.append({'title': title, 'message': msg, 'type': 'info', 'icon': 'fa-chart-line'})
            if total_budget > 0:
                utilization = round((total_spent / total_budget) * 100) if total_budget > 0 else 0
                if utilization < 50:
                    title, msg = t('budget_low', pct=utilization, budget=f'{total_budget:,.0f}')
                    insights.append({'title': title, 'message': msg, 'type': 'warning', 'icon': 'fa-wallet'})
                else:
                    title, msg = t('budget_ok', pct=utilization, budget=f'{total_budget:,.0f}', spent=f'{total_spent:,.0f}')
                    insights.append({'title': title, 'message': msg, 'type': 'success', 'icon': 'fa-wallet'})
            if avg_rating > 0:
                title, msg = t('satisfaction', avg=f'{avg_rating:.1f}', count=feedbacks.count())
                insights.append({'title': title, 'message': msg, 'type': 'success' if avg_rating >= 4 else 'info', 'icon': 'fa-star'})
            if completed > 0 and total > 0:
                title, msg = t('completion', done=completed, total=total, pct=round(completed/total*100), bene=total_beneficiaries)
                insights.append({'title': title, 'message': msg, 'type': 'success', 'icon': 'fa-check-circle'})
        else:
            title, msg = t('get_started')
            insights.append({'title': title, 'message': msg, 'type': 'info', 'icon': 'fa-rocket'})

    elif role == 'ngo':
        assigned = Pilot.objects.filter(assigned_ngo=user)
        active = assigned.filter(status='active').count()
        completed = assigned.filter(status='completed').count()
        total = assigned.count()
        avg_progress = assigned.filter(status='active').aggregate(a=Avg('progress'))['a'] or 0
        beneficiaries_reached = BeneficiaryEnrollment.objects.filter(pilot__assigned_ngo=user).count()
        total_budget = float(assigned.aggregate(t=Sum('budget'))['t'] or 0)
        total_spent = float(Expense.objects.filter(pilot__in=assigned).aggregate(t=Sum('amount'))['t'] or 0)

        if active > 0:
            title, msg = t('field_ops', active=active, progress=round(avg_progress), bene=beneficiaries_reached)
            insights.append({'title': title, 'message': msg, 'type': 'info', 'icon': 'fa-clipboard-list'})
        if total_budget > 0:
            utilization = round((total_spent / total_budget) * 100) if total_budget > 0 else 0
            title, msg = t('financial', budget=f'{total_budget:,.0f}', spent=f'{total_spent:,.0f}', pct=utilization)
            insights.append({'title': title, 'message': msg, 'type': 'warning' if (total_budget - total_spent) < total_budget * 0.1 else 'info', 'icon': 'fa-indian-rupee-sign'})
        if completed > 0:
            title, msg = t('track_record', done=completed)
            insights.append({'title': title, 'message': msg, 'type': 'success', 'icon': 'fa-trophy'})
        stale = assigned.filter(status='active', progress__lte=10)
        if stale.count() > 0:
            title, msg = t('stale_alert', count=stale.count())
            insights.append({'title': title, 'message': msg, 'type': 'warning', 'icon': 'fa-triangle-exclamation'})
        if total == 0:
            title, msg = t('ngo_start')
            insights.append({'title': title, 'message': msg, 'type': 'info', 'icon': 'fa-hand-holding-heart'})

    elif role == 'admin':
        total_users = User.objects.count()
        total_pilots = Pilot.objects.count()
        ngo_count = User.objects.filter(role='ngo').count()
        total_budget = float(Pilot.objects.aggregate(t=Sum('budget'))['t'] or 0)
        total_spent = float(Expense.objects.aggregate(t=Sum('amount'))['t'] or 0)
        all_feedbacks = Feedback.objects.all()
        avg_rating = all_feedbacks.aggregate(a=Avg('rating'))['a'] or 0
        from .models import PilotAssignment
        pending_requests = PilotAssignment.objects.filter(status='pending_admin').count()

        title, msg = t('admin_overview', users=total_users, pilots=total_pilots, ngos=ngo_count)
        insights.append({'title': title, 'message': msg, 'type': 'info', 'icon': 'fa-chart-pie'})
        if total_budget > 0:
            utilization = round((total_spent / total_budget) * 100) if total_budget > 0 else 0
            title, msg = t('admin_finance', budget=f'{total_budget:,.0f}', spent=f'{total_spent:,.0f}', pct=utilization)
            insights.append({'title': title, 'message': msg, 'type': 'info', 'icon': 'fa-wallet'})
        if pending_requests > 0:
            title, msg = t('admin_pending', count=pending_requests)
            insights.append({'title': title, 'message': msg, 'type': 'warning', 'icon': 'fa-clipboard-check'})
        if avg_rating > 0:
            title, msg = t('admin_satisfaction', avg=f'{avg_rating:.1f}', count=all_feedbacks.count())
            insights.append({'title': title, 'message': msg, 'type': 'success' if avg_rating >= 4 else 'warning', 'icon': 'fa-star'})

    elif role == 'beneficiary':
        enrollments = BeneficiaryEnrollment.objects.filter(user=user).select_related('pilot')
        program_count = enrollments.count()
        feedbacks = Feedback.objects.filter(user=user)
        feedback_count = feedbacks.count()
        certificates = Certificate.objects.filter(beneficiary=user)
        cert_count = certificates.count()

        if program_count > 0:
            active_programs = enrollments.filter(pilot__status='active').count()
            completed_programs = enrollments.filter(pilot__status='completed').count()
            title, msg = t('program_status', total=program_count, active=active_programs, done=completed_programs)
            insights.append({'title': title, 'message': msg, 'type': 'info', 'icon': 'fa-book-open'})
        if cert_count > 0:
            title, msg = t('certs_earned', count=cert_count)
            insights.append({'title': title, 'message': msg, 'type': 'success', 'icon': 'fa-certificate'})
        if feedback_count > 0:
            avg = feedbacks.aggregate(a=Avg('rating'))['a'] or 0
            title, msg = t('your_feedback', count=feedback_count, avg=f'{avg:.1f}')
            insights.append({'title': title, 'message': msg, 'type': 'success', 'icon': 'fa-pen-to-square'})
        else:
            title, msg = t('share_exp')
            insights.append({'title': title, 'message': msg, 'type': 'info', 'icon': 'fa-comment-dots'})

    # If RAG engine available, try to enrich with AI-generated insight
    if rag_available and len(insights) > 0:
        try:
            context_summary = '; '.join([f"{i['title']}: {i['message']}" for i in insights[:3]])
            rag = RAGPipeline()
            query = f"Based on these metrics for a {role}: {context_summary}. Provide one actionable recommendation."
            result = rag.query(query, top_k=3)
            if result and result.get('answer'):
                title, _ = t('ai_rec')
                insights.append({'title': title, 'message': result['answer'][:300], 'type': 'ai', 'icon': 'fa-wand-magic-sparkles'})
        except Exception as e:
            logger.debug(f"RAG insight enrichment skipped: {e}")

    return insights[:5]  # Return max 5 insights
