"""Resume one physical page at a time; leave compilation to the user."""
import argparse
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import book_tools as bt


def page_path(book, n, working=False):
    book=Path(book)
    if '__pages-' not in book.stem: raise ValueError('Expected a session range filename')
    doc=bt.read(book); subject=book.parent.parent
    folder=subject/'temp' if working else subject/bt.form_folder(doc['metadata']['form'])
    return folder/(book.stem.split('__pages-')[0]+f'__page-{n:04d}.json')


def matching(template, doc, n):
    for key in ['book_id','schema_version']:
        if doc[key]!=template[key]: raise ValueError('Page identity mismatch: '+key)
    if any(doc['source'].get(k)!=template['source'].get(k) for k in ['pdf','sha256','pdf_page_count']) or doc['schema']!=template['schema']:
        raise ValueError('Page source/schema mismatch; resolve explicitly')
    if doc['extraction']['requested_pdf_pages']!=[n] or [p['pdf_page'] for p in doc['pages']]!=[n]:
        raise ValueError('Standalone page must own only PDF page '+str(n))


def checked(doc, path, root, full=False):
    errors,_=bt.validate(copy.deepcopy(doc),path,root,check_files=full)
    if errors: raise ValueError('; '.join(errors))


def next_page(args):
    book=Path(args.book).resolve(); template=bt.read(book); root=Path(args.root).resolve()
    for n in sorted(template['extraction']['requested_pdf_pages']):
        finished=page_path(book,n)
        path=finished if finished.exists() else page_path(book,n,working=True)
        if path.exists():
            doc=bt.read(path); matching(template,doc,n); checked(doc,path,root)
            if doc['status'] in {'complete','complete_with_issues'}:
                if path!=finished: bt.save(path,doc,backup=True)
                continue
        else:
            original=next(p for p in template['pages'] if p['pdf_page']==n)
            if original['state']!='pending':
                raise ValueError('Existing range contains page content; preserve it and explicitly migrate it before starting page sequencing')
            doc=copy.deepcopy(template)
            doc['status']='partial';doc['pages']=[copy.deepcopy(original)]
            for field in ['groups','relations','figures','exclusions','review']: doc[field]=[]
            doc['extraction']['requested_pdf_pages']=[n]
            doc['extraction']['front_details_in_scope']=n==1
            doc['extraction']['runs']=[]
            doc['stats']=bt.stats(doc);checked(doc,path,root);bt.save(path,doc)
        print(json.dumps({'page':n,'page_json':str(path),'range_json':str(book),'status':doc['status'],
                          'all_pages_saved':False,'resume':bool(doc['pages'][0]['surfaces'])}))
        if args.prep:
            pdf=Path(doc['source']['pdf']);pdf=pdf if pdf.is_absolute() else bt.inside(root,str(pdf))
            bt.prep(SimpleNamespace(pdf=str(pdf),root=str(root),book_id=doc['book_id'],pages=str(n),dpi=args.dpi))
        if getattr(args,'measure',False):
            import measure
            pdf=Path(doc['source']['pdf']);pdf=pdf if pdf.is_absolute() else bt.inside(root,str(pdf))
            result=measure.measure_page(str(pdf),n,dpi=getattr(args,'measure_dpi',300),
                                        x0=getattr(args,'x0',None),x1=getattr(args,'x1',None))
            print(measure.format_measure(result))
        return
    print(json.dumps({'all_pages_saved':True,'session_json':str(book),'next_action':'report_finished_pages; user compiles manually'}))


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    for command in ['next']:
        p=sub.add_parser(command);p.add_argument('--book',required=True);p.add_argument('--root',default=bt.default_root())
        if command=='next':
            p.add_argument('--prep',action='store_true');p.add_argument('--dpi',type=int,default=150)
            p.add_argument('--measure',action='store_true',help='also print the numeric geometry table for the page')
            p.add_argument('--measure-dpi',type=int,default=300)
            p.add_argument('--x0',type=float,default=None);p.add_argument('--x1',type=float,default=None)
    args=parser.parse_args()
    try:
        if getattr(args,'dpi',150)<=0: raise ValueError('DPI must be positive')
        next_page(args)
    except (ValueError,KeyError,TypeError,OSError,AttributeError) as error:
        print(json.dumps({'errors':[str(error)]}));raise SystemExit(1)


if __name__=='__main__':main()
