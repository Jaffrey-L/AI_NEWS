"""Create a self-contained HTML review preview from the static site assets."""

from pathlib import Path

root = Path(__file__).resolve().parents[1]
html = (root / "index.html").read_text(encoding="utf-8")
css = (root / "workspace.css").read_text(encoding="utf-8")
data = (root / "data" / "site-payload.js").read_text(encoding="utf-8")
app = (root / "app.js").read_text(encoding="utf-8")
safe_data = data.replace("</script", "<\\/script")
html = html.replace('<link rel="stylesheet" href="./workspace.css?v=3">', f"<style>\n{css}\n</style>")
html = html.replace('<script src="./data/site-payload.js?v=3"></script>', f"<script>\n{safe_data}\n</script>")
html = html.replace('<script src="./app.js?v=3" defer></script>', f"<script>\n{app}\n</script>")
target = root / "preview.html"
target.write_text(html, encoding="utf-8")
print(f"preview={target} bytes={target.stat().st_size}")
