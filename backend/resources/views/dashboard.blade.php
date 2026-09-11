<!doctype html>
<html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Certify — Laravel backend</title>
        <style>body{font-family:system-ui,sans-serif;margin:0;background:#f7f9fc;color:#18212f}.wrap{max-width:760px;margin:11vh auto;padding:32px}.card{background:white;border:1px solid #e8edf3;border-radius:12px;padding:28px;box-shadow:0 2px 8px #14213d0a}h1{margin:0 0 8px}p{color:#66758a;line-height:1.6}code{background:#edf3fb;padding:3px 6px;border-radius:4px;color:#1e4e94}.tag{display:inline-block;background:#e1f4ec;color:#15835e;border-radius:20px;padding:6px 10px;font-size:12px;font-weight:700}.routes{margin-top:20px;border-top:1px solid #e8edf3;padding-top:14px}.routes li{margin:8px 0}</style>
    </head>
    <body>
        <main class="wrap"><section class="card"><span class="tag">LARAVEL BACKEND READY</span><h1>Certify API is running</h1><p>The existing HTML/CSS/JavaScript prototype remains in the workspace. This Laravel app is now its database-backed backend for certificates, membership data, validity dates, custom fields, layouts, and audit events.</p><div class="routes"><strong>Available API endpoints</strong><ul><li><code>GET {{ $apiBase }}/certificates</code></li><li><code>POST {{ $apiBase }}/certificates</code></li><li><code>GET {{ $apiBase }}/certificates/{publicId}</code></li><li><code>POST {{ $apiBase }}/certificates/{publicId}/revoke</code></li></ul></div></section></main>
    </body>
</html>
