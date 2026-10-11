export function invitationCode(url:string, origin:string):string|null {
  try {
    const parsed=new URL(url);
    const allowed=(parsed.origin===origin&&parsed.pathname==='/join') || (parsed.protocol==='conditionalok:'&&parsed.hostname==='join');
    const code=parsed.searchParams.get('code')?.toUpperCase();
    return allowed && code && /^[A-Z2-9]{8}$/.test(code) ? code : null;
  } catch {return null;}
}
