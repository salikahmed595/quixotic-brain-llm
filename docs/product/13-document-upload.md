<!-- PRODUCT.md section 13 -->
# 13. Document Upload

## 13.1 V1 File Support

- PDF
- DOCX
- TXT
- Markdown
- JSON
- CSV

Potential later:

- Google Drive
- Website crawling
- Notion
- Slack
- Email
- CRM integrations

## 13.2 Upload Form

```text
Upload Document

File:
sales_handbook.pdf

Department:
Sales

Category:
Sales Training

Access:
Sales + Managers

Version:
3

Status:
Active

[Upload & Process]
```

## 13.3 Processing Pipeline

```text
Upload
   ↓
Store Original File
   ↓
Extract Text
   ↓
Clean Text
   ↓
Chunk Content
   ↓
Attach Metadata
   ↓
Generate Embeddings
   ↓
Create Keyword Index
   ↓
Store
   ↓
Available for Retrieval
```
