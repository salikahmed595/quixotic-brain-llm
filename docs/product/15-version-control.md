<!-- PRODUCT.md section 15 -->
# 15. Version Control

Current information must always override old information.

Example:

```text
Discount Policy V1
Maximum discount: 20%
Status: ARCHIVED

Discount Policy V2
Maximum discount: 10%
Status: ACTIVE
```

Default retrieval must include:

```text
status = active
```

Archived information should not influence current answers unless explicitly requested.
