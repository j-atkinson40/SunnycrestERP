/**
 * Phase R-6.2b — IntakeFieldDispatcher.
 *
 * Routes IntakeFieldConfig.type → the right primitive. Unknown types
 * log warn + skip render (forward-compatible — backend can ship new
 * field types ahead of frontend support).
 *
 * file_upload is intentionally NOT dispatched here — file uploads
 * have a different shape (upload-progress state, drop zone) and live
 * on PortalFileUploadPage where the orchestrator controls them.
 */

import { DateField } from "./fields/DateField";
import { EmailField } from "./fields/EmailField";
import { PhoneField } from "./fields/PhoneField";
import { SelectField } from "./fields/SelectField";
import { TextField } from "./fields/TextField";
import { TextareaField } from "./fields/TextareaField";
import type { IntakeFieldProps } from "./fields/_shared";

export function IntakeFieldDispatcher(props: IntakeFieldProps) {
  switch (props.config.type) {
    case "text":
      return <TextField {...props} />;
    case "textarea":
      return <TextareaField {...props} />;
    case "email":
      return <EmailField {...props} />;
    case "phone":
      return <PhoneField {...props} />;
    case "date":
      return <DateField {...props} />;
    case "select":
      return <SelectField {...props} />;
    case "file_upload":
      // File upload routes through PortalFileUploadPage which owns
      // the upload-progress + dropzone state — not renderable as a
      // generic dispatch-target.
      return null;
    default:
      // Forward-compat: backend can ship new field types ahead of
      // frontend; log warn + skip render.
      // eslint-disable-next-line no-console
      console.warn(
        `[intake] Unknown field type "${
          (props.config as { type?: string }).type
        }"; skipping.`,
      );
      return null;
  }
}
