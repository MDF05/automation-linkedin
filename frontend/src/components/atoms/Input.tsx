import React from 'react';
import { clsx } from 'clsx';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ error, className, ...rest }, ref) => {
    return (
      <input
        ref={ref}
        {...rest}
        aria-invalid={!!error}
        className={clsx(
          'block w-full rounded-md border bg-white px-3 py-2 text-sm',
          'placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-offset-0',
          'disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-500',
          error
            ? 'border-red-400 focus:border-red-400 focus:ring-red-400'
            : 'border-gray-300 focus:border-blue-500 focus:ring-blue-500',
          className,
        )}
      />
    );
  },
);

Input.displayName = 'Input';
