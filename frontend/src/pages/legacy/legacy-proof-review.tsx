// DEPRECATED: This page is superseded by Legacy Studio (library + compositor).
// Route /legacy/proof/:orderId now redirects to the Legacy Studio library.
// Kept for backward compatibility — existing bookmarks and links will redirect.

import { Navigate } from "react-router-dom"

export default function LegacyProofReviewPage() {
  return <Navigate to="/legacy/library" replace />
}
