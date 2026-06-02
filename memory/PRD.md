# AI Receptionist PRD

## Original Problem Statement
- Build an “a.i receptionist”.

## User Choices Captured
- Core flow: answer FAQs, collect lead/contact details, book appointments/callbacks.
- Business types: clinic/healthcare, salon/spa/wellness, real estate/agency, and general small business.
- AI model: GPT-5.2 with user-provided OpenAI API key.
- Appointment booking: include selectable available time slots.

## Architecture Decisions
- Frontend: React single-page workspace with chat, booking, lead capture, profile, dashboard stats, and inbox sections.
- Backend: FastAPI API under `/api` with MongoDB persistence.
- Database: MongoDB collections for business profiles, chat sessions/messages, appointments, and leads; responses exclude Mongo `_id` fields.
- AI: Server-side GPT-5.2 integration through emergentintegrations using EMERGENT_LLM_KEY; key remains backend-only. Graceful fallback message is returned if provider service fails.
- Styling: Organic & Earthy light dashboard using Outfit/Figtree, forest green, clay, warm sand, responsive bento/control-room layout.

## User Personas
- Small business owner who needs after-hours/front-desk coverage.
- Reception/admin staff reviewing appointments, leads, and conversations.
- Visitor/customer looking for answers, callback support, or a booking slot.

## Core Requirements
- AI receptionist chat that can answer business questions and guide next steps.
- Persistent chat session/message storage.
- Business profile and FAQ knowledge base.
- Lead/contact capture for callbacks.
- Appointment slot lookup and booking with conflict prevention.
- Dashboard summary and handoff inbox.
- Responsive UI with test IDs on critical interactive/user-facing elements.

## Implemented — 2026-06-02
- Built full AI receptionist workspace UI with hero, stats, chat, profile, booking, lead capture, and inbox.
- Added FastAPI endpoints for business profile, dashboard, appointments, leads, chat sessions, and chat messages.
- Added GPT-5.2 backend integration with safe server-side key handling and graceful failure fallback.
- Added MongoDB persistence for all core flows with ObjectId-safe response models.
- Added appointment slot availability, booking conflict checks, and input validation for phone/date/time/email.
- Added partial profile update endpoint and inline profile editing.
- Verified via backend curl, screenshot interaction, and testing agent regression.

## Current Integration Status
- GPT-5.2 wiring is implemented and working with the Emergent LLM key.
- Live receptionist replies were verified via `/api/chat/message`.

## Prioritized Backlog
### P0
- Move access-code values into a managed secret rotation process for production use.

### P1
- Add structured conversation-to-lead extraction from chat.
- Add appointment rescheduling/cancellation workflows.

### P2
- Add calendar integration.
- Add SMS/email notifications for new leads and appointments.
- Add analytics for conversion, missed questions, and popular services.

## Next Tasks
1. Configure real Resend/Twilio credentials when ready for email/SMS alerts.
2. Add notification paging for larger inboxes.
3. Add scheduled compliance export emails once email credentials are configured.


## Code Quality Fixes — 2026-06-02
- Fixed React hook dependency issues using stable callbacks and corrected effect dependencies.
- Extracted repeated animation, icon-size, timing, and test-id values into named constants.
- Wrapped production console warning behind a development-only guard.
- Simplified backend regression tests with helper functions and removed problematic literal comparison style.
- Verified with JavaScript lint, Python lint, backend regression tests, and frontend smoke test.


## Staff Login & Role Protection — 2026-06-02
- Added simple staff access-code login with JWT session tokens.
- Added Admin, Staff, and Viewer roles.
- Protected receptionist dashboard, inbox, appointments list, lead list, chat session/message admin views, and profile editing endpoints.
- Admin can edit business profile; Staff can access leads; Viewer can access dashboard/inbox summaries.
- Frontend now shows a staff login panel for protected inbox access and supports logout/session restoration.
- Verified with backend regression tests, browser smoke test, and testing-agent role protection checks.


## Notifications, Chat-to-Lead Extraction & Audit Logs — 2026-06-02
- Added in-app notification center for appointment bookings, lead captures, lead suggestions, and approved suggestions.
- Added automatic chat-to-lead extraction when visitor messages include contact info and appointment/callback intent.
- Suggested chat leads require Staff/Admin approval before becoming active new leads.
- Added staff activity audit logs for login/logout, viewing protected resources, profile edits, lead approval, and system-created visitor events.
- Added Admin-only audit log panel in the receptionist inbox.
- Real Resend email and Twilio SMS were intentionally deferred per user choice; current notifications are in-app only.
- Verified with backend regression, browser smoke tests, and testing-agent validation.


## Notification Filters & Audit Export — 2026-06-02
- Added notification filters by type and read/unread status.
- Updated unread notification count to respect the current staff user and selected type filter.
- Added Admin audit filters by action and actor role.
- Added Admin-only CSV export endpoint for compliance review.
- Added frontend export button that downloads filtered audit logs as CSV.
- Verified role restrictions: Staff/Viewer cannot access audit export.
- Verified with backend regression, browser smoke test, and testing-agent compliance validation.


## Code Review Security & Quality Fixes — 2026-06-02
- Fixed backend staff auth undefined-variable risk by explicitly initializing and validating staff before return.
- Removed localStorage token persistence; staff session token is now kept in memory only.
- Updated toast subscription hook to use React useSyncExternalStore instead of manual effect listener state.
- Refactored protected data loading helpers and CSV download helper to reduce stale-closure risk.
- Removed nested ternary expressions from profile field rendering.
- Simplified complex regression tests with focused helper functions.
- Verified with lint, 40-test backend regression suite, browser smoke test, and independent testing-agent validation.


## Code Review Follow-up Fixes — 2026-06-02
- Replaced backend identity-style staff check with safer falsy validation.
- Removed production console warning from CRACO visual-edits fallback.
- Added named HTTP status constants in frontend auth/session handling.
- Made reviewed React callback dependencies explicit while keeping memory-only staff sessions.
- Simplified notification/audit compliance tests and auth URL helper nesting.
- Verified with lint, 52-test backend regression, browser smoke test, and independent iteration-6 testing.
