# Wildcat Capital — Business Context Q&A Log

This document records the business-understanding questions asked during the "understanding the business and portfolio" stage of the project, along with a summary of the analysis provided and an open follow-up question raised by each. Full responses are available in the project chat history; this log is a summary, not a verbatim transcript.

---

## Question 1: Credit-Risk Metrics (Credit Score, DTI, Annual Income)

**Exact prompt:**
"Wildcat Capital's borrower data includes credit score, debt-to-income ratio, and annual income. How should a consumer lender interpret these three attributes together when assessing credit risk, and what risks could arise from relying too heavily on any one of them? Explain what each attribute contributes and how conflicting signals—such as a strong credit score but a high debt-to-income ratio—should be interpreted."

**Summary of response:**
Credit score is a backward-looking measure of repayment history, debt-to-income ratio is a forward-looking measure of current repayment capacity, and annual income is a scale/context variable that makes DTI and loan size interpretable rather than a risk measure on its own. Relying on any single attribute can miss real risk: a strong score can mask current over-extension, a low DTI can mask a poor repayment history, and high income doesn't guarantee low leverage. The specific conflicting-signal case of a strong score with a high DTI should be read as elevated forward-looking risk despite a clean history, since a strong score reflects the past while a high DTI describes current financial strain. The recommended approach is to require both a favorable score (willingness to repay) and a favorable DTI/income position (capacity to repay) rather than letting one compensate for the other.

**Follow-up question raised:**
What DTI and credit-score thresholds count as "high" or "strong" for Wildcat Capital's own underwriting?

---

## Question 2: Quarterly Portfolio Review Across Loan Purposes

**Exact prompt:**
"Wildcat Capital's portfolio contains Auto, Personal, Home Improvement, Education, and Business loans. What would a portfolio committee typically want to review each quarter to understand the performance and risk of this specific loan-purpose mix? Explain which comparisons, trends, and warning signs would be most important and why the committee should evaluate the five purposes separately rather than viewing the portfolio only as a whole."

**Summary of response:**
A committee would typically want to see, for each loan purpose separately, the trend (not just the current level) in delinquency and default rates, the dollar exposure at risk (not just loan counts), shifts in origination mix toward riskier purposes, and average credit score/DTI/interest rate to detect underwriting drift. Key warning signs include one purpose deteriorating while others stay flat, rapid origination growth paired with declining average credit score, and loan-count trends diverging from dollar-exposure trends (signaling growing average loan size). The five purposes differ structurally in collateral status, loan size, term, and borrower risk profile, so blending them into one portfolio-wide number is a weighted average that can hide a purpose-specific problem. The core rationale for separate review is that aggregate stability can mask offsetting trends — improvement in one purpose canceling out deterioration in another.

**Follow-up question raised:**
How concentrated is the actual portfolio, by count and dollars, across the five purposes?

---

## Question 3: Delinquency vs. Default and Status Transitions

**Exact prompt:**
"Wildcat Capital classifies loans as Current, Paid Off, Delinquent, or Default. What is the business difference between delinquency and default, how do loans typically move among these four statuses, and what should management infer from changes in the number of Delinquent loans compared with changes in Defaults? Explain which status transitions could serve as early-warning indicators of worsening portfolio risk."

**Summary of response:**
Delinquent means a loan has missed payments but is still considered an active, potentially recoverable obligation, while Default means the loan has breached the agreement seriously enough to be treated as a loss event, typically moving toward write-off or collections. The typical path is Current → Delinquent → either cures back to Current or progresses to Default, with Paid Off and Default generally treated as terminal statuses. Rising Delinquent counts with flat Default counts suggest a growing at-risk pool that hasn't yet converted to losses (a leading indicator), while rising Default counts suggest losses are already crystallizing (a lagging, more serious signal) — and both rising together is the most concerning combination. The most useful early-warning metrics are the Current-to-Delinquent flow rate (how much of the healthy book is newly slipping) and the Delinquent-to-Default conversion/cure rate (how well delinquent loans are recovering), since these flow rates catch deterioration earlier than the raw point-in-time status counts.

**Follow-up question raised:**
Does the dataset track status history per loan, or just a single point-in-time status?
