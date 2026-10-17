"""Synthetic checks: resume in temp, promote finished pages, never compile."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import pymupdf
import book_tools as bt
import book_sequence as seq


class SequenceTests(unittest.TestCase):
    def test_resume_and_finished_pages(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();pdf=root/'tie/books/csee/biology/Biology_Form-two.pdf';pdf.parent.mkdir(parents=True)
            source=pymupdf.open()
            for _ in range(3):source.new_page(width=300,height=400)
            source.save(pdf);source.close()
            with contextlib.redirect_stdout(io.StringIO()):
                bt.session(SimpleNamespace(root=str(root),level='csee',subject='biology',form='4m2',pages='1-3',prep=True,dpi=72))
            subject=root/'tie/output/csee/biology';book=next((subject/'temp').glob('*__pages-*.json'))
            self.assertFalse((subject/'form two').exists())
            self.assertEqual([p.name for p in (root/'pages/books').rglob('*.png')],['page-0001.png'])
            args=SimpleNamespace(book=str(book),root=str(root),prep=False)
            def advance():
                output=io.StringIO()
                with contextlib.redirect_stdout(output):seq.next_page(args)
                return json.loads(output.getvalue())
            self.assertEqual(advance()['page'],1);self.assertEqual(advance()['page'],1)
            hashes={};session_hash=bt.digest(book)
            for n in range(1,4):
                info=advance();self.assertEqual(info['page'],n)
                working=Path(info['page_json']);self.assertEqual(working.parent,subject/'temp');doc=bt.read(working)
                bt.save(working,doc,backup=True)
                self.assertTrue(list((subject/'temp').glob(working.name+'*.bak')))
                doc['pages'][0].update(state='verified',visual_qa='passed',surfaces=[{'id':f's-p{n:04d}-01','order':0,
                    'bbox_pt':[0,0,300,400],'printed_page':None,'printed_page_status':'not_printed','printed_page_system':'none',
                    'elements':[{'id':f'e-p{n:04d}-01','type':'paragraph','surface_id':f's-p{n:04d}-01','order':0,
                    'bbox_pt':[20,20,200,100],'group_refs':[],'payload':{'text':f'Synthetic page {n}'},'legibility':'clear'}]}])
                doc['status']='complete';bt.fill(doc);doc['stats']=bt.stats(doc)
                self.assertEqual(bt.validate(copy.deepcopy(doc),working,root,check_files=False)[0],[])
                finished=bt.save(working,doc,backup=True)
                self.assertEqual(finished,seq.page_path(book,n));self.assertFalse(working.exists())
                self.assertEqual(finished.parent,subject/'form two');hashes[n]=bt.digest(finished)
                self.assertFalse(list(finished.parent.glob('*.bak')))
            self.assertTrue(advance()['all_pages_saved']);self.assertEqual(bt.digest(book),session_hash)
            self.assertFalse(hasattr(seq,'assemble'))
            self.assertEqual(len(list((subject/'form two').glob('*.json'))),3)
            self.assertFalse(list((subject/'form two').glob('*__pages-*.json')))
            for n in hashes:self.assertEqual(bt.digest(seq.page_path(book,n)),hashes[n])


if __name__=='__main__':unittest.main()
