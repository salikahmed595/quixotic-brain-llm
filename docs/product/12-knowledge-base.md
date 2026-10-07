<!-- PRODUCT.md section 12 -->
# 12. Knowledge Base

## 12.1 Supported Knowledge Types

- Company policies
- SOPs
- Sales scripts
- Product information
- Pricing rules
- FAQs
- HR documents
- Training material
- Marketing knowledge
- Technical documentation
- Management instructions
- Customer support processes
- Internal standards

## 12.2 Knowledge Entry

The interface must hide technical concepts.

Users should not see:

- Embeddings
- Vectors
- Tokenization
- Chunking strategy
- Vector dimensions

Example form:

```text
Add Knowledge

Title:
Premium Artwork Pricing Rule

Department:
Sales

Category:
Pricing

Information:
Customers buying 3+ artworks can receive
up to a 10% discount after manager approval.

Access:
Sales + Managers

[Submit]
```

## 12.3 Approval Workflow

```text
Draft
  ↓
Submitted
  ↓
Pending Review
  ↓
Approved
  ↓
Active
```

Alternative states:

- Rejected
- Archived
- Expired

Each record should track:

- Created by
- Created at
- Reviewed by
- Reviewed at
- Last updated by
- Last updated at
- Version
- Status
