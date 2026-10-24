"""Meaningful regression checks for the supplied transcript import."""
import json
from pathlib import Path
import tempfile
import unittest
from import_book_text import ROOT, tokens, normalize, list_items, table_rows, toc_entries

class TranscriptImportTests(unittest.TestCase):
    def test_inline_markers_and_underscore_end(self):
        seq=list(tokens('[PDF_PAGE 1] [PRINTED_PAGE ii]\n[BEGIN EXERCISE label="Exercise 1"] [QUESTION label="1."] Why?\n[END_EXERCISE]\n[END_PAGE]'))
        self.assertEqual([t[0] for t in seq],['PDF_PAGE','PRINTED_PAGE','BEGIN','QUESTION','END_EXERCISE','END_PAGE'])
        self.assertEqual(seq[3][2],'Why?')

    def test_flattened_list_does_not_split_references(self):
        items=list_items('(i) Do this. (ii) Repeat steps (i) to (ii) for a root.','roman')
        self.assertEqual(len(items),2)
        self.assertIn('steps (i) to (ii)',items[1]['text'])

    def test_math_is_wrapped_once(self):
        self.assertEqual(normalize(r'Use \ce{CO2} and \(\ce{K+}\).'),r'Use \(\ce{CO2}\) and \(\ce{K+}\).')

    def test_flattened_contents(self):
        self.assertEqual(toc_entries('Preface\tiii Chapter One: A\t1 A subsection\t2'),[{'text':'Preface','page_ref_printed':'iii'},{'text':'Chapter One: A','page_ref_printed':'1'},{'text':'A subsection','page_ref_printed':'2'}])

    def test_imported_documents_and_lossless_table_boundaries(self):
        files=sorted((ROOT/'tie/output/acsee/biology/form six').glob('*.json'))
        self.assertEqual(len(files),40)
        registry=json.loads((ROOT/'skills/books_extraction/references/content-types.json').read_text())
        for n,p in enumerate(files,1):
            d=json.loads(p.read_text());self.assertEqual(d['pages'][0]['pdf_page'],n)
            self.assertEqual(d['status'],'partial');self.assertIsNone(d['source']['sha256'])
            self.assertEqual(d['pages'][0]['visual_qa'],'pending')
            elements=d['pages'][0]['surfaces'][0]['elements'];ids={e['id'] for e in elements}
            self.assertEqual(len(ids),len(elements))
            for i,e in enumerate(elements):
                self.assertEqual(e['order'],i);self.assertIsNone(e['bbox_pt'])
                fields=registry['types'][e['type']]
                for key in fields['required']:self.assertIn(key,e['payload'])
                allowed=set(fields['required'])|set(fields['optional'])|set(registry['common_optional'])
                self.assertFalse(set(e['payload'])-allowed)
                if e['type']=='table':
                    self.assertTrue(all(len(row)==e['payload']['columns'] for row in e['payload']['rows']))
                if e['type']=='caption':self.assertTrue(set(e['payload']['target_refs'])<=ids)
            for g in d['groups']:
                self.assertTrue(set(g['element_refs'])<=ids)
                for eid in g['element_refs']:self.assertIn(g['id'],next(e for e in elements if e['id']==eid)['group_refs'])
            for f in d['figures']:
                self.assertEqual(f['asset_status'],'pending');self.assertIsNone(f['file'])
        first=(ROOT/'tie/output/acsee/biology/temp/text-import/pages-0001-0020.txt').read_text()
        for kind,attrs,raw in tokens(first):
            if kind=='TABLE':
                rows,ambiguous=table_rows(raw,2)
                self.assertTrue(ambiguous);self.assertEqual(len(rows),6)
                self.assertEqual(' '.join(v for row in rows for v in row),normalize(raw.replace('\t',' ')))
        report=json.loads((ROOT/'tie/output/acsee/biology/temp/text-import/import-report.json').read_text())
        self.assertEqual(report['input_blocks'],report['converted_blocks'])

if __name__=='__main__':unittest.main()
