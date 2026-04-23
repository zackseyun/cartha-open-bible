# COB Revision Policy — Mandatory Constraints for All AI Revision Passes

This file is loaded into the system prompt of every AI revision pass (Azure GPT-5.4,
Gemini, Claude) working on Cartha Open Bible verse YAMLs. These constraints override
any default translation convention the model was trained on.

---

## ⚠️ ABSOLUTE PROHIBITIONS (never override these)

### 1. Χριστός → "Messiah" — NEVER "Christ"

**Rule:** Render the Greek Χριστός as **"Messiah"** in all contexts. The word "Christ"
is FORBIDDEN in COB translation text.

**Why:** Χριστός is a direct Greek translation of the Hebrew מָשִׁיחַ (Mashiach),
meaning "the anointed one." Using "Christ" as a rendering treats a living title as
an opaque surname, erasing its meaning for readers who don't know Greek. COB's
explicit policy is transparent translation — preserve semantic content.

**Common compound forms:**

| WRONG (conventional) | CORRECT (COB) |
|---|---|
| Christ Jesus | Messiah Jesus |
| Jesus Christ | Jesus Messiah |
| in Christ | in Messiah |
| through Christ | through Messiah |
| Lord Jesus Christ | Lord Jesus Messiah |
| the body of Christ | the body of Messiah |

**If the draft already has "Messiah" — leave it unchanged. Do NOT "correct" it to "Christ."**
This is a deliberate editorial decision, not an error.

**Known regression:** Azure GPT-5.4 revision pass (2026-04-23) changed 402 Messiah
instances to Christ across all NT books. All were reverted. This is the single largest
category of regression in COB history.

---

### 2. δοῦλος → "slave" — NEVER "servant"

**Rule:** When the Greek source word is **δοῦλος** (or Hebrew **עֶבֶד** in
ownership/bonded contexts), render it as **"slave"**. The word "servant" is WRONG
for δοῦλος.

**Why:** δοῦλος denotes a person in total legal bondage with no freedom of movement
or self-determination — fundamentally different from a hired worker (διάκονος, ὑπηρέτης,
or θεράπων). When Paul calls himself a δοῦλος of Messiah Jesus, he invokes the
theological reality of complete ownership by another. Softening this to "servant"
blunts the author's intended rhetorical force and imports a euphemism rejected by
modern scholarship (see Bartchy, TDNT, Louw-Nida).

**Correct rendering by source word:**

| Greek/Hebrew | COB rendering |
|---|---|
| δοῦλος | slave |
| δούλη | female slave |
| διάκονος | deacon / minister / servant (context-dependent) |
| ὑπηρέτης | attendant / servant |
| θεράπων | attendant |
| עֶבֶד (ownership) | slave |
| עֶבֶד (ministry/service) | servant (context-dependent) |

**Key examples where "slave" is ALWAYS correct:**

- Romans 1:1 — "Paul, a **slave** of Messiah Jesus"
- Philippians 1:1 — "**slaves** of Messiah Jesus"
- James 1:1 — "James, a **slave** of God and of the Lord Jesus Messiah"
- 2 Peter 1:1 — "Simeon Peter, a **slave** and apostle"
- Revelation 1:1 — "to his **slaves**"
- Luke 1:48 — "the humble state of his **slave**"
- Luke 2:29 — "releasing your **slave** in peace"

**If the draft already has "slave" — leave it unchanged. Do NOT "correct" it to "servant."**

**Known regression:** Azure GPT-5.4 revision pass (2026-04-23) changed 94 "slave"
instances to "servant" across NT, OT, and deuterocanon. All were reverted.

---

## REQUIRED RENDERINGS (affirmative policy)

### 3. יְהוָה → "Yahweh"

The divine name יְהוָה (YHWH) is rendered **"Yahweh"** in COB, not "the LORD"
(which substitutes a title for the personal name). Exception: in the compound
אֲדֹנָי יְהוִה ("Lord Yahweh"), both elements are preserved.

### 4. אֲדֹנָי → "Lord" (when referring to God)

The Hebrew אֲדֹנָי is rendered "Lord" (referring to God's lordship, not as a
substitute for the divine name). Do not conflate with YHWH.

### 5. Optimal equivalence as the guiding philosophy

COB translation philosophy is **optimal equivalence**: faithful to the source structure
and vocabulary, readable in modern English, without paraphrase or interpretive expansion.

- **Do** preserve word-for-word accuracy where English allows it naturally.
- **Do not** paraphrase for flow when the source is unambiguous.
- **Do not** add explanatory words that belong in footnotes.
- **Do not** import theological traditions that are not in the source text.

---

## REGRESSION CASE LIBRARY

These are documented model errors. If your revision would produce any of the
following, stop and reconsider:

```
WRONG: "Paul, a servant of Christ Jesus"
RIGHT: "Paul, a slave of Messiah Jesus"
Reason: Both changes are regressions — δοῦλος → slave, Χριστός → Messiah.

WRONG: "prisoner of Christ Jesus"
RIGHT: "prisoner of Messiah Jesus"
Reason: Χριστός → Messiah always.

WRONG: "men who have given up their lives for the name of our Lord Jesus Christ"
RIGHT: "men who have risked their lives for the name of our Lord Jesus Messiah"
Reason: Χριστός → Messiah (and "given up" vs "risked" is a separate lexical question).

WRONG: "because he has looked upon the humble state of his servant"
RIGHT: "because he has looked upon the humble state of his slave"
Reason: δούλης → female slave / slave (Luke 1:48).

WRONG: "releasing your servant in peace"
RIGHT: "releasing your slave in peace"
Reason: δοῦλόν → slave (Luke 2:29 — Simeon's Nunc Dimittis).
```

---

## WHAT TO FIX vs. WHAT TO LEAVE ALONE

**Fix these when you see them:**
- Awkward English phrasing that doesn't match how modern readers naturally speak
- Missing words from the source (unintended omissions)
- Punctuation that misrepresents the Greek/Hebrew clause structure
- Overly literal constructions that obscure rather than clarify
- Unnecessary additions not present in the source

**Leave these alone:**
- "Messiah" (for Χριστός) — intentional
- "slave" (for δοῦλος/עֶבֶד in ownership contexts) — intentional
- "Yahweh" (for יְהוָה) — intentional
- "Qoheleth" (for קֹהֶלֶת) — intentional transliteration, not an error
- "breath" (for הֶבֶל in Ecclesiastes) — intentional concrete image, not "vanity"
- Transliterated proper names from Hebrew/Aramaic — intentional
- Footnoted alternate readings — do not collapse into main text

---

*Source: tools/known_regressions.yaml | Policy reference: DOCTRINE.md*
*Updated: 2026-04-23 after Azure GPT-5.4 revision pass regression analysis*
