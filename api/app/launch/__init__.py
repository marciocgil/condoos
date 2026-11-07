"""CondoOS Launch (D88, D89): the guided implementation of a condominium.

A conduction layer over the existing objects, with no domain of its own:

- ``journey``: the five milestones (LM1-LM5), each computed from a fact in the database. A
  milestone is never stored and never grants anything.
- ``readiness``: per capability (C1-C3 for now), whether it is "não configurado", "análise
  parcial" or "supervisionada", with what is missing. Requirements are binary: no score
  unlocks anything (ADR-L03).
- ``first_value``: the card a síndico sees after sending a contract: each field with its
  source and excerpt, uncertain fields as "a confirmar", and the limits of the reading.
- ``steps``: at most three next steps, one primary, ordered by the chosen goal.
- ``state``: the only stored part, the human choices (``launch_state``, ADR-L01).

Planning: ``docs/condoos-planning/launch/``.
"""
