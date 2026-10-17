"""Isolated behavior checks for the visual transcription writer."""
import contextlib
import copy
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import pymupdf
import book_tools as bt
from book_batch import apply_batch


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);folder=self.root/'tie/books/csee/biology';folder.mkdir(parents=True)
        self.pdf=folder/'Biology_Form-two_fixture.pdf'
        with pymupdf.open() as pdf:
            page=pdf.new_page(width=200,height=300);page.draw_rect(pymupdf.Rect(20,40,80,100));pdf.save(self.pdf)
        args=SimpleNamespace(root=str(self.root),level='csee',subject='biology',form='4m2',pages='1-1',prep=False)
        with contextlib.redirect_stdout(io.StringIO()) as output:bt.session(args)
        self.book=Path(__import__('json').loads(output.getvalue())['book']);self.doc=bt.read(self.book)
        self.batch={'book_id':self.doc['book_id'],'source_sha256':self.doc['source']['sha256'],
            'pages':[{'pdf_page':1,'transcribed':True,'surfaces':[{'printed_page':'1','render_size_px':[400,600],
            'elements':[{'key':'diagram','type':'figure','bbox':[40,80,160,200],'crop':{'kind':'diagram','dpi':72}},
                        {'key':'caption','type':'caption','bbox':[40,210,300,250],'text':'Exact caption','payload':{'target_refs':['@diagram']}},
                        {'key':'number','type':'page_number','bbox':[180,550,220,580],'text':'1'}]}]}],
            'groups':[{'key':'activity','kind':'activity','element_refs':['@diagram','@caption']}]}

    def test_visual_batch_and_full_integrity(self):
        doc,_=apply_batch(self.doc,self.batch,self.root,self.book)
        self.assertEqual(self.doc['pages'][0]['surfaces'],[])
        s=doc['pages'][0]['surfaces'][0];e=s['elements'][0]
        self.assertEqual(e['bbox_pt'],[20,40,80,100])
        self.assertEqual(doc['relations'][0]['to_ref'],e['id'])
        self.assertEqual(e['group_refs'],[doc['groups'][0]['id']])
        self.assertEqual(doc['figures'][0]['pixel_size'],[60,60])
        self.assertEqual(doc['figures'][0]['crop_check'],'pending')
        self.assertEqual(doc['pages'][0]['visual_qa'],'pending')
        self.assertEqual(doc['status'],'partial')
        self.assertEqual(bt.validate(doc,self.book,self.root)[0],[])
        doc['figures'][0]['sha256']='0'*64
        self.assertEqual(bt.validate(doc,self.book,self.root,check_files=False)[0],[])
        self.assertTrue(any('hash mismatch' in e for e in bt.validate(doc,self.book,self.root)[0]))

    def test_scope_identity_and_unknown_types(self):
        for mutate in [lambda b:b.update(source_sha256='wrong'),lambda b:b['pages'][0].update(pdf_page=2),
                       lambda b:b['pages'][0]['surfaces'][0]['elements'][0].update(type='unapproved')]:
            b=copy.deepcopy(self.batch);mutate(b)
            with self.assertRaises(ValueError):apply_batch(self.doc,b,self.root,self.book)
            self.assertEqual(bt.read(self.book),self.doc)

    def test_invalid_grid_reference_and_box(self):
        for spec in [
            {'key':'bad','type':'table','bbox':[20,20,100,100],'payload':{'columns':2,'header_rows':0,'rows':[[{'text':'hole'}]]}},
            {'key':'bad','type':'caption','bbox':[20,20,100,100],'text':'Caption','payload':{'target_refs':['@missing']}},
            {'key':'bad','type':'paragraph','bbox':[0,0,999,999],'text':'Out of page'}]:
            b=copy.deepcopy(self.batch);b['pages'][0]['surfaces'][0]['elements']=[spec]
            b['groups']=[]
            with self.assertRaises(ValueError):apply_batch(self.doc,b,self.root,self.book)

    def test_append_retains_ids_and_rejects_overwrite(self):
        doc,_=apply_batch(self.doc,self.batch,self.root,self.book)
        with self.assertRaises(ValueError):apply_batch(doc,self.batch,self.root,self.book)
        b=copy.deepcopy(self.batch);b['groups']=[]
        b['pages'][0]['surfaces'][0]['elements']=[{'key':'later','type':'paragraph','bbox':[40,300,300,340],'text':'@literal stays literal'}]
        appended,_=apply_batch(doc,b,self.root,self.book)
        self.assertEqual(appended['pages'][0]['surfaces'][0]['elements'][:3],doc['pages'][0]['surfaces'][0]['elements'])
        self.assertEqual(appended['pages'][0]['surfaces'][0]['elements'][-1]['payload']['text'],'@literal stays literal')
        doc['status']='complete'
        with self.assertRaises(ValueError):apply_batch(doc,b,self.root,self.book)


if __name__=='__main__':unittest.main()
