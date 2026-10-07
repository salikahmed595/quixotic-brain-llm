<!-- PRODUCT.md section 38 -->
# 38. Ask API

## Request

```json
{
  "user_id": "emp_104",
  "department": "sales",
  "question": "customer bol raha hai artwork expensive hai"
}
```

## Response

```json
{
  "answer": "First acknowledge the concern and explain the value before discussing a discount.",
  "confidence": "high",
  "sources": [
    {
      "title": "Sales Objection Playbook",
      "section": "Price Objections"
    }
  ],
  "historical_cases": {
    "similar": 14,
    "successful": 9
  }
}
```
