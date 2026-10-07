<!-- PRODUCT.md section 47 -->
# 47. Background Jobs

Large processing tasks must be asynchronous.

Use:

- Amazon SQS
- ECS workers

Tasks include:

- Document parsing
- Bulk chat parsing
- Embedding generation
- Re-indexing
- Data import
- Batch processing

Frontend should show progress.

Example:

```text
Processing Discord Conversations

████████████░░░░ 73%

5,143 / 7,043 processed
```
