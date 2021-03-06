import sys
import re

fname = sys.argv[1]
file = open(fname)
good_line = re.compile(r'^.*\&.*\\$')

out_csv = ''

delimiters = r'&', r'$\pm$'
regexPattern = '|'.join(map(re.escape, delimiters))

for l in file.readlines():
    match = good_line.match(l.rstrip())
#    print(l)
    if not match:
        continue

    values = l.rstrip().replace(r'\\', '').replace(' ', '')

    values = re.split(regexPattern, values)

    out_csv += ','.join(values) + '\n'

file.close()
file_out = open(fname.replace('tex', 'csv'), 'w')
file_out.write(out_csv)
file_out.close()
