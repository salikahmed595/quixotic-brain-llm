<!-- PRODUCT.md section 28 -->
# 28. LLM Generation Layer

The generation layer should be replaceable.

Possible providers:

- OpenAI
- Gemini
- Claude
- AWS Bedrock
- Local model

Internal interface:

```python
generate_answer(context, question)
```

The rest of the system should not depend on one provider.
