import React from 'react';
import { clsx } from 'clsx';

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: string;
  maxLength?: number;
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ error, maxLength, className, value, ...rest }, ref) => {
    const currentLength = typeof value === 'string' ? value.length : 0;

    return (
      <div className="relative">
        <textarea
          ref={ref}
          {...rest}
          value={value}
          maxLength={maxLength}
          aria-invalid={!!error}
          className={clsx(
            'block w-full rounded-md border bg-white px-3 py-2 text-sm',
            'placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-offset-0',
            'disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-500',
            maxLength ? 'pb-6' : '',
            error
              ? 'border-red-400 focus:border-red-400 focus:ring-red-400'
              : 'border-gray-300 focus:border-blue-500 focus:ring-blue-500',
            className,
          )}
        />
        {maxLength !== undefined && (
          <span className="pointer-events-none absolute bottom-2 right-3 text-xs text-gray-400">
            {currentLength}/{maxLength}
          </span>
        )}
      </div>
    );
  },
);

Textarea.displayName = 'Textarea';
