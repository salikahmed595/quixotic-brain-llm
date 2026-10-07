<!-- PRODUCT.md section 17 -->
# 17. Discord Import

## 17.1 Import UI

```text
Sales Memory
   ↓
Import Conversations
   ↓

Drop JSON File

discord-sales-history.json

Detected:

7,043 conversations
86,421 messages

[Process Conversations]
```

## 17.2 Processing Pipeline

```text
JSON Upload
   ↓
Store Raw JSON
   ↓
Parse Conversations
   ↓
Remove System Messages
   ↓
Detect Customer / Agent
   ↓
Anonymize Personal Data
   ↓
Detect Language
   ↓
Extract Objection
   ↓
Extract Intent
   ↓
Extract Sales Stage
   ↓
Extract Agent Response
   ↓
Extract Outcome
   ↓
Extract Sale Value / Discount if available
   ↓
Calculate Quality Signals
   ↓
Generate Embeddings
   ↓
Store as Sales Memory
```
