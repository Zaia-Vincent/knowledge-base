"""Local HTTP service with deterministic cookie-overlay fixtures for capture tests."""

from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from typing import Iterator


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def _write_fixture_pages(site_root: Path) -> None:
    (site_root / "iframe-overlay.html").write_text(
        """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Iframe Overlay Fixture</title>
  <style>
    html, body { margin: 0; height: 100%; background: #ffffff; }
    iframe { position: fixed; inset: 0; border: 0; width: 100vw; height: 100vh; }
  </style>
</head>
<body>
  <iframe src="/iframe-content.html" title="content"></iframe>
</body>
</html>
        """.strip(),
        encoding="utf-8",
    )

    (site_root / "iframe-content.html").write_text(
        """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Iframe Content Fixture</title>
  <style>
    html, body { margin: 0; min-height: 2000px; background: rgb(52, 165, 98); color: #ffffff; }
    main { padding: 40px; font: 700 24px/1.3 Arial, sans-serif; }
    #privacy-layer {
      position: fixed;
      inset: 0;
      z-index: 2147483646;
      background: rgb(20, 20, 20);
      color: #ffffff;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      gap: 16px;
      font: 500 18px/1.4 Arial, sans-serif;
    }
    #frame-accept { padding: 10px 16px; border: 0; cursor: pointer; }
  </style>
</head>
<body>
  <main>REAL WEBSITE CONTENT</main>
  <div id="privacy-layer">
    <p>This website uses cookies. See our cookie policy.</p>
    <button id="frame-accept">Accept all</button>
  </div>
  <script>
    document.getElementById("frame-accept").addEventListener("click", () => {
      document.getElementById("privacy-layer").remove();
    });
  </script>
</body>
</html>
        """.strip(),
        encoding="utf-8",
    )

    (site_root / "shadow-overlay.html").write_text(
        """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Shadow Overlay Fixture</title>
  <style>
    html, body { margin: 0; min-height: 2200px; background: rgb(40, 128, 220); color: #ffffff; }
    main { padding: 48px; font: 700 24px/1.3 Arial, sans-serif; }
  </style>
</head>
<body>
  <main>REAL WEBSITE CONTENT</main>
  <shadow-cookie-wall></shadow-cookie-wall>
  <script>
    class ShadowCookieWall extends HTMLElement {
      connectedCallback() {
        const root = this.attachShadow({ mode: "open" });
        root.innerHTML = `
          <style>
            .veil {
              position: fixed;
              inset: 0;
              z-index: 2147483647;
              background: rgb(16, 16, 16);
              color: #ffffff;
              display: flex;
              align-items: center;
              justify-content: center;
              text-align: center;
              padding: 24px;
              font: 500 18px/1.4 Arial, sans-serif;
            }
          </style>
          <div class="veil">
            We use cookies for analytics. Read the cookie policy before continuing.
          </div>
        `;
      }
    }
    customElements.define("shadow-cookie-wall", ShadowCookieWall);
  </script>
</body>
</html>
        """.strip(),
        encoding="utf-8",
    )

    (site_root / "policy-redirect-root.html").write_text(
        """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Policy Redirect Root Fixture</title>
  <style>
    html, body { margin: 0; min-height: 1600px; background: rgb(26, 162, 96); color: #ffffff; }
    main { padding: 48px; font: 700 24px/1.3 Arial, sans-serif; }
    #cookie-gate {
      position: fixed;
      inset: 0;
      z-index: 2147483647;
      background: rgba(0,0,0,.9);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-direction: column;
      gap: 12px;
      font: 500 17px/1.4 Arial, sans-serif;
    }
    #cookie-accept-btn { padding: 10px 14px; border: 0; cursor: pointer; }
  </style>
</head>
<body>
  <main>REAL WEBSITE CONTENT</main>
  <div id="cookie-gate">
    <p>This website uses cookies. Accept all cookies to continue.</p>
    <button id="cookie-accept-btn" class="cookie-accept">Accept all cookies</button>
  </div>
  <script>
    document.getElementById("cookie-accept-btn").addEventListener("click", () => {
      window.location.href = "/cookie-policy.html";
    });
  </script>
</body>
</html>
        """.strip(),
        encoding="utf-8",
    )

    (site_root / "cookie-policy.html").write_text(
        """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Cookie Policy Fixture</title>
  <style>
    html, body { margin: 0; min-height: 1200px; background: rgb(22, 22, 22); color: #ffffff; }
    main { padding: 48px; font: 500 18px/1.5 Arial, sans-serif; }
  </style>
</head>
<body>
  <main>COOKIE POLICY PAGE</main>
</body>
</html>
        """.strip(),
        encoding="utf-8",
    )


@contextmanager
def run_cookie_test_service() -> Iterator[str]:
    """Serve local cookie-overlay fixture pages over HTTP."""
    with TemporaryDirectory(prefix="cookie-test-service-") as tmpdir:
        site_root = Path(tmpdir)
        _write_fixture_pages(site_root)

        handler = partial(_QuietHandler, directory=str(site_root))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            host, port = server.server_address
            yield f"http://{host}:{port}"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
