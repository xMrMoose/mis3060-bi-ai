# Prompt Comparison — HW01

## Strategy: One-Shot

### 1. Complete Prompt

> What should a BI dashboard for a loan portfolio committee include, and why?

### 2. First 150 Words of Claude's Response

> For a loan portfolio committee, the dashboard needs to answer three things fast: how big and risky is the book, is performance trending the right way, and where is risk concentrated. Given Wildcat's fields (loan_status, credit_score, DTI, interest_rate, loan_amount, loan_purpose, state, origination_date), here's what I'd include: Portfolio summary (top of dashboard) Total outstanding balance and loan count, weighted average interest rate, weighted average credit score, and a breakdown of loan_status by both count and dollar exposure. Committees care about dollars more than counts — a small number of large delinquent loans can matter more than a large number of small ones, so both views should be visible side by side. Performance/risk trend Delinquency rate and default rate over time (by origination cohort or by month), so the committee can see whether newer vintages are performing better or worse than older ones. This is usually the single most important chart for

### 3. Evaluation

**What it did well:** The response was well-organized — it broke the answer into clear, labeled sections (portfolio summary, performance/risk trend, composition, risk segmentation, yield/return context) rather than giving one long block of text. That structure made it easy to scan.

**What was missing/generic:** The content itself felt generic and short on detail. It read like a standard "what a lending dashboard should include" answer rather than one built specifically around Wildcat Capital's actual data and situation — it didn't dig deep into the reasoning behind each metric, propose specific thresholds or benchmarks, or push further into how the pieces should work together. A one-shot prompt with no back-and-forth didn't give it room to get more specific or detailed.

---

## Strategy: Role-Assignment

### 1. Complete Prompt

> You are a senior credit risk analyst presenting to a portfolio committee of three senior executives. You are an expert in Business Intelligence and creating visualization dashboards for stakeholder presentation. You specialize in loans and presenting technical data and numbers in an effective data story to outside stakeholders

### 2. First 150 Words of Claude's Response

> I've read through the project setup (CLAUDE.md, business context Q&A log, and your estimate-vs-actual draft) — good foundation on the portfolio (2,340 loans, Auto/Personal/HI/Education/Business, elevated default rates even in the low-DTI segment).
>
> Your message sets up the persona (credit risk analyst presenting to a portfolio committee) but doesn't say what you want built yet. What's the actual deliverable for this session?
>
> *(Full response — under 150 words. Unlike the one-shot prompt, this prompt was a persona assignment with no explicit question or task attached, so Claude's response was a clarifying question rather than a substantive answer.)*

### 3. Evaluation

**What it did well:** Setting the persona up front gave Claude useful context/expertise framing to carry into later answers — it read the project files (CLAUDE.md, prior Q&A log, prior draft) before responding rather than answering blind, and grounded itself in that context. Because the prompt had no explicit question attached, Claude avoided jumping to a premature, generic answer and instead asked what deliverable was actually wanted — which is arguably better behavior than guessing.

**What was missing/generic:** Since the prompt was persona-only with no task, it didn't produce a real answer to evaluate on its own — the "response" was just a clarifying question. Once the persona was established and a real question followed later, some of the answers were still fairly short and lacked deep detail, so the persona framing alone didn't fully solve the genericness problem seen in the one-shot strategy.

---

## Strategy: Few-Shot/Example

### 1. Complete Prompt

> I am going to give you a specific question. Please respond in a concise way to gather the information in an efficient amount of time. The format of the response should be separated by overall metric/data point given an overall blurb and then specific bullet points answering the why. When responding it should be for the perspective of outsiders who do not posses technical knowledge to understand. It should be formatted exactly as described to be the easiest to grasp.
>
> What should a BI dashboard for a loan portfolio committee include, and why?

### 2. First 150 Words of Claude's Response

> This is a conceptual question, not a request to build/analyze data, so no need to touch the portfolio files. Here's what belongs on a loan portfolio committee dashboard: Portfolio Size & Composition — Total loans outstanding and total dollar balance, broken out by loan status (Current, Paid Off, Delinquent, Default). The committee needs to see the whole portfolio at a glance before drilling into any one problem area. Showing both loan count and dollar exposure matters because a handful of large loans can carry more risk than many small ones. Delinquency Rate — Share of loans (and dollars) that are past due, tracked over time. This is the earliest warning sign that borrowers are starting to struggle, before loans move to default. Watching the trend, not just the current number, tells the committee if the problem is getting better or worse. Default Rate — Share of loans (and dollars) that

### 3. Evaluation

**What it did well:** Specifying the output format up front (metric → plain-language blurb → bullet points on the "why") made the response much easier to read and understand — it forced Claude to present what it produced in a clearer, more digestible structure than either the one-shot or role-assignment strategies did on their own.

**What was missing/generic:** Even with the format locked in, the underlying content still lacked depth — it didn't get noticeably more specific to Wildcat Capital's actual portfolio or dig deeper into the reasoning than the earlier strategies did. The example/format instruction improved *presentation*, not *substance*.

---

## Conclusion

Across the three strategies, the format/example prompt produced the easiest output to actually read and use, since it forced a clear metric → blurb → bullet structure instead of a dense paragraph. But in terms of depth and specificity to Wildcat Capital's actual portfolio, the jump from role-assignment to few-shot/example was much smaller than the jump from one-shot to role-assignment — role-assignment was the first strategy to meaningfully improve the output by grounding Claude in the actual project context (reading CLAUDE.md, prior Q&A, prior drafts) rather than answering generically. My overall takeaway is that a combination of role-assignment and few-shot/example would produce the most useful output for a BI analyst: role-assignment supplies the context and expertise framing needed for substance, while the example/format instruction ensures that substance is delivered in a way stakeholders can actually digest.

---

## Fact-Check

**1. The claim:**

From `business_context.md`, Question 1 (Credit-Risk Metrics), Claude's response stated:

> "...debt-to-income ratio is a forward-looking measure of current repayment capacity..."

**2. Source used:**

CFPB — [What is a debt-to-income ratio?](https://www.consumerfinance.gov/ask-cfpb/what-is-a-debt-to-income-ratio-en-1791/)

**3. What the source says:**

> "Your debt-to-income ratio (DTI) is all your monthly debt payments divided by your gross monthly income."

CFPB defines DTI purely as a calculation (total monthly debt payments ÷ gross monthly income), with no "forward-looking" or "repayment capacity" language in the definition itself. Elsewhere on CFPB's site, DTI is described as a tool lenders use to judge whether a borrower can manage monthly loan payments — which is consistent with the "repayment capacity" idea, just not stated in those words.

**4. Do they agree?**

Partially. The core mechanics don't conflict — Claude never contradicted the actual formula (debt payments over income) and CFPB's stated use of DTI (assessing ability to manage payments) lines up with Claude calling it a "repayment capacity" measure. But CFPB's actual definition is a plain mathematical ratio, not a "forward-looking" concept — that framing was Claude's own interpretive language layered on top of the real definition, not something CFPB itself says.

**Conclusion on reliability:** This is a useful pattern to watch for — Claude's underlying facts (the DTI formula, its general purpose) were accurate, but the analytical labels wrapped around them ("forward-looking," "backward-looking") are Claude's own framing, not verified terminology from the source. For this type of claim, I'd trust Claude's raw definitions but treat any added descriptive/interpretive language as its own analysis rather than an established industry term unless I confirm it separately.
