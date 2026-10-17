"""Rewrite speech-insert pronouns that sit in object/possessive positions.

{01}C{00}{00} (and 01/02) always prints "I", {01}C{04}{00} "we", {01}C{07}{00}/{0B} "you".
English needs "me/my", "us/our", "your" in other positions, so those inserts are
replaced by plain words (tl.py allows English to drop speech inserts).

usage: pronouns.py tl/msgsecNN.txt [...]   # edits batches in place, prints changes
"""
import re, sys

FORCE = {'let', 'make', 'making', 'help', 'hear'}      # always followed by an object
OBJ = FORCE | {
    'for', 'to', 'with', 'of', 'take', 'face', 'like', 'suspect', 'challenging', 'duel', 'by',
    'on', 'lend', 'follow', 'attacked', 'invite', 'tame', 'attack', 'teach', 'give', 'than',
    'alongside', 'in', 'avoiding', 'harm', 'kill', 'handle', 'underestimate', 'belittle',
    'persuade', 'spare', 'beating', 'why', 'eh', 'about', 'into', 'from', 'against', 'without',
    'beside', 'toward', 'upon', 'join', 'serve', 'cool', 'trust', 'fool', 'betray', 'mock',
    'mocking', 'surprise', 'pity', 'thank', 'tell', 'leave', 'send', 'ask', 'value', 'valued',
    'captured', 'capture', 'defeat', 'defeated', 'beat', 'meet', 'watch', 'understand', 'judge',
    'recommend', 'spared', 'haunt', 'remind', 'challenge', 'fight', 'call', 'despise', 'blame'}
# a following word that marks the pronoun as a subject ("on {I} rule" -> keep)
VERBS = {'am', 'will', 'can', 'could', 'would', 'must', 'shall', 'should', 'have', 'had', 'did',
         'do', 'don', 'won', 'cannot', 'rule', 'think', 'know', 'want', 'wish', 'was', 'were',
         'swear', 'feel', 'hope', 'believe', 'need', 'see', 'came', 'went', 'got', 'found',
         'took', 'made', 'also', 'alone', 'myself', 'personally', 'truly', 'really', 'still',
         'just', 'already', 'never', 'always', 'ever', 'only', 'once'}
POSS = {'{04}': 'our', '{07}': 'your', '{0B}': 'your'}
START = re.compile(r'(^|[.!?]|\{05\}|\n|[ev]\d)\s*$')

def fix(s, log):
    def poss(m):
        before, tok = m.group(1), m.group(2)
        w = POSS.get(tok, 'my')
        out = before + (w.capitalize() if START.search(before) else w)
        log.append((m.group(0)[-30:], out[-30:]))
        return out
    s = re.sub(r"([^\n]{0,12}?)\{01\}C(\{0[0-2]\}|\{04\}|\{07\}|\{0B\})\{00\}'s", poss, s)

    def obj(m):
        prev, sep, tok, gap, nxt = m.groups()
        p = re.sub(r'^[ev]\d', '', prev.lower())
        if p not in OBJ:
            return m.group(0)
        if p not in FORCE and gap.startswith(' ') and nxt.lower().strip(".,!?'") in VERBS:
            return m.group(0)
        out = prev + sep + ('us' if tok == '{04}' else 'me') + gap + nxt
        log.append((m.group(0), out))
        return out
    return re.sub(r"(\w+)(\W{1,2})\{01\}C(\{0[0-2]\}|\{04\})\{00\}(\s*)([\w']*)", obj, s)

if __name__ == '__main__':
    for path in sys.argv[1:]:
        log = []
        s = open(path, encoding='utf-8').read()
        t = fix(s, log)
        if t != s:
            open(path, 'w', encoding='utf-8').write(t)
        for a, b in log:
            print('%s: %s => %s' % (path, a, b))
