"""
DataPulse Onboarding Questionnaire — Interactive CLI.

Walks a new user through 9 sections to build a complete skill profile.
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
DEV_USER_ID = "00000000-0000-0000-0000-000000000001"


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


def ask_repeating(
    prompt: str,
    fields: List[Dict[str, Any]],
    min_entries: int = 0,
) -> List[Dict[str, Any]]:
    """Prompt the user for a repeating set of field groups (e.g., roles).

    This helper is used for collections like work experiences or certifications,
    where we need a list of similarly shaped dictionaries. The function drives
    the "add another?" loop and defers individual field handling to the type
    metadata so that sections can configure their own schema.

    Args:
        prompt: A high-level label describing what is being collected.
        fields: A list of field configuration dictionaries with the keys:
            - ``name``: machine name of the field.
            - ``prompt``: user-facing prompt string.
            - ``type``: one of ``\"text\"``, ``\"select\"``, or ``\"multi_text\"``.
            - ``required``: boolean indicating if the field is mandatory.
            - ``options``: for ``\"select\"`` types, the list of options.
        min_entries: Minimum number of entries required before allowing exit.

    Returns:
        A list of dictionaries, each representing one completed entry.
    """
    entries: List[Dict[str, Any]] = []
    print(prompt.strip())

    while True:
        entry: Dict[str, Any] = {}
        for field in fields:
            field_name: str = field["name"]
            field_prompt: str = field["prompt"]
            field_type: str = field.get("type", "text")
            field_required: bool = bool(field.get("required", False))
            options: List[str] = field.get("options", [])

            if field_type == "text":
                entry[field_name] = ask_text(field_prompt, required=field_required)
            elif field_type == "select":
                entry[field_name] = ask_select(
                    field_prompt,
                    options,
                    required=field_required,
                )
            elif field_type == "multi_text":
                raw = ask_text(field_prompt, required=field_required)
                if raw:
                    entry[field_name] = [part.strip() for part in raw.split(",") if part.strip()]
                else:
                    entry[field_name] = []
            else:
                raise ValueError(f"Unsupported field type in ask_repeating: {field_type}")

        entries.append(entry)

        if len(entries) < min_entries:
            # Enforce minimum entries before allowing the user to stop.
            print(f"At least {min_entries} entries are required; please add another.")
            continue

        more = input("Add another? (y/n): ").strip().lower()
        if more not in ("y", "yes"):
            break

    return entries


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
    """Collect core identity information about the user.

    This section focuses on who the user is today: their name, current role,
    industry, location, languages, and team context. The responses seed the
    ``user_profiles`` table and provide context for interpreting later signals.

    Returns:
        A dictionary containing identity fields to be merged into the overall
        onboarding payload.
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

    print("Let's capture the languages you use.")
    languages = _collect_languages()

    team_options = [
        "Solo (I work with data alone)",
        "Small team (2-5 people)",
        "Larger team (5+)",
        "Cross-functional (embedded in non-data team)",
    ]
    team_choice = ask_select(
        "What's your usual team context?",
        team_options,
        required=True,
    )
    team_mapping = {
        "Solo (I work with data alone)": "solo",
        "Small team (2-5 people)": "small_team",
        "Larger team (5+)": "larger_team",
        "Cross-functional (embedded in non-data team)": "cross_functional",
    }
    team_context = team_mapping.get(team_choice, "solo")

    result: Dict[str, Any] = {
        "display_name": display_name,
        "current_role": current_role,
        "industry": industry,
        "country": country,
        "languages": languages,
        "team_context": team_context,
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
    It is shared between work experience and certifications for consistency.

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


def section_2_background(skills_mapper: SkillsMapper) -> Dict[str, Any]:
    """Collect education and work experience background information.

    This section captures formal education and detailed work history, including
    technology stacks. It provides much of the evidence for skill inference and
    later ties into ``work_experience`` and related junction tables.

    Args:
        skills_mapper: Shared instance used to map free-text technologies to
            canonical skill IDs.

    Returns:
        A dictionary containing background fields and a list of experiences.
    """
    print_section_header(2, "Your background")
    print(
        "Want to upload a CV later? For now, let's go step by step.\n"
        "(CV processing will be available in a future update.)\n",
    )

    # 2A: Education
    education_level_options = [
        "High school",
        "Bachelor's",
        "Master's",
        "PhD",
        "Bootcamp",
        "Self-taught",
    ]
    education_level = ask_select(
        "What's your highest level of education?",
        education_level_options,
        required=True,
    )
    field_of_study = ask_text("What did you study?", required=True)

    print(
        "Topic doesn't need to relate to data — we extract signals about "
        "analytical thinking from any topic.",
    )
    thesis_description = ask_text(
        "What was your thesis/final project about? (brief description)",
        required=False,
    )
    thesis_url = ask_text(
        "Link to your thesis (if available online)",
        required=False,
    )

    # 2B: Work experience
    years_total_experience = ask_number(
        "How many years of total professional experience?",
        min_val=0,
        max_val=50,
        required=True,
    )
    years_in_current_role = ask_number(
        "How many years in your current/most recent data role?",
        min_val=0,
        max_val=50,
        required=True,
    )

    work_experiences: List[Dict[str, Any]] = []
    print("Let's capture your work experience.")

    while True:
        job_title = ask_text("Job title:", required=True)
        company = ask_text("Company:", required=True)

        start_year = ask_number("Start year (e.g., 2019):", required=True)

        # For end year we accept either a numeric year or "current".
        while True:
            end_year_raw = ask_text(
                "End year (or type 'current' if this is your current role):",
                required=True,
            )
            if end_year_raw.lower() == "current":
                end_year: Optional[int] = None
                break
            try:
                end_year_val = int(end_year_raw)
            except ValueError:
                print("Please enter a valid year (e.g., 2023) or 'current'.")
                continue
            end_year = end_year_val
            break

        description = ask_text(
            "Describe what you did in 2-3 sentences:",
            required=True,
        )

        visibility_choice = ask_select(
            "Visibility:",
            ["Public", "Private", "Confidential"],
            required=True,
        )
        visibility = visibility_choice.lower()

        technologies_raw = ask_text(
            "Technologies/tools used (comma-separated):",
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
                "job_title": job_title,
                "company": company,
                "start_year": start_year,
                "end_year": end_year,
                "description": description,
                "visibility": visibility,
                "technology_skill_ids": tech_skill_ids,
            },
        )

        if len(work_experiences) == 0:
            # Defensive; unreachable because we always append before asking.
            continue

        more_roles = input("Add another role? (y/n): ").strip().lower()
        if more_roles not in ("y", "yes"):
            break

    result: Dict[str, Any] = {
        "education_level": education_level,
        "field_of_study": field_of_study,
        "thesis_description": thesis_description,
        "thesis_url": thesis_url,
        "years_total_experience": years_total_experience,
        "years_in_current_role": years_in_current_role,
        "work_experiences": work_experiences,
    }

    print_summary("Background", result)
    return result


def section_3_certifications(skills_mapper: SkillsMapper) -> Dict[str, Any]:
    """Collect certifications and courses completed by the user.

    This section is optional: users can skip it entirely or add as many
    certifications as they like. Each entry can include mapped skills to help
    connect learning signals to the canonical skills graph.

    Args:
        skills_mapper: Shared instance used to map free-text skill names.

    Returns:
        A dictionary with a single ``\"certifications\"`` key containing a list
        of certification dictionaries.
    """
    print_section_header(3, "Certifications & courses")

    any_certs = input("Any certifications or courses to add? (y/n): ").strip().lower()
    if any_certs not in ("y", "yes"):
        result: Dict[str, Any] = {"certifications": []}
        print_summary("Certifications & courses", result)
        return result

    certifications: List[Dict[str, Any]] = []

    while True:
        name = ask_text("Certificate/course name:", required=True)
        provider = ask_text(
            "Provider (Coursera, Udemy, dbt Labs, etc.):",
            required=False,
        )
        year_completed = ask_number(
            "Year completed (optional):",
            required=False,
        )
        skills_raw = ask_text(
            "Skills gained (comma-separated, optional):",
            required=False,
        )
        if skills_raw:
            skill_ids, _ = _map_technologies_to_skill_ids(
                skills_raw,
                skills_mapper,
            )
        else:
            skill_ids = []

        certificate_url = ask_text(
            "Link to certificate (optional):",
            required=False,
        )

        certifications.append(
            {
                "name": name,
                "provider": provider,
                "year_completed": year_completed,
                "skill_ids": skill_ids,
                "certificate_url": certificate_url,
            },
        )

        more = input("Add another? (y/n): ").strip().lower()
        if more not in ("y", "yes"):
            break

    result = {"certifications": certifications}
    print_summary("Certifications & courses", result)
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


def section_4_skills(skills_mapper: SkillsMapper) -> Dict[str, Any]:
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
    print_section_header(4, "Technical skills self-assessment")
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


def section_5_ai_usage() -> Dict[str, Any]:
    """Collect how the user currently uses AI tools in their work and life.

    This section focuses on frequency, tools, use cases, and depth of API/automation
    experience. The answers feed AI-related fields on ``user_profiles`` so later
    modules can tailor recommendations based on current adoption level.

    Returns:
        A dictionary containing AI usage fields to be merged into the payload.
    """
    print_section_header(5, "How you use AI today")

    ai_usage_frequency_options = [
        "Never",
        "Occasionally (few times a month)",
        "Regularly (few times a week)",
        "Daily",
        "It's core to my workflow",
    ]
    ai_usage_frequency = ask_select(
        "How often do you use AI tools (ChatGPT, Copilot, etc.) today?",
        ai_usage_frequency_options,
        required=True,
    )

    ai_tools_options = [
        "ChatGPT",
        "Claude",
        "GitHub Copilot",
        "Cursor",
        "Midjourney",
        "Custom AI tools",
        "LLM APIs (direct)",
        "Other",
    ]
    ai_tools = ask_multi_select(
        "Which AI tools do you currently use? (optional, comma-separated numbers)",
        ai_tools_options,
        required=False,
    )

    ai_use_cases_options = [
        "Writing",
        "Coding",
        "Analysis",
        "Research",
        "Automation",
        "Brainstorming",
        "Learning",
        "Content creation",
        "Other",
    ]
    ai_use_cases = ask_multi_select(
        "What do you mainly use AI for? (optional, comma-separated numbers)",
        ai_use_cases_options,
        required=False,
    )

    ai_api_experience_options = [
        "No",
        "I've experimented",
        "Yes, personal projects",
        "Yes, production use",
    ]
    ai_api_experience = ask_select(
        "Have you used AI APIs (OpenAI, Anthropic, etc.) directly?",
        ai_api_experience_options,
        required=True,
    )

    ai_automation_level_options = [
        "No automation",
        "Basic (email, docs)",
        "Intermediate (data pipelines, scripts)",
        "Advanced (multi-step agents, production systems)",
    ]
    ai_automation_level = ask_select(
        "How far have you gone with automation using AI and scripting?",
        ai_automation_level_options,
        required=True,
    )

    result: Dict[str, Any] = {
        "ai_usage_frequency": ai_usage_frequency,
        "ai_tools": ai_tools,
        "ai_use_cases": ai_use_cases,
        "ai_api_experience": ai_api_experience,
        "ai_automation_level": ai_automation_level,
    }

    print_summary("AI usage", result)
    return result


def section_6_learning() -> Dict[str, Any]:
    """Collect how the user prefers to learn and their available time.

    This section captures learning formats, realistic weekly time, preferred time
    slots, platform access, and past learning friction. The data powers the
    recommendation engine for future learning plans.

    Returns:
        A dictionary containing learning-related fields for the profile.
    """
    print_section_header(6, "How you learn")

    learning_preferences_options = [
        "Video courses",
        "Reading (books, docs, articles)",
        "Hands-on projects (build something)",
        "Interactive exercises (quizzes, coding challenges)",
        "Audio (podcasts, audiobooks)",
        "Structured courses with deadlines",
        "Peer learning (study groups, pair programming)",
        "Teaching others (writing, presenting)",
    ]
    learning_preferences = ask_multi_select(
        "How do you learn best? (pick up to 3)",
        learning_preferences_options,
        max_choices=3,
        required=True,
    )

    weekly_hours_available = ask_number(
        "How many hours per week can you realistically dedicate to learning?",
        min_val=1,
        max_val=20,
        required=True,
    )

    learning_time_preference_options = [
        "Early morning",
        "During commute",
        "Lunch break",
        "Evening after work",
        "Weekends",
        "Whenever I have a free moment",
    ]
    learning_time_preference = ask_multi_select(
        "When do you usually have time to learn? (optional)",
        learning_time_preference_options,
        required=False,
    )

    course_completion_rate_options = [
        "Never tried online courses",
        "Started but rarely finish",
        "Finish about half",
        "Usually complete what I start",
    ]
    course_completion_rate = ask_select(
        "How often do you finish online courses you start? (optional)",
        course_completion_rate_options,
        required=False,
    )

    platform_options = [
        "Udemy",
        "Coursera",
        "Pluralsight",
        "LinkedIn Learning",
        "O'Reilly",
        "DataCamp",
        "Codecademy",
        "Claude Pro",
        "ChatGPT Plus",
        "GitHub Copilot",
        "Cursor Pro",
        "Other",
    ]
    selected_platforms = ask_multi_select(
        "Which platforms do you have access to? (optional)",
        platform_options,
        required=False,
    )

    access_type_options = [
        "Paid (personal)",
        "Employer-provided",
        "Free tier",
    ]
    access_type_mapping = {
        "Paid (personal)": "paid",
        "Employer-provided": "employer",
        "Free tier": "free",
    }

    platform_access: List[Dict[str, str]] = []
    for platform in selected_platforms:
        access_type = ask_select(
            f"Access type for {platform}?",
            access_type_options,
            required=True,
        )
        mapped_access_type = access_type_mapping.get(access_type, "free")
        platform_access.append(
            {
                "platform": platform,
                "access_type": mapped_access_type,
            },
        )

    print(
        "Have you tried learning something and given up? What was it and why?\n"
        "(This helps us avoid recommending approaches that haven't worked for you.)",
    )
    learning_failures = ask_text("", required=False)

    result: Dict[str, Any] = {
        "learning_preferences": learning_preferences,
        "weekly_hours_available": weekly_hours_available,
        "learning_time_preference": learning_time_preference,
        "course_completion_rate": course_completion_rate,
        "platform_access": platform_access,
        "learning_failures": learning_failures,
    }

    print_summary("Learning preferences", result)
    return result


def section_7_career_goals() -> Dict[str, Any]:
    """Collect the user's target roles and career trajectory.

    This section focuses on desired roles, timeline for change, market scope,
    and prior career changes or frustrations. The answers drive ``user_target_roles``
    and help personalize roadmap sequencing.

    Returns:
        A dictionary containing career goal fields.
    """
    print_section_header(7, "Career goals")

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

    timeline_options = [
        "Exploring (no rush)",
        "6 months",
        "12 months",
        "Already applying",
    ]
    timeline = ask_select(
        "What's your rough timeline for this transition?",
        timeline_options,
        required=True,
    )

    market_scope_options = [
        "Local (my city)",
        "National",
        "EU",
        "Global",
        "Remote only",
    ]
    market_scope_selections = ask_multi_select(
        "Where are you open to opportunities?",
        market_scope_options,
        required=True,
    )
    market_scope_mapping = {
        "Local (my city)": "local",
        "National": "national",
        "EU": "eu",
        "Global": "global",
        "Remote only": "remote",
    }
    market_scope_short = [
        market_scope_mapping.get(scope, scope.lower()) for scope in market_scope_selections
    ]
    market_scope = ",".join(market_scope_short)

    career_change_history_options = [
        "No, this is my first field",
        "Yes, once",
        "Yes, multiple times",
    ]
    career_change_history = ask_select(
        "Have you changed careers before?",
        career_change_history_options,
        required=True,
    )

    print(
        "What frustrates you most in your current work? What slows you down?\n"
        "(Pain points = what you'll be most motivated to learn.)",
    )
    work_frustrations = ask_text("", required=False)

    result: Dict[str, Any] = {
        "target_roles": target_roles,
        "timeline": timeline,
        "market_scope": market_scope,
        "career_change_history": career_change_history,
        "work_frustrations": work_frustrations,
    }

    print_summary("Career goals", result)
    return result


def section_8_career_story() -> Dict[str, Any]:
    """Collect the user's free-text career narrative.

    This is the highest-signal qualitative input, used to understand context,
    motivations, and transferable skills. It is stored as ``career_narrative``
    on the profile.

    Returns:
        A dictionary containing the ``career_narrative`` key.
    """
    print_section_header(8, "Your story")
    print(
        "Tell me your career story in a few sentences.\n\n"
        "What path brought you here? What are you most proud of?\n"
        "What do you want to change? If you've changed careers —\n"
        "what transferable skills did you bring?\n\n"
        "Type your story below. Press Enter twice (empty line) to finish.",
    )

    while True:
        lines: List[str] = []
        while True:
            line = input()
            if line == "":
                if lines:
                    break
                # No lines yet, keep waiting for the first non-empty line.
                continue
            lines.append(line)

        career_narrative = "\n".join(lines).strip()
        if career_narrative:
            break

        print("This field is required. Please share at least a short story.\n")

    result: Dict[str, Any] = {"career_narrative": career_narrative}
    print_summary("Career story", result)
    return result


def section_9_portfolio(skills_mapper: SkillsMapper) -> Dict[str, Any]:
    """Collect portfolio links and highlight projects.

    This optional section captures GitHub, LinkedIn, and other portfolio URLs,
    plus a structured list of highlight projects. Projects are later stored as
    ``work_experience`` rows with ``experience_type='project'``.

    Args:
        skills_mapper: Shared ``SkillsMapper`` instance for mapping technologies.

    Returns:
        A dictionary containing portfolio links and projects list.
    """
    print_section_header(9, "Projects & portfolio")
    print("This section is optional. Press Enter to skip any question.\n")

    github_username = ask_text("GitHub username (optional):", required=False)
    linkedin_url = ask_text("LinkedIn URL (optional):", required=False)
    portfolio_url = ask_text("Personal site/portfolio URL (optional):", required=False)

    projects: List[Dict[str, Any]] = []
    any_projects = input("Any projects you want to highlight? (y/n): ").strip().lower()
    if any_projects in ("y", "yes"):
        while True:
            title = ask_text("Project title:", required=True)
            description = ask_text(
                "Describe the project in 2-3 sentences:",
                required=True,
            )

            technologies_raw = ask_text(
                "Technologies/tools used (comma-separated, optional):",
                required=False,
            )
            if technologies_raw:
                tech_skill_ids, _ = _map_technologies_to_skill_ids(
                    technologies_raw,
                    skills_mapper,
                )
            else:
                tech_skill_ids = []

            visibility_choice = ask_select(
                "Visibility:",
                ["Public", "Private", "Confidential"],
                required=True,
            )
            visibility = visibility_choice.lower()

            projects.append(
                {
                    "title": title,
                    "description": description,
                    "visibility": visibility,
                    "technology_skill_ids": tech_skill_ids,
                },
            )

            more = input("Add another project? (y/n): ").strip().lower()
            if more not in ("y", "yes"):
                break

    result: Dict[str, Any] = {
        "github_username": github_username,
        "linkedin_url": linkedin_url,
        "portfolio_url": portfolio_url,
        "projects": projects,
    }

    print_summary("Portfolio & projects", result)
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
    print("  ~15 minutes to build your skill profile")
    print("=" * 50)

    # Initialize skills mapper (fetches canonical skills from DB)
    mapper = SkillsMapper()

    # Collect data from all sections into a single dictionary. Using ``update``
    # keeps the merge logic simple and makes it clear that keys must be unique
    # across sections.
    data: Dict[str, Any] = {}
    data.update(section_1_identity())
    data.update(section_2_background(mapper))
    data.update(section_3_certifications(mapper))
    data.update(section_4_skills(mapper))
    data.update(section_5_ai_usage())
    data.update(section_6_learning())
    data.update(section_7_career_goals())
    data.update(section_8_career_story())
    data.update(section_9_portfolio(mapper))

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
            # certification_skills -> user_certifications
            certs_resp = client.table("user_certifications").select("id").eq(
                "user_id",
                DEV_USER_ID,
            ).execute()
            cert_ids = [
                row["id"]
                for row in getattr(
                    certs_resp,
                    "data",
                    getattr(certs_resp, "get", lambda *_: [])("data"),  # type: ignore[call-arg]
                )
            ]
            if cert_ids:
                client.table("certification_skills").delete().in_(
                    "certification_id",
                    cert_ids,
                ).execute()
        except Exception:
            # If there are no certification skills, proceed with cleanup.
            pass

        client.table("user_certifications").delete().eq(
            "user_id",
            DEV_USER_ID,
        ).execute()

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
        client.table("user_target_roles").delete().eq(
            "user_id",
            DEV_USER_ID,
        ).execute()
        client.table("user_profiles").delete().eq(
            "user_id",
            DEV_USER_ID,
        ).execute()
        print("  Existing profile cleared.\n")

    # Persist collected data to Supabase, respecting foreign key dependencies
    # and ensuring that partial failures surface clearly.
    try:
        # 1) user_profiles — core profile row with JSONB fields.
        print("  Saving profile...")
        profile_data: Dict[str, Any] = {
            "user_id": DEV_USER_ID,
            "display_name": data.get("display_name"),
            "current_role": data.get("current_role"),
            "industry": data.get("industry"),
            "country": data.get("country"),
            "languages": data.get("languages", []),
            "team_context": data.get("team_context"),
            "education_level": data.get("education_level"),
            "field_of_study": data.get("field_of_study"),
            "thesis_description": data.get("thesis_description"),
            "thesis_url": data.get("thesis_url"),
            "years_total_experience": data.get("years_total_experience"),
            "years_in_current_role": data.get("years_in_current_role"),
            "ai_usage_frequency": data.get("ai_usage_frequency"),
            "ai_tools": data.get("ai_tools", []),
            "ai_use_cases": data.get("ai_use_cases", []),
            "ai_api_experience": data.get("ai_api_experience"),
            "ai_automation_level": data.get("ai_automation_level"),
            "learning_preferences": data.get("learning_preferences", []),
            "weekly_hours_available": data.get("weekly_hours_available"),
            "learning_time_preference": data.get("learning_time_preference", []),
            "course_completion_rate": data.get("course_completion_rate"),
            "platform_access": data.get("platform_access", []),
            "learning_failures": data.get("learning_failures"),
            "career_change_history": data.get("career_change_history"),
            "work_frustrations": data.get("work_frustrations"),
            "career_narrative": data.get("career_narrative"),
            "github_username": data.get("github_username"),
            "linkedin_url": data.get("linkedin_url"),
            "portfolio_url": data.get("portfolio_url"),
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
                    "confidence": 0.5,
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
                "job_title": exp["job_title"],
                "company": exp["company"],
                "start_date": f"{exp['start_year']}-01-01",
                "end_date": f"{exp['end_year']}-12-31" if exp.get("end_year") else None,
                "description": exp["description"],
                "visibility": exp["visibility"],
                "experience_type": "job",
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

        # 4) user_certifications + certification_skills — structured learning artifacts.
        print("  Saving certifications...")
        for cert in data.get("certifications", []):
            cert_row: Dict[str, Any] = {
                "user_id": DEV_USER_ID,
                "name": cert["name"],
                "provider": cert.get("provider"),
                "year_completed": cert.get("year_completed"),
                "certificate_url": cert.get("certificate_url"),
            }
            cert_row = {k: v for k, v in cert_row.items() if v is not None}
            result = client.table("user_certifications").insert(cert_row).execute()
            cert_data = getattr(
                result,
                "data",
                getattr(result, "get", lambda *_: [])("data"),  # type: ignore[call-arg]
            )
            cert_id = cert_data[0]["id"]

            cert_skills = cert.get("skill_ids", [])
            if cert_skills:
                junction_rows = [
                    {"certification_id": cert_id, "skill_id": sid}
                    for sid in cert_skills
                ]
                client.table("certification_skills").insert(junction_rows).execute()

        # 5) user_target_roles — one row per selected role, preserving priority.
        print("  Saving career goals...")
        target_roles = data.get("target_roles", [])
        timeline = data.get("timeline", "")
        market_scope = data.get("market_scope", "")
        for i, role in enumerate(target_roles):
            role_row = {
                "user_id": DEV_USER_ID,
                "role_name": role,
                "priority": i + 1,
                "timeline": timeline,
                "market_scope": market_scope,
            }
            client.table("user_target_roles").insert(role_row).execute()

        # 6) Projects from Section 9 — stored as work_experience with type 'project'.
        print("  Saving projects...")
        for proj in data.get("projects", []):
            proj_row: Dict[str, Any] = {
                "user_id": DEV_USER_ID,
                "job_title": proj["title"],
                "company": "Personal project",
                "description": proj["description"],
                "visibility": proj["visibility"],
                "experience_type": "project",
            }
            result = client.table("work_experience").insert(proj_row).execute()
            proj_data = getattr(
                result,
                "data",
                getattr(result, "get", lambda *_: [])("data"),  # type: ignore[call-arg]
            )
            proj_id = proj_data[0]["id"]

            tech_skills = proj.get("technology_skill_ids", [])
            if tech_skills:
                junction_rows = [
                    {"work_experience_id": proj_id, "skill_id": sid}
                    for sid in tech_skills
                ]
                client.table("work_experience_skills").insert(junction_rows).execute()

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
    print(f"  Certifications: {len(data.get('certifications', []))}")
    print(f"  Target roles: {len(data.get('target_roles', []))}")
    print("=" * 50)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully so the user is not left with a stack trace.
        print("\nOnboarding cancelled.")
