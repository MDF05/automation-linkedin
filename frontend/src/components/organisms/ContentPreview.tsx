import React from 'react';
import { clsx } from 'clsx';
import { Badge, Button } from '../atoms';

const MAX_CHARS = 3000;

export interface ContentPreviewProps {
  content: string;
  imageUrl?: string | null;
  charCount?: number;
  onPost?: () => void;
  onSaveDraft?: () => void;
  onSplitThread?: () => void;
  loading?: boolean;
}

export const ContentPreview: React.FC<ContentPreviewProps> = ({
  content,
  imageUrl,
  charCount,
  onPost,
  onSaveDraft,
  onSplitThread,
  loading,
}) => {
  const chars = charCount ?? content.length;
  const overLimit = chars > MAX_CHARS;

  return (
    <div className="flex flex-col gap-4">
      {/* LinkedIn-style preview card */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-3 mb-4">
          {/* Avatar placeholder */}
          <div
            className="h-10 w-10 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-bold"
            aria-hidden="true"
          >
            U
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-800">Pengguna</p>
            <p className="text-xs text-gray-400">Baru saja</p>
          </div>
        </div>

        {/* Content */}
        <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
          {content || <span className="text-gray-300">Preview konten akan muncul di sini...</span>}
        </p>

        {/* Image preview */}
        {imageUrl && (
          <div className="mt-3 rounded-lg overflow-hidden border border-gray-100">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={imageUrl} alt="Gambar konten" className="w-full object-cover max-h-64" />
          </div>
        )}
      </div>

      {/* Character count */}
      <div className="flex items-center justify-between">
        <span
          className={clsx('text-sm', overLimit ? 'text-red-600 font-medium' : 'text-gray-500')}
          aria-live="polite"
        >
          {chars.toLocaleString()} / {MAX_CHARS.toLocaleString()} karakter
        </span>
        {overLimit && (
          <Badge label="Melebihi batas" color="red" />
        )}
      </div>

      {/* Over-limit warning */}
      {overLimit && onSplitThread && (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-3 flex items-center justify-between">
          <p className="text-sm text-yellow-800">
            Konten melebihi 3.000 karakter. Pecah menjadi thread?
          </p>
          <Button variant="secondary" size="sm" onClick={onSplitThread}>
            Pecah Thread
          </Button>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        {onPost && (
          <Button
            variant="primary"
            onClick={onPost}
            loading={loading}
            disabled={loading || !content}
          >
            Post Sekarang
          </Button>
        )}
        {onSaveDraft && (
          <Button
            variant="secondary"
            onClick={onSaveDraft}
            disabled={loading || !content}
          >
            Simpan Draft
          </Button>
        )}
      </div>
    </div>
  );
};
