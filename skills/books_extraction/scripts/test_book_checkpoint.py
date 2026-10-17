"""Synthetic checks: checkpoint --verified promotes a finished page in one step."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import pymupdf
import book_tools as bt
import book_sequence as seq


class CheckpointTests(unittest.TestCase):
    def test_verified_promotes_in_one_step(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();pdf=root/'tie/books/csee/biology/Biology_Form-two.pdf';pdf.parent.mkdir(parents=True)
            source=pymupdf.open();source.new_page(width=300,height=400);source.save(pdf);source.close()
            with contextlib.redirect_stdout(io.StringIO()):
                bt.session(SimpleNamespace(root=str(root),level='csee',subject='biology',form='4m2',pages='1-1',prep=False,dpi=72))
            subject=root/'tie/output/csee/biology';book=next((subject/'temp').glob('*__pages-*.json'))
            out=io.StringIO()
            with contextlib.redirect_stdout(out):
                seq.next_page(SimpleNamespace(book=str(book),root=str(root),prep=False))
            info=json.loads(out.getvalue())
            working=Path(info['page_json']);doc=bt.read(working)
            doc['pages'][0].update(state='transcribed',visual_qa='pending',surfaces=[{'id':'s-p0001-01','order':0,
                'bbox_pt':[0,0,300,400],'printed_page':None,'printed_page_status':'not_printed','printed_page_system':'none',
                'elements':[{'id':'e-p0001-01','type':'paragraph','surface_id':'s-p0001-01','order':0,
                'bbox_pt':[20,20,200,100],'group_refs':[],'payload':{'text':'Synthetic page 1'},'legibility':'clear'}]}])
            bt.save(working,doc)
            # Without --verified the page stays in temp.
            old=sys.argv;sys.argv=['book_tools.py','checkpoint','--book',str(working),'--root',str(root)]
            out=io.StringIO()
            try:
                with contextlib.redirect_stdout(out):bt.main()
            finally:sys.argv=old
            self.assertEqual(json.loads(out.getvalue())['errors'],[])
            self.assertTrue(working.exists());self.assertFalse(seq.page_path(book,1).exists())
            # With --verified it is promoted in one step.
            sys.argv=['book_tools.py','checkpoint','--book',str(working),'--root',str(root),'--verified']
            out=io.StringIO()
            try:
                with contextlib.redirect_stdout(out):bt.main()
            finally:sys.argv=old
            result=json.loads(out.getvalue())
            self.assertEqual(result['errors'],[])
            finished=seq.page_path(book,1)
            self.assertEqual(Path(result['book']).resolve(),finished.resolve())
            self.assertTrue(finished.exists());self.assertFalse(working.exists())
            saved=bt.read(finished)
            self.assertEqual(saved['status'],'complete')
            self.assertEqual(saved['pages'][0]['state'],'verified')
            self.assertEqual(saved['pages'][0]['visual_qa'],'passed')


if __name__=='__main__':unittest.main()
