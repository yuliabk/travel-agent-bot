import * as React from 'react'
import { cva,type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'
const inputVariants=cva('flex w-full rounded-lg border bg-background text-sm placeholder:text-muted-foreground focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50',{variants:{variant:{default:'border-input focus-visible:ring-2 focus-visible:ring-ring',error:'border-destructive focus-visible:ring-2 focus-visible:ring-destructive',success:'border-emerald-500',ghost:'border-transparent bg-muted/50'},size:{default:'h-10 px-3 py-2',sm:'h-8 px-2.5 py-1 text-xs',lg:'h-12 px-4 py-3 text-base'}},defaultVariants:{variant:'default',size:'default'}})
export interface InputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>,'size'>,VariantProps<typeof inputVariants>{}
const Input=React.forwardRef<HTMLInputElement,InputProps>(({className,type,variant,size,...props},ref)=><input type={type} className={cn(inputVariants({variant,size,className}))} ref={ref} {...props}/>);Input.displayName='Input';export{Input,inputVariants}
