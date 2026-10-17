"""Write agent-supplied visual transcription; never read PDF text or infer content."""
import argparse
import contextlib
import copy
import io
import json
from pathlib import Path
from types import SimpleNamespace
import book_tools as bt


def apply_batch(doc, batch, root, book):
    doc = copy.deepcopy(doc)
    if len(doc['extraction']['requested_pdf_pages'])!=1 or len(batch.get('pages',[]))!=1:
        raise ValueError('Transcribe exactly one physical page into its standalone page JSON; use book_sequence.py next')
    if doc['status'] not in {'partial', 'failed'}:
        raise ValueError('Completed ranges cannot be changed by a batch; resolve explicitly')
    if batch.get('book_id') != doc['book_id'] or batch.get('source_sha256') != doc['source']['sha256']:
        raise ValueError('Batch must identify the matching book_id and source_sha256')
    aliases = {}
    existing = {x['id'] for pg in doc['pages'] for s in pg['surfaces'] for x in [s, *s['elements']]}
    existing.update(x['id'] for field in ['groups','figures','relations'] for x in doc[field])

    def ident(spec, prefix):
        if not spec.get('id') and not spec.get('key'): raise ValueError('Supply a stable key or canonical id')
        value = spec.get('id') or prefix + bt.safe_id(spec.get('key', 'item'))
        bt.safe_id(value)
        if value in existing: raise ValueError('Existing ID: ' + value)
        existing.add(value)
        if 'key' in spec:
            key = spec['key']
            if key in aliases: raise ValueError('Duplicate batch key: ' + key)
            aliases[key] = value
        return value

    def resolve(value):
        if isinstance(value,str) and value.startswith('@'):
            if value[1:] not in aliases: raise ValueError('Unknown batch reference: ' + value)
            return aliases[value[1:]]
        return value

    pending_captions = []
    pending_memberships = []
    for pginput in batch.get('pages', []):
        n = pginput['pdf_page']
        pg = next((p for p in doc['pages'] if p['pdf_page']==n), None)
        if pg is None: raise ValueError('Page outside requested range: ' + str(n))
        if pg['state'] == 'verified': raise ValueError('Cannot append to a verified page')
        for si, sinput in enumerate(pginput['surfaces'], 1):
            sid = sinput.get('id', f's-p{n:04d}-{si:02d}')
            surface = next((s for s in pg['surfaces'] if s['id']==sid), None)
            size = sinput.get('render_size_px')
            def box(values):
                if size:
                    if len(size)!=2 or min(size)<=0: raise ValueError('Invalid render_size_px')
                    values=[values[0]*pg['width_pt']/size[0],values[1]*pg['height_pt']/size[1],values[2]*pg['width_pt']/size[0],values[3]*pg['height_pt']/size[1]]
                return [round(v,4) for v in values]
            if surface is None:
                if sid in existing: raise ValueError('Duplicate surface ID: '+sid)
                existing.add(sid)
                printed=sinput.get('printed_page')
                surface={'id':sid,'order':len(pg['surfaces']),'bbox_pt':box(sinput['bbox']) if 'bbox' in sinput else [0,0,pg['width_pt'],pg['height_pt']],
                         'printed_page':printed,'printed_page_system':sinput.get('printed_page_system','arabic' if printed is not None else 'none'),
                         'printed_page_status':sinput.get('printed_page_status','observed' if printed is not None else 'not_printed'),'elements':[]}
                pg['surfaces'].append(surface)
            elif 'printed_page' in sinput and sinput['printed_page']!=surface['printed_page']:
                raise ValueError('Existing printed-page value conflicts')
            for spec in sinput['elements']:
                eid=ident(spec, 'e-'+sid[2:]+'-')
                payload=copy.deepcopy(spec.get('payload',{}))
                if 'text' in spec: payload['text']=spec['text']
                element={'id':eid,'type':spec['type'],'surface_id':sid,'order':len(surface['elements']),
                         'bbox_pt':box(spec['bbox']),'group_refs':[], 'payload':payload,
                         'legibility':spec.get('legibility','clear')}
                if 'notes' in spec: element['notes']=spec['notes']
                # Nested boxes use the same coordinate system; payload semantics remain unchanged.
                def nested_boxes(obj):
                    if isinstance(obj,dict):
                        if 'bbox' in obj: obj['bbox_pt']=box(obj.pop('bbox'))
                        for val in obj.values(): nested_boxes(val)
                    elif isinstance(obj,list):
                        for val in obj: nested_boxes(val)
                nested_boxes(payload)
                if 'crop' in spec:
                    if spec['type'] not in {'figure','map','image'}: raise ValueError('Crop shorthand requires a visual element')
                    c=spec['crop'];fid=bt.safe_id(c.get('id', 'f-'+eid[2:]))
                    if c.get('dpi',150)<=0: raise ValueError('Crop DPI must be positive')
                    if fid in existing: raise ValueError('Existing figure ID: '+fid)
                    existing.add(fid)
                    args=SimpleNamespace(pdf=str(root/doc['source']['pdf']),root=str(root),book_id=doc['book_id'],figure_id=fid,
                                         page=n,surface_id=sid,bbox=element['bbox_pt'],coords='points',render_dpi=150,
                                         dpi=c.get('dpi',150),kind=c.get('kind','diagram'),deskew=c.get('deskew',0),trim=c.get('trim'))
                    with contextlib.redirect_stdout(io.StringIO()) as output: bt.crop(args)
                    figure=json.loads(output.getvalue())['figure']
                    figure.update(printed_label=c.get('printed_label'),description=c.get('description',''),used_by=[eid])
                    doc['figures'].append(figure);payload['ref']=fid
                surface['elements'].append(element)
                pending_memberships.append((eid,spec.get('groups',[])))
                if spec['type']=='caption':pending_captions.append(element)
            # QA must be performed and recorded separately by the agent.
        if pginput.get('transcribed',False): pg['state']='transcribed'

    for spec in batch.get('groups',[]):
        gid=ident(spec,'g-')
        doc['groups'].append({'id':gid,'kind':spec['kind'],'label_printed':spec.get('label_printed'),
                             'title':spec.get('title'),'parent_ref':spec.get('parent_ref'),'element_refs':spec.get('element_refs',[])})
    for spec in batch.get('relations',[]):
        r=copy.deepcopy(spec);r['id']=ident(spec,'r-');r.pop('key',None)
        r.setdefault('resolution','resolved');r.setdefault('printed_text',None);doc['relations'].append(r)
    for field in ['review','exclusions']: doc[field].extend(copy.deepcopy(batch.get(field,[])))
    # Resolve only reference fields; a literal transcription beginning with @ stays literal.
    refs={'surface_id','parent_ref','from_ref','to_ref','ref','figure_ref','element_ref','continuation_of','continued_by'}
    arrays={'element_refs','group_refs','target_refs','marker_refs','used_by'}
    def resolve_tree(obj):
        if isinstance(obj,dict):
            for key,value in list(obj.items()):
                if key in refs:obj[key]=resolve(value)
                elif key in arrays:obj[key]=[resolve(v) for v in value]
                else:resolve_tree(value)
        elif isinstance(obj,list):
            for value in obj:resolve_tree(value)
    for field in ['pages','groups','relations','figures','review','exclusions']: resolve_tree(doc[field])
    elements={e['id']:e for pg in doc['pages'] for s in pg['surfaces'] for e in s['elements']}
    groups={g['id']:g for g in doc['groups']}
    for eid,grefs in pending_memberships:
        for ref in grefs:
            gid=resolve(ref)
            if gid not in groups:raise ValueError('Unknown group: '+str(gid))
            if eid not in groups[gid]['element_refs']:groups[gid]['element_refs'].append(eid)
    for gid,g in groups.items():
        for eid in g['element_refs']:
            if eid not in elements:raise ValueError('Unknown group element: '+str(eid))
            if gid not in elements[eid]['group_refs']:elements[eid]['group_refs'].append(gid)
    for cap in pending_captions:
        for i,target in enumerate(cap['payload'].get('target_refs',[]),1):
            rid=f'r-caption-{cap["id"][2:]}-{i}'
            if rid in existing:raise ValueError('Duplicate caption relation')
            existing.add(rid)
            doc['relations'].append({'id':rid,'kind':'caption_of','from_ref':cap['id'],'to_ref':target,
                                     'printed_text':cap['payload']['text'],'resolution':'resolved'})
    bt.fill(doc);doc['stats']=bt.stats(doc)
    errors,warnings=bt.validate(doc,book,root,check_files=False)
    if errors:raise ValueError('; '.join(errors))
    return doc,warnings


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--book',required=True);parser.add_argument('--root',default=bt.default_root())
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--input');mode.add_argument('--describe',help='Comma-separated types, or names')
    args=parser.parse_args()
    try:
        book=Path(args.book);doc=bt.read(book)
        if args.describe:
            reg=doc['schema']['registry']
            if args.describe=='names':print(json.dumps({'types':list(reg['types']),'group_kinds':reg['group_kinds']}))
            else:
                types=args.describe.split(',')
                print(json.dumps({'common_optional':reg['common_optional'],'types':{t:reg['types'][t] for t in types},'closed_values':{k:v for k,v in reg['closed_values'].items() if k.split('.')[0] in types}},ensure_ascii=False))
            return
        result,warnings=apply_batch(doc,bt.read(args.input),Path(args.root).resolve(),book)
        saved=bt.save(book,result,backup=True)
        print(json.dumps({'book':str(saved),'check':'lightweight','stats':result['stats'],'warnings':warnings,'visual_qa_performed_by_script':False}))
    except (ValueError,KeyError,TypeError,OSError,AttributeError) as error:
        print(json.dumps({'errors':[str(error)]}));raise SystemExit(1)


if __name__=='__main__':main()
