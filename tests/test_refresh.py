import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import refresh
class Reports(unittest.TestCase):
    def test_periods_selected_independently_and_future_excluded(self):
        body=''.join(f'<a href="/documents/download/{i}/">Аналитический отчет, {kind} {i} ({period})</a>' for i,kind,period in [(1,'неделя','12.11-18.11.2026'),(2,'уикенд','12.11-15.11.2026'),(3,'уикенд','19.11-22.11.2026'),(4,'неделя','19.11-25.11.2026')])
        with patch.object(refresh,'TODAY','2026-11-24'):
            result=refresh.reports_from_html(body)
        self.assertEqual(result['week']['end'],'2026-11-18');self.assertEqual(result['weekend']['end'],'2026-11-22')
    def test_wrong_eais_order_rejected(self):
        import json
        rows=[dict(id=i,title=str(i),sum=i,quantity=1) for i in range(20)]
        with patch.object(refresh,'fetch',return_value=json.dumps(rows).encode()):
            with self.assertRaises(ValueError):refresh.eais_records(dict(start='2026-11-12',end='2026-11-15'))
    def test_unrecognized_index_rejected(self):
        with self.assertRaises(ValueError):refresh.reports_from_html('<html>Challenge</html>')
if __name__=='__main__':unittest.main()
