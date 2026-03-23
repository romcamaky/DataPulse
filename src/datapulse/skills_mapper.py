"""
Skills Mapper — translates free-text skill names to canonical skill IDs.

The skills table has ~51 canonical skills with lowercase underscored names
(e.g., "postgresql", "window_functions"). Users type all sorts of variations
("Postgres", "PBI", "github actions"). This mapper handles the translation.

Used by: onboarding questionnaire, CV parser, market signal extraction.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from datapulse.db import get_client
from datapulse.skill_aliases import SKILL_ALIASES


class SkillsMapper:
    """Translate free-text skill names into canonical skill IDs.

    The mapper loads all skills from Supabase and builds several lookup
    structures for efficient resolution:

    - ``_by_name``: maps canonical ``name`` -> ``id``
    - ``_by_display``: maps lowercased ``display_name`` -> ``id``
    - ``_aliases``: maps common free-text aliases -> canonical ``name``
    """

    def __init__(self) -> None:
        """Initialize the skills mapper and load skills from Supabase.

        On initialization, the mapper:

        1. Fetches all rows from the ``skills`` table using the shared
           Supabase client.
        2. Builds lookup dictionaries for ``name`` and ``display_name``.
        3. Stores the raw skills list for display and grouping helpers.

        If any error occurs while fetching from Supabase, the mapper
        degrades gracefully: all lookup structures are left empty and
        mapping methods will simply return ``None`` for all inputs.
        A warning is printed to aid debugging during development.
        """
        # Initialize empty structures so the instance is always usable,
        # even if Supabase access fails.
        self._by_name: Dict[str, str] = {}
        self._by_display: Dict[str, str] = {}
        self._aliases: Dict[str, str] = dict(SKILL_ALIASES)
        self._skills_list: List[Dict[str, Any]] = []

        try:
            client = get_client()
            # Select all columns from the skills table. The Supabase Python
            # client returns an object whose ``data`` attribute contains
            # the list of rows.
            response = client.table("skills").select("*").execute()
            skills_data: List[Dict[str, Any]] = getattr(
                response, "data", getattr(response, "get", lambda *_: [])("data")  # type: ignore[call-arg]
            )

            if not isinstance(skills_data, list):
                # Defensive check: if the response is unexpectedly shaped,
                # fall back to an empty list to avoid runtime errors.
                skills_data = []

            self._skills_list = skills_data

            # Build lookup dictionaries for efficient mapping.
            for skill in skills_data:
                skill_id = str(skill.get("id", "")).strip()
                name = str(skill.get("name", "")).strip()
                display_name = str(skill.get("display_name", "")).strip()

                if not skill_id or not name:
                    # Skip malformed rows without an identifier or canonical name.
                    continue

                normalized_name = name.lower()
                self._by_name[normalized_name] = skill_id

                if display_name:
                    normalized_display = display_name.lower()
                    self._by_display[normalized_display] = skill_id

        except Exception as exc:  # noqa: BLE001
            # Print a warning instead of raising so that onboarding and
            # other flows can still run, just without skill mapping.
            print(
                "Warning: Failed to load skills from Supabase; "
                "skill mapping is disabled. Error:",
                exc,
            )

    def map_skill(self, text: str) -> Optional[str]:
        """Map a single free-text skill name to a canonical skill ID.

        The matching logic is applied in the following priority order:

        1. Exact match on canonical ``name`` (case-insensitive).
        2. Exact match on ``display_name`` (case-insensitive).
        3. Alias lookup (free-text alias -> canonical ``name``).
        4. If no match is found, returns ``None``.

        Args:
            text: The free-text skill name provided by the user.

        Returns:
            The canonical skill UUID as a string if a match is found,
            otherwise ``None``.
        """
        if not text:
            return None

        # Normalize input by trimming whitespace and lowercasing.
        normalized = text.strip().lower()
        if not normalized:
            return None

        # 1) Exact match on canonical name.
        skill_id = self._by_name.get(normalized)
        if skill_id:
            return skill_id

        # 2) Exact match on display name (case-insensitive).
        skill_id = self._by_display.get(normalized)
        if skill_id:
            return skill_id

        # 3) Alias lookup: map alias -> canonical name, then canonical name -> ID.
        canonical_name = self._aliases.get(normalized)
        if canonical_name:
            return self._by_name.get(canonical_name)

        # 4) No match found.
        return None

    def map_skills(self, texts: List[str]) -> List[Tuple[str, Optional[str]]]:
        """Map a list of free-text skill names to their canonical IDs.

        This is a bulk helper that preserves the original text for each
        entry while resolving to the corresponding skill ID when possible.

        Args:
            texts: A list of free-text skill names.

        Returns:
            A list of ``(original_text, skill_id_or_none)`` tuples, where
            ``skill_id_or_none`` is the canonical skill UUID if a match is
            found, otherwise ``None``.
        """
        results: List[Tuple[str, Optional[str]]] = []
        for raw in texts:
            mapped_id = self.map_skill(raw)
            results.append((raw, mapped_id))
        return results

    def get_all_skills(self) -> List[Dict[str, Any]]:
        """Return the full list of skills as loaded from the database.

        This method is intended for display purposes, such as showing all
        available skills during onboarding or in configuration screens.

        Returns:
            A list of dictionaries, each containing at least:
            ``{"id": str, "name": str, "display_name": str, "category": str}``.
        """
        # Return a shallow copy so callers cannot accidentally mutate
        # the internal list.
        return list(self._skills_list)

    def get_skills_by_category(self) -> Dict[str, List[Dict[str, Any]]]:
        """Group skills by their category field.

        This is used to present skills in structured sections, for example
        grouping by language, framework, platform, or tool during self-
        assessment or onboarding flows.

        Returns:
            A dictionary mapping category name to a list of skill dicts,
            e.g. ``{"language": [...], "framework": [...], "tool": [...]}``.
            Skills with a missing or empty category are grouped under the
            ``"uncategorized"`` key.
        """
        grouped: Dict[str, List[Dict[str, Any]]] = {}

        for skill in self._skills_list:
            raw_category = skill.get("category") or "uncategorized"
            category = str(raw_category).strip() or "uncategorized"

            if category not in grouped:
                grouped[category] = []

            grouped[category].append(skill)

        return grouped

