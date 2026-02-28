"""
Main Demo Script for HumanLoop RAG System

Takes input as form fields (Type of Activity, Location, Target Date, Budget,
Volunteers, Target Beneficiaries), runs the Pilot Plan model, and prints
the generated plan and sources.
Preloads embedder and vector store so first query is fast.
"""

from typing import Optional

from embedder import get_model
from retriever import _load_index, _load_metadata
from pilot_plan_model import generate_pilot_plan, ACTIVITY_TYPE_OPTIONS


def _preload() -> None:
    """Load embedder and FAISS index into memory once at startup."""
    get_model()
    try:
        _load_index()
        _load_metadata()
    except FileNotFoundError:
        pass  # index built later


def _prompt(msg: str, default: str = "") -> str:
    """Read a line; return default if empty."""
    val = input(msg).strip()
    return val if val else default


def _prompt_int(msg: str) -> Optional[int]:
    """Read an integer or empty; return None if empty."""
    val = input(msg).strip()
    if not val:
        return None
    try:
        return int(val)
    except ValueError:
        return None


def main() -> None:
    """Run interactive demo with form-style inputs."""
    print("=" * 60)
    print("HumanLoop RAG Demo - Generate Pilot Plan")
    print("=" * 60)
    print("Loading model and vector store…")
    _preload()
    print("Ready. Fill the form (or leave optional fields blank).\n")

    while True:
        try:
            print("--- Form ---")
            print("Type of Activity options:", ", ".join(ACTIVITY_TYPE_OPTIONS[:5]) + ", ...")
            type_of_activity = _prompt("Type of Activity: ").strip() or "Education & Literacy"
            location_area = _prompt("Location / Area (e.g. Sector 15, Rajasthan): ")
            target_date = _prompt("Target Date (dd-mm-yyyy): ")
            estimated_budget = _prompt_int("Estimated Budget (₹) (e.g. 25000): ")
            expected_volunteers = _prompt_int("Expected Volunteers (e.g. 30): ")
            target_beneficiaries = _prompt_int("Target Beneficiaries (e.g. 200): ")

            if not location_area:
                location_area = "India"
            if not target_date:
                target_date = "01-06-2025"

            print("\nProcessing...\n")

            result = generate_pilot_plan(
                type_of_activity=type_of_activity,
                location_area=location_area,
                target_date=target_date,
                estimated_budget=estimated_budget,
                expected_volunteers=expected_volunteers,
                target_beneficiaries=target_beneficiaries,
                top_k=6,
                fast=True,
            )

            # NGO recommendations (from retrieval, instant)
            ngo_recs = result.get("ngo_recommendations", [])
            if ngo_recs:
                print("NGO Recommendations (best match for your purpose):")
                for r in ngo_recs:
                    print(f"  - {r['name']} (match score: {r['match_score']}%)  [{r['source']}]")
                print()

            print("Retrieved Sources:")
            for s in result["sources"]:
                print(f"  - {s['source']} ({s['category']})")

            print("\nPilot Plan:")
            print("-" * 40)
            print(result["plan"])
            print("-" * 40)

        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        except FileNotFoundError as e:
            print(f"Error: {e}")
            print("Run 'python build_index.py' first to create the vector index.")
        except Exception as e:
            print(f"Error: {e}")

        print()
        again = input("Generate another plan? (y/n, or 'quit'): ").strip().lower()
        if again in ("n", "no", "quit", "q"):
            print("Exiting.")
            break
        print()


if __name__ == "__main__":
    main()
