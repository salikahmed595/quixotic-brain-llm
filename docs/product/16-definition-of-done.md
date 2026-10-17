<!-- PRODUCT.md section 16 -->
# 16. Definition of done

Release only when: (a) the two screenshot-based views pass visual review; (b) registration and administrator approval function end-to-end; (c) permission tests pass at API, retrieval, and document levels; (d) approved answers are sourced and unsupported questions fail safely; (e) admins can manage accounts/documents/departments; (f) history and data are durable; (g) backups and restore have been tested; (h) model/data-provider usage is authorized; and (i) the system passes the agreed 160-employee load profile. Telegram/Discord/Hermes automation is a later milestone and must not delay a safe Phase 1 launch.

**Implementation direction to Claude Code:** Treat the supplied screenshots as non-negotiable desktop visual references. First audit the existing Quixotic AI repository and list what already works. Reuse rather than replace functioning components. Implement P0 in small, testable milestones with migrations, API contracts, seed data, unit/integration/E2E permission tests, screenshots, and a written deployment guide. Ask for real department rules and permissions instead of fabricating them.
