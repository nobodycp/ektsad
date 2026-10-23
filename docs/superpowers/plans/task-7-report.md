# Task 7 Report: Single-Page Shell and Account Screens

Status: DONE_WITH_CONCERNS

Commit SHA: the commit that adds this file, `feat: add the single-page shell and account screens`. A report cannot hold its own SHA. Run `git log -1 --format=%H -- docs/superpowers/plans/task-7-report.md` to get it.

Test summary: `npm test -- --run` in `web/` gives 7 files and 57 tests passing, 12 of them new in `src/router.test.tsx`. `tsc --noEmit` is clean and `vite build` succeeds.

## What was built

- `react-router-dom` 6 was added. `main.tsx` wraps `App` in `BrowserRouter`. `App` holds only the auth provider and routes, so tests mount it inside `MemoryRouter`.
- Routes: `/` is the login page. `/account/` is the settings page. `/complaints/`, `/governor/report/`, `/reports/`, `/telegram-health/`, `/governorates/`, `/regions/`, `/users/`, `/prices/` and `/crossings/` are placeholders that show their heading plus a short "coming soon" note. Unknown paths show a not-found state inside the shell.
- The sidebar per role matches the spec order exactly. A route the role may not use shows exactly `لا تملك صلاحية الوصول إلى هذه الصفحة.` Anonymous visitors are sent to `/` and returned to the page they wanted after login.
- `AppShell` renders plain `<a href>` links. Its source was not touched. A wrapper in `Shell.tsx` catches plain left-clicks on internal links, calls `preventDefault`, and uses `navigate()`. There is no `location.reload` or document navigation. A test checks that the click event's default is prevented.
- API calls go through `api.ts` with `credentials: "include"`. POST and PATCH send `X-CSRFToken` from the `csrftoken` cookie. If the cookie is missing before login, the login page calls `GET /api/auth/me/` first to get one.
- Login failure shows the server's `detail`, which is `بيانات الدخول غير صحيحة.`, and falls back to that same string. Network and other errors have their own Arabic messages.
- Account page: the display name is saved with `PATCH /api/users/<id>/`, and the header updates. The password form has current, new and confirm fields. It checks for at least 12 characters and a matching confirmation before calling `POST /api/users/<id>/password/` with `{mode: "set", password, password_confirm, current_password}`. A 404 or 405 shows `تغيير كلمة المرور غير متاح على الخادم حالياً. لم تتغير كلمة المرور.`. Other rejections show the server's message.
- A sign-out button in the header posts to `/api/auth/logout/` and returns to `/`.
- Styles in `src/app.css` use only design-system tokens. The login page is a ledger-ruled paper sheet with an ink edge, and the account sections are hairline panels. No `<table` is used anywhere in pages.

## Concerns

- `POST /api/users/<id>/password/` is not routed in `config/urls.py` yet, so password changes will 404 until the backend adds it. The form is complete and shows the Arabic error above. The backend may also need to keep the session alive after the change.
- `PATCH /api/users/<id>/` returns no `role`. The client merges the response into the current user, so the role is kept.
- To let the given test query the sidebar synchronously, `auth.tsx` exports `primeSession()`. Tests use it to seed the session. In the browser, the session starts empty and is loaded from `/api/auth/me/`.
- Django does not serve the SPA yet. `config/spa.py` and the catch-all URL were out of scope for this task, so a deep link like `/account/` only works through the Vite dev server for now.
- React Router 6 prints v7 future-flag warnings in tests. They are harmless.
- I did not check the screens in a real browser.
- `docs/superpowers/plans/task-8-11-report.md` was already untracked in the tree. I left it out of this commit.
