import React from 'react';

export interface StudioLayoutProps {
  /** Left column: form inputs */
  form: React.ReactNode;
  /** Right column: content preview */
  preview: React.ReactNode;
}

/**
 * Two-column layout for the Studio page.
 * Left: form inputs. Right: LinkedIn-style content preview.
 *
 * Requirements: 2.1–2.11, 3.1–3.7, 10.1–10.6
 */
export const StudioLayout: React.FC<StudioLayoutProps> = ({ form, preview }) => {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:items-start">
      {/* Left — Form */}
      <section aria-label="Form input konten">
        {form}
      </section>

      {/* Right — Preview */}
      <section
        aria-label="Preview konten LinkedIn"
        className="lg:sticky lg:top-6"
      >
        {preview}
      </section>
    </div>
  );
};
