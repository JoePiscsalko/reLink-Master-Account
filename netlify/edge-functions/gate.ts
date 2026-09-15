import type { Config, Context } from "@netlify/edge-functions";

// Shared-password gate for the whole site, including /data/*.json.
// Password lives in the ACCESS_PASSWORD environment variable in Netlify.
// If that variable is not set, the site is blocked — this never fails open.

const COOKIE = "am_session";
const MAX_AGE = 60 * 60 * 24; // 24 hours

async function sha256(s: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// length-independent comparison, so timing doesn't leak the token
function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function page(msg: string, status = 200): Response {
  return new Response(
    `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>reLink360 Account Master</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
         background:#F7F3EA; font-family:'Source Sans 3',-apple-system,Arial,sans-serif; color:#2E2622; padding:24px; }
  .card { background:#FFFFFF; border:1px solid #E4DED0; padding:34px 32px; width:100%; max-width:400px; }
  .eyebrow { font-size:11px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#036E78; margin-bottom:8px; }
  h1 { margin:0 0 6px; font-size:22px; font-weight:600; }
  p { margin:0 0 20px; font-size:14px; color:#6B615C; line-height:1.55; }
  label { display:block; font-size:11px; font-weight:700; letter-spacing:0.09em;
          text-transform:uppercase; color:#4A3E3A; margin-bottom:6px; }
  input { width:100%; padding:11px 13px; border:1px solid #E4DED0; background:#FFFFFF;
          font-family:inherit; font-size:15px; color:#2E2622; }
  input:focus { outline:2px solid #036E78; outline-offset:-1px; }
  button { width:100%; margin-top:14px; padding:12px; border:none; background:#036E78; color:#FFFFFF;
           font-family:inherit; font-size:14px; font-weight:600; cursor:pointer; }
  button:hover { background:#02565E; }
  .err { margin:0 0 16px; padding:10px 12px; background:#FDF1E8; border-left:3px solid #D46A1E;
         font-size:13px; color:#8A4413; }
  .foot { margin:18px 0 0; font-size:11.5px; color:#9A8F88; }
</style></head><body>
<div class="card">
  <div class="eyebrow">reLink Medical \u00b7 internal</div>
  <h1>Account Master</h1>
  <p>This dashboard contains partner account and escrow data. Enter the access password to continue.</p>
  ${msg}
</div></body></html>`,
    { status, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } },
  );
}

const FORM = (error?: string) => `
  ${error ? `<div class="err">${error}</div>` : ""}
  <form method="POST" action="/">
    <label for="p">Password</label>
    <input id="p" name="password" type="password" autocomplete="current-password" autofocus required>
    <button type="submit">Open dashboard</button>
  </form>
  <p class="foot">Sessions last 24 hours. Visit /logout to sign out.</p>`;

export default async (request: Request, context: Context) => {
  const secret = Deno.env.get("ACCESS_PASSWORD");

  // never fail open
  if (!secret) {
    return page(
      `<div class="err">This site is not yet configured. An administrator needs to set the
       <code>ACCESS_PASSWORD</code> environment variable in Netlify.</div>`,
      503,
    );
  }

  const expected = await sha256(secret);
  const url = new URL(request.url);

  // sign out
  if (url.pathname === "/logout") {
    const res = page(`<div class="err">You have been signed out.</div>${FORM()}`);
    res.headers.append(
      "set-cookie",
      `${COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0`,
    );
    return res;
  }

  // password submission
  if (request.method === "POST") {
    const form = await request.formData().catch(() => null);
    const given = String(form?.get("password") ?? "");
    if (given && safeEqual(await sha256(given), expected)) {
      const res = new Response(null, { status: 303, headers: { location: "/" } });
      res.headers.append(
        "set-cookie",
        `${COOKIE}=${expected}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=${MAX_AGE}`,
      );
      return res;
    }
    return page(FORM("That password is not correct."), 401);
  }

  // already signed in
  const session = context.cookies.get(COOKIE);
  if (session && safeEqual(session, expected)) return context.next();

  return page(FORM(), 401);
};

export const config: Config = {
  // everything, including /data/*.json and report.html
  path: "/*",
};
