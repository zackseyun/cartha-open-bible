# Tyndale NLT API / Permissions Outreach Email

**To:** permissions@tyndale.com (CC: dev@tyndale.com if it exists)
**From:** Zack Seyun Kim, Founder, Cartha Inc. (support@cartha.ai)
**Subject:** NLT API use — Christian mobile app, scripture-only free access,
written permission request

---

## Draft body

Dear Tyndale Permissions team,

I'm the founder of Cartha (cartha.ai), a faith-based mobile app that
connects Christians through short video conversations to build authentic
relationships rooted in Christ. We're building out a full Bible-reading
experience inside Cartha and would love to offer the NLT alongside other
translations.

I've registered at api.nlt.to and want to disclose our use case upfront to
request written permission that covers our specific model, since I
understand that apps displaying full books on demand exceed the default
permissions allowance and require direct authorization.

**Our model:**

- Bible reading in Cartha is and will remain completely free. No ads, no
  paywalls, no upsells, no promotions anywhere in the scripture flow.
- The app has paid subscriptions ($5.99 Basic, $19.99 Pro) that gate only
  matchmaking features (queue priority, extended conversation length).
  These features are architecturally separate from scripture and never
  appear alongside it.
- We do not sell advertising.
- We do not charge for scripture access.

**What we'd like to display:**

- Full NLT text, queryable by book/chapter/verse, with users able to read
  any full book they want.
- Display only (no editing, modification, or redistribution as raw text
  to other apps).
- Cached per your API's technical limits, refreshed regularly.
- With the full NLT attribution displayed on our About screen:
  "Scripture quotations are taken from the Holy Bible, New Living
  Translation, copyright ©1996, 2004, 2015 by Tyndale House Foundation.
  Used by permission of Tyndale House Publishers, Carol Stream, Illinois
  60188. All rights reserved."
- And "(NLT)" markers on each displayed passage.

**What we'd request:**

Written permission for commercial-tier display of the full NLT via
api.nlt.to, under our specific model (free scripture, paid unrelated
features). We're happy to accept any additional constraints you'd want to
impose.

We're also exploring NVI (Spanish) for our Dallas/Latin American audience
and would love to include that under the same permission if possible.

**About Cartha:**

- Legal entity: Cartha Inc. (Delaware C-Corp)
- Mission: Connect the body of Christ through authentic video conversation
- Target audience: 18-35 digitally active Christians
- Launch market: Dallas, TX → Bible Belt → Brazil and international
- We're ministry-aligned and building partnerships with churches as a
  primary distribution channel.

I'd be happy to share additional information, a demo of the app, or jump
on a call if that's helpful for your evaluation. Thank you for the
stewardship of the NLT — it's one of the most widely-read translations
among the younger Christian readers we're building for, and we'd love
to include it.

In Christ,

Zack Seyun Kim
Founder, Cartha Inc.
support@cartha.ai
cartha.ai

---

## Notes for OpenClaw

- **Send from:** support@cartha.ai
- **Initial recipient:** permissions@tyndale.com (Tyndale House Publishers
  Permissions). Confirm this address is current before sending.
- **If separate developer contact exists:** CC that too.
- **Expected response time:** 2-4 weeks for permissions requests.
- **If declined:** ship without NLT. Not a critical path.
- **If approved:** reply thanking them, save approval email to this
  directory as `tyndale_approval.md`, then unblock task #7 (NLT API
  integration).
- **If they ask for more info:** loop back to Zack Seyun Kim before responding.
