"""Checks for Physics Form One imported drafts, not PDF accuracy checks."""
import collections
import json
import re
import unittest
from import_physics_form_one_text import ROOT, FOLDER, OUTPUT, repairs, split_labels, table

class PhysicsTextImportTests(unittest.TestCase):
    def test_control_character_repair(self):
        self.assertEqual(repairs('\x0crac{1}{2} \times x \nightarrow y'),r'\frac{1}{2} \times x \rightarrow y')
        self.assertEqual(repairs('An unchanged sentence.'),'An unchanged sentence.')

    def test_nested_item_references_remain_text(self):
        items=split_labels('(i) Cut it.\n(ii) Repeat steps (i) to (iv).','roman')
        self.assertEqual(len(items),2)
        self.assertIn('(i) to (iv)',items[1]['text'])

    def test_table_instructions_stay_outside_grid(self):
        p,tail,issues,_=table('Object\tMass\nRock\t4\n\n3. Compare values.',{'columns':'2','header_rows':'1'})
        self.assertEqual(len(p['rows']),2)
        self.assertEqual(tail,['3. Compare values.'])

    def test_table_retains_empty_leading_cell(self):
        p,_,_,_=table('A\tB\n\tVolume',{'columns':'2','header_rows':'1'})
        self.assertEqual(p['rows'][1][0]['text'],'')
        self.assertEqual(p['rows'][1][1]['text'],'Volume')

    def test_coverage_payloads_references_and_pending_state(self):
        files=sorted(OUTPUT.glob('*.json'));self.assertEqual(len(files),232)
        pages=[];figures=0
        for path in files:
            d=json.loads(path.read_text());page=d['pages'][0];pages.append(page['pdf_page'])
            self.assertEqual(d['status'],'partial');self.assertEqual(page['visual_qa'],'pending')
            self.assertIsNone(d['source']['sha256']);self.assertIsNone(page['width_pt'])
            es=page['surfaces'][0]['elements'];ids={e['id'] for e in es}
            self.assertEqual(len(ids),len(es))
            groups={g['id']:g for g in d['groups']}
            for i,e in enumerate(es):
                self.assertEqual(e['order'],i);self.assertIsNone(e['bbox_pt'])
                r=d['schema']['registry'];definition=r['types'][e['type']]
                self.assertTrue(set(definition['required'])<=e['payload'].keys())
                allowed=set(definition['required'])|set(definition['optional'])|set(r['common_optional'])
                self.assertFalse(set(e['payload'])-allowed)
                for gid in e['group_refs']:self.assertIn(e['id'],groups[gid]['element_refs'])
                if e['type']=='table':self.assertTrue(all(len(row)==e['payload']['columns'] for row in e['payload']['rows']))
                if e['type']=='caption':self.assertTrue(set(e['payload']['target_refs'])<=ids)
                for field in ['text','latex']:
                    self.assertIsNone(re.search('[\x00-\x08\x0b\x0c\x0e-\x1f]',e['payload'].get(field,'')))
            for g in groups.values():
                self.assertTrue(set(g['element_refs'])<=ids)
                if g['parent_ref']:self.assertIn(g['parent_ref'],groups)
            for f in d['figures']:
                self.assertEqual(f['asset_status'],'pending');self.assertIsNone(f['file']);figures+=1
            for rel in d['relations']:
                self.assertIn(rel['from_ref'],ids)
                if rel['resolution']=='resolved':self.assertIn(rel['to_ref'],ids)
        self.assertEqual(set(range(1,241))-set(pages),{233,234,235,236,237,238,239,240})
        self.assertEqual(figures,164)
        report=json.loads((FOLDER/'import-report.json').read_text())
        self.assertEqual(report['input_blocks'],report['converted_blocks'])
        self.assertEqual(report['page_boundary_repairs'],[])
        self.assertEqual(report['missing_pdf_pages'],[])
        self.assertEqual(report['source_pdf_total_pages'],232)
        page200=json.loads((OUTPUT/'physics-form-one__page-0200.json').read_text())
        self.assertFalse(any(r['issue']=='page_boundary_repaired' for r in page200['review']))
        self.assertTrue(any(r['issue']=='transcript_sequence_needs_source_review' for r in page200['review']))

if __name__=='__main__':unittest.main()
