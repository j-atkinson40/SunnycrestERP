/**
 * Arc 4b.1b — SuggestionDropdown public surface.
 *
 * Ninth shared authoring component primitive. Imported by
 * DocumentsTab slash command summoning (Arc 4b.1b) + future
 * Workflows tab + Focus compositions tab inline-summon UX.
 *
 * Arc 4b.2b — `getCaretCoordinates` companion utility (settled
 * Q-ARC4B2-4 outcome b). Co-located here because every textarea /
 * input consumer of SuggestionDropdown needs caret-relative
 * positioning; centralizing the helper prevents drift across
 * consumers (slash command at template-edit level + mention picker
 * at block-content level + future inline-summon UX).
 */
export {
  SuggestionDropdown,
  handleSuggestionKeyDown,
} from "./SuggestionDropdown"
export type { SuggestionDropdownProps } from "./SuggestionDropdown"
export { getCaretCoordinates } from "./getCaretCoordinates"
export type { CaretCoordinates } from "./getCaretCoordinates"
export { MentionPicker } from "./MentionPicker"
export type { MentionPickerProps } from "./MentionPicker"
export { useMentionPicker } from "./useMentionPicker"
export type {
  MentionPickerState,
  PickedMentionCandidate,
  UseMentionPickerOptions,
  UseMentionPickerResult,
} from "./useMentionPicker"
