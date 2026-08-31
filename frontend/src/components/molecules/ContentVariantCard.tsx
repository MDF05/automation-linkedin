import React from 'react';
import { clsx } from 'clsx';
import { Button } from '../atoms';

export interface ContentVariant {
  content: string;
  char_count: number;
  hashtags: string[];
}

export interface ContentVariantCardProps {
  variant: ContentVariant;
  index: number;
  selected?: boolean;
  onSelect: (variant: ContentVariant) => void;
  onEdit?: (variant: ContentVariant) => void;
}

export const ContentVariantCard: React.FC<ContentVariantCardProps> = ({
  variant,
  index,
  selected,
  onSelect,
  onEdit,
}) => {
  return (
    <div
      className={clsx(
        'rounded-xl border p-4 transition-all cursor-pointer',
        selected
          ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500'
          : 'border-gray-200 bg-white hover:border-gray-300',
      )}
      onClick={() => onSelect(variant)}
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onSelect(variant)}
      aria-selected={selected}
      role="option"
      aria-label={`Variasi ${index + 1}: ${variant.char_count} karakter`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-gray-500">Variasi {index + 1}</span>
        <span className="text-xs text-gray-400">{variant.char_count} karakter</span>
      </div>

      <p className="text-sm text-gray-700 line-clamp-4 whitespace-pre-wrap mb-3">
        {variant.content}
      </p>

      {variant.hashtags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {variant.hashtags.slice(0, 5).map((tag) => (
            <span key={tag} className="text-xs text-blue-600">
              {tag.startsWith('#') ? tag : `#${tag}`}
            </span>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        <Button
          variant="primary"
          size="sm"
          onClick={(e) => { e.stopPropagation(); onSelect(variant); }}
        >
          {selected ? 'Dipilih' : 'Pilih'}
        </Button>
        {onEdit && (
          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => { e.stopPropagation(); onEdit(variant); }}
          >
            Edit
          </Button>
        )}
      </div>
    </div>
  );
};
