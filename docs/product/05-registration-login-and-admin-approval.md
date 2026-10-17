<!-- PRODUCT.md section 5 -->
# 5. Registration, login, and admin approval

**FR-AUTH-01 — Sign up:** Public registration page styled consistently with the screenshots. Required fields: full name, work email, password, confirm password, requested department; optional employee ID/phone if the company uses them. No self-selection of admin/CEO roles. Validate email uniqueness, password policy, and rate limits.

**FR-AUTH-02 — Email verification:** Verify email or issue company-specific invitations/OTP. A verified email is not equivalent to company employment approval.

**FR-AUTH-03 — Pending approval:** New account status is Pending. Show a clear pending page after signup. User cannot access chat, company knowledge, admin APIs, or indexed content while pending.

**FR-AUTH-04 — Review by admin:** Send a pending-user event to Admin → Access requests. An authorized admin can open the request, check identity/department, assign role and scope, then Approve or Reject with an optional note. Approval creates an audit record and activates access.

**FR-AUTH-05 — Account states:** Pending, Active, Rejected, Suspended, Deactivated. Suspending access revokes active sessions promptly. Rejected users are told how to contact an administrator without revealing internal data.

**FR-AUTH-06 — Login security:** Secure password hashing (Argon2id preferred), HttpOnly secure session cookies, CSRF protection as appropriate, login throttling, password reset, logout, session expiry, and admin MFA. Use an established authentication framework rather than inventing cryptography. Bootstrap the first system administrator through a one-time protected setup path; never via public signup.

**FR-AUTH-07 — Profile:** Employee can view name, department(s), effective access scope, and account settings; cannot escalate own role. Admin can update membership, disable users, and view account status history.
