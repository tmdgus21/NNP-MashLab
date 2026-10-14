export function invitationCode(url:string, origin:string):string|null {
  try {
    // React Native's URL implementation does not implement every URLSearchParams API.
    // Accept only the two exact entry points, then decode a single code parameter.
    const [base,query,...extra]=url.split('#')[0].split('?');
    if(extra.length || !query || (base!==`${origin}/join` && base!=='conditionalok://join')) {return null;}
    const codes=query.split('&').map(pair=>pair.split('=')).filter(([key])=>decodeURIComponent(key)==='code');
    if(codes.length!==1 || codes[0].length!==2) {return null;}
    const code=decodeURIComponent(codes[0][1]).toUpperCase();
    return /^[A-Z2-9]{8}$/.test(code) ? code : null;
  } catch {return null;}
}
