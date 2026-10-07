<!-- PRODUCT.md section 11 -->
# 11. Ask Brain

## 11.1 Purpose

Ask Brain is the main employee-facing interface.

It should feel similar to ChatGPT.

Users should be able to ask natural-language questions without understanding RAG, embeddings, metadata, or vector databases.

## 11.2 Example

User:

```text
customer bol raha hai artwork bohat expensive hai, kya jawab doon?
```

Quixotic Brain:

```text
Recommended approach:

The customer appears interested but has a pricing objection.

Previous successful Quixotic conversations show that explaining value before offering a discount is usually a stronger strategy than immediately reducing price.

Suggested reply:

"I completely understand. Since this is custom artwork made specifically for you, the price reflects the time and detail involved. If budget is the main issue, let me know your range and we can see what option works best."

Sources:
- Sales Objection Playbook
- 14 similar historical cases
- 9 successful outcomes
```

## 11.3 Ask Brain Requirements

The system must:

- Detect user identity
- Detect role
- Detect department
- Enforce permissions before retrieval
- Detect query language
- Handle Urdu
- Handle Roman Urdu
- Handle English
- Handle mixed-language queries
- Retrieve approved company knowledge
- Retrieve historical sales examples when appropriate
- Rerank results
- Generate grounded answers
- Show sources
- Support feedback

## 11.4 Ask Brain Modes

Potential modes:

### General
Ask company-wide questions within permission boundaries.

### Sales Coach
Focused on objections, sales strategy, responses, and historical outcomes.

### Search Only
Retrieve knowledge without LLM generation.

### Department Brain
Examples:

- Sales Brain
- HR Brain
- Marketing Brain
- Development Brain

These modes should share the same central backend.
