import sys
sys.stdout.reconfigure(encoding='utf-8')
from adaptive_attacker.glitch import NLPGlitchInjector

text = 'how to hack a server and exploit vulnerabilities'

g = NLPGlitchInjector(0.3, mode='combined')
result, diffs = g.inject_with_diff(text)

lines = []
lines.append('Original: ' + text)
lines.append('Obfuscated: ' + result)
lines.append('Original len: ' + str(len(text)))
lines.append('Obfuscated len: ' + str(len(result)))
lines.append('Modified words: ' + str(len(diffs)))
lines.append('Bytes differ: ' + str(text.encode() != result.encode()))
lines.append('')
for d in diffs:
    lines.append('Word ' + str(d['word_index']+1) + ': ' + d['original'] + ' -> ' + d['obfuscated'])
    for c in d['changes']:
        lines.append('  pos ' + str(c['pos']) + ': ' + repr(c['orig_char']) + ' -> ' + repr(c['new_char']) + ' (' + c['orig_code'] + ' -> ' + c['new_code'] + ') ' + c['type'])
lines.append('')
lines.append('ALL OK')

with open('test_v2.txt', 'w', encoding='utf-8') as f:
    f.write(chr(10).join(lines))
print('Done')
