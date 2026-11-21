# Problem research: Agentic AI Hackathon, 21 Nov 2026

Step 1 of the playbook: find the real problems users have before thinking about solutions.

---

## Track 2: Smart Campus & City Tech (Debrecen)

### International students at the University of Debrecen
- **Size of the group:** about **7,800 international students** in 2025/26, from **130–140 countries**. That is roughly a quarter of the ~30–32k total enrolment. [UniDeb news](https://hirek.unideb.hu/en/node/28257), [THE profile](https://timeshighereducation.com/world-university-rankings/university-debrecen)
- **Typical problems, as listed by UniDeb's own research:** language difficulties, financial problems, homesickness, accommodation issues, employment issues, and a lack of emotional and social support. [UniDeb](https://edu.unideb.hu/page.php?id=145)
- **Paperwork they keep coming back to:** since July 2023 most immigration tasks (residence-permit extension, change of accommodation and so on) are done online, and third-country nationals also have to file accommodation reports. [UniDeb Immigration Office](https://edu.unideb.hu/page.php?id=145)
- **Housing:** students arrange their own housing before they arrive, demand peaks before each semester, and housing is the biggest monthly cost. [UniDeb housing guide](https://southasia.edu.unideb.hu/blog/blog-details/Student-Housing-Debrecen-Ultimate-Guide-for-Stress-Free-Living/)
- **Money:** a study permit limits working hours, which adds to financial vulnerability. A 2022 Debrecen study looked at food insecurity and psychological distress among international students. [Nutrients/MDPI](https://mdpi.com/2072-6643/16/2/241)
- **The same pattern abroad:** in Germany, 29% name the language barrier as their biggest issue after arriving and 12% name bureaucracy. 83% of German universities report visa and administrative delays. In the Netherlands, information on finances, housing and work rules is often missing in English. [Expatrio](https://www.expatrio.com/about-germany/challenges-international-students-germany-face?hsLang=en), [expat.com](https://www.expat.com/en/expat-mag/10198-daily-realities-and-unexpected-challenges-of-being-an-international-student.html), [NL Times](https://nltimes.nl/node/87383)

### Student wellbeing in general
- 49% of UK undergraduates feel anxious every day, 44% have experienced burnout, and 39% have trouble making friends (Chegg 2025, 11,706 respondents in 15 countries). [Yorkshire Post](https://www.yorkshirepost.co.uk/education/chegg-global-student-survey-2025-uk-students-struggling-mental-health-how-compare-worldwide-4963735)
- 64.7% of US college students report feeling lonely (Active Minds 2024). [Campus Safety](https://www.campussafetymagazine.com/?p=168549)

### Public transport in Debrecen
- A Feb 2026 opinion piece says service is weak: slow trams, a sparse bus network and limited coverage. [Debrecen Sun](https://www.debrecensun.hu/local/2026/02/03/its-not-just-a-feeling-debrecens-public-transport-is-really-in-trouble/)
- DKV pass sales fell 60% after the integrated county pass appeared (HUF 945 for students, previously HUF 5,500), so fares are now very confusing. [Debrecen Sun](https://www.debrecensun.hu/local/2026/03/02/will-debrecen-get-trams-3-and-4-we-asked-the-ceo-of-dkv/), [Xpatloop](https://xpatloop.com/channels/2025/12/hungarys-2nd-city-adopts-integrated-public-transport-fare-system.html)
- In a 2022 UniDeb survey, **over half of respondents said real-time passenger information would get them to switch from car to public transport**. [ResearchGate](https://researchgate.net/profile/Tuende-Kovacs-3/publication/363634146_Issues_in_Information_Systems_Digital_transformation_possibilities_in_public_transportation_in_Debrecen/links/6326188b70cc936cd316143b/Issues-in-Information-Systems-Digital-transformation-possibilities-in-public-transportation-in-Debrecen.pdf)

---

## Track 3: Developer Productivity
- **Searching for information:** 61% of developers spend more than 30 minutes a day searching for answers (Stack Overflow, via Sourcegraph). [Sourcegraph](https://sourcegraph.com/blog/developer-onboarding)
- **Time lost:** 69% lose 8 or more hours a week to inefficiencies such as tech debt and poor documentation. [The New Stack](https://thenewstack.io/why-do-developers-lose-1-day-a-week-to-inefficiencies/)
- **Documentation:** missing or fragmented docs are among the top barriers. 41% call insufficient documentation the biggest barrier (Perforce Java 2025). [Stack Overflow blog](https://stackoverflow.blog/2025/12/10/tell-us-what-you-really-really-do-not-want-to-spend-time-working-on/), [ITPro](https://www.itpro.com/software/development/java-developer-productivity-challenges)
- **Onboarding:** 72% take more than a month to submit their first 3 meaningful PRs in a new codebase (Cortex 2024). Google names the top ramp-up blockers as new tech, poor docs and finding experts. [Augment](https://www.augmentcode.com/blog/the-hidden-cost-of-code-complexity-why-developer-ramp-up-takes-longer-than-you-think), [DX](https://newsletter.getdx.com/p/developer-onboarding-time)
- **Risk:** this is a crowded space (Copilot, Sourcegraph, Claude Code itself), so standing out is hard.

## Track 1: Autonomous Agents
- 79% of companies say they are adopting agents, but 68% say half or fewer of their staff use them (PwC 2025). [PwC](https://www.pwc.com/us/en/tech-effect/ai-analytics/ai-agent-survey.html)
- **Trust is the blocker:** only 6% fully trust agents with core operations (Workato/HBR), and trust drops further for financial tasks (20%). [Fortune](https://fortune.com/2025/12/09/business-leaders-dont-trust-ai-harvard-survey/)
- **Risk:** the user is "companies", which is abstract. The problem is hard to make concrete and demoable in 9 hours.

---

## Assessment

| Track | Specific user? | Evidence | Demoable in 9h | Local "why us" |
|---|---|---|---|---|
| 2: Smart Campus | ✅ first-year international students at UniDeb | medium (strong abroad, thinner for Debrecen) | ✅ | ✅ strong |
| 3: Dev Productivity | ✅ developers onboarding to a new codebase | strong | ✅ | weak, crowded space |
| 1: Autonomous Agents | ❌ abstract "businesses" | medium | hard | weak |

**Initial recommendation was Track 2. The team chose Track 1.** See the Track 1 deep dive below.

<details><summary>Original Track 2 notes</summary>

**Track 2.** Target user: **first-year, non-EU international students at the University of Debrecen**, in their first 1–3 months. The problem is getting through Hungarian bureaucracy, housing and city life in a foreign language: residence permit, accommodation reporting, Neptun, DKV passes, finding the right office.

### Evidence gap to close (pitch page 2)
The Debrecen-specific numbers are thin. Tonight, run a 5-question Google Form in UniDeb international student groups and on the hackathon Discord. For example: "How many hours did you spend on paperwork in your first month?" and "What was the most confusing process?" 30+ answers would give you your own survey data, which judges love.

</details>

---

# Track 1 deep dive (chosen track): Autonomous Agents & Intelligent Systems

"Businesses" is too generic, so the job is to find **one specific user** with a painful, repetitive, multi-step task that an agent can *execute*, not just chat about.

## Problem A: Small business owners buried in admin ⭐ recommended
- UK SME owners spend about **7.3 h/week** on admin and operations, about 21% of their time (NerdWallet/OnePoll, Jun 2025, n=500). [NerdWallet](https://www.nerdwallet.com/uk/business/survey-how-uk-business-owners-are-prioritising-time-and-money-in-2025/)
- Another estimate is **about 11 h/week** on admin and finance (SME Business Barometer, n=1,000; date not confirmed). [Startups Magazine](https://startupsmagazine.co.uk/small-businesses-spend-more-time-on-admin-than-growing-their-business)
- Admin is the 2nd most common task outside small-business leaders' job description, at 18% (Upwork, Nov 2025, n=2,272). [business.com](https://www.business.com/articles/productivity-crisis-facing-small-business-leaders/)
- **Why agents haven't solved it yet: trust.** Only 6% fully trust agents with core operations, and trust falls to 20% for financial transactions (PwC 2025; Workato/HBR). [PwC](https://www.pwc.com/us/en/tech-effect/ai-analytics/ai-agent-survey.html), [Fortune](https://fortune.com/2025/12/09/business-leaders-dont-trust-ai-harvard-survey/)
- **Possible USP:** an agent that does the boring multi-step work (email → invoice → reminder → bookkeeping entry) but **asks for one-tap approval before anything irreversible**. That design answers the trust gap directly.
- **Narrow the user further:** e.g. *freelancers and micro-businesses with 1–5 people in Hungary* (tutors, photographers, repair shops) who have no office manager or accountant on staff.

## Problem B: Knowledge workers acting as "human middleware"
- Workers spend **about 30% of the week (1.5 days)** navigating disconnected tools (Asana, n=3,000+ UK/US). [TechRadar](https://techradar.com/pro/using-too-many-collaboration-tools-is-actually-making-work-harder)
- 57% redo work across different tools (Miro 2025, n=6,148). 17% switch apps more than 100 times a day (Lokalise). [Lokalise](https://lokalise.com/blog/blog-tool-fatigue-productivity-report/)
- People lose nearly a full day a week copying between AI tools and internal systems (Workday 2026). [ITPro](https://www.itpro.com/technology/artificial-intelligence/too-many-employees-are-serving-as-the-human-middleware-workers-are-wasting-a-full-work-day-each-week-switching-between-disparate-ai-tools-and-internal-systems)
- **Risk:** "knowledge workers" is generic. It needs narrowing to one role and one workflow.

## Problem C: Developers whose agents fail in production
- Gartner (Jun 2025, 3,400+ orgs) predicts **over 40% of agentic AI projects will be cancelled by the end of 2027**. [Arize](https://arize.com/blog/common-ai-agent-failures/)
- 78% have an agent pilot, but only **14% have scaled one** (survey of 650 tech leaders, Mar 2026). [AI Accelerator Institute](https://www.aiacceleratorinstitute.com/ai-agents-keep-breaking-in-production-heres-why-nobodys-fixed-it-yet/)
- Failures are silent: hallucinated tool arguments, ignored prompt restrictions (the Replit production-DB incident, Jul 2025), and schema breakage. [Arize](https://arize.com/blog/common-ai-agent-failures/), [KDnuggets](https://kdnuggets.com/heres-what-everyone-gets-wrong-about-agentic-ai)
- **Risk:** crowded (Arize, LangSmith, Maxim), and it's hard to make the demo emotional for non-technical judges.

## Problem D: PhD students doing literature reviews
- Systematic reviews "can take months". Many PhD programmes have students spend their first ~9 months scoping and reviewing. Medical writers average about 85 h per new review. [arXiv](https://arxiv.org/pdf/2007.07751), [LSE](https://blogs.lse.ac.uk/writingforresearch/2014/12/08/doing-a-quick-literature-review), [EMWA](https://journal.emwa.org/artificial-intelligence-and-machine-learning/a-survey-on-current-use-of-software-tools-for-systematic-literature-reviews/article/15176/9-a-survey-on-current-use-of-software-tools-for-systematic-literature-reviews.pdf)
- **Pros:** faculty judges feel this pain personally. **Cons:** the evidence is thin, and the space is crowded (Elicit, Consensus, SciSpace).

## Track 1 comparison

| | Specific user | Evidence | Unique angle | Demo in 9h |
|---|---|---|---|---|
| **A: Micro-business admin agent** | ✅ freelancers / 1–5 person businesses | good (hours/week + trust data) | ✅ approval-first agent answers the trust gap | ✅ |
| B: Human middleware | ⚠️ needs narrowing | good | medium | ✅ |
| C: Agent reliability tooling | ✅ agent developers | good | ⚠️ crowded | ⚠️ |
| D: Literature review agent | ✅ PhD students | thin | ⚠️ crowded | ✅ |
