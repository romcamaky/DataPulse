"""
DataPulse Onboarding Questionnaire — Interactive CLI.

Walks a new user through 5 sections (~5 minutes) to build a skill profile.
Collects all data in memory, then writes to Supabase in one batch at the end.
This is the core of Module 1: Profile Engine.

Usage:
    python -m datapulse.onboarding
    python src/datapulse/onboarding.py
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from datapulse.db import get_client
from datapulse.skills_mapper import SkillsMapper


# Temporary user ID for development — replaced by Supabase Auth in Module 5
# Fixed UUID so we can re-run onboarding without creating duplicates
DEV_USER_ID = "83531240-a099-48a3-aee7-320a5b34f328"


def ask_text(prompt: str, required: bool = True) -> str:
    """Prompt the user for a free-text input and return their response.

    This helper centralizes basic validation and normalization of text inputs so
    each section does not need to reimplement the same loops. It also ensures
    that required fields cannot be left empty, which keeps the collected data
    usable when we later write it to Supabase.

    Args:
        prompt: The message shown to the user before reading input.
        required: Whether an empty response is allowed.

    Returns:
        The user's response as a stripped string (may be empty if not required).
    """
    while True:
        value = input(f"{prompt.strip()} ").strip()
        if value or not required:
            return value
        print("This field is required. Please enter a value.")


def ask_number(
    prompt: str,
    min_val: Optional[int] = None,
    max_val: Optional[int] = None,
    required: bool = True,
) -> Optional[int]:
    """Prompt the user for an integer within an optional range.

    The function loops until the user provides a valid integer that satisfies
    the configured bounds. For optional numeric questions, the user can press
    Enter to skip, in which case ``None`` is returned.

    Args:
        prompt: The message shown to the user.
        min_val: Optional minimum allowed value (inclusive).
        max_val: Optional maximum allowed value (inclusive).
        required: Whether a value is required.

    Returns:
        The parsed integer value, or ``None`` if not required and skipped.
    """
    while True:
        raw = input(f"{prompt.strip()} ")
        if not raw.strip():
            if required:
                print("This field is required. Please enter a number.")
                continue
            return None

        try:
            value = int(raw.strip())
        except ValueError:
            print("Please enter a valid integer (e.g., 0, 1, 2).")
            continue

        if min_val is not None and value < min_val:
            print(f"Value must be at least {min_val}.")
            continue
        if max_val is not None and value > max_val:
            print(f"Value must be at most {max_val}.")
            continue

        return value


def ask_select(prompt: str, options: List[str], required: bool = True) -> Optional[str]:
    """Prompt the user to select a single option from a numbered list.

    Centralizing this logic keeps each section lightweight and ensures a
    consistent UX across the onboarding flow. Users select by typing the
    1-based index of their choice.

    Args:
        prompt: The question to display before the options list.
        options: A list of option labels.
        required: Whether a selection is mandatory.

    Returns:
        The selected option string, or ``None`` if not required and skipped.
    """
    if not options:
        raise ValueError("ask_select requires at least one option.")

    while True:
        print(prompt.strip())
        for idx, option in enumerate(options, start=1):
            print(f"  {idx}. {option}")

        raw = input("Select an option by number: ").strip()

        if not raw:
            if required:
                print("This field is required. Please enter a number.")
                continue
            return None

        try:
            choice = int(raw)
        except ValueError:
            print("Please enter a valid number corresponding to an option.")
            continue

        if choice < 1 or choice > len(options):
            print("Selection out of range. Please choose a valid option number.")
            continue

        return options[choice - 1]


def ask_multi_select(
    prompt: str,
    options: List[str],
    max_choices: Optional[int] = None,
    required: bool = True,
) -> List[str]:
    """Prompt the user to select multiple options from a numbered list.

    The function expects a comma-separated list of 1-based indices (e.g.,
    ``1,3,5``). It validates the indices, enforces an optional maximum number
    of selections, and supports a conventional "other" option as the final
    element in the list which triggers a free-text follow-up.

    Args:
        prompt: The question to display before the options list.
        options: A list of option labels; if the last is "Other" (case-insensitive),
            selecting it will prompt for a custom free-text value.
        max_choices: Optional maximum number of choices allowed.
        required: Whether at least one choice is required.

    Returns:
        A list of selected option strings (including any custom "other" text).
    """
    if not options:
        raise ValueError("ask_multi_select requires at least one option.")

    has_other = options and options[-1].lower() == "other"

    while True:
        print(prompt.strip())
        for idx, option in enumerate(options, start=1):
            print(f"  {idx}. {option}")

        raw = input("Select one or more options by number (e.g., 1,3,5): ").strip()

        if not raw:
            if required:
                print("At least one selection is required. Please enter a value.")
                continue
            return []

        parts = [part.strip() for part in raw.split(",") if part.strip()]
        indices: List[int] = []
        invalid_input = False

        for part in parts:
            try:
                index = int(part)
            except ValueError:
                print(f"'{part}' is not a valid number.")
                invalid_input = True
                break
            if index < 1 or index > len(options):
                print(f"Choice {index} is out of range.")
                invalid_input = True
                break
            indices.append(index)

        if invalid_input:
            continue

        # Enforce maximum number of choices if configured.
        if max_choices is not None and len(indices) > max_choices:
            print(f"You can select at most {max_choices} options.")
            continue

        # Remove duplicates while preserving order.
        seen: set[int] = set()
        unique_indices: List[int] = []
        for idx in indices:
            if idx not in seen:
                seen.add(idx)
                unique_indices.append(idx)

        selections: List[str] = []
        custom_other_values: List[str] = []

        for idx in unique_indices:
            label = options[idx - 1]
            if has_other and idx == len(options):
                # Ask for a custom free-text value for "other".
                other_value = ask_text("Please describe the 'Other' option:", required=True)
                custom_other_values.append(other_value)
            else:
                selections.append(label)

        selections.extend(custom_other_values)
        return selections


def print_section_header(number: int, title: str) -> None:
    """Print a formatted section header to visually separate steps.

    Using a consistent style makes the CLI feel more deliberate and helps users
    understand where they are in the overall flow.

    Args:
        number: Numeric section identifier (1–9).
        title: Human-readable section title.
    """
    line = "=" * 50
    print(f"\n{line}\n  Section {number}: {title}\n{line}\n")


def print_summary(label: str, data: Dict[str, Any]) -> None:
    """Print a brief summary of collected data for a section.

    This helper provides fast visual feedback so users can sanity-check what
    was captured before moving on. Only non-empty values are displayed.

    Args:
        label: A human-readable label for the section (e.g., \"Identity\").
        data: The dictionary of collected values for that section.
    """
    print(f"\nSummary — {label}:")
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        print(f"  \u2713 {key}: {value}")


def _collect_languages() -> List[Dict[str, str]]:
    """Collect one or more language entries for Section 1.

    This function is kept separate from the generic helpers because language
    collection has a very specific structure (name + level) and a minimum of
    one entry, but the pattern can be reused later if needed.

    Returns:
        A list of dictionaries with keys ``\"language\"`` and ``\"level\"``.
    """
    levels = ["native", "fluent", "working proficiency", "basic"]
    languages: List[Dict[str, str]] = []

    while True:
        language_name = ask_text("Language name?", required=True)
        level = ask_select("Level:", levels, required=True)
        languages.append({"language": language_name, "level": level})  # type: ignore[arg-type]

        if len(languages) == 0:
            # Defensive; this branch will not be reached because we always
            # append at least one entry before asking to continue.
            continue

        more = input("Add another language? (y/n): ").strip().lower()
        if more not in ("y", "yes"):
            break

    return languages


def section_1_identity() -> Dict[str, Any]:
    """Collect minimal identity information for skill gap analysis (Module 3).

    Returns:
        A dictionary containing identity fields for the ``user_profiles`` table.
    """
    print_section_header(1, "Who are you")

    display_name = ask_text("What's your name?", required=True)
    current_role = ask_text("What's your current job title?", required=True)

    industry_options = [
        "Tech",
        "Finance",
        "Healthcare",
        "Retail",
        "Manufacturing",
        "Consulting",
        "Education",
        "Government",
        "Other",
    ]
    industry_choice = ask_select(
        "Which industry do you primarily work in?",
        industry_options,
        required=True,
    )
    if industry_choice == "Other":
        industry = ask_text("Which industry best describes your work?", required=True)
    else:
        industry = industry_choice

    country = ask_text("Where are you based? (country)", required=True)

    result: Dict[str, Any] = {
        "display_name": display_name,
        "current_role": current_role,
        "industry": industry,
        "country": country,
    }

    print_summary("Identity", result)
    return result


def _map_technologies_to_skill_ids(
    technologies_raw: str,
    skills_mapper: SkillsMapper,
) -> Tuple[List[str], List[str]]:
    """Map a comma-separated technology string to skill IDs using SkillsMapper.

    This helper normalizes the free-text list, looks up each entry against the
    canonical skills table, and separates matched from unmatched technologies.
    It is shared across onboarding sections for consistency.

    Args:
        technologies_raw: Comma-separated user input listing tools/skills.
        skills_mapper: Initialized ``SkillsMapper`` instance.

    Returns:
        A tuple of ``(skill_ids, unmatched_names)`` where ``skill_ids`` is a
        list of canonical skill UUID strings and ``unmatched_names`` lists the
        original tokens that could not be mapped.
    """
    tokens = [part.strip() for part in technologies_raw.split(",") if part.strip()]
    skill_ids: List[str] = []
    unmatched: List[str] = []

    for token in tokens:
        mapped_id = skills_mapper.map_skill(token)
        if mapped_id:
            skill_ids.append(mapped_id)
        else:
            unmatched.append(token)

    for tech in unmatched:
        print(f"  \u26a0 '{tech}' not found in skills database — skipping")

    return skill_ids, unmatched


def section_2_work_experience(skills_mapper: SkillsMapper) -> Dict[str, Any]:
    """Collect work experience for skill gap analysis (Module 3).

    Returns:
        A dictionary with:
        - ``years_total_experience``
        - ``work_experiences`` (list of roles, each mapped to technology skill IDs)
    """
    print_section_header(2, "Work experience")

    years_total_experience = ask_number(
        "How many years of total professional experience?",
        min_val=0,
        max_val=50,
        required=True,
    )

    work_experiences: List[Dict[str, Any]] = []
    print("Let's capture your work history.")

    while True:
        # Collect at least one role entry.
        role_title = ask_text("Job title", required=True)
        company_name = ask_text("Company", required=True)

        start_year = ask_number("Start year", required=True)

        # For end year we accept either a numeric year or "current".
        while True:
            end_year_raw = ask_text(
                "End year (or type 'current' if this is your current role)",
                required=True,
            )
            if end_year_raw.lower() == "current":
                end_year: Optional[int] = None
                break
            try:
                end_year = int(end_year_raw)
            except ValueError:
                print("Please enter a valid year (e.g., 2023) or 'current'.")
                continue
            break

        description = ask_text(
            "What did you do? (2-3 sentences)",
            required=True,
        )

        visibility_choice = ask_select(
            "Visibility",
            ["Public", "Private", "Confidential"],
            required=True,
        )
        visibility = visibility_choice.lower()

        technologies_raw = ask_text(
            "Technologies/tools used (comma-separated)",
            required=False,
        )
        if technologies_raw:
            tech_skill_ids, _ = _map_technologies_to_skill_ids(
                technologies_raw,
                skills_mapper,
            )
        else:
            tech_skill_ids = []

        work_experiences.append(
            {
                "role_title": role_title,
                "company_name": company_name,
                "start_year": start_year,
                "end_year": end_year,
                "description": description,
                "visibility": visibility,
                "technology_skill_ids": tech_skill_ids,
            },
        )

        more_roles = input("Add another role? (y/n): ").strip().lower()
        if more_roles not in ("y", "yes"):
            break

    result: Dict[str, Any] = {
        "years_total_experience": years_total_experience,
        "work_experiences": work_experiences,
    }
    print_summary("Work experience", result)
    return result


SKILL_ASSESSMENT_GROUPS: List[Tuple[str, List[Tuple[str, str]]]] = [
    (
        "SQL & Databases",
        [
            ("SQL (SELECT, JOIN, GROUP BY)", "sql"),
            ("Advanced SQL (window functions, CTEs)", "window_functions"),
            ("Data modeling (star schema, normalization)", "data_modeling"),
            ("PostgreSQL specifically", "postgresql"),
            ("MS SQL Server", "ms_sql_server"),
            ("Database admin (indexes, performance)", "query_optimization"),
        ],
    ),
    (
        "Python & Programming",
        [
            ("Python fundamentals", "python"),
            ("Pandas / data manipulation", "pandas"),
            ("APIs & HTTP requests", "api_integration"),
            ("Testing (pytest)", "python_testing"),
            ("Error handling & logging", "python_scripting"),
            ("Git / version control", "git"),
        ],
    ),
    (
        "Data Engineering & Analytics",
        [
            ("dbt (data build tool)", "dbt"),
            ("ETL / ELT pipeline design", "etl_design"),
            ("CI/CD (GitHub Actions or similar)", "ci_cd"),
            ("Cloud platforms (AWS/GCP/Azure)", "aws"),
            ("Orchestration (Airflow, Prefect)", "airflow"),
            ("Docker / containers", "docker"),
        ],
    ),
    (
        "BI & Visualization",
        [
            ("Power BI / DAX", "power_bi"),
            ("Tableau", "tableau"),
            ("Data storytelling / presenting", "stakeholder_communication"),
        ],
    ),
    (
        "AI & Machine Learning",
        [
            ("Prompt engineering", "prompt_engineering"),
            ("LLM API integration", "llm_integration"),
            ("RAG / vector search", "rag"),
        ],
    ),
]


def section_3_skills(skills_mapper: SkillsMapper) -> Dict[str, Any]:
    """Collect self-assessed technical skill levels across key categories.

    The ratings are intentionally lightweight but structured so they can be
    combined later with harder evidence from projects, courses, and work
    history. Only skills with level > 0 (non-zero experience) are stored.

    Args:
        skills_mapper: Shared instance used to map canonical names to IDs.

    Returns:
        A dictionary with a ``\"skill_ratings\"`` list of rating dictionaries
        (``{\"skill_id\", \"level\", \"evidence_type\"}``).
    """
    print_section_header(3, "Technical skills self-assessment")
    print(
        "Rate your comfort level with each skill. Be honest — this isn't a test.\n"
        "The system combines self-assessment with other evidence (projects, courses, work history).\n\n"
        "Scale: 0=Never used | 1=Aware | 2=Beginner | 3=Intermediate | 4=Advanced | 5=Expert\n"
        "Press Enter to skip (defaults to 0).\n",
    )

    rated_skill_ids: set[str] = set()
    skill_ratings: List[Dict[str, Any]] = []

    for group_name, skills in SKILL_ASSESSMENT_GROUPS:
        print(f"\n--- {group_name} ---")
        for display, canonical_name in skills:
            # Avoid duplicate questions if the same canonical name appears twice.
            if canonical_name in rated_skill_ids:
                continue

            skill_id = skills_mapper.map_skill(canonical_name)
            if not skill_id:
                print(
                    f"  \u26a0 Skill '{canonical_name}' not found in skills database — skipping",
                )
                continue

            while True:
                raw = input(f"  {display}: ").strip()
                if not raw:
                    level = 0
                    break
                try:
                    level = int(raw)
                except ValueError:
                    print("Please enter a number between 0 and 5, or press Enter to skip.")
                    continue
                if level < 0 or level > 5:
                    print("Please enter a number between 0 and 5.")
                    continue
                break

            if level <= 0:
                # We do not store "never used" entries.
                continue

            rated_skill_ids.add(canonical_name)
            skill_ratings.append(
                {
                    "skill_id": skill_id,
                    "level": level,
                    "evidence_type": "self_assessment",
                },
            )

    count_total = len(skill_ratings)
    count_strong = sum(1 for rating in skill_ratings if rating.get("level", 0) >= 3)
    print(f"\n{count_total} skills rated, {count_strong} with level 3+")

    result: Dict[str, Any] = {"skill_ratings": skill_ratings}
    print_summary("Technical skills self-assessment", result)
    return result


def section_4_career_goals() -> Dict[str, Any]:
    """Collect the user's target roles for Module 3 skill gap analysis."""
    print_section_header(4, "Career goals")

    target_roles_options = [
        "Data Engineer",
        "Analytics Engineer",
        "AI/Data Designer",
        "Data Scientist",
        "ML Engineer",
        "Data Analyst",
        "Data Architect",
        "AI Product Manager",
        "Other",
    ]
    target_roles = ask_multi_select(
        "Which roles are you aiming for? (select one or more)",
        target_roles_options,
        required=True,
    )

    result: Dict[str, Any] = {"target_roles": target_roles}
    print_summary("Career goals", result)
    return result


def section_5_career_story() -> Dict[str, Any]:
    """Collect the user's career narrative for profile context."""
    print_section_header(5, "Your story")
    print(
        "Tell me your career story in a few sentences.\n"
        "What path brought you here? What are you most proud of? What do you want to change?\n\n"
        "Type below. Press Enter twice (empty line) to finish.\n",
    )

    while True:
        lines: List[str] = []
        while True:
            line = input()
            if line == "":
                if lines:
                    break
                continue
            lines.append(line)

        career_narrative = "\n".join(lines).strip()
        if career_narrative:
            break

        print("This field is required. Please share at least a short story.\n")

    result: Dict[str, Any] = {"career_narrative": career_narrative}
    print_summary("Your story", result)
    return result


def main() -> None:
    """Run the DataPulse onboarding questionnaire end-to-end.

    The function coordinates the high-level flow: prints the welcome banner,
    initializes the shared ``SkillsMapper``, runs each section in sequence, and
    aggregates the resulting dictionaries into a single payload. In Step 3b we
    will extend this to persist the collected data to Supabase in a single
    batch.
    """
    print("\n" + "=" * 50)
    print("  Welcome to DataPulse Onboarding")
    print("  ~5 minutes to build your skill profile")
    print("=" * 50)

    # Initialize skills mapper (fetches canonical skills from DB)
    mapper = SkillsMapper()

    # Collect data from all sections into a single dictionary. Using ``update``
    # keeps the merge logic simple and makes it clear that keys must be unique
    # across sections.
    data: Dict[str, Any] = {}
    data.update(section_1_identity())
    data.update(section_2_work_experience(mapper))
    data.update(section_3_skills(mapper))
    data.update(section_4_career_goals())
    data.update(section_5_career_story())

    # Initialize Supabase client only after collecting all data so that the
    # interactive flow remains responsive even if the network is slow.
    client = get_client()

    # Pre-write check: if a profile already exists for this development user,
    # offer to overwrite it and clear related rows in reverse FK order.
    existing = client.table("user_profiles").select("id").eq(
        "user_id",
        DEV_USER_ID,
    ).execute()
    existing_data = getattr(existing, "data", getattr(existing, "get", lambda *_: [])("data"))  # type: ignore[call-arg]
    if existing_data:
        overwrite = input(
            "\n⚠ A profile already exists for this user. Overwrite? (y/n): ",
        ).strip().lower()
        if overwrite != "y":
            print("Onboarding cancelled. Existing profile unchanged.")
            return

        # Delete existing data in reverse FK order so that junction tables
        # referencing core tables are cleared first.
        try:
            # work_experience_skills -> work_experience
            work_resp = client.table("work_experience").select("id").eq(
                "user_id",
                DEV_USER_ID,
            ).execute()
            work_ids = [
                row["id"]
                for row in getattr(
                    work_resp,
                    "data",
                    getattr(work_resp, "get", lambda *_: [])("data"),  # type: ignore[call-arg]
                )
            ]
            if work_ids:
                client.table("work_experience_skills").delete().in_(
                    "work_experience_id",
                    work_ids,
                ).execute()
        except Exception:
            # If there are no work experience skills, proceed with cleanup.
            pass

        client.table("work_experience").delete().eq(
            "user_id",
            DEV_USER_ID,
        ).execute()
        client.table("user_skills").delete().eq("user_id", DEV_USER_ID).execute()
        client.table("user_target_roles").delete().eq("user_id", DEV_USER_ID).execute()
        client.table("user_profiles").delete().eq("user_id", DEV_USER_ID).execute()
        print("  Existing profile cleared.\n")

    # Persist collected data to Supabase, respecting foreign key dependencies
    # and ensuring that partial failures surface clearly.
    try:
        # 1) user_profiles — minimal core profile for Module 3.
        print("  Saving profile...")
        profile_data: Dict[str, Any] = {
            "user_id": DEV_USER_ID,
            "display_name": data.get("display_name"),
            # DB column is `role_title` (NOT `current_role`)
            "role_title": data.get("current_role"),
            "industry": data.get("industry"),
            "country": data.get("country"),
            "years_total_experience": data.get("years_total_experience"),
            "career_narrative": data.get("career_narrative"),
        }
        profile_data = {k: v for k, v in profile_data.items() if v is not None}
        client.table("user_profiles").insert(profile_data).execute()

        # 2) user_skills — self-assessed technical skills.
        print("  Saving skill ratings...")
        skill_rows: List[Dict[str, Any]] = []
        for rating in data.get("skill_ratings", []):
            skill_rows.append(
                {
                    "user_id": DEV_USER_ID,
                    "skill_id": rating["skill_id"],
                    "level": rating["level"],
                    "evidence_type": rating["evidence_type"],
                    "confidence": "medium",
                    "visibility": "public",
                },
            )
        if skill_rows:
            client.table("user_skills").insert(skill_rows).execute()

        # 3) work_experience + work_experience_skills — jobs first, then junction.
        print("  Saving work experience...")
        for exp in data.get("work_experiences", []):
            exp_row: Dict[str, Any] = {
                "user_id": DEV_USER_ID,
                "role_title": exp["role_title"],
                "company_name": exp["company_name"],
                "start_date": f"{exp['start_year']}-01-01",
                "end_date": f"{exp['end_year']}-12-31" if exp.get("end_year") else None,
                "description": exp["description"],
                "visibility": exp["visibility"],
            }
            result = client.table("work_experience").insert(exp_row).execute()
            work_data = getattr(
                result,
                "data",
                getattr(result, "get", lambda *_: [])("data"),  # type: ignore[call-arg]
            )
            work_exp_id = work_data[0]["id"]

            tech_skills = exp.get("technology_skill_ids", [])
            if tech_skills:
                junction_rows = [
                    {"work_experience_id": work_exp_id, "skill_id": sid}
                    for sid in tech_skills
                ]
                client.table("work_experience_skills").insert(junction_rows).execute()

        # 4) user_target_roles — one row per selected role, preserving priority.
        print("  Saving career goals...")
        for i, role in enumerate(data.get("target_roles", [])):
            role_row = {
                "user_id": DEV_USER_ID,
                "role_name": role,
                "priority": i + 1,
            }
            client.table("user_target_roles").insert(role_row).execute()

    except Exception as e:  # noqa: BLE001
        print(f"\n❌ Error saving to Supabase: {e}")
        print("Check your .env file and database connection.")
        print("Your answers were collected but not saved. Run onboarding again to retry.")
        return

    print("\n" + "=" * 50)
    print("  ✅ Profile saved to DataPulse!")
    print(f"  User ID: {DEV_USER_ID}")
    print(f"  Skills rated: {len(data.get('skill_ratings', []))}")
    print(f"  Work experiences: {len(data.get('work_experiences', []))}")
    print(f"  Target roles: {len(data.get('target_roles', []))}")
    print("=" * 50)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully so the user is not left with a stack trace.
        print("\nOnboarding cancelled.")
