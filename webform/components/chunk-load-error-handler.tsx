'use client'
import { useEffect } from 'react'
export function ChunkLoadErrorHandler(){useEffect(()=>{const handler=(event:ErrorEvent)=>{if(event.error?.name==='ChunkLoadError'||event.error?.message?.includes('Loading chunk')){event.preventDefault();window.location.reload()}};window.addEventListener('error',handler);return()=>window.removeEventListener('error',handler)},[]);return null}
