# Cartha Open Bible — Cross-Platform Parity Map

A side-by-side reference for the **Cartha Open Bible** (COB) reading experience as it exists on **mobile (Flutter)** and on the **website (Next.js)**.

The two surfaces ship the same product. They use different code, different state libraries, different rendering primitives — but every feature on one should have a counterpart on the other. This document is the lookup table: when you add a feature to one surface, find its row, copy the change to the mirror.

> **Status:** living document. Update the same change set whenever you add, rename, or remove a COB surface on either platform.

---

## 1. Repos and entry points

| Concern | Mobile (Flutter) | Web (Next.js) |
|---|---|---|
| Repo | `cartha.ai.mobile/cartha_ai_mobile` | `cartha.website` |
| COB root | `lib/screens/bible/` | `src/app/(main)/cartha-open-bible/` |
| Reader entry | `bible_reader_screen.dart` | `BibleReader.jsx` (page = `page.js`) |
| Chapter URL | (in-app navigation, no URL) | `?view=read&book=…&chapter=…` (URL-synced via `useSearchParams`) |
| Translation source | `assets/bibles/*.json` (bundled) + `cob_runtime_sync.dart` (delta sync) | `bibleApi.js` (CDN-fetched) + `bibleData.js` (canon definitions) |
| Library / bookmarks store | `bible_library_store.dart` | `useLibraryStore.js` |
| Tool-thread cache | `bible_tool_threads_store.dart` | `bible_tool_threads_store.js` (mirrored under `lib/` of the website) |
| Concept history | `lib/services/bible/concept_history.dart` | `conceptHistory.js` |
| Canon preferences | `lib/services/bible/canon_preferences.dart` | `canonPreferences.js` |

**Convention:** files keep the same logical name across surfaces — Flutter uses `snake_case.dart`, Next.js uses `PascalCase.jsx` for components and `camelCase.js` for helpers/stores. Every web `*Sheet.jsx` corresponds to a mobile `*_sheet.dart`.

---

## 2. Surface-by-surface mirror

Each row is a single user-facing surface. If you add or rename one, update both columns in the same change set.

| Surface (what the user sees) | Mobile file | Web file |
|---|---|---|
| Reader (book grid → chapter grid → chapter view) | `bible_reader_screen.dart` | `BibleReader.jsx` |
| Chapter view (verse list, selection, footnotes) | inside `bible_reader_screen.dart` (`ChapterView` widget) | inside `BibleReader.jsx` (`ChapterView` function component) |
| Translation picker | inside `bible_reader_screen.dart` (`TopNavUser` / `TranslationPickerSheet`) | inside `BibleReader.jsx` (`TopNavUser`) |
| Library menu (bookmarks, notes, recent study) | `bible_library_api.dart` + sheets in `bible_reader_screen.dart` | `useLibraryStore.js` + library views in `BibleReader.jsx` |
| Verse detail sheet (AI insight, commentary, cross-refs) | `bible_verse_detail_sheet.dart` | `VerseDetailSheet.jsx` |
| Verse hover / preview card | `bible_verse_hover_card.dart` | (web shows it inline in `ChapterView`) |
| Connections / cross-reference sheet | `bible_connections_sheet.dart` | `HiddenConnectionsPanel.jsx` |
| AI Study tool sheet (Simplify / Cross-ref / Original / Summarize) | `bible_study_overlay.dart` + `bible_tool_runner.dart` + `bible_tool_widgets.dart` | `StudyToolSheet.jsx` |
| Note editor | `bible_note_editor_sheet.dart` | `NoteEditorSheet.jsx` |
| Suggest revision | (not yet shipped on mobile) | `SuggestRevisionSheet.jsx` |
| Insight / explanation panel | (inline in chapter view) | `InsightPanel.jsx` |
| Commentary drawer | inside `bible_verse_detail_sheet.dart` | `CommentaryDrawer.jsx` |
| Thread view (saved AI conversation) | `bible_thread_screen.dart` | `thread/page.jsx` |
| Concept atlas | `bible_concept_atlas_screen.dart` + `bible_concept_navigator.dart` + `bible_force_graph.dart` | `atlas/ConceptAtlas.jsx` + `atlas/AtlasNavigator.jsx` |
| Spotlight / search | `bible_spotlight_search.dart` + `bible_search_*.dart` | inline search in `BibleReader.jsx` |
| Sign-in gate (auth modal) | shared app auth (Cognito → SuperTokens migration) | `UnifyAuthModal.jsx` |
| Verse share / OG card | (mobile share sheet) | `share/_lib/` + `share/[book]/` + `verse/page.jsx` |
| Chapter concept strip | `bible_chapter_concept_strip.dart` | `ChapterConceptStrip` (inline in `BibleReader.jsx`) |
| Bible study chat (per chapter, freeform) | `bible_study_chat_sheet.dart` | `StudyToolSheet.jsx` (with `skipInitialRun=true` and `CHAPTER_CHAT_TOOL`) |
| Compare translations | (in-screen translation picker) | `compare/page.js` |
| Cross-check (chapter-vs-chapter) | (not shipped on mobile) | `cross-check/page.js` |
| Reading progress | (in `bible_library_store.dart`) | `progress/page.js` |
| Revisions browser | (links out) | `revisions/page.js` |
| About COB | (in app menu) | `about/page.js` |
| Methodology / docs | (links out to website) | `docs/[slug]/` |

**Rule of thumb:** if a row has only one cell filled, the next product cycle should fill the other or explicitly mark the gap.

---

## 3. State and storage parity

| Concern | Mobile | Web |
|---|---|---|
| Reactive state | `setState` + `ChangeNotifier` (Flutter built-ins; no Riverpod for the COB tree) | `useState` + `useMemo` (React) |
| Persistent local state | `SharedPreferences` (e.g., `mixpanel_device_id`, recent translation) | `localStorage` (e.g., `cob-oauth-pending`, `cartha_mixpanel_user_id`, theme override) |
| Per-user library | `bible_library_store.dart` (in-memory + REST sync) | `useLibraryStore.js` (in-memory + REST sync) |
| Tool-thread cache | `bible_tool_threads_store.dart` | analogous web store; key shape is `${tool.id}__${book}__${chapter}__…` on both |
| Auth token | `Preferences().getToken()` (Cognito JWT today, SuperTokens after migration) | Amplify session cookie + bearer pulled from session |
| Theme (light/dark) | `bible_theme.dart` | `cobTheme.js` |

**Design rule:** keys, ids, and JSON shapes are mirrored verbatim across surfaces. A `threadId` produced on web must be readable by mobile and vice versa.

---

## 4. Backend / API parity

Both surfaces talk to the same `mobile-api-service-go` cluster (alpha = `https://alpha-api-mobile.cartha.ai`). They share endpoints; the wrappers differ.

| Endpoint family | Mobile client | Web client |
|---|---|---|
| Translation/chapter fetch | `bible_library_api.dart` | `bibleApi.js` |
| Verse-tool runner (`/bible/verse-tool`) | `bible_tool_runner.dart` (`runVerseTool`) | `bibleApi.js` (`runVerseTool`) |
| Tool-thread store (`/bible/tool-threads/*`) | `bible_tool_threads_api.dart` | `bibleApi.js` (`upsertToolThread`, `readToolThreads`) |
| Shared summary cache (`/bible/shared-summary`) | inline in `bible_reader_screen.dart` | `bibleApi.js` (`fetchSharedSummary`) |
| Bookmarks / notes (`/library/*`) | `bible_library_api.dart` | `useLibraryStore.js` |
| Verse detail / AI insight | inline in `bible_verse_detail_sheet.dart` | `VerseDetailSheet.jsx` (calls `bibleApi.js`) |
| Concept atlas / graph | `bible_concept_navigator.dart` | `atlas/AtlasNavigator.jsx` |

> When you change a request/response shape, change both clients in the same PR. The backend is single-tenant; surfaces drift silently if you don't.

---

## 5. Analytics — the canonical `cob_*` event vocabulary

This is the single source of truth that the moderation dashboard's `/_admin/metrics/website/overview` endpoint queries. Both surfaces emit the **same event names** with the **same property keys**. Mixpanel's `platform` super-property (`web` / `ios` / `android` / `macos`) is what the dashboard splits on.

### 5.1 Canonical events

| Event name | Fired when | Required properties | Optional properties |
|---|---|---|---|
| `cob_reader_view` | The reader opens a chapter view OR the chapter content first paints | `book`, `chapter`, `translation` | `verse_count`, `from` (`books`/`chapters`/`search`/`library`/`deeplink`) |
| `cob_book_open` | A book is opened from the book grid | `book`, `translation` | `from` |
| `cob_chapter_open` | A chapter is opened from the chapter grid | `book`, `chapter`, `translation` | `from` |
| `cob_translation_change` | User switches translation in the picker | `from_translation`, `to_translation` | `book`, `chapter` |
| `cob_verse_toggled` | A verse is selected or deselected | `book`, `chapter`, `verse`, `selected` (bool) | `selection_count_after` |
| `cob_tool_open` | A study tool sheet opens (Simplify / Cross-ref / Original / Summarize / Chapter-chat) | `tool` (`simplify`/`cross_reference`/`original`/`summarize`/`chapter_chat`), `book`, `chapter`, `translation` | `verse_count`, `resumed` (bool), `cache_hit` (bool) |
| `cob_tool_output` | The tool sheet receives its first assistant message (live OR cache hit) | `tool`, `book`, `chapter`, `translation`, `cache_hit` (bool) | `verse_count`, `latency_ms` |
| `cob_thread_open` | A saved AI thread is reopened from history/library/inline indicator | `tool`, `book`, `chapter` | `from` (`library`/`recent`/`inline`) |
| `cob_note_editor_open` | The note editor sheet opens | `book`, `chapter`, `verse` | `had_existing_note` (bool) |
| `cob_note_saved` | A note is saved | `book`, `chapter`, `verse` | `length` |
| `cob_bookmark_toggled` | A bookmark is added or removed | `book`, `chapter`, `verse_count`, `action` (`added`/`removed`) | |
| `cob_related_passage_open` | User taps a related/cross-referenced passage | `from_book`, `from_chapter`, `from_verse`, `to_book`, `to_chapter`, `to_verse` | `surface` (`detail_sheet`/`connections`/`tool_output`) |
| `cob_auth_gate` | Sign-in is required to use a gated COB feature | `gate` (`tool`/`bookmark`/`note`/`library`), `tool` (when `gate=tool`) | |
| `cob_auth_success` | Sign-in completes and the gated action proceeds | `gate`, `method` (`apple`/`google`/`email`) | |
| `cob_search_executed` | Reader runs a search | `query_length` | `result_count` |
| `cob_concept_atlas_open` | Concept atlas surface opens | | `from`, `concept` |

### 5.2 Required super-properties (auto-attached by both SDKs)

- `platform` — `web` / `ios` / `android` / `macos`
- `app_version` (mobile) / `app_version: 'web'` (web)
- `user_id` (when signed in)
- `device_id` (mobile) — anonymous identifier persisted in `SharedPreferences`

### 5.3 Mobile alias map (transitional)

Mobile already fires `bible_reader_*` events. The `MixpanelAnalyticsService` translation table emits the canonical `cob_*` twin so historical dashboards and the new dashboard both work. Drop the legacy names after one full release cycle.

| Mobile legacy event | Canonical alias |
|---|---|
| `bible_reader_book_opened` | `cob_book_open` |
| `bible_reader_chapter_opened` | `cob_chapter_open` |
| `bible_reader_translation_selected` | `cob_translation_change` |
| `bible_reader_verse_toggled` | `cob_verse_toggled` |
| `bible_reader_bookmark_toggle_tapped` | `cob_bookmark_toggled` |
| `bible_reader_note_editor_opened` | `cob_note_editor_open` |
| `bible_reader_note_saved` | `cob_note_saved` |
| `bible_reader_tool_tapped` | `cob_tool_open` |
| `bible_reader_chapter_chat_opened` | `cob_tool_open` (`tool=chapter_chat`) |
| `bible_reader_summarize_book_tapped` | `cob_tool_open` (`tool=summarize`) |
| `bible_reader_related_passage_tapped` | `cob_related_passage_open` |
| `bible_reader_search_result_opened` | `cob_search_executed` |

The `trackScreen('bible_reader_chapter_view', …)` call also emits `cob_reader_view` with the same payload.

### 5.4 Web call-site map

| Canonical event | Web call site |
|---|---|
| `cob_reader_view` | `BibleReader.jsx` — the chapter-view `useEffect` after `chapterObj` resolves |
| `cob_book_open` | `BibleReader.jsx` — `BookList`/`Section` `onPick` |
| `cob_chapter_open` | `BibleReader.jsx` — `ChapterGrid`/`ChapterList` `onPick` |
| `cob_translation_change` | `BibleReader.jsx` — translation picker `onSelect` |
| `cob_verse_toggled` | `BibleReader.jsx` — `setSelectedVerses` paths |
| `cob_tool_open` | `StudyToolSheet.jsx` — first `useEffect` once `threadIdRef.current` is assigned |
| `cob_tool_output` | `StudyToolSheet.jsx` — inside `run` after `setMessages(withAssistant)` |
| `cob_thread_open` | `BibleReader.jsx` — `setResumeThread` paths (history, recent, inline indicator) |
| `cob_note_editor_open` | `BibleReader.jsx` — `openNoteForSelection` / `handleNoteVerse` |
| `cob_note_saved` | `NoteEditorSheet.jsx` — `onSave` resolved branch |
| `cob_bookmark_toggled` | `BibleReader.jsx` — `toggleBookmarkOnSelection`, `handleBookmarkVerse` |
| `cob_related_passage_open` | `VerseDetailSheet.jsx` and `HiddenConnectionsPanel.jsx` — passage-tap handlers |
| `cob_auth_gate` | `BibleReader.jsx` — `requireAuth` (the `setSignInOpen(true)` branch) |
| `cob_auth_success` | `BibleReader.jsx` — `onSignInSuccess` |
| `cob_search_executed` | `BibleReader.jsx` — debounced `setActiveSearchQuery` effect |
| `cob_concept_atlas_open` | `atlas/ConceptAtlas.jsx` — mount effect |

---

## 6. Naming conventions

| Concept | Rule |
|---|---|
| Mobile widget files | `snake_case.dart` (e.g., `bible_note_editor_sheet.dart`) |
| Web component files | `PascalCase.jsx` (e.g., `NoteEditorSheet.jsx`) |
| Web helper/store files | `camelCase.js` (e.g., `useLibraryStore.js`) |
| Mixpanel event names | `cob_*` snake_case, lower-case, **passed verbatim** to Mixpanel (no title-casing) |
| Property keys | `snake_case` |
| Translation IDs | shortName matches across surfaces (`BSB`, `COB`, `KJV`, `ASV`) |
| Verse identifiers | canonical form `book/chapter:verse` (function: mobile `canonicalVerseId`, web `canonicalVerseId`) |
| Tool ids | `simplify`, `cross_reference`, `original`, `summarize`, `chapter_chat`, `recontextualize_bible` |

---

## 7. Adding a new feature — checklist

When adding a new COB feature, walk this checklist:

1. **Pick the surface.** Find the equivalent row in §2. If your new surface has no row, add one.
2. **Mirror the file paths.** If you create `something_sheet.dart`, also create `SomethingSheet.jsx` (and vice versa).
3. **Reuse existing API endpoints.** If you need a new endpoint, add it once in `mobile-api-service-go` and consume from both clients (§4).
4. **Mirror state shape.** Use the same JSON keys, the same id format, the same cache keys (§3).
5. **Instrument analytics.** Add the canonical `cob_*` event in both surfaces, with the same property keys (§5). Update the alias map in `mixpanel_analytics_service.dart` if there is a mobile-only legacy name to retain.
6. **Update this doc.** New row in §2, new event in §5.1 if applicable, new mobile↔web call site in §5.4.

---

## 8. Where the dashboard reads from

`https://dashboard.cartha.com/analytics/` consumes `/_admin/metrics/website/overview` on `mobile-api-service-go`. That handler (`internal/handlers/website_overview_handler.go`) queries Mixpanel's Export API for the events in §5.1, splits by `platform` super-property, and returns:

- `overview` totals
- `by_platform` totals (per-card split: web vs ios vs android)
- `time_series` (daily rollup)
- `funnels.{website,download,cob}`
- `top_pages`, `top_clicks`, `cob_actions`, `cob_tools`, `cob_translations`, `cob_surfaces`
- `website_platforms`, `device_types`

The dashboard exposes a platform pill (All / Web / iOS / Android) that re-issues the request with `?platform=…`.
