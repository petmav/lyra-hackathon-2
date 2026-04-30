export const dynamic = "force-static";

const ICON = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" fill="#0e1216"/>
  <rect x="6" y="5" width="7" height="22" fill="#c4a572"/>
  <rect x="16" y="11" width="10" height="2" fill="#f5efe6"/>
  <rect x="16" y="16" width="10" height="2" fill="#f5efe6"/>
  <rect x="16" y="21" width="7" height="2" fill="#f5efe6"/>
</svg>`;

export function GET() {
  return new Response(ICON, {
    headers: {
      "content-type": "image/svg+xml",
      "cache-control": "public, max-age=31536000, immutable"
    }
  });
}
