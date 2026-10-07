<!-- PRODUCT.md section 44 -->
# 44. V1 Infrastructure

```text
Frontend
Next.js + Tailwind
→ Vercel initially

Backend
FastAPI
→ AWS ECS Fargate

Database
Amazon RDS PostgreSQL
+ pgvector

Storage
Amazon S3

Queue
Amazon SQS

Background Worker
AWS ECS Worker

Embedding Service
BGE-M3
→ CPU or EC2 initially

Reranker
Multilingual reranker

Generation
External API or AWS Bedrock

Secrets
AWS Secrets Manager

Monitoring
AWS CloudWatch
```
