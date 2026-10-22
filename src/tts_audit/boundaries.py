"""An independent, shifted segmentation checks boundary-adjacent differences."""
from difflib import SequenceMatcher
from .core import normalize


def reconcile(primary, secondary):
    """Deprioritize only a fully matched span with matching kana context on pass two.

    The two passes receive audio only. Labels are retained, never turned into a
    human 'correct' verdict. A missing second-pass warning alone is insufficient.
    """
    expected = normalize(secondary['expected_kana'])[0]
    actual = normalize(secondary['observed_kana'])[0]
    equal = [(i,j) for tag,i,j,_,_ in SequenceMatcher(None,expected,actual,autojunk=False).get_opcodes() if tag=='equal']
    checks=[]
    for finding in primary['findings']:
        if not finding.get('boundary_context'):
            continue
        lo,hi=finding['expected_span']
        context_lo,context_hi=max(0,lo-6),min(len(expected),hi+6)
        overlapping=[f['id'] for f in secondary['findings'] if f['script_start']<finding['script_end'] and f['script_end']>finding['script_start']]
        confirmed=any(i<=context_lo and j>=context_hi for i,j in equal)
        clean=secondary['alignment_equal_fraction']>=.8 and confirmed and not overlapping and not finding['expected_reading_uncertain']
        status='not_reproduced' if clean else 'persistent' if overlapping else 'inconclusive'
        finding['boundary_check']={'status':status,'second_pass_overlaps':overlapping,'context_match_confirmed':confirmed}
        variant = finding.get('reading_variant', {})
        finding['review_priority']='low_boundary' if clean else 'low_variant' if variant and not variant.get('explicit_reading_difference') else 'normal'
        checks.append({'finding_id':finding['id'],**finding['boundary_check']})
    return checks
