/**
 * Park bootstrap (S-5) — side-effect registrations, imported once at app
 * boot (App.tsx), before any park tablet mounts. Mirrors the
 * `register.ts` convention used by scheduling-focus + quote-focus.
 *
 * Registers: the act-type declarations (via import side effect), the three
 * tablet widget renderers (via their module side effects), and the
 * intent-shaped command-bar summon actions.
 */

import { registerActions } from "@/services/actions/registry"

import "./park-act-registry"
import "./tablets/ReplyDmTablet"
import "./tablets/AddNoteTablet"
import "./tablets/StartQuoteTablet"
import { parkSummonActions } from "./park-actions"

registerActions(parkSummonActions)
