import { forwardRef } from "react";
import { cn } from "@/lib/utils/cn";

/**
 * A flat input. Single underline border by default; lights up gold on focus.
 * No filled background — the input is part of the page's typographic flow.
 */
export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...rest },
  ref
) {
  return (
    <input
      ref={ref}
      className={cn(
        "w-full bg-transparent text-paper placeholder:text-paper-fade",
        "border-b border-rule focus:border-gold focus:outline-none",
        "h-9 px-0 text-[14px] font-mono tracking-tight",
        className
      )}
      {...rest}
    />
  );
});
