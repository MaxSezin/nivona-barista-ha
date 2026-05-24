/**
 * Shared CSS design tokens for the Melitta panel.
 *
 * Exposes a `css` template (Lit) that defines :host-scoped CSS custom
 * properties. Every component imports `sharedStyles` from lit-base.js
 * (which composes this) so the tokens are uniformly available.
 *
 * Tokens stick to HA theme vars where applicable (--primary-color,
 * --card-background-color, etc.) and only add what HA does not provide
 * (spacing scale, radius, focus ring).
 */

import { css } from "./vendor/lit.js";

export const designTokens = css`
  :host {
    --mb-space-xs: 4px;
    --mb-space-sm: 8px;
    --mb-space-md: 12px;
    --mb-space-lg: 16px;
    --mb-space-xl: 24px;

    --mb-radius-sm: 4px;
    --mb-radius-md: 8px;

    --mb-focus-ring: 0 0 0 2px var(--primary-color);

    --mb-font-size-sm: 12px;
    --mb-font-size-md: 14px;
    --mb-font-size-lg: 16px;
  }
`;
