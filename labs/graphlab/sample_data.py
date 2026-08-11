"""Sample corpus for the labs. Deliberately messy: aliases, a job change,
a hallucination trap, and dates in mixed formats.
"""

EPISODES = [
    {
        "source": "standup-2024-01",
        "occurred_at": "2024-01-15",
        "body": "Alice joined Northwind 2024. Alice worked on Project Atlas.",
    },
    {
        "source": "design-doc",
        "occurred_at": "2024-03-02",
        "body": "Project Atlas depends on Billing Service. Project Atlas uses Postgres.",
    },
    {
        "source": "standup-2025-06",
        "occurred_at": "2025-06-10",
        "body": "Bob joined Northwind 2025. Bob worked on Project Atlas.",
    },
    {
        "source": "incident-review",
        "occurred_at": "2026-02-11",
        "body": "Billing Service depends on Postgres. Ledger Service replaced Billing Service 2026.",
    },
    {
        "source": "hr-note",
        "occurred_at": "2026-04-01",
        "body": "Alice left Northwind 2026. Alice joined Contoso 2026.",
    },
]

# Aliases you seed by hand. Entity resolution is a data problem, not a
# prompting problem — see Lesson 6.
ALIASES = {
    "Northwind Inc": "Northwind",
    "Atlas": "Project Atlas",
}

KNOWN_PEOPLE = {"Alice", "Bob"}
