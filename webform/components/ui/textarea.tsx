import * as React from 'react'
import { cva,type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'
const textareaVariants=cva('flex min-h-[80px] w-full rounded-lg border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none disabled:opacity-50',{variants:{variant:{default:'border-input focus-visible:ring-2 focus-visible:ring-ring',error:'border-destructive focus-visible:ring-2 focus-visible:ring-destructive',success:'border-emerald-500',ghost:'border-transparent bg-muted/50'}},defaultVariants:{variant:'default'}})
export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement>,VariantProps<typeof textareaVariants>{}
const Textarea=React.forwardRef<HTMLTextAreaElement,TextareaProps>(({className,variant,...props},ref)=><textarea className={cn(textareaVariants({variant,className}))} ref={ref} {...props}/>);Textarea.displayName='Textarea';export{Textarea,textareaVariants}
