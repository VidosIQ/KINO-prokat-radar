"""Build the page and Excel from the last verified snapshot without network calls."""
import json
from refresh import ROOT,export_excel
snapshot=json.loads((ROOT/'data/snapshot.json').read_text())
export_excel(snapshot)
(ROOT/'site/data.js').write_text('window.CINEMA_DATA='+json.dumps(snapshot,ensure_ascii=False).replace('<','\\u003c')+';\n')
print('Built page and Excel from verified snapshot')
