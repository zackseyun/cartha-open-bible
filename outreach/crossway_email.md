# Crossway ESV API Outreach Email

**To:** api@crossway.org
**From:** Zack Seyun Kim, Founder, Cartha Inc. (zack@cartha.com)
**Subject:** ESV API free-tier eligibility — Christian mobile app with scripture-only free access

---

## Draft body

Hi Crossway team,

I'm the founder of Cartha (cartha.ai), a faith-based mobile app that connects
Christians through short video conversations with the mission of helping
believers find one another and build relationships rooted in Christ. We're
building out a full Bible-reading experience and want to include the ESV for
our users.

Before we integrate the ESV API, I want to be fully transparent about our
app's model so your team can tell me whether we qualify for the free tier
or whether we need a different licensing arrangement.

**Our model:**

- Bible reading in the Cartha app is and will remain completely free. No
  ads, no paywalls, no upsells, no promotions anywhere in the scripture
  reading flow.
- The app itself has paid features — subscriptions ($5.99 Basic, $19.99 Pro)
  — but these exclusively gate matchmaking features (queue priority, extended
  conversation length). Subscriptions do not touch, appear alongside, or
  influence the scripture experience.
- We do not sell advertising anywhere in the app.
- We do not charge for scripture access, and have no plans to.

I recognize that Crossway's standard API terms define "commercial" at the
app level, which would technically disqualify an app that has subscriptions
for any feature. I'd like to request written confirmation that Cartha's
use case is acceptable under the free tier, given that:

1. ESV readers in our app will have a scripture experience indistinguishable
   from a purely non-commercial app.
2. Our mission is aligned with Crossway's — we exist to connect the body
   of Christ and make scripture more accessible to 18-35-year-old
   Christians who may not otherwise be reading daily.
3. We're happy to comply with any additional constraints you'd want to
   impose (e.g., no scripture adjacent to subscription prompts, specific
   attribution placement, opt-in AI-usage disclosures).

A few additional specifics I want to disclose upfront:

- **Caching:** We'd cache within the 500-verse limit you specify and
  refresh periodically.
- **AI usage:** We may eventually build features that use LLMs to suggest
  scripture verses relevant to a user's conversation or journaling (e.g.,
  "a passage that relates to what you've been praying about"). We would
  obtain your explicit written approval before shipping any such feature
  and are happy to discuss the design.
- **Offline:** We understand the free tier caps caching at 500 verses and
  are not requesting unrestricted offline access.
- **Attribution:** We will display the full ESV attribution string on the
  app's About screen and the "(ESV)" marker on every displayed passage,
  per your guidelines.

If you need additional information about Cartha, our legal entity is
Cartha Inc. (Delaware C-Corp). Happy to provide anything that helps your
evaluation.

Thank you for the ministry of the ESV — it's been a deeply formative
translation for many of our target users, and we'd love to make it easy
for them to read it inside Cartha.

In Christ,

Zack Seyun Kim
Founder, Cartha Inc.
zack@cartha.com
cartha.ai

---

## Notes for OpenClaw

- **Send from:** zack@cartha.com
- **Send via:** standard Gmail (no special headers required)
- **Expected response time:** 1-2 weeks (per research)
- **If declined:** ship without ESV. We have BSB + KJV + ASV + WEB + Cartha
  Translation + originals, which is sufficient.
- **If approved:** reply thanking them, save approval email to this directory
  as `crossway_approval.md`, then unblock task #6 (ESV API integration).
- **If they ask for more info:** loop back to Zack Seyun Kim before responding.
