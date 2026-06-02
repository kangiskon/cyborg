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
- Add staff authentication before exposing admin inbox data outside internal use.

### P1
- Add staff authentication and private admin-only inbox access.
- Add structured conversation-to-lead extraction from chat.
- Add appointment rescheduling/cancellation workflows.

### P2
- Add calendar integration.
- Add SMS/email notifications for new leads and appointments.
- Add analytics for conversion, missed questions, and popular services.

## Next Tasks
1. Add staff login before exposing inbox data beyond demo use.
2. Add notification handoff for appointments and callback requests.
3. Add automatic chat-to-lead extraction.


## Code Quality Fixes — 2026-06-02
- Fixed React hook dependency issues using stable callbacks and corrected effect dependencies.
- Extracted repeated animation, icon-size, timing, and test-id values into named constants.
- Wrapped production console warning behind a development-only guard.
- Simplified backend regression tests with helper functions and removed problematic literal comparison style.
- Verified with JavaScript lint, Python lint, backend regression tests, and frontend smoke test.
