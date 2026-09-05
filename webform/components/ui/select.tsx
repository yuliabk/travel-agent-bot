'use client'
import * as React from 'react'
import * as S from '@radix-ui/react-select'
import { Check,ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
const Select=S.Root,SelectValue=S.Value,SelectGroup=S.Group
const SelectTrigger=React.forwardRef<React.ElementRef<typeof S.Trigger>,React.ComponentPropsWithoutRef<typeof S.Trigger>>(({className,children,...props},ref)=><S.Trigger ref={ref} className={cn('flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring',className)} {...props}>{children}<S.Icon asChild><ChevronDown className="h-4 w-4 opacity-50"/></S.Icon></S.Trigger>);SelectTrigger.displayName=S.Trigger.displayName
const SelectContent=React.forwardRef<React.ElementRef<typeof S.Content>,React.ComponentPropsWithoutRef<typeof S.Content>>(({className,children,position='popper',...props},ref)=><S.Portal><S.Content ref={ref} className={cn('relative z-50 min-w-[8rem] overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md',className)} position={position} {...props}><S.Viewport className="p-1">{children}</S.Viewport></S.Content></S.Portal>);SelectContent.displayName=S.Content.displayName
const SelectItem=React.forwardRef<React.ElementRef<typeof S.Item>,React.ComponentPropsWithoutRef<typeof S.Item>>(({className,children,...props},ref)=><S.Item ref={ref} className={cn('relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none focus:bg-accent',className)} {...props}><span className="absolute left-2"><S.ItemIndicator><Check className="h-4 w-4"/></S.ItemIndicator></span><S.ItemText>{children}</S.ItemText></S.Item>);SelectItem.displayName=S.Item.displayName
export{Select,SelectValue,SelectGroup,SelectTrigger,SelectContent,SelectItem}
