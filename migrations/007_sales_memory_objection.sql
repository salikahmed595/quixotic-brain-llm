-- PRD §17.2 "Extract Objection": the owner's sales-memory export carries the customer's objection per record.
ALTER TABLE sales_memories ADD COLUMN customer_objection text;
CREATE INDEX sales_memories_department ON sales_memories (tenant_id, department_id);
