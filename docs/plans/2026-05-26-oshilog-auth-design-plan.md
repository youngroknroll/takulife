# OshiLog Authentication Design Plan

Date: 2026-05-26
Sources:
- `docs/plans/2026-05-20-oshilog-mvp-planning.md`
- `docs/erd/2026-05-26-oshilog-screen-design-erd.html`
- `docs/plans/2026-05-26-oshilog-rest-api-design-plan.md`

Project root: `/Users/yeongroksong/Desktop/study/project/taku`

## 1. Goal

Define the authentication approach for OshiLog users and admin operators.

The product needs:

- Google login for regular members.
- Django-admin-based operator access for draft review and publication.
- A user model that can support future profile fields without rewriting the auth stack.

## 2. Decision

Use Django authentication as the base and introduce a custom user model from the start.

Recommended shape:

- `AUTH_USER_MODEL = "accounts.User"`
- `accounts.User` extends `AbstractUser`
- Google login is the primary member sign-in path
- Local password signup is not a first-MVP requirement
- First login through Google creates the account automatically

This is the smallest design that fits the product:

- Django still handles sessions, permissions, admin, CSRF, and auth middleware.
- OshiLog only customizes the user model where product fields are needed.
- Member onboarding stays simple because users do not need to create a separate password account.

## 3. Why Not A Fully Custom Auth System

Do not build login and signup from scratch.

Reasons:

- Django already solves session auth, password hashing, permissions, and admin integration.
- The product does not need a bespoke identity system.
- Custom auth would add risk without improving the MVP outcome.
- Google login already gives the user-friendly onboarding the product needs.

## 4. User Model Scope

### Include

- Base identity and permissions from `AbstractUser`.
- `email` as a unique field.
- `display_name` for the service profile.
- `avatar_url` or image field only if the UI needs it later.
- Optional `login_provider` metadata if needed for analytics or debugging.

### Exclude for now

- Multiple social providers.
- Password reset UX.
- Email-only signup.
- Phone number auth.
- MFA.
- Account merging UI.

## 5. Login Flow

### Member login

1. User clicks Google login.
2. Frontend obtains Google identity proof.
3. Backend verifies the token or authorization code.
4. Backend finds or creates the user by verified Google email.
5. Backend logs the user in and returns the session or API auth state.

### First login

- If the Google email does not exist, create the user automatically.
- Set a usable default display name from Google profile data if available.
- Keep the account minimal until the user edits their profile.

### Subsequent login

- Reuse the existing user row.
- Do not create duplicate accounts for the same verified email.

## 6. Admin Access

- Draft creation, review, approval, and rejection stay admin-only.
- Admin operators continue to use Django admin.
- `is_staff` and `is_superuser` remain the control flags for operator access.
- Member Google login does not automatically grant admin access.

## 7. API Boundary

The REST API design should stay provider-agnostic where possible.

Recommended auth-related endpoints:

| Method | Path | Purpose | Auth |
| --- | --- | --- | --- |
| GET | `/api/auth/me/` | current logged-in user | required |
| POST | `/api/auth/google/` | Google login or account creation | public |
| POST | `/api/auth/logout/` | end current session | required |

If the implementation later chooses a library such as `django-allauth` or a token-based provider flow, the external provider details can change without changing the member-facing contract above.

## 8. Security Rules

- Verify Google identity on the backend.
- Trust only the verified email claim from Google.
- Never accept a client-provided email as proof of identity.
- Require CSRF protection for session-based POST/PATCH/DELETE requests.
- Keep admin review endpoints separate from member endpoints.
- Use HTTPS in production and reject insecure OAuth callback handling.

## 9. Deferred Work

Deferred Refactoring Note

- Topic: Add support for additional login providers and account linking.
- Why it is not part of the current scope: Google login is enough for the first member onboarding path.
- Why it may be needed later: Some users may prefer Apple, Kakao, or email-based login.
- Trigger condition: When member demand or regional expansion requires alternative identity providers.
- Expected change location: `accounts` app and auth API layer.
- Related tests: Google login, current-user endpoint, and duplicate account prevention tests.

