import main
from fastapi.routing import APIRoute

app = main.app
paths = []
for r in app.routes:
    if isinstance(r, APIRoute):
        paths.append(r.path)
print('\n'.join(sorted(paths)))
