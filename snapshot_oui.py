"""Helper for manually parsing the OUI table.

Trying to GET https://standards-oui.ieee.org using `requests` returns HTTP "I'm a teapot",
so I don't think they want to be scraped. `curl`ing works but might break in the future,
so this function is intended to be called manually from a REPL to generate a snapshot:

```shell
$ python3 snapshot_oui.py
```
"""

import pathlib
import subprocess
import json
import re

OUI_PATH = pathlib.Path("oui_snapshot.json")

text = subprocess.check_output(["curl", "https://standards-oui.ieee.org"])

# Looking for lines like:
# 00-62-0B   (hex)		Broadcom Limited
OUI_REGEX = re.compile(
    r"^((?:[0-9a-zA-Z]{2}-)*[0-9a-zA-Z]{2})\s*\(hex\)\s*(.*)", flags=re.MULTILINE
)
result = dict[str, str]()
for match in OUI_REGEX.finditer(text.decode()):
    result[match[1].strip().replace("-", ":")] = match[2].strip()
OUI_PATH.write_text(json.dumps(result))
