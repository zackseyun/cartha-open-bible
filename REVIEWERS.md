# Review Board

No verse is published in the Cartha Translation until a named reviewer on
this list has signed it with their ed25519 private key. Reviewers are
scholars, pastors, or theologically-trained contributors with disclosed
credentials.

This list is public and append-only — prior versions are preserved in git
history. Reviewers may resign; their past signatures remain valid for the
verses they signed.

## Current board

> **Status: seeding.** The board is being assembled. Founding reviewers
> will be named here as they join.

### Zack Seyun Kim — Founder, Project Lead

- **Role:** Project lead and initial reviewer during bootstrap phase
- **Credentials:** Founder, Cartha Inc.
- **Scope:** Interim review of all verses during pilot phase until the
  external board is fully seeded. Reviews during this period carry the
  explicit disclosure that they predate full external scholarly validation.
- **Public key (ed25519):** *(to be generated and committed)*
- **Joined:** 2026-04-16

## Credentials we seek

The target composition of the full board:

- **At least three reviewers** holding advanced theological degrees
  (MDiv, ThM, PhD) from accredited seminaries
- **Cross-denominational representation** within ecumenical orthodoxy:
  at minimum one Reformed, one Wesleyan/Arminian, one Catholic or
  Orthodox voice
- **Language specialization**: at least one NT (Koine Greek) specialist
  and one OT (Biblical Hebrew) specialist
- **Denominational standing**: active ordination or institutional
  affiliation, disclosed publicly

## How reviewers are added

1. A candidate is nominated (by self or by existing reviewer).
2. Candidate discloses credentials, denomination, and scope.
3. Existing board discusses in a public GitHub issue.
4. If accepted, candidate generates an ed25519 keypair and submits the
   public key via pull request adding their entry to this file.
5. Their entry is signed by at least one existing reviewer, then merged.

## Scope of review

Reviewers sign individual verses, not entire books. A reviewer may decline
to review verses outside their competence (e.g., a NT specialist declining
to review Psalms). Every verse shipped must have at least one signature
from a reviewer with competence in the source language.

## Disclosure of review practice

For transparency, each reviewer maintains a brief public statement of their
review practice — how much time they spend per verse, what reference works
they consult, which theological commitments they bring. These statements
live in `reviewers/<reviewer-slug>.md` and are referenced from this file.
