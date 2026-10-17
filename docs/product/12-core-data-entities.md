<!-- PRODUCT.md section 12 -->
# 12. Core data entities

users, user_departments, roles, permissions, access_requests, sessions, departments, chats, chat_messages, feedback, knowledge_documents, document_versions, document_chunks, document_permissions, knowledge_proposals, approval_decisions, knowledge_gaps, integration_identities, ingestion_events, index_jobs, audit_events, system_settings, secret_references.

Store the last indexed document version and checksum; uniquely identify external bot events to prevent duplicate writes. Avoid a data model where one user's role or one document's department exists only as an LLM-generated label.
