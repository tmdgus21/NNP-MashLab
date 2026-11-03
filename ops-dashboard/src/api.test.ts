// @vitest-environment jsdom
import {afterEach,it,expect,vi} from 'vitest';
import {api} from './api';
afterEach(()=>vi.unstubAllGlobals());
it('sends session cookies, CSRF and idempotency without persisted tokens',async()=>{
 const fetcher=vi.fn().mockResolvedValue({ok:true,json:async()=>({saved:true})});vi.stubGlobal('fetch',fetcher);
 await api('/rooms/id/actions',{action:'extend'},'csrf','key');
 expect(fetcher).toHaveBeenCalledWith('/admin-api/rooms/id/actions',expect.objectContaining({credentials:'same-origin',cache:'no-store',headers:expect.objectContaining({'X-CSRF-Token':'csrf','Idempotency-Key':'key'})}));
 expect(localStorage.length).toBe(0);
});
it('rejects server errors without a fallback success',async()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:409,json:async()=>({detail:'다시 조회하세요'})}));await expect(api('/rooms/id')).rejects.toThrow('다시 조회하세요')});
it('invalidates the UI session on protected API 401',async()=>{const listener=vi.fn();window.addEventListener('admin-session-expired',listener);vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:401,json:async()=>({detail:'로그인 필요'})}));await expect(api('/rooms')).rejects.toThrow();expect(listener).toHaveBeenCalledOnce();window.removeEventListener('admin-session-expired',listener)});
